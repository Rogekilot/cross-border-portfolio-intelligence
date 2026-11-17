"""CP1-A tests for `domain.instrument` — `Issuer`/`Instrument`/`Listing`
internal identity, external-identifier correction, and the identity-based
equality rule (Tech Plan §13.C; PD-0021 §2.1; PRD §10).

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
from typing import Optional

_SRC = Path(__file__).resolve().parents[2] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from domain.currency import CurrencyCode  # noqa: E402
from domain.field_validation import DomainFieldTypeError  # noqa: E402
from domain.instrument import Instrument, Issuer, Listing, SecurityType  # noqa: E402

# Fixed, deterministic UUID literals — no randomness anywhere in this file.
_ISSUER_ALIBABA = uuid.UUID("11111111-1111-1111-1111-111111111111")
_INSTRUMENT_ALIBABA = uuid.UUID("22222222-2222-2222-2222-222222222222")
_LISTING_BABA_NYSE = uuid.UUID("33333333-3333-3333-3333-333333333333")
_LISTING_9988_HKEX = uuid.UUID("44444444-4444-4444-4444-444444444444")
_LISTING_OTHER = uuid.UUID("55555555-5555-5555-5555-555555555555")


def _alibaba_issuer() -> Issuer:
    return Issuer(issuer_id=_ISSUER_ALIBABA, name="Alibaba Group Holding Limited")


def _alibaba_instrument() -> Instrument:
    return Instrument(
        instrument_id=_INSTRUMENT_ALIBABA,
        issuer_id=_ISSUER_ALIBABA,
        security_type=SecurityType.COMMON_STOCK,
    )


def _baba_nyse_listing(ticker: str = "BABA", figi: Optional[str] = None) -> Listing:
    return Listing(
        listing_id=_LISTING_BABA_NYSE,
        instrument_id=_INSTRUMENT_ALIBABA,
        mic="XNYS",
        exchange="New York Stock Exchange",
        ticker=ticker,
        trading_currency=CurrencyCode("USD"),
        figi=figi,
    )


def _listing_9988_hkex(ticker: str = "9988", figi: Optional[str] = None) -> Listing:
    return Listing(
        listing_id=_LISTING_9988_HKEX,
        instrument_id=_INSTRUMENT_ALIBABA,
        mic="XHKG",
        exchange="Hong Kong Stock Exchange",
        ticker=ticker,
        trading_currency=CurrencyCode("HKD"),
        figi=figi,
    )


class InternalIdIndependentOfExternalIdentifiersTests(unittest.TestCase):
    def test_issuer_instrument_listing_each_have_their_own_internal_id(self) -> None:
        issuer = _alibaba_issuer()
        instrument = _alibaba_instrument()
        listing = _baba_nyse_listing()
        self.assertEqual(issuer.issuer_id, _ISSUER_ALIBABA)
        self.assertEqual(instrument.instrument_id, _INSTRUMENT_ALIBABA)
        self.assertEqual(listing.listing_id, _LISTING_BABA_NYSE)
        # Internal IDs are independent of each other and of any external
        # identifier — no field derives one from ticker/FIGI/MIC.
        self.assertNotEqual(issuer.issuer_id, instrument.instrument_id)
        self.assertNotEqual(instrument.instrument_id, listing.listing_id)

    def test_instrument_references_issuer_by_internal_id(self) -> None:
        instrument = _alibaba_instrument()
        self.assertEqual(instrument.issuer_id, _ISSUER_ALIBABA)

    def test_listing_references_instrument_by_internal_id(self) -> None:
        listing = _baba_nyse_listing()
        self.assertEqual(listing.instrument_id, _INSTRUMENT_ALIBABA)


class MissingFigiTests(unittest.TestCase):
    def test_missing_figi_is_a_valid_listing(self) -> None:
        listing = _baba_nyse_listing(figi=None)
        self.assertIsNone(listing.figi)

    def test_figi_defaults_to_none_when_not_supplied(self) -> None:
        listing = Listing(
            listing_id=_LISTING_BABA_NYSE,
            instrument_id=_INSTRUMENT_ALIBABA,
            mic="XNYS",
            exchange="New York Stock Exchange",
            ticker="BABA",
            trading_currency=CurrencyCode("USD"),
        )
        self.assertIsNone(listing.figi)

    def test_present_figi_is_also_valid(self) -> None:
        listing = _baba_nyse_listing(figi="BBG000BBQCY0")
        self.assertEqual(listing.figi, "BBG000BBQCY0")


class MultipleListingsPerInstrumentTests(unittest.TestCase):
    def test_two_listings_reference_the_same_instrument(self) -> None:
        nyse = _baba_nyse_listing()
        hkex = _listing_9988_hkex()
        self.assertEqual(nyse.instrument_id, hkex.instrument_id)
        self.assertEqual(nyse.instrument_id, _INSTRUMENT_ALIBABA)

    def test_the_two_listings_are_themselves_distinct_entities(self) -> None:
        nyse = _baba_nyse_listing()
        hkex = _listing_9988_hkex()
        self.assertNotEqual(nyse, hkex)
        self.assertNotEqual(nyse.listing_id, hkex.listing_id)


class ListingsDifferByMicAndCurrencyTests(unittest.TestCase):
    def test_mic_differs_across_listings_of_one_instrument(self) -> None:
        nyse = _baba_nyse_listing()
        hkex = _listing_9988_hkex()
        self.assertEqual(nyse.mic, "XNYS")
        self.assertEqual(hkex.mic, "XHKG")
        self.assertNotEqual(nyse.mic, hkex.mic)

    def test_trading_currency_differs_across_listings_of_one_instrument(self) -> None:
        nyse = _baba_nyse_listing()
        hkex = _listing_9988_hkex()
        self.assertEqual(nyse.trading_currency, CurrencyCode("USD"))
        self.assertEqual(hkex.trading_currency, CurrencyCode("HKD"))
        self.assertNotEqual(nyse.trading_currency, hkex.trading_currency)


class ExternalIdentifierCorrectionPreservesIdentityTests(unittest.TestCase):
    """PD-0021's decisive invariant: a correction to an external identifier
    is an attribute update on the existing row, never a migration of
    everything that already references its internal ID."""

    def test_correcting_ticker_keeps_the_same_internal_id(self) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        corrected = dataclasses.replace(original, ticker="BABA-NEW")
        self.assertEqual(corrected.listing_id, original.listing_id)
        self.assertEqual(corrected.ticker, "BABA-NEW")
        self.assertEqual(original.ticker, "BABA")  # original is untouched

    def test_correcting_ticker_produces_an_entity_still_equal_to_the_original(
        self,
    ) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        corrected = dataclasses.replace(original, ticker="BABA-NEW")
        # Same internal ID -> same entity under this module's identity-based
        # equality, even though the ticker attribute now differs.
        self.assertEqual(corrected, original)
        self.assertEqual(hash(corrected), hash(original))

    def test_correcting_figi_keeps_the_same_internal_id(self) -> None:
        original = _baba_nyse_listing(figi=None)
        corrected = dataclasses.replace(original, figi="BBG000BBQCY0")
        self.assertEqual(corrected.listing_id, original.listing_id)
        self.assertEqual(corrected.figi, "BBG000BBQCY0")
        self.assertEqual(corrected, original)


class TickerIsNotCanonicalIdentityTests(unittest.TestCase):
    def test_two_listings_with_the_same_ticker_are_distinct_entities(self) -> None:
        # Two different, unrelated listings that happen to reuse a ticker
        # string (tickers are recycled across exchanges/over time, per PRD
        # §10.1) must not compare equal.
        one = Listing(
            listing_id=_LISTING_BABA_NYSE,
            instrument_id=_INSTRUMENT_ALIBABA,
            mic="XNYS",
            exchange="New York Stock Exchange",
            ticker="ABC",
            trading_currency=CurrencyCode("USD"),
        )
        other = Listing(
            listing_id=_LISTING_OTHER,
            instrument_id=_INSTRUMENT_ALIBABA,
            mic="XNYS",
            exchange="New York Stock Exchange",
            ticker="ABC",
            trading_currency=CurrencyCode("USD"),
        )
        self.assertNotEqual(one, other)
        self.assertNotEqual(one.listing_id, other.listing_id)

    def test_a_re_ticker_is_the_same_entity(self) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        re_tickered = dataclasses.replace(original, ticker="BABAX")
        self.assertEqual(original, re_tickered)


class EqualityHashSerializationDoesNotUseTickerOrFigiTests(unittest.TestCase):
    def test_hash_is_stable_across_a_ticker_correction(self) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        corrected = dataclasses.replace(original, ticker="BABA-NEW")
        self.assertEqual(hash(original), hash(corrected))

    def test_set_membership_collapses_same_id_different_ticker(self) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        corrected = dataclasses.replace(original, ticker="BABA-NEW")
        listings = {original, corrected}
        # Same internal ID -> one entity, regardless of two distinct Python
        # objects with different ticker attribute values.
        self.assertEqual(len(listings), 1)

    def test_dataclasses_asdict_serializes_ticker_and_figi_as_plain_attributes(
        self,
    ) -> None:
        # Serialization (dataclasses.asdict) includes ticker/FIGI as ordinary
        # data fields — it is not, and must not become, an identity
        # computation. Equality/hash (tested above) never consult this dict;
        # this test only pins that the dict form carries the attribute
        # values, not that it participates in identity.
        listing = _baba_nyse_listing(ticker="BABA", figi="BBG000BBQCY0")
        as_dict = dataclasses.asdict(listing)
        self.assertEqual(as_dict["ticker"], "BABA")
        self.assertEqual(as_dict["figi"], "BBG000BBQCY0")
        self.assertEqual(as_dict["listing_id"], listing.listing_id)

    def test_issuer_equality_is_id_based_not_name_based(self) -> None:
        a = Issuer(issuer_id=_ISSUER_ALIBABA, name="Alibaba Group Holding Limited")
        b = Issuer(issuer_id=_ISSUER_ALIBABA, name="Alibaba (corrected name)")
        self.assertEqual(a, b)

    def test_instrument_equality_is_id_based(self) -> None:
        # Demonstrates equality is id-based, not attribute-based, for
        # Instrument as well (security_type is not an external identifier in
        # the ticker/FIGI sense, but the same identity-comparison mechanism
        # governs every entity in this module).
        a = _alibaba_instrument()
        b = dataclasses.replace(a, security_type=SecurityType.ETF)
        self.assertEqual(a, b)


class EqualityWithUnrelatedTypeTests(unittest.TestCase):
    def test_listing_does_not_equal_a_non_listing_object(self) -> None:
        listing = _baba_nyse_listing()
        self.assertNotEqual(listing, "BABA")
        self.assertNotEqual(listing, 42)

    def test_listing_does_not_equal_an_issuer_even_with_related_ids(self) -> None:
        listing = _baba_nyse_listing()
        issuer = _alibaba_issuer()
        self.assertNotEqual(listing, issuer)


class SecurityTypeIsV1OnlyTests(unittest.TestCase):
    def test_exactly_two_members(self) -> None:
        self.assertEqual({m.value for m in SecurityType}, {"COMMON_STOCK", "ETF"})
        self.assertEqual(len(SecurityType), 2)

    def test_mutual_fund_is_not_a_member(self) -> None:
        self.assertNotIn("MUTUAL_FUND", {m.value for m in SecurityType})
        self.assertNotIn("MUTUAL_FUND", SecurityType.__members__)


class IssuerFieldTypeValidationTests(unittest.TestCase):
    """F1: Issuer.issuer_id must be uuid.UUID; .name must be str;
    .issuer_domicile must be str or None (None stays valid)."""

    def test_str_issuer_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Issuer(issuer_id=str(_ISSUER_ALIBABA), name="Alibaba")  # type: ignore[arg-type]

    def test_non_str_name_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Issuer(issuer_id=_ISSUER_ALIBABA, name=12345)  # type: ignore[arg-type]

    def test_none_issuer_domicile_is_still_accepted(self) -> None:
        issuer = Issuer(issuer_id=_ISSUER_ALIBABA, name="Alibaba", issuer_domicile=None)
        self.assertIsNone(issuer.issuer_domicile)

    def test_str_issuer_domicile_is_accepted(self) -> None:
        issuer = Issuer(
            issuer_id=_ISSUER_ALIBABA, name="Alibaba", issuer_domicile="KY"
        )
        self.assertEqual(issuer.issuer_domicile, "KY")

    def test_non_str_non_none_issuer_domicile_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Issuer(
                issuer_id=_ISSUER_ALIBABA,
                name="Alibaba",
                issuer_domicile=42,  # type: ignore[arg-type]
            )

    def test_replace_with_wrong_type_issuer_id_is_rejected(self) -> None:
        issuer = _alibaba_issuer()
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(issuer, issuer_id=str(_ISSUER_ALIBABA))


class InstrumentFieldTypeValidationTests(unittest.TestCase):
    """F1: Instrument.instrument_id, .issuer_id must be uuid.UUID;
    .security_type must be an actual SecurityType member, never a raw
    string."""

    def test_str_instrument_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Instrument(
                instrument_id=str(_INSTRUMENT_ALIBABA),  # type: ignore[arg-type]
                issuer_id=_ISSUER_ALIBABA,
                security_type=SecurityType.COMMON_STOCK,
            )

    def test_str_issuer_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Instrument(
                instrument_id=_INSTRUMENT_ALIBABA,
                issuer_id=str(_ISSUER_ALIBABA),  # type: ignore[arg-type]
                security_type=SecurityType.COMMON_STOCK,
            )

    def test_raw_string_security_type_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Instrument(
                instrument_id=_INSTRUMENT_ALIBABA,
                issuer_id=_ISSUER_ALIBABA,
                security_type="COMMON_STOCK",  # type: ignore[arg-type]
            )

    def test_replace_with_wrong_type_security_type_is_rejected(self) -> None:
        instrument = _alibaba_instrument()
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(instrument, security_type="ETF")


class ListingFieldTypeValidationTests(unittest.TestCase):
    """F1: every Listing field validated — listing_id/instrument_id as
    uuid.UUID; mic/exchange/ticker as str; trading_currency as CurrencyCode;
    figi as str-or-None; is_active as an exact bool (1/0/"true" all
    rejected)."""

    def test_str_listing_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=str(_LISTING_BABA_NYSE),  # type: ignore[arg-type]
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
            )

    def test_str_instrument_id_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=str(_INSTRUMENT_ALIBABA),  # type: ignore[arg-type]
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
            )

    def test_non_str_mic_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic=1234,  # type: ignore[arg-type]
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
            )

    def test_non_str_exchange_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange=1234,  # type: ignore[arg-type]
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
            )

    def test_non_str_ticker_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker=1234,  # type: ignore[arg-type]
                trading_currency=CurrencyCode("USD"),
            )

    def test_raw_string_trading_currency_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency="USD",  # type: ignore[arg-type]
            )

    def test_none_figi_is_still_accepted(self) -> None:
        listing = _baba_nyse_listing(figi=None)
        self.assertIsNone(listing.figi)

    def test_non_str_non_none_figi_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
                figi=987654,  # type: ignore[arg-type]
            )

    def test_is_active_true_and_false_are_accepted(self) -> None:
        active = Listing(
            listing_id=_LISTING_BABA_NYSE,
            instrument_id=_INSTRUMENT_ALIBABA,
            mic="XNYS",
            exchange="New York Stock Exchange",
            ticker="BABA",
            trading_currency=CurrencyCode("USD"),
            is_active=True,
        )
        inactive = dataclasses.replace(active, is_active=False)
        self.assertTrue(active.is_active)
        self.assertFalse(inactive.is_active)

    def test_is_active_int_one_is_rejected(self) -> None:
        # bool subclasses int in Python; 1 must still be rejected because
        # type(1) is bool is False.
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
                is_active=1,  # type: ignore[arg-type]
            )

    def test_is_active_int_zero_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
                is_active=0,  # type: ignore[arg-type]
            )

    def test_is_active_string_true_is_rejected(self) -> None:
        with self.assertRaises(DomainFieldTypeError):
            Listing(
                listing_id=_LISTING_BABA_NYSE,
                instrument_id=_INSTRUMENT_ALIBABA,
                mic="XNYS",
                exchange="New York Stock Exchange",
                ticker="BABA",
                trading_currency=CurrencyCode("USD"),
                is_active="true",  # type: ignore[arg-type]
            )

    def test_replace_with_wrong_type_ticker_is_rejected(self) -> None:
        original = _baba_nyse_listing(ticker="BABA")
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(original, ticker=12345)

    def test_replace_with_wrong_type_is_active_is_rejected(self) -> None:
        original = _baba_nyse_listing()
        with self.assertRaises(DomainFieldTypeError):
            dataclasses.replace(original, is_active=1)


class AdditionalIdentityRegressionTests(unittest.TestCase):
    """Preserved-identity regression beyond the equality tests already above
    in this file: explicit hash-equality and set-collapse for Issuer and
    Instrument, and a different-classes-matching-UUID case for
    Instrument/Issuer."""

    def test_issuer_correction_keeps_equal_hash(self) -> None:
        a = _alibaba_issuer()
        b = dataclasses.replace(a, name="Alibaba (corrected name)")
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_set_collapses_after_issuer_name_correction(self) -> None:
        a = _alibaba_issuer()
        b = dataclasses.replace(a, name="Alibaba (corrected name)")
        issuers = {a, b}
        self.assertEqual(len(issuers), 1)

    def test_instrument_correction_keeps_equal_hash(self) -> None:
        a = _alibaba_instrument()
        b = dataclasses.replace(a, security_type=SecurityType.ETF)
        self.assertEqual(a, b)
        self.assertEqual(hash(a), hash(b))

    def test_set_collapses_after_instrument_security_type_correction(self) -> None:
        a = _alibaba_instrument()
        b = dataclasses.replace(a, security_type=SecurityType.ETF)
        instruments = {a, b}
        self.assertEqual(len(instruments), 1)

    def test_instrument_and_issuer_with_matching_uuid_stay_unequal(self) -> None:
        shared_id = _ISSUER_ALIBABA
        issuer = Issuer(issuer_id=shared_id, name="Alibaba")
        instrument = Instrument(
            instrument_id=shared_id,
            issuer_id=_ISSUER_ALIBABA,
            security_type=SecurityType.COMMON_STOCK,
        )
        self.assertNotEqual(issuer, instrument)


if __name__ == "__main__":
    unittest.main()
