"""Canonical encodings for market-data values (determinism, NFR-001).

Everything that is hashed or compared byte-for-byte (a release id, a data-set reference,
a per-file normalized digest, a consumer's value part) goes through `canonical_json`:
sorted keys, no whitespace, no floats (a float anywhere is an error), `Decimal` written
as its exact value with no exponent and no trailing zeros, so the same fact written as
`150.20` and `150.2` is the same bytes.
"""

from __future__ import annotations

import datetime
import hashlib
import json
from decimal import Context, Decimal
from fractions import Fraction
from typing import Any

from marketdata import contracts as c

# Exact for any value the ledger bounds allow (< 1E30, <= 24 decimals) and for float-origin
# text with 17 significant digits; far wider than needed, never rounds in practice.
_WIDE = Context(prec=200)


class CanonicalEncodingError(ValueError):
    pass


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical_decimal(value: Decimal) -> str:
    if not isinstance(value, Decimal) or not value.is_finite():
        raise CanonicalEncodingError(f"not a finite Decimal: {value!r}")
    if value == 0:
        return "0"
    sign, digits, exponent = value.normalize(_WIDE).as_tuple()
    text = "".join(str(d) for d in digits)
    if exponent >= 0:
        text = text + "0" * exponent
    else:
        point = len(text) + exponent
        if point <= 0:
            text = "0." + "0" * (-point) + text
        else:
            text = text[:point] + "." + text[point:]
    return ("-" if sign else "") + text


def _plain(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        raise CanonicalEncodingError("floats are not allowed in canonical JSON")
    if isinstance(obj, Decimal):
        return canonical_decimal(obj)
    if isinstance(obj, Fraction):  # exact rational, in lowest terms: "n/d"
        return f"{obj.numerator}/{obj.denominator}"
    if isinstance(obj, datetime.datetime):
        if obj.tzinfo is None:
            raise CanonicalEncodingError("naive datetime")
        return obj.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    if isinstance(obj, datetime.date):
        return obj.isoformat()
    if isinstance(obj, datetime.time):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    if hasattr(obj, "value") and hasattr(obj, "name") and not isinstance(obj, type):
        return obj.value  # Enum
    raise CanonicalEncodingError(f"cannot encode {type(obj).__name__}")


def canonical_json(obj: Any) -> str:
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def canonical_bytes(obj: Any) -> bytes:
    return canonical_json(obj).encode("utf-8")


def _lineage_obj(lineage: c.Lineage) -> dict:
    return {
        "source": lineage.source,
        "adjustment_status": lineage.adjustment_status.value,
        "source_id": lineage.source_id,
        "file_sha256": lineage.file_sha256,
        "adapter_id": lineage.adapter_id,
        "adapter_version": lineage.adapter_version,
        "source_record_ref": lineage.source_record_ref,
        "retrieved_at": lineage.retrieved_at,
        "usage_scope": lineage.usage_scope.value,
        "adjustment_anchor": lineage.adjustment_anchor,
        "upstream": lineage.upstream,
        "independence_group": lineage.independence_group,
        "adjustment_method": lineage.adjustment_method,
        "label_status": None if lineage.label_status is None else lineage.label_status.value,
        "precision_profile_id": lineage.precision_profile_id,
        "source_value_text": lineage.source_value_text,
        "market": lineage.market,
        "library": lineage.library,
        "library_version": lineage.library_version,
        "library_function": lineage.library_function,
        "consistency_checks_passed": lineage.consistency_checks_passed,
        "volume_unit_status": lineage.volume_unit_status,
        "provenance": lineage.provenance,
        "adjustment_label_source": lineage.adjustment_label_source,
    }


def lineage_json_obj(lineage: c.Lineage) -> dict:
    """The lineage as PLAIN JSON (strings, booleans, nulls only; a datetime is its canonical UTC text), for a
    store that keeps lineage next to the values. The exact inverse is `lineage_from_json_obj`."""
    return json.loads(canonical_json(_lineage_obj(lineage)))


def parse_instant(text: str) -> datetime.datetime:
    """The inverse of the canonical datetime text (`2025-01-02T14:15:00.000000Z`): an aware UTC datetime."""
    return datetime.datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=datetime.timezone.utc)


def lineage_from_json_obj(obj: dict) -> c.Lineage:
    """Rebuild a `Lineage` from `lineage_json_obj`'s output, field for field."""
    retrieved = obj["retrieved_at"]
    label = obj["label_status"]
    return c.Lineage(
        source=obj["source"],
        adjustment_status=c.AdjustmentStatus(obj["adjustment_status"]),
        source_id=obj["source_id"],
        file_sha256=obj["file_sha256"],
        adapter_id=obj["adapter_id"],
        adapter_version=obj["adapter_version"],
        source_record_ref=obj["source_record_ref"],
        retrieved_at=None if retrieved is None else parse_instant(retrieved),
        usage_scope=c.UsageScope(obj["usage_scope"]),
        adjustment_anchor=obj["adjustment_anchor"],
        upstream=obj["upstream"],
        independence_group=obj["independence_group"],
        adjustment_method=obj["adjustment_method"],
        label_status=None if label is None else c.LabelStatus(label),
        precision_profile_id=obj["precision_profile_id"],
        source_value_text=obj["source_value_text"],
        market=obj["market"],
        library=obj["library"],
        library_version=obj["library_version"],
        library_function=obj["library_function"],
        consistency_checks_passed=obj["consistency_checks_passed"],
        volume_unit_status=obj["volume_unit_status"],
        provenance=obj["provenance"],
        adjustment_label_source=obj["adjustment_label_source"],
    )


def _timing_obj(timing: c.SourceTiming) -> dict:
    return {"source_time": timing.source_time, "delay_status": timing.delay_status.value}


def observation_obj(obs: object) -> dict:
    """Full (value + lineage) plain form of a normalized observation, for digests."""
    if isinstance(obs, c.QuoteObservation):
        return {
            "kind": "QUOTE", "listing_id": str(obs.listing_id), "value_date": obs.value_date,
            "price": obs.price, "currency": obs.currency.code, "volume": obs.volume,
            "price_kind": obs.price_kind.value, "recovered": obs.recovered,
            "precision_bound": obs.precision_bound, "timing": _timing_obj(obs.timing),
            "lineage": _lineage_obj(obs.lineage), "observed_at": obs.observed_at,
        }
    if isinstance(obs, c.FXObservation):
        return {
            "kind": "FX", "base": obs.base_currency.code, "quote": obs.quote_currency.code,
            "value_date": obs.value_date, "rate": obs.rate, "rate_basis": obs.rate_basis,
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
            "observed_at": obs.observed_at,
        }
    if isinstance(obs, c.CorporateActionObservation):
        extra = {} if obs.paid_amount is None else {"paid_amount": obs.paid_amount}  # present only when stated: every digest recorded before the field existed is unchanged
        return {
            **extra, "kind": "ACTION", "listing_id": str(obs.listing_id),
            "action_type": obs.action_type.value, "effective_date": obs.effective_date,
            "split": None if obs.split_ratio is None else
            [obs.split_ratio.new_units, obs.split_ratio.old_units],
            "amount": None if obs.amount_per_unit is None else
            [obs.amount_per_unit.amount, obs.amount_per_unit.currency.code],
            "pay_date": obs.pay_date, "record_date": obs.record_date,
            "paid_currency": None if obs.paid_currency is None else obs.paid_currency.code,
            "issuer_fx_rate": obs.issuer_fx_rate, "old_ticker": obs.old_ticker,
            "new_ticker": obs.new_ticker, "unsupported_label": obs.unsupported_label,
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
        }
    if isinstance(obs, c.BenchmarkSeries):
        return {
            "kind": "BENCHMARK", "benchmark_id": obs.benchmark_id, "provider": obs.provider,
            "value_kind": obs.value_kind.value, "currency": obs.currency.code,
            "points": [[p.value_date, p.value] for p in obs.points],
            "licensing": [obs.licensing.license_status.value, obs.licensing.display_permitted,
                          obs.licensing.terms_ref],
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
        }
    if isinstance(obs, c.RiskFreeSeries):
        return {
            "kind": "RISK_FREE", "series_id": obs.series_id, "name": obs.name, "provider": obs.provider, "currency": obs.currency.code, "instrument": obs.instrument,
            "tenor_weeks": obs.tenor_weeks, "quote_type": obs.quote_type.value, "day_count_basis": obs.day_count_basis, "unit": obs.unit.value,
            "decimals_published": obs.decimals_published, "date_semantics": obs.date_semantics, "calendar_id": obs.calendar_id, "revision_policy": obs.revision_policy.value,
            "points": [[p.value_date, p.rate, p.term_days] for p in obs.points],
            "licensing": [obs.licensing.license_status.value, obs.licensing.display_permitted, obs.licensing.terms_ref],
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
        }
    if isinstance(obs, c.AdjustedQuote):
        return {
            "kind": "ADJUSTED", "listing_id": str(obs.listing_id), "value_date": obs.value_date,
            "open": obs.open, "high": obs.high, "low": obs.low, "close": obs.close,
            "currency": obs.currency.code, "label": [obs.label.adjustment_status.value,
                                                     obs.label.method.value,
                                                     None if obs.label.anchor is None else obs.label.anchor.value,
                                                     obs.label.vintage],
            "precision_bound": obs.precision_bound,
            "field_bounds": None if obs.field_bounds is None else list(obs.field_bounds),
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
        }
    if isinstance(obs, c.CalendarDays):
        return {
            "kind": "CALENDAR", "calendar_id": obs.calendar_id, "calendar_kind": obs.kind.value,
            "applies_to": list(obs.applies_to), "timezone": obs.timezone,
            "covers": [obs.covers_from, obs.covers_to], "actual_through": obs.actual_through,
            "dates": list(obs.dates), "default_close": obs.default_close,
            "early_closes": [[d, t] for d, t in obs.early_closes],
            "fixing_time": obs.fixing_time, "publication_time": obs.publication_time,
            "evidence": obs.evidence, "prepared_by": obs.prepared_by, "prepared_on": obs.prepared_on,
            "version_label": obs.version_label, "lineage": _lineage_obj(obs.lineage),
        }
    if isinstance(obs, c.IdentityAssertion):
        return {
            "kind": "IDENTITY", "figi": obs.figi, "composite_figi": obs.composite_figi,
            "share_class_figi": obs.share_class_figi, "ticker": obs.ticker,
            "exch_code": obs.exch_code, "name": obs.name, "security_type": obs.security_type,
            "timing": _timing_obj(obs.timing), "lineage": _lineage_obj(obs.lineage),
        }
    raise CanonicalEncodingError(f"not a normalized observation: {type(obs).__name__}")


def observation_value_obj(obs: object) -> dict:
    """The VALUE part only: what the fact says, with no provenance. Two adapters that
    report the same fact give equal value parts."""
    full = observation_obj(obs)
    for key in ("lineage", "timing", "observed_at"):
        full.pop(key, None)
    return full
