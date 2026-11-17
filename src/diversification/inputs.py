"""Derive CP5 capital and return inputs from existing CP3 and CP4 boundaries.

No account balance, FX conversion, return or corporate action is supplied by an
explanation layer. The existing ledger valuation and market-data ports own them.
"""
from __future__ import annotations

import uuid
from fractions import Fraction

from domain.catalogs import BenchmarkEntry, ReturnBasis, SeriesForm
from domain.currency import CurrencyCode
from marketdata.states import fx_input_state
from performance.engine import calendar_id_resolver
from risk.benchmark import BenchmarkLeg
from risk.levels import build_proxy
from diversification.contracts import AVAILABLE, LIMITED, INSUFFICIENT, Bucket, History, Observation


def capital_buckets(valuation):
    """Group account-level components by listing/currency using exact CP3 values."""
    native = {(m.metric_id, m.subject): m for m in valuation.metrics if m.view == "NATIVE"}
    grouped = {}
    for m in valuation.metrics:
        if m.view != "REPORTING" or m.metric_id not in ("holding_value", "cash_value", "receivable_value"):
            continue
        subject = dict(m.subject)
        currency = native[m.metric_id, m.subject].currency
        kind = {"holding_value": "SECURITY", "cash_value": "CASH", "receivable_value": "RECEIVABLE"}[m.metric_id]
        key = "SECURITY:" + subject["listing"] if kind == "SECURITY" else kind + ":" + str(currency)
        grouped.setdefault((key, kind, currency), []).append(m)
    out = []
    for (key, kind, currency), rows in sorted(grouped.items()):
        rank = {AVAILABLE: 0, LIMITED: 1, INSUFFICIENT: 2}
        state = max((m.result.sufficiency_state for m in rows), key=rank.__getitem__)
        value = None if state is INSUFFICIENT else sum((m.exact for m in rows), Fraction())
        reasons = sorted({m.result.reason_code.value for m in rows if m.result.reason_code is not None})
        details = tuple(sorted({c.detail for m in rows for c in m.causes if c.detail} | {d for m in rows for d in m.details}))
        if any(m.exact is not None and m.exact < 0 for m in rows):
            details = tuple(sorted(set(details) | {"NEGATIVE_COMPONENT"}))
        out.append(Bucket(key, kind, currency or "UNKNOWN", value, state, reasons[0] if reasons else None, details))
    return tuple(out)


def _missing(bucket, dates, detail, reason=None):
    return History(bucket.key, tuple(Observation(a, b, None, INSUFFICIENT, reason, (detail,)) for a, b in zip(dates, dates[1:])))


def history_for(bucket, dates, reporting, port, resolver, conventions, *, coverage=None, as_of=None, instant=None):
    """Total-return security leg or zero-native-interest FX leg; consumed files travel with it."""
    if len(dates) < 2:
        return History(bucket.key, ()), ()
    if bucket.kind != "SECURITY":
        values, files = [], set()
        for day in dates:
            lookup = port.fx_on(CurrencyCode(bucket.currency), reporting, day, conventions)
            state = fx_input_state(lookup)
            files.update(lookup.consumed)
            rate = lookup.rate
            values.append((None if rate is None else Fraction(rate), state))
        rows = []
        for a, b, (left, sa), (right, sb) in zip(dates, dates[1:], values, values[1:]):
            rank = {AVAILABLE: 0, LIMITED: 1, INSUFFICIENT: 2}
            state = max((sa.state, sb.state), key=rank.__getitem__)
            reasons = sorted({s.reason.value for s in (sa, sb) if s.reason is not None})
            details = tuple(s.note for s in (sa, sb) if s.note)
            if left is None or right is None or left <= 0:
                state = INSUFFICIENT
            rows.append(Observation(a, b, None if state is INSUFFICIENT else right / left - 1, state,
                                    reasons[0] if reasons else None, details or (("MISSING_FX_HISTORY",) if state is INSUFFICIENT else ())))
        return History(bucket.key, tuple(rows), (("native_interest", "ZERO_ASSUMPTION"), ("currency", bucket.currency))), tuple(sorted(files))
    listing = uuid.UUID(bucket.key.split(":", 1)[1])
    if coverage is not None and coverage.return_basis != "TOTAL_RETURN_GROSS":
        return _missing(bucket, dates, "NOT_TOTAL_RETURN"), ()
    if (coverage is None or not coverage.confirmed or coverage.listing_id != str(listing)
            or coverage.start > dates[0] or coverage.end < dates[-1] or coverage.as_of > (as_of or dates[-1])):
        return _missing(bucket, dates, "TOTAL_RETURN_COVERAGE_UNCONFIRMED"), ()
    cal = calendar_id_resolver(conventions)(resolver.exchange_mic(listing))
    if cal is None:
        return _missing(bucket, dates, "CALENDAR_COVERAGE_GAP"), ()
    built = build_proxy(listing, port, conventions, dates[-1], cal)
    if built is None:
        return _missing(bucket, dates, "MISSING_PRICE_HISTORY", "MISSING_PRICE_HISTORY"), ()
    if built.currency != bucket.currency:
        return _missing(bucket, dates, "IDENTITY_CURRENCY_MISMATCH", "MISSING_PRICE_HISTORY"), built.consumed
    # Internal leg descriptor only: it is not admitted to any benchmark catalog and
    # never changes the user's benchmark selection.
    descriptor = BenchmarkEntry("CP5_" + listing.hex, "Security total return", "Existing market-data release", built.source_id or "unknown",
                                "existing release terms", bucket.currency, ReturnBasis.TOTAL_RETURN_GROSS, "gross cash dividends reinvested",
                                cal, SeriesForm.LEVELS, None, built.synthetic, str(listing))
    leg = BenchmarkLeg(descriptor, built.book, built.source_id, built.synthetic, built.consumed, port, reporting, conventions, instant)
    rows = []
    for period in leg.period_returns(dates):
        v = period.valued
        reason = "MISSING_PRICE_HISTORY" if v.reason == "MISSING_BENCHMARK" else v.reason
        details = tuple(sorted({c.detail.replace("BENCHMARK", "SECURITY") for c in v.causes if c.detail}))
        rows.append(Observation(period.start, period.end, v.exact, v.state, reason, details))
    return History(bucket.key, tuple(rows), (("return_basis", "TOTAL_RETURN_GROSS"), ("calendar", cal),
                                            ("currency", bucket.currency), ("currency_treatment", leg.currency_treatment))), leg.consumed
