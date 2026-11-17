"""CP1-A tests for `domain.portfolio` — `User`/`Portfolio`/`Account` internal
identity and the reporting-currency/native-currency independence invariant
(Tech Plan §13.E; PRD §7.2, §7.3, §8.1; PD-0021 §2.1-§2.2).

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

from domain.currency import CurrencyCode  # noqa: E402
from domain.field_validation import DomainFieldTypeError  # noqa: E402
from domain.instrument import Instrument, Issuer, Listing, SecurityType  # noqa: E402
from domain.portfolio import Account, Portfolio, User  # noqa: E402

# Fixed, deterministic UUID literals — no randomness anywhere in this file.
_USER_ID = uuid.UUID("a1111111-1111-1111-1111-111111111111")
_USER_ID_OTHER = uuid.UUID("a1111111-1111-1111-1111-111111111112")
_PORTFOLIO_ID = uuid.UUID("a2222222-2222-2222-2222-222222222222")
_ACCOUNT_US_BROKER_ID = uuid.UUID("a3333333-3333-3333-3333-333333333333")
_ACCOUNT_FUTU_ID = uuid.UUID("a4444444-4444-4444-4444-444444444444")
_ISSUER_ID = uuid.UUID("b1111111-1111-1111-1111-111111111111")
_INSTRUMENT_ID = uuid.UUID("b2222222-2222-2222-2222-222222222222")
_LISTING_ID = uuid.UUID("b3333333-3333-3333-3333-333333333333")


class UserIdentityTests(unittest.TestCase):
    def test_user_carries_its_own_internal_id(self) -> None:
        user = User(user_id=_USER_ID)
        self.assertEqual(user.user_id, _USER_ID)

    def test_two_users_with_same_id_are_equal(self) -> None:
        self.assertEqual(User(user_id=_USER_ID), User(user_id=_USER_ID))

    def test_two_users_with_different_ids_are_not_equal(self) -> None:
        self.assertNotEqual(User(user_id=_USER_ID), User(user_id=_USER_ID_OTHER))


class PortfolioIdentityAndOwnershipTests(unittest.TestCase):
    def test_portfolio_carries_its_own_internal_id_and_owner(self) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        self.assertEqual(portfolio.portfolio_id, _PORTFOLIO_ID)
        self.assertEqual(portfolio.user_id, _USER_ID)

    def test_portfolio_has_exactly_one_reporting_currency(self) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        currency_fields = [
            f.name
            for f in dataclasses.fields(portfolio)
            if "currency" in f.name
        ]
        self.assertEqual(currency_fields, ["reporting_currency"])

    def test_portfolio_equality_is_id_based(self) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        changed_currency = dataclasses.replace(
            portfolio, reporting_currency=CurrencyCode("HKD")
        )
        self.assertEqual(portfolio, changed_currency)


class AccountIdentityAndContainmentTests(unittest.TestCase):
    def test_account_scoped_to_its_portfolio(self) -> None:
        account = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        self.assertEqual(account.portfolio_id, _PORTFOLIO_ID)

    def test_account_has_no_single_currency_field(self) -> None:
        # PRD §7.3: account containers are organizational, not
        # currency-typed — cash is differentiated by (account, currency),
        # not by an account-level currency attribute.
        account = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        account_field_names = {f.name for f in dataclasses.fields(account)}
        self.assertNotIn("currency", account_field_names)

    def test_two_accounts_in_the_same_portfolio_are_distinct(self) -> None:
        usbroker = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        futu = Account(
            account_id=_ACCOUNT_FUTU_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="Futu HK",
        )
        self.assertNotEqual(usbroker, futu)
        self.assertEqual(usbroker.portfolio_id, futu.portfolio_id)


class ReportingCurrencyIndependentOfListingCurrencyTests(unittest.TestCase):
    """Item 7 of the CP1-A test list: a Portfolio's reporting currency is
    independent of any Listing's trading/native currency — no conversion is
    performed or implied by holding both."""

    def test_usd_reporting_portfolio_can_reference_an_hkd_listing_without_conversion(
        self,
    ) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        issuer = Issuer(issuer_id=_ISSUER_ID, name="Alibaba Group Holding Limited")
        instrument = Instrument(
            instrument_id=_INSTRUMENT_ID,
            issuer_id=issuer.issuer_id,
            security_type=SecurityType.COMMON_STOCK,
        )
        hkex_listing = Listing(
            listing_id=_LISTING_ID,
            instrument_id=instrument.instrument_id,
            mic="XHKG",
            exchange="Hong Kong Stock Exchange",
            ticker="9988",
            trading_currency=CurrencyCode("HKD"),
        )
        # Both currencies stand independently — reporting_currency is never
        # rewritten by, or rewritten onto, the listing's trading_currency.
        self.assertEqual(portfolio.reporting_currency, CurrencyCode("USD"))
        self.assertEqual(hkex_listing.trading_currency, CurrencyCode("HKD"))
        self.assertNotEqual(
            portfolio.reporting_currency, hkex_listing.trading_currency
        )


class UserFieldTypeValidationTests(unittest.TestCase):
    """CP1-A correction round, finding F1: `User.user_id` must be a
    `uuid.UUID`; a str (or any other wrong type) is rejected at
    construction, deterministically."""

    def test_str_user_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            User(user_id=str(_USER_ID))  # type: ignore[arg-type]

    def test_replace_with_wrong_type_user_id_is_rejected(self) -> None:
        user = User(user_id=_USER_ID)
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(user, user_id=str(_USER_ID_OTHER))


class PortfolioFieldTypeValidationTests(unittest.TestCase):
    """F1: Portfolio.portfolio_id, .user_id must be uuid.UUID;
    .reporting_currency must be CurrencyCode — never a raw str."""

    def test_str_portfolio_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Portfolio(
                portfolio_id=str(_PORTFOLIO_ID),  # type: ignore[arg-type]
                user_id=_USER_ID,
                reporting_currency=CurrencyCode("USD"),
            )

    def test_str_user_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Portfolio(
                portfolio_id=_PORTFOLIO_ID,
                user_id=str(_USER_ID),  # type: ignore[arg-type]
                reporting_currency=CurrencyCode("USD"),
            )

    def test_raw_string_reporting_currency_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Portfolio(
                portfolio_id=_PORTFOLIO_ID,
                user_id=_USER_ID,
                reporting_currency="USD",  # type: ignore[arg-type]
            )

    def test_replace_with_wrong_type_reporting_currency_is_rejected(self) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(portfolio, reporting_currency="HKD")

    def test_replace_with_wrong_type_portfolio_id_is_rejected(self) -> None:
        portfolio = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(portfolio, portfolio_id=str(_PORTFOLIO_ID))


class AccountFieldTypeValidationTests(unittest.TestCase):
    """F1: Account.account_id, .portfolio_id must be uuid.UUID; .name must
    be str."""

    def test_str_account_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Account(
                account_id=str(_ACCOUNT_US_BROKER_ID),  # type: ignore[arg-type]
                portfolio_id=_PORTFOLIO_ID,
                name="US Broker",
            )

    def test_str_portfolio_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Account(
                account_id=_ACCOUNT_US_BROKER_ID,
                portfolio_id=str(_PORTFOLIO_ID),  # type: ignore[arg-type]
                name="US Broker",
            )

    def test_non_str_name_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Account(
                account_id=_ACCOUNT_US_BROKER_ID,
                portfolio_id=_PORTFOLIO_ID,
                name=12345,  # type: ignore[arg-type]
            )

    def test_replace_with_wrong_type_name_is_rejected(self) -> None:
        account = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(account, name=12345)


class IdentityRegressionTests(unittest.TestCase):
    """Preserved-identity regression: `User`/`Portfolio`/`Account` equality
    and hash remain exact-class-plus-internal-ID after the F1 correction —
    same class and ID equal with equal hash; a correction via
    `dataclasses.replace` on a non-identity field preserves identity, equal-
    ity and set collapse; different IDs stay unequal; different classes with
    matching UUIDs stay unequal."""

    def test_same_class_same_id_equal_and_equal_hash(self) -> None:
        a = User(user_id=_USER_ID)
        b = User(user_id=_USER_ID)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_account_correction_keeps_same_id_and_stays_equal(self) -> None:
        original = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        corrected = dataclasses.replace(original, name="US Broker Investments")
        self.assertEqual(corrected.account_id, original.account_id)
        self.assertEqual(corrected, original)
        self.assertEqual(hash(corrected), hash(original))

    def test_set_collapses_after_account_correction(self) -> None:
        original = Account(
            account_id=_ACCOUNT_US_BROKER_ID,
            portfolio_id=_PORTFOLIO_ID,
            name="US Broker",
        )
        corrected = dataclasses.replace(original, name="US Broker Investments")
        accounts = {original, corrected}
        self.assertEqual(len(accounts), 1)

    def test_portfolio_correction_keeps_same_id_and_stays_equal_with_hash(
        self,
    ) -> None:
        original = Portfolio(
            portfolio_id=_PORTFOLIO_ID,
            user_id=_USER_ID,
            reporting_currency=CurrencyCode("USD"),
        )
        corrected = dataclasses.replace(
            original, reporting_currency=CurrencyCode("HKD")
        )
        self.assertEqual(corrected, original)
        self.assertEqual(hash(corrected), hash(original))

    def test_different_ids_stay_unequal(self) -> None:
        self.assertNotEqual(
            Account(
                account_id=_ACCOUNT_US_BROKER_ID,
                portfolio_id=_PORTFOLIO_ID,
                name="US Broker",
            ),
            Account(
                account_id=_ACCOUNT_FUTU_ID,
                portfolio_id=_PORTFOLIO_ID,
                name="US Broker",
            ),
        )

    def test_different_classes_with_matching_uuid_stay_unequal(self) -> None:
        # A User and an Account constructed with the numerically-equal UUID
        # value are never equal — identity_eq requires an exact class match
        # first, regardless of internal-ID equality.
        shared_id = _USER_ID
        user = User(user_id=shared_id)
        account = Account(
            account_id=shared_id, portfolio_id=_PORTFOLIO_ID, name="US Broker"
        )
        self.assertNotEqual(user, account)


if __name__ == "__main__":
    unittest.main()
