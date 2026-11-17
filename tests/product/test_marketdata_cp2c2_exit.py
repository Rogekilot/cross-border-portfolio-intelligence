"""THE CP2 EXIT TEST (PRD section 38.3, Checkpoint 2; tech plan 15.9 as amended in 15.17).

    "same internal analytics contract can consume test data from more than one adapter/mock without
     business-logic change"

ONE analytics-facing consumer, `assemble_valuation_inputs`, UNCHANGED, runs over four complete market-data versions
(worlds, `marketdata_exit_kit`) and over BOTH stores:

  (a) the MOCK adapter (every kind from the mock's own format);
  (b) SYNTHETIC mainland and Hong Kong files in the real Eastmoney and Sina CSV formats, read by their real parsers,
      with a synthetic Alpha Vantage-format US file and a synthetic ECB `eurofxref-hist`-format FX file (path c);
  (c) the same, with the FX in the Frankfurter JSON format instead;
  (d) the same as (b), with the US quotes through a TEST-LOCAL adapter for a format no production code knows (the fourth
      adapter).

Every source id is a SYNTHETIC id (`synthetic.*`), registered `synthetic: true`: no file here is, or is attested as, a
real source (Ruling 4.8; PD-0031/0032), and every result says `synthetic`. Both stores: the in-memory store, and the
PostgreSQL projection read by the application role `finweb_app` under the production grants (opt-in).

THE SIX "NO BUSINESS-LOGIC CHANGE" CHECKS of tech plan 15.9, and where each is:
  1. same code            `test_check_1_the_analytics_source_is_byte_for_byte_unchanged_by_adding_adapters_and_stores`
  2. no adapter in the    `test_check_2_the_analytics_modules_and_both_stores_import_no_adapter_ingest_file_or_vendor`
     dependency
  3. same output          `test_check_3_*`: the value part and the resolution part are byte-identical across every
                          world, the lineage part differs and names the right files and adapters
  4. a fourth adapter     the `novel` world: a test-local adapter, no production edit, the same body
  5. negative controls    `test_check_5_*`
  6. determinism          `test_check_6_*`: across builds, across processes and PYTHONHASHSEED, and (PostgreSQL) across
                          a stored release read in another process

Expected values are written by hand in `marketdata_exit_kit.expected_value_obj` (the arithmetic is shown there) or here,
never read from the code under test.
"""

import ast
import datetime
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import marketdata_exit_kit as x  # noqa: E402
import pg_market_kit as pk  # noqa: E402

k = x.k
c = x.c
kit = x.kit

from marketdata.canonical import canonical_json  # noqa: E402
from marketdata.consumption import ValuationInputsError, assemble_valuation_inputs  # noqa: E402
from marketdata.manifest import (  # noqa: E402
    CONVENTION_SET_ID,
    DataKind,
    ManifestError,
    MarketDataRelease,
    SourceRegistry,
    SourceTermsNotAttestedError,
)
from marketdata.market11 import PARITY_NOT_RUN, market11_conventions  # noqa: E402
from marketdata.port import LookupOutcome  # noqa: E402
from marketdata.states import fx_input_state, price_input_state  # noqa: E402
from persistence import market_data_store as mds  # noqa: E402
from product_contract.vocabulary import ReasonCode, SufficiencyState  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src"
D = datetime.date
ANALYTICS = ("consumption", "port", "conventions", "states", "market11", "calendars", "reconciliation", "store",
             "canonical", "manifest", "contracts", "profiles", "segments")
CALENDAR_ADAPTER = "calendar.manual.calendar"
# by hand: the adapters that read the files the consumer cited on 2025-01-03. C2-1 (CP2 review of 39733e9): every
# print and fixing is dated the as-of date, and a print dated D is CURRENT only under a governing calendar covering D, so
# the calendar files were consulted and are cited too (before the fix the empty interval consulted none)
EXPECTED_ADAPTERS = {
    "mock": {"mock.synthetic.quote", "mock.synthetic.fx", CALENDAR_ADAPTER},
    "formats": {"synthetic.eastmoney_cn.quotes", "synthetic.sina_hk.quotes", "synthetic.alphavantage_us.quotes",
                "synthetic.ecb_direct.fx", CALENDAR_ADAPTER},
    "formats_frankfurter": {"synthetic.eastmoney_cn.quotes", "synthetic.sina_hk.quotes", "synthetic.alphavantage_us.quotes",
                            "synthetic.frankfurter_fx.fx", CALENDAR_ADAPTER},
    "novel": {"synthetic.eastmoney_cn.quotes", "synthetic.sina_hk.quotes", "synthetic.tsv_us.quotes",
              "synthetic.ecb_direct.fx", CALENDAR_ADAPTER},
}


def run_consumer(port, calendars, ident, as_of=x.AS_OF):
    """THE test body, written once: it calls only `assemble_valuation_inputs` with the injected conventions."""
    state = x.replayed_state(ident, as_of)
    return assemble_valuation_inputs(port, ident, state, as_of, x.USD, market11_conventions(calendars))


def parts(inputs):
    return (canonical_json(inputs.value_obj()), canonical_json(inputs.lineage_obj()), canonical_json(inputs.resolution_obj()))


def digest_of(inputs) -> str:
    return hashlib.sha256("|".join(parts(inputs)).encode("utf-8")).hexdigest()


def module_hashes():
    return {n: hashlib.sha256((SRC / "marketdata" / f"{n}.py").read_bytes()).hexdigest() for n in ANALYTICS}


# C2-11 (CP2 review of 39733e9), check 1. The old check hashed the analytics modules before and after building worlds IN THE
# SAME PROCESS, so a committed edit changed both hashes alike and it could never fail. This is a COMMITTED REFERENCE: the
# SHA-256 of each analytics module as it stood when this exit test was last reviewed. Adding an adapter, a store or a world must
# leave them as they are. A deliberate change to the consumer or to a rule it applies is a change to business logic: it changes a
# hash here, fails this test, and is then made in the same commit as the new pin, where review sees it as a changed line. The
# test names the modules that moved. (Recorded 2026-10-01, CP2 closing round, market-data/1.7: market11, reconciliation, store, manifest and profiles moved.
# Re-recorded 2026-10-01, CP3 midpoint fix round, market-data/1.9: manifest, profiles, reconciliation and market11 moved, for the convention-set id (1.8 -> 1.9) and, in
# market11, a read-only `calendars` property on the freshness policy that the performance engine uses to key its freshness vector; no analytics RULE changed.
# Re-recorded 2026-10-01, CP3 re-check round, market-data/1.10: manifest, profiles, reconciliation and market11 moved for the id (1.9 -> 1.10), and `port` moved: the
# `MarketDataPort` Protocol now REQUIRES `contains_synthetic` (CP3-10); no analytics rule changed.
# Re-recorded 2026-10-02, CP4 part A, market-data/1.11: manifest, profiles, reconciliation and market11 moved for the id (1.10 -> 1.11) only; the confirmation-policy test (Ruling 6.4d) is in
# `corporate_actions_service` and `performance_service`, not in an analytics module; no analytics rule changed.
# Re-recorded 2026-10-02, CP4 part A round 2: `manifest` (`SourceRecord.to_obj`, `source_registry_digest`), `store` (`InMemoryMarketData` carries the registry records of its sources, `source_registry_records()`)
# and `market11` (the Current-mode `UNBUILT` item removed, performance/1.12 Ruling 1.7 items 2 and 5) moved; no analytics rule changed.
# Re-recorded 2026-10-02, CP4 part A round 4 (CP4-10): `store` (`source_registry_records()` also refuses a reading whose synthetic flag disagrees with its record); no analytics rule changed.
# Re-recorded 2026-10-02, CP4 part A round 3: `manifest` (`SourceRegistryNotPinnedError`) and `store` (`source_registry_records()` fails closed when a served source has no record) moved; no analytics rule changed.
# Re-recorded 2026-10-02, CP4b-2 (risk/1.1 section 4; tech plan 17.15): the RISK_FREE kind is ADDITIVE: `contracts` (`RiskFreeSeries`, `RiskFreePoint`, the enums, `CalendarKind.RATE_PUBLICATIONS`), `manifest` (`DataKind.RISK_FREE`),
# `canonical` (the series' canonical form), `port` (`RiskFreeLookup`, `RiskFreeSet` and two read methods) and `store` (`RiskFreeEntry`, `risk_free_on`/`risk_free_series`, the registry records of a risk-free source) moved. No price, FX, calendar-
# count or reconciliation rule changed, and `market-data/1.11` is unchanged (risk/1.1 OI-R5: a later market-data issue may absorb the kind).)
# Re-recorded 2026-10-02, CP4c (tech plan 17.16): `calendars` gained `by_id` and `count_after_calendar` (the same counting rules for a calendar NAMED by id, for a benchmark's index calendar); `count_after` is the
# same code through a shared `_count`, and a test says the two give identical counts. No price, FX or calendar rule changed.
# Re-recorded 2026-10-02, CP4c fix round (tech plan 17.17): `store` (`_rf_one_series`: the segments of ONE risk-free series, delivered as file vintages told apart by the adjustment anchor, make one series when
# disjoint, ascending and equal in every declared field; a real/synthetic mix is refused). No price, FX, calendar or reconciliation rule changed.
# Re-recorded 2026-10-02, CP4c round 2 (tech plan 17.18, market-data/1.12 Ruling 0.1 (1.12), CP4M-7): `segments` is NEW and pinned (the rule for several files of one series: disjoint declared coverage, one identity,
# vintage-stable series; pure). `manifest` (the id 1.11 -> 1.12; `VENDOR_ADJUSTED`; `series_keys` carries the anchor only for a vendor-adjusted series; `from_manifests` admits segments the manifests prove disjoint),
# Re-recorded 2026-10-03, CP4d increment 2 (tech plan 17.21): `manifest` only (`SourceRecord.source_priority`, the registry's order of the sources of one benchmark, absent from `to_obj` and so from every registry digest
# when unset). No price, FX, calendar, reconciliation or segment rule changed.
# Re-recorded again 2026-10-03, CP4c round 3 (tech plan 17.19, market-data/1.13, CP4M-10): `segments` (rows outside the declared coverage refused, never widened; "first row held" is a start for a full-history file
# only; the order of checks; the calendar-free projection check) and the id 1.12 -> 1.13 in `manifest`, `profiles`, `reconciliation` and `market11`. No price, FX, calendar or reconciliation RULE changed.
# `profiles`, `reconciliation` and `market11` (the id only) and `store` (the read-side join is now documented as an assertion of what the build admitted) moved. No price, FX, calendar or reconciliation RULE changed.
# Re-recorded 2026-10-24 (PD-0067 decision 6, L-2/N-1): `manifest`, `profiles`, `reconciliation` and `market11` moved for the LABEL only (market-data/1.14 -> 1.15; the profile set 1.14#profiles/3 -> 1.15#profiles/4). The ASTs of the four
# modules differ from the previous ones in those string constants (8 of them) and nowhere else (`ast.dump` equal after reading the old labels as the new); the other lines that moved are comments. No price, FX, calendar, reconciliation or segment RULE changed.
# Re-recorded again 2026-10-24 (review M-1 of the label change): `market11` gained `UNBUILT_1_15` (five `not built` lines for the 1.15 behaviours the label now cites but the code does not run) and `open_items=UNBUILT + UNBUILT_1_15`; `manifest`
# gained only a longer trailing comment on CONVENTION_SET_ID. Shown by `ast.dump`, against the file at HEAD with the new labels read as the old: `manifest` equal; `market11` equal once the `UNBUILT_1_15` assignment is dropped and `UNBUILT + UNBUILT_1_15` is read as `UNBUILT`.
# The pin is a hash of the file's bytes, so a comment moves it too. No price, FX, calendar, reconciliation or segment RULE changed; the only effect on a result is five more open-items lines.
ANALYTICS_PINS = {
    "consumption": "b054374e60b3708403ca8214a46a7f459f443f2722f6eb95868c5c7a6c6891ab",
    "port": "51b547b5dca132945ced514d08d8e9fe30b0967243e0dacd940a4352a1f87b8a",
    "conventions": "4be3363b2c85fb4f5ea1fc2345645019c1472617b2d69e5fc10005f3171b9102",
    "states": "20a019121f831ca000fe63ebdd6a4c7a56858926802265ad8d8ed6c4dacacc24",
    "market11": "81730a26cb4d3cf8c09c01e192653b18ff7a71769f3e2cf2e646248594332444",  # 2026-10-25 (F1 R4a label increment, CP2 section 11 item 35): the three convention ids read market-data/1.16 (FRESHNESS_ID, PRICE_OF_DATE_ID, FX_ID) and `UNBUILT_1_15` is `UNBUILT_1_16`, six `not built` lines for the 1.16 form (five re-worded, one new: securityType / securityType2, the Quant's answer (d)); `open_items=UNBUILT + UNBUILT_1_16`. Shown by `ast.dump` against the file at HEAD: equal once the old labels are read as 1.16, the tuple assignment is dropped from both and its name is read as one name; so the tuple's text is the only content that moved. Before (pin b7286fa4...): 2026-10-24 (PD-0067 decision 6 and its review M-1): market-data/1.15 convention ids (FRESHNESS_ID, PRICE_OF_DATE_ID, FX_ID), plus `UNBUILT_1_15` (five `not built` open-items lines) joined to `open_items`; the AST differs from the pin before the label move (42f45090...) in those three string constants, that tuple and that argument, and nowhere else
    "calendars": "82d6515572baccaa4560edc3ffa7c8c009878ecd9a2b815efe9a70872cbef8e0",
    "reconciliation": "48f6969a8daf0a8005013ad94cd81fc6a5dece738231dd31ea2d28c562246c5e",  # 2026-10-25 (F1 R4a label increment, CP2 section 11 item 35): market-data/1.16, the rule ids only (RULE_ID, TOLERANCE_REF); `ast.dump` of the file at HEAD with market-data/1.15 read as market-data/1.16 equals the new one (the other lines that moved are comments). Before (pin dd72ed82...): 2026-10-24 (PD-0067 decision 6): market-data/1.15, the rule ids only (RULE_ID, TOLERANCE_REF); the AST differs from the previous pin (1f82af6b...) in those two string constants and nowhere else. Before: market-data/1.14 Ruling 4.5 (1.14): the issuer's stated payment is compared only when both sides state one; the rule ids
    "store": "ed4acf278a6ca07264cac100faa2294a24a4d4290dc100c3a6bf80bd7493fc78",  # 2026-10-25 (F1 R4a, market-data/1.16 section 11 item 28, Ruling 4.7 item 1): `quote_on` adds the cause NO_ADMITTED_SOURCE only when M holds no series of the listing at all (an excluded series is the cause, SERIES_CONTRADICTED; freshness stays UNKNOWN), and `SeriesExclusion.test` documents `V0_FX_DUPLICATE_DATE` (a comment). Nothing else in the file moved: no price, FX, calendar or reconciliation RULE changed. Before (pin 8951ceb9...): 2026-10-24 (night run, B2 fix round, review M-1): the constructor refuses a REAL reading whose listing's market its source's profile does not cover or admit (`_require_readings_admitted`, replacing the pin-time source-level check of B2); refusal only, no price, FX, calendar or reconciliation RULE changed
    "canonical": "a5d5ceb45e93c70489a8abbbe51e0080d5c54d859f0277800df5ee9e2c303a4d",  # CP4 final fix round (risk/1.8): `paid_amount`, present in the canonical form only when stated
    "manifest": "fe4e5201f7004fe514a759b24ca5e739b66e268998a8670e9a3edfca5ac9b40a",  # 2026-10-25 (F1 R4a label increment, CP2 section 11 item 35): CONVENTION_SET_ID = market-data/1.16 (was 1.15, pin 0b9103e2...); `ast.dump` of the file at HEAD with 1.15 read as 1.16 equals the new one; only the string constant and its trailing comment (which now lists the 1.16 behaviours not built) moved. Before: 2026-10-24 (PD-0067 decision 6 and its review M-1): CONVENTION_SET_ID = market-data/1.15 (was 1.14, pin bdf80447...); the AST differs in that one string constant and nowhere else; the trailing comment now lists the 1.15 behaviours not built
    "contracts": "7cb650353a67e27b72b06632635c66e26e47951d5e98a607b9b2b522549f8851",  # 2026-10-25 (F1 R4a): a COMMENT only (the note on `adjustment_label_source` now says the profile's status is DECLARED since market-data/1.16, MEMORY before); the AST equals the previous pin's (ac990c22...), checked with ast.dump on `git show HEAD:` against the working file. Before: market-data/1.14 Ruling 7.1 (1.14): `paid_currency` must differ from the declared currency (enforced);  # `CorporateActionObservation.paid_amount` (optional, a dividend's stated payment; risk/1.8 Ruling 5.5 (1.8) item 2). No price, FX, calendar or reconciliation rule changed.
    "profiles": "eae4650fc831dbe79bde82bac5372896354c4c2190706ff6a02d52efeac08bd1",  # 2026-10-25 (F1 R4a label increment, CP2 section 11 item 35): CONVENTION_SET = market-data/1.16 and PROFILE_SET_VERSION = market-data/1.16#profiles/5 (were 1.15 and 1.15#profiles/4); the counter moves because the profile content did (the Quant's answer (b): the DECLARED `call_adjustment` entries of the two Alpha Vantage `TIME_SERIES_DAILY` calls, the three US MICs ARCX/BATS/XASE and their zones, and the Ruling 4.7 item 6 gate). A comment on the two constants was reworded. No admitted profile's price, FX, calendar or reconciliation rule changed. Before (pin 38befe69...): 2026-10-25 (F1 R4a, market-data/1.16 section 11 item 27, Ruling 4.7 item 6 and Ruling 2.2 item 1): `MIC_MARKET` gains ARCX, BATS, XASE (US) and `EXCHANGE_ZONES` their zone America/New_York; `listing_market_refusal` applies the Ruling's conditions in its order (an unmapped or unknown MIC is LISTING_EXCHANGE_UNKNOWN naming the MIC; a source with no profile is SOURCE_NOT_ADMITTED; then coverage, then admission); both were `not judged here` before. Admission refusals only: no price, FX, calendar or reconciliation rule changed; the label constants are still NOT moved. Before (pin 2d16366e...): 2026-10-25 (F1 R4a, market-data/1.16 section 11 item 23, PD-0066 decision 3): `call_adjustment` entries are `CallAdjustment(adjustment, status, reference)` and not a bare status string; `alphavantage.us` and `alphavantage.cn` `TIME_SERIES_DAILY` carry status DECLARED and the reference "PD-0066 decision 3" (was MEMORY, hard-coded in the adapter); new `CallAdjustment`, `CALL_ADJUSTMENT_STATUSES`, `PD_0066_DECISION_3`. No price, FX, calendar or reconciliation rule changed; the label constants are NOT moved in this pin (they move with the label step). Before (pin <private pin, PD-0083>...): 2026-10-24 (PD-0067 decision 6, L-2/N-1): CONVENTION_SET = market-data/1.15 and PROFILE_SET_VERSION = market-data/1.15#profiles/4 (were 1.14 and 1.14#profiles/3, pin <private pin, PD-0083>...); the AST differs in those two string constants and nowhere else; no profile entry, status or field changed; the counter moves because the content did when `alphavantage.cn` was added. Before that, 2026-10-24 (night run, B2 fix round, review M-1): `listing_market_refusal` / `require_listing_market` (the per-listing form of the gate: SOURCE_MARKET_NOT_COVERED, LISTING_EXCHANGE_UNKNOWN) and `not_admitted_code` follows the order of `not_admitted_reason`; on top of 2026-10-23 (B2, market-data/1.15 section 7A): the TO_OBSERVE `alphavantage.cn` profile and `gate_refusal`. (CONVENTION_SET and PROFILE_SET_VERSION then still carried market-data/1.14); no admitted profile changed
    "segments": "604cf42beb243c051d156192311dc5bf6f8872f97c8b9c5ed66349c44b4a6c7c",
}


def unpinned_changes(hashes):
    """The analytics modules whose hash is not the committed pin (empty when nothing moved)."""
    return sorted(n for n in ANALYTICS if hashes.get(n) != ANALYTICS_PINS.get(n))


# The exact prices and rates the files say, written by hand here (the same facts the kit writes into every world). The adapters'
# OUTPUT is compared with them directly, not through the consumer: a quirk cancelled by a compensating branch in the consumer
# (an adapter that emits x10 and a consumer that divides by 10 for that source) leaves the consumer's values right and the
# adapter's wrong, and this is where it shows (M1 of the CP2 review).
HAND_CLOSES = {("AAPL", "XNAS"): Decimal("151.10"), ("0700", "XHKG"): Decimal("332.6"), ("600519", "XSHG"): Decimal("1502.00")}
HAND_FIXINGS = {"USD": Decimal("1.0810"), "HKD": Decimal("8.4100"), "CNY": Decimal("7.8100")}


def imported_names(path: Path):
    names = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


class _ExitChecks:
    """The checks, written once; a concrete class supplies `ports()` (flavour -> (port, calendars, identity))."""

    FLAVOURS = x.FLAVOURS

    def ports(self):
        raise NotImplementedError

    def run_all(self, as_of=x.AS_OF):
        return {fl: run_consumer(port, cal, ident, as_of) for fl, (port, cal, ident) in self.ports().items()
                if fl in self.FLAVOURS}

    # -- the criterion itself ----------------------------------------------------------------------------------------

    def test_the_same_consumer_gives_the_hand_derived_values_over_every_adapter_mock_and_format(self):
        results = self.run_all()
        self.assertEqual(set(results), set(x.FLAVOURS))
        for fl, inputs in results.items():
            ident = self.ports()[fl][2]
            self.assertEqual(x.normalize(inputs.value_obj()), x.normalize(x.expected_value_obj(ident)), fl)

    def test_check_3b_every_adapters_own_output_equals_the_hand_derived_price_and_rate_before_the_consumer_touches_it(self):
        # C2-11: the consumer's values were already compared with hand values per world, which a compensating pair
        # (adapter x10, consumer / 10 for that source) passes. The port's raw readings are the adapters' output.
        for fl, (port, _, ident) in self.ports().items():
            if fl not in self.FLAVOURS:
                continue
            for (ticker, mic), price in HAND_CLOSES.items():
                readings = port.quotes(x.lid(ident, ticker, mic), x.AS_OF, x.AS_OF).readings
                self.assertEqual([r.observation.price for r in readings], [price], (fl, ticker))
            for ccy, rate in HAND_FIXINGS.items():
                readings = port.fx_series(k.EUR, k.CurrencyCode(ccy), x.AS_OF, x.AS_OF).readings
                self.assertEqual([r.observation.rate for r in readings], [rate], (fl, ccy))

    def test_check_3c_the_consumer_side_modules_never_branch_on_a_source(self):
        # no reference to a source id, and no string-prefix/suffix test, in the modules a consumer reaches (the way a
        # compensating branch in the consumer would be written)
        for name in ("consumption", "port", "states"):
            tree = ast.parse((SRC / "marketdata" / f"{name}.py").read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute):
                    self.assertNotIn(node.attr, ("source_id", "independence_group", "endswith", "startswith"), f"{name}.py: .{node.attr}")
                if isinstance(node, ast.Name):
                    self.assertNotEqual(node.id, "source_id", f"{name}.py names source_id")

    def test_check_3_value_and_resolution_parts_are_byte_identical_across_worlds_and_lineage_differs_correctly(self):
        results = self.run_all()
        values = {fl: parts(r)[0] for fl, r in results.items()}
        resolutions = {fl: parts(r)[2] for fl, r in results.items()}
        self.assertEqual(len(set(values.values())), 1, "the value part must be byte-identical across every adapter")
        self.assertEqual(len(set(resolutions.values())), 1, "so must the resolution part (date used, missed, causes)")
        lineages = {fl: parts(r)[1] for fl, r in results.items()}
        self.assertEqual(len(set(lineages.values())), len(x.FLAVOURS), "provenance differs per world")
        for fl, inputs in results.items():
            port = self.ports()[fl][0]
            consumed = {r for ref in inputs.data_set_refs for r in ref.consumed}
            self.assertEqual({r.adapter_id for r in consumed}, EXPECTED_ADAPTERS[fl], fl)
            self.assertEqual({ref.release_id for ref in inputs.data_set_refs}, {port.release_id()}, fl)
            self.assertEqual({ref.kind for ref in inputs.data_set_refs}, {DataKind.QUOTE, DataKind.FX}, fl)
            self.assertEqual({ref.convention_set_id for ref in inputs.data_set_refs}, {"market-data/1.16"}, fl)  # section 11 item 13 (1.8); 1.16 from the label increment of 2026-10-25
            self.assertTrue({r.file_sha256 for r in consumed} <= set(self.releases()[fl].files), fl)
        self.assertEqual(len({r.release_id for r in results.values()}), len(x.FLAVOURS))

    def releases(self):
        return {fl: w.release for fl, w in self.worlds.items()}

    def test_the_resolution_part_is_the_hand_derived_one(self):
        # as-of = the date of every print and of the fixing: no session or fixing is missed, no calendar is counted
        inputs = self.run_all()["formats"]
        res = inputs.resolution_obj()
        for q in res["quotes"]:
            self.assertEqual((q["outcome"], q["date_used"], q["missed_count"], q["notes"], q["synthetic"]),
                             ("FOUND", D(2025, 1, 3), 0, [], True))
        fx = {f["currency"]: f for f in res["fx"]}
        # HKD -> USD crosses x_USD = 1.0810 over x_HKD = 8.4100 (EUR quotes of 2025-01-03): HKD per USD = 8.41 / 1.081
        # = 7.7798 lies inside the 7.75..7.85 peg band (inclusive): PASS. No CNY leg: no parity note.
        self.assertEqual((fx["HKD"]["date_used"], fx["HKD"]["missed_count"]), (D(2025, 1, 3), 0))
        self.assertEqual(fx["HKD"]["cross"], {"numerator": Decimal("1.0810"), "denominator": Decimal("8.4100"),
                                              "fixing_date": D(2025, 1, 3)})
        self.assertEqual(fx["HKD"]["checks"], [["HKD_PEG_BAND", "PASS"]])
        self.assertEqual(fx["HKD"]["notes"], [])
        # CNY: no central-parity series is admitted, so the band check did not run and says so (Ruling 1.5a)
        self.assertEqual(fx["CNY"]["checks"], [["CNY_PARITY_BAND", "UNVERIFIABLE"]])
        self.assertEqual(fx["CNY"]["notes"], [PARITY_NOT_RUN])

    def test_every_result_is_marked_synthetic_conformant_and_lists_what_is_still_open(self):
        for fl, inputs in self.run_all().items():
            self.assertTrue(inputs.synthetic, fl)  # Ruling 4.8: a result from a synthetic version is never a real market fact
            self.assertTrue(inputs.conformant, fl)
            self.assertTrue(any(i.startswith("not built:") for i in inputs.open_items), fl)

    def test_a_later_as_of_ages_every_input_by_one_missed_session_and_one_missed_fixing(self):
        # sessions and fixing days (calendars): 2, 3, 6, 7 January. As-of 6 January: the last print and fixing are the 3rd.
        # Sessions d with 3 < d <= 6: {6 January} -> 1 missed -> AVAILABLE + STALE_DATA (Ruling 5.2); the same for fixings.
        for fl, inputs in self.run_all(x.LATER).items():
            for q in inputs.quotes:
                st = price_input_state(q.lookup)
                self.assertEqual((q.lookup.outcome, q.lookup.date_used, q.lookup.missed_count, st.state, st.reason),
                                 (LookupOutcome.FOUND, x.AS_OF, 1, SufficiencyState.AVAILABLE, ReasonCode.STALE_DATA), fl)
            for f in inputs.fx:
                st = fx_input_state(f.lookup)
                self.assertEqual((f.lookup.outcome, f.lookup.date_used, f.lookup.missed_count, st.state, st.reason),
                                 (LookupOutcome.FOUND, x.AS_OF, 1, SufficiencyState.AVAILABLE, ReasonCode.STALE_DATA), fl)

    def test_the_consumer_refuses_a_mismatched_as_of(self):
        port, cal, ident = self.ports()["mock"]
        state = x.replayed_state(ident, x.AS_OF)
        with self.assertRaises(ValuationInputsError):
            assemble_valuation_inputs(port, ident, state, x.LATER, x.USD, market11_conventions(cal))

    # -- Ruling 4.7: mainland and Hong Kong listings with no admitted source ---------------------------------------------

    def test_ruling_4_7_cn_and_hk_listings_with_no_admitted_source_are_missing_price_history_with_the_cause(self):
        port, cal, ident = self.ports()[x.NO_CN_HK]
        inputs = run_consumer(port, cal, ident)
        by = {q.listing_id: q for q in inputs.quotes}
        aapl = by[x.lid(ident, "AAPL", "XNAS")]
        self.assertEqual((aapl.lookup.outcome, aapl.lookup.selected.observation.price),
                         (LookupOutcome.FOUND, Decimal("151.10")))
        for ticker, mic, market in (("0700", "XHKG", "HK"), ("600519", "XSHG", "CN")):
            lk = by[x.lid(ident, ticker, mic)].lookup
            st = price_input_state(lk)
            self.assertEqual((lk.outcome, lk.selected, st.state, st.reason),
                             (LookupOutcome.NO_HISTORY, None, SufficiencyState.INSUFFICIENT_DATA, ReasonCode.MISSING_PRICE_HISTORY), ticker)
            self.assertTrue(any(n.startswith(f"NO_ADMITTED_SOURCE: market {market}") for n in lk.lineage_notes), lk.lineage_notes)
            self.assertIs(lk.freshness.state, c.FreshnessState.UNKNOWN)  # nothing was ever printed: not STALE
        # the ledger facts stay available: only what combines a quantity with a price is suppressed
        self.assertEqual(sorted(p.quantity.value for p in inputs.positions), [Decimal(2), Decimal(10), Decimal(100)])

    def test_ruling_4_7_the_committed_source_registry_admits_no_mainland_or_hong_kong_price_source(self):
        registry = SourceRegistry.from_json((REPO / "data" / "marketdata" / "SOURCES.json").read_text(encoding="utf-8"))
        for source_id in ("akshare.cn", "akshare.hk", "akshare_sina.cn", "akshare_sina.hk", "baostock.cn"):
            self.assertFalse(registry.get(source_id).terms_attested, source_id)
            with self.assertRaises(SourceTermsNotAttestedError):
                registry.require_attested(source_id)  # a real CN or HK file is refused before its payload is read

    # -- check 5: negative controls -----------------------------------------------------------------------------------------

    def test_check_5_a_file_with_a_wrong_hash_a_source_without_attestation_and_a_stale_release_id_are_refused(self):
        from marketdata.files import FileHashMismatchError, FileStore  # noqa: PLC0415
        from marketdata.ingest import build_in_memory_market_data  # noqa: PLC0415
        from marketdata.manifest import SourceRecord  # noqa: PLC0415

        with tempfile.TemporaryDirectory() as tmp:  # (i) a changed byte: the hash no longer matches
            w = x.build_world("formats", root=Path(tmp))
            payload = next(p for p in Path(tmp).rglob("*.csv") if "ecb" in str(p))
            os.chmod(payload, 0o644)
            payload.write_bytes(payload.read_bytes().replace(b"1.0810", b"1.0811"))
            files = FileStore(Path(tmp))
            with self.assertRaises(FileHashMismatchError):
                build_in_memory_market_data(w.release, files, files.load_registry(), w.adapters, x.identity(), catalog_calendars={})
        with tempfile.TemporaryDirectory() as tmp:  # (ii) a source with no terms attestation: refused, never read
            root = Path(tmp)
            kit.write_registry(root, extra=[SourceRecord(x.SRC_US, "US", "alphavantage", "alphavantage")])  # not synthetic, no terms_check
            m = kit.write_file(root, source_id=x.SRC_US, kind=DataKind.QUOTE, payload_format="alphavantage_csv_daily/1",
                               payload=x.av_us_csv(x._rows("AAPL", "XNAS")), label="AAPL", ext="csv", currency=x.USD,
                               usage_scope=c.UsageScope.INTERNAL_DEVELOPMENT_ONLY, retrieved_by="human",
                               source_identifiers=("AAPL",))
            files = FileStore(root)
            with self.assertRaises(SourceTermsNotAttestedError):
                build_in_memory_market_data(MarketDataRelease.from_manifests("r", [m], []), files, files.load_registry(),
                                            x.world_specs("formats")[1], x.identity(), catalog_calendars={})
        # (iii) a release whose content was changed but whose id was not
        release = self.releases()["mock"]
        tampered = release.to_json().replace('"name": "exit-mock"', '"name": "exit-mocx"')
        with self.assertRaises(ManifestError):
            MarketDataRelease.from_json(tampered)

    def test_check_5_an_adapter_that_breaks_the_contract_is_refused_not_loaded(self):
        # a float price, a naive timestamp, a ticker given as the listing key and a vendor-shaped extra field
        from decimal import Decimal  # noqa: PLC0415

        ids = c.ExternalIdentifiers(vendor_id="A", source_id="s")
        timing, lineage = c.SourceTiming(), k.lineage()
        with self.assertRaises((TypeError, c.ObservationRuleError)):
            c.UnresolvedQuote(ids, D(2025, 1, 3), 150.25, k.USD, timing, lineage)  # a float, never a Decimal
        with self.assertRaises((TypeError, c.ObservationRuleError)):
            c.SourceTiming(source_time=datetime.datetime(2025, 1, 3, 12, 0))  # naive
        with self.assertRaises((TypeError, c.ObservationRuleError)):
            c.QuoteObservation("AAPL", D(2025, 1, 3), Decimal("1"), k.USD, timing, lineage)  # a ticker as the key
        from marketdata.adapters.base import AdapterOutput  # noqa: PLC0415

        with self.assertRaises(TypeError):
            AdapterOutput(vendor_extra={"close": 1})  # no vendor-shaped extra field exists on the output type

    def test_check_5_a_missing_value_is_stated_never_filled_and_a_number_is_withheld_only_when_insufficient(self):
        port, cal, ident = self.ports()["formats"]
        aapl, conv = x.lid(ident, "AAPL", "XNAS"), market11_conventions(cal)
        # 7 January: sessions after the last print (3 January) up to the 7th are {6, 7}: 2 missed -> LIMITED, and the
        # number IS returned with its state (a LIMITED value is never withheld: PD-0007)
        limited = port.quote_on(aapl, D(2025, 1, 7), conv)
        st = price_input_state(limited)
        self.assertEqual((limited.outcome, limited.missed_count, limited.selected is not None, st.state, st.reason),
                         (LookupOutcome.FOUND, 2, True, SufficiencyState.LIMITED, ReasonCode.STALE_DATA))
        # 15 February is outside the calendar's coverage (1-31 January): the interval cannot be counted, the number is
        # withheld, INSUFFICIENT_DATA with NO reason code, the cause in lineage; nothing is filled or inferred
        unknown = port.quote_on(aapl, D(2025, 2, 15), conv)
        st = price_input_state(unknown)
        self.assertEqual((unknown.outcome, unknown.selected, st.state, st.reason),
                         (LookupOutcome.FRESHNESS_UNKNOWN, None, SufficiencyState.INSUFFICIENT_DATA, None))
        self.assertTrue(any("CALENDAR_COVERAGE_GAP" in n for n in unknown.lineage_notes))

    # -- check 6: determinism ---------------------------------------------------------------------------------------------------

    def test_check_6_two_independent_builds_give_byte_identical_output(self):
        for fl in x.FLAVOURS:
            again = x.build_world(fl)
            self.addCleanup(again.close)
            first = self.run_all()[fl]
            second = run_consumer(again.store, again.built.calendars, again.ident)
            self.assertEqual(parts(first), parts(second), fl)


class ExitCriterionInMemoryTests(_ExitChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.worlds = {fl: x.build_world(fl) for fl in x.FLAVOURS + (x.NO_CN_HK,)}
        for w in cls.worlds.values():
            cls.addClassCleanup(w.close)

    def ports(self):
        return {fl: (w.store, w.built.calendars, w.ident) for fl, w in self.worlds.items()}

    def test_check_1_the_analytics_source_matches_its_committed_pin_and_is_unchanged_by_adding_adapters_and_stores(self):
        # (i) AGAINST A COMMITTED REFERENCE (C2-11): this fails if any analytics module is edited without the pin moving
        self.assertEqual(unpinned_changes(module_hashes()), [], "an analytics module changed: that is a business-logic change; "
                         "review it, then update ANALYTICS_PINS in the same commit")
        # (ii) and adding adapters and a store changes none of them
        before = module_hashes()
        for fl in ("formats", "novel"):  # a new set of adapters (and a fourth) is added and exercised
            w = x.build_world(fl)
            self.addCleanup(w.close)
            run_consumer(w.store, w.built.calendars, w.ident)
        self.assertEqual(before, module_hashes())
        self.assertIn("consumption", before)  # the consumer file itself is in the set

    def test_check_1_can_fail_a_changed_module_is_named_and_a_missing_pin_is_a_change(self):
        # the negative control of check 1: the comparison against the pins reports exactly the module that moved
        real = module_hashes()
        self.assertEqual(unpinned_changes(dict(real, consumption="0" * 64)), ["consumption"])
        self.assertEqual(unpinned_changes(dict(real, market11=hashlib.sha256(b"# edited").hexdigest(), states="1" * 64)),
                         ["market11", "states"])
        self.assertEqual(unpinned_changes({k_: v for k_, v in real.items() if k_ != "port"}), ["port"])
        self.assertEqual(set(ANALYTICS_PINS), set(ANALYTICS))

    def test_check_2_the_analytics_modules_and_both_stores_import_no_adapter_ingest_file_or_vendor(self):
        banned = ("marketdata.adapters", "marketdata.ingest", "marketdata.files", "marketdata_tools")
        # C2-11: the vendor words now include the UPSTREAM names (`sina`, `eastmoney`) and the ECB file's own name
        # (`eurofxref`; the same list as the import-boundary test), over the modules it checks plus the database store
        vendors = ("akshare", "baostock", "tushare", "yfinance", "alphavantage", "alpha vantage", "frankfurter", "cfets",
                   "openfigi", "pandas", "sina", "eastmoney", "eurofxref")
        vendor_free = ("consumption", "port", "conventions", "store", "contracts", "market11", "calendars", "states")
        # `ecb` is the PUBLISHER of the fixing the conventions define (Ruling 1.1), so the convention modules name it; the
        # modules that only carry a result to the analytics layer have no business with it, nor with a source id
        consumer_facing = ("consumption", "port", "states")
        for path in [SRC / "marketdata" / f"{n}.py" for n in ANALYTICS] + [SRC / "persistence" / "market_data_store.py"]:
            names = imported_names(path)
            for b in banned:
                self.assertFalse({n for n in names if n == b or n.startswith(b + ".")}, f"{path.name} imports {b}")
        for path in [SRC / "marketdata" / f"{n}.py" for n in vendor_free] + [SRC / "persistence" / "market_data_store.py"]:
            text = path.read_text(encoding="utf-8").lower()
            for v in vendors:
                self.assertNotIn(v, text, f"{path.name} names {v}")
        for path in [SRC / "marketdata" / f"{n}.py" for n in consumer_facing]:
            self.assertNotIn("ecb", path.read_text(encoding="utf-8").lower(), f"{path.name} names ecb")

    def test_check_6_output_is_byte_identical_across_processes_and_hash_seeds(self):
        for fl in x.FLAVOURS:
            seen = set()
            for seed in ("1", "2", "random"):
                env = dict(os.environ, PYTHONHASHSEED=seed)
                out = subprocess.run([sys.executable, str(Path(__file__)), "digest", fl], env=env, cwd=str(REPO),
                                     capture_output=True, text=True, timeout=180)
                self.assertEqual(out.returncode, 0, out.stderr)
                seen.add(out.stdout.strip())
            self.assertEqual(len(seen), 1, (fl, seen))
            self.assertEqual(seen.pop(), digest_of(self.run_all()[fl]), fl)  # and equals this process's own


_SKIP = pk.skip_reason()


@unittest.skipIf(bool(_SKIP), _SKIP)
class ExitCriterionPostgreSQLTests(_ExitChecks, unittest.TestCase):
    """The SAME checks over the PostgreSQL projection, read by the application role under the production grants, plus the
    two-store identity: for every world the memory store and the database give the same bytes."""

    @classmethod
    def setUpClass(cls):
        cls.db = pk.PgSchema().open()  # migrated, granted to the app role
        cls.addClassCleanup(cls.db.close)
        cls.memory_worlds = {fl: x.build_world(fl) for fl in x.FLAVOURS + (x.NO_CN_HK,)}
        for w in cls.memory_worlds.values():
            cls.addClassCleanup(w.close)
        cls.worlds = cls.memory_worlds
        pk.insert_identity(cls.db.owner, next(iter(cls.memory_worlds.values())).ident)
        cls.results = {}
        for fl, w in cls.memory_worlds.items():
            cls.results[fl] = mds.write_release(cls.db.owner, w.release, w.built.manifests, w.store.export(), w.built.calendars)
        cls.app = cls.db.app_connection()
        cls.addClassCleanup(cls.app.close)
        cls.pg_ports = {}
        for fl, w in cls.memory_worlds.items():
            pg = mds.read_release(cls.app, w.release.release_id, exchange_of=w.ident.exchange_mic, registry=k.registry_for(w.store))
            cls.pg_ports[fl] = (pg, pg.calendars(), w.ident)

    def ports(self):
        return self.pg_ports

    def test_the_consumer_reads_as_finweb_app_and_the_store_is_the_postgresql_projection(self):
        self.assertEqual(self.app.execute("SELECT current_user").fetchone()[0], self.db.app_role)
        for fl, (port, _, _) in self.pg_ports.items():
            self.assertIsInstance(port, mds.PostgresMarketData, fl)

    def test_both_stores_give_byte_identical_value_lineage_and_resolution_output_for_every_world(self):
        for fl in x.FLAVOURS + (x.NO_CN_HK,):
            w = self.memory_worlds[fl]
            in_memory = run_consumer(w.store, w.built.calendars, w.ident)
            in_db = run_consumer(*self.pg_ports[fl])
            self.assertEqual(parts(in_memory), parts(in_db), fl)
            self.assertEqual(digest_of(in_memory), digest_of(in_db), fl)
            later_memory = run_consumer(w.store, w.built.calendars, w.ident, x.LATER)
            later_db = run_consumer(*self.pg_ports[fl], x.LATER)
            self.assertEqual(parts(later_memory), parts(later_db), fl)

    def test_check_1_the_analytics_source_matches_its_pin_and_is_unchanged_by_adding_the_database_store(self):
        self.assertEqual(unpinned_changes(module_hashes()), [])  # the committed reference (C2-11), as in memory
        before = module_hashes()
        for fl in x.FLAVOURS:
            run_consumer(*self.pg_ports[fl])
        self.assertEqual(before, module_hashes())

    def test_check_6_a_stored_release_read_in_another_process_gives_the_same_bytes(self):
        import test_postgres_least_privilege as lp  # noqa: PLC0415,F401  (keeps the grant spec imported once)

        for fl in x.FLAVOURS:
            env = dict(os.environ, PYTHONHASHSEED="random", FINWEB_EXIT_SCHEMA=self.db.schema)
            out = subprocess.run([sys.executable, str(Path(__file__)), "pgdigest", fl, self.memory_worlds[fl].release.release_id],
                                 env=env, cwd=str(REPO), capture_output=True, text=True, timeout=180)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), digest_of(self.run_all()[fl]), fl)

    def test_check_6_a_projection_rebuilt_from_the_same_files_in_a_fresh_schema_gives_the_same_bytes(self):
        fl = "formats"
        w = self.memory_worlds[fl]
        rebuilt = x.build_world(fl, root=w.root)
        scratch = pk.PgSchema().open()
        try:
            pk.insert_identity(scratch.owner, rebuilt.ident)
            result = mds.write_release(scratch.owner, rebuilt.release, rebuilt.built.manifests, rebuilt.store.export(),
                                       rebuilt.built.calendars)
            self.assertEqual(result.projection_digest, self.results[fl].projection_digest)
            app = scratch.app_connection()
            pg = mds.read_release(app, rebuilt.release.release_id, exchange_of=rebuilt.ident.exchange_mic, registry=k.registry_for(rebuilt.store))
            self.assertEqual(digest_of(run_consumer(pg, pg.calendars(), rebuilt.ident)), digest_of(self.run_all()[fl]))
            app.close()
        finally:
            scratch.close()


def _main(argv):
    """Subprocess entry points for the determinism checks."""
    if argv[0] == "digest":
        w = x.build_world(argv[1])
        print(digest_of(run_consumer(w.store, w.built.calendars, w.ident)))
    elif argv[0] == "pgdigest":
        from persistence import connection  # noqa: PLC0415

        ident = x.identity()
        conninfo = connection.build_conninfo(
            dbname=os.environ[connection.DATABASE_VAR], user=os.environ[pk.APP_USER_VAR],
            socket=os.environ.get(connection.SOCKET_VAR) or None)
        conn = connection.connect(conninfo, autocommit=True)
        conn.execute('SET search_path TO "%s"' % os.environ["FINWEB_EXIT_SCHEMA"])
        w = x.build_world(argv[1])  # the registry in force: the records the build of this flavour read (`read_release` requires one)
        pg = mds.read_release(conn, argv[2], exchange_of=ident.exchange_mic, registry=k.registry_for(w.store))
        print(digest_of(run_consumer(pg, pg.calendars(), ident)))
        conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("digest", "pgdigest"):
        _main(sys.argv[1:])
    else:
        unittest.main()
