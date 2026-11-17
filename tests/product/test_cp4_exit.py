"""THE CP4 EXIT TEST (PRD 38.3 / tech plan 17, CP4e: "every metric includes definition/version/data requirements and fails safely when inputs are insufficient"; risk/1.4 Ruling 7.5).

The exit criterion is proved here, in one module, as seven statements. The expected cells are the Quant's (`risk/1.4` Rulings 7.1 to 7.5 and the golden fixtures' own asserted items), never the engine's output:
a cell is written by hand from the rulings, and WHEREVER a fixture asserts the same metric on the same request the cell is compared with the fixture's item (`CellsAgreeWithTheFixtureTests`).

  (a) THE REGISTRY IS COMPLETE. Every one of the 12 metrics has an entry that carries every requirement of PRD 16.3 (definition, data requirements, minimum sample, window and frequency, annualization,
      benchmark requirement, risk-free requirement, FX treatment, missing-data policy, known limitations), and every result of every scenario below names that entry (`method_key`) and the registry id
      and digest in its manifest: its definition, version and data requirements are one lookup away, and the lookup cannot be of another version.
  (b) FAILS SAFELY. Every metric x every HG3 edge case (PRD 38.4: insufficient history, missing FX, missing cost basis, cash-only, single security, multi-currency, recently listed, unavailable benchmark,
      no risk-free source; plus the engineer-added zero variance, Current mode, account scope, snapshot, zero-capital period, split suppression) gives the state, reason and detail Ruling 7.5 (with 7.1 to 7.4)
      gives, and a refused metric presents NO NUMBER: no value, no exact, no radicand, no intermediates, no comparability, no decomposition, no drawdown dates.
  (c) THE RISK AVAILABILITY MATRIX is complete: metrics x conditions, every cell present, every cell holds, and a metric or a condition added without a row fails.
  (d) DETERMINISM across processes and five PYTHONHASHSEED values for every scenario; the engine holds no memo (a test fails if one appears, and then demands the on/off comparison).
  (e) `reproduce_risk` gives REPRODUCED for EVERY golden result (parts 1 to 3, historical and Current mode), RESULT_NOT_COMPARED without a digest, RESULT_DIFFERS for a wrong one.
  (f) UAT-03: a selection change moves only the benchmark-dependent group (the engine partition here; the same through `risk_service` and PostgreSQL when the database tests are enabled).
  (g) CP3 NON-REGRESSION: the byte-identity test holds (the CP3 results are what they were).

OPEN FINDINGS. `OPEN_FINDINGS` names what is reported to the Quant and not decided here; `test_the_exit_criterion_has_no_open_finding` fails while one is listed. It is EMPTY: the CP4e finding (the active return
over a window that contains a zero-capital period) was ruled in `risk/1.5` Ruling 6.9 (1.5) as INSUFFICIENT_DATA, detail `ZERO_CAPITAL_PERIOD`, no reason (cell below; mutation M-C30). The expected cells are those of `risk/1.6`.
"""

from __future__ import annotations

import copy
import dataclasses
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import unittest
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import cp4_golden_kit as g  # noqa: E402
import pg_market_kit as pk  # noqa: E402
import test_cp1_reconstruction as cp1  # noqa: E402
import test_performance_cp3_byte_identity as byte_identity  # noqa: E402
import test_postgres_risk_service as pg_service  # noqa: E402

from product_contract.vocabulary import SufficiencyState as SS  # noqa: E402
from risk.engine import COMPUTABLE, RISK_ENGINE_ID, reproduce_risk  # noqa: E402
from risk.manifest import RiskReproductionStatus as St  # noqa: E402
from risk.registry import REGISTRY  # noqa: E402
from risk_service import default_view as dv  # noqa: E402
from risk_service import groups as grp  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
D = g.D

# --- the cells ------------------------------------------------------------------------------------------------------------------------------

SHORT = {"vol": "risk_volatility", "ds": "risk_downside_deviation", "dd": "risk_max_drawdown", "sharpe": "risk_sharpe", "sortino": "risk_sortino", "beta": "risk_beta", "r2": "risk_r_squared",
         "alpha": "risk_alpha_jensen", "active": "risk_active_return", "te": "risk_tracking_error", "ir": "risk_information_ratio", "bret": "benchmark_return"}
ALL = tuple(sorted(SHORT.values()))
D4 = ("vol", "ds", "sharpe", "sortino")  # the dispersion and ratio statistics that read no benchmark
R5 = ("beta", "r2", "alpha", "te", "ir")  # the benchmark-relative statistics with a count threshold

Cell = Tuple[str, Optional[str], FrozenSet[str]]  # (state, reason code, the risk detail names, exactly: Ruling 7.4's names)


def A(*details: str) -> Cell:
    return ("AVAILABLE", None, frozenset(details))


def L(reason: Optional[str], *details: str) -> Cell:
    return ("LIMITED", reason, frozenset(details))


def I(reason: Optional[str], *details: str) -> Cell:  # noqa: E741
    return ("INSUFFICIENT_DATA", reason, frozenset(details))


def row(every: Optional[Cell] = None, d4: Optional[Cell] = None, dd: Optional[Cell] = None, r5: Optional[Cell] = None, act: Optional[Cell] = None, bret: Optional[Cell] = None, **each: Cell) -> Dict[str, Cell]:
    out: Dict[str, Cell] = {}
    if every is not None:
        out.update({k: every for k in SHORT})
    for names, cell in ((D4, d4), (("dd",), dd), (R5, r5), (("active",), act), (("bret",), bret)):
        if cell is not None:
            out.update({k: cell for k in names})
    out.update(each)
    assert set(out) == set(SHORT), sorted(set(SHORT) ^ set(out))
    return out


OBS_BELOW, INSUFF_OBS = "OBSERVATIONS_BELOW_STANDARD", "INSUFFICIENT_OBSERVATIONS"
NO_BENCH, NO_RF = "NO_BENCHMARK_SELECTED", "NO_RISK_FREE_SOURCE"
MB, SC, FX, SD = "MISSING_BENCHMARK", "SOURCE_CONFLICT", "MISSING_FX_HISTORY", "STALE_DATA"
NO_BENCHMARK = I(MB, NO_BENCH)  # a window fact or a relative metric with no benchmark selected: MISSING_BENCHMARK outranks every missing-data code (Ruling 7.3)

TRAILING_12 = {"rule": "TRAILING_MONTHS", "months": 12}
TRAILING_36 = {"rule": "TRAILING_MONTHS", "months": 36}

CONDITIONS = ("INSUFFICIENT_HISTORY", "MISSING_FX", "MISSING_COST_BASIS", "CASH_ONLY", "SINGLE_SECURITY", "MULTI_CURRENCY", "RECENTLY_LISTED", "UNAVAILABLE_BENCHMARK", "NO_RISK_FREE_SOURCE",
              "ZERO_VARIANCE", "CURRENT_MODE", "ACCOUNT_SCOPE", "SNAPSHOT", "ZERO_CAPITAL_PERIOD", "SPLIT_SUPPRESSION")
HG3_CONDITIONS = CONDITIONS[:9]  # PRD 38.4's eight edge cases and "no risk-free source" (the tech plan's plus-row)


@dataclasses.dataclass(frozen=True)
class Scenario:
    key: str
    condition: str
    world: str            # "part1", "part2", "part3" or a constructed world
    portfolio: str        # the fixture portfolio's prefix, e.g. "Q1"
    assertion: str        # the fixture assertion that pins the as-of, the ledger version and the selection version
    request: dict
    cells: Dict[str, Cell]
    frequency: str = "WEEKLY"
    item: int = 0         # which item of the assertion carries the scope (account scope) the call needs
    constructed: bool = False  # not a fixture's own request: a variant of a fixture world (cells are Ruling-derived and no fixture item exists to compare with)
    note: str = ""
    selection_version: Optional[int] = None  # the selection-log version to pin instead of the assertion's own (Q1's log: 1 US TR, 2 cleared, 3 series absent from M, 4 price return, 5 a late-start series)


# Each scenario is a (portfolio, as-of, request) of the Quant's fixtures. The cells are derived from Rulings 7.1 (counts), 7.2 (a window is answered or refused), 7.3 (how the states and the single reason
# combine: the worst state; the reason only from causes at that level; MISSING_BENCHMARK outranks the missing-data codes) and 7.5 (the HG3 rows); the NOTE says which.
SCENARIOS: Tuple[Scenario, ...] = (
    # -- insufficient history (7.5 row 1; 7.1; 7.2) ----------------------------------------------------------------------------------------------------
    Scenario("history/before_inception", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B2", {"rule": "TRAILING_MONTHS", "months": 60}, row(every=I(None, "WINDOW_BEFORE_INCEPTION")), constructed=True,
             note="a trailing request before inception: INSUFFICIENT_DATA, WINDOW_BEFORE_INCEPTION, for every metric (7.2); the benchmark leg is never asked about a window that was refused"),
    # Ruling 7.3 (1.5): a refused window still evaluates the window-independent causes (CP4F-2): no selection (R6-W0), a series not in M, a price-return series, no risk-free source
    Scenario("history/before_inception_no_selection", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B2", {"rule": "TRAILING_MONTHS", "months": 60},
             row(d4=I(None, "WINDOW_BEFORE_INCEPTION"), dd=I(None, "WINDOW_BEFORE_INCEPTION"), r5=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), act=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"),
                 bret=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION")), constructed=True, selection_version=2,
             note="the cleared selection is a window-independent cause: MISSING_BENCHMARK outranks the refusal's missing code, and the window detail stays (the pattern of fixture R6-W0)"),
    Scenario("history/before_inception_series_absent", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B2", {"rule": "TRAILING_MONTHS", "months": 60},
             row(d4=I(None, "WINDOW_BEFORE_INCEPTION"), dd=I(None, "WINDOW_BEFORE_INCEPTION"), r5=I(MB, "BENCHMARK_SERIES_UNAVAILABLE", "WINDOW_BEFORE_INCEPTION"),
                 act=I(MB, "BENCHMARK_SERIES_UNAVAILABLE", "WINDOW_BEFORE_INCEPTION"), bret=I(MB, "BENCHMARK_SERIES_UNAVAILABLE", "WINDOW_BEFORE_INCEPTION")), constructed=True, selection_version=3,
             note="a selected series that M does not hold: the cause that will still refuse the metric once the history has grown is not hidden (CP4F-2, the reviewer's Q1 v3)"),
    Scenario("history/before_inception_price_return", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B2", {"rule": "TRAILING_MONTHS", "months": 60},
             row(d4=I(None, "WINDOW_BEFORE_INCEPTION"), dd=I(None, "WINDOW_BEFORE_INCEPTION"), r5=I(MB, "BENCHMARK_NOT_TOTAL_RETURN", "WINDOW_BEFORE_INCEPTION"),
                 act=I(MB, "BENCHMARK_NOT_TOTAL_RETURN", "WINDOW_BEFORE_INCEPTION"), bret=I(MB, "BENCHMARK_NOT_TOTAL_RETURN", "WINDOW_BEFORE_INCEPTION")), constructed=True, selection_version=4,
             note="a price-return series (Ruling 5.4), the reviewer's Q1 v4"),
    Scenario("history/below_n1", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B1", {"rule": "CUSTOM", "base": "2025-11-14"},
             row(d4=I(None, INSUFF_OBS), r5=I(None, INSUFF_OBS), dd=A(), act=A(), bret=A()), constructed=True,
             note="7 weekly observations < N1 = 51: the nine statistics INSUFFICIENT_DATA with no reason, the three window facts AVAILABLE (7.5 row 1)"),
    Scenario("history/limited_n1_to_n3", "INSUFFICIENT_HISTORY", "part2", "Q1", "Q1-B1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), r5=L(None, OBS_BELOW), dd=A(), act=A(), bret=A()), note="52 observations: N1 <= n < N3: LIMITED with the value, no reason (7.1)"),
    # -- missing FX (7.5 row 2; 7.3; market-data 5.2) ----------------------------------------------------------------------------------------------------
    Scenario("fx/portfolio_five_missed", "MISSING_FX", "part1", "P7", "P7-F1", TRAILING_12,
             row(d4=I(FX, OBS_BELOW, "PERIOD_INSUFFICIENT", "STALE_PERIODS"), dd=I(FX, "PERIOD_INSUFFICIENT", "STALE_PERIODS"),
                 r5=I(MB, NO_BENCH, OBS_BELOW, "PERIOD_INSUFFICIENT", "STALE_PERIODS"), act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="a flow-day valuation missed for >= 5 fixings: that period INSUFFICIENT_DATA + MISSING_FX_HISTORY and every metric over the window; with no benchmark selected MISSING_BENCHMARK outranks (7.3)"),
    Scenario("fx/portfolio_two_to_four_missed", "MISSING_FX", "part1", "P7", "P7-F2", {"rule": "MAX_AVAILABLE"},
             row(d4=I(None, INSUFF_OBS, "STALE_PERIODS"), dd=L(SD, "STALE_PERIODS"), r5=I(MB, INSUFF_OBS, NO_BENCH, "STALE_PERIODS"), act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="2-4 missed: LIMITED + STALE_DATA with the stale period count; the count (28 < N1) is what makes the statistics INSUFFICIENT, so they have NO reason (7.3 item 3)"),
    Scenario("fx/benchmark_translation_two_missed", "MISSING_FX", "part3", "R3", "R3-X1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=L(SD, OBS_BELOW), act=A(), bret=A()),
             note="the benchmark's translation 2 fixings stale at one interior grid date: LIMITED + STALE_DATA (both causes at LIMITED: the code); the window facts read g_0 and g_n only (6.9 (1.1))"),
    Scenario("fx/proxy_dividend_conversion_stale", "MISSING_FX", "part3", "R5", "R5-E9", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=L(SD, OBS_BELOW), act=L(SD), bret=L(SD)),
             note="Ruling 5.5 (1.8): a USD ETF declaring in CNY; the dividend of 2025-03-14 is converted at the fixing of 03-12 (2 missed): LIMITED + STALE_DATA for every ratio spanning it, with no risk detail; the statistics "
                  "that read the periods and the window facts from 2025-01-08 both span it"),
    Scenario("fx/proxy_dividend_no_fixing", "MISSING_FX", "part3_div5", "R5", "R5-E9", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(FX, OBS_BELOW), act=I(FX), bret=I(FX)), constructed=True,
             note="the same ETF with the CNY fixings of 2025-02-25 to 03-03 missing: five missed at the ex-date 03-03, so no rate is used, the dividend is not applied and every ratio spanning it is INSUFFICIENT_DATA + "
                  "MISSING_FX_HISTORY (Ruling 5.5 (1.8) item 4)"),
    Scenario("fx/benchmark_translation_five_missed", "MISSING_FX", "part3_fx5", "R3", "R3-X1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(FX, OBS_BELOW), act=A(), bret=A()), constructed=True,
             note="R3 with 5 consecutive CNY fixings missing: the translation is INSUFFICIENT_DATA + MISSING_FX_HISTORY (5.3: the worse of level and translation; market-data 5.2 thresholds)"),
    # -- missing cost basis (7.5 row 3): no effect ------------------------------------------------------------------------------------------------------
    Scenario("basis/in_kind_no_benchmark", "MISSING_COST_BASIS", "part1", "P6", "P6-B1", TRAILING_36,
             row(d4=A(), dd=A(), r5=NO_BENCHMARK, act=NO_BENCHMARK, bret=NO_BENCHMARK), note="no risk statistic reads cost basis: nothing changes, and MISSING_COST_BASIS never appears"),
    Scenario("basis/in_kind_with_benchmark", "MISSING_COST_BASIS", "part2", "Q2", "Q2-T1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), beta=L(None, OBS_BELOW), r2=L(None, OBS_BELOW), alpha=L(None, OBS_BELOW), te=L(None, OBS_BELOW), ir=I(None, OBS_BELOW, "ZERO_TRACKING_ERROR"),
                 act=A(), bret=A()), note="a holding received in kind with no basis, against an index translated from HKD"),
    # -- cash-only (7.5 row 4) ------------------------------------------------------------------------------------------------------------------------
    Scenario("cash/no_benchmark", "CASH_ONLY", "part1", "P4", "P4-C1", TRAILING_36,
             row(vol=A(), ds=A(), dd=A(), sharpe=I(None, "ZERO_VOLATILITY"), sortino=I(None, "ZERO_VOLATILITY"), r5=NO_BENCHMARK, act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="cash in R with no interest: volatility 0 and drawdown 0 AVAILABLE, downside deviation positive, Sharpe and Sortino ZERO_VOLATILITY"),
    Scenario("cash/against_benchmark", "CASH_ONLY", "part2", "Q4", "Q4-C1", TRAILING_12,
             row(vol=L(None, OBS_BELOW), ds=L(None, OBS_BELOW), dd=A(), sharpe=I(None, OBS_BELOW, "ZERO_VOLATILITY"), sortino=I(None, OBS_BELOW, "ZERO_VOLATILITY"), beta=L(None, OBS_BELOW),
                 r2=I(None, OBS_BELOW, "ZERO_PORTFOLIO_VARIANCE"), alpha=L(None, OBS_BELOW), te=L(None, OBS_BELOW), ir=L(None, OBS_BELOW), act=A(), bret=A()),
             note="part 2 cash-only: beta 0, R-squared ZERO_PORTFOLIO_VARIANCE, TE the benchmark's volatility"),
    # -- single security (7.5 row 5) --------------------------------------------------------------------------------------------------------------------
    Scenario("single/three_years_with_benchmark", "SINGLE_SECURITY", "part2", "Q1", "Q1-B2", TRAILING_36, row(every=A()), note="one listing, 156 weekly observations >= N3: every metric AVAILABLE"),
    Scenario("single/three_years_no_benchmark", "SINGLE_SECURITY", "part1", "P3", "P3-A1", TRAILING_36, row(d4=A(), dd=A(), r5=NO_BENCHMARK, act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="the same without a selection: the five independent metrics AVAILABLE and the seven benchmark-dependent ones MISSING_BENCHMARK"),
    # -- multi-currency (7.5 row 6) -------------------------------------------------------------------------------------------------------------------
    Scenario("multicurrency/listing_and_foreign_cash", "MULTI_CURRENCY", "part2", "Q6", "Q6-S1", TRAILING_12, row(d4=L(None, OBS_BELOW), r5=L(None, OBS_BELOW), dd=A(), act=A(), bret=A()),
             note="a US listing plus HKD cash against the US index: the return is the return in R, translated at each grid date's fixing"),
    Scenario("multicurrency/hk_listing_against_translated_index", "MULTI_CURRENCY", "part2", "Q2", "Q2-T1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), beta=L(None, OBS_BELOW), r2=L(None, OBS_BELOW), alpha=L(None, OBS_BELOW), te=L(None, OBS_BELOW), ir=I(None, OBS_BELOW, "ZERO_TRACKING_ERROR"), act=A(), bret=A()),
             note="an HKD listing in a USD portfolio against an HKD index translated at the same fixing"),
    Scenario("multicurrency/foreign_cash_no_benchmark", "MULTI_CURRENCY", "part1", "P5", "P5-M1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(MB, NO_BENCH, OBS_BELOW), act=NO_BENCHMARK, bret=NO_BENCHMARK), note="HKD cash only: the return is the FX return"),
    # -- recently listed (7.5 row 7) ----------------------------------------------------------------------------------------------------------------------
    Scenario("listed/whole_portfolio_trailing", "RECENTLY_LISTED", "part1", "P8", "P8-L1", TRAILING_12,
             row(d4=I(None, "WINDOW_BEFORE_INCEPTION"), dd=I(None, "WINDOW_BEFORE_INCEPTION"), r5=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), act=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"),
                 bret=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION")), note="the whole portfolio is a security listed 12 weeks ago: short history, as row 1; the portfolio's own refusal stays listed"),
    Scenario("listed/whole_portfolio_max_available", "RECENTLY_LISTED", "part1", "P8", "P8-L2", {"rule": "MAX_AVAILABLE"},
             row(d4=I(None, INSUFF_OBS), dd=A(), r5=I(MB, INSUFF_OBS, NO_BENCH), act=NO_BENCHMARK, bret=NO_BENCHMARK), note="MAX_AVAILABLE: 12 observations < N1; drawdown a window fact"),
    Scenario("listed/inside_established_portfolio", "RECENTLY_LISTED", "part1", "P11", "P11-R1", TRAILING_36, row(d4=A(), dd=A(), r5=NO_BENCHMARK, act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="a recently listed holding inside an established portfolio: no effect, and no price before purchase is needed"),
    # -- unavailable benchmark (7.5 row 8): all the forms --------------------------------------------------------------------------------------------------
    Scenario("benchmark/none_selected", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-U2", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(MB, NO_BENCH, OBS_BELOW), act=NO_BENCHMARK, bret=NO_BENCHMARK), note="a cleared selection: no benchmark is substituted"),
    Scenario("benchmark/series_unavailable", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-U3", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(MB, "BENCHMARK_SERIES_UNAVAILABLE", OBS_BELOW), act=I(MB, "BENCHMARK_SERIES_UNAVAILABLE"), bret=I(MB, "BENCHMARK_SERIES_UNAVAILABLE")),
             note="a selected benchmark with no series in M"),
    Scenario("benchmark/price_return_only", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-U4", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(MB, "BENCHMARK_NOT_TOTAL_RETURN", OBS_BELOW), act=I(MB, "BENCHMARK_NOT_TOTAL_RETURN"), bret=I(MB, "BENCHMARK_NOT_TOTAL_RETURN")),
             note="a PRICE_RETURN series (Ruling 5.4)"),
    Scenario("benchmark/not_covering_window", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-U5", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(MB, "BENCHMARK_NOT_COVERING_WINDOW", OBS_BELOW), act=I(MB, "BENCHMARK_NOT_COVERING_WINDOW"), bret=I(MB, "BENCHMARK_NOT_COVERING_WINDOW")),
             note="a series that begins inside the window"),
    Scenario("benchmark/stale_two_missed", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-B3", {"rule": "CUSTOM", "base": "2026-01-02"},
             row(d4=I(None, INSUFF_OBS), dd=A(), r5=I(None, "BENCHMARK_STALE", INSUFF_OBS), act=L(SD, "BENCHMARK_STALE"), bret=L(SD, "BENCHMARK_STALE")),
             note="a benchmark 2 sessions stale at g_n: LIMITED + STALE_DATA for the window facts; the count (2 < N1) alone sets the statistics' state, so they have no reason (7.3)"),
    Scenario("benchmark/stale_five_missed", "UNAVAILABLE_BENCHMARK", "part2", "Q1", "Q1-B5", {"rule": "CUSTOM", "base": "2026-01-30"},
             row(d4=I(None, INSUFF_OBS), dd=A(), r5=I(SD, "BENCHMARK_STALE", INSUFF_OBS), act=I(SD, "BENCHMARK_STALE"), bret=I(SD, "BENCHMARK_STALE")), note="5 or more missed: INSUFFICIENT_DATA + STALE_DATA"),
    Scenario("benchmark/two_sources_disagree_interior", "UNAVAILABLE_BENCHMARK", "part3", "R4", "R4-S1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(SC, "BENCHMARK_SOURCE_CONFLICT", OBS_BELOW), act=A(), bret=A()),
             note="the day withheld is interior: the statistics read it, the window facts (g_0 and g_n) do not"),
    Scenario("benchmark/etf_proxy_conflict_at_endpoint", "UNAVAILABLE_BENCHMARK", "part3", "R5", "R5-E2", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), r5=I(SC, "BENCHMARK_SOURCE_CONFLICT", OBS_BELOW), act=I(SC, "BENCHMARK_SOURCE_CONFLICT"), bret=I(SC, "BENCHMARK_SOURCE_CONFLICT")),
             note="an ETF proxy's disagreeing dividend withholds the level at g_n: every benchmark-dependent metric"),
    # -- no risk-free source (the tech plan's plus-row; 7.6) -------------------------------------------------------------------------------------------------
    Scenario("riskfree/no_source_window_refused", "NO_RISK_FREE_SOURCE", "part1", "P10", "P10-H1", {"rule": "TRAILING_MONTHS", "months": 60},
             row(vol=I(None, "WINDOW_BEFORE_INCEPTION"), ds=I(None, "WINDOW_BEFORE_INCEPTION", NO_RF), sharpe=I(None, "WINDOW_BEFORE_INCEPTION", NO_RF), sortino=I(None, "WINDOW_BEFORE_INCEPTION", NO_RF),
                 dd=I(None, "WINDOW_BEFORE_INCEPTION"), beta=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), r2=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), alpha=I(MB, NO_BENCH, NO_RF, "WINDOW_BEFORE_INCEPTION"),
                 te=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), ir=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), act=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION"), bret=I(MB, NO_BENCH, "WINDOW_BEFORE_INCEPTION")),
             constructed=True, note="Ruling 7.3 (1.5): a refused window still names NO_RISK_FREE_SOURCE on the rate-dependent metrics (CP4F-2, the reviewer's P10)"),
    Scenario("riskfree/no_source", "NO_RISK_FREE_SOURCE", "part1", "P10", "P10-H1", {"rule": "CUSTOM", "base": "2025-09-19"},
             row(vol=I(None, INSUFF_OBS), ds=I(None, INSUFF_OBS, NO_RF), sharpe=I(None, INSUFF_OBS, NO_RF), sortino=I(None, INSUFF_OBS, NO_RF), dd=A(), beta=I(MB, INSUFF_OBS, NO_BENCH),
                 r2=I(MB, INSUFF_OBS, NO_BENCH), alpha=I(MB, INSUFF_OBS, NO_BENCH, NO_RF), te=I(MB, INSUFF_OBS, NO_BENCH), ir=I(MB, INSUFF_OBS, NO_BENCH), act=NO_BENCHMARK, bret=NO_BENCHMARK),
             note="a CNY portfolio with no CNY risk-free source: the four rf-dependent metrics name NO_RISK_FREE_SOURCE and no other metric does (the registry says which are rf-dependent)"),
    # -- the engineer-added plus rows -------------------------------------------------------------------------------------------------------------------
    Scenario("variance/flat_benchmark", "ZERO_VARIANCE", "part3", "R1", "R1-F1", TRAILING_12,
             row(d4=L(None, OBS_BELOW), dd=A(), beta=I(None, OBS_BELOW, "ZERO_BENCHMARK_VARIANCE"), r2=I(None, OBS_BELOW, "ZERO_BENCHMARK_VARIANCE"), alpha=I(None, OBS_BELOW, "ZERO_BENCHMARK_VARIANCE"),
                 te=L(None, OBS_BELOW), ir=L(None, OBS_BELOW), act=A(), bret=A()), note="a flat benchmark: no slope to estimate (6.12); the tracking error is the portfolio's own volatility"),
    Scenario("current/instant", "CURRENT_MODE", "part3", "R7", "R7-C1", TRAILING_12, row(d4=L(None, OBS_BELOW), r5=L(None, OBS_BELOW), dd=A(), act=A(), bret=A()),
             note="Current mode at an instant at which Friday's US close is not yet due: not a lag, not stale (5.8)"),
    Scenario("scope/one_account", "ACCOUNT_SCOPE", "part3", "R8", "R8-K1", TRAILING_12, row(d4=L(None, OBS_BELOW), r5=L(None, OBS_BELOW), dd=A(), act=A(), bret=A()),
             note="one account's series (a transfer in from the other account is an external flow of this scope)"),
    Scenario("snapshot/window_before_snapshot", "SNAPSHOT", "part3", "R10", "R10-S1", TRAILING_36, row(every=I("NOT_RECONSTRUCTABLE", "WINDOW_BEFORE_SNAPSHOT")),
             note="a snapshot portfolio asked for a window before the snapshot (7.2): the history before it is not reconstructable, for every metric"),
    Scenario("zero_capital/interior_period", "ZERO_CAPITAL_PERIOD", "part3", "R9", "R9-Z1", TRAILING_12,
             row(d4=I(None, OBS_BELOW, "PERIOD_INSUFFICIENT", "ZERO_CAPITAL_PERIOD"), dd=I(None, "PERIOD_INSUFFICIENT", "ZERO_CAPITAL_PERIOD"), r5=I(None, OBS_BELOW, "PERIOD_INSUFFICIENT", "ZERO_CAPITAL_PERIOD"),
                 act=I(None, "ZERO_CAPITAL_PERIOD"), bret=A()),
             note="a period with no capital throughout is not an observation (2.4): every statistic over a window containing it is INSUFFICIENT_DATA (2.5), and (Ruling 6.9 (1.5), fixture R9-Z3, mutation M-C30) so is the "
                  "ACTIVE RETURN, with no reason and the one detail; the benchmark return has no portfolio leg and stands"),
    Scenario("valuation/interior_insufficient_active_return_stands", "MISSING_FX", "part2_hkd_gap", "Q6", "Q6-S1", TRAILING_12,
             row(d4=I(FX, OBS_BELOW, "PERIOD_INSUFFICIENT"), dd=I(FX, "PERIOD_INSUFFICIENT"), r5=I(FX, OBS_BELOW, "PERIOD_INSUFFICIENT"), act=A(), bret=A()), constructed=True,
             note="CP4F-1's other half: five consecutive HKD fixings missing at ONE interior grid date make that period INSUFFICIENT_DATA, so there is no period chain, but the interior valuation is not an input of "
                  "TWR(g_0, g_n]: the active return stays AVAILABLE (Ruling 6.9 (1.1)), with RS-1 recorded NOT_COMPUTABLE. Only a ZERO_CAPITAL_PERIOD refuses it (6.9 (1.5))"),
    Scenario("split/uncovered_split_trailing", "SPLIT_SUPPRESSION", "part3", "R11", "R11-X1", TRAILING_12,
             row(d4=I(SC, OBS_BELOW, "PERIOD_INSUFFICIENT"), dd=I(SC, "PERIOD_INSUFFICIENT"), r5=I(SC, OBS_BELOW, "PERIOD_INSUFFICIENT"), act=I(SC), bret=A()),
             note="a corroborated split not in the ledger suppresses the period (F8); the benchmark is not what failed, so benchmark_return stands"),
)

#: What is reported to the Quant and not decided here (key: (scenario key, metric id)).
OPEN_FINDINGS: Dict[Tuple[str, str], str] = {}  # empty: the CP4e finding was ruled (risk/1.5 Ruling 6.9 (1.5))


def matrix() -> Dict[str, Dict[str, FrozenSet[Cell]]]:
    """metric id -> condition -> the set of cells its scenarios give. Built from the data above, never from a run."""
    out: Dict[str, Dict[str, set]] = {mid: {c: set() for c in CONDITIONS} for mid in SHORT.values()}
    for sc in SCENARIOS:
        for short, cell in sc.cells.items():
            out[SHORT[short]][sc.condition].add(cell)
    return {mid: {c: frozenset(v) for c, v in by.items()} for mid, by in out.items()}


# --- the worlds -------------------------------------------------------------------------------------------------------------------------------

_WORLDS: Dict[str, g.Runner] = {}
_OWNED: List[g.Market] = []


def runner_of(world: str) -> g.Runner:
    if world not in _WORLDS:
        if world in ("part1", "part2", "part3", "part4"):
            _WORLDS[world] = g.shared_runner(int(world[-1]))
        elif world == "part2_hkd_gap":
            data = copy.deepcopy(g.load_part(2))  # Q6 holds HKD cash: five consecutive missing HKD fixings put the interior grid date 2025-06-13 five fixings stale (a period INSUFFICIENT_DATA, MISSING_FX_HISTORY)
            data["market_data"]["fx"].setdefault("gaps_by_currency", {})["HKD"] = ["2025-06-09", "2025-06-10", "2025-06-11", "2025-06-12", "2025-06-13"]
            ids = cp1.Ids(randomize=False)
            market = g.Market(data, ids)
            _OWNED.append(market)
            _WORLDS[world] = g.Runner(data, market, ids)
        elif world == "part3_div5":
            data = copy.deepcopy(g.load_part(3))  # SYN35 declares CNY dividends: with the CNY fixings of 02-25..02-28 and the ex-date 03-03 missing, 5 fixings are missed at the ex-date
            data["market_data"]["fx"]["gaps_by_currency"]["CNY"] = ["2025-02-25", "2025-02-26", "2025-02-27", "2025-02-28", "2025-03-03", "2025-03-13", "2025-03-14"]
            ids = cp1.Ids(randomize=False)
            market = g.Market(data, ids)
            _OWNED.append(market)
            _WORLDS[world] = g.Runner(data, market, ids)
        elif world == "part3_fx5":
            data = copy.deepcopy(g.load_part(3))  # R3's benchmark is in CNY: five consecutive missing CNY fixings put the translation 5 fixings stale at 2025-03-14
            data["market_data"]["fx"]["gaps_by_currency"]["CNY"] = ["2025-03-10", "2025-03-11", "2025-03-12", "2025-03-13", "2025-03-14"]
            ids = cp1.Ids(randomize=False)
            market = g.Market(data, ids)
            _OWNED.append(market)
            _WORLDS[world] = g.Runner(data, market, ids)
        else:
            raise KeyError(world)
    return _WORLDS[world]


def portfolio_of(runner: g.Runner, prefix: str) -> dict:
    return next(p for p in runner.data["portfolios"] if p["name"].startswith(prefix + " "))


def case_of(sc: Scenario):
    runner = runner_of(sc.world)
    p = portfolio_of(runner, sc.portfolio)
    a = next(a for a in p["assertions"] if a["id"] == sc.assertion)
    if sc.selection_version is not None:  # the runner caches by assertion id: another selection version is another question
        a = dict(a, id=f"{a['id']}-sel{sc.selection_version}", selection_log_version=sc.selection_version)
    it = dict(a["expect"][sc.item], request=sc.request, frequency=sc.frequency)
    return runner, p, a, it


def run_scenario(sc: Scenario):
    runner, p, a, it = case_of(sc)
    return runner.risk(p, a, it, ALL)


def actual_cell(m) -> Cell:
    return (m.state.value, None if m.result.reason_code is None else m.result.reason_code.value, frozenset(g._risk_names(m.details)))


def digest_of_all() -> str:
    parts = sorted(f"{sc.key}:{run_scenario(sc).canonical_json()}" for sc in SCENARIOS)
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


_RESULTS: Dict[str, object] = {}


def setUpModule():
    for sc in SCENARIOS:
        _RESULTS[sc.key] = run_scenario(sc)  # ONE run of every scenario for the whole module (building the three worlds is the cost, paid once)


def tearDownModule():
    for market in _OWNED:
        market.close()
    _OWNED.clear()
    _WORLDS.pop("part3_fx5", None)
    _WORLDS.pop("part2_hkd_gap", None)
    _WORLDS.pop("part3_div5", None)
    _RESULTS.clear()


def run_case(case, names):
    suite = unittest.TestSuite([case(n) for n in names])
    return unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)


# --- (a) the registry is complete -------------------------------------------------------------------------------------------------------------

#: PRD 16.3's ten requirements -> the registry fields (the fifteen PRD 33 fields) that carry them
PRD_16_3 = {"exact definition/formula": ("human_definition", "formula"), "data requirements": ("data_inputs",), "minimum sample requirement": ("minimum_observations",),
            "window/frequency": ("frequency", "lookback"), "annualization convention": ("annualization_convention",), "benchmark requirement": ("benchmark_dependency",),
            "risk-free-rate requirement": ("risk_free_rate_dependency",), "FX treatment": ("fx_treatment",), "missing-data policy": ("missing_data_handling",), "known limitations": ("known_limitations",)}


def nonempty(value) -> bool:
    if value is None:
        return False
    if isinstance(value, (str, list, tuple, dict)):
        return len(value) > 0
    return True


class RegistryIsCompleteTests(unittest.TestCase):
    def test_the_engine_computes_exactly_the_registered_metrics(self):
        self.assertEqual(set(COMPUTABLE), set(REGISTRY.metric_ids))
        self.assertEqual(set(ALL), set(REGISTRY.metric_ids))
        self.assertEqual(len(ALL), 12)

    def test_every_entry_carries_every_requirement_of_prd_16_3(self):
        for mid in ALL:
            entry = REGISTRY.resolved(mid)
            for requirement, fields in PRD_16_3.items():
                for field in fields:
                    self.assertTrue(nonempty(entry.get(field)), (mid, requirement, field))
            self.assertTrue(nonempty(entry.get("implementation_version")), mid)  # the version the metric was computed under
            self.assertEqual(entry["implementation_version"][0], REGISTRY.registry_id, mid)
            self.assertTrue(nonempty(entry.get("defined_in")), mid)  # every entry cites the rulings that define it (audit)

    def test_the_minimum_sample_is_a_number_at_every_frequency_and_the_ui_reads_it_from_here(self):
        for mid in ALL:
            for frequency in ("DAILY", "WEEKLY", "MONTHLY"):
                m = REGISTRY.minimum_observations(mid, frequency)
                self.assertIsInstance(m.insufficient_below, int)
                self.assertIsInstance(m.available_from, int)
                self.assertTrue(1 <= m.insufficient_below <= m.available_from, (mid, frequency, m))

    def test_the_registry_says_which_metrics_need_a_benchmark_and_which_need_a_risk_free_rate(self):
        needs_benchmark = {mid for mid in ALL if str(REGISTRY.resolved(mid)["benchmark_dependency"]).lower() != "none"}
        needs_rate = {mid for mid in ALL if not str(REGISTRY.resolved(mid)["risk_free_rate_dependency"]).lower().startswith("none")}
        self.assertEqual(needs_benchmark, set(grp.BENCHMARK_GROUP))  # the engine's partition is the registry's
        self.assertEqual(needs_rate, {"risk_downside_deviation", "risk_sharpe", "risk_sortino", "risk_alpha_jensen"})

    def test_every_result_of_every_scenario_names_its_entry_and_its_registry_by_id_and_digest(self):
        seen = 0
        for sc in SCENARIOS:
            res = _RESULTS[sc.key]
            self.assertEqual((res.manifest.registry_id, res.manifest.registry_digest), (REGISTRY.registry_id, REGISTRY.digest), sc.key)
            self.assertEqual(res.manifest.risk_engine_id, RISK_ENGINE_ID)
            self.assertEqual(res.manifest.metrics, tuple(sorted(ALL)))
            for mid in ALL:
                m = res.metric(mid)
                self.assertEqual(m.method_key, REGISTRY.entry_key(mid), (sc.key, mid))  # `risk/1.4#<metric>`: the definition, version and data requirements are that entry
                self.assertEqual(m.method_key.split("#")[0], res.manifest.registry_id)
                self.assertIs(REGISTRY.entry(mid)["metric_id"] == mid, True)
                seen += 1
        self.assertEqual(seen, len(SCENARIOS) * 12)


# --- (b) fails safely --------------------------------------------------------------------------------------------------------------------------

class EveryMetricFailsSafelyTests(unittest.TestCase):
    def test_every_scenario_gives_the_state_reason_and_details_of_its_cells_for_every_metric(self):
        wrong = []
        for sc in SCENARIOS:
            res = _RESULTS[sc.key]
            self.assertEqual({m.metric_id for m in res.metrics}, set(ALL), sc.key)
            for short, mid in SHORT.items():
                got, want = actual_cell(res.metric(mid)), sc.cells[short]
                if got != want and (sc.key, mid) not in OPEN_FINDINGS:
                    wrong.append((sc.key, mid, "expected", (want[0], want[1], sorted(want[2])), "got", (got[0], got[1], sorted(got[2]))))
        self.assertEqual(wrong, [], "\n" + "\n".join(map(str, wrong)))

    def test_a_refused_metric_presents_no_number_anywhere(self):
        refused = 0
        for sc in SCENARIOS:
            for m in _RESULTS[sc.key].metrics:
                obj = m.to_canonical_dict()
                if m.state is SS.INSUFFICIENT_DATA:
                    refused += 1
                    self.assertIsNone(m.value, (sc.key, m.metric_id))
                    for field in ("value", "exact", "exact_square", "sign", "comparability", "decomposition", "drawdown"):
                        self.assertIsNone(obj[field], (sc.key, m.metric_id, field))
                    self.assertEqual(obj["intermediates"], [], (sc.key, m.metric_id))  # no exact sum or mean from which a number could be rebuilt
                    self.assertTrue(m.causes, (sc.key, m.metric_id))  # and it names why
                else:
                    self.assertIsNotNone(m.value, (sc.key, m.metric_id))
                    self.assertIsNotNone(obj["exact"] if obj["exact_square"] is None else obj["exact_square"], (sc.key, m.metric_id))
        self.assertGreater(refused, 150)  # the matrix really exercises refusals

    def test_available_and_limited_results_carry_their_count_and_the_threshold_of_the_registry(self):
        for sc in SCENARIOS:
            freq = sc.frequency
            for m in _RESULTS[sc.key].metrics:
                if m.state is SS.INSUFFICIENT_DATA:
                    continue
                self.assertIsNotNone(m.observation_count, (sc.key, m.metric_id))
                self.assertIsNotNone(m.window, (sc.key, m.metric_id))  # the window is declared: nothing is silently shortened (7.2)
                t = REGISTRY.minimum_observations(m.metric_id, freq)
                if m.metric_id in ("risk_max_drawdown", "risk_active_return", "benchmark_return"):
                    self.assertIsNone(m.thresholds, (sc.key, m.metric_id))
                else:
                    self.assertEqual(m.thresholds, (t.insufficient_below, t.available_from), (sc.key, m.metric_id))
                    self.assertGreaterEqual(m.observation_count, t.insufficient_below, (sc.key, m.metric_id))  # a number below N1 is never shown
                    if m.state is SS.AVAILABLE:
                        self.assertGreaterEqual(m.observation_count, t.available_from, (sc.key, m.metric_id))

    def test_a_reason_is_coupled_to_its_state_and_cost_basis_never_appears_on_a_risk_metric(self):
        allowed_insufficient = {None, MB, FX, SC, SD, "NOT_RECONSTRUCTABLE"}
        for sc in SCENARIOS:
            for m in _RESULTS[sc.key].metrics:
                reason = None if m.result.reason_code is None else m.result.reason_code.value
                if m.state is SS.INSUFFICIENT_DATA:
                    self.assertIn(reason, allowed_insufficient, (sc.key, m.metric_id))
                else:
                    self.assertIn(reason, {None, SD}, (sc.key, m.metric_id))  # AVAILABLE and LIMITED can carry STALE_DATA only
                self.assertNotIn("MISSING_COST_BASIS", json.dumps(m.to_canonical_dict(), default=str), (sc.key, m.metric_id))

    def test_the_benchmark_group_alone_is_refused_when_only_the_benchmark_is_missing(self):
        """HG3 'unavailable benchmark': the independent metrics are unaffected (identical to the same request under a working benchmark), the seven benchmark-dependent ones are refused."""
        baseline = _RESULTS["history/limited_n1_to_n3"]  # Q1, 12 months, benchmark selected
        for key in ("benchmark/none_selected", "benchmark/series_unavailable", "benchmark/price_return_only", "benchmark/not_covering_window"):
            res = _RESULTS[key]
            for mid in grp.INDEPENDENT_GROUP:
                a, b = res.metric(mid), baseline.metric(mid)
                self.assertEqual((a.state, a.result.reason_code, a.value, a.exact, a.exact_square, a.details, a.observation_count), (b.state, b.result.reason_code, b.value, b.exact, b.exact_square, b.details,
                                                                                                                                 b.observation_count), (key, mid))
            for mid in grp.BENCHMARK_GROUP:
                m = res.metric(mid)
                self.assertEqual((m.state, m.result.reason_code.value, m.value), (SS.INSUFFICIENT_DATA, MB, None), (key, mid))

    def test_missing_cost_basis_is_independent_the_same_portfolio_with_a_basis_gives_the_same_risk_numbers(self):
        """The metamorphic form of 7.5 row 3: give P6's in-kind holding a cost basis. Every state, reason, detail, value and exact value of every metric is unchanged."""
        runner = runner_of("part1")
        data = copy.deepcopy(runner.data)
        p6 = next(p for p in data["portfolios"] if p["name"].startswith("P6 "))
        for entry in p6["events"]:
            if entry["event"]["event_type"] == "TRANSFER_IN":
                entry["event"]["cost_basis"] = {"amount": "12345.67", "currency": "USD"}
        with_basis = g.Runner(data, runner.market, runner.ids)
        base_p = portfolio_of(runner, "P6")
        a = next(x for x in base_p["assertions"] if x["id"] == "P6-B1")
        it = dict(a["expect"][0], request=TRAILING_36)
        without = runner.risk(base_p, a, it, ALL)
        with_ = with_basis.risk(p6, a, it, ALL)
        self.assertNotEqual(without.manifest.series.ledger_digest, with_.manifest.series.ledger_digest)  # it really is another ledger
        for mid in ALL:
            x, y = without.metric(mid), with_.metric(mid)
            self.assertEqual((x.state, x.result.reason_code, x.value, x.exact, x.exact_square, x.sign, x.details, x.observation_count),
                             (y.state, y.result.reason_code, y.value, y.exact, y.exact_square, y.sign, y.details, y.observation_count), mid)

    def test_the_cash_only_facts_of_ruling_7_5(self):
        res = _RESULTS["cash/no_benchmark"]
        self.assertEqual((res.metric("risk_volatility").value, res.metric("risk_max_drawdown").value), (Decimal(0), Decimal(0)))  # volatility 0 and drawdown 0 (AVAILABLE)
        self.assertGreater(res.metric("risk_downside_deviation").value, 0)  # the shortfall below the risk-free rate


class CellsAgreeWithTheFixtureTests(unittest.TestCase):
    def test_wherever_a_fixture_asserts_a_metric_on_the_same_request_the_cell_is_the_fixtures(self):
        compared = 0
        per_scenario = {}
        for sc in SCENARIOS:
            if sc.constructed:  # a variant of a fixture world: the fixture's items are about the unchanged world
                continue
            runner, p, a, it = case_of(sc)
            for item in a["expect"]:
                if item["kind"] not in g.KIND_METRIC or item["request"] != sc.request or item["frequency"] != sc.frequency or item.get("scope") != it.get("scope"):
                    continue
                short = next(k for k, v in SHORT.items() if v == g.KIND_METRIC[item["kind"]])
                fixture_cell = (item["state"], item["reason"], frozenset(item["details_include"]))
                self.assertEqual(sc.cells[short], fixture_cell, (sc.key, item["kind"], "the cell must be the Quant's item"))
                compared += 1
                per_scenario[sc.key] = per_scenario.get(sc.key, 0) + 1
        for sc in SCENARIOS:
            if not sc.constructed:
                self.assertGreater(per_scenario.get(sc.key, 0), 0, f"{sc.key}: a fixture-backed scenario has at least one item of the Quant's to be compared with")
        self.assertGreater(compared, 60)


# --- (c) the availability matrix --------------------------------------------------------------------------------------------------------------

class RiskAvailabilityMatrixTests(unittest.TestCase):
    def test_the_matrix_has_a_row_for_every_registered_metric_and_a_cell_for_every_condition(self):
        m = matrix()
        self.assertEqual(set(m), set(REGISTRY.metric_ids))
        for mid, by in m.items():
            self.assertEqual(set(by), set(CONDITIONS), mid)
            for condition, cells in by.items():
                self.assertTrue(cells, (mid, condition, "an empty cell: the condition has no scenario that gives this metric a state"))
        self.assertEqual({sc.condition for sc in SCENARIOS}, set(CONDITIONS))  # a scenario of an unlisted condition, or a condition with none, fails
        for sc in SCENARIOS:
            self.assertEqual(set(sc.cells), set(SHORT), sc.key)
            self.assertEqual(sc.frequency in ("DAILY", "WEEKLY", "MONTHLY"), True)

    def test_the_eight_hg3_edge_cases_and_the_no_risk_free_row_are_all_present(self):
        self.assertEqual(HG3_CONDITIONS, ("INSUFFICIENT_HISTORY", "MISSING_FX", "MISSING_COST_BASIS", "CASH_ONLY", "SINGLE_SECURITY", "MULTI_CURRENCY", "RECENTLY_LISTED", "UNAVAILABLE_BENCHMARK",
                                          "NO_RISK_FREE_SOURCE"))

    def test_every_cell_of_the_matrix_holds_in_the_run(self):
        m = matrix()
        for sc in SCENARIOS:
            res = _RESULTS[sc.key]
            for short, mid in SHORT.items():
                if (sc.key, mid) in OPEN_FINDINGS:
                    continue
                self.assertIn(actual_cell(res.metric(mid)), m[mid][sc.condition], (sc.key, mid))

    def test_every_state_of_the_vocabulary_is_exercised_and_every_reason_the_rulings_allow_appears(self):
        states = {actual_cell(r.metric(mid))[0] for r in _RESULTS.values() for mid in ALL}
        reasons = {actual_cell(r.metric(mid))[1] for r in _RESULTS.values() for mid in ALL}
        self.assertEqual(states, {"AVAILABLE", "LIMITED", "INSUFFICIENT_DATA"})
        self.assertEqual(reasons, {None, MB, FX, SC, SD, "NOT_RECONSTRUCTABLE"})

    def test_the_no_risk_free_row_names_the_source_on_exactly_the_registrys_rate_dependent_metrics(self):
        res = _RESULTS["riskfree/no_source"]
        dependent = {mid for mid in ALL if not str(REGISTRY.resolved(mid)["risk_free_rate_dependency"]).lower().startswith("none")}
        for mid in ALL:
            self.assertEqual(NO_RF in res.metric(mid).details, mid in dependent, mid)


# --- (d) determinism --------------------------------------------------------------------------------------------------------------------------

SEEDS = ("0", "1", "2", "3", "random")


class DeterminismTests(unittest.TestCase):
    def test_the_engine_holds_no_memo_so_there_is_nothing_to_turn_off(self):
        """If a memo is ever added to the performance or risk engines this fails, and the memo-on versus memo-off comparison of the statement (d) becomes mandatory before it is removed."""
        pattern = re.compile(r"lru_cache|functools\.cache|@cache\b|_memo\b|memoize|_MEMO")
        hits = []
        for package in ("risk", "performance", "marketdata", "risk_service", "performance_service"):
            for path in sorted((ROOT / "src" / package).rglob("*.py")):
                for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                    if pattern.search(line):
                        hits.append(f"{path.relative_to(ROOT)}:{number}: {line.strip()}")
        self.assertEqual(hits, [])

    def test_a_cold_world_gives_the_bytes_of_the_warm_one(self):
        """The in-process half: a world built again from nothing (its own market, its own runner) gives the same canonical result for a scenario of each part."""
        for key in ("single/three_years_with_benchmark", "fx/portfolio_five_missed", "current/instant"):
            sc = next(s for s in SCENARIOS if s.key == key)
            world = {"part1": 1, "part2": 2, "part3": 3}[sc.world]
            runner, market = g.build_runner(world)
            self.addCleanup(market.close)
            p = portfolio_of(runner, sc.portfolio)
            a = next(x for x in p["assertions"] if x["id"] == sc.assertion)
            it = dict(a["expect"][sc.item], request=sc.request, frequency=sc.frequency)
            cold = runner.risk(p, a, it, ALL)
            self.assertEqual(cold.canonical_json(), _RESULTS[key].canonical_json(), key)

    def test_every_scenario_is_byte_identical_across_processes_and_five_hash_seeds(self):
        first = digest_of_all()
        procs = [subprocess.Popen([sys.executable, str(Path(__file__)), "digest"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=dict(os.environ, PYTHONHASHSEED=seed)) for seed in SEEDS]
        digests = []
        for proc in procs:
            out, err = proc.communicate(timeout=1500)
            self.assertEqual(proc.returncode, 0, err)
            digests.append(out.strip().splitlines()[-1])
        self.assertEqual(len(SEEDS), 5)
        self.assertEqual(set(digests), {first}, digests)


# --- (e) reproduction --------------------------------------------------------------------------------------------------------------------------

def golden_results():
    """Every metric item of parts 1 to 3: `(world, runner, portfolio, assertion, item, result)`, once per distinct manifest and answer."""
    seen = set()
    for world, part in (("part1", 1), ("part2", 2), ("part3", 3), ("part4", 4)):
        runner = runner_of(world)
        for p, a, it in g.items(runner.data):
            if it["kind"] not in g.KIND_METRIC:
                continue
            res = runner.risk(p, a, it, (g.KIND_METRIC[it["kind"]],))
            key = (res.manifest.manifest_id, res.result_digest)
            if key in seen:
                continue
            seen.add(key)
            yield world, runner, p, a, it, res


class ReproduceEveryGoldenResultTests(unittest.TestCase):
    def reproduce(self, runner, p, a, res, digest):
        events, version = runner.events[p["name"]], runner.version(p, a)
        kw = dict(suppressions=runner.suppressions_for(p, version), risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=runner.catalog, selections=g.selections_of(p, runner.ids))
        if res.manifest.current is not None:
            kw["market_at"] = runner.market.market_at
        return reproduce_risk(res.manifest, digest, events, runner.market.store, runner.market.ident, runner.market.conventions, runner.perf, **kw)

    def test_every_golden_result_is_reproduced_with_its_digest_and_never_without_one(self):
        count, current, uncompared, scoped = 0, 0, 0, 0
        for world, runner, p, a, it, res in golden_results():
            report = self.reproduce(runner, p, a, res, res.result_digest)
            self.assertEqual((report.status, report.detail), (St.REPRODUCED, ""), (world, a["id"], it["kind"]))
            count += 1
            current += res.manifest.current is not None
            scoped += res.manifest.series.scope != "PORTFOLIO"
            if count % 7 == 1:  # without an expected digest: never reported as reproduced
                self.assertEqual(self.reproduce(runner, p, a, res, None).status, St.RESULT_NOT_COMPARED, (world, a["id"]))
                uncompared += 1
        self.assertGreater(count, 150)
        self.assertGreater(current, 0)  # Current-mode results are among them
        self.assertGreater(scoped, 0)   # and account-scope ones
        self.assertGreater(uncompared, 10)

    def test_a_wrong_digest_is_named_not_reproduced(self):
        world, runner, p, a, it, res = next(golden_results())
        self.assertEqual(self.reproduce(runner, p, a, res, "0" * 64).status, St.RESULT_DIFFERS)

    def test_every_scenario_result_reproduces_too(self):
        for sc in SCENARIOS:
            runner, p, a, it = case_of(sc)
            res = _RESULTS[sc.key]
            report = self.reproduce(runner, p, a, res, res.result_digest)
            self.assertEqual((report.status, report.detail), (St.REPRODUCED, ""), sc.key)


# --- (f) UAT-03 --------------------------------------------------------------------------------------------------------------------------------

UAT_DB_TESTS = ("test_uat_03_changing_the_benchmark_recomputes_only_the_benchmark_group", "test_uat_03_clearing_the_benchmark_suppresses_only_the_benchmark_group",
                "test_uat_03_a_ledger_that_moved_recomputes_both_groups_and_no_old_view_stays_current", "test_a_held_view_is_not_current_after_the_release_the_as_of_or_the_reporting_currency_moved",
                "test_a_result_computed_at_an_old_pin_is_reproducible_after_the_selection_moved")


class Uat03Tests(unittest.TestCase):
    def test_the_groups_partition_the_twelve_metrics_by_what_they_read(self):
        self.assertEqual(set(grp.INDEPENDENT_GROUP) | set(grp.BENCHMARK_GROUP), set(ALL))
        self.assertEqual(set(grp.INDEPENDENT_GROUP) & set(grp.BENCHMARK_GROUP), set())
        self.assertEqual(set(grp.INDEPENDENT_GROUP), {"risk_volatility", "risk_downside_deviation", "risk_max_drawdown", "risk_sharpe", "risk_sortino"})

    def test_engine_level_a_selection_change_moves_only_the_benchmark_group(self):
        """Q1's selection log has five versions (a benchmark, cleared, an absent one, a price-return one, the late one): the independent group's answer is the same bytes at every version, the benchmark
        group's is not. (The same through the service and PostgreSQL: `test_uat_03_end_to_end_through_the_risk_service_and_the_database`.)"""
        runner = runner_of("part2")
        p = portfolio_of(runner, "Q1")
        a = next(x for x in p["assertions"] if x["id"] == "Q1-B1")
        it = dict(a["expect"][0], request=TRAILING_12)
        independent, benchmark = {}, {}
        for version in (1, 2, 3, 4, 5):
            at = dict(a, id=f"{a['id']}-sel{version}", selection_log_version=version)  # the runner caches by assertion id: another version is another question
            independent[version] = runner.risk(p, at, it, grp.INDEPENDENT_GROUP)
            benchmark[version] = runner.risk(p, at, it, grp.BENCHMARK_GROUP)
        self.assertEqual({r.result_digest for r in independent.values()}, {independent[1].result_digest})
        self.assertEqual({r.manifest.manifest_id for r in independent.values()}, {independent[1].manifest.manifest_id})
        self.assertTrue(all(r.manifest.benchmark is None for r in independent.values()))  # it names no benchmark: the selection is not one of its inputs
        self.assertEqual(len({r.result_digest for r in benchmark.values()}), 5)  # every version of the selection gave the benchmark group another answer
        self.assertEqual(benchmark[1].metric("risk_beta").benchmark.benchmark_id, "SYN4_BM_US_TR")
        self.assertEqual({m.state for m in benchmark[2].metrics}, {SS.INSUFFICIENT_DATA})  # cleared: no benchmark is substituted
        # and the independent group's answer is the same bytes as the same metrics asked inside the full set (nothing else moved)
        full = runner.risk(p, a, it, ALL)
        for mid in grp.INDEPENDENT_GROUP:
            self.assertEqual(full.metric(mid).to_canonical_dict()["value"], independent[1].metric(mid).to_canonical_dict()["value"])

    @unittest.skipIf(bool(pk.skip_reason()), pk.skip_reason())
    def test_uat_03_end_to_end_through_the_risk_service_and_the_database(self):
        """Through `risk_service` as `finweb_app` against the ledger and selection tables: the selection moved recomputes only the benchmark group (the independent result is the same object), a ledger that
        moved recomputes both, and no view stays labelled CURRENT after an input moved."""
        result = run_case(pg_service.RiskServiceTests, UAT_DB_TESTS)
        self.assertEqual(result.testsRun, len(UAT_DB_TESTS))
        self.assertEqual((len(result.failures), len(result.errors), len(result.skipped)), (0, 0, 0), (result.failures, result.errors))


# --- (g) CP3 non-regression -------------------------------------------------------------------------------------------------------------------

class Cp3NonRegressionTests(unittest.TestCase):
    def test_the_cp3_byte_identity_test_still_holds(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(byte_identity)
        result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        self.assertGreater(result.testsRun, 3)
        self.assertEqual((len(result.failures), len(result.errors)), (0, 0), (result.failures, result.errors))


# --- the golden fixtures and the open findings -----------------------------------------------------------------------------------------------

class GoldenPartsAreAllCheckedTests(unittest.TestCase):
    def test_parts_1_to_3_are_checked_in_full_with_no_mismatch_and_nothing_deferred(self):
        total = 0
        for world, expected in (("part1", 78), ("part2", 61), ("part3", 107), ("part4", 11)):
            runner = runner_of(world)
            mismatches, checked, deferred = g.check_all(runner)
            self.assertEqual((checked, deferred), (expected, []), world)
            self.assertEqual(mismatches, [], world)
            total += checked
        self.assertEqual(total, 257)


class OpenFindingsTests(unittest.TestCase):
    def test_every_open_finding_names_a_scenario_and_a_metric_that_exist(self):
        keys = {sc.key for sc in SCENARIOS}
        for (key, mid), why in OPEN_FINDINGS.items():
            self.assertIn(key, keys)
            self.assertIn(mid, ALL)
            self.assertTrue(why)

    def test_the_active_return_over_a_zero_capital_window_is_refused_with_no_reason_and_no_number(self):
        """Ruling 6.9 (1.5) (CP4F-1; mutation M-C30): INSUFFICIENT_DATA, no reason, detail ZERO_CAPITAL_PERIOD only (not PERIOD_INSUFFICIENT); the benchmark return, which has no portfolio leg, stands."""
        res = _RESULTS["zero_capital/interior_period"]
        m = res.metric("risk_active_return")
        self.assertEqual((m.state, m.result.reason_code, m.value, m.exact, m.comparability, m.decomposition), (SS.INSUFFICIENT_DATA, None, None, None, None, None))
        self.assertEqual(g._risk_names(m.details), ["ZERO_CAPITAL_PERIOD"])
        self.assertEqual(res.metric("benchmark_return").state, SS.AVAILABLE)
        for mid in grp.INDEPENDENT_GROUP:  # and every other statistic over the same window is refused
            self.assertEqual(res.metric(mid).state, SS.INSUFFICIENT_DATA, mid)

    def test_an_interior_valuation_that_is_not_a_twr_input_keeps_the_active_return_available(self):
        """The reviewer's caution (CP4F-1): a window with no period chain is NOT refused wholesale. Five missing HKD fixings at one interior grid date make that period INSUFFICIENT_DATA (every statistic is
        refused with MISSING_FX_HISTORY), but that valuation is not an input of TWR(g_0, g_n] (Ruling 6.9 (1.1)): the active return is AVAILABLE, with RS-1 recorded NOT_COMPUTABLE, never PASS."""
        res = _RESULTS["valuation/interior_insufficient_active_return_stands"]
        m = res.metric("risk_active_return")
        self.assertEqual((m.state, m.result.reason_code), (SS.AVAILABLE, None))
        self.assertIsNotNone(m.value)
        self.assertEqual(dict(m.lineage)["identity:RS-1"], "NOT_COMPUTABLE")
        self.assertEqual(dict(m.lineage)["identity:RS-2"], "PASS")
        self.assertEqual(dict(m.lineage)["portfolio_leg_state"], "AVAILABLE")  # the leg's own state is in the lineage (Ruling 7.7 (1.6)), and the default view does not fall back on it
        self.assertEqual(res.metric("risk_volatility").state, SS.INSUFFICIENT_DATA)
        self.assertFalse(dv.falls_back(m))

    def test_the_exit_criterion_has_no_open_finding(self):
        """`OPEN_FINDINGS` is empty (the CP4e finding was ruled in risk/1.5); the day one is listed again this fails until it is ruled."""
        self.assertEqual(OPEN_FINDINGS, {})


class FaultNotesCarryNoNumberTests(unittest.TestCase):
    """CP4F-9: a metric refused for a calculation error (an identity that did not hold) must not carry the unverified number in its cause note, its lineage or anywhere else a view or the AI layer reads."""

    NUMBER = re.compile(r"-?\d*[1-9]\d*/\d*[1-9]\d*|\d+\.\d{4,}")  # a fraction or a long decimal: what an exact value or its presentation looks like (the words "0/0" of a degenerate case are not a value)

    def refused_by_a_lying_twr_engine(self):
        import risk.engine as E  # noqa: PLC0415

        real = E.compute_twr_between

        def lying(*args, **kw):
            v = real(*args, **kw)
            return dataclasses.replace(v, exact=None if v.exact is None else v.exact + Fraction(1, 10 ** 9))

        runner = runner_of("part2")
        p = portfolio_of(runner, "Q1")
        a = next(x for x in p["assertions"] if x["id"] == "Q1-B1")
        it = dict(a["expect"][0], request={"rule": "CUSTOM", "base": "2025-01-08"})
        honest = runner.risk(p, a, it, ALL)
        with mock.patch("risk.engine.compute_twr_between", lying):
            fresh = E.compute_risk(runner.events[p["name"]], runner.version(p, a), g.spec_of(it["request"]), g.D(a["as_of"]), g.Frequency(it["frequency"]), g.CurrencyCode(p["reporting_currency"]),
                                   runner.market.store, runner.market.ident, runner.market.conventions, runner.perf, suppressions=runner.suppressions_for(p, runner.version(p, a)),
                                   risk_free_catalog=g.EMPTY_RISK_FREE_CATALOG, benchmark_catalog=runner.catalog, selections=g.selections_of(p, runner.ids),
                                   selection_version=a.get("selection_log_version", 0), portfolio_id=runner.ids(p["portfolio_id"]), metrics=ALL)
        return honest, fresh

    def test_a_calculation_error_names_the_identity_and_no_value(self):
        honest, fresh = self.refused_by_a_lying_twr_engine()
        faulted = [m for m in fresh.metrics if m.result.reason_code is not None and m.result.reason_code.value == "CALCULATION_ERROR"]
        self.assertTrue({m.metric_id for m in faulted} >= {"risk_max_drawdown", "risk_active_return"}, [m.metric_id for m in faulted])  # RD-1 and RS-1 both bite
        for m in faulted:
            self.assertEqual((m.state, m.value, m.exact), (SS.INSUFFICIENT_DATA, None, None))
            text = json.dumps([c.to_obj() for c in m.causes], default=str) + json.dumps(m.lineage, default=str)
            self.assertIsNone(self.NUMBER.search(text), (m.metric_id, text))
            for earlier in honest.metrics:  # nor the value the honest computation gives, in any form
                if earlier.metric_id == m.metric_id and earlier.exact is not None:
                    self.assertNotIn(str(earlier.exact), text)
                    self.assertNotIn(str(earlier.value), text)
            self.assertIn(m.lineage[0][0].split(":")[0], ("identity",))

    def test_no_refused_metric_of_any_scenario_carries_a_number_in_a_cause_or_in_lineage(self):
        for sc in SCENARIOS:
            for m in _RESULTS[sc.key].metrics:
                if m.state is not SS.INSUFFICIENT_DATA:
                    continue
                text = json.dumps([c.to_obj() for c in m.causes], default=str) + json.dumps(m.lineage, default=str)
                self.assertIsNone(self.NUMBER.search(text), (sc.key, m.metric_id, self.NUMBER.search(text) and self.NUMBER.search(text).group(0)))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "digest":
        print(digest_of_all())
        for market in _OWNED:
            market.close()
    else:
        unittest.main()
