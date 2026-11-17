"""The analytics-facing consumer of the market-data port (Tech Plan §15.9).

`assemble_valuation_inputs` gathers, for the positions and cash a CP1 replay produced, the
quote lookup for each held listing and the FX lookup for each currency other than the
reporting currency, with each outcome, freshness, reconciliation and the files consumed.
It performs NO valuation arithmetic and chooses NO convention: conventions are injected
(Tech Plan §13.E keeps FX conversion outside the ledger; CP3 builds valuation on this).

This module depends on the port protocols, the normalized contracts and CP1 replay result
types only. It must stay free of any adapter, vendor or file-format knowledge: that is the
CP2 exit criterion ("same internal analytics contract can consume test data from more than
one adapter/mock without business-logic change"), enforced by an import-boundary test.
"""

from __future__ import annotations

import datetime
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple

from domain.currency import CurrencyCode
from domain.replay import ReplayedState
from marketdata.conventions import ConventionSet
from marketdata.contracts import QuoteObservation, Reconciliation
from marketdata.manifest import DataKind, DataSetRef, FileRef
from marketdata.port import (
    FXLookup,
    InstrumentResolverPort,
    LookupOutcome,
    MarketDataPort,
    QuoteLookup,
)
from product_contract.metric_state import MetricResult


class ValuationInputsError(ValueError):
    pass


def _status(reconciliation: Optional[Reconciliation]) -> Optional[str]:
    if reconciliation is None or reconciliation.status is None:
        return None
    return reconciliation.status.value


@dataclass(frozen=True)
class PositionInput:
    account_id: uuid.UUID
    listing_id: uuid.UUID
    quantity: MetricResult  # passed through from replay, untouched


@dataclass(frozen=True)
class QuoteInput:
    listing_id: uuid.UUID
    native_currency: Optional[CurrencyCode]
    lookup: QuoteLookup


@dataclass(frozen=True)
class FXInput:
    currency: CurrencyCode
    lookup: FXLookup


@dataclass(frozen=True)
class ValuationInputs:
    as_of: datetime.date
    reporting_currency: CurrencyCode
    release_id: str
    convention_ids: Tuple[Tuple[str, str], ...]
    conformant: bool  # False while any placeholder convention is injected
    positions: Tuple[PositionInput, ...]
    quotes: Tuple[QuoteInput, ...]
    fx: Tuple[FXInput, ...]
    data_set_refs: Tuple[DataSetRef, ...]
    # market-data/1.2: what is still open, listed so no result can hide it (placeholders injected, profiles
    # still TO_OBSERVE, rules not yet built); and Ruling 4.8: True if any input comes from a market-data
    # version that holds synthetic data (a result from it may never be presented as a real market fact).
    open_items: Tuple[str, ...] = ()
    synthetic: bool = False

    def value_obj(self) -> Dict[str, object]:
        """What the data SAYS, with no provenance: identical for two adapters that report
        the same facts."""
        quotes = []
        for q in self.quotes:
            lk = q.lookup
            sel = None if lk.selected is None else lk.selected.observation
            assert sel is None or isinstance(sel, QuoteObservation)
            quotes.append({
                "listing_id": str(q.listing_id),
                "native_currency": None if q.native_currency is None else q.native_currency.code,
                "outcome": lk.outcome.value,
                "value_date": None if sel is None else sel.value_date,
                "price": None if sel is None else sel.price,
                "currency": None if sel is None else sel.currency.code,
                "reconciliation": _status(lk.reconciliation),
                "freshness": None if lk.freshness is None else lk.freshness.state.value,
            })
        fx = [{
            "currency": f.currency.code,
            "outcome": f.lookup.outcome.value,
            "rate": f.lookup.rate,
            "reconciliation": _status(f.lookup.reconciliation),
            "freshness": [x.state.value for x in f.lookup.leg_freshness],
        } for f in self.fx]
        positions = [{
            "account_id": str(p.account_id), "listing_id": str(p.listing_id),
            "quantity": p.quantity.value, "state": p.quantity.sufficiency_state.value,
        } for p in self.positions]
        return {
            "as_of": self.as_of, "reporting_currency": self.reporting_currency.code,
            "positions": positions, "quotes": quotes, "fx": fx,
        }

    def lineage_obj(self) -> Dict[str, object]:
        """Where it came from: the release, the conventions and the exact files read."""
        def refs(items: Tuple[FileRef, ...]) -> List[List[str]]:
            return [[r.file_sha256, r.adapter_id, r.adapter_version] for r in items]

        return {
            "release_id": self.release_id,
            "conventions": [list(p) for p in self.convention_ids],
            "conformant": self.conformant,
            "open_items": list(self.open_items),
            "synthetic": self.synthetic,
            "quotes": [{"listing_id": str(q.listing_id), "consumed": refs(q.lookup.consumed)}
                       for q in self.quotes],
            "fx": [{"currency": f.currency.code, "consumed": refs(f.lookup.consumed)}
                   for f in self.fx],
            "data_set_refs": [r.to_obj() for r in self.data_set_refs],
        }

    def resolution_obj(self) -> Dict[str, object]:
        """HOW each input was resolved (market-data/1.2 Rulings 1.6, 5.2, 4.7, 5.3): the date actually
        used, the missed-session or missed-fixing count, the exact cross legs and the lineage notes
        (causes such as NO_ADMITTED_SOURCE and CALENDAR_COVERAGE_GAP). Kept apart from `value_obj` so the
        value part stays byte-identical for adapters that report the same facts."""
        quotes = [{
            "listing_id": str(q.listing_id), "outcome": q.lookup.outcome.value,
            "date_used": q.lookup.date_used, "missed_count": q.lookup.missed_count,
            "notes": list(q.lookup.lineage_notes), "synthetic": q.lookup.synthetic,
        } for q in self.quotes]
        fx = [{
            "currency": f.currency.code, "outcome": f.lookup.outcome.value,
            "date_used": f.lookup.date_used, "missed_count": f.lookup.missed_count,
            "cross": None if f.lookup.cross is None else {
                "numerator": f.lookup.cross.numerator.rate, "denominator": f.lookup.cross.denominator.rate,
                "fixing_date": f.lookup.cross.fixing_date},
            "checks": [list(c) for c in f.lookup.checks],
            "notes": list(f.lookup.lineage_notes), "synthetic": f.lookup.synthetic,
        } for f in self.fx]
        return {"quotes": quotes, "fx": fx}


def assemble_valuation_inputs(
    port: MarketDataPort,
    resolver: InstrumentResolverPort,
    state: ReplayedState,
    as_of: datetime.date,
    reporting_currency: CurrencyCode,
    conventions: ConventionSet,
) -> ValuationInputs:
    if state.as_of != as_of:
        raise ValuationInputsError("as_of must equal the replayed state's as_of")
    positions: List[PositionInput] = []
    listings: Set[uuid.UUID] = set()
    cash_currencies: Set[CurrencyCode] = set()
    for account in state.accounts:
        for p in account.positions:
            positions.append(PositionInput(p.account_id, p.listing_id, p.quantity))
            listings.add(p.listing_id)
        for balance in account.cash:
            cash_currencies.add(balance.balance.currency)
    quotes: List[QuoteInput] = []
    native: Set[CurrencyCode] = set()
    for listing_id in sorted(listings, key=str):
        lookup = port.quote_on(listing_id, as_of, conventions)
        currency: Optional[CurrencyCode] = None
        if lookup.selected is not None:
            obs = lookup.selected.observation
            assert isinstance(obs, QuoteObservation)
            currency = obs.currency
        else:
            currency = resolver.trading_currency(listing_id)
        if currency is not None:
            native.add(currency)
        quotes.append(QuoteInput(listing_id, currency, lookup))
    needed = sorted((native | cash_currencies) - {reporting_currency}, key=lambda c: c.code)
    fx = tuple(FXInput(c, port.fx_on(c, reporting_currency, as_of, conventions)) for c in needed)
    ids = conventions.ids()
    refs: List[DataSetRef] = []
    if quotes:
        consumed = [r for q in quotes for r in q.lookup.consumed]
        refs.append(DataSetRef.build(DataKind.QUOTE, port.release_id(), consumed, ids, as_of,
                                     as_of, conventions.convention_set_id))
    if fx:
        consumed = [r for f in fx for r in f.lookup.consumed]
        refs.append(DataSetRef.build(DataKind.FX, port.release_id(), consumed, ids, as_of,
                                     as_of, conventions.convention_set_id))
    return ValuationInputs(
        as_of=as_of,
        reporting_currency=reporting_currency,
        release_id=port.release_id(),
        convention_ids=tuple(sorted(ids.items())),
        conformant=conventions.is_conformant,
        positions=tuple(positions),
        quotes=tuple(quotes),
        fx=tuple(fx),
        data_set_refs=tuple(refs),
        open_items=conventions.visible_open_items(),
        synthetic=any(q.lookup.synthetic for q in quotes) or any(f.lookup.synthetic for f in fx),
    )
