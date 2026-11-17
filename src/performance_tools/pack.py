"""The HG2 evidence pack builder (PRD 38.4 "Required evidence"; tech plan 16.10; PD-0035 section 3).

A PACK is a directory of JSON files (one per evidence item, plus the inputs, the manifests and the open items) and ONE human-readable Markdown summary. It REPORTS what the engine computes for a
named portfolio, as-of date and windows; it derives no expected value and states no judgment (the owner decides). The golden fixtures and their tests are the correctness proof; this pack is the
evidence an inspector reads.

RULES the builder keeps:
- every number is shown WITH its state, reason and detail, its manifest id, and the result digest it was computed to; a manifest is re-run and its digest compared, and a re-run without an expected
  digest is `RESULT_NOT_COMPARED`, never presented as reproduced (Ruling 11.1 (1.4));
- every result of a synthetic release is labelled synthetic (market-data Ruling 4.8), in every file, and the pack carries the PD-0035 caveat that CN and HK price behaviour is shown on SYNTHETIC
  data only (no admissible real CN or HK price source exists);
- an input the pack does not have is stated, never fabricated (no calendar: freshness UNKNOWN and the states that follow);
- the engine is called through its public entries; split detection (F8-B, read-only) is always run where calendars exist, and its absence is stated where they do not.
"""

from __future__ import annotations

import dataclasses
import datetime
import enum
import hashlib
import json
import uuid
from dataclasses import dataclass, field
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from corporate_actions_service import split_confirmation as f8b
from domain.currency import CurrencyCode
from domain.replay import SequencedEvent, live_events, reconstruct
from performance import engine
from performance.manifest import ComputationResult, ReproductionStatus
from performance.numerics import CARINO_RESIDUAL_BOUND, IRR_MAX_ITERATIONS, IRR_STOP, TRANSCENDENTAL_PRECISION
from performance.periods import WindowRule, WindowSpec
from performance.rounding import RATE_DECIMALS, RETURN_DECIMALS
from performance_service import service as svc

PACK_SCHEMA = "finweb.hg2_evidence_pack/1"
PD_0035_CAVEAT = ("PD-0035 section 3: Mainland China and Hong Kong price behaviour is shown on SYNTHETIC data only. No admissible real CN or HK price source exists (PD-0031, PD-0032); the real slice is "
                  "US prices (Alpha Vantage, the last 100 sessions) and ECB FX only. A synthetic result is never a real market fact (market-data Ruling 4.8).")
FRANKFURTER_LABEL = ("ECB reference rates as republished by Frankfurter (source `frankfurter.ecb`); provenance UNCONFIRMED: not evidence that a value is the ECB reference rate for its date "
                     "(market-data Ruling 1.1a)")
FX_SOURCE_LABELS = {"frankfurter.ecb": FRANKFURTER_LABEL, "ecb.eurofxref": "the ECB's own euro reference-rate history file (source `ecb.eurofxref`)"}
SYNTHETIC_LABEL = "SYNTHETIC: every result below was computed from a market-data version that holds synthetic files; none is a real market fact (market-data Ruling 4.8)."
HYPOTHETICAL_LABEL = "DEMONSTRATION LEDGER: these events are not a user's holdings (P8); they exist to exercise the engine."


# --- subject ------------------------------------------------------------------------------------------------------------------------------

@dataclass
class PackSubject:
    """What a pack is about. `files` describes every data file of the release (source, kind, hash, retrieval, usage scope, whether it is admitted)."""

    name: str
    kind: str  # SYNTHETIC_DEMONSTRATION_A | REAL_SLICE_DEMONSTRATION_B
    description: str
    portfolio_id: uuid.UUID
    events: Tuple[SequencedEvent, ...]
    ledger_version: int
    reporting: CurrencyCode
    store: Any
    resolver: Any
    market_conventions: Any
    perf: Any
    policy: f8b.ConfirmationPolicy
    as_of: datetime.date
    windows: Tuple[Tuple[str, WindowSpec], ...]
    files: Tuple[Mapping[str, Any], ...] = ()
    notes: Tuple[str, ...] = ()
    limitations: Tuple[str, ...] = ()
    account_names: Mapping[uuid.UUID, str] = field(default_factory=dict)
    requirements: Tuple[str, ...] = ()  # what an absent input still needs (the real slice)
    operator_selection: Mapping[str, Any] = field(default_factory=dict)  # the file set the operator named by sha256 (CP3-12); empty when none was named
    vintage_conflicts: Tuple[Mapping[str, Any], ...] = ()  # two vintages of one series: reported with both files, neither in M
    extra_reporting: Tuple[CurrencyCode, ...] = ()  # further reporting-currency VIEWS of the same ledger (the real slice: EUR and CNY, so the ECB FX path is exercised)


# --- encoding -------------------------------------------------------------------------------------------------------------------------------

def enc(x: Any) -> Any:
    """A deterministic JSON-able form: exact rationals as `n/d` text, decimals as plain text, dates ISO, ids text, dataclasses and mappings with sorted keys."""
    if isinstance(x, Fraction):
        return str(x)
    if isinstance(x, Decimal):
        return format(x, "f")
    if isinstance(x, datetime.datetime):
        return x.isoformat()
    if isinstance(x, datetime.date):
        return x.isoformat()
    if isinstance(x, (uuid.UUID, Path)):
        return str(x)
    if isinstance(x, enum.Enum):
        return x.value
    if dataclasses.is_dataclass(x) and not isinstance(x, type):
        return {f.name: enc(getattr(x, f.name)) for f in dataclasses.fields(x)}
    if isinstance(x, Mapping):
        return {str(enc(k)): enc(v) for k, v in sorted(x.items(), key=lambda kv: str(enc(kv[0])))}
    if isinstance(x, (list, tuple)):
        return [enc(v) for v in x]
    if isinstance(x, (set, frozenset)):
        return sorted((enc(v) for v in x), key=lambda v: json.dumps(v, sort_keys=True))
    return x


def dumps(obj: Any) -> str:
    return json.dumps(enc(obj), indent=1, sort_keys=True, ensure_ascii=True) + "\n"


def mdict(m: Any) -> Dict[str, Any]:
    return enc(m.to_canonical_dict())


# --- the computations -----------------------------------------------------------------------------------------------------------------------

@dataclass
class Computation:
    key: str
    kind: str
    result: ComputationResult
    window_label: Optional[str] = None


@dataclass
class Computed:
    subject: PackSubject
    suppressions: Tuple[Any, ...]
    detection: str
    detection_report: Optional[Any]
    detection_note: str
    results: List[Computation]

    def get(self, key: str) -> ComputationResult:
        return next(c.result for c in self.results if c.key == key)

    def of_kind(self, kind: str) -> List[Computation]:
        return [c for c in self.results if c.kind == kind]


def _listings(subject: PackSubject) -> List[uuid.UUID]:
    return sorted({i.event.listing_id for i in subject.events if i.event.listing_id is not None and i.ledger_seq <= subject.ledger_version}, key=str)


def _detect(subject: PackSubject) -> Tuple[Tuple[Any, ...], str, Optional[Any], str]:
    """Split detection (F8-B, read-only, over the pinned ledger). Without calendars it cannot run, and the pack says so (the engine then has no freshness either)."""
    calendars = getattr(getattr(subject.market_conventions, "freshness", None), "calendars", None)
    if calendars is None or not calendars:
        return (), "NOT_RUN_NO_CALENDARS", None, ("split detection (F8-B) needs the session calendars of the market-data version, and none is registered: it was NOT run, so a corroborated split missing from the ledger "
                                                   "could not be found; every freshness is UNKNOWN as well")
    listings = _listings(subject)
    currencies = {lid: c for lid in listings for c in [subject.resolver.trading_currency(lid)] if c is not None}
    report, sup = svc.detect_split_suppressions(
        svc.PinnedLedgerAccess(subject.ledger_version, subject.events), subject.store, subject.portfolio_id, listings, datetime.date.min, datetime.date.max, subject.policy, currencies,
        calendars=calendars, exchange_of=subject.resolver.exchange_mic)
    return sup, svc.DETECTION, report, "split detection ran read-only over the pinned ledger and the whole release"


def run_all(subject: PackSubject) -> Computed:
    sup, detection, report, note = _detect(subject)
    base = dict(suppressions=sup, portfolio_id=subject.portfolio_id, detection=detection, detection_policy=svc.policy_reference(subject.policy))
    args = (subject.reporting, subject.store, subject.resolver, subject.market_conventions, subject.perf)
    L, end = subject.ledger_version, subject.as_of
    out: List[Computation] = []

    def add(key: str, kind: str, result: ComputationResult, window: Optional[str] = None) -> None:
        out.append(Computation(key, kind, result, window))

    for ccy in subject.extra_reporting:  # the same ledger in another reporting currency: every value then needs an FX rate (kinds `fx_valuation` and `fx_window`, apart from the PRD sections)
        view_args = (ccy, subject.store, subject.resolver, subject.market_conventions, subject.perf)
        add(f"fx_valuation:{ccy.code}@{end.isoformat()}", "fx_valuation", engine.compute(subject.events, L, end, *view_args, **base))
        for label, spec in subject.windows:
            add(f"fx_window:{ccy.code}:{label}", "fx_window", engine.compute_window(subject.events, L, spec, end, *view_args, verify_identities=True, **base), label)

    add(f"valuation@{end.isoformat()}", "valuation", engine.compute(subject.events, L, end, *args, **base))
    for item in live_events(subject.events, L):  # an accrued dividend is a receivable until its pay date: value the day before it settles
        e = item.event
        if e.event_type.value == "DIVIDEND" and e.ex_date is not None and e.ex_date < e.event_date <= end:
            day = e.event_date - datetime.timedelta(days=1)
            if f"valuation@{day.isoformat()}" not in {c.key for c in out}:
                add(f"valuation@{day.isoformat()}", "valuation", engine.compute(subject.events, L, day, *args, **base))
    for label, spec in subject.windows:
        res = engine.compute_window(subject.events, L, spec, end, *args, verify_identities=True, **base)
        add(f"window:{label}", "window", res, label)
        add(f"gains:{label}", "gains", engine.compute_gains(subject.events, L, end, *args, window=spec, **base), label)
        add(f"attribution:{label}", "attribution", engine.compute_attribution(subject.events, L, spec, end, *args, **base), label)
        bound = next((m.window.start for m in res.metrics if m.metric_id == "return_twr"), None)
        if bound is not None and bound != end and f"valuation@{bound.isoformat()}" not in {c.key for c in out}:
            add(f"valuation@{bound.isoformat()}", "valuation", engine.compute(subject.events, L, bound, *args, **base))
    return Computed(subject, sup, detection, report, note, out)


def reproduction(computed: Computed) -> List[Dict[str, Any]]:
    """Re-run every manifest and compare the digest recorded when the number was computed. A re-run is `REPRODUCED` only with an expected digest that matched; without one it is
    `RESULT_NOT_COMPARED` and is reported as exactly that."""
    s = computed.subject
    rows = []
    for c in computed.results:
        report = engine.reproduce(c.result.manifest, c.result.result_digest, s.events, s.store, s.resolver, s.market_conventions, s.perf, suppressions=computed.suppressions)
        rows.append({"key": c.key, "kind": c.kind, "manifest_id": c.result.manifest.manifest_id, "expected_result_digest": c.result.result_digest,
                     "reproduction": report.status.value, "reproduced": report.status is ReproductionStatus.REPRODUCED, "detail": report.detail,
                     "synthetic": c.result.manifest.synthetic, "engine_id": c.result.manifest.engine_id, "identities_run": list(c.result.manifest.identities_run)})
    return rows


# --- helpers for the sections ---------------------------------------------------------------------------------------------------------------

def _label_of(subject: PackSubject, listing_id: Optional[uuid.UUID]) -> str:
    if listing_id is None:
        return "-"
    try:
        lst = subject.resolver.listing(listing_id)
        return f"{lst.ticker}@{lst.mic}"
    except Exception:  # noqa: BLE001 (a resolver without `listing` still names the id)
        return str(listing_id)


def _event_row(subject: PackSubject, item: SequencedEvent) -> Dict[str, Any]:
    e = item.event
    row = {"ledger_seq": item.ledger_seq, "event_id": e.event_id, "account": subject.account_names.get(e.account_id, str(e.account_id)), "type": e.event_type, "date": e.event_date,
           "currency": e.currency.code, "listing": _label_of(subject, e.listing_id), "quantity": e.quantity, "amount": None if e.amount is None else {"amount": e.amount.amount, "currency": e.amount.currency.code}}
    for name in ("cost_basis", "bought_amount", "split_ratio", "counterparty_account_id", "settlement_date", "ex_date", "reverses_event_id", "corrects_event_id", "acquired_on"):
        v = getattr(e, name, None)
        if v is not None:
            row[name] = ({"amount": v.amount, "currency": v.currency.code} if hasattr(v, "currency") else v)
    return row


def _state_of(subject: PackSubject, day: datetime.date) -> Dict[str, Any]:
    state = reconstruct(subject.events, day, subject.ledger_version)
    accounts = []
    for a in state.accounts:
        accounts.append({
            "account": subject.account_names.get(a.account_id, str(a.account_id)), "status": a.status, "snapshot_date": a.snapshot_date,
            "positions": [{"listing": _label_of(subject, p.listing_id), "quantity": {"value": p.quantity.value, "state": p.quantity.sufficiency_state, "reason": p.quantity.reason_code,
                                                                                     "detail": p.quantity_detail},
                           "cost_basis": [{"currency": b.currency.code if getattr(b, "currency", None) is not None else None, "value": b.result.value, "state": b.result.sufficiency_state,
                                           "reason": b.result.reason_code} for b in p.cost_basis], "basis_detail": p.basis_detail} for p in a.positions],
            "cash": [{"currency": c.balance.currency.code, "balance": c.balance.amount} for c in a.cash]})
    return {"as_of": day, "ledger_version": state.ledger_version, "replay_convention_set": state.convention_set, "accounts": accounts}


def _metrics(res: ComputationResult, metric_id: str) -> List[Any]:
    return [m for m in res.metrics if m.metric_id == metric_id]


def _states(res: ComputationResult) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for m in res.metrics:
        key = m.result.sufficiency_state.value
        out[key] = out.get(key, 0) + 1
    return out


def _headline(m: Any) -> Dict[str, Any]:
    return {"metric_id": m.metric_id, "view": m.view, "subject": m.subject, "value": m.result.value, "exact": m.exact, "state": m.result.sufficiency_state,
            "reason": m.result.reason_code, "details": m.details, "currency": m.currency, "synthetic": m.synthetic, "manifest_id": m.manifest_id}


def fx_sources(subject: PackSubject) -> List[str]:
    """The source ids of the FX files in M (the admitted FX files of the subject's data files)."""
    return sorted({f["source_id"] for f in subject.files if f.get("data_kind") == "FX" and f.get("admitted")})


def fx_source_label(source_id: str) -> str:
    return FX_SOURCE_LABELS.get(source_id, source_id)


def caveat_for(subject: PackSubject) -> str:
    """The PD-0035 caveat (the owner's words), followed by what the FX in the pack is whenever it came from Frankfurter (market-data Ruling 1.1a item 2: not evidence of the ECB reference rate)."""
    if "frankfurter.ecb" in fx_sources(subject):
        return f"{PD_0035_CAVEAT} Qualification for the FX in this pack: {FRANKFURTER_LABEL}."
    return PD_0035_CAVEAT


def _labels(computed: Computed) -> Dict[str, Any]:
    results = [c.result for c in computed.results]
    syn = [r.manifest.synthetic for r in results]
    s = computed.subject
    return {"all_results_synthetic": all(syn), "any_result_synthetic": any(syn),
            "label": SYNTHETIC_LABEL if any(syn) else "REAL INPUTS: no synthetic file was read (usage scope INTERNAL_DEVELOPMENT_ONLY; not for onward provision)",
            "demonstration_ledger": HYPOTHETICAL_LABEL, "pd_0035_caveat": caveat_for(s), "fx_sources_in_m": [{"source_id": x, "what_it_is": fx_source_label(x)} for x in fx_sources(s)]}


def _fx_handling(computed: Computed) -> List[Dict[str, Any]]:
    """The rate the engine's lookup gives for each ledger event dated at its own date (never the user's own conversion rate), asked of the same port with the same conventions."""
    s = computed.subject
    rows = []
    for item in live_events(s.events, s.ledger_version):
        e = item.event
        if e.currency == s.reporting or e.event_date > s.as_of:
            continue
        if e.event_type.value in ("SPLIT", "REVERSAL"):
            continue
        lookup = s.store.fx_on(e.currency, s.reporting, e.event_date, s.market_conventions)
        rows.append({"event_id": e.event_id, "date": e.event_date, "type": e.event_type, "currency": e.currency.code, "to": s.reporting.code,
                     "outcome": lookup.outcome, "rate": lookup.rate, "fixing_date_used": lookup.date_used, "missed_fixings": lookup.missed_count,
                     "lineage_notes": list(lookup.lineage_notes), "synthetic": lookup.synthetic,
                     "source": [{"source_id": r.source_id, "what_it_is": fx_source_label(r.source_id)} for r in lookup.legs]})
    return rows


def _bridge(computed: Computed) -> List[Dict[str, Any]]:
    s = computed.subject
    rows = []
    for c in computed.of_kind("window"):
        twr = next(m for m in c.result.metrics if m.metric_id == "return_twr")
        gain = next(m for m in c.result.metrics if m.metric_id == "gain_absolute")
        base, end = twr.window.start, twr.window.end
        vb = next((m for cc in computed.of_kind("valuation") if cc.result.manifest.as_of == base for m in cc.result.metrics
                   if m.metric_id == "portfolio_value" and m.view == "REPORTING"), None)
        ve = next((m for cc in computed.of_kind("valuation") if cc.result.manifest.as_of == end for m in cc.result.metrics
                   if m.metric_id == "portfolio_value" and m.view == "REPORTING"), None)
        derived = None
        if vb is not None and ve is not None and vb.exact is not None and ve.exact is not None and gain.exact is not None:
            derived = ve.exact - vb.exact - gain.exact  # V_E - V_B - G: the net external flow the identity G = V_E - V_B - (I^C + I^K - O) implies
        flows = []
        for ce in engine.classify_events(s.events, s.ledger_version, s.perf.flows):
            if base < ce.event_date <= end and ce.flow_class.value.startswith("EXTERNAL"):
                flows.append({"event_id": ce.event_id, "date": ce.event_date, "type": ce.event_type, "class": ce.flow_class, "timing": ce.timing, "currency": ce.currency,
                              "native_amount": ce.native_amount, "listing": _label_of(s, ce.listing_id), "quantity": ce.quantity})
        rows.append({"window": c.window_label, "base": base, "end": end, "V_B": None if vb is None else _headline(vb), "V_E": None if ve is None else _headline(ve),
                     "G_investment_gain": _headline(gain), "net_external_flow_derived_as_VE_minus_VB_minus_G": derived, "external_flows": flows,
                     "reading": "deposits and withdrawals are external flows and are not gains; G is the change in value that is not an external flow (Ruling 5.1)"})
    return rows


def _internal_transfers(computed: Computed) -> Dict[str, Any]:
    s = computed.subject
    classified = engine.classify_events(s.events, s.ledger_version, s.perf.flows)
    internal = [ce for ce in classified if ce.internal]
    ids = {ce.event_id for ce in internal}
    out: Dict[str, Any] = {"internal_legs": [{"event_id": ce.event_id, "account": s.account_names.get(ce.account_id, str(ce.account_id)), "date": ce.event_date, "type": ce.event_type,
                                              "listing": _label_of(s, ce.listing_id), "quantity": ce.quantity, "native_amount": ce.native_amount, "currency": ce.currency,
                                              "class": ce.flow_class} for ce in internal],
                           "checks": []}
    if not internal:
        return out
    without = tuple(i for i in s.events if i.event.event_id not in ids)
    args = (s.reporting, s.store, s.resolver, s.market_conventions, s.perf)
    base = dict(suppressions=computed.suppressions, portfolio_id=s.portfolio_id, detection=computed.detection, detection_policy=svc.policy_reference(s.policy))
    for label, spec in s.windows:
        a = engine.compute_window(s.events, s.ledger_version, spec, s.as_of, *args, **base)
        b = engine.compute_window(without, s.ledger_version, spec, s.as_of, *args, **base)
        pick = lambda r: {m.metric_id: (m.exact, m.result.sufficiency_state.value) for m in r.metrics if m.metric_id in ("gain_absolute", "return_twr")}  # noqa: E731
        out["checks"].append({"window": label, "with_pairs": pick(a), "without_pairs": pick(b), "no_portfolio_level_effect": pick(a) == pick(b),
                              "reading": "removing the paired internal legs changes no portfolio-level gain or TWR (R8, PRD 9.6)"})
    return out


def _dividends(computed: Computed) -> Dict[str, Any]:
    s = computed.subject
    rows = []
    by_ccy: Dict[str, Fraction] = {}
    for item in live_events(s.events, s.ledger_version):
        e = item.event
        if e.event_type.value in ("DIVIDEND", "INTEREST", "TAX", "FEE", "INTEREST_CHARGED") and e.amount is not None and e.event_date <= s.as_of:
            rows.append(_event_row(s, item))
            if e.event_type.value == "DIVIDEND":
                by_ccy[e.currency.code] = by_ccy.get(e.currency.code, Fraction(0)) + Fraction(e.amount.amount)
    amounts = []
    for c in computed.of_kind("window"):
        for m in c.result.metrics:
            if m.metric_id in ("income_amount", "fees_amount", "taxes_amount", "financing_amount", "conversion_result_amount"):
                amounts.append({"window": c.window_label, **_headline(m)})
    receivables = [mdict(m) for m in _metrics(computed.get(f"valuation@{s.as_of.isoformat()}"), "receivable_value")]
    before_pay = [{"date": c.result.manifest.as_of, "receivable_metrics": [mdict(m) for m in _metrics(c.result, "receivable_value")]}
                  for c in computed.of_kind("valuation") if _metrics(c.result, "receivable_value") and c.result.manifest.as_of != s.as_of]
    return {"dividend_and_cost_events": rows, "receivable_on_the_day_before_each_pay_date": before_pay, "dividends_recorded_by_currency_native_sum": by_ccy, "income_and_cost_amounts_by_window": amounts, "receivables_at_as_of": receivables,
            "reading": "income is recognized on the ex-date when the ledger records one before the pay date (accrual), else on the pay date; the receivable is revalued by FX until it settles (Ruling 8.1)"}


def _splits(computed: Computed) -> Dict[str, Any]:
    s = computed.subject
    rows = []
    for item in live_events(s.events, s.ledger_version):
        e = item.event
        if e.event_type.value != "SPLIT":
            continue
        before = reconstruct(s.events, e.event_date - datetime.timedelta(days=1), s.ledger_version)
        after = reconstruct(s.events, e.event_date, s.ledger_version)

        def qty(state: Any) -> Any:
            a = next((x for x in state.accounts if x.account_id == e.account_id), None)
            p = None if a is None else next((y for y in a.positions if y.listing_id == e.listing_id), None)
            return None if p is None else p.quantity.value

        closes = []
        for day in (e.event_date - datetime.timedelta(days=1), e.event_date):
            lk = s.store.quote_on(e.listing_id, day, s.market_conventions)
            closes.append({"date": day, "raw_close_as_traded": None if lk.selected is None else lk.selected.observation.price, "session_used": lk.date_used})
        rows.append({"event_id": e.event_id, "account": s.account_names.get(e.account_id, str(e.account_id)), "listing": _label_of(s, e.listing_id), "date": e.event_date,
                     "ratio": e.split_ratio, "quantity_before": qty(before), "quantity_after": qty(after), "raw_closes_around_the_split": closes,
                     "reading": "the price used is the as-traded close of each date and the quantity is the replayed one (market-data Ruling 2.5); no adjusted series is read"})
    detection = None if computed.detection_report is None else {"outcomes": computed.detection_report.outcomes, "ledger_version_before": computed.detection_report.ledger_version_before,
                                                                 "ledger_version_after": computed.detection_report.ledger_version_after}
    return {"ledger_splits": rows, "detection": computed.detection, "detection_note": computed.detection_note, "split_detection_report": detection,
            "suppressions_handed_to_the_engine": computed.suppressions}


def _missing_cost(computed: Computed) -> Dict[str, Any]:
    gains = [c for c in computed.of_kind("gains")]
    table = []
    for c in gains:
        for m in c.result.metrics:
            table.append({"window": c.window_label, "metric_id": m.metric_id, "view": m.view, "subject": m.subject, "state": m.result.sufficiency_state, "reason": m.result.reason_code,
                          "details": m.details, "value": m.result.value})
    withheld = [r for r in table if r["reason"] == "MISSING_COST_BASIS" or "UNKNOWN_BASIS" in r["details"]]
    avail = [r for r in table if r["state"] in ("AVAILABLE", "LIMITED")]
    return {"metrics_returning_MISSING_COST_BASIS": withheld, "gain_metrics_that_stay_available_or_limited": avail,
            "valuation_and_returns_unaffected": [_headline(m) for c in computed.of_kind("window") for m in c.result.metrics if m.metric_id in ("gain_absolute", "return_twr")],
            "reading": "a missing basis withholds the realized and unrealized gain (never 0, never market value); the value, G, TWR and MWR do not need a basis and stay available"}


def _twr(computed: Computed) -> List[Dict[str, Any]]:
    rows = []
    for c in computed.of_kind("window"):
        twr = next(m for m in c.result.metrics if m.metric_id == "return_twr")
        ann = next(m for m in c.result.metrics if m.metric_id == "return_annualized")
        factors = {k: v for k, v in twr.lineage if k.startswith("factor:")}
        rows.append({"window": c.window_label, "twr": mdict(twr), "annualized": mdict(ann), "segment_factors": factors,
                     "daily_product_identity_I-2": dict(twr.lineage).get("identity:I-2"), "manifest_id": c.result.manifest.manifest_id})
    return rows


def _mwr(computed: Computed) -> List[Dict[str, Any]]:
    rows = []
    for c in computed.of_kind("window"):
        mwr = next(m for m in c.result.metrics if m.metric_id == "return_mwr")
        ann = next(m for m in c.result.metrics if m.metric_id == "return_mwr_annualized")
        rows.append({"window": c.window_label, "mwr": mdict(mwr), "annualized": mdict(ann), "investor_flows": dict(mwr.lineage).get("investor_flows"),
                     "identity_I-6": dict(mwr.lineage).get("identity:I-6"), "solver": {"precision_digits": TRANSCENDENTAL_PRECISION, "stop_relative": IRR_STOP, "max_iterations": IRR_MAX_ITERATIONS},
                     "unsupported_case_states": {"details": mwr.details, "state": mwr.result.sufficiency_state, "reason": mwr.result.reason_code}})
    return rows


def _gains(computed: Computed) -> List[Dict[str, Any]]:
    return [{"window": c.window_label, "manifest_id": c.result.manifest.manifest_id, "metrics": [mdict(m) for m in c.result.metrics],
             "caveat": "gains follow FIFO/1 (PD-0035 section 1); a broker's lot method may differ (Ruling 3.3a)"} for c in computed.of_kind("gains")]


def _fx_attribution(computed: Computed) -> List[Dict[str, Any]]:
    rows = []
    for c in computed.of_kind("attribution"):
        money = next(m for m in c.result.metrics if m.metric_id == "attribution_money")
        ret = next(m for m in c.result.metrics if m.metric_id == "attribution_return")
        fx_by_currency = next((mdict(m) for m in c.result.metrics if m.metric_id == "attribution_breakdown"
                               and dict(m.subject).get("group_by") == "currency" and dict(m.subject).get("line") == "attr.fx"), None)
        rows.append({"window": c.window_label, "money": mdict(money), "percentage": mdict(ret), "fx_effect_by_currency": fx_by_currency,
                     "identities": {k: v for k, v in dict(money.lineage).items() if k.startswith("identity:")}, "carino_residual": dict(ret.lineage).get("carino_residual"),
                     "reading": "the FX effect (attr.fx) is the revaluation of positions, cash and receivables by the moving rate; the price-FX interaction is shown, never folded (Ruling 9.1)"})
    return rows


def _i7(computed: Computed) -> List[Dict[str, Any]]:
    """Identity I-7 (method independence, Ruling 11.1): `RG + UG = proceeds + MV - sum of costs`, exactly, where it applies: the since-inception realized and unrealized aggregates are both AVAILABLE
    (every basis known) and the ledger has no transfer and no opening position (lots then come only from purchases). Where it does not apply, the row says why; it is never counted as a pass."""
    s = computed.subject
    rows = []
    live = [i.event for i in live_events(s.events, s.ledger_version) if i.event.event_date <= s.as_of]
    blockers = sorted({e.event_type.value for e in live if e.event_type.value in ("TRANSFER_IN", "TRANSFER_OUT", "OPENING_POSITION")})
    val = computed.get(f"valuation@{s.as_of.isoformat()}")
    for c in computed.of_kind("gains"):
        spec = next(sp for label, sp in s.windows if label == c.window_label)
        row: Dict[str, Any] = {"window": c.window_label, "identity": "I-7"}
        rg = next((m for m in c.result.metrics if m.metric_id == "realized_gain_total"), None)
        ug = next((m for m in c.result.metrics if m.metric_id == "unrealized_gain_total"), None)
        if spec.rule is not WindowRule.SINCE_INCEPTION:
            row.update(status="NOT_APPLICABLE", why="only the since-inception window holds every sale")
        elif blockers:
            row.update(status="NOT_APPLICABLE", why=f"the ledger has {blockers}: lots carried or opened are outside this identity's domain")
        elif rg is None or ug is None or rg.exact is None or ug.exact is None or rg.result.sufficiency_state.value != "AVAILABLE" or ug.result.sufficiency_state.value != "AVAILABLE":
            row.update(status="NOT_APPLICABLE", why="an aggregate is not AVAILABLE (a basis is unknown or an input is missing)",
                       realized=None if rg is None else _headline(rg), unrealized=None if ug is None else _headline(ug))
        else:
            total_proceeds, total_costs, missing = Fraction(0), Fraction(0), False
            for e in live:
                if e.event_type.value in ("SELL", "BUY") and e.amount is not None:
                    rate = Fraction(1) if e.amount.currency == s.reporting else s.store.fx_on(e.amount.currency, s.reporting, e.event_date, s.market_conventions).rate
                    if rate is None:
                        missing = True
                        continue
                    if e.event_type.value == "SELL":
                        total_proceeds += Fraction(e.amount.amount) * rate
                    else:
                        total_costs += Fraction(e.amount.amount) * rate
            mv = sum((m.exact for m in val.metrics if m.metric_id == "holding_value" and m.view == "REPORTING" and m.exact is not None), Fraction(0))
            if missing:
                row.update(status="NOT_COMPUTABLE", why="a trade-date fixing is missing")
            else:
                lhs, rhs = rg.exact + ug.exact, total_proceeds + mv - total_costs
                row.update(status="PASS" if lhs == rhs else "FAIL", realized_plus_unrealized=lhs, proceeds_plus_market_value_minus_costs=rhs, proceeds=total_proceeds, market_value=mv, costs=total_costs)
        rows.append(row)
    return rows


def _fx_probe(s: PackSubject, target: CurrencyCode, day: datetime.date) -> Dict[str, Any]:
    """The rate the engine's lookup gives for `reporting -> target` on `day`: outcome, exact rate, the fixing date and instant of every leg, the missed-fixing count, the freshness of each leg and
    the lineage notes. Asked of the same port with the same conventions, so it is what the valuation used."""
    lk = s.store.fx_on(s.reporting, target, day, s.market_conventions)
    legs = [{"source": r.source_id, "pair": f"{r.observation.base_currency.code}->{r.observation.quote_currency.code}", "rate": r.observation.rate, "fixing_date": r.observation.value_date,
             "observed_at": r.observation.observed_at, "rate_basis": r.observation.rate_basis, "usage_scope": r.observation.lineage.usage_scope} for r in lk.legs]
    return {"on": day, "pair": f"{s.reporting.code}->{target.code}", "outcome": lk.outcome, "rate": lk.rate, "fixing_date_used": lk.date_used, "missed_fixings": lk.missed_count,
            "legs": legs, "leg_freshness": list(lk.leg_freshness), "lineage_notes": list(lk.lineage_notes), "synthetic": lk.synthetic}


def _fx_views(computed: Computed) -> Dict[str, Any]:
    s = computed.subject
    days = sorted({s.as_of} | {i.event.event_date for i in live_events(s.events, s.ledger_version) if i.event.event_date <= s.as_of})
    out: Dict[str, Any] = {"reporting_currency_of_the_pack": s.reporting.code, "views": []}
    for ccy in s.extra_reporting:
        val = computed.get(f"fx_valuation:{ccy.code}@{s.as_of.isoformat()}")
        wins = [c for c in computed.results if c.kind == "fx_window" and c.key.startswith(f"fx_window:{ccy.code}:")]
        what = " and ".join(fx_source_label(x) for x in fx_sources(s)) or "no FX file is admitted"
        view = {"reporting_currency": ccy.code, "fx_source": what,
                "route": (f"a direct quote (EUR-based, units per EUR) from: {what}" if ccy.code == "EUR" else
                          f"a cross through EUR from two legs of: {what} (market-data Ruling 1.3); the CNY parity band check does not run (PARITY_CHECK_NOT_RUN)"),
                "valuation": [_headline(m) | {"causes": [c.note or c.ref for c in m.causes][:6]} for m in val.metrics if m.metric_id == "portfolio_value"],
                "windows": [{"window": c.window_label, "metrics": [_headline(m) | {"causes": [x.note or x.ref for x in m.causes][:4]} for m in c.result.metrics if m.metric_id in ("gain_absolute", "return_twr")]} for c in wins],
                "rates_asked_of_the_port": [_fx_probe(s, ccy, d) for d in days]}
        out["views"].append(view)
    return out


def _identities(computed: Computed) -> Dict[str, Any]:
    table: Dict[str, Dict[str, int]] = {}
    where_failed = []
    for c in computed.results:
        for m in c.result.metrics:
            for k, v in m.lineage:
                if k.startswith("identity:"):
                    table.setdefault(k[len("identity:"):], {}).setdefault(v, 0)
                    table[k[len("identity:"):]][v] += 1
                    if v == "FAIL":
                        where_failed.append({"computation": c.key, "metric_id": m.metric_id, "identity": k})
    i7 = _i7(computed)
    for row in i7:
        table.setdefault("I-7", {}).setdefault(row["status"], 0)
        table["I-7"][row["status"]] += 1
        if row["status"] == "FAIL":
            where_failed.append({"computation": f"gains:{row['window']}", "metric_id": "realized_gain_total+unrealized_gain_total", "identity": "identity:I-7"})
    return {"identity_I-7_method_independence": i7, "identity_status_counts_over_every_metric_carrying_one": table, "identities_run_per_computation": {c.key: list(c.result.manifest.identities_run) for c in computed.results},
            "failed": where_failed, "reading": "PASS means the identity ran and held exactly (tier E, tolerance 0); NOT_COMPUTABLE means its inputs do not exist (it is not a pass); NOT_RUN means it is not required in that call"}


def tolerances(perf: Any) -> Dict[str, Any]:
    return {
        "convention_set": perf.convention_set_id, "source": "performance/1.12 Ruling 11.2 and Rulings 2.2 to 2.4",
        "table": [
            {"comparison": "tier-E identities I-1 to I-9", "tolerance": "0", "basis": "exact rationals"},
            {"comparison": "a presented money value against its exact value", "tolerance": "<= 1/2 minor unit", "basis": "Ruling 2.2"},
            {"comparison": "independently presented parts against their presented total", "tolerance": "<= (k+1)/2 quanta", "basis": "Ruling 2.4 item 2"},
            {"comparison": "an apportioned decomposition, displayed parts against displayed total", "tolerance": "0", "basis": "Ruling 2.4 item 3"},
            {"comparison": "a presented return against its exact value", "tolerance": f"<= 0.5 x 10^-{RETURN_DECIMALS}", "basis": "the quantum"},
            {"comparison": "Carino sum of components against the TWR, internal", "tolerance": f"<= {CARINO_RESIDUAL_BOUND}", "basis": f"precision {TRANSCENDENTAL_PRECISION}"},
            {"comparison": "presented components against the presented TWR", "tolerance": f"<= 4.5 x 10^-{RETURN_DECIMALS}", "basis": "Ruling 2.4 item 2, K = 8"},
            {"comparison": "IRR against the true root", "tolerance": "<= 10^-30 relative + 0.5 x 10^-12", "basis": "Ruling 6.2"},
            {"comparison": "fixture against engine, exact outputs", "tolerance": "0 on the presented value", "basis": "Ruling 11.2"},
            {"comparison": "fixture against engine, transcendental outputs", "tolerance": "10^-10 absolute", "basis": "Ruling 11.2"}],
        "rounding": {"mode": "half away from zero", "money": "the minor unit of the currency (minor-unit table, status per row)", "return_decimals": RETURN_DECIMALS, "rate_decimals": RATE_DECIMALS,
                     "rounding_rule_id": perf.rounding.rule_id, "minor_unit_table_version": perf.rounding.table_version},
        "open_items_still_injected": list(perf.visible_open_items()), "is_conformant": perf.is_conformant}


# --- the pack ---------------------------------------------------------------------------------------------------------------------------------

SECTION_FILES = (
    ("01_positions", "Reconstructed positions from ledger events"), ("02_current_value", "Current portfolio value"), ("03_currencies", "Reporting and native currencies"),
    ("04_price_fx_timestamps", "Price and FX timestamps"), ("05_historical_fx", "Historical FX handling"), ("06_deposits_vs_gains", "Deposits versus investment gains"),
    ("07_internal_transfers", "Internal transfers"), ("08_dividends", "Dividends"), ("09_splits", "Splits"), ("10_missing_cost_basis", "Missing cost basis behaviour"),
    ("11_twr", "TWR"), ("12_mwr_irr", "MWR / IRR where supported"), ("13_realized_unrealized", "Realized and unrealized gain where supported"), ("14_fx_attribution", "FX attribution"),
    ("15_reconciliation_proof", "Reconciliation proof"), ("16_tolerances", "Known numerical tolerances"))


def build_sections(computed: Computed, reproduced: List[Dict[str, Any]]) -> Dict[str, Any]:
    s = computed.subject
    val = computed.get(f"valuation@{s.as_of.isoformat()}")
    dates = sorted({s.as_of} | {m.window.start for c in computed.of_kind("window") for m in c.result.metrics if m.metric_id == "return_twr"})
    lineage_rows = []
    for m in val.metrics:
        if m.metric_id in ("holding_value", "cash_value", "receivable_value"):
            lineage_rows.append({"metric_id": m.metric_id, "view": m.view, "subject": m.subject, "state": m.result.sufficiency_state, "reason": m.result.reason_code,
                                 "lineage": dict(m.lineage), "freshness": m.freshness, "details": m.details})
    currencies = {
        "reporting_currency": s.reporting.code,
        "holdings": [{"listing": _label_of(s, lid), "trading_currency": getattr(s.resolver.trading_currency(lid), "code", None), "exchange_mic": s.resolver.exchange_mic(lid)} for lid in _listings(s)],
        "cash_currencies_by_account": {s.account_names.get(a.account_id, str(a.account_id)): sorted(c.balance.currency.code for c in a.cash)
                                       for a in reconstruct(s.events, s.as_of, s.ledger_version).accounts},
        "native_and_reporting_values_at_as_of": [mdict(m) for m in val.metrics if m.metric_id in ("holding_value", "cash_value", "receivable_value", "portfolio_value")]}
    labels = _labels(computed)
    sections = {
        "01_positions": {"states": [_state_of(s, d) for d in dates], "events": [_event_row(s, i) for i in live_events(s.events, s.ledger_version)],
                         "reading": "positions and cash are replayed from the live events at the pinned ledger version; nothing is read from a stored balance"},
        "02_current_value": {"as_of": s.as_of, "as_of_note": "the as-of date the subject names; Current mode (D_c(t) over M_t) is available through the service and is not what this pack exercises",
                             "manifest_id": val.manifest.manifest_id, "metric_states": _states(val), "metrics": [mdict(m) for m in val.metrics],
                             "total_reporting": [_headline(m) for m in val.metrics if m.metric_id == "portfolio_value" and m.view == "REPORTING"],
                             "partial_priced_holdings_figure": [_headline(m) for m in val.metrics if m.metric_id == "portfolio_value_priced_holdings"]},
        "03_currencies": currencies,
        "04_price_fx_timestamps": {"per_component": lineage_rows, "data_files": [dict(f) for f in s.files],
                                   "files_cited_by_the_valuation_manifest": [{"kind": r.kind, "consumed": r.consumed} for r in val.manifest.data_set_refs],
                                   "calendar_files_cited": val.manifest.calendar_file_refs, "release_id": val.manifest.release_id},
        "05_historical_fx": {"fx_sources_in_m": [{"source_id": x, "what_it_is": fx_source_label(x)} for x in fx_sources(s)],
                             "rate_for_each_foreign_currency_event_at_its_own_date": _fx_handling(computed),
                             "basis_translation": "the reporting-currency basis of a lot is translated at the fixing of its acquisition date (Ruling 3.7); see section 13 for the lots",
                             "never": "the user's own conversion rate is never used as a rate (ledger-replay 5A.7)"},
        "06_deposits_vs_gains": _bridge(computed),
        "07_internal_transfers": _internal_transfers(computed),
        "08_dividends": _dividends(computed),
        "09_splits": _splits(computed),
        "10_missing_cost_basis": _missing_cost(computed),
        "11_twr": _twr(computed),
        "12_mwr_irr": _mwr(computed),
        "13_realized_unrealized": _gains(computed),
        "14_fx_attribution": _fx_attribution(computed),
        "15_reconciliation_proof": {**_identities(computed), "reproduction": reproduced,
                                    "reproduction_reading": "REPRODUCED = a re-run reproduced the result digest recorded when the number was computed; RESULT_NOT_COMPARED (no expected digest) is never counted as reproduced"},
        "16_tolerances": dict(tolerances(s.perf), market_data_open_items_in_manifests=sorted({i for c in computed.results for i in c.result.manifest.open_items if i.startswith("market_data:")})),
    }
    if s.extra_reporting:  # not a PRD item: the real ECB FX path, shown as reporting views (PD-0035 section 3)
        sections["17_fx_views"] = _fx_views(computed)
    titles = dict(SECTION_FILES, **{"17_fx_views": "Reporting views in other currencies: the FX path (the source is named in each view)"})
    for name, section in sections.items():
        title = titles[name]
        wrapped = section if isinstance(section, dict) else {"rows": section}
        sections[name] = {"section": name, "title": title, "subject": s.name, "kind": s.kind, "labels": labels, "data": wrapped}
    return sections


def _summary(computed: Computed, sections: Dict[str, Any], reproduced: List[Dict[str, Any]], files: Dict[str, str]) -> str:
    s = computed.subject
    labels = _labels(computed)
    val = computed.get(f"valuation@{s.as_of.isoformat()}")
    lines: List[str] = []
    w = lines.append
    w(f"# HG2 evidence pack: {s.name}")
    w("")
    w(f"**Subject kind:** `{s.kind}`. **Pack schema:** `{PACK_SCHEMA}`. **Engine:** `{val.manifest.engine_id}`. **Conventions:** "
      + ", ".join(f"`{v}`" for k, v in val.manifest.conventions if k in ("performance.convention_set", "ledger_replay", "market_data.convention_set")) + ".")
    w("")
    w(f"> **{labels['label']}**")
    w(f"> {labels['demonstration_ledger']}")
    w(f"> {caveat_for(s)}")
    w("")
    w("This pack REPORTS what the engine computed. It derives no expected value and states no judgment; the golden fixtures and their tests are the correctness proof, and the owner decides (HG2).")
    w("")
    w("## Subject")
    w("")
    w(s.description)
    w("")
    w(f"- Reporting currency: **{s.reporting.code}**. As-of date: **{s.as_of.isoformat()}**. Ledger version pinned: **{s.ledger_version}** ({len(s.events)} events).")
    w(f"- Windows: " + ", ".join(f"`{label}`" for label, _ in s.windows) + ".")
    w(f"- Split detection: **{computed.detection}** ({computed.detection_note}).")
    for n in s.notes:
        w(f"- {n}")
    w("")
    if s.operator_selection:
        sel = s.operator_selection
        w("## File set chosen by the operator")
        w("")
        w("The operator named the files of M by sha256 (market-data Ruling 0.1: at most one vintage of a series in M; a human choosing one vintage satisfies it, an automatic choice would not). "
          f"`--exclude-file`: {', '.join(sel.get('exclude', [])) or 'none'}; `--use-file`: {', '.join(sel.get('only', [])) or 'none'}.")
        w("")
        for f in sel.get("files_in_m", []):
            w(f"- in M: `{f['source_id']}` {f['data_kind']} retrieved {f['retrieval_time']} sha256 `{f['file_sha256']}` ({f['payload_filename']})")
        for f in sel.get("named_files", []):
            w(f"- named by `--{f['named_by']}`: `{f['source_id']}` ({f['payload_filename']}) sha256 `{f['file_sha256']}`: " + ("in M" if f["in_m"] else f"NOT in M: {f['reason']}"))
        w("")
    if s.vintage_conflicts:
        w("## Vintage conflicts (M fails closed for these series)")
        w("")
        for c in s.vintage_conflicts:
            w(f"- series {c['series']}: " + "; ".join(f"`{f['source_id']}` retrieved {f['retrieval_time']} sha256 `{f['file_sha256']}`" for f in c["files"]) + ". Neither file is in M; nothing that depends on the series has a number.")
            d = c.get("disagreement")
            if d is not None:
                if not d.get("comparable"):
                    w(f"  - whether the vintages disagree on a shared date could not be established: {d.get('reason')}")
                elif d["shared_dates"] == 0:
                    w("  - the vintages share no (subject, date) point: they cover different dates of one series")
                elif not d["disagree"]:
                    w(f"  - the vintages agree on all {d['shared_dates']} shared points: no shared date disagrees")
                else:
                    w(f"  - the vintages DISAGREE on {len(d['disagree'])} of {d['shared_dates']} shared dates: " + "; ".join(f"{x['subject']} {x['date']}" for x in d["disagree"][:20]))
        w("")
    w("## Current value")
    w("")
    w("| view | value | state | reason | details | why (first cause) | manifest |")
    w("|---|---|---|---|---|---|---|")

    def why(m: Any) -> str:
        if m.result.value is not None or not m.causes:
            return "-"
        return (m.causes[0].note or m.causes[0].ref)[:110].replace("|", "/")

    for m in val.metrics:
        if m.metric_id == "portfolio_value":
            shown = "no value" if m.result.value is None else f"{m.result.value} {m.currency or ''}"
            w(f"| {m.metric_id} {m.view} {dict(m.subject).get('currency', '')} | {shown} | {m.result.sufficiency_state.value} | {m.result.reason_code.value if m.result.reason_code else '-'} | "
              f"{', '.join(m.details) or '-'} | {why(m)} | `{m.manifest_id[:12]}` |")
    partial = [m for m in val.metrics if m.metric_id == "portfolio_value_priced_holdings"]
    for m in partial:
        w(f"| value of priced holdings (partial, never the total) | {m.result.value} | {m.result.sufficiency_state.value} | - | excluded {len(m.excluded)} | - | `{m.manifest_id[:12]}` |")
    w("")
    w("## Returns and gains by window")
    w("")
    w("| window | G | TWR | MWR | attribution (money) | attribution (%) |")
    w("|---|---|---|---|---|---|")

    def cell(m: Any) -> str:
        r = m.result.reason_code.value if m.result.reason_code else ""
        return f"{m.result.value if m.result.value is not None else 'no value'} ({m.result.sufficiency_state.value}{' ' + r if r else ''}{' ' + '/'.join(m.details) if m.details and m.result.value is None else ''})"

    for label, _spec in s.windows:
        win = computed.get(f"window:{label}")
        att = computed.get(f"attribution:{label}")
        pick = lambda r, mid: next(m for m in r.metrics if m.metric_id == mid)  # noqa: E731
        w(f"| {label} | {cell(pick(win, 'gain_absolute'))} | {cell(pick(win, 'return_twr'))} | {cell(pick(win, 'return_mwr'))} | {cell(pick(att, 'attribution_money'))} | {cell(pick(att, 'attribution_return'))} |")
    w("")
    if "17_fx_views" in sections:
        w("## Reporting views in other currencies (the FX path)")
        w("")
        w("The same ledger reported in each currency below, so every value needs an FX rate (a USD ledger reported in USD touches no rate). "
          f"FX source in M: {' and '.join(fx_source_label(x) for x in fx_sources(s)) or 'none (no FX file is admitted)'}.")
        w("")
        w("| reporting currency | route | value | state | why (first cause) | rates asked: outcomes |")
        w("|---|---|---|---|---|---|")
        for view in sections["17_fx_views"]["data"]["views"]:
            total = next((v for v in view["valuation"] if v["view"] == "REPORTING"), None)
            probes = view["rates_asked_of_the_port"]
            outcomes: Dict[str, int] = {}
            for pr in probes:
                outcomes[pr["outcome"].value] = outcomes.get(pr["outcome"].value, 0) + 1
            cause = (total["causes"][0] if total and total["causes"] else "-")[:100].replace("|", "/")
            shown = "no value" if total is None or total["value"] is None else f"{total['value']}"
            w(f"| {view['reporting_currency']} | {view['route'][:60]} | {shown} | {total['state'].value if total else '-'} | {cause} | " + ", ".join(f"{k} x {v}" for k, v in sorted(outcomes.items())) + " |")
        w("")
        w("Each rate's fixing date, fixing instant, source, missed-fixing count and freshness are in `17_fx_views.json`.")
        w("")
    w("## Evidence items (PRD 38.4)")
    w("")
    for name, title in SECTION_FILES:
        w(f"- {title}: `{name}.json`")
    w("")
    w("## Reconciliation proof")
    w("")
    ident = sections["15_reconciliation_proof"]["data"]["identity_status_counts_over_every_metric_carrying_one"]
    w("| identity | status counts |")
    w("|---|---|")
    for k in sorted(ident):
        w(f"| {k} | " + ", ".join(f"{st} x {n}" for st, n in sorted(ident[k].items())) + " |")
    w("")
    failed = sections["15_reconciliation_proof"]["data"]["failed"]
    w(f"Identities that FAILED: **{len(failed)}** (a failure is an engine fault and withholds the number).")
    w("")
    w("## Reproduction (manifest id, expected result digest)")
    w("")
    w("| computation | manifest id | expected digest | re-run |")
    w("|---|---|---|---|")
    for r in reproduced:
        w(f"| {r['key']} | `{r['manifest_id'][:16]}` | `{r['expected_result_digest'][:16]}` | {r['reproduction']} |")
    not_compared = [r for r in reproduced if r["reproduction"] == "RESULT_NOT_COMPARED"]
    w("")
    w(f"Reproduced with a matching digest: **{sum(1 for r in reproduced if r['reproduced'])} of {len(reproduced)}**. `RESULT_NOT_COMPARED` (never counted as reproduced): {len(not_compared)}.")
    w("")
    w("## Known tolerances and open items")
    w("")
    tol = sections["16_tolerances"]["data"]
    for row in tol["table"]:
        w(f"- {row['comparison']}: {row['tolerance']} ({row['basis']})")
    w("")
    w(f"`is_conformant` = **{tol['is_conformant']}**. Open items the convention set still lists:")
    for item in tol["open_items_still_injected"] or ["none"]:
        w(f"- {item}")
    # CP4-4: the conformance flag is the PERFORMANCE set's alone; every manifest in this pack also lists the market-data set's open items (so no result can hide them, tech plan 16.2)
    w("")
    w("Open items of the market-data convention set that every manifest in this pack lists (the `conformant` flag above does not cover them):")
    for item in tol["market_data_open_items_in_manifests"] or ["none"]:
        w(f"- {item}")
    if s.limitations:
        w("")
        w("## Limitations of this pack")
        for item in s.limitations:
            w(f"- {item}")
    if s.requirements:
        w("")
        w("## What this subject still needs (from the owner)")
        for item in s.requirements:
            w(f"- {item}")
    w("")
    w("## Files")
    w("")
    for name, digest in sorted(files.items()):
        w(f"- `{name}` sha256 `{digest[:16]}`")
    w("")
    w(f"Reproduce: `PYTHONPATH=src python -m performance_tools.evidence_pack {'synthetic' if s.kind.startswith('SYNTHETIC') else 'real'} --out <dir>` re-runs every computation and compares every digest.")
    w("")
    return "\n".join(lines)


def build_pack(subject: PackSubject, out_dir: Path) -> Dict[str, Any]:
    """Compute everything, write the JSON files and the Markdown summary under `out_dir`, and return the index (file name -> sha256)."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    computed = run_all(subject)
    reproduced = reproduction(computed)
    sections = build_sections(computed, reproduced)
    files: Dict[str, str] = {}

    def write(name: str, obj: Any) -> None:
        text = dumps(obj)
        (out_dir / name).write_text(text, encoding="utf-8")
        files[name] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    for name, section in sections.items():
        write(f"{name}.json", section)
    write("00_inputs.json", {"subject": subject.name, "kind": subject.kind, "labels": _labels(computed), "portfolio_id": subject.portfolio_id, "reporting_currency": subject.reporting.code,
                             "as_of": subject.as_of, "ledger_version": subject.ledger_version, "windows": [{"label": label, "rule": spec.rule, "months": spec.months, "base": spec.custom_base} for label, spec in subject.windows],
                             "events": [_event_row(subject, i) for i in subject.events], "data_files": [dict(f) for f in subject.files], "detection": computed.detection,
                             "detection_note": computed.detection_note, "notes": list(subject.notes), "limitations": list(subject.limitations), "requirements": list(subject.requirements),
                             "file_set_chosen_by_operator": dict(subject.operator_selection), "vintage_conflicts": [dict(c) for c in subject.vintage_conflicts]})
    write("00_manifests.json", {"labels": _labels(computed), "computations": reproduced,
                                "manifests": {c.key: enc(c.result.manifest.to_canonical_dict()) if hasattr(c.result.manifest, "to_canonical_dict") else enc(c.result.manifest) for c in computed.results}})
    write("00_open_items.json", {"open_items": list(subject.perf.visible_open_items()), "is_conformant": subject.perf.is_conformant, "limitations": list(subject.limitations),
                                 "requirements": list(subject.requirements), "pd_0035_caveat": caveat_for(subject)})
    summary = _summary(computed, sections, reproduced, files)
    (out_dir / "SUMMARY.md").write_text(summary, encoding="utf-8")
    files["SUMMARY.md"] = hashlib.sha256(summary.encode("utf-8")).hexdigest()
    return {"files": files, "computed": computed, "reproduced": reproduced}
