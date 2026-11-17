"""Test V2 (market-data/1.1 §3, Ruling 2.3): the affine fit that ESTABLISHES an adjusted series'
method. Verification only: nothing here yields a price, and nothing here is imported by the
analytics consumer (an import-boundary test enforces it).

    adj_t = a x ref_t - b            within each interval between known ex-dates

(a) Fit each interval, exactly in rationals, from the two rows with the smallest and largest
    reference close; every row and every price field (open, high, low, close) must satisfy it
    within the propagated bound `delta_adj + |a| x delta_ref`. A row that breaks it makes the
    interval, and the label, CONTRADICTED with method UNKNOWN.
(b) Classify from all intervals: b = 0, a != 1 -> PROPORTIONAL; b != 0 -> SUBTRACTIVE; every
    interval a = 1, b = 0 -> IDENTITY (method UNKNOWN: unverifiable here); proportional in some
    intervals and subtractive in others -> CONTRADICTED.
(c) Event check, ONLY where confirmed corporate actions are supplied: each fitted interval's
    (a, b) must equal the composition of the event maps of every event with ex-date after the
    interval (up to the vintage), under the classified method. With none supplied the result
    is UNVERIFIABLE (the method may still be established by (a)-(b)).

THE BOUND (market-data/1.2 Test V2 (a')): it is DERIVED from the two series' precision profiles, never a
caller input and never a function of the market's `max_dp`. Each row carries its own bound `delta`
(`PriceRow.bound`): 0 for a recovered raw close, half a unit of the decimals the source DELIVERS for
adjusted values (profile field `adjusted_dp`) for an adjusted row. With `delta_r`, `delta_j` the
reference and adjusted bounds of row i, `e_i = delta_j + |a| x delta_r`, anchors lo and hi and
`Delta = ref_hi - ref_lo`:

    residual test:  |adj_i - (a x ref_i - b)| <= e_i + max(e_lo, e_hi)       (every row, every price field)
    a != 1  only if |a - 1| > u_a = (e_lo + e_hi) / Delta
    b != 0  only if |b| > u_b = e_lo + |ref_lo| x u_a

Example 3-C: delta_r = 0, delta_j = 0.005, e = 0.005, Delta = 48, u_a = 0.01/48, u_b = 0.005 + 1240 x
u_a ≈ 0.263 (the Quant's figure, for the public copy's invented values). 1.3 (section 9B #2): delta_r is PER FIELD from that field's own profile:
a recovered close is 0; open, high and low (never grid-checked) are half a unit of the DECLARED delivered decimals
for a text or float64 field and half an ulp for a float32 field (`PriceRow.field_bounds`; the close's 0 is NOT
copied to them). 1.4 (C2-10): a text or float64 field with no declared `delivered_dp` has no bound at all and V2
does not run on the series (PROFILE_INCOMPLETE, see `ingest._run_v2`); half an ulp of binary64 is not a substitute.
Nothing is rounded. The 3-C real-file arithmetic is only ever reproduced here on synthetic
copies.

Test V0 (calendar alignment, Ruling 3.1) is `verify_v0`: a pure function over a series' session dates
and the calendars of M.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction
from typing import Dict, List, Mapping, Optional, Protocol, Sequence, Tuple

from marketdata.calendars import CalendarSet
from marketdata.contracts import (
    AdjustedQuote,
    AdjustmentLabel,
    AdjustmentMethod,
    AdjustmentStatus,
    AnchorKind,
    LabelStatus,
)


@dataclass(frozen=True)
class PriceRow:
    """One daily row. `bound` is the precision bound `delta` of the row's price values as its series
    delivers them (Ruling 4.2; V2 (a')): 0 for a recovered raw close, half a unit of `adjusted_dp` for
    an adjusted row. It comes from the series' profile, not from the caller of the test."""

    date: datetime.date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    bound: Fraction = Fraction(0)
    # market-data/1.3 V2 (a'): delta_r is PER FIELD. `bound` is the CLOSE's bound; when `field_bounds` (the
    # bounds of open, high, low) is given, those three are used for the three fields instead of copying the
    # close's bound to them (a recovered close is 0; open/high/low are never grid-validated).
    field_bounds: Optional[Tuple[Fraction, Fraction, Fraction]] = None

    def bounds(self) -> Tuple[Fraction, Fraction, Fraction, Fraction]:
        """(open, high, low, close) bounds, in the order of `_fields`."""
        if self.field_bounds is None:
            return (self.bound, self.bound, self.bound, self.bound)
        o, h, low = self.field_bounds
        return (o, h, low, self.bound)


@dataclass(frozen=True)
class CorporateEvent:
    """A CONFIRMED corporate action: ex-date, cash per pre-event share, share ratio (n, o), and
    the last close before the ex-date (needed for the proportional factor 1 - d/P_prev)."""

    ex_date: datetime.date
    cash: Decimal = Decimal(0)
    n: Decimal = Decimal(1)
    o: Decimal = Decimal(1)
    p_prev: Optional[Decimal] = None


@dataclass(frozen=True)
class IntervalFit:
    first: datetime.date
    last: datetime.date
    a: Fraction
    b: Fraction
    bound_a: Fraction
    bound_b: Fraction
    kind: str  # IDENTITY, PROPORTIONAL, SUBTRACTIVE


@dataclass(frozen=True)
class V2Result:
    method: AdjustmentMethod
    status: LabelStatus
    anchor: Optional[AnchorKind]
    fits: Tuple[IntervalFit, ...]
    reason: str


class VerificationPort(Protocol):
    """Reads of verification-only data. Separate from `MarketDataPort`: analytics never uses it."""

    def adjusted_series(self, listing_id: uuid.UUID) -> Tuple[AdjustedQuote, ...]: ...


def _fields(row: PriceRow) -> Tuple[Decimal, ...]:
    return (row.open, row.high, row.low, row.close)


def _split_intervals(dates: Sequence[datetime.date], boundaries: Sequence[datetime.date]) -> List[List[int]]:
    """Index groups: a row belongs to the interval after the latest boundary <= its date."""
    cuts = sorted(set(boundaries))
    groups: Dict[int, List[int]] = {}
    for i, d in enumerate(dates):
        k = sum(1 for c in cuts if c <= d)
        groups.setdefault(k, []).append(i)
    return [groups[k] for k in sorted(groups)]


def verify_adjustment_v2(
    reference: Sequence[PriceRow],
    adjusted: Sequence[PriceRow],
    events: Sequence[CorporateEvent],
    vintage: datetime.date,
) -> V2Result:
    ref_by_date = {r.date: r for r in reference}
    pairs = [(ref_by_date[a.date], a) for a in sorted(adjusted, key=lambda r: r.date) if a.date in ref_by_date]
    if not pairs:
        return V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, (), "no common dates")
    dates = [p[0].date for p in pairs]
    ev = sorted(events, key=lambda e: e.ex_date)
    groups = _split_intervals(dates, [e.ex_date for e in ev])

    fits: List[IntervalFit] = []
    for idx in groups:
        rows = [pairs[i] for i in idx]
        closes = {r.close for r, _ in rows}
        if len(closes) < 2:
            continue  # not fittable: fewer than two distinct reference values
        lo = min(rows, key=lambda p: p[0].close)
        hi = max(rows, key=lambda p: p[0].close)
        ref_lo, ref_hi = Fraction(lo[0].close), Fraction(hi[0].close)
        a = (Fraction(hi[1].close) - Fraction(lo[1].close)) / (ref_hi - ref_lo)
        b = a * ref_hi - Fraction(hi[1].close)
        delta = ref_hi - ref_lo

        def e_of(pair: Tuple[PriceRow, PriceRow], index: int = 3) -> Fraction:  # e_i = delta_j + |a| x delta_r
            # index 3 is the close: the anchors are chosen by, and fitted on, the reference close
            return Fraction(pair[1].bounds()[index]) + abs(a) * Fraction(pair[0].bounds()[index])

        e_lo, e_hi = e_of(lo), e_of(hi)
        anchor_error = max(e_lo, e_hi)
        for ref, adj in rows:
            for index, (rf, af) in enumerate(zip(_fields(ref), _fields(adj))):
                # residual test: e_i + max(e_lo, e_hi), with e_i taken from THAT field's own bounds (1.3)
                allowed = e_of((ref, adj), index) + anchor_error
                if abs(Fraction(af) - (a * Fraction(rf) - b)) > allowed:
                    return V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.CONTRADICTED, None, tuple(fits),
                                    f"{ref.date}: the relation is not affine in its interval")
        bound_a = (e_lo + e_hi) / delta  # u_a
        bound_b = e_lo + abs(ref_lo) * bound_a  # u_b
        a_is_one = abs(a - 1) <= bound_a
        b_is_zero = abs(b) <= bound_b
        kind = "IDENTITY" if (a_is_one and b_is_zero) else ("PROPORTIONAL" if b_is_zero else "SUBTRACTIVE")
        fits.append(IntervalFit(rows[0][0].date, rows[-1][0].date, a, b, bound_a, bound_b, kind))

    if not fits:
        return V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, (),
                        "no interval has two distinct reference values")
    kinds = {f.kind for f in fits}
    if {"PROPORTIONAL", "SUBTRACTIVE"} <= kinds:
        return V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.CONTRADICTED, None, tuple(fits),
                        "proportional in some intervals and subtractive in others")
    if "SUBTRACTIVE" in kinds:
        method = AdjustmentMethod.SUBTRACTIVE
    elif "PROPORTIONAL" in kinds:
        method = AdjustmentMethod.PROPORTIONAL
    else:
        return V2Result(AdjustmentMethod.UNKNOWN, LabelStatus.UNVERIFIABLE, None, tuple(fits),
                        "IDENTITY: no adjustment in this window; the method is unverifiable here")

    applicable = [e for e in ev if e.ex_date <= vintage]
    if not applicable:
        return V2Result(method, LabelStatus.UNVERIFIABLE, None, tuple(fits),
                        "no confirmed corporate actions: the event check cannot run")

    for fit in fits:
        after = [e for e in applicable if e.ex_date > fit.last]
        a_exp, b_exp = Fraction(1), Fraction(0)
        for e in sorted(after, key=lambda e: e.ex_date, reverse=True):  # latest first
            ratio = Fraction(e.o) / Fraction(e.n)
            if method is AdjustmentMethod.PROPORTIONAL:
                if e.p_prev is None:
                    return V2Result(method, LabelStatus.UNVERIFIABLE, None, tuple(fits),
                                    f"{e.ex_date}: P_prev is needed for the proportional factor")
                a_exp = a_exp * (1 - Fraction(e.cash) / Fraction(e.p_prev)) * ratio
            else:
                b_exp = b_exp + a_exp * ratio * Fraction(e.cash)
                a_exp = a_exp * ratio
        if abs(fit.a - a_exp) > fit.bound_a or abs(fit.b - b_exp) > fit.bound_b:
            return V2Result(method, LabelStatus.CONTRADICTED, None, tuple(fits),
                            f"interval {fit.first}..{fit.last}: (a, b) does not match the event maps")
    return V2Result(method, LabelStatus.VERIFIED, AnchorKind.LATEST, tuple(fits),
                    "every interval matches the composition of the confirmed events (anchor LATEST)")


def apply_v2(label: AdjustmentLabel, result: V2Result) -> AdjustmentLabel:
    """The label after V2: the METHOD and the verified ANCHOR come only from the test."""
    status = label.adjustment_status
    if result.method is AdjustmentMethod.SUBTRACTIVE:
        status = AdjustmentStatus.DIVIDEND_ADJUSTED  # b != 0 can only come from cash
    return AdjustmentLabel(status, result.method, result.anchor, label.vintage)


@dataclass(frozen=True)
class ProvenanceResult:
    """Ruling 1.1a item 3: the verdict on a re-server's DECLARED upstream, from one exact comparison."""

    status: str  # CONFIRMED | REFUTED | UNCONFIRMED
    window: Optional[Tuple[datetime.date, datetime.date]]
    confirmed_dates: Tuple[datetime.date, ...]  # dates of the declared file the check confirmed
    reason: str


FileWindow = Tuple[Optional[datetime.date], Optional[datetime.date]]  # (start, end); see `check_provenance`


def _coverage(window: Optional[FileWindow], held: "set[datetime.date]") -> Optional[Tuple[datetime.date, datetime.date]]:
    """Ruling 1.1a item 5 (1.3): a file's coverage of one currency, `[start, end]`. `start` is the window's
    start, or the first date held for the currency when it is None (a full-history file); `end` is the
    window's end. None when the end is unknown: the coverage cannot be stated. It is never the first and last
    date held, which would hide a missing edge date."""
    if window is None or window[1] is None or not held:
        return None
    return (window[0] if window[0] is not None else min(held), window[1])


def check_provenance(
    declared: Mapping[Tuple[datetime.date, str], Decimal],
    direct: Mapping[Tuple[datetime.date, str], Decimal],
    declared_window: Optional[FileWindow] = None,
    direct_window: Optional[FileWindow] = None,
) -> ProvenanceResult:
    """Ruling 1.1a item 3, one deterministic check, with the coverage of item 5 (1.3). `declared` and `direct`
    map (date, currency) to the published rate of a re-server file and of the publisher's own file;
    `declared_window` / `direct_window` are the files' `(start, end)` (see `_coverage`; the build path derives
    them from the manifest's request and the retrieval time).

    VALUE part: every (date, currency) both files hold must be EQUAL as a decimal (trailing zeros ignored).
    DATE-SET part: inside the OVERLAP of the two files' COVERAGES (per currency) the set of dates present must be
    the same, so a date missing from a file's edge is seen. Where a coverage cannot be stated (no window, or no
    end) the date-set part is UNVERIFIABLE: it does not run, and nothing is CONFIRMED beyond what it verified.
    Any difference -> REFUTED for the whole declared file; both parts hold on a non-empty verified overlap ->
    CONFIRMED for the declared file's dates inside it; otherwise UNCONFIRMED."""
    currencies = {c for _, c in declared} & {c for _, c in direct}
    if not currencies:
        return ProvenanceResult("UNCONFIRMED", None, (), "no currency in common")
    # every difference is listed, not only the first: the evidence of a refutation must be reproducible
    # (Ruling 1.1a item 6: the file stays in M, flagged REFUTED with the differing (date, currency) list)
    value_diffs = [f"{day.isoformat()}/{ccy}" for (day, ccy), rate in sorted(declared.items())
                   if ccy in currencies and (day, ccy) in direct and rate != direct[(day, ccy)]]
    confirmed: List[datetime.date] = []
    spans: List[Tuple[datetime.date, datetime.date]] = []
    date_diffs: List[str] = []
    for ccy in sorted(currencies):
        d_held = {d for d, c in declared if c == ccy}
        e_held = {d for d, c in direct if c == ccy}
        d_cov, e_cov = _coverage(declared_window, d_held), _coverage(direct_window, e_held)
        if d_cov is None or e_cov is None:
            continue  # UNVERIFIABLE for this currency
        low, high = max(d_cov[0], e_cov[0]), min(d_cov[1], e_cov[1])
        if low > high:
            continue
        d_in = {d for d in d_held if low <= d <= high}
        e_in = {d for d in e_held if low <= d <= high}
        if d_in != e_in:
            date_diffs += [f"{d.isoformat()}/{ccy}" for d in sorted(d_in ^ e_in)]
            continue
        spans.append((low, high))
        confirmed += sorted(d_in)
    if value_diffs or date_diffs:
        parts = []
        if value_diffs:
            parts.append("value differs: " + ", ".join(value_diffs))
        if date_diffs:
            parts.append("date present in one file only, inside both coverages: " + ", ".join(date_diffs))
        return ProvenanceResult("REFUTED", None, (), "; ".join(parts))
    if not spans:
        return ProvenanceResult("UNCONFIRMED", None, (), "no overlap of the two files' coverages could be verified")
    return ProvenanceResult("CONFIRMED", (min(s[0] for s in spans), max(s[1] for s in spans)),
                            tuple(sorted(set(confirmed))), "equal on the whole verified overlap")


@dataclass(frozen=True)
class V0Result:
    status: LabelStatus
    off_calendar: Tuple[datetime.date, ...]  # series dates inside the coverage that are not sessions
    uncovered: Tuple[datetime.date, ...]  # series dates outside the coverage: UNVERIFIABLE for that part
    reason: str


def verify_v0(session_dates: Sequence[datetime.date], calendars: CalendarSet, mic: Optional[str]) -> V0Result:
    """Test V0, calendar alignment (Ruling 3.1): every session date of a series must be a session of
    the calendar governing its MIC. Any date inside the coverage that is not listed makes the series
    CONTRADICTED (the signature of a UTC date shift: every row on a Sunday). A date outside the coverage
    cannot be judged (UNVERIFIABLE for that part: Ruling 5.3). No weekday is ever inferred."""
    calendar, problem = calendars.governing(mic)
    if calendar is None:
        return V0Result(LabelStatus.UNVERIFIABLE, (), tuple(sorted(set(session_dates))),
                        f"CALENDAR_COVERAGE_GAP: {problem}")
    off: List[datetime.date] = []
    uncovered: List[datetime.date] = []
    for day in sorted(set(session_dates)):
        verdict = calendars.is_session(mic, day)
        if verdict is None:
            uncovered.append(day)
        elif not verdict:
            off.append(day)
    if off:
        return V0Result(LabelStatus.CONTRADICTED, tuple(off), tuple(uncovered),
                        f"{len(off)} date(s) are not sessions of {calendar.calendar_id}: "
                        + ", ".join(d.isoformat() for d in off))  # the dates are named (Example 7A-G2 (c): lineage names V0 and the date)
    if uncovered:
        return V0Result(LabelStatus.UNVERIFIABLE, (), tuple(uncovered),
                        f"{len(uncovered)} date(s) lie outside the coverage of {calendar.calendar_id}")
    return V0Result(LabelStatus.VERIFIED, (), (), "every date is a listed session")
