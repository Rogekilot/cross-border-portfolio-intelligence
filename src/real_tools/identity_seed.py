"""F1 R6: the owner-run IDENTITY SEED of the real database (PM decision at R4b; STATUS "Open for R6/R8"; design 6.4, 7.1 R4b/R5).

The observation tables reference `listing`, and `listing` references `instrument` and `issuer`. The executor holds NO grant on those three tables
(R3 fix round, M-1: they have no root, no fence and no journal, so an executor write would be a durable lease-less write), and the loader writes
only `md_*`. So the identity rows reach the real database by ONE owner-run, idempotent step: this tool, run by the owner in the owner's terminal as
the superuser (`SET ROLE` the schema owner), never by an agent session and never by a runtime tool.

THE CHECK. Before it opens a connection the tool rebuilds the identity resolver from the seed file and requires its `identity_digest`
(`persistence.real_digests.identity_digest`, sorted by canonical-JSON text: TR4B-M2) to equal the `identity_digest` of the verified proposal's
snapshot. The rows written are therefore the rows the snapshot's digest names, or nothing is written (`RW_SEED_DIGEST_DIFFERS`).

IDEMPOTENT. Each row is `INSERT ... ON CONFLICT (primary key) DO NOTHING`, then read back by key and compared: a row that is already there and equal is
left alone, a row that is there and DIFFERENT refuses the whole seed (`RW_SEED_CONFLICT`; one transaction, nothing is written). Re-running the same seed
writes nothing and says so.

THE SEED FILE (`finweb.real_identity_seed/1`) is canonical JSON of the registry's rows (issuers, instruments, listings, identifier rows): written from a
resolver by `seed_bytes` (the qualification run's owner step), read by `read_seed`. The tables hold fewer columns than the digest covers (no share-class
or composite FIGI, no identifier rows), so the tool also READS BACK every row of the seed after the writes, in the same transaction, and requires it to
equal the seed's row on the STORED columns (a difference rolls the whole seed back). What the tables cannot hold (share-class and composite FIGI,
identifier rows) is not in the database to read back: it is held to the proposal's digest only through the seed file, which `check_digest` compares.

Tested on TEST installs only (E11: the owner of a disposable database). The real database is reached only by `main`, whose database name is the
real install's constant; it takes no credential option and no environment variable (the prompt alone).
"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
import json
import sys
import uuid

from domain.currency import CurrencyCode
from domain.instrument import Instrument, Issuer, Listing, SecurityType
from marketdata.canonical import canonical_json
from marketdata.resolver import IdentifierRow
from persistence import prompt_route, real_preflight as pf, real_proposal
from persistence.real_digests import identity_digest
from persistence.real_workspace_context import identifier

SEED_SCHEMA = "finweb.real_identity_seed/1"
EXIT_OK, EXIT_REFUSED = 0, 2


class SeedError(ValueError):
    def __init__(self, code, detail=""):
        self.code, self.detail = code, detail
        super().__init__(code if not detail else "%s: %s" % (code, detail))


class RowsResolver:
    """The two reads `identity_digest` makes of a registry, over fixed rows."""

    def __init__(self, issuers, instruments, listings, identifier_rows):
        self._i, self._n, self._l, self._r = tuple(issuers), tuple(instruments), tuple(listings), tuple(identifier_rows)

    def snapshot(self):
        return self._i, self._n, self._l

    def identifier_rows(self, listing_id=None):
        return tuple(r for r in self._r if listing_id is None or r.listing_id == listing_id)


def _ordered(rows):
    return sorted(rows, key=lambda row: canonical_json(row))


def seed_bytes(resolver):
    """The seed file's bytes for a resolver (anything with `snapshot()` and `identifier_rows()`). Deterministic: every list is sorted by the canonical
    text of its rows."""
    issuers, instruments, listings = resolver.snapshot()
    body = {
        "schema": SEED_SCHEMA,
        "issuers": _ordered([str(i.issuer_id), i.name, i.issuer_domicile] for i in issuers),
        "instruments": _ordered([str(i.instrument_id), str(i.issuer_id), i.security_type.value, i.share_class_figi] for i in instruments),
        "listings": _ordered([str(x.listing_id), str(x.instrument_id), x.mic, x.exchange, x.ticker, x.trading_currency.code, x.figi, x.is_active,
                              x.composite_figi] for x in listings),
        "identifiers": _ordered([str(r.listing_id), r.scheme, r.value, r.qualifier, None if r.valid_from is None else r.valid_from.isoformat(),
                                 None if r.valid_to is None else r.valid_to.isoformat(), r.asserted_by] for r in resolver.identifier_rows())}
    return canonical_json(body).encode("utf-8")


def read_seed(data):
    """A `RowsResolver` from seed-file bytes; anything malformed is `RW_SEED_SHAPE`."""
    try:
        body = json.loads(data.decode("utf-8"))
        if not isinstance(body, dict) or body.get("schema") != SEED_SCHEMA or set(body) != {"schema", "issuers", "instruments", "listings", "identifiers"}:
            raise ValueError("schema")
        issuers = [Issuer(uuid.UUID(a), b, c) for a, b, c in body["issuers"]]
        instruments = [Instrument(uuid.UUID(a), uuid.UUID(b), SecurityType(c), d) for a, b, c, d in body["instruments"]]
        listings = [Listing(uuid.UUID(a), uuid.UUID(b), c, d, e, CurrencyCode(f), g, h, i) for a, b, c, d, e, f, g, h, i in body["listings"]]
        rows = [IdentifierRow(uuid.UUID(a), b, c, d, None if e is None else dt.date.fromisoformat(e), None if f is None else dt.date.fromisoformat(f), g)
                for a, b, c, d, e, f, g in body["identifiers"]]
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
        raise SeedError("RW_SEED_SHAPE", "the seed file is not a %s document (%s)" % (SEED_SCHEMA, type(error).__name__)) from error
    return RowsResolver(sorted(issuers, key=lambda x: str(x.issuer_id)), sorted(instruments, key=lambda x: str(x.instrument_id)),
                        sorted(listings, key=lambda x: str(x.listing_id)), rows)


def check_digest(resolver, expected):
    """Refuse unless the resolver's identity digest is the snapshot's. Pure."""
    got = identity_digest(resolver)
    if got != expected:
        raise SeedError("RW_SEED_DIGEST_DIFFERS", "the seed's identity digest %s is not the snapshot's %s" % (got[:16], str(expected)[:16]))
    return got


def snapshot_identity_digest(proposal_bytes):
    """The `identity_digest` of a VERIFIED proposal's snapshot."""
    return real_proposal.verify_proposal(proposal_bytes).snapshot.content["identity_digest"]


@dataclass(frozen=True)
class SeedResult:
    inserted: dict
    present: dict
    others: dict

    @property
    def lines(self):
        return tuple("%s: %d written, %d already present and equal, %d other row(s) in the table (untouched)" % (
            t, self.inserted[t], self.present[t], self.others[t]) for t in ("issuer", "instrument", "listing"))


def _stored(resolver):
    issuers, instruments, listings = resolver.snapshot()
    return (
        ("issuer", "issuer_id", "(issuer_id,name,issuer_domicile)", "%s,%s,%s", [(i.issuer_id, i.name, i.issuer_domicile) for i in issuers]),
        ("instrument", "instrument_id", "(instrument_id,issuer_id,security_type)", "%s,%s,%s",
         [(i.instrument_id, i.issuer_id, i.security_type.value) for i in instruments]),
        ("listing", "listing_id", "(listing_id,instrument_id,mic,exchange,ticker,trading_currency,figi,is_active)", "%s,%s,%s,%s,%s,%s,%s,%s",
         [(x.listing_id, x.instrument_id, x.mic, x.exchange, x.ticker, x.trading_currency.code, x.figi, x.is_active) for x in listings]))


def apply_seed(conn, schema, resolver, expected_digest):
    """Write the resolver's issuers, instruments and listings into `schema`, as the owner (the caller's connection: `SET ROLE` the schema owner),
    in ONE transaction. The digest is checked first, so a mismatch writes nothing. Idempotent: an equal existing row is left alone, a different one
    refuses. Returns a `SeedResult`."""
    schema = identifier(schema)
    check_digest(resolver, expected_digest)
    inserted, present, others = {}, {}, {}
    with conn.transaction():
        for table, key, columns, marks, rows in _stored(resolver):
            inserted[table] = present[table] = 0
            for row in rows:
                done = conn.execute('INSERT INTO "%s".%s %s VALUES (%s) ON CONFLICT (%s) DO NOTHING RETURNING 1' % (schema, table, columns, marks, key), row).fetchone()
                if done is not None:
                    inserted[table] += 1
                    continue
                stored = conn.execute('SELECT %s FROM "%s".%s WHERE %s=%%s' % (columns.strip("()"), schema, table, key), (row[0],)).fetchone()
                if stored is None or tuple(stored) != tuple(row):
                    raise SeedError("RW_SEED_CONFLICT", "%s %s already exists with other values; nothing was written" % (table, row[0]))
                present[table] += 1
            # READ BACK (still inside the transaction, so a difference rolls everything back): every row of the seed, as the table now stores it,
            # equals the seed's row on the stored columns. The columns the tables lack (share-class and composite FIGI, identifier rows) cannot be
            # read back; they are held to the proposal's digest only through the seed file (`check_digest`).
            keys = [row[0] for row in rows]
            stored_rows = {tuple(r)[0]: tuple(r) for r in conn.execute(
                'SELECT %s FROM "%s".%s WHERE %s = ANY(%%s)' % (columns.strip("()"), schema, table, key), (keys,)).fetchall()}
            for row in rows:
                if stored_rows.get(row[0]) != tuple(row):
                    raise SeedError("RW_SEED_CONFLICT", "%s %s read back with other values than the seed's; nothing was written" % (table, row[0]))
            others[table] = conn.execute('SELECT count(*) FROM "%s".%s' % (schema, table)).fetchone()[0] - len(rows)
    return SeedResult(inserted, present, others)


# ---- the command line (owner only; the real database only) ----------------------------------------------------------------------------
def _build_parser():
    import argparse
    parser = argparse.ArgumentParser(prog="identity_seed", description="Owner-run identity seed of the REAL database (superuser password at a prompt).")
    parser.add_argument("--socket", required=True)
    parser.add_argument("--user", required=True, help="the cluster's superuser (the tool then sets the schema owner's role)")
    parser.add_argument("--seed-file", required=True)
    parser.add_argument("--proposal", required=True)
    return parser


def main(argv=None, *, prompt=None, out=None, connect=None):
    args = _build_parser().parse_args(argv)
    say = (lambda text: print(text, file=out)) if out is not None else print
    try:
        prompt_route.require_genuine(pf)                 # TR7R4-L-1: before any file is read or prompt used
    except prompt_route.PromptRouteError as error:
        say("REFUSED SEED_PROMPT_ROUTE: %s. Nothing was written." % error.reason)
        return EXIT_REFUSED
    try:
        with open(args.seed_file, "rb") as handle:
            resolver = read_seed(handle.read())
        with open(args.proposal, "rb") as handle:
            expected = snapshot_identity_digest(handle.read())
        check_digest(resolver, expected)                       # before any connection
    except (SeedError, real_proposal.ProposalError, OSError) as error:
        say("REFUSED %s: %s. Nothing was written." % (getattr(error, "code", type(error).__name__), error))
        return EXIT_REFUSED
    say("the seed's identity digest equals the snapshot's (%s)" % expected[:16])
    import psycopg
    try:
        if connect is None:
            conn = pf.connect_with_prompt(args.socket, pf.REAL_DATABASE, args.user, require_auth=pf.GATED_REQUIRE_AUTH,
                                          prompt=prompt or pf.terminal_prompt, autocommit=True)
        else:
            conn = connect(args.socket, pf.REAL_DATABASE, args.user)
        try:
            conn.execute('SET ROLE "%s"' % pf.REAL_ROLES["owner"])
            result = apply_seed(conn, pf.REAL_SCHEMA, resolver, expected)
        finally:
            conn.close()
    except SeedError as error:
        say("REFUSED %s. Nothing was written." % error)
        return EXIT_REFUSED
    except psycopg.Error as error:
        say("REFUSED %s (%s): the seed's connection or statement failed; the seed is one transaction, so nothing was written" % (
            pf.classify_own_connection_error(str(error)), type(error).__name__))
        return EXIT_REFUSED
    for line in result.lines:
        say(line)
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
