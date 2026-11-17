"""The market-data/1.4 rules for freshness, price of date and FX, built over the calendar files of M.

(1.4 changes in this module: a print or fixing dated the as-of date is CURRENT only when ONE calendar governs and
covers that date (C2-1); a date held only by a REFUTED re-server file is tested by the date-set check and is
not carried forward over (C2-9, Ruling 1.1a item 6).)

(1.3 changes in this module: the date-set check of Ruling 1.1a item 4 runs inside each file's COVERAGE as
Ruling 1.1a item 5 defines it, never inside the dates the file happens to hold; a REFUTED re-server file
supplies no rate (item 6); the central-parity check does not run in product paths and says so in lineage,
PARITY_CHECK_NOT_RUN (Ruling 1.5a); and the lookup outcomes keep their causes apart, section 9B.)

Nothing here is a method the engineer chose; each rule is a transcription of a RULING, and where a
ruling gives a number, the number is a named constant with its ruling beside it:

FRESHNESS (Ruling 5.2; Ruling 1.6 for FX). The count is the number of sessions (or fixing days) `d`
of the governing calendar with `last_print < d <= D`. 0 -> CURRENT; 1 -> STALE; 2..4 -> STALE;
5 or more -> STALE and the number is WITHHELD. A count that cannot be made (the calendar does not
govern the MIC exactly once, or does not cover the whole interval) is UNKNOWN and the number is
WITHHELD, with the lineage cause CALENDAR_COVERAGE_GAP (Ruling 5.3): weekdays are never inferred.
An empty interval (the print is dated D) still needs the calendar: one governing calendar whose coverage contains D
and that lists D (C2-1; Rulings 5.3, 1.6, 5.2). The sufficiency states that go with the
counts (AVAILABLE / LIMITED / INSUFFICIENT_DATA and the reason codes) are mapped in `states.py`,
the only module that names a reason code.

PRICE OF DATE (Rulings 2.1, 2.2, 2.4 item 4a). The price for D is the latest ADMISSIBLE print on or
before D: a RAW reading with volume > 0 (print rule) that is RECOVERED (an unrecovered reading is not
an admissible print: it may confirm another source's recovered value, supplies no price on its own,
and its session counts as missed). The session date is the source's local date label (the reading's
`value_date`; nothing is converted through UTC). There is no sibling-listing substitution: only the
listing's own readings are ever passed in. No admissible print on or before D: NO_HISTORY.

FX (Rulings 1.1, 1.3, 1.4, 1.5, 1.6, 1.1a). Quotes are EUR-based, as published. A cross is the exact
ratio of two SAME-DATE legs `x_q / x_b` held as two linked observations (`ExactRatioRate`); a rate
whose base (or quote) is EUR is the published quote (or its labelled exact inverse). The date used is
the latest date on which every leg exists; the missed fixings are counted from it (freshness). CNH is
strict: never translated, never replaced by the CNY rate (PD-0030). The HKD peg band 7.75..7.85 and the
CNY +-2 % band around the central parity are plausibility checks that run only where their data exist;
with no central-parity series the CNY check is UNVERIFIABLE and is never fabricated. A leg whose two
readings from one upstream (the ECB file and its re-server) differ, or one of which is absent on a date
inside both files' coverage, is a DISAGREEMENT (Ruling 1.1a item 4); each leg is reconciled alone.

Pure: no clock, no randomness, no network, no file access.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from fractions import Fraction
from typing import Callable, List, Mapping, Optional, Tuple

import dataclasses

from domain.currency import CurrencyCode
from marketdata.calendars import OFF_CALENDAR, CalendarSet
from marketdata.conventions import (
    ConventionSet,
    FreshnessAssessment,
    FXOutcome,
    FXSelection,
    History,
    Selection,
    Withhold,
)
from marketdata.contracts import (
    AdjustmentStatus,
    ExactRatioRate,
    Freshness,
    FreshnessState,
    FXObservation,
    QuoteObservation,
    Reconciliation,
    ReconciliationStatus,
    SourceReading,
    SourceTiming,
)
from marketdata.profiles import ECB_CALENDAR_ID
from marketdata.reconciliation import Market11Reconciler

FRESHNESS_ID = "market-data/1.16#5.2"
PRICE_OF_DATE_ID = "market-data/1.16#2.1-2.4a"
FX_ID = "market-data/1.16#1.1-1.6"

# Ruling 5.2 / Ruling 1.6: the count thresholds. 1 missed -> AVAILABLE + STALE_DATA; 2..4 -> LIMITED +
# STALE_DATA; 5 or more -> INSUFFICIENT_DATA (and the number is withheld).
LIMITED_FROM = 2
NO_VALUE_FROM = 5

# Ruling 1.5: the HKD linked-exchange-rate band (HKD per USD) and the onshore band around the central parity.
HKD_PEG_LOW = Fraction(775, 100)
HKD_PEG_HIGH = Fraction(785, 100)
CNY_BAND = Fraction(2, 100)

EUR = CurrencyCode("EUR")
USD = CurrencyCode("USD")

PARITY_NOT_RUN = ("PARITY_CHECK_NOT_RUN: no central-parity source is admitted, so the CNY band "
                  "check did not run (Ruling 1.5a); no state effect")

# What this increment does not build, listed so no result can hide it (market-data/1.4 section 11).
UNBUILT = (
    "not built: Test V1 (split-day jump) and Test V3 (cross-source factor): they need corroborated corporate actions",
    "not built: human resolution records (RESOLVED_BY_EVIDENCE) as inputs of M",
    "not built: a central-parity series, so the CNY band check is UNVERIFIABLE (no source is admitted)",
    "not built: a real corporate-action FEED adapter and an issuer-FILING adapter (no input exists for F8-B in production)",
)

# The code label moved to market-data/1.15 (PD-0067 decision 6) and then to market-data/1.16 (the F1 R4a label increment) before the engine behaviours
# of section 11 items 17 to 20, 29 and 30 were built, so a manifest that cites 1.16 must say which of them it does not run (P9, section 21: an auditor
# re-deriving a result from the cited text must be able to tell a build gap from a pass; section 11 "When a manifest may cite 1.16", point 2). One line per
# behaviour, kept apart from UNBUILT so the CP4 count of that tuple stands. Items 21 (the A-share route and its not-admitted gate) and 22 (Ruling 6.5 item 4,
# `test_marketdata_r4a_inputs.ConfirmationPolicyWithNoCorporateActionFileTests.test_7`) are built, so they have no line; the profile line from
# `visible_open_items()` says the A-share route is TO_OBSERVE. The last line is the Quant's answer (d) of 2026-10-25 (a text defect carried to the next version).
# No vendor is named here (this module is vendor-free, tested by test_marketdata_cp2c2_exit): the Rulings are cited, and they name the vendor.
# `tests/product/test_marketdata_version_label.py` fails when one of the first five behaviours appears in src/ while its line is still here.
UNBUILT_1_16 = (
    "not built: market-data/1.16 Ruling 3.2 item 4 with Test V1, in its 1.16 form (the synthetic-world V1 events of item 1, the coverage clause of item 3, "
    "and clearing by Test V4 only where Ruling 3.3 establishes RAW): the split-label exposure rule. No close is withheld (INSUFFICIENT_DATA, "
    "MISSING_PRICE_HISTORY, SPLIT_LABEL_EXPOSED) when a filing-attested split has its ex-date in E(d_p, R) and the file's RAW label is not "
    "established. Until it is built, Ruling 3.2 item 6 applies: a real-data computation is not run if M holds a filing-role SPLIT with X in "
    "E(d_p, R). That check is made by hand before the run, and this manifest does not record that it was made or what it found",
    "not built: market-data/1.16 Ruling 3.2 item 5: the lineage of a valuation does not state, for each RAW reading used, its label status "
    "and label source (they are held only in the reading's own ingest lineage), E(d_p, R) as a date list, or the item 5 statement of V1 events in "
    "its three cases (found in E; none in E; none in M); DIVIDEND_LABEL_EXPOSED is not raised",
    "not built: market-data/1.16 Ruling 3.3, Test V4, in its 1.16 form: no human-recorded exchange close is an input of M, so no RAW label is "
    "established by it; the window (d, N(R)] and the consolidation condition are not applied",
    "not built: market-data/1.16 Ruling 4.5 (1.15): a split ratio delivered as a decimal factor is not compared with the filing's exact ratio",
    "not built: market-data/1.16 Rulings 7.4 and 7.5: no adapter for a corporate-action feed whose fields have no granted meaning "
    "(UNMAPPED_ACTION for every record, the UNMAPPED_ACTION_RECORD flag) and no classification of empty or non-data responses (EMPTY_RESPONSE)",
    "not built: market-data/1.16 Ruling 7.3 item 3 and Ruling 7A.1 as worded: the text names the identity feed's securityType2 for the type check, and the rule means "
    "securityType (the code reads securityType; the two are equal on every record held) until the next market-data version corrects the text. The "
    "securityType and securityType2 values of an ETF record need a human's confirmation before any ETF record is used",
)


class Market11Freshness:
    """Ruling 5.2 (prices) and Ruling 1.6 (FX): counts missed sessions or fixings in the calendars of M."""

    policy_id = FRESHNESS_ID

    def __init__(self, calendars: CalendarSet):
        self._calendars = calendars

    @property
    def calendars(self) -> CalendarSet:
        """The calendars of M this policy counts in (read-only; performance/1.2 Ruling 1.6 keys a freshness entry by calendar id)."""
        return self._calendars

    def assess(self, timing: SourceTiming, value_date: datetime.date, as_of: datetime.date) -> Freshness:
        return self.assess_in(timing, value_date, as_of, None).freshness

    def assess_in(
        self, timing: SourceTiming, last_date: datetime.date, as_of: datetime.date,
        calendar_key: Optional[str],
    ) -> FreshnessAssessment:
        count = self._calendars.count_after(calendar_key, last_date, as_of)
        missed = count.missed
        if missed is None:
            state, withhold = FreshnessState.UNKNOWN, Withhold.UNCOUNTABLE
        elif missed == 0:
            state, withhold = FreshnessState.CURRENT, None
        else:
            state = FreshnessState.STALE
            withhold = Withhold.STALE_BEYOND_LIMIT if missed >= NO_VALUE_FROM else None
        freshness = Freshness(timing.source_time, state, timing.delay_status, as_of, self.policy_id)
        return FreshnessAssessment(freshness, missed, withhold, count.calendar_ref, count.notes)


def _is_raw_quote(reading: SourceReading) -> bool:
    obs = reading.observation
    return isinstance(obs, QuoteObservation) and obs.lineage.adjustment_status is AdjustmentStatus.RAW


class Market11PriceOfDate:
    """Rulings 2.1, 2.2, 2.4 item 4a: the latest admissible print on or before the date."""

    rule_id = PRICE_OF_DATE_ID

    def select(self, history: History, as_of: datetime.date) -> Selection:
        for day in sorted((d for d in history if d <= as_of), reverse=True):
            prints = tuple(r for r in history[day] if _is_raw_quote(r) and r.observation.is_print)  # type: ignore[attr-defined]
            admissible = [r for r in prints if r.observation.recovered]  # type: ignore[attr-defined]
            if not admissible:
                continue  # a session without an admissible print: counted as missed by freshness
            if len(prints) == 1:
                return Selection(prints[0], prints, f"the latest admissible print on or before as_of ({day.isoformat()})")
            return Selection(None, prints, f"several prints on {day.isoformat()}: the reconciliation rule decides "
                                           "which is used")
        return Selection(None, (), "no admissible print on or before as_of (Rulings 2.1, 2.4 item 4a)",
                         no_history=True)


class _CalendarFilteredView:
    """The FX view a rule sees, minus the dates that are not fixing days of the governing calendar (C2-14). It proxies
    everything else and records what it dropped."""

    def __init__(self, inner, calendars: Optional[CalendarSet]):  # type: ignore[no-untyped-def]
        self._inner = inner
        self._calendars = calendars
        self.dropped = set()  # type: ignore[var-annotated]

    def __call__(self, base, quote, day):  # type: ignore[no-untyped-def]
        return self._inner(base, quote, day)

    def has_series(self, base, quote):  # type: ignore[no-untyped-def]
        return self._inner.has_series(base, quote)

    def refuted_only_dates(self, base, quote, after, upto):  # type: ignore[no-untyped-def]
        return self._inner.refuted_only_dates(base, quote, after, upto)

    def file_coverage(self, base, quote):  # type: ignore[no-untyped-def]
        return self._inner.file_coverage(base, quote)

    def dates(self, base, quote, upto):  # type: ignore[no-untyped-def]
        out = []
        for d in self._inner.dates(base, quote, upto):
            if self._calendars is not None and self._calendars.is_session(ECB_CALENDAR_ID, d) is False:
                self.dropped.add(d)
                continue
            out.append(d)
        return tuple(out)


class Market11FX:
    """Rulings 1.1, 1.3, 1.4, 1.5, 1.5a, 1.6, 1.1a.

    Ruling 1.5a: no central-parity source is admitted, so the CNY band check does NOT run in product
    paths: `Market11FX()` has no parity series, the check is UNVERIFIABLE and lineage says PARITY_CHECK_NOT_RUN
    (no state effect). `_test_central_parity` (date -> CNY per USD) exists for tests ONLY and is keyword-only and
    underscore-named on purpose: a test-injected mapping must never reach a product path. The only builder
    that passes it is `market11_conventions_with_injected_parity_for_tests`; a boundary test checks that no
    other module of `src/` does."""

    rule_id = FX_ID

    def __init__(self, calendars: Optional[CalendarSet] = None, *,
                 _test_central_parity: Optional[Mapping[datetime.date, Decimal]] = None):
        self._parity = _test_central_parity
        self._calendars = calendars

    # -- helpers ----------------------------------------------------------------------------
    @staticmethod
    def _used_rate(view, reconcile, ccy: CurrencyCode, day: datetime.date) -> Optional[Fraction]:  # type: ignore[no-untyped-def]
        readings = tuple(view(EUR, ccy, day))
        if not readings:
            return None
        rec = reconcile(readings)
        if rec.used is None or rec.status in (ReconciliationStatus.DISAGREEMENT, ReconciliationStatus.IMPLAUSIBLE):
            return None
        obs = rec.used.observation
        assert isinstance(obs, FXObservation)
        return Fraction(obs.rate)

    @staticmethod
    def _flag(rec: Reconciliation, status: ReconciliationStatus, note: str) -> Reconciliation:
        return dataclasses.replace(rec, status=status, used=None, selected_source=None, selection_basis="",
                                   flags=rec.flags + (note,))

    def resolve(self, base, quote, as_of, lookup, reconcile=None) -> FXSelection:  # type: ignore[no-untyped-def]
        """C2-14 (re-check of the CP2 fix round): a fixing whose date is NOT a listed fixing day of the governing ECB
        calendar (inside that calendar's coverage, where it is complete: Ruling 5.3 item 4) is never admissible as a
        print on ANY as-of date, not only on its own date. It is excluded here, before the date used is chosen, so the
        lookup falls back to the previous valid fixing, counted by missed fixings (Ruling 1.6); where no calendar
        covers the date it is not excluded and freshness is UNKNOWN downstream (Ruling 5.3). The exclusion is recorded in
        the lineage notes as OFF_CALENDAR_DATE. (Prices get the same rule from Test V0 at build, which drops a series
        with any date on a non-session.)"""
        view = _CalendarFilteredView(lookup, self._calendars)
        selection = self._resolve(base, quote, as_of, view, reconcile)
        if view.dropped:
            note = (f"{OFF_CALENDAR}: {len(view.dropped)} fixing date(s) are not fixing days of the governing "
                    f"calendar and are never admissible (Ruling 5.3 item 4): "
                    f"{', '.join(d.isoformat() for d in sorted(view.dropped))}")
            selection = dataclasses.replace(selection, lineage_notes=tuple(sorted(set(selection.lineage_notes) | {note})))
        return selection

    def _resolve(self, base, quote, as_of, lookup, reconcile=None) -> FXSelection:  # type: ignore[no-untyped-def]
        if base == quote:
            return FXSelection(FXOutcome.SAME_CURRENCY, Fraction(1), (), (), "same currency")
        if reconcile is None:
            raise ValueError("the market-data/1.2 FX rule needs the reconciler (each leg is reconciled alone)")
        if "CNH" in (base.code, quote.code):
            return FXSelection(FXOutcome.NOT_IN_RELEASE, None, (), (),
                               "CNH is strict (Ruling 1.4, PD-0030): no admitted source publishes it, and the "
                               "CNY rate is never substituted")
        currencies = [c for c in (quote, base) if c != EUR]  # numerator leg first
        for c in currencies:
            if not lookup.has_series(EUR, c):
                return FXSelection(FXOutcome.NOT_IN_RELEASE, None, (), (),
                                   f"no published EUR->{c.code} series in the market-data version")
        common = None
        for c in currencies:
            days = set(lookup.dates(EUR, c, as_of))
            common = days if common is None else common & days
        if not common:
            return FXSelection(FXOutcome.NO_HISTORY, None, (), (),
                               "no fixing dated on or before as_of on which every leg exists (Ruling 1.6)")
        used_day = max(common)  # the latest date on which every leg exists: legs of two dates never combine
        groups = [tuple(lookup(EUR, c, used_day)) for c in currencies]
        recs: List[Reconciliation] = [reconcile(g) for g in groups]
        considered = tuple(r for g in groups for r in g)

        def conflict(basis: str) -> FXSelection:
            return FXSelection(FXOutcome.NO_SELECTION, None, (), considered, basis, reconciliations=tuple(recs))

        # Ruling 1.1a item 6 (1.4 clarification, C2-9): a date that ONLY a REFUTED re-server file holds, later than
        # the date used, is tested here too. Where the publisher's file lacks it inside both coverages, that date is
        # a DISAGREEMENT with no rate, and the rate is NOT carried forward over it (before this, the refuted-only
        # date was dropped from `dates` and the earlier fixing was carried over it, AVAILABLE + STALE_DATA, while the
        # mirror case, a date the publisher holds and the refuted file lacks, was a SOURCE_CONFLICT).
        for i, c in enumerate(currencies):
            for later in lookup.refuted_only_dates(EUR, c, used_day, as_of):
                cover_later = [f for f in lookup.file_coverage(EUR, c) if f.covered and f.first <= later <= f.last]
                if any(x.independence_group == y.independence_group and x.file_sha256 < y.file_sha256
                       and (later in x.dates) != (later in y.dates) for x in cover_later for y in cover_later):
                    recs[i] = self._flag(recs[i], ReconciliationStatus.DISAGREEMENT,
                                         f"1.1a item 6: {later.isoformat()} is held only by a REFUTED re-server file, "
                                         "within both coverages: no rate, and not carried forward over")
                    return conflict("a date held only by a refuted re-server file lies between the last common "
                                    "fixing and the as-of date (Ruling 1.1a item 6)")

        # Ruling 1.1a item 4: a date present in one of two files from one upstream and absent in the other,
        # inside both files' coverage, is a DISAGREEMENT for that date.
        for i, c in enumerate(currencies):
            # Ruling 1.1a item 5 (1.3): the coverage is [start, end] as the file's request and the retrieval
            # time define it (computed at ingest), never the first and last date the file holds. A file whose
            # coverage could not be determined (`covered` False) is UNVERIFIABLE here: the date-set part of the
            # check does not run for it, and no DISAGREEMENT is invented.
            cover = [f for f in lookup.file_coverage(EUR, c) if f.covered and f.first <= used_day <= f.last]
            for x in cover:
                for y in cover:
                    if x.independence_group == y.independence_group and x.file_sha256 < y.file_sha256 and (
                            (used_day in x.dates) != (used_day in y.dates)):
                        recs[i] = self._flag(recs[i], ReconciliationStatus.DISAGREEMENT,
                                             f"1.1a: {used_day.isoformat()} is present in one {x.independence_group} "
                                             "file and absent from another within both coverages")
        if any(r.status is ReconciliationStatus.DISAGREEMENT for r in recs):
            return conflict("two renditions of one fixing differ (Ruling 1.1a item 4, 4.3)")
        if any(r.used is None for r in recs):
            return conflict("no usable reading for a leg")

        # plausibility checks, only where their data exist (Ruling 1.5)
        checks: List[Tuple[str, str]] = []
        parity_notes: List[str] = []
        x_usd = self._used_rate(lookup, reconcile, USD, used_day)
        by_ccy = {c.code: i for i, c in enumerate(currencies)}
        for code, check_id in (("HKD", "HKD_PEG_BAND"), ("CNY", "CNY_PARITY_BAND")):
            leg = by_ccy.get(code)
            if leg is None:  # the currency is not in this pair
                continue
            leg_obs = recs[leg].used.observation  # type: ignore[union-attr]
            assert isinstance(leg_obs, FXObservation)
            if x_usd is None:
                checks.append((check_id, "UNVERIFIABLE"))
                continue
            ratio = Fraction(leg_obs.rate) / x_usd  # that currency per USD
            if code == "HKD":
                ok: Optional[bool] = HKD_PEG_LOW <= ratio <= HKD_PEG_HIGH
                note = "7.75..7.85 HKD per USD (linked exchange rate band)"
            else:
                parity = None if self._parity is None else self._parity.get(used_day)
                if self._parity is None:
                    parity_notes.append(PARITY_NOT_RUN)
                if parity is None:
                    ok, note = None, "no central-parity series in the market-data version"
                else:
                    p = Fraction(parity)
                    ok, note = abs(ratio - p) <= CNY_BAND * p, "+-2 % of the central parity"
            if ok is None:
                checks.append((check_id, "UNVERIFIABLE"))
            elif ok:
                checks.append((check_id, "PASS"))
            else:
                checks.append((check_id, "FAIL"))
                recs[leg] = self._flag(recs[leg], ReconciliationStatus.IMPLAUSIBLE,
                                       f"{check_id}: {ratio} is outside {note}")
        if any(r.status is ReconciliationStatus.IMPLAUSIBLE for r in recs):
            return FXSelection(FXOutcome.NO_SELECTION, None, (), considered,
                               "a leg breaches a published plausibility bound (Ruling 1.5)",
                               reconciliations=tuple(recs), checks=tuple(checks))

        used = [r.used for r in recs]
        observations = [u.observation for u in used]  # type: ignore[union-attr]
        assert all(isinstance(o, FXObservation) for o in observations)
        cross: Optional[ExactRatioRate] = None
        if len(observations) == 1:
            only = observations[0]
            if base == EUR:
                rate = Fraction(only.rate)  # type: ignore[attr-defined]
                basis = f"the published EUR->{quote.code} quote of {used_day.isoformat()}"
            else:
                rate = Fraction(1) / Fraction(only.rate)  # type: ignore[attr-defined]
                basis = (f"the exact inverse of the published EUR->{base.code} quote of {used_day.isoformat()} "
                         "(a separate labelled value, Ruling 1.3)")
        else:
            cross = ExactRatioRate(observations[0], observations[1])  # type: ignore[arg-type]
            rate = cross.as_fraction()
            basis = (f"the exact cross x_{quote.code}/x_{base.code} through EUR from the two same-date legs of "
                     f"{used_day.isoformat()} (Ruling 1.3)")
        notes: List[str] = list(parity_notes)
        for u in used:
            prov = u.observation.lineage.provenance  # type: ignore[union-attr]
            if prov in ("UNCONFIRMED", "REFUTED"):
                notes.append(f"provenance: {prov} ({u.source_id}): not evidence that the value is the ECB "  # type: ignore[union-attr]
                             "reference rate for the date (Ruling 1.1a)")
        return FXSelection(FXOutcome.FOUND, rate, tuple(used), considered, basis,  # type: ignore[arg-type]
                           reconciliations=tuple(recs), cross=cross, checks=tuple(checks),
                           lineage_notes=tuple(sorted(set(notes))))


def market11_conventions(calendars: CalendarSet) -> ConventionSet:
    """The conforming convention set: no placeholder is injected. `open_items` lists what this
    increment does not build; profiles still TO_OBSERVE are added by `visible_open_items()`.

    Ruling 1.5a: this is the PRODUCT path. It takes no central-parity mapping, so the CNY band check
    does not run and every CNY result says PARITY_CHECK_NOT_RUN."""
    return ConventionSet(
        freshness=Market11Freshness(calendars),
        price_of_date=Market11PriceOfDate(),
        reconciler=Market11Reconciler(),
        fx=Market11FX(calendars),
        open_items=UNBUILT + UNBUILT_1_16,
    )


def market11_conventions_with_injected_parity_for_tests(
    calendars: CalendarSet, parity: Mapping[datetime.date, Decimal],
) -> ConventionSet:
    """TESTS ONLY (Ruling 1.5a: an injected mapping must never reach a product path)."""
    return dataclasses.replace(market11_conventions(calendars), fx=Market11FX(calendars, _test_central_parity=parity))


FX_CALENDAR_KEY = ECB_CALENDAR_ID
