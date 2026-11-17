"""CP1-A tests for `domain.cash` — the `(account_id, currency)` cash-keying
primitive (PRD §9.4; Tech Plan §13.E).

Run via either:
    python3 -m unittest discover -s tests -p 'test_*.py'      (repository canonical)
    python3 -m unittest discover -s tests/product -v
No `PYTHONPATH` is required for either invocation — see the sys.path setup
below and `tests/product/__init__.py` for why it lives here rather than
there.
"""

import dataclasses
import sys
import unittest
import uuid
from pathlib import Path

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.cash import CashKey  # noqa: E402
from domain.currency import CurrencyCode  # noqa: E402
from domain.field_validation import DomainFieldTypeError  # noqa: E402

# Fixed, deterministic UUID literals — no randomness anywhere in this file.
_ACCOUNT_ID = uuid.UUID("c1111111-1111-1111-1111-111111111111")
_OTHER_ACCOUNT_ID = uuid.UUID("c2222222-2222-2222-2222-222222222222")


class CashKeyDoesNotCollapseCurrenciesTests(unittest.TestCase):
    def test_same_account_different_currency_are_distinct_keys(self) -> None:
        usd = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        hkd = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("HKD"))
        self.assertNotEqual(usd, hkd)

    def test_same_account_three_currencies_are_three_distinct_keys(self) -> None:
        keys = {
            CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode(code))
            for code in ("USD", "HKD", "CNY")
        }
        self.assertEqual(len(keys), 3)

    def test_same_account_and_currency_is_the_same_key(self) -> None:
        a = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("usd"))
        b = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_same_currency_different_account_are_distinct_keys(self) -> None:
        one = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        two = CashKey(account_id=_OTHER_ACCOUNT_ID, currency=CurrencyCode("USD"))
        self.assertNotEqual(one, two)


class CashKeyCarriesNoBalanceTests(unittest.TestCase):
    def test_cash_key_has_no_balance_or_amount_field(self) -> None:
        # CP1-A does not store authoritative cash balances — those are
        # derived state, CP1-C's job. CashKey is a pure keying dimension.
        key = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        field_names = {f.name for f in dataclasses.fields(key)}
        self.assertEqual(field_names, {"account_id", "currency"})


class CashKeyFieldTypeValidationTests(unittest.TestCase):
    """CP1-A correction round, finding F1: CashKey.account_id must be
    uuid.UUID; CashKey.currency must be CurrencyCode — never a raw str."""

    def test_str_account_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            CashKey(
                account_id=str(_ACCOUNT_ID),  # type: ignore[arg-type]
                currency=CurrencyCode("USD"),
            )

    def test_raw_string_currency_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            CashKey(account_id=_ACCOUNT_ID, currency="USD")  # type: ignore[arg-type]

    def test_replace_with_wrong_type_currency_is_rejected(self) -> None:
        key = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(key, currency="HKD")

    def test_replace_with_wrong_type_account_id_is_rejected(self) -> None:
        key = CashKey(account_id=_ACCOUNT_ID, currency=CurrencyCode("USD"))
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(key, account_id=str(_OTHER_ACCOUNT_ID))


if __name__ == "__main__":
    unittest.main()
