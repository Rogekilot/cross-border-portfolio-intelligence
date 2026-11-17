"""PostgreSQL account/session and owner-scoped immutable synthetic sandbox storage.

No global connection and no in-memory identity fallback: each call reconnects to the
configured schema. All resource queries start with the authenticated owner join.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import uuid
from contextlib import contextmanager, nullcontext
from dataclasses import replace

import psycopg

from domain.replay import SequencedEvent
from marketdata.canonical import canonical_json, sha256_hex
from persistence import connection, ledger_replay_store, ledger_store
from web_api.auth import digest_token, new_token

MODE = "LOCAL_SYNTHETIC_ACCOUNT"
# Separate CP7 application grants: never widen the historical ledger-only grants.
APP_GRANTS = (
    "GRANT USAGE ON SCHEMA {schema} TO {role}",
    "GRANT SELECT, INSERT ON {schema}.app_user, {schema}.portfolio, {schema}.account, "
    "{schema}.issuer, {schema}.instrument, {schema}.listing, {schema}.ledger_event, "
    "{schema}.web_identity, {schema}.web_saved_sandbox TO {role}",
    "GRANT SELECT, INSERT, UPDATE, DELETE ON {schema}.web_session, {schema}.web_auth_rate TO {role}",
    "GRANT USAGE ON SEQUENCE {schema}.ledger_event_ledger_seq_seq TO {role}",
    "GRANT SELECT, INSERT ON {schema}.web_portfolio_revision, {schema}.benchmark_selection TO {role}",
    "GRANT SELECT, INSERT ON {schema}.web_csv_report, {schema}.web_csv_source_key TO {role}",
    "GRANT USAGE ON SEQUENCE {schema}.web_portfolio_revision_seq_seq, {schema}.benchmark_selection_seq_seq TO {role}",
)


class AccountStoreError(Exception):
    def __init__(self, status, code, detail):
        self.status, self.code, self.detail = status, code, detail


def not_found():
    raise AccountStoreError(404, "NOT_FOUND", "Portfolio or packet is not available in this account")


@contextmanager
def _saved_capacity_error(schema):
    try:
        yield
    except psycopg.errors.CheckViolation as error:
        if (str(error).split("\n", 1)[0] == "F2_PORTFOLIO_CAPACITY"
                and error.diag.constraint_name == "gw_web_portfolio_capacity"
                and error.diag.schema_name == schema and error.diag.table_name == "web_saved_sandbox"):
            raise AccountStoreError(429, "PORTFOLIO_CAPACITY_REACHED", "Per-account saved sandbox capacity reached") from None
        raise


class WebAccountStore:
    def __init__(self, conninfo, schema, *, clock=None, opener=None):
        """`opener`, if given, returns a NEW autocommit connection and replaces the connection-string route (F1 R7: the real-mode launcher opens
        a REAL target's connection with a password from the terminal prompt, which is never part of a stored connection string). Every check
        after the connection is made is the same."""
        if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", schema):
            raise ValueError("A validated PostgreSQL schema is required")
        self.conninfo, self.schema, self.opener = conninfo, schema, opener
        self.clock = clock or (lambda: dt.datetime.now(dt.timezone.utc))

    def connect(self):
        conn = self.opener() if self.opener is not None else connection.connect(self.conninfo, autocommit=True)
        role = conn.execute("SELECT r.rolsuper,n.nspowner=r.oid FROM pg_roles r "
                            "JOIN pg_namespace n ON n.nspname=%s WHERE r.rolname=current_user", (self.schema,)).fetchone()
        if role is None or any(role):
            conn.close()
            raise AccountStoreError(503, "UNSAFE_DATABASE_ROLE", "Account runtime requires a non-owner, non-superuser application role")
        conn.execute('SET search_path TO "' + self.schema + '", pg_temp')
        conn.execute("SET statement_timeout TO '15000ms'")
        return conn

    def rate_limit(self, action, peer, username):
        """Two durable buckets bound unknown-user attempts and reconnect/restart abuse."""
        now = self.clock()
        buckets = sorted((hashlib.sha256((action + ":peer:" + peer).encode()).hexdigest(),
                          hashlib.sha256((action + ":name:" + username).encode()).hexdigest()))
        rejected = False
        with self.connect() as conn, conn.transaction():
            # Prune only expired rate state, not sessions or portfolio history.
            conn.execute("DELETE FROM web_auth_rate WHERE window_start < %s", (now - dt.timedelta(hours=1),))
            for key in buckets:
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (key,))
                row = conn.execute("SELECT window_start, attempts FROM web_auth_rate WHERE bucket_hash=%s", (key,)).fetchone()
                start, count = (now, 1) if row is None or now - row[0] >= dt.timedelta(minutes=15) else (row[0], row[1] + 1)
                count = min(count, 1000)
                conn.execute("INSERT INTO web_auth_rate VALUES (%s,%s,%s) ON CONFLICT (bucket_hash) "
                             "DO UPDATE SET window_start=EXCLUDED.window_start, attempts=EXCLUDED.attempts", (key, start, count))
                rejected = rejected or count > (20 if action == "login" else 10)
        if rejected:
            raise AccountStoreError(429, "AUTH_RATE_LIMITED", "Authentication attempt limit reached; wait fifteen minutes")

    def register(self, username, password_hash):
        user_id, now = uuid.uuid4(), self.clock()
        with self.connect() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s || current_schema(),0))", ("web-register",))
            if conn.execute("SELECT 1 FROM web_identity WHERE username=%s", (username,)).fetchone():
                raise AccountStoreError(409, "USERNAME_UNAVAILABLE", "Username is unavailable")
            if conn.execute("SELECT count(*) FROM web_identity").fetchone()[0] >= 1000:
                raise AccountStoreError(429, "ACCOUNT_CAPACITY_REACHED", "Local account capacity reached")
            conn.execute("INSERT INTO app_user (user_id) VALUES (%s)", (user_id,))
            conn.execute("INSERT INTO web_identity VALUES (%s,%s,%s,%s)", (user_id, username, password_hash, now))
        return {"user_id": str(user_id), "username": username}

    def credential(self, username):
        with self.connect() as conn:
            row = conn.execute("SELECT user_id,username,password_hash FROM web_identity WHERE username=%s", (username,)).fetchone()
        return None if row is None else ({"user_id": str(row[0]), "username": row[1]}, row[2])

    def start_session(self, user, lifetime):
        token, now = new_token(), self.clock()
        with self.connect() as conn, conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s || current_schema(),0))", ("web-user:" + user["user_id"],))
            conn.execute("DELETE FROM web_session WHERE user_id=%s AND expires_at<=%s", (uuid.UUID(user["user_id"]), now))
            # At most eight active sessions per user, with oldest eviction.
            conn.execute("DELETE FROM web_session WHERE token_hash IN (SELECT token_hash FROM web_session "
                         "WHERE user_id=%s ORDER BY created_at DESC,token_hash OFFSET 7)", (uuid.UUID(user["user_id"]),))
            conn.execute("INSERT INTO web_session VALUES (%s,%s,%s,%s)",
                         (digest_token(token), uuid.UUID(user["user_id"]), now, now + dt.timedelta(seconds=lifetime)))
        return token

    def session_user(self, token):
        with self.connect() as conn:
            row = conn.execute("SELECT i.user_id,i.username FROM web_session s JOIN web_identity i USING(user_id) "
                               "WHERE s.token_hash=%s AND s.expires_at>%s", (digest_token(token), self.clock())).fetchone()
        return None if row is None else {"user_id": str(row[0]), "username": row[1]}

    def logout(self, token):
        with self.connect() as conn:
            conn.execute("DELETE FROM web_session WHERE token_hash=%s", (digest_token(token),))

    def list_portfolios(self, user_id):
        with self.connect() as conn:
            rows = conn.execute("SELECT s.portfolio_id,s.name,p.reporting_currency,s.created_at,s.request_json, "
                "(SELECT r.as_of FROM web_portfolio_revision r WHERE r.portfolio_id=s.portfolio_id ORDER BY r.revision_seq DESC LIMIT 1) "
                "FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s "
                "ORDER BY s.created_at,s.portfolio_id LIMIT 32", (uuid.UUID(user_id),)).fetchall()
        return [{"portfolio_id": str(row[0]), "name": row[1], "mode": MODE, "synthetic": True,
                 "reporting_currency": row[2], "as_of": str(row[5]) if row[5] is not None else json.loads(row[4])["as_of"], "created_at": row[3]}
                for row in rows]

    @staticmethod
    def _identities(conn, world):
        issuers, instruments, listings = world.resolver.snapshot()
        tables = (
            ("issuer", "issuer_id", [(i.issuer_id, i.name, i.issuer_domicile) for i in issuers]),
            ("instrument", "instrument_id", [(i.instrument_id, i.issuer_id, i.security_type.value) for i in instruments]),
            ("listing", "listing_id", [(i.listing_id, i.instrument_id, i.mic, i.exchange, i.ticker,
                                      i.trading_currency.code, i.figi, i.is_active) for i in listings]),
        )
        for table, key, rows in tables:
            for row in rows:
                conn.execute("INSERT INTO " + table + " VALUES (" + ",".join(["%s"] * len(row)) + ") ON CONFLICT DO NOTHING", row)
                if tuple(conn.execute("SELECT * FROM " + table + " WHERE " + key + "=%s", (row[0],)).fetchone() or ()) != row:
                    raise AccountStoreError(503, "SYNTHETIC_IDENTITY_CONFLICT", "Stored identities do not match the explicit fictional sandbox")

    @staticmethod
    def _persisted(item):
        value = item.snapshot()
        value.update(mode=MODE, persisted=True)
        value["limitations"] = [note for note in value["limitations"] if not note.startswith("EPHEMERAL_GUEST:")]
        value["limitations"].insert(1, "SAVED_SYNTHETIC_SANDBOX: saved to this account; never an actual holding or real-market claim.")
        return replace(item, snapshot_json=canonical_json(value))

    def create_portfolio(self, user_id, body, world, *, connection=None, portfolio_id=None):
        opening_date = world.as_of
        if "opening_date" in body:
            value = body["opening_date"]
            try:
                if type(value) is not str or len(value) != 10:
                    raise ValueError("Non-canonical opening date")
                opening_date = dt.date.fromisoformat(value)
                if opening_date.isoformat() != value or opening_date > world.as_of:
                    raise ValueError("Opening date outside the fictional source as-of")
            except ValueError:
                raise AccountStoreError(422, "INVALID_OPENING_DATE", "Opening date must be a canonical ISO date no later than the fictional valuation date") from None
        ident, now = uuid.uuid4() if portfolio_id is None else uuid.UUID(str(portfolio_id)), self.clock()
        context = self.connect() if connection is None else nullcontext(connection)
        with _saved_capacity_error(self.schema), context as conn, conn.transaction():
            owner = uuid.UUID(user_id)
            conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s || current_schema(),0))", ("web-user:" + user_id,))
            count = conn.execute("SELECT count(*) FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s", (owner,)).fetchone()[0]
            if count >= 32:
                raise AccountStoreError(429, "PORTFOLIO_CAPACITY_REACHED", "Per-account saved sandbox capacity reached")
            self._identities(conn, world)
            conn.execute("INSERT INTO portfolio VALUES (%s,%s,%s)", (ident, owner, body["reporting_currency"]))
            account_id = uuid.uuid5(ident, "guest-account")
            conn.execute("INSERT INTO account VALUES (%s,%s,%s)", (account_id, ident, "Explicit fictional sandbox"))
            events = []
            for entry in world.opening_events(ident, body):
                # Unlike the ephemeral adapter, real storage needs a distinct idempotency key per opening row.
                event = replace(entry.event, event_date=opening_date,
                    source_reference="CP7 saved synthetic opening:" + str(entry.event.event_id))
                appended = ledger_store.append_event(conn, event)
                events.append(SequencedEvent(appended.ledger_seq, appended.event))
            item = self._persisted(world.create(ident, body, ledger_events=events))
            request = {**body, "as_of": world.as_of.isoformat(), "source_sha256": world.input_sha256,
                       "calendar_sha256": world.calendar_sha256}
            conn.execute("INSERT INTO web_saved_sandbox VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (ident, MODE, body["name"], canonical_json(request), item.snapshot_json,
                 sha256_hex(item.snapshot_json.encode()), max(event.ledger_seq for event in events), now))
        return item

    def get_portfolio(self, user_id, portfolio_id, world, *, revision_id=None):
        from persistence.web_workspace_store import WorkspaceStore
        return WorkspaceStore(self, world).read(user_id, portfolio_id, revision_id=revision_id)

    def workspace(self, user_id, portfolio_id, world, *, revision_id=None):
        from persistence.web_workspace_store import WorkspaceStore
        return WorkspaceStore(self, world).workspace(user_id, portfolio_id, revision_id=revision_id)

    def command(self, user_id, portfolio_id, body, world, *, preferences=False, preview=False):
        from persistence.web_workspace_store import WorkspaceStore
        return WorkspaceStore(self, world).command(user_id, portfolio_id, body, preferences=preferences, preview=preview)

    def _get_initial_portfolio(self, user_id, portfolio_id, world):
        try:
            ident = uuid.UUID(portfolio_id)
        except (ValueError, TypeError, AttributeError):
            not_found()
        with self.connect() as conn:
            # Ownership is checked BEFORE ledger/source/financial/proof work.
            row = conn.execute("SELECT s.request_json,s.snapshot_json,s.snapshot_sha256,s.ledger_version "
                "FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) "
                "WHERE p.user_id=%s AND s.portfolio_id=%s", (uuid.UUID(user_id), ident)).fetchone()
            if row is None:
                not_found()
            try:
                request = json.loads(row[0])
                matches = (sha256_hex(row[1].encode()) == row[2] and request["source_sha256"] == world.input_sha256
                    and request["calendar_sha256"] == world.calendar_sha256 and request["as_of"] == world.as_of.isoformat())
            except (ValueError, KeyError, TypeError):
                matches = False
            if not matches:
                raise AccountStoreError(503, "SAVED_SOURCE_DIFFERS", "Saved source identity cannot be reproduced by this version")
            current = ledger_replay_store.current_ledger_version(conn, ident)
            try:
                if row[3] > current:
                    raise ValueError("uncommitted ledger pin")
                ledger_replay_store.require_committed_boundary(conn, ident, row[3])
            except ValueError:
                raise AccountStoreError(503, "SAVED_RESULT_DIFFERS", "Saved ledger pin is not a committed transaction boundary") from None
            columns = ",".join("e." + col for col in ledger_store.EVENT_COLUMNS)
            records = conn.execute("SELECT e.ledger_seq," + columns + " FROM ledger_event e JOIN account a USING(account_id) "
                "JOIN portfolio p ON p.portfolio_id=a.portfolio_id WHERE p.user_id=%s AND p.portfolio_id=%s "
                "AND e.ledger_seq<=%s ORDER BY e.ledger_seq", (uuid.UUID(user_id), ident, row[3])).fetchall()
            events = tuple(SequencedEvent(*ledger_store.row_to_event(tuple(record))) for record in records)
        try:
            item = self._persisted(world.create(ident, request, ledger_events=events))
        except (ValueError, KeyError, TypeError):
            raise AccountStoreError(503, "SAVED_RESULT_DIFFERS", "Saved financial inputs cannot be reconstructed") from None
        if item.snapshot_json != row[1]:
            raise AccountStoreError(503, "SAVED_RESULT_DIFFERS", "Saved financial facts or proof no longer reproduce exactly")
        return item
