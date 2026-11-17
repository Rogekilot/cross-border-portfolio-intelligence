"""Strict transport shapes; financial validity remains in the issued domain/store."""
from __future__ import annotations

import datetime as dt
import re
import uuid
from decimal import Decimal
from fractions import Fraction
from typing import Literal

from pydantic import Field, StrictBool, StrictStr, field_validator

from domain.ledger import numeric_bounds_violation
from web_api.app import StrictModel


def decimal_text(value, *, zero=False):
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,29})(?:\.[0-9]{1,24})?", value):
        raise ValueError("Use an unsigned exact decimal, below 1E30 and at most 24 decimal places")
    number = Decimal(value)
    if number < 0 or not zero and number == 0 or numeric_bounds_violation(number):
        raise ValueError("A positive bounded exact decimal is required")
    return value


def date_text(value):
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValueError("Use YYYY-MM-DD")
    dt.date.fromisoformat(value)
    return value


def uuid_text(value):
    if str(uuid.UUID(value)) != value:
        raise ValueError("Use a canonical UUID")
    return value


class BoughtAmount(StrictModel):
    amount: StrictStr
    currency: StrictStr = Field(pattern=r"^[A-Z]{3}$")
    _amount = field_validator("amount")(decimal_text)


class Ratio(StrictModel):
    new_units: StrictStr
    old_units: StrictStr
    _values = field_validator("new_units", "old_units")(decimal_text)


class EventInput(StrictModel):
    event_type: Literal["BUY", "SELL", "DIVIDEND", "INTEREST", "FEE", "TAX", "DEPOSIT", "WITHDRAWAL", "TRANSFER_IN", "TRANSFER_OUT", "SPLIT", "INTEREST_CHARGED", "CURRENCY_CONVERSION", "OPENING_POSITION", "OPENING_CASH"]
    account_id: StrictStr
    event_date: StrictStr
    currency: StrictStr = Field(pattern=r"^[A-Z]{3}$")
    listing_id: StrictStr | None = None
    quantity: StrictStr | None = None
    amount: StrictStr | None = None
    cost_basis: StrictStr | None = None
    bought_amount: BoughtAmount | None = None
    split_ratio: Ratio | None = None
    counterparty_account_id: StrictStr | None = None
    settlement_date: StrictStr | None = None
    ex_date: StrictStr | None = None
    acquired_on: StrictStr | None = None

    _ids = field_validator("account_id")(uuid_text)
    _date = field_validator("event_date")(date_text)

    @field_validator("listing_id", "counterparty_account_id")
    @classmethod
    def optional_id(cls, value):
        return None if value is None else uuid_text(value)

    @field_validator("quantity", "amount")
    @classmethod
    def optional_decimal(cls, value):
        return None if value is None else decimal_text(value)

    @field_validator("cost_basis")
    @classmethod
    def optional_basis(cls, value):
        return None if value is None else decimal_text(value, zero=True)

    @field_validator("settlement_date", "ex_date", "acquired_on")
    @classmethod
    def optional_date(cls, value):
        return None if value is None else date_text(value)


class CommandBase(StrictModel):
    operation_id: StrictStr
    expected_revision_id: StrictStr
    as_of: StrictStr
    _ids = field_validator("operation_id", "expected_revision_id")(uuid_text)
    _date = field_validator("as_of")(date_text)


class LedgerCommand(CommandBase):
    operation: Literal["APPEND", "CORRECT", "REVERSE", "ADD_ACCOUNT"]
    events: list[EventInput] = Field(default_factory=list, max_length=32)
    target_event_ids: list[StrictStr] = Field(default_factory=list, max_length=32)
    account_name: StrictStr | None = Field(default=None, max_length=80)

    @field_validator("target_event_ids")
    @classmethod
    def targets(cls, values):
        if len(set(values)) != len(values):
            raise ValueError("Duplicate correction/reversal target")
        return [uuid_text(value) for value in values]


class PolicyInput(StrictModel):
    policy_id: StrictStr
    source_kind: Literal["CP4", "CP5"]
    metric_id: StrictStr = Field(min_length=1, max_length=100)
    semantic_key: StrictStr = Field(min_length=1, max_length=128)
    scope_kind: Literal["PORTFOLIO", "ACCOUNT"]
    account_id: StrictStr | None = None
    subject: list[StrictStr] = Field(default_factory=list, max_length=8)
    direction: Literal["MAXIMUM", "MINIMUM"]
    limit: StrictStr = Field(min_length=1, max_length=128)
    effective_from: StrictStr
    effective_until: StrictStr | None = None
    evidence: StrictStr = Field(min_length=1, max_length=1000)
    _id = field_validator("policy_id")(uuid_text)
    _date = field_validator("effective_from")(date_text)

    @field_validator("limit")
    @classmethod
    def exact_limit(cls, value):
        if not re.fullmatch(r"-?(?:[0-9]{1,30}/[1-9][0-9]{0,29}|[0-9]{1,30}(?:\.[0-9]{1,24})?)", value):
            raise ValueError("Use an exact decimal or numerator/denominator; no percentage conversion is inferred")
        Fraction(value)
        return value

    @field_validator("effective_until")
    @classmethod
    def optional_date(cls, value):
        return None if value is None else date_text(value)

    @field_validator("evidence")
    @classmethod
    def evidence_text(cls, value):
        if not value.strip() or any(ord(char) < 32 for char in value):
            raise ValueError("Explicit visible confirmation evidence is required")
        return value


class BenchmarkInput(StrictModel):
    action: Literal["KEEP", "CLEAR", "SELECT"]
    benchmark_id: StrictStr | None = Field(default=None, max_length=64)
    selected_on: StrictStr | None = None
    _date = field_validator("selected_on")(lambda value: None if value is None else date_text(value))


class PreferencesCommand(CommandBase):
    policies: list[PolicyInput] = Field(max_length=32)
    policies_confirmed: StrictBool
    benchmark: BenchmarkInput
