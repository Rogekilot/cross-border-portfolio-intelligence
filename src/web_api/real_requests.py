"""Strict E1 intent, deliberately incapable of expressing financial portfolio rows."""
import datetime as dt
import uuid
from typing import Literal

from pydantic import Field, StrictBool, StrictStr, ValidationError, field_validator
from web_api.app import StrictModel
from web_api.real_source_contexts import MODE, RealSourceError, strict_json


class RealPortfolioGateRequest(StrictModel):
    operation_id: StrictStr
    mode: Literal[MODE]
    source_context_id: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    expected_configuration_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    release_id: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    as_of: StrictStr
    constructed_ledger_acknowledged: StrictBool

    @field_validator("operation_id")
    @classmethod
    def identifier(cls, value):
        if str(uuid.UUID(value)) != value:
            raise ValueError("Canonical UUID required")
        return value

    @field_validator("as_of")
    @classmethod
    def date(cls, value):
        if len(value) != 10 or dt.date.fromisoformat(value).isoformat() != value:
            raise ValueError("Exact ISO date required")
        return value

    @field_validator("constructed_ledger_acknowledged")
    @classmethod
    def acknowledged(cls, value):
        if value is not True:
            raise ValueError("Constructed non-personal input acknowledgement required")
        return value


def parse_create_gate(raw_json_bytes):
    try:
        if len(raw_json_bytes) > 32768:
            raise ValueError("bounded JSON required")
        return RealPortfolioGateRequest.model_validate(strict_json(raw_json_bytes)).model_dump()
    except (ValueError, TypeError, ValidationError, RecursionError):
        raise RealSourceError(422, "INVALID_REQUEST", "Invalid E1 source-intent fields or JSON", "REQUEST") from None
