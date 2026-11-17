"""Helpers for the opt-in PostgreSQL tests of the market-data projection (not collected as a test module).

Rules (the project's, restated): database `finweb_dev` only, through the integration variables, only inside
disposable `finweb_it_*` schemas this class creates and drops; no role or database is created or altered; the
application role (`FINWEB_PG_APP_USER`, e.g. `finweb_app`) is granted only what the production grant spec lists, and
the cleanup fails loudly if a schema is left behind.
"""

import importlib.util
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from persistence import connection, migrator  # noqa: E402

APP_USER_VAR = "FINWEB_PG_APP_USER"


def skip_reason(need_app_role: bool = True) -> str:
    missing = list(connection.missing_env_vars(os.environ))
    if need_app_role and not os.environ.get(APP_USER_VAR):
        missing.append(APP_USER_VAR + " (the least-privilege role, e.g. finweb_app)")
    if missing:
        return "the PostgreSQL tests are opt-in; set: " + "; ".join(missing)
    if importlib.util.find_spec("psycopg") is None:
        return "psycopg is not installed (the owner runs `uv sync --python 3.12`)"
    return ""


def grant_statements(schema: str, role: str):
    """The production grant spec (the one constant `APP_GRANTS` in the least-privilege test), filled in."""
    import test_postgres_least_privilege as lp  # noqa: PLC0415 (only the constant is used)

    return [g.format(schema=schema, role=role) for g in lp.APP_GRANTS]


class PgSchema:
    """One disposable schema: created and migrated by the OWNER role, optionally granted to the app role."""

    def __init__(self, prefix: str = "finweb_it_md_"):
        self.schema = prefix + uuid.uuid4().hex[:12]
        self.owner: Any = None
        self.app_role: Optional[str] = os.environ.get(APP_USER_VAR)

    def open(self, grant: bool = True) -> "PgSchema":
        self.owner = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        self.owner.execute('CREATE SCHEMA "%s"' % self.schema)
        self.owner.execute('SET search_path TO "%s"' % self.schema)
        migrator.apply_migrations(self.owner)
        if grant and self.app_role:
            self.grant()
        return self

    def grant(self) -> None:
        for statement in grant_statements(self.schema, self.app_role or ""):
            self.owner.execute(statement)

    def app_connection(self, autocommit: bool = True) -> Any:
        conninfo = connection.build_conninfo(
            dbname=os.environ[connection.DATABASE_VAR], user=self.app_role or "",
            socket=os.environ.get(connection.SOCKET_VAR) or None, host=os.environ.get(connection.HOST_VAR) or None,
            port=os.environ.get(connection.PORT_VAR) or None)
        conn = connection.connect(conninfo, autocommit=autocommit)
        conn.execute('SET search_path TO "%s"' % self.schema)
        if not autocommit:
            conn.commit()
        return conn

    def owner_connection(self) -> Any:
        conn = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        conn.execute('SET search_path TO "%s"' % self.schema)
        return conn

    def close(self) -> None:
        try:
            self.owner.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % self.schema)
            left = self.owner.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name = %s",
                                      (self.schema,)).fetchall()
            assert left == [], "disposable schema was not dropped: %r" % (left,)
        finally:
            self.owner.close()


def insert_identity(conn: Any, ident: Any) -> None:
    """Write the identity registry's issuers, instruments and listings into the schema (no identity writer exists
    in CP1; the observation tables reference `listing`)."""
    issuers, instruments, listings = ident.snapshot()
    for i in issuers:
        conn.execute("INSERT INTO issuer VALUES (%s, %s, %s)", (i.issuer_id, i.name, i.issuer_domicile))
    for n in instruments:
        conn.execute("INSERT INTO instrument VALUES (%s, %s, %s)", (n.instrument_id, n.issuer_id, n.security_type.value))
    for listing in listings:
        conn.execute("INSERT INTO listing VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                     (listing.listing_id, listing.instrument_id, listing.mic, listing.exchange, listing.ticker,
                      listing.trading_currency.code, listing.figi, listing.is_active))
