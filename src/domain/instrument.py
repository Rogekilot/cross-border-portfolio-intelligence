"""Instrument-context domain entities — `Issuer`, `Instrument`, `Listing`
(Tech Plan §3.1, §13.C; PRD §10; `specs/PHASE_B_CP1_IMPLEMENTATION_AUTHORITY.
md` §2.1, `PD-0021`).

**Canonical identity (PD-0021 §2.1, Option A).** Each of the three entities
below carries its own immutable internal `uuid.UUID` — `issuer_id`,
`instrument_id`, `listing_id` — and that internal ID, **never** a ticker,
FIGI, a FIGI+MIC composite, or any vendor ID, is the join/persistence key.
FIGI and MIC remain authoritative *resolution* primitives (PRD §10.1) for
real-world identification, matching, and evidence — never physical database
primary keys.

**The decisive invariant (PD-0021 §2.1).** A correction to an external
identifier (a ticker changing, a FIGI arriving or being corrected, an MIC
mapping being fixed) must be capable of becoming an identity/resolution
*attribute update* on the existing row — never a migration of every
reference that already points at it. Because every entity below is a frozen
dataclass, the concrete mechanic is `dataclasses.replace(listing,
ticker="NEW")`: this produces a new Python object carrying the corrected
attribute and the **same** `listing_id`, and — because of the equality rule
below — that new object still compares equal to, and hashes identically to,
the pre-correction object. Nothing that already holds a reference to the old
object's ID needs to change.

**Entity equality — deliberate, not the dataclass default.** A default
frozen-dataclass `__eq__` compares every field. That is wrong for these three
types for two independent reasons:

1. A ticker/FIGI **correction** (same entity, new attribute value) would
   compare as a *different* entity under field-by-field comparison,
   defeating the invariant above.
2. Two *different* `Listing`s that happen to share a ticker (tickers are not
   globally unique, are reused across exchanges and over time, and are
   explicitly "a user-facing lookup/search attribute, not the database
   primary key" per PRD §10.1) would compare *equal* under field-by-field
   comparison, which is simply wrong — they are different rows.

All three types therefore use `eq=False` plus an explicit, `*_id`-based
`__eq__`/`__hash__` (`domain.entity_identity`): identity, not attribute
content, is what "the same entity" means here. See
`domain.entity_identity`'s module docstring for the full rationale.

**Security type.** `SecurityType` enumerates only the two instrument-bearing
asset types PRD §5.1 names for V1: `COMMON_STOCK`, `ETF`. Cash is not an
`Instrument` (see `domain.cash.CashKey`). **Mutual funds are never added** —
PRD §5.3 lists them explicitly out of V1, and PD-0011 requires a separate
product decision before they could be (Tech Plan §13, "standing
constraints").

**Multiplicity.** Many `Listing`s may reference one `Instrument`
(`instrument_id`) — e.g. a single Alibaba `Instrument` with one `Listing` on
NYSE (BABA) and a separate `Listing` on HKEX (9988), matching PRD §10.3's
worked example. `Listing`s of the same `Instrument` may carry different
`mic`, `exchange`, and `trading_currency` values. Nothing here implies or
computes any pricing/return equivalence between them (e.g. no ADR-vs-
ordinary conversion ratio) — that is a methodology decision this module does
not make (Tech Plan §13.E's Quant boundary).

**External identifiers, kept minimal and unabstracted.** `ticker`, `mic`, and
`figi` are plain typed fields directly on `Listing`, not wrapped in a
generic "external identifier" type. They have distinct semantics (an `mic`
is shared across many listings on one venue; a `ticker` is exchange-scoped
and mutable over time; a `figi` is intended to be globally unique per
listing where assigned) and PD-0021/PRD §10.1 treat them as plain resolution
attributes, not as instances of one interchangeable shape — a generic
wrapper here would be structure with no present justification.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from enum import Enum, unique
from typing import Any, Optional

from domain.currency import CurrencyCode
from domain.entity_identity import identity_eq, identity_hash
from domain.field_validation import require_optional_type, require_exact_bool, require_type


@unique
class SecurityType(Enum):
    """V1 instrument-bearing asset types (PRD §5.1). Exactly these two —
    never mutual funds (PRD §5.3; PD-0011)."""

    COMMON_STOCK = "COMMON_STOCK"
    ETF = "ETF"


@dataclass(frozen=True, eq=False)
class Issuer:
    """The economic/legal issuing entity (e.g. "Alibaba Group Holding
    Limited") — distinct from any one exchange listing (PRD §10.3).

    `issuer_domicile` is a plain optional string (e.g. a country name/code)
    — "where available" per PRD §10.2. CP1-A does not build a country-code
    normalization primitive analogous to `domain.currency.CurrencyCode`:
    this increment's scope explicitly requires the currency primitive and
    says nothing about one for geography, so none is built here.
    """

    issuer_id: uuid.UUID
    name: str
    issuer_domicile: Optional[str] = None

    def __post_init__(self) -> None:
        require_type(self, "issuer_id", self.issuer_id, uuid.UUID)
        require_type(self, "name", self.name, str)
        require_optional_type(self, "issuer_domicile", self.issuer_domicile, str)

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "issuer_id")

    def __hash__(self) -> int:
        return identity_hash(self, "issuer_id")


@dataclass(frozen=True, eq=False)
class Instrument:
    """The security/economic instrument — references its issuing `Issuer`
    (`issuer_id`) and carries a `security_type` (`SecurityType`). Multiple
    `Listing`s (below) may reference one `Instrument`."""

    instrument_id: uuid.UUID
    issuer_id: uuid.UUID
    security_type: SecurityType
    # market-data/1.5 Ruling 7.3 item 1 (ADDITIVE, default None; no CP1 contract changes): the SHARE-CLASS-level FIGI,
    # global across countries, belongs to the instrument and never to a listing.
    share_class_figi: Optional[str] = None

    def __post_init__(self) -> None:
        require_type(self, "instrument_id", self.instrument_id, uuid.UUID)
        require_type(self, "issuer_id", self.issuer_id, uuid.UUID)
        require_type(self, "security_type", self.security_type, SecurityType)
        require_optional_type(self, "share_class_figi", self.share_class_figi, str)

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "instrument_id")

    def __hash__(self) -> int:
        return identity_hash(self, "instrument_id")


@dataclass(frozen=True, eq=False)
class Listing:
    """A venue-specific tradable line — references its `Instrument`
    (`instrument_id`). Carries the external resolution/evidence identifiers
    (PRD §10.1, §10.2): `mic`, `exchange`, `ticker` (a user-facing search
    attribute, never the identity key), `trading_currency` (the listing's
    native currency — never converted by this module), and an optional
    `figi` (`None` is a valid, ordinary state — FIGI is "where available"
    per PRD §10.2, not required on every listing). `is_active` is the
    required status flag (PRD §10.2).
    """

    listing_id: uuid.UUID
    instrument_id: uuid.UUID
    mic: str
    exchange: str
    ticker: str
    trading_currency: CurrencyCode
    figi: Optional[str] = None
    is_active: bool = True
    # market-data/1.5 Ruling 7.3 item 1 (ADDITIVE, default None, last field so no positional use moves): `figi` above is
    # the EXCHANGE-level FIGI only; the COMPOSITE-level FIGI (the security across a country's venues) is this separate
    # attribute. One field holding two levels would make equality joins silently wrong.
    composite_figi: Optional[str] = None

    def __post_init__(self) -> None:
        require_type(self, "listing_id", self.listing_id, uuid.UUID)
        require_type(self, "instrument_id", self.instrument_id, uuid.UUID)
        require_type(self, "mic", self.mic, str)
        require_type(self, "exchange", self.exchange, str)
        require_type(self, "ticker", self.ticker, str)
        require_type(self, "trading_currency", self.trading_currency, CurrencyCode)
        require_optional_type(self, "figi", self.figi, str)
        require_exact_bool(self, "is_active", self.is_active)
        require_optional_type(self, "composite_figi", self.composite_figi, str)

    def __eq__(self, other: object) -> Any:
        return identity_eq(self, other, "listing_id")

    def __hash__(self) -> int:
        return identity_hash(self, "listing_id")
