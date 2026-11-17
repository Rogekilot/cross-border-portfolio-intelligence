"""Number normalization through precision profiles (market-data/1.1 Ruling 2.4, 4.2, 2.6).

Replaces the 1.0 "round half-even to a fixed number of decimals" rule, which 1.1 FORBIDS.

1. A `Decimal` is NEVER constructed from a binary float. Every value starts as the file's TEXT.
   (A float is used only as a calculator to find a binary value's neighbours; the result is
   always built from a string.)
2. Normalization: the shortest decimal string that converts back to the same binary value in
   the field's DECLARED format. TEXT_DECIMAL: the text. FLOAT64 as printed by pandas: the text
   is already the shortest round-trip form (identity). FLOAT32: the shortest `%.{p}g` that
   round-trips through IEEE-754 binary32 (`474.20001` -> `474.2`).
3. Validation (fail closed): a close must have at most `max_dp` decimals for its market and
   price level, AND the format must resolve that grid at that price (for float32,
   ulp(v) < 10^-max_dp). Otherwise the value is kept but marked NOT RECOVERED: its bound is half
   an ulp in the declared format, and it may corroborate only, never be the value used.
4. Profile check (fail closed): a TEXT_DECIMAL/FLOAT64 field showing the float32 signature
   fails; so does a FLOAT32 field whose text is not the float32 rendering of its own value.
   A failed check means the profile is wrong: the file is not admitted.
5. Volume must normalize to an integer in its unit; the unit check (Ruling 2.6) uses the median
   of turnover / (close x volume).
"""

from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from decimal import Context, Decimal, InvalidOperation
from fractions import Fraction
from typing import Iterable, List, Optional, Sequence, Tuple

from marketdata.profiles import FieldProfile, NumberFormat, max_dp

_WIDE = Context(prec=400)
UNIT_BAND_LOW = Fraction(9, 10)
UNIT_BAND_HIGH = Fraction(11, 10)


class NumberError(ValueError):
    pass


# --- binary helpers (calculators only; never a source of a Decimal) -----------------------

def _f32(text: str) -> float:
    """The float32 nearest to `text`, held in a Python float (which holds it exactly)."""
    try:
        return struct.unpack("<f", struct.pack("<f", float(text)))[0]
    except (OverflowError, ValueError, struct.error):
        raise NumberError(f"{text!r} is not a finite float32-range number") from None


def shortest_float32(text: str) -> Decimal:
    """The shortest decimal that round-trips through binary32 to the same value as `text`."""
    v = _f32(text)
    for digits in range(1, 10):
        candidate = format(v, f".{digits}g")
        if _f32(candidate) == v:
            return Decimal(candidate)  # built from a string
    return Decimal(format(v, ".9g"))


def significant_digits(d: Decimal) -> int:
    return len(d.normalize().as_tuple().digits)


def decimals_of(d: Decimal) -> int:
    return max(0, -d.normalize().as_tuple().exponent)


def has_float32_signature(text: str) -> bool:
    """Ruling 2.4 item 5: the text equals the 8-significant-digit rendering of its own float32
    value and is longer than that value's float32 shortest round-trip form (474.20001)."""
    d = Decimal(text.strip())
    v = _f32(text)
    return Decimal(format(v, ".8g")) == d and significant_digits(d) > significant_digits(shortest_float32(text))


def is_float32_rendering(text: str) -> bool:
    d = Decimal(text.strip())
    v = _f32(text)
    return d == Decimal(format(v, ".8g")) or d == shortest_float32(text)


def float32_ulp(d: Decimal) -> Fraction:
    """ulp(v) = 2^(floor(log2 v) - 23) for float32 (v > 0)."""
    mantissa, exponent = math.frexp(float(d))  # exponent only; v = m * 2^e, 0.5 <= m < 1
    return Fraction(2) ** (exponent - 1 - 23)


def float64_ulp(d: Decimal) -> Fraction:
    mantissa, exponent = math.frexp(float(d))
    return Fraction(2) ** (exponent - 1 - 52)


def _fraction_to_decimal(f: Fraction) -> Decimal:
    # a power of two or 10^-k: its decimal expansion is finite and the division is exact
    return _WIDE.divide(Decimal(f.numerator), Decimal(f.denominator))


def _is_float32_integer(n: int) -> bool:
    """Float32 integers >= 2^24 are multiples of 2^(k-23) on [2^k, 2^(k+1))."""
    if n < 2 ** 24:
        return True
    k = n.bit_length() - 1
    return n % (2 ** (k - 23)) == 0


def check_field_format(texts: Iterable[str], profile: FieldProfile) -> Optional[str]:
    """The per-file profile check (Ruling 2.4 item 5). None if every value is consistent with
    the declared format, else a message: the profile is wrong and the file is not admitted.
    A.4 item 7 (market-data/1.16 section 11 item 26, on every route; opt-in for the A-share route only in 1.15): a non-integral
    `TEXT_DECIMAL` or `FLOAT64` field with a declared `delivered_dp` that SHOWS more decimals than it fails the check (a float
    rendering in a text field; trailing zeros count: `50.50000` shows 5). Showing fewer is not a failure. A `FLOAT32`
    rendering is exempt (HK Sina files: their decimals are the float32 rendering's)."""
    for raw in texts:
        text = raw.strip()
        if not text:
            return "empty value"
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return f"{text!r} is not a number"
        if profile.integral and (not parsed.is_finite() or parsed != parsed.to_integral_value()):
            return f"{text} is not an integer in its unit (Ruling 2.4 item 6)"
        if profile.integral:
            # Appendix A.4 item 2: integers are tested by float32 SPACING, not by the 8-digit
            # signature (which misfires on integers of 8+ digits: the first real Sina US file's
            # 41000008.0 is such a case). A value that is not a multiple of its float32 spacing
            # cannot be a float32; a multiple is ambiguous and the declared format stands.
            if profile.format is NumberFormat.FLOAT32 and not _is_float32_integer(int(parsed)):
                return f"{text} is not a possible float32 integer (profile says FLOAT32)"
            continue
        if profile.format is not NumberFormat.FLOAT32 and profile.delivered_dp is not None and parsed.is_finite():
            shown = -parsed.as_tuple().exponent  # type: ignore[operator]  # the decimals the text shows, trailing zeros included
            if shown > profile.delivered_dp:
                return (f"{text} shows {shown} decimals but the profile delivers {profile.delivered_dp} "
                        "(Ruling 2.4 item 5; A.4 item 7): the profile is wrong, not the value")
        try:
            if profile.format is NumberFormat.FLOAT32:
                if not is_float32_rendering(text):
                    return f"{text} is not the float32 rendering of its own value (profile says FLOAT32)"
            elif has_float32_signature(text):
                return (f"{text} shows the float32 signature but the profile says "
                        f"{profile.format.value}")
        except NumberError as exc:
            return str(exc)
    return None


def normalize(text: str, fmt: NumberFormat) -> Decimal:
    """Ruling 2.4 item 3. Raises NumberError for anything not a finite decimal."""
    text = text.strip()
    try:
        d = Decimal(text)
    except InvalidOperation:
        raise NumberError(f"{text!r} is not a number") from None
    if not d.is_finite():
        raise NumberError(f"{text!r} is not finite")
    if fmt is NumberFormat.FLOAT32:
        return shortest_float32(text)
    return d  # TEXT_DECIMAL and FLOAT64 (pandas prints the shortest round trip): identity


@dataclass(frozen=True)
class PriceValue:
    value: Decimal
    recovered: bool
    bound: Decimal  # the Ruling 4.2 delta for this value: 0 when recovered
    note: str = ""


def resolve_close(text: str, profile: FieldProfile, market: str,
                  security_class: Optional[str] = None) -> PriceValue:
    """Normalize a close and apply the Ruling 2.4 item 4 validation. Never rounds."""
    value = normalize(text, profile.format)
    if value <= 0:
        raise NumberError(f"{text!r} is not a positive price")
    dp_allowed = max_dp(market, value, security_class)
    on_grid = decimals_of(value) <= dp_allowed
    resolvable = True
    half_ulp: Optional[Fraction] = None
    if profile.format is NumberFormat.FLOAT32:
        ulp = float32_ulp(value)
        resolvable = ulp < Fraction(1, 10 ** dp_allowed)
        half_ulp = ulp / 2
    elif profile.format is NumberFormat.FLOAT64:
        half_ulp = float64_ulp(value) / 2
    if on_grid and resolvable:
        return PriceValue(value, True, Decimal(0))
    if half_ulp is None:  # TEXT_DECIMAL beyond the grid: half a unit of the decimals the source delivers
        delivered = profile.delivered_dp if profile.delivered_dp is not None else decimals_of(value)
        half_ulp = Fraction(1, 2 * 10 ** delivered)
    why = ("beyond the market's maximum decimals" if not on_grid
           else "the format cannot resolve the grid at this price")
    if market == "CN" and security_class is None and not on_grid:
        why += (" (SECURITY_CLASS_UNRESOLVED: no class is known for this listing, so the strict 2-decimal grid "
                "applies, Ruling 2.4 item 4 / Appendix A.1)")
    return PriceValue(value, False, _fraction_to_decimal(half_ulp), why)


def field_bound(profile: FieldProfile, value: Decimal) -> Optional[Decimal]:
    """The V2 (a', market-data/1.4) reference bound `delta_r` of ONE never-grid-validated field (open, high, low),
    from that field's own profile (never copied from another field):

    - FLOAT32: half an ulp in binary32 (there the format is the binding limit);
    - TEXT_DECIMAL or FLOAT64: half a unit of the DECLARED `delivered_dp` (the source's own rounding, which cannot be
      ruled out without a grid);
    - a TEXT_DECIMAL or FLOAT64 field with NO declared `delivered_dp`: None. C2-10 (Ruling V2 (a'), section 9C item 4):
      half an ulp in binary64 bounds only the float RENDERING, not a decimal rounding the source applied first (a
      high or low rounded to 2 dp), so it understates the bound and V2 could classify on noise. The caller must stop
      V2 on that series with method UNKNOWN, label UNVERIFIABLE and the cause PROFILE_INCOMPLETE."""
    if profile.format is NumberFormat.FLOAT32:
        return _fraction_to_decimal(float32_ulp(abs(value) or Decimal(1)) / 2)
    if profile.delivered_dp is not None:
        return _fraction_to_decimal(Fraction(1, 2 * 10 ** profile.delivered_dp))
    return None


def normalize_adjusted(text: str, profile: FieldProfile) -> PriceValue:
    """Adjusted values are not on any grid: normalized by rule 3, never rounded. Their bound is
    half an ulp in the declared format (the 'format bound' of Ruling 2.4)."""
    value = normalize(text, profile.format)
    if profile.format is NumberFormat.FLOAT32:
        half = float32_ulp(abs(value) or Decimal(1)) / 2
    elif profile.format is NumberFormat.FLOAT64:
        half = float64_ulp(abs(value) or Decimal(1)) / 2
    else:
        half = Fraction(1, 2 * 10 ** decimals_of(value))
    return PriceValue(value, False, _fraction_to_decimal(half), "adjusted value: not on the grid")


def normalize_volume(text: str, profile: FieldProfile) -> Decimal:
    """In SOURCE units; must be an integer (Ruling 2.4 item 6)."""
    value = normalize(text, profile.format)
    if value < 0 or value != value.to_integral_value():
        raise NumberError(f"volume {text!r} is not a non-negative integer")
    return value


def volume_unit_check(
    rows: Sequence[Tuple[Decimal, Decimal, Decimal]], shares_per_unit: int
) -> Tuple[Optional[bool], Optional[Fraction]]:
    """Ruling 2.6: the MEDIAN of turnover / (close x volume), over rows with volume > 0, must lie
    within [0.9, 1.1] x the declared shares per unit. Rows are (turnover, close, volume in
    source units). Returns (True/False, median) or (None, None) if no row can be tested."""
    ratios: List[Fraction] = sorted(
        Fraction(t) / (Fraction(c) * Fraction(v)) for t, c, v in rows if v > 0 and c > 0)
    if not ratios:
        return None, None
    n = len(ratios)
    median = ratios[n // 2] if n % 2 else (ratios[n // 2 - 1] + ratios[n // 2]) / 2
    centre = Fraction(shares_per_unit)
    return UNIT_BAND_LOW * centre <= median <= UNIT_BAND_HIGH * centre, median


def row_is_consistent(open_: Decimal, high: Decimal, low: Decimal, close: Decimal) -> bool:
    """Ruling 4.6 item 2: low <= min(open, close) <= max(open, close) <= high."""
    return low <= min(open_, close) <= max(open_, close) <= high
