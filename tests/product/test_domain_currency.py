"""CP1-A tests for `domain.currency` — `CurrencyCode` normalization and the
`Money` native monetary primitive (Tech Plan §13.E; increment scope: currency
primitives, and the hard invariant that money is `Decimal`-only and never
implicitly converted across currencies).

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'      (repository canonical)
    python3 -m unittest discover -s tests/product -v
No `PYTHONPATH` is required for either invocation — see the sys.path setup
below and `tests/product/__init__.py` for why it lives here rather than
there.
"""

import sys
import unittest
from decimal import Decimal
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import (  # noqa: E402
    CurrencyCode,
    CurrencyMismatchError,
    InvalidCurrencyCodeError,
    InvalidMoneyAmountError,
    Money,
    NonFiniteMoneyAmountError,
)

# Three non-ASCII alphabetic characters (Latin capital A/O/U with diaeresis),
# expressed as escapes rather than literal characters for source-encoding
# safety: unicode.isalpha() is True for these, but they are not ASCII.
_NON_ASCII_ALPHA_TRIPLE = "ÄÖÜ"


class CurrencyCodeNormalizationTests(unittest.TestCase):
    def test_lowercase_input_is_normalized_to_uppercase(self) -> None:
        self.assertEqual(CurrencyCode("usd").code, "USD")

    def test_mixed_case_and_surrounding_whitespace_is_normalized(self) -> None:
        self.assertEqual(CurrencyCode("  Hkd  ").code, "HKD")

    def test_already_normalized_code_is_unchanged(self) -> None:
        self.assertEqual(CurrencyCode("CNY").code, "CNY")

    def test_str_returns_the_normalized_code(self) -> None:
        self.assertEqual(str(CurrencyCode("usd")), "USD")

    def test_not_three_letters_is_rejected(self) -> None:
        with self.assertRaises(InvalidCurrencyCodeError):
            CurrencyCode("US")
        with self.assertRaises(InvalidCurrencyCodeError):
            CurrencyCode("USDA")

    def test_non_alphabetic_is_rejected(self) -> None:
        with self.assertRaises(InvalidCurrencyCodeError):
            CurrencyCode("US1")

    def test_non_ascii_alphabetic_is_rejected(self) -> None:
        # str.isalpha() is True for non-ASCII letters too; this module
        # normalizes to (and requires) ASCII only — documented format-only
        # scope, not an ISO-4217 membership check.
        with self.assertRaises(InvalidCurrencyCodeError):
            CurrencyCode(_NON_ASCII_ALPHA_TRIPLE)

    def test_non_string_input_is_rejected(self) -> None:
        with self.assertRaises(InvalidCurrencyCodeError):
            CurrencyCode(123)  # type: ignore[arg-type]

    def test_syntactically_well_formed_but_not_a_real_iso4217_code_is_accepted(
        self,
    ) -> None:
        # This module does NOT implement full ISO-4217 membership validation
        # (documented in domain.currency's module docstring). "ZZZ" is not an
        # assigned ISO-4217 currency; this module carries no list of assigned
        # codes to check it against, so it is accepted as format-valid.
        self.assertEqual(CurrencyCode("zzz").code, "ZZZ")

    def test_not_hardcoded_to_usd_hkd_cny_only(self) -> None:
        # Any well-formed three-letter code is accepted — a format
        # primitive, not an enum of the three currencies this product's
        # example markets happen to use.
        for code in ("USD", "HKD", "CNY", "EUR", "GBP", "JPY"):
            with self.subTest(code=code):
                self.assertEqual(CurrencyCode(code).code, code)


class CurrencyCodeEqualityTests(unittest.TestCase):
    def test_equal_codes_compare_equal_and_hash_equal(self) -> None:
        a = CurrencyCode("usd")
        b = CurrencyCode("USD")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_different_codes_compare_unequal(self) -> None:
        self.assertNotEqual(CurrencyCode("USD"), CurrencyCode("HKD"))


class MoneyDecimalOnlyTests(unittest.TestCase):
    def test_decimal_amount_is_accepted(self) -> None:
        m = Money(Decimal("100.50"), CurrencyCode("USD"))
        self.assertEqual(m.amount, Decimal("100.50"))

    def test_float_amount_is_rejected(self) -> None:
        with self.assertRaises(InvalidMoneyAmountError):
            Money(100.50, CurrencyCode("USD"))  # type: ignore[arg-type]

    def test_int_amount_is_rejected_not_silently_coerced(self) -> None:
        # Decimal only, per this increment's hard invariant — an int is not
        # a Decimal, and this module does not silently coerce it.
        with self.assertRaises(InvalidMoneyAmountError):
            Money(100, CurrencyCode("USD"))  # type: ignore[arg-type]

    def test_non_currency_code_currency_is_rejected(self) -> None:
        with self.assertRaises(TypeError):
            Money(Decimal("1.00"), "USD")  # type: ignore[arg-type]


class MoneyCurrencyCoexistenceTests(unittest.TestCase):
    def test_usd_hkd_cny_are_all_independently_representable(self) -> None:
        usd = Money(Decimal("100.00"), CurrencyCode("USD"))
        hkd = Money(Decimal("780.00"), CurrencyCode("HKD"))
        cny = Money(Decimal("710.00"), CurrencyCode("CNY"))
        # No conversion is performed or implied — each retains its own
        # currency and amount, independently of the other two.
        self.assertEqual(usd.currency.code, "USD")
        self.assertEqual(hkd.currency.code, "HKD")
        self.assertEqual(cny.currency.code, "CNY")


class MoneySameCurrencyArithmeticTests(unittest.TestCase):
    def test_add_same_currency_sums_amounts(self) -> None:
        a = Money(Decimal("10.00"), CurrencyCode("USD"))
        b = Money(Decimal("5.25"), CurrencyCode("USD"))
        self.assertEqual((a + b).amount, Decimal("15.25"))

    def test_subtract_same_currency(self) -> None:
        a = Money(Decimal("10.00"), CurrencyCode("USD"))
        b = Money(Decimal("5.25"), CurrencyCode("USD"))
        self.assertEqual((a - b).amount, Decimal("4.75"))


class MoneyCrossCurrencyRefusalTests(unittest.TestCase):
    """P8 / Tech Plan §13.E: no implicit FX. Combining `Money` in different
    currencies must be refused, never silently converted or fabricated."""

    def test_add_different_currencies_raises(self) -> None:
        usd = Money(Decimal("100.00"), CurrencyCode("USD"))
        hkd = Money(Decimal("780.00"), CurrencyCode("HKD"))
        with self.assertRaises(CurrencyMismatchError):
            usd + hkd

    def test_subtract_different_currencies_raises(self) -> None:
        usd = Money(Decimal("100.00"), CurrencyCode("USD"))
        cny = Money(Decimal("710.00"), CurrencyCode("CNY"))
        with self.assertRaises(CurrencyMismatchError):
            usd - cny

    def test_no_conversion_method_exists_on_money(self) -> None:
        # This module deliberately builds no FX engine and no conversion
        # boundary type (increment scope, hard invariant 4). Pinning the
        # absence of obvious method names so a future addition shows in a
        # diff rather than silently reintroducing implicit FX here.
        usd = Money(Decimal("1.00"), CurrencyCode("USD"))
        for attr in ("convert", "to", "to_currency", "in_currency", "fx_convert"):
            self.assertFalse(
                hasattr(usd, attr),
                f"Money must not expose a {attr!r} conversion method (no FX "
                "engine in CP1-A).",
            )


class MoneyFiniteAmountTests(unittest.TestCase):
    """CP1-A correction round, finding F2: `Money.amount` must be a *finite*
    `decimal.Decimal` — `Decimal.is_finite()`, checked after the existing
    `Decimal` type check, so float/int amounts keep raising
    `InvalidMoneyAmountError` exactly as before this round. Never compares
    an sNaN (`==`, `<`, etc.) anywhere here — every assertion below tests
    the constructor invariant directly via `assertRaises`/`assertEqual` on
    ordinary, already-constructed values."""

    def test_finite_positive_amount_is_accepted(self) -> None:
        m = Money(Decimal("100.50"), CurrencyCode("USD"))
        self.assertEqual(m.amount, Decimal("100.50"))

    def test_finite_zero_amount_is_accepted(self) -> None:
        m = Money(Decimal("0"), CurrencyCode("USD"))
        self.assertEqual(m.amount, Decimal("0"))

    def test_finite_negative_amount_is_accepted(self) -> None:
        # Nothing in Money's current semantics restricts sign — a negative
        # finite Decimal (e.g. representing a liability/debit) constructs
        # cleanly, same as any other finite Decimal.
        m = Money(Decimal("-42.13"), CurrencyCode("USD"))
        self.assertEqual(m.amount, Decimal("-42.13"))

    def test_nan_amount_is_rejected(self) -> None:
        with self.assertRaises(NonFiniteMoneyAmountError):
            Money(Decimal("NaN"), CurrencyCode("USD"))

    def test_signaling_nan_amount_is_rejected(self) -> None:
        # Decimal("sNaN") constructs without raising; is_finite() is a quiet
        # predicate that does not raise on sNaN either. This test asserts
        # only the constructor's own behavior — no comparison of the sNaN
        # value is performed anywhere in this test.
        with self.assertRaises(NonFiniteMoneyAmountError):
            Money(Decimal("sNaN"), CurrencyCode("USD"))

    def test_positive_infinity_amount_is_rejected(self) -> None:
        with self.assertRaises(NonFiniteMoneyAmountError):
            Money(Decimal("Infinity"), CurrencyCode("USD"))

    def test_negative_infinity_amount_is_rejected(self) -> None:
        with self.assertRaises(NonFiniteMoneyAmountError):
            Money(Decimal("-Infinity"), CurrencyCode("USD"))

    def test_float_amount_still_rejected_as_wrong_type_not_non_finite(self) -> None:
        # float rejection is InvalidMoneyAmountError (a type violation,
        # unchanged by this round) — not NonFiniteMoneyAmountError (a
        # content violation on an already-Decimal value).
        with self.assertRaises(InvalidMoneyAmountError):
            Money(100.50, CurrencyCode("USD"))  # type: ignore[arg-type]

    def test_int_amount_still_rejected_as_wrong_type_not_non_finite(self) -> None:
        with self.assertRaises(InvalidMoneyAmountError):
            Money(100, CurrencyCode("USD"))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
