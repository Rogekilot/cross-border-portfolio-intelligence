"""CP1-D: the golden fixture as a permanent regression test (PD-0011 Priority D).

Fixture: `methodology/fixtures/cp1_golden/cp1_golden_fixture.json` (`cp1_golden/1.1`, convention
set `ledger-replay/1.3`), hand-derived and ratified by the Quant. This file NEVER edits the
fixture and never derives an expected value from the code. If replay disagrees with the fixture
the test fails and names the assertion; neither side is adjusted here.

Three layers:

1. PURE (always runs): `domain.replay.reconstruct` at every assertion's (D, L), every `expect`
   item checked (state, Decimal value, reason, detail). One subTest per item.
2. DATABASE (opt-in, like the other DB tests): the same events appended through the real store
   (honouring `atomic_group`) into a disposable schema, replayed with
   `ledger_replay_store.replay`, plus T11-T13. Every id is remapped to a fresh random UUID per
   run, so concurrent runs share no lock key.
3. DETERMINISM (T10): byte-identical canonical output across runs, shuffled inputs and separate
   processes with different PYTHONHASHSEED; pure equals database output; pinned-version stability.

Detail. An explicit expected `detail` list (including []) is checked exactly, through the
position's `quantity_detail` / `basis_detail`. `"detail": null` (fixture 1.1) means NOT ASSERTED:
it is used only where the reason code fully determines the cause, and is never treated as []. A
detail that is asserted but that the API cannot expose fails loudly rather than being skipped.

Opt in to the database layer with the variables of `test_postgres_replay_integration.py`
(FINWEB_PG_INTEGRATION=1 FINWEB_PG_SOCKET=... FINWEB_PG_DATABASE=... FINWEB_PG_USER=...;
FINWEB_PG_APP_USER adds the least-privilege T11 variant).
"""

import dataclasses
import datetime
import importlib.util
import inspect
import json
import os
import random
import subprocess
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode, Money  # noqa: E402
from domain.ledger import EventType, LedgerEvent, SplitRatio  # noqa: E402
from domain.replay import (  # noqa: E402
    CONVENTION_SET_ID,
    ReplayedState,
    SequencedEvent,
    reconstruct,
)
from persistence import connection, ledger_replay_store, ledger_store, migrator  # noqa: E402

try:  # the production grant spec, imported so the two never drift
    from tests.product.test_postgres_least_privilege import APP_GRANTS  # noqa: E402
except ImportError:  # run with `-s tests/product` and no package root
    from test_postgres_least_privilege import APP_GRANTS  # noqa: E402

FIXTURE_PATH =_ROOT / "methodology" / "fixtures" / "cp1_golden" / "cp1_golden_fixture.json"


def _no_float(text):
    raise AssertionError(f"the fixture must hold no float literal, found {text!r}")


FIXTURE = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"), parse_float=_no_float)

# CP1D-2: a tripwire against a silently trimmed fixture. The fixture legitimately changes only
# with a new `fixture_id` (the Quant bumps it); a version bump is the ONE place to update this
# table. Per assertion id: the number of `expect` items; plus a sha256 over every assertion's
# (id, as_of, ledger_version, expect, derived_checks, structural_checks) content, taken from the
# fixture file (never from replay output).
FIXTURE_PINS = {
    "cp1_golden/1.1": {
        "expect_counts": {
            "T1": 4, "T2": 3, "T3": 4, "T4": 2, "T5": 2, "T6-before": 3, "T6": 3, "T7": 3, "T8": 2,
            "T9": 9, "V1-before": 4, "V1-after": 2, "V1-day-before": 2, "V2-shortfall": 3,
            "V2-funded": 1, "V2-interest": 1, "V3-two-lots": 3, "V3-unresolved": 4, "V4-before": 2,
            "V4": 6, "T13-L23": 1, "T13-L24": 1, "T13-L25": 1, "T13-retro": 1,
            "S1": 4, "S2": 4, "S3": 3,
        },
        "expect_total": 78,
        "content_sha256": "9177ee83965f6851c513608bf9146d85827c008464379d98cc17548ff7885d94",
    },
}


def expected_content_hash():
    import hashlib
    content = [[a["id"], a["as_of"], a["ledger_version"], a["expect"], a.get("derived_checks"),
                a.get("structural_checks")] for p in FIXTURE["portfolios"] for a in p["assertions"]]
    text = json.dumps(content, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fixture_items():
    for portfolio, assertion in ((p, a) for p in FIXTURE["portfolios"] for a in p["assertions"]):
        for item in assertion["expect"]:
            yield assertion, item


# Items the fixture marks "detail": null (not asserted); derived from the fixture, not pinned.
NOT_ASSERTED_ITEMS = {(a["id"], i["kind"], i.get("account_id")) for a, i in fixture_items()
                      if i["kind"] != "account_status" and i["detail"] is None}


# --- loader -------------------------------------------------------------------------------


class Ids:
    """Maps the fixture's fixed ids to the ids actually used (identity, or fresh random ones)."""

    def __init__(self, randomize):
        self.map = {}
        self.randomize = randomize

    def __call__(self, text):
        if text is None:
            return None
        if text not in self.map:
            self.map[text] = uuid.uuid4() if self.randomize else uuid.UUID(text)
        return self.map[text]


def _money(obj):
    return None if obj is None else Money(Decimal(obj["amount"]), CurrencyCode(obj["currency"]))


def build_events(portfolio, ids):
    """[(ledger_seq, label, atomic_group, LedgerEvent)] in ledger_seq order. Decimal from strings."""
    out = []
    for entry in portfolio["events"]:
        e = entry["event"]
        ratio = e.get("split_ratio")
        event = LedgerEvent(
            event_id=ids(e["event_id"]),
            account_id=ids(e["account_id"]),
            event_type=EventType(e["event_type"]),
            event_date=datetime.date.fromisoformat(e["event_date"]),
            currency=CurrencyCode(e["currency"]),
            listing_id=ids(e.get("listing_id")),
            quantity=None if e.get("quantity") is None else Decimal(e["quantity"]),
            amount=_money(e.get("amount")),
            cost_basis=_money(e.get("cost_basis")),
            bought_amount=_money(e.get("bought_amount")),
            split_ratio=None if ratio is None else SplitRatio(Decimal(ratio["new_units"]),
                                                              Decimal(ratio["old_units"])),
            counterparty_account_id=ids(e.get("counterparty_account_id")),
            settlement_date=None if e.get("settlement_date") is None
            else datetime.date.fromisoformat(e["settlement_date"]),
            ex_date=None if e.get("ex_date") is None else datetime.date.fromisoformat(e["ex_date"]),
            reverses_event_id=ids(e.get("reverses_event_id")),
            corrects_event_id=ids(e.get("corrects_event_id")),
            source_reference=e.get("source_reference"),
            acquired_on=None if e.get("acquired_on") is None else datetime.date.fromisoformat(e["acquired_on"]),  # PD-0036 (part 3, P20)
        )
        out.append((entry["ledger_seq"], entry.get("label", f"seq-{entry['ledger_seq']}"), entry.get("atomic_group"), event))  # part 3's events carry no label
    return out


def sequenced(events, seq_map=None):
    return [SequencedEvent(seq if seq_map is None else seq_map[seq], ev) for seq, _l, _g, ev in events]


def portfolio_named(prefix):
    return next(p for p in FIXTURE["portfolios"] if p["name"].startswith(prefix))


def d(text):
    return datetime.date.fromisoformat(text)


# --- checking one assertion ---------------------------------------------------------------


def _money_list(entries):
    return [{"amount": e.result.value, "currency": e.currency.code} for e in entries]


def check_detail(tc, item, observed, available, not_asserted, key):
    """`detail` null = not asserted (recorded, never treated as []). A list is checked exactly."""
    tc.assertIn("detail", item)  # a missing key is not "not asserted"
    expected = item["detail"]
    if expected is None:
        not_asserted.add(key)
        return
    if available:
        tc.assertEqual(expected, [])  # an AVAILABLE envelope carries no detail
    if observed is not None:
        tc.assertEqual(observed, expected)
    elif expected != []:
        tc.fail(f"detail {expected!r} is asserted but the replay API cannot expose it")


def check_expect(tc, state: ReplayedState, ids, assertion, item, unobserved):
    """Assert one `expect` item against `state`. `unobserved` collects the items whose
    `detail` the fixture leaves unasserted (null)."""
    kind = item["kind"]
    acct = ids(item.get("account_id"))
    listing = ids(item.get("listing_id"))
    ccy = None if item.get("currency") is None else CurrencyCode(item["currency"])
    if kind == "account_status":
        account = state.account(acct)
        tc.assertEqual(account.status.value, item["value"])
        if "snapshot_date" in item:  # optional (1.1): the account's snapshot date S, or null
            tc.assertEqual(None if account.snapshot_date is None else account.snapshot_date.isoformat(),
                           item["snapshot_date"])
        return
    detail = None  # what the API exposes, or None when it cannot
    if kind == "quantity":
        result = state.position_quantity(acct, listing)
        position = next((p for p in state.account(acct).positions if p.listing_id == listing), None)
        detail = [x.value for x in position.quantity_detail] if position is not None else None
    elif kind == "basis":
        entries = state.position_basis(acct, listing)
        position = next((p for p in state.account(acct).positions if p.listing_id == listing), None)
        detail = [x.value for x in position.basis_detail] if position is not None else []
        if item["state"] == "AVAILABLE":
            tc.assertEqual([e.result.sufficiency_state.value for e in entries],
                           ["AVAILABLE"] * len(entries))
            actual = _money_list(entries)
            expected = [{"amount": Decimal(m["amount"]), "currency": m["currency"]} for m in item["value"]]
            tc.assertEqual(actual, expected)  # Decimal numeric equality, sorted by currency code
            check_detail(tc, item, detail, True, unobserved, (assertion["id"], kind, item.get("account_id")))
            return
        tc.assertEqual(len(entries), 1)
        result = entries[0].result
    elif kind == "cash":
        result = state.cash_balance(acct, ccy)
    elif kind == "portfolio_cash":
        result = state.portfolio_cash(ccy)
    elif kind == "portfolio_quantity":
        result = state.portfolio_position_quantity(listing)
    else:
        tc.fail(f"unknown expect kind {kind!r}")
    tc.assertEqual(result.sufficiency_state.value, item["state"])
    tc.assertEqual(result.value, None if item["value"] is None else Decimal(item["value"]))
    tc.assertEqual(None if result.reason_code is None else result.reason_code.value, item["reason"])
    check_detail(tc, item, detail, item["state"] == "AVAILABLE", unobserved,
                 (assertion["id"], kind, item.get("account_id")))


def check_assertion(tc, state, ids, assertion, unobserved):
    for index, item in enumerate(assertion["expect"]):
        with tc.subTest(assertion=assertion["id"], item=index, kind=item["kind"]):
            check_expect(tc, state, ids, assertion, item, unobserved)
    for check in assertion.get("derived_checks", []):
        with tc.subTest(assertion=assertion["id"], derived=check["name"]):
            item_q = next(i for i in assertion["expect"] if i["kind"] == "quantity")
            item_b = next(i for i in assertion["expect"] if i["kind"] == "basis")
            quantity = state.position_quantity(ids(item_q["account_id"]), ids(item_q["listing_id"])).value
            (entry,) = state.position_basis(ids(item_b["account_id"]), ids(item_b["listing_id"]))
            tc.assertEqual(entry.result.value / quantity, Decimal(check["value"]))  # 7500 / 200
    if assertion["id"] == "T9":
        with tc.subTest(assertion="T9", structural=True):
            (a1,) = [a for a in state.accounts if a.account_id == ids("a1000000-0000-4000-8000-000000000001")]
            tc.assertEqual({e.balance.currency.code: e.balance.amount for e in a1.cash},
                           {"HKD": Decimal(750), "USD": Decimal(2748)})
            tc.assertEqual(len(a1.cash), 2)  # two separate entries, never one number
            public = [n for n in dir(state) if not n.startswith("_") and callable(getattr(state, n))]
            tc.assertFalse([n for n in public if any(w in n.lower() for w in ("total", "convert", "reporting", "fx"))])
            tc.assertEqual(list(inspect.signature(state.portfolio_cash).parameters), ["currency"])
            tc.assertFalse(hasattr(state, "reporting_currency"))


def all_assertions():
    for portfolio in FIXTURE["portfolios"]:
        for assertion in portfolio["assertions"]:
            yield portfolio, assertion


def canonical_of(state, drop_version=False):
    data = state.to_canonical_dict()
    if drop_version:
        data = dict(data, ledger_version=None)
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def emit_all():
    """(assertion id, canonical_json) for every assertion, pure path, fixture ids."""
    ids = Ids(randomize=False)
    lines = []
    for portfolio, assertion in all_assertions():
        events = sequenced(build_events(portfolio, ids))
        state = reconstruct(events, d(assertion["as_of"]), assertion["ledger_version"])
        lines.append(f"{assertion['id']}\t{state.canonical_json()}")
    return "\n".join(lines) + "\n"


# --- 1. the pure path -------------------------------------------------------------------------


class FixtureShapeTests(unittest.TestCase):
    def test_fixture_identity_and_counts(self):
        self.assertEqual(FIXTURE["fixture_id"], "cp1_golden/1.1")
        self.assertEqual(FIXTURE["convention_set"], CONVENTION_SET_ID)
        self.assertEqual(len(FIXTURE["portfolios"]), 2)
        self.assertEqual(sum(len(p["events"]) for p in FIXTURE["portfolios"]), 28)
        self.assertEqual(sum(len(p["assertions"]) for p in FIXTURE["portfolios"]), 27)
        self.assertEqual([a["id"] for a in FIXTURE["determinism_assertions"]], ["T10"])
        self.assertEqual([a["id"] for a in FIXTURE["storage_assertions"]],
                         ["T11", "T12", "T12-conflict", "T13", "T13-correction"])

    def test_cp1d2_the_fixture_content_is_pinned_to_its_version(self):
        """A trimmed or emptied fixture must fail. Update FIXTURE_PINS only with a new fixture_id."""
        pins = FIXTURE_PINS.get(FIXTURE["fixture_id"])
        self.assertIsNotNone(
            pins, f"fixture {FIXTURE['fixture_id']!r} has no entry in FIXTURE_PINS: pin its counts and hash")
        counts = {a["id"]: len(a["expect"]) for _p, a in all_assertions()}
        self.assertEqual(counts, pins["expect_counts"])
        self.assertEqual(sum(counts.values()), pins["expect_total"])
        self.assertEqual(expected_content_hash(), pins["content_sha256"])

    def test_cp1d2_every_assertion_has_expectations_and_the_named_ones_are_present(self):
        ids = [a["id"] for _p, a in all_assertions()]
        self.assertEqual(len(ids), len(set(ids)))
        for _p, a in all_assertions():
            with self.subTest(assertion=a["id"]):
                self.assertTrue(a["expect"], "an assertion with no expect items would pass vacuously")
                for item in a["expect"]:
                    self.assertIn(item["kind"], FIXTURE["format"]["expect_kinds"])
        # the B0b §11 ids the CP1-D acceptance names, all present with content
        for required in ("T1", "T2", "T3", "T4", "T5", "T6", "T7", "T8", "T9",
                         "T13-L23", "T13-L24", "T13-L25", "T13-retro"):
            self.assertIn(required, ids)
        by_id = {a["id"]: a for _p, a in all_assertions()}
        t5 = by_id["T5"]  # split preserves value: quantity, basis AND the derived unit basis
        self.assertEqual({i["kind"] for i in t5["expect"]}, {"quantity", "basis"})
        self.assertEqual([c["name"] for c in t5.get("derived_checks", [])], ["unit_basis_AAPL_A1"])
        self.assertEqual(t5["derived_checks"][0]["value"], "37.5")
        self.assertTrue(by_id["T9"].get("structural_checks"))
        self.assertEqual([a["id"] for a in FIXTURE["determinism_assertions"]], ["T10"])
        for s in FIXTURE["storage_assertions"]:
            self.assertTrue(s.get("scenario") and s.get("expected"), s["id"])

    def test_events_are_valid_domain_events_with_sequential_seqs(self):
        for portfolio in FIXTURE["portfolios"]:
            events = build_events(portfolio, Ids(randomize=False))
            self.assertEqual([e[0] for e in events], list(range(1, len(events) + 1)))
            self.assertEqual(len({e[3].event_id for e in events}), len(events))


class PureFixtureTests(unittest.TestCase):
    def test_every_assertion_matches_the_fixture(self):
        ids = Ids(randomize=False)
        by_portfolio = {p["name"]: sequenced(build_events(p, ids)) for p in FIXTURE["portfolios"]}
        unobserved = set()
        ran = 0
        for portfolio, assertion in all_assertions():
            state = reconstruct(by_portfolio[portfolio["name"]], d(assertion["as_of"]),
                                assertion["ledger_version"])
            with self.subTest(assertion=assertion["id"], part="envelope"):
                self.assertEqual(state.convention_set, "ledger-replay/1.3")
                self.assertEqual(state.ledger_version, assertion["ledger_version"])
            check_assertion(self, state, ids, assertion, unobserved)
            ran += 1
        self.assertEqual(ran, 27)
        self.assertEqual(unobserved, NOT_ASSERTED_ITEMS)

    def test_the_checker_really_fails_on_a_wrong_expectation(self):
        """Guards the harness itself: a doctored expected value, state, reason or detail
        must fail (the fixture file is not touched; the copy lives in memory)."""
        import copy
        ids = Ids(randomize=False)
        p1 = portfolio_named("P1")
        events = sequenced(build_events(p1, ids))
        t8 = copy.deepcopy(next(a for a in p1["assertions"] if a["id"] == "T8"))
        state = reconstruct(events, d(t8["as_of"]), t8["ledger_version"])
        basis = next(i for i in t8["expect"] if i["kind"] == "basis")
        quantity = next(i for i in t8["expect"] if i["kind"] == "quantity")
        for label, mutate in (
            ("value", lambda: quantity.update(value="11")),
            ("reason", lambda: basis.update(reason="LEDGER_INCONSISTENT")),
            ("detail", lambda: basis.update(detail=[])),
            ("state", lambda: basis.update(state="AVAILABLE", value=[{"amount": "0", "currency": "USD"}], detail=[])),
        ):
            doctored = copy.deepcopy(t8)
            b = next(i for i in doctored["expect"] if i["kind"] == "basis")
            q = next(i for i in doctored["expect"] if i["kind"] == "quantity")
            quantity, basis = q, b
            mutate()
            with self.subTest(mutation=label), self.assertRaises(AssertionError):
                for item in doctored["expect"]:
                    check_expect(self, state, ids, doctored, item, set())

    def test_null_detail_means_not_asserted_and_is_never_treated_as_an_empty_list(self):
        ids = Ids(randomize=False)
        p2 = portfolio_named("P2")
        events = sequenced(build_events(p2, ids))
        s2 = next(a for a in p2["assertions"] if a["id"] == "S2")
        state = reconstruct(events, d(s2["as_of"]), s2["ledger_version"])
        basis = next(i for i in s2["expect"] if i["kind"] == "basis")  # actual detail: [UNKNOWN_BASIS]
        self.assertEqual(basis["detail"], ["UNKNOWN_BASIS"])
        skipped = set()
        import copy
        nulled = dict(basis, detail=None)  # not asserted: passes without consulting the detail
        check_expect(self, state, ids, s2, nulled, skipped)
        self.assertEqual(skipped, {("S2", "basis", basis["account_id"])})
        with self.assertRaises(AssertionError):  # an explicit [] must NOT behave like null
            check_expect(self, state, ids, s2, dict(basis, detail=[]), set())
        missing = copy.deepcopy(basis)
        del missing["detail"]
        with self.assertRaises(AssertionError):  # an absent key is not "not asserted" either
            check_expect(self, state, ids, s2, missing, set())

    def test_only_reason_determined_values_use_null_detail(self):
        self.assertEqual(len(NOT_ASSERTED_ITEMS), 3)
        for aid, kind, _acct in NOT_ASSERTED_ITEMS:
            self.assertEqual(aid, "S1")
        for assertion, item in fixture_items():
            if item["kind"] != "account_status" and item["detail"] is None:
                self.assertEqual(item["reason"], "NOT_RECONSTRUCTABLE")  # reason fixes the cause

    def test_the_snapshot_date_is_observable_and_checked(self):
        ids = Ids(randomize=False)
        p2 = portfolio_named("P2")
        events = sequenced(build_events(p2, ids))
        s1 = next(a for a in p2["assertions"] if a["id"] == "S1")
        item = next(i for i in s1["expect"] if i["kind"] == "account_status")
        self.assertEqual(item["snapshot_date"], "2025-06-30")
        state = reconstruct(events, d(s1["as_of"]), s1["ledger_version"])
        check_expect(self, state, ids, s1, item, set())
        with self.assertRaises(AssertionError):
            check_expect(self, state, ids, s1, dict(item, snapshot_date="2025-07-01"), set())

    def test_no_expected_value_is_a_float(self):
        def walk(node):
            if isinstance(node, float):
                self.fail("float in fixture")
            elif isinstance(node, dict):
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for v in node:
                    walk(v)
        walk(FIXTURE)


# --- 3a. determinism, pure ----------------------------------------------------------------------


class DeterminismTests(unittest.TestCase):
    def setUp(self):
        self.ids = Ids(randomize=False)
        self.events = {p["name"]: sequenced(build_events(p, self.ids)) for p in FIXTURE["portfolios"]}

    def outputs(self, transform):
        out = {}
        for portfolio, assertion in all_assertions():
            events = transform(list(self.events[portfolio["name"]]))
            out[assertion["id"]] = reconstruct(
                events, d(assertion["as_of"]), assertion["ledger_version"]).canonical_json()
        return out

    def test_t10_two_runs_reversed_and_shuffled_are_byte_identical(self):
        first = self.outputs(lambda e: e)
        self.assertEqual(first, self.outputs(lambda e: e))
        self.assertEqual(first, self.outputs(lambda e: list(reversed(e))))

        def shuffled(e):
            random.Random(20250930).shuffle(e)  # fixed seed; ledger_seq values untouched
            return e
        self.assertEqual(first, self.outputs(shuffled))
        for aid, text in first.items():
            with self.subTest(assertion=aid):
                self.assertTrue(text.isascii())
                self.assertEqual(json.loads(text)["convention_set"], "ledger-replay/1.3")

    def test_t10_separate_processes_with_different_hash_seeds_agree(self):
        here = emit_all()
        for seed in ("0", "1", "424242"):
            with self.subTest(pythonhashseed=seed):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                done = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--emit"],
                                      env=env, capture_output=True, text=True, timeout=120, check=True)
                self.assertEqual(done.stdout, here)

    def test_pinned_version_is_stable_when_later_events_are_appended_pure(self):
        p1 = portfolio_named("P1")
        events = build_events(p1, self.ids)
        first = sequenced(events)
        pinned = reconstruct(first, d("2025-06-30"), 17).canonical_json()
        extra = dataclasses.replace(
            events[0][3], event_id=uuid.uuid4(), event_date=d("2025-07-01"), source_reference="P1-EXTRA")
        grown = first + [SequencedEvent(26, extra)]
        self.assertEqual(reconstruct(grown, d("2025-06-30"), 17).canonical_json(), pinned)
        self.assertNotEqual(reconstruct(grown, d("2025-07-01"), 26).canonical_json(),
                            reconstruct(first, d("2025-07-01"), 25).canonical_json())


# --- 2 and 3b. the database path -----------------------------------------------------------------

_MISSING = connection.missing_env_vars(os.environ)
if _MISSING:
    _SKIP = "CP1-D database tests are opt-in; set: " + "; ".join(_MISSING)
elif importlib.util.find_spec("psycopg") is None:
    _SKIP = "psycopg is not installed"
else:
    _SKIP = ""


class Loaded:
    """One copy of the fixture appended to the database under fresh random ids."""

    def __init__(self, conn, instrument_id, user_id, append_conn=None):
        """`conn` (the owner) inserts the reference rows; `append_conn` (default `conn`)
        appends the events, so a least-privilege role can do the ledger work."""
        self.ids = Ids(randomize=True)
        self.conn = conn
        self.append_conn = append_conn if append_conn is not None else conn
        self.portfolio = {}  # "P1"/"P2" -> uuid
        self.seq = {}  # "P1"/"P2" -> {fixture seq: stored ledger_seq}
        self.results = {}
        self.events = {}
        for listing in FIXTURE["listings"]:
            conn.execute("INSERT INTO listing VALUES (%s, %s, %s, %s, %s, %s, NULL, true)",
                         (self.ids(listing["listing_id"]), instrument_id, listing["mic"], listing["mic"],
                          listing["ticker"], listing["trading_currency"]))
        for p in FIXTURE["portfolios"]:
            key = p["name"][:2]
            pid = self.ids(p["portfolio_id"])
            self.portfolio[key] = pid
            conn.execute("INSERT INTO portfolio VALUES (%s, %s, %s)", (pid, user_id, p["reporting_currency"]))
            for account in p["accounts"]:
                conn.execute("INSERT INTO account VALUES (%s, %s, %s)",
                             (self.ids(account["account_id"]), pid, account["name"]))
            self.events[key] = build_events(p, self.ids)
            self.append(key)

    def append(self, key):
        events = self.events[key]
        self.seq[key] = {}
        i = 0
        while i < len(events):
            seq, _label, group, event = events[i]
            members = [events[i]]
            if group is not None:
                while i + len(members) < len(events) and events[i + len(members)][2] == group:
                    members.append(events[i + len(members)])
            evs = [m[3] for m in members]
            if group is None:
                results = [ledger_store.append_event(self.append_conn, evs[0])]
            elif evs[0].event_type is EventType.REVERSAL:
                pair = ledger_store.append_correction(self.append_conn, evs[0], evs[1])
                results = [pair.reversal, pair.replacement]
            elif evs[0].event_type is EventType.TRANSFER_OUT:
                results = list(ledger_store.append_internal_transfer(self.append_conn, evs[0], evs[1]))
            else:
                results = ledger_store.append_batch(self.append_conn, evs)
            for member, result in zip(members, results):
                self.seq[key][member[0]] = result.ledger_seq
                self.results[(key, member[0])] = result
            i += len(members)


@unittest.skipIf(bool(_SKIP), _SKIP)
class DatabaseFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import psycopg  # noqa: PLC0415

        cls.pg = psycopg
        cls.conn = connection.connect(connection.conninfo_from_env(os.environ), autocommit=True)
        cls.schema = "finweb_it_" + uuid.uuid4().hex[:12]
        cls.addClassCleanup(cls._cleanup)
        cls.conn.execute('CREATE SCHEMA "%s"' % cls.schema)
        cls.conn.execute('SET search_path TO "%s"' % cls.schema)
        migrator.apply_migrations(cls.conn)
        cls.user = uuid.uuid4()
        cls.instrument = uuid.uuid4()
        issuer = uuid.uuid4()
        cls.conn.execute("INSERT INTO app_user VALUES (%s)", (cls.user,))
        cls.conn.execute("INSERT INTO issuer VALUES (%s, 'Issuer', NULL)", (issuer,))
        cls.conn.execute("INSERT INTO instrument VALUES (%s, %s, 'COMMON_STOCK')", (cls.instrument, issuer))
        cls.main = Loaded(cls.conn, cls.instrument, cls.user)

    @classmethod
    def _cleanup(cls):
        try:
            cls.conn.execute('DROP SCHEMA IF EXISTS "%s" CASCADE' % cls.schema)
        finally:
            cls.conn.close()

    # -- helpers --

    def app_connection(self):
        """A connection as the least-privilege role under EXACTLY the production grants
        (`APP_GRANTS`, imported so the two can never drift), in this class's schema."""
        role = os.environ["FINWEB_PG_APP_USER"]
        for grant in APP_GRANTS:
            self.conn.execute(grant.format(schema=self.schema, role=role))
        env = os.environ
        app = connection.connect(connection.build_conninfo(
            dbname=env[connection.DATABASE_VAR], user=role, socket=env.get(connection.SOCKET_VAR) or None,
            host=env.get(connection.HOST_VAR) or None, port=env.get(connection.PORT_VAR) or None),
            autocommit=True)
        app.execute('SET search_path TO "%s"' % self.schema)
        self.assertEqual(app.execute("SELECT current_user").fetchone()[0], role)
        return app

    def replay(self, loaded, key, as_of, fixture_l):
        pin = loaded.seq[key][fixture_l] if fixture_l else 0
        return ledger_replay_store.replay(self.conn, loaded.portfolio[key], d(as_of), pin)

    def rows(self, loaded, key):
        return self.conn.execute(
            "SELECT * FROM ledger_event WHERE portfolio_id = %s ORDER BY ledger_seq",
            (loaded.portfolio[key],)).fetchall()

    # -- assertions through the real store ------------------------------------------------------

    def test_every_assertion_matches_the_fixture_through_the_database(self):
        unobserved, ran = set(), 0
        for portfolio, assertion in all_assertions():
            key = portfolio["name"][:2]
            state = self.replay(self.main, key, assertion["as_of"], assertion["ledger_version"])
            with self.subTest(assertion=assertion["id"], part="envelope"):
                self.assertEqual(state.convention_set, "ledger-replay/1.3")
                self.assertEqual(state.ledger_version, self.main.seq[key][assertion["ledger_version"]])
            check_assertion(self, state, self.main.ids, assertion, unobserved)
            ran += 1
        self.assertEqual(ran, 27)
        self.assertEqual(unobserved, NOT_ASSERTED_ITEMS)

    def test_t10_pure_and_database_paths_give_identical_canonical_output(self):
        for portfolio, assertion in all_assertions():
            key = portfolio["name"][:2]
            with self.subTest(assertion=assertion["id"]):
                db = self.replay(self.main, key, assertion["as_of"], assertion["ledger_version"])
                pure = reconstruct(sequenced(self.main.events[key]), d(assertion["as_of"]),
                                   assertion["ledger_version"])
                # Same events, same (remapped) ids; only the storage-assigned ledger_version
                # differs (fixture seq vs global sequence value), so it is normalised.
                self.assertEqual(canonical_of(db, drop_version=True), canonical_of(pure, drop_version=True))

    def test_t10_database_replay_is_repeatable(self):
        for portfolio, assertion in all_assertions():
            key = portfolio["name"][:2]
            a = self.replay(self.main, key, assertion["as_of"], assertion["ledger_version"]).canonical_json()
            b = self.replay(self.main, key, assertion["as_of"], assertion["ledger_version"]).canonical_json()
            self.assertEqual(a, b, assertion["id"])

    def test_pinned_version_is_stable_when_later_events_are_appended(self):
        copy = Loaded(self.conn, self.instrument, self.user)  # own portfolio: leaves `main` alone
        a1 = copy.ids("a1000000-0000-4000-8000-000000000001")
        before = self.replay(copy, "P1", "2025-06-30", 17).canonical_json()
        before_max = ledger_replay_store.current_ledger_version(self.conn, copy.portfolio["P1"])
        extra = dataclasses.replace(
            copy.events["P1"][0][3], event_id=uuid.uuid4(), account_id=a1,
            event_date=d("2025-07-01"), source_reference="P1-EXTRA")
        appended = ledger_store.append_event(self.conn, extra)
        self.assertTrue(appended.created)
        self.assertGreater(ledger_replay_store.current_ledger_version(self.conn, copy.portfolio["P1"]), before_max)
        self.assertEqual(self.replay(copy, "P1", "2025-06-30", 17).canonical_json(), before)
        self.assertNotEqual(
            ledger_replay_store.replay(self.conn, copy.portfolio["P1"], d("2025-07-01")).canonical_json(),
            self.replay(copy, "P1", "2025-07-01", 25).canonical_json())

    # -- T11 ---------------------------------------------------------------------------------------

    def test_t11_update_and_delete_are_refused_and_nothing_changes(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        e1 = copy.events["P1"][0][3].event_id
        before = self.rows(copy, "P1")
        self.assertEqual(len(before), 25)
        for sql in ("UPDATE ledger_event SET amount = 10001 WHERE event_id = %s",
                    "DELETE FROM ledger_event WHERE event_id = %s"):
            with self.subTest(sql=sql), self.assertRaises(self.pg.Error):
                self.conn.execute(sql, (e1,))
        self.assertEqual(self.rows(copy, "P1"), before)
        t1 = next(a for a in FIXTURE["portfolios"][0]["assertions"] if a["id"] == "T1")
        check_assertion(self, self.replay(copy, "P1", t1["as_of"], 25), copy.ids, t1, set())

    @unittest.skipUnless(os.environ.get("FINWEB_PG_APP_USER"), "set FINWEB_PG_APP_USER for the app-role variant")
    def test_t11_the_application_role_cannot_update_or_delete(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        app = self.app_connection()
        try:
            before = self.rows(copy, "P1")
            e1 = copy.events["P1"][0][3].event_id
            for sql in ("UPDATE ledger_event SET amount = 10001 WHERE event_id = %s",
                        "DELETE FROM ledger_event WHERE event_id = %s"):
                with self.subTest(sql=sql), self.assertRaises(self.pg.Error):
                    app.execute(sql, (e1,))
            self.assertEqual(self.rows(copy, "P1"), before)
        finally:
            app.close()

    # -- CP1D-1: the whole fixture as the least-privilege role ---------------------------------------

    @unittest.skipUnless(os.environ.get("FINWEB_PG_APP_USER"), "set FINWEB_PG_APP_USER for the app-role variant")
    def test_cp1d1_golden_fixture_appended_and_replayed_as_the_application_role(self):
        app = self.app_connection()
        try:
            copy = Loaded(self.conn, self.instrument, self.user, append_conn=app)  # app appends
            unobserved, ran = set(), 0
            for portfolio, assertion in all_assertions():
                key = portfolio["name"][:2]
                pin = copy.seq[key][assertion["ledger_version"]]  # includes pins 15, 17, 23, 24
                state = ledger_replay_store.replay(app, copy.portfolio[key], d(assertion["as_of"]), pin)
                with self.subTest(assertion=assertion["id"], part="envelope"):
                    self.assertEqual(state.convention_set, "ledger-replay/1.3")
                    self.assertEqual(state.ledger_version, pin)
                check_assertion(self, state, copy.ids, assertion, unobserved)
                # the application role and the owner read the same bytes
                owner = ledger_replay_store.replay(self.conn, copy.portfolio[key], d(assertion["as_of"]), pin)
                with self.subTest(assertion=assertion["id"], part="owner-equals-app"):
                    self.assertEqual(state.canonical_json(), owner.canonical_json())
                ran += 1
            self.assertEqual(ran, 27)
            self.assertEqual(unobserved, NOT_ASSERTED_ITEMS)
            # the mid-correction pin (seq 16) is refused for the application role too
            with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
                ledger_replay_store.replay(app, copy.portfolio["P1"], d("2025-04-02"), copy.seq["P1"][16])
            # unknown portfolio: a typed error, not an empty ledger
            with self.assertRaises(ledger_replay_store.PortfolioNotFoundError):
                ledger_replay_store.current_ledger_version(app, uuid.uuid4())
            # and the default (current) pin works without a caller-supplied version
            current = ledger_replay_store.replay(app, copy.portfolio["P1"], d("2025-06-30"))
            self.assertEqual(current.ledger_version, copy.seq["P1"][25])
        finally:
            app.close()

    # -- T12 ---------------------------------------------------------------------------------------

    def test_t12_resubmitting_seq_1_to_9_inserts_nothing(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        pid = copy.portfolio["P1"]
        before_rows = self.rows(copy, "P1")
        before_max = ledger_replay_store.current_ledger_version(self.conn, pid)
        canonical_before = {a["id"]: self.replay(copy, "P1", a["as_of"], a["ledger_version"]).canonical_json()
                            for a in FIXTURE["portfolios"][0]["assertions"]}
        for seq, _label, _group, event in copy.events["P1"][:9]:
            again = dataclasses.replace(event, event_id=uuid.uuid4())  # a second import: fresh ids
            result = ledger_store.append_event(self.conn, again)
            with self.subTest(seq=seq):
                self.assertFalse(result.created)
                self.assertEqual(result.event.event_id, event.event_id)  # the stored event comes back
        self.assertEqual(self.rows(copy, "P1"), before_rows)
        self.assertEqual(ledger_replay_store.current_ledger_version(self.conn, pid), before_max)
        for a in FIXTURE["portfolios"][0]["assertions"]:
            with self.subTest(assertion=a["id"]):
                self.assertEqual(self.replay(copy, "P1", a["as_of"], a["ledger_version"]).canonical_json(),
                                 canonical_before[a["id"]])

    def test_t12_conflict_a_different_amount_under_the_same_key_is_refused(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        e1 = copy.events["P1"][0][3]
        before = self.rows(copy, "P1")
        clash = dataclasses.replace(
            e1, event_id=uuid.uuid4(), amount=Money(Decimal("10001"), CurrencyCode("USD")))
        with self.assertRaises(ledger_store.IdempotencyConflictError):
            ledger_store.append_event(self.conn, clash)
        self.assertEqual(self.rows(copy, "P1"), before)

    # -- T13 ---------------------------------------------------------------------------------------

    def test_t13_reversed_rows_stay_stored_and_the_reversal_is_retroactive(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        x15 = copy.events["P1"][23][3]  # seq 24 (X15), reversed by seq 25 (X16)
        self.assertEqual(copy.events["P1"][23][1], "X15")
        stored = ledger_store.get_event(self.conn, x15.event_id)
        self.assertIsNotNone(stored)
        self.assertEqual(stored.event.amount.amount, Decimal(500))
        by_id = {a["id"]: a for a in FIXTURE["portfolios"][0]["assertions"]}
        for name in ("T13-L23", "T13-L24", "T13-L25", "T13-retro"):
            with self.subTest(assertion=name):
                a = by_id[name]
                check_assertion(self, self.replay(copy, "P1", a["as_of"], a["ledger_version"]),
                                copy.ids, a, set())
        self.assertEqual(self.replay(copy, "P1", "2025-06-30", 25).canonical_json().replace(
            '"ledger_version":%d' % copy.seq["P1"][25], ""), self.replay(
            copy, "P1", "2025-06-30", 23).canonical_json().replace('"ledger_version":%d' % copy.seq["P1"][23], ""))

    def test_t13_correction_the_x1_row_stays_and_pin_16_is_refused(self):
        copy = Loaded(self.conn, self.instrument, self.user)
        x1 = copy.events["P1"][9][3]
        self.assertEqual(copy.events["P1"][9][1], "X1")
        self.assertIsNotNone(ledger_store.get_event(self.conn, x1.event_id))
        with self.assertRaises(ledger_replay_store.LedgerVersionNotABoundaryError):
            self.replay(copy, "P1", "2025-04-02", 16)  # 16 was never a committed version
        by_id = {a["id"]: a for a in FIXTURE["portfolios"][0]["assertions"]}
        for name in ("V1-before", "V1-after"):  # pins 15 and 17
            with self.subTest(assertion=name):
                a = by_id[name]
                check_assertion(self, self.replay(copy, "P1", a["as_of"], a["ledger_version"]),
                                copy.ids, a, set())


if __name__ == "__main__":
    if "--emit" in sys.argv:
        sys.stdout.write(emit_all())
    else:
        unittest.main()
