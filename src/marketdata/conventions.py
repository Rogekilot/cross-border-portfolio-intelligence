"""Convention plug points (Tech Plan §15.0, §15.7, §15.8; market-data/1.2).

Everything a market-data CONVENTION owns is a protocol, injected into the port and the consumer,
and recorded by id in the release and the data-set reference. The `quant-analyst` owns the rules
(methodology/CP2_MARKET_DATA_CONVENTIONS.md).

IMPLEMENTED from market-data/1.2 (not placeholders): number normalization and precision profiles
(`precision`, `profiles`), reconciliation (`reconciliation.Market11Reconciler`), Test V2
(`verification`), and, in `marketdata.market11` (the rules built over the calendar files of M),
freshness (Ruling 5.2), price of date (Rulings 2.1, 2.2, 2.4 item 4a) and FX (Rulings 1.1-1.6).
`market11.market11_conventions(calendars)` builds the conforming `ConventionSet`.

The `placeholder/...` classes below are RETAINED ONLY as injectable stand-ins that exercise the
plug points (mechanics tests); no product path builds them. They are listed in `PLACEHOLDER_IDS`:

- freshness: assigns nothing (UNKNOWN), never a threshold;
- price of date: RAW readings dated exactly `as_of`, no session lookup, no look-back;
- FX: only the pair exactly as published on exactly that date; no inversion, no crossing through
  EUR, no carry-forward, no CNH-for-CNY substitution (PD-0030: CNH stays strict).

`CONVENTION_SET_ID` is the set that GOVERNS. While any placeholder is injected,
`ConventionSet.is_conformant` is False and the placeholder ids are visible in `ids()`, so no
result can claim conformance it does not have. `is_conformant` True says "no placeholder rule is
injected"; it does NOT say every convention is implemented: `visible_open_items()` lists what
remains (profiles still TO_OBSERVE, rules not yet built), and every `ValuationInputs` carries it.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from enum import Enum, unique
from fractions import Fraction
from typing import Callable, Dict, Mapping, Optional, Protocol, Tuple, runtime_checkable

from domain.currency import CurrencyCode
from marketdata.contracts import (
    AdjustmentStatus,
    ExactRatioRate,
    Freshness,
    FreshnessState,
    FXObservation,
    QuoteObservation,
    Reconciliation,
    SourceReading,
    SourceTiming,
)
from marketdata.manifest import CONVENTION_SET_ID, FileRef
from marketdata.profiles import profile_open_items
from marketdata.reconciliation import Market11Reconciler


@unique
class FXOutcome(Enum):
    FOUND = "FOUND"
    NO_OBSERVATION = "NO_OBSERVATION"
    NO_SELECTION = "NO_SELECTION"
    NOT_IN_RELEASE = "NOT_IN_RELEASE"
    SAME_CURRENCY = "SAME_CURRENCY"
    NO_HISTORY = "NO_HISTORY"  # no fixing (both legs) on or before the date


@dataclass(frozen=True)
class Selection:
    """A price-of-date rule's answer: the reading it chose (or none), the readings it
    considered (all of them go to reconciliation), and its stated basis. `no_history` is True when
    nothing admissible exists on or before the date (no print): the market-data/1.2 rule's
    "no price print <= D" (Ruling 4.4), as opposed to the placeholder's "no exact-date reading"."""

    selected: Optional[SourceReading]
    considered: Tuple[SourceReading, ...]
    basis: str
    no_history: bool = False


@dataclass(frozen=True)
class FXSelection:
    outcome: FXOutcome
    rate: Optional[Fraction]  # EXACT (Ruling 1.3): a cross is never a rounded Decimal
    legs: Tuple[SourceReading, ...]  # the published observations behind the rate, all kept
    considered: Tuple[SourceReading, ...]
    basis: str
    # market-data/1.2: set by a rule that reconciles per leg itself (a cross has two legs of two
    # currencies, which must never be reconciled against each other). Empty: the store reconciles
    # `considered` as one group (the placeholder's single published pair).
    reconciliations: Tuple[Reconciliation, ...] = ()
    cross: Optional[ExactRatioRate] = None
    checks: Tuple[Tuple[str, str], ...] = ()  # plausibility checks that ran: (id, PASS|FAIL|UNVERIFIABLE)
    lineage_notes: Tuple[str, ...] = ()


# date -> readings of that date (all sources), for dates up to and including as_of
History = Mapping[datetime.date, Tuple[SourceReading, ...]]
# (base, quote, date) -> readings of the published pair on that date
PairLookup = Callable[[CurrencyCode, CurrencyCode, datetime.date], Tuple[SourceReading, ...]]


@unique
class Withhold(Enum):
    """Why a freshness policy says the number may not be used (Rulings 1.6, 5.2)."""

    STALE_BEYOND_LIMIT = "STALE_BEYOND_LIMIT"
    UNCOUNTABLE = "UNCOUNTABLE"


@dataclass(frozen=True)
class FreshnessAssessment:
    """A calendar-aware policy's answer: the freshness, the missed count (None: cannot be counted),
    whether the value must be withheld, the calendar file consulted and the lineage notes."""

    freshness: Freshness
    missed: Optional[int]
    withhold: Optional[Withhold] = None
    calendar_ref: Optional[FileRef] = None
    notes: Tuple[str, ...] = ()


class FreshnessPolicy(Protocol):
    policy_id: str

    def assess(
        self, timing: SourceTiming, value_date: datetime.date, as_of: datetime.date
    ) -> Freshness: ...


@runtime_checkable
class CalendarFreshnessPolicy(Protocol):
    """A freshness policy that counts sessions or fixings in a calendar. `calendar_key` is a
    listing's MIC, or `ECB` for a fixing."""

    policy_id: str

    def assess_in(
        self, timing: SourceTiming, last_date: datetime.date, as_of: datetime.date,
        calendar_key: Optional[str],
    ) -> FreshnessAssessment: ...


class PriceOfDateRule(Protocol):
    rule_id: str

    def select(self, history: History, as_of: datetime.date) -> Selection: ...


class Reconciler(Protocol):
    rule_id: str

    def reconcile(self, readings: Tuple[SourceReading, ...]) -> Reconciliation: ...


class FXRule(Protocol):
    rule_id: str

    def resolve(
        self,
        base: CurrencyCode,
        quote: CurrencyCode,
        as_of: datetime.date,
        lookup: PairLookup,
        reconcile: Optional[Callable[[Tuple[SourceReading, ...]], Reconciliation]] = None,
    ) -> FXSelection: ...


@dataclass(frozen=True)
class ConventionSet:
    """The conventions injected into a lookup. `ids()` goes into the release and every
    `DataSetRef`, so a result can be reproduced with the same rules. `open_items` names what is
    not yet built (set by the builder of the set); profiles still TO_OBSERVE are always added by
    `visible_open_items()`."""

    freshness: FreshnessPolicy
    price_of_date: PriceOfDateRule
    reconciler: Reconciler
    fx: FXRule
    convention_set_id: str = CONVENTION_SET_ID
    open_items: Tuple[str, ...] = ()

    def ids(self) -> Dict[str, str]:
        return {
            "convention_set": self.convention_set_id,
            "freshness": self.freshness.policy_id,
            "fx": self.fx.rule_id,
            "price_of_date": self.price_of_date.rule_id,
            "reconciliation": self.reconciler.rule_id,
        }

    def placeholder_ids(self) -> Tuple[str, ...]:
        return tuple(sorted(v for k, v in self.ids().items()
                            if k != "convention_set" and v.startswith("placeholder/")))

    @property
    def is_conformant(self) -> bool:
        """True only when no placeholder is injected."""
        return not self.placeholder_ids()

    def visible_open_items(self) -> Tuple[str, ...]:
        """Placeholders injected, profiles still TO_OBSERVE and rules not yet built, in a stable order."""
        return tuple(f"placeholder rule injected: {p}" for p in self.placeholder_ids()) + (
            profile_open_items() + tuple(self.open_items))


# --- placeholder stand-ins (mechanics tests only; no product path builds them) -----------

FRESHNESS_PLACEHOLDER_ID = "placeholder/freshness-unassessed/0"
PRICE_OF_DATE_PLACEHOLDER_ID = "placeholder/price-of-date-exact/0"
FX_PLACEHOLDER_ID = "placeholder/fx-published-pair-exact/0"
PLACEHOLDER_IDS = (
    FRESHNESS_PLACEHOLDER_ID,
    FX_PLACEHOLDER_ID,
    PRICE_OF_DATE_PLACEHOLDER_ID,
)


class PlaceholderFreshnessPolicy:
    """Assigns no freshness state: always UNKNOWN. Infers no threshold."""

    policy_id = FRESHNESS_PLACEHOLDER_ID

    def assess(
        self, timing: SourceTiming, value_date: datetime.date, as_of: datetime.date
    ) -> Freshness:
        return Freshness(
            source_time=timing.source_time,
            state=FreshnessState.UNKNOWN,
            delay_status=timing.delay_status,
            assessed_as_of=as_of,
            policy_id=self.policy_id,
        )


class PlaceholderExactDateRule:
    """RAW readings dated exactly `as_of`; nothing else (Ruling 2.3: valuation uses RAW only).
    ALL such readings are `considered` (they go to reconciliation, which decides the value used
    when several upstreams report). It selects directly only a single reading, and never one
    that is not recovered (Ruling 2.4 item 4)."""

    rule_id = PRICE_OF_DATE_PLACEHOLDER_ID

    def select(self, history: History, as_of: datetime.date) -> Selection:
        readings = tuple(
            r for r in history.get(as_of, ())
            if r.observation.lineage.adjustment_status is AdjustmentStatus.RAW  # type: ignore[attr-defined]
        )
        if not readings:
            return Selection(None, (), "no RAW reading dated exactly as_of")
        if len(readings) == 1:
            only = readings[0]
            assert isinstance(only.observation, QuoteObservation)
            if not only.observation.recovered:
                return Selection(None, readings, "the only reading is not recovered: it may corroborate, never be used")
            return Selection(only, readings, "single reading dated exactly as_of")
        return Selection(None, readings, "several readings: the reconciliation rule decides which is used")


class PlaceholderPublishedPairFXRule:
    """The pair exactly as published, same direction, exact date. Same currency is rate 1
    with no legs. No inversion, crossing, carry-forward or CNY/CNH mapping (a later increment;
    PD-0030: CNH stays strict). Several readings go to reconciliation."""

    rule_id = FX_PLACEHOLDER_ID

    def resolve(
        self, base: CurrencyCode, quote: CurrencyCode, as_of: datetime.date, lookup: PairLookup,
        reconcile: Optional[Callable[[Tuple[SourceReading, ...]], Reconciliation]] = None,
    ) -> FXSelection:
        if base == quote:
            return FXSelection(FXOutcome.SAME_CURRENCY, Fraction(1), (), (), "same currency")
        readings = tuple(lookup(base, quote, as_of))
        if not readings:
            return FXSelection(FXOutcome.NO_OBSERVATION, None, (), (),
                               "no published reading for this pair dated exactly as_of")
        if len(readings) == 1:
            obs = readings[0].observation
            assert isinstance(obs, FXObservation)
            return FXSelection(FXOutcome.FOUND, Fraction(obs.rate), readings, readings,
                               "single published reading dated exactly as_of")
        return FXSelection(FXOutcome.NO_SELECTION, None, (), readings,
                           "several readings: the reconciliation rule decides which is used")


def placeholder_conventions() -> ConventionSet:
    """1.1 reconciliation with the remaining placeholders (freshness, price of date, FX)."""
    return ConventionSet(
        freshness=PlaceholderFreshnessPolicy(),
        price_of_date=PlaceholderExactDateRule(),
        reconciler=Market11Reconciler(),
        fx=PlaceholderPublishedPairFXRule(),
    )
