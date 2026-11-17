"""Two-source reconciliation (market-data/1.2 Rulings 4.1-4.4, 4.1a, 4.6, 4.8, 4.2 bound, Appendix A.5).

market-data/1.2 additions: a non-RAW reading is left out of the reading set with a note (4.1a); an
unrecovered single reading has NO status (2.4 item 4a); synthetic readings are never reconciled with
real ones (4.8); within one upstream, agreement is SINGLE_SOURCE and disagreement is DISAGREEMENT
(4.3, already the behaviour).

- INDEPENDENCE is by UPSTREAM (the reading's `independence_group`), not by library: two upstreams
  reached through one library are independent; two functions reaching one upstream are not.
- AGREEMENT: |a - b| <= delta_a + delta_b, where delta is the reading's precision bound: 0 for a
  recovered value (so two recovered closes must be EQUAL), half an ulp for one that is not.
  No other tolerance exists. A value that is not recovered may corroborate; it is never the
  value used.
- STATUS (Ruling 4.3): CORROBORATED (>= 2 independent upstreams agree, safeguards pass),
  SINGLE_SOURCE (one upstream; or the 4.6 safeguards fail for a same-library pair, which is
  flagged), DISAGREEMENT (any pair beyond its bound: NO value used, never settled by order,
  recency, majority or average). IMPLAUSIBLE and RESOLVED_BY_EVIDENCE are not produced here
  (bands of Ruling 1.5 and human resolution records are a later increment).
- PRIMARY ORDER (A.5, data in `marketdata.profiles`) decides only which of several AGREEING
  recovered values is carried. With recovered values that agree it never changes a number.
- RULING 4.6 for a pair sharing a library: different library functions, neither side's
  within-source check failed, and the library version recorded on both sides.
"""

from __future__ import annotations

from decimal import Context, Decimal, Inexact
from itertools import combinations
from typing import Dict, List, Mapping, Optional, Tuple

from marketdata.contracts import (
    AdjustmentStatus,
    CorporateActionObservation,
    CorporateActionType,
    FieldDifference,
    FXObservation,
    QuoteObservation,
    Reconciliation,
    ReconciliationStatus,
    SourceReading,
)
from marketdata.profiles import PRIMARY_ORDER, SOURCES

RULE_ID = "market-data/1.16#4.1-4.8"
TOLERANCE_REF = "market-data/1.16#4.2"
UNRECOVERED_AGREE = "UNRECOVERED_READINGS_AGREE"  # lineage only (Ruling 2.4 item 4a, 1.3); no state effect
_EXACT = Context(prec=400, traps=[Inexact])


def value_fields(obs: object) -> Dict[str, Decimal]:
    if isinstance(obs, QuoteObservation):
        return {"price": obs.price}
    if isinstance(obs, FXObservation):
        return {"rate": obs.rate}
    if isinstance(obs, CorporateActionObservation):
        if obs.action_type is CorporateActionType.SPLIT:
            assert obs.split_ratio is not None
            return {"new_units": obs.split_ratio.new_units, "old_units": obs.split_ratio.old_units}
        if obs.action_type is CorporateActionType.CASH_DIVIDEND:
            assert obs.amount_per_unit is not None
            return {"amount_per_unit": obs.amount_per_unit.amount}
        return {}
    raise TypeError(type(obs).__name__)


def exact_differences(readings: Tuple[SourceReading, ...]) -> Tuple[FieldDifference, ...]:
    """Exact per-field spread across ALL readings (no tolerance, no rounding)."""
    if len(readings) < 2:
        return ()
    per_field: Dict[str, Dict[str, Decimal]] = {}
    for r in readings:
        try:
            fields = value_fields(r.observation)
        except TypeError:
            return ()
        for name, value in fields.items():
            per_field.setdefault(name, {})[r.source_id + "#" + r.file_sha256[:12]] = value
    out = []
    for name in sorted(per_field):
        by_source = tuple(sorted(per_field[name].items()))
        values = [v for _, v in by_source]
        try:
            spread: Optional[Decimal] = _EXACT.subtract(max(values), min(values))
        except Inexact:
            spread = None
        out.append(FieldDifference(name, by_source, spread))
    return tuple(out)


def _bound(reading: SourceReading) -> Decimal:
    return getattr(reading.observation, "precision_bound", Decimal(0))


def _agree(a: SourceReading, b: SourceReading) -> bool:
    fa, fb = value_fields(a.observation), value_fields(b.observation)
    if fa.keys() != fb.keys():
        return False
    bound = _bound(a) + _bound(b)
    if not all(abs(fa[k] - fb[k]) <= bound for k in fa):
        return False
    # Ruling 4.5 (1.14): the issuer's stated payment is compared ONLY when both sides state one (a one-sided statement is a single-source addition, never a disagreement)
    paid_a, paid_b = _paid(a.observation), _paid(b.observation)
    return paid_a is None or paid_b is None or paid_a == paid_b


def _paid(obs: object):  # type: ignore[no-untyped-def]
    amount = getattr(obs, "paid_amount", None)
    return None if amount is None else (obs.paid_currency, amount)  # type: ignore[attr-defined]


def _lineage(reading: SourceReading):  # type: ignore[no-untyped-def]
    return reading.observation.lineage  # type: ignore[attr-defined]


def _shared_library_failures(a: SourceReading, b: SourceReading) -> List[str]:
    """Ruling 4.6 for a pair whose two sides came through the same library."""
    la, lb = _lineage(a), _lineage(b)
    if la.library is None or la.library != lb.library:
        return []
    failures = []
    if la.library_function is None or lb.library_function is None or la.library_function == lb.library_function:
        failures.append(f"4.6(1): both sides used one {la.library} function ({la.library_function})")
    for side, lin in (("a", la), ("b", lb)):
        if lin.consistency_checks_passed is False:
            failures.append(f"4.6(3): the within-source arithmetic check failed on side {side}")
        if lin.library_version is None:
            failures.append(f"4.6(4): library version not recorded on side {side}")
    return failures


class Market11Reconciler:
    rule_id = RULE_ID

    def __init__(self, primary_order: Mapping[str, Tuple[str, ...]] = PRIMARY_ORDER):
        self._order = dict(primary_order)

    def _sorted(self, readings: Tuple[SourceReading, ...]) -> Tuple[SourceReading, ...]:
        markets = {_lineage(r).market for r in readings}
        market = next(iter(markets)) if len(markets) == 1 else None
        order = self._order.get("FX" if isinstance(readings[0].observation, FXObservation) else market or "", ())

        def rank(item: Tuple[int, SourceReading]) -> Tuple[int, int, int]:
            group = item[1].independence_group
            profile = SOURCES.get(item[1].source_id)
            # A.5: within one upstream the publisher's own file (ecb.eurofxref) comes before a re-server
            direct = 0 if (profile is not None and profile.role == "PREFERRED_FX") else 1
            return (order.index(group) if group in order else len(order), direct, item[0])

        return tuple(r for _, r in sorted(enumerate(readings), key=rank))

    def reconcile(self, readings: Tuple[SourceReading, ...]) -> Reconciliation:
        flags: List[str] = []
        original = self._sorted(readings)
        working = original
        # Ruling 4.8: synthetic data is its own upstream and never meets real data, in either direction:
        # when both are present, only the real readings are reconciled (a synthetic one neither
        # corroborates nor is corroborated, and never resolves a disagreement).
        real = tuple(r for r in working if not _lineage(r).is_synthetic)
        if real and len(real) != len(working):
            flags.append(f"4.8: {len(working) - len(real)} synthetic reading(s) excluded: synthetic data never "
                         "meets real data")
            working = real
        # Ruling 4.1a: only RAW readings (in the listing's trading currency, which ingest enforces) are
        # comparable; a non-RAW reading that is not exactly un-adjustable has no status and no effect.
        if isinstance(working[0].observation, QuoteObservation):
            raw = tuple(r for r in working if r.observation.lineage.adjustment_status  # type: ignore[attr-defined]
                        is AdjustmentStatus.RAW)
            if len(raw) != len(working):
                flags.append(f"4.1a: {len(working) - len(raw)} non-RAW reading(s) left out of the reading set: "
                             "not comparable (cannot be exactly un-adjusted)")
                working = raw
        ordered = working or original
        differences = exact_differences(ordered)

        def result(status: Optional[ReconciliationStatus], used: Optional[SourceReading], basis: str) -> Reconciliation:
            return Reconciliation(
                status, ordered, differences, self.rule_id, TOLERANCE_REF,
                selected_source=None if used is None else used.source_id,
                selection_basis=basis if used is not None else "", flags=tuple(flags), used=used)

        if not working:
            return result(None, None, "")
        if isinstance(ordered[0].observation, QuoteObservation) and len(
                {r.observation.currency for r in ordered}) > 1:  # type: ignore[attr-defined]
            flags.append("NOT_COMPARABLE: readings differ in currency (refused at ingest; defensive guard)")
            return result(None, None, "")
        groups = []
        for r in ordered:
            if r.independence_group not in groups:
                groups.append(r.independence_group)

        disagreeing = [(a, b) for a, b in combinations(ordered, 2) if not _agree(a, b)]
        if disagreeing:
            flags.append(f"{len(disagreeing)} pair(s) differ beyond the Ruling 4.2 bound")
            return result(ReconciliationStatus.DISAGREEMENT, None, "")

        def first_usable() -> Optional[SourceReading]:
            for r in ordered:
                # Ruling 1.1a item 6 (1.3): a REFUTED re-server file supplies NO rate on any date. It stays in
                # the comparison (a difference from the ECB's own value is a DISAGREEMENT), never the value used.
                if _lineage(r).provenance == "REFUTED":
                    continue
                if getattr(r.observation, "recovered", True):
                    return r
            return None

        used = first_usable()
        basis = "primary order among agreeing recovered values (Ruling 4.3)"
        if used is None:
            # Ruling 2.4 item 4a (1.3 clarification): readings that are all unrecovered are not an admissible
            # print however many agree: there is no value and NO reconciliation status (CORROBORATED means a
            # value is used; SINGLE_SOURCE likewise). Agreement is only a lineage flag, with no state effect.
            if any(_lineage(r).provenance == "REFUTED" for r in ordered):
                flags.append("REFUTED_PROVENANCE: every reading is from a refuted file: no rate (Ruling 1.1a item 6)")
            else:
                flags.append("no recovered value: corroboration only, no value used (Ruling 2.4 item 4)")
            if len(ordered) >= 2:
                flags.append(UNRECOVERED_AGREE)  # we are past the disagreement check: they agree within their bounds
            return result(None, None, "")
        if len(groups) == 1:
            return result(ReconciliationStatus.SINGLE_SOURCE, used, "the only upstream reporting")
        cross = [(a, b) for a, b in combinations(ordered, 2) if a.independence_group != b.independence_group]
        failures = [f for a, b in cross for f in _shared_library_failures(a, b)]
        if failures:
            flags.extend(sorted(set(failures)))
            return result(ReconciliationStatus.SINGLE_SOURCE, used, "Ruling 4.6 safeguards not met: counted as one source")
        return result(ReconciliationStatus.CORROBORATED, used, basis)
