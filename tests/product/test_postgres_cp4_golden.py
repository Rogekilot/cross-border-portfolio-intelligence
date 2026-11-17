"""CP4d: the golden fixture's checked items through PostgreSQL, as the least-privilege role, through the RISK SERVICE (tech plan 17.21).

Opt-in, like every database test here:

    FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=/tmp/.s.PGSQL.5432 FINWEB_PG_DATABASE=finweb_dev FINWEB_PG_USER=finweb_dev FINWEB_PG_APP_USER=finweb_app \\
        uv run --no-cache --no-sync --frozen --offline python -m unittest discover -s tests/product -t . -p 'test_postgres_cp4_golden.py' -v

EVERYTHING the engine reads comes from the database, and every number is asked of `risk_service.compute_risk_for_portfolio` (or `compute_risk_current_for_portfolio`) as `finweb_app`:
- the LEDGER: each fixture portfolio's events are appended (a REVERSAL and its replacement, or an internal transfer's two legs, in ONE transaction) and loaded back at the pinned version (the fixture's ledger seq is
  mapped to the stored one);
- the BENCHMARK SELECTION LOG: appended with `append_selection` / `append_correction`; the engine is handed exactly what `load_selections` returns at the pinned version, truncated at it, with the loader's boundary facts;
- the MARKET DATA: the release is projected by the owner role and read back with `read_release`; in Current mode every `M_t` is projected the same way (the derived release written by the owner, read by `finweb_app`);
- the reporting currency is the portfolio's own row (`currency_of`).
The same fixture items are compared as on the pure path: every checked item of parts 2 and 3 must match the database-read answer, with nothing deferred. The fixture's market data is synthetic, so the service is told
`allow_synthetic=True`, the labelled opt-in that leaves `synthetic=True` on every manifest and result.
"""

from __future__ import annotations

import datetime
import json
import sys
import unittest
import uuid
from pathlib import Path
from typing import Dict

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402
from domain.benchmark_selection import RecordType  # noqa: E402
from domain.ledger import EventType  # noqa: E402
from marketdata.files import FileStore  # noqa: E402
from marketdata.ingest import build_in_memory_market_data  # noqa: E402
from marketdata.manifest import FileManifest, MarketDataRelease  # noqa: E402
from marketdata.market11 import market11_conventions  # noqa: E402
from performance.inputs import MarketView  # noqa: E402
from persistence import benchmark_selection_store as sel_store  # noqa: E402
from persistence import ledger_replay_store, ledger_store  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402
from risk_service import service as rsvc  # noqa: E402

D = datetime.date
_SKIP = pk.skip_reason()
_USER = uuid.UUID("a1111111-1111-1111-1111-1111111111c4")


class PgMarket:
    """The same Market as the pure path, with the store and the conventions replaced by what the database returns."""

    def __init__(self, market, port, market_at):
        self.__dict__.update(vars(market))
        self.store = port
        self.conventions = market11_conventions(port.calendars())
        self.market_at = market_at


class PgDerivedView:
    """`M_t` through the database: the files of `M` retrieved at or before `t` are built into a derived release (every CP2 step re-run), WRITTEN by the owner role and READ BACK by `finweb_app`."""

    def __init__(self, market, owner, app, registry, catalog_calendars):
        self.market, self.owner, self.app, self.registry, self.catalog_calendars = market, owner, app, registry, catalog_calendars
        self.written = set()

    def view(self, instant: datetime.datetime) -> MarketView:
        files = FileStore(self.market.root)
        index = files.index()
        keep, left = [], []
        for sha in self.market.release.files:
            manifest = FileManifest.from_json(index[sha].read_text(encoding="utf-8"))
            (keep if manifest.retrieval_time <= instant else left).append(sha)
        release = self.market.release
        derived = MarketDataRelease(name=f"{release.name}@{instant.astimezone(datetime.timezone.utc).isoformat()}", files=tuple(sorted(keep)), source_precedence=release.source_precedence,
                                    conventions=release.conventions, created_for=release.created_for, convention_set_id=release.convention_set_id)
        built = build_in_memory_market_data(derived, files, self.registry, self.market.adapters, self.market.ident, catalog_calendars=self.catalog_calendars)
        if derived.release_id not in self.written:
            mds.write_release(self.owner, derived, built.manifests, built.store.export(), built.calendars)
            self.written.add(derived.release_id)
        port = mds.read_release(self.app, derived.release_id, exchange_of=self.market.ident.exchange_mic, registry=self.registry)
        return MarketView(port, port.calendars(), market11_conventions(port.calendars()), release.release_id, tuple(sorted(left)), instant)


class PgRunner(g.Runner):
    """Runs the engine through the risk service over the database-read ledger, selection log and market data."""

    def __init__(self, data, market, ids, app, stored_selection: Dict[str, Dict[int, int]], seq_map: Dict[str, Dict[int, int]], events, portfolio_ids: Dict[str, uuid.UUID]):
        super().__init__(data, market, ids)
        self.app, self.stored_selection, self.seq_map, self.portfolio_ids = app, stored_selection, seq_map, portfolio_ids
        self.events = events  # the events AS THE DATABASE RETURNS THEM (stored sequence numbers)

    def version(self, portfolio, assertion):
        name = portfolio["name"]
        if "ledger_version" in assertion:
            return self.seq_map[name][assertion["ledger_version"]]
        return max(e.ledger_seq for e in self.events[name])

    def selection_log(self, portfolio, assertion):
        """The log the DATABASE stores for the portfolio, truncated at the stored version of the fixture's pin (as `load_selections` returns it, with the loader's boundary facts)."""
        name = portfolio["name"]
        stored_version = self.stored_selection[name][assertion["selection_log_version"]]
        return sel_store.load_selections(self.app, self.portfolio_ids[name], stored_version), stored_version

    def fixture_selection_seq(self, portfolio, seq):
        inverse = {stored: fixture for fixture, stored in self.stored_selection[portfolio["name"]].items()}
        return inverse[seq]

    def risk(self, portfolio, assertion, item, metrics):
        account, version = self._args(portfolio, assertion, item)
        key = (portfolio["name"], assertion["id"], json.dumps(item["request"], sort_keys=True), item["frequency"], account, tuple(metrics))
        if key not in self._risk:
            name = portfolio["name"]
            pid = self.portfolio_ids[name]
            fixture_version = assertion.get("selection_log_version", 0)
            stored_version = 0 if fixture_version == 0 else self.stored_selection[name][fixture_version]
            common = dict(policy=g.POLICY, risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=self.catalog, ledger_version=version, selection_version=stored_version, metrics=metrics,
                          account_scope=account, verify_identities=self.verify, allow_synthetic=True)
            spec = g.spec_of(item["request"])
            frequency = g.Frequency(item["frequency"])
            if assertion.get("valuation_mode") == "CURRENT":
                result = rsvc.compute_risk_current_for_portfolio(self.app, pid, spec, g._utc(assertion["instant"]), frequency, self.market.ident, self.market.market_at, self.perf, **common)
            else:
                result = rsvc.compute_risk_for_portfolio(self.app, pid, spec, D.fromisoformat(assertion["as_of"]), frequency, self.market.store, self.market.ident, self.market.conventions, self.perf,
                                                         **common)
            assert not isinstance(result, rsvc.RiskRefusal), result
            self._risk[key] = result
        return self._risk[key]


def append_selections(app, data, ids) -> Dict[str, Dict[int, int]]:
    """Append each portfolio's selection log to the database in the fixture's order (a REVERSAL and its replacement in ONE transaction); returns, per portfolio, the fixture's seq -> the stored seq."""
    stored: Dict[str, Dict[int, int]] = {}
    for p in data["portfolios"]:
        records = sorted(p.get("benchmark_selections", []), key=lambda r: r["seq"])
        if not records:
            continue
        rows = {s.selection_seq: s.selection for s in g.selections_of(p, ids)}
        mapping: Dict[int, int] = {}
        done = set()
        for rec in records:
            seq = rec["seq"]
            if seq in done:
                continue
            partner = rec.get("atomic_with_seq")
            if partner is not None and partner > seq:
                out = sel_store.append_correction(app, rows[seq], rows[partner])
                mapping[seq], mapping[partner] = out.reversal.selection_seq, out.replacement.selection_seq
                done |= {seq, partner}
            else:
                mapping[seq] = sel_store.append_selection(app, rows[seq]).selection_seq
                done.add(seq)
        stored[p["name"]] = mapping
    return stored


def append_ledger(app, built) -> Dict[int, int]:
    """Append `[(seq, label, atomic group, event)]` honouring the atomic groups; returns {fixture seq: stored ledger_seq}."""
    mapping: Dict[int, int] = {}
    i = 0
    while i < len(built):
        seq, _label, group, event = built[i]
        members = [built[i]]
        if group is not None:
            while i + len(members) < len(built) and built[i + len(members)][2] == group:
                members.append(built[i + len(members)])
        elif event.event_type is EventType.TRANSFER_OUT and event.counterparty_account_id is not None and i + 1 < len(built) and built[i + 1][3].event_type is EventType.TRANSFER_IN:
            members.append(built[i + 1])  # the fixture lists an internal transfer's two legs one after the other; the database wants them in ONE transaction
        evs = [m[3] for m in members]
        if group is None and len(members) == 1:
            results = [ledger_store.append_event(app, evs[0])]
        elif evs[0].event_type is EventType.REVERSAL:
            pair = ledger_store.append_correction(app, evs[0], evs[1])
            results = [pair.reversal, pair.replacement]
        elif evs[0].event_type is EventType.TRANSFER_OUT:
            results = list(ledger_store.append_internal_transfer(app, evs[0], evs[1]))
        else:
            results = ledger_store.append_batch(app, evs)
        for member, result in zip(members, results):
            mapping[member[0]] = result.ledger_seq
        i += len(members)
    return mapping


class PgWorld:
    """One part of the fixture loaded into one disposable schema (each part has its own listings): the ledger, the selection log and the release, all as `finweb_app` reads them."""

    PART = 0

    @classmethod
    def setUpClass(cls):
        cls.db = pk.PgSchema(prefix="finweb_it_g4_").open()
        cls.addClassCleanup(cls.db.close)
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.owner = cls.db.owner
        cls.owner.execute("INSERT INTO app_user VALUES (%s)", (_USER,))
        pure = g.shared_runner(cls.PART)
        market = pure.market
        pk.insert_identity(cls.owner, market.ident)
        release = market.release
        written = mds.write_release(cls.owner, release, market.manifests, market.store.export(), market.built.calendars)
        registry = FileStore(market.root).load_registry()
        port = mds.read_release(cls.app, release.release_id, exchange_of=market.ident.exchange_mic, registry=registry)
        assert port.projection_digest() == written.projection_digest
        catalog_calendars = {e.benchmark_id: e.calendar_id for e in pure.catalog.entries}
        market_at = PgDerivedView(market, cls.owner, cls.app, registry, catalog_calendars)
        portfolio_ids, seq_map, events = {}, {}, {}
        for p in pure.data["portfolios"]:
            pid = pure.ids(p["portfolio_id"])
            cls.owner.execute("INSERT INTO portfolio VALUES (%s, %s, %s)", (pid, _USER, p["reporting_currency"]))
            for account in p["accounts"]:
                cls.owner.execute("INSERT INTO account VALUES (%s, %s, %s)", (pure.ids(account["account_id"]), pid, account["name"]))
            seq_map[p["name"]] = append_ledger(cls.app, cp1.build_events(p, pure.ids))
            events[p["name"]] = list(ledger_replay_store.load_events(cls.app, pid, ledger_replay_store.current_ledger_version(cls.app, pid)))
            portfolio_ids[p["name"]] = pid
        stored = append_selections(cls.app, pure.data, pure.ids)
        cls.runner = PgRunner(pure.data, PgMarket(market, port, market_at), pure.ids, cls.app, stored, seq_map, events, portfolio_ids)


class GoldenThroughPostgres(PgWorld):
    CHECKED = (0, 0)

    def test_every_checked_item_matches_through_the_database(self):
        mismatches, checked, deferred = g.check_all(self.runner)
        self.assertEqual([str(m) for m in mismatches], [])
        self.assertEqual((checked, len(deferred)), self.CHECKED)


@unittest.skipIf(bool(_SKIP), _SKIP)
class PartOneThroughPostgresTests(GoldenThroughPostgres, unittest.TestCase):
    """CP4F-11: part 1 (cash only, missing FX, a snapshot, in-kind transfers, recently listed, no risk-free source) through the database as well; the main session's STATUS and the reviewer's run said 78 of 78."""

    PART = 1
    CHECKED = (78, 0)


@unittest.skipIf(bool(_SKIP), _SKIP)
class PartFourThroughPostgresTests(GoldenThroughPostgres, unittest.TestCase):
    """Part 4: the risk-free quote at instant t in Current mode (each `M_t` written to the database and read back as `finweb_app`) and the default view of a relative metric."""

    PART = 4
    CHECKED = (11, 0)


@unittest.skipIf(bool(_SKIP), _SKIP)
class PartTwoThroughPostgresTests(GoldenThroughPostgres, unittest.TestCase):
    PART = 2
    CHECKED = (61, 0)


@unittest.skipIf(bool(_SKIP), _SKIP)
class PartThreeThroughPostgresTests(GoldenThroughPostgres, unittest.TestCase):
    PART = 3
    CHECKED = (107, 0)

    def test_every_selection_resolution_item_resolves_the_log_the_database_stores_not_the_fixtures(self):
        """The `selection_resolution` items (R13) were resolved from the fixture's in-memory log (CP4 final review 41.8): they now read the stored one, with the stored sequence numbers mapped back."""
        r = self.runner
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R13 ")]
        a = next(x for x in p["assertions"] if x["id"] == "R13-V8")
        rows, version = r.selection_log(p, a)
        self.assertEqual(version, r.stored_selection[p["name"]][a["selection_log_version"]])
        self.assertTrue(all(x.selection_seq <= version for x in rows))
        self.assertTrue(any(x.selection.selection_id != y.selection.selection_id or x.selection_seq != y.selection_seq for x in rows for y in g.selections_of(p, r.ids)))  # not the fixture's own rows
        items = [(x, it) for x in p["assertions"] for it in x["expect"] if it["kind"] == "selection_resolution"]
        self.assertGreaterEqual(len(items), 7)
        for assertion, item in items:
            self.assertEqual([str(m) for m in g.resolve_item(r, p, assertion, item)], [], assertion["id"])

    def test_the_selection_log_the_engine_read_is_the_stored_one_truncated_at_the_version(self):
        r = self.runner
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R13 ")]
        stored = r.stored_selection[p["name"]]
        rows = sel_store.load_selections(self.app, r.portfolio_ids[p["name"]], stored[10])
        self.assertEqual([x.selection_seq for x in rows], sorted(stored.values()))
        self.assertTrue(any(x.selection.record_type is RecordType.REVERSAL for x in rows))
        self.assertEqual([x.atomic_with_seq is not None for x in rows[-4:]], [True, True, True, True])  # the two pairs state their boundary facts

    def test_the_reporting_currency_is_the_portfolios_own_row(self):
        r = self.runner
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R7 ")]
        self.assertEqual(rsvc.currency_of(self.app, r.portfolio_ids[p["name"]]).code, "HKD")  # R7 reports in HKD: never a default

    def test_the_ledger_the_engine_read_is_the_stored_one(self):
        r = self.runner
        (p,) = [p for p in r.data["portfolios"] if p["name"].startswith("R12 ")]
        events = ledger_replay_store.load_events(self.app, r.portfolio_ids[p["name"]], ledger_replay_store.current_ledger_version(self.app, r.portfolio_ids[p["name"]]))
        self.assertEqual([e.ledger_seq for e in events], sorted(r.seq_map[p["name"]].values()))


if __name__ == "__main__":
    unittest.main()
