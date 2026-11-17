"""Strict questions for on-demand analytics; no caller financial facts or pins."""
import datetime as dt
import uuid
from typing import Literal

from pydantic import Field,StrictBool,StrictInt,StrictStr,field_validator,model_validator
from web_api.app import StrictModel

FAMILY=r"(?:PERFORMANCE_WINDOW|GAINS|ATTRIBUTION|RISK)"
GROUP=r"(?:PERFORMANCE|INDEPENDENT|BENCHMARK)"


def canonical_uuid(value):
    if str(uuid.UUID(value))!=value:
        raise ValueError("Canonical UUID text is required")
    return value


def iso_date(value):
    if len(value)!=10 or dt.date.fromisoformat(value).isoformat()!=value:
        raise ValueError("An exact ISO calendar date is required")
    return value


class AnalyticsWindow(StrictModel):
    rule:Literal["TRAILING_MONTHS","YTD","SINCE_INCEPTION","CUSTOM","MAX_AVAILABLE"]
    months:StrictInt|None
    base:StrictStr|None

    @model_validator(mode="after")
    def variant(self):
        if self.rule=="TRAILING_MONTHS":
            if self.months not in (1,3,6,12,36,60) or self.base is not None:
                raise ValueError("Trailing months must be1/3/6/12/36/60 with no custom base")
        elif self.rule=="CUSTOM":
            if self.months is not None or self.base is None:
                raise ValueError("A custom window needs only its explicit base")
            iso_date(self.base)
        elif self.months is not None or self.base is not None:
            raise ValueError("This window has no months or custom base")
        return self


class AnalyticsScope(StrictModel):
    kind:Literal["PORTFOLIO","ACCOUNT"]
    account_id:StrictStr|None

    @model_validator(mode="after")
    def variant(self):
        if self.kind=="PORTFOLIO":
            if self.account_id is not None:
                raise ValueError("Portfolio scope does not name an account")
        elif self.account_id is None:
            raise ValueError("Account scope requires an explicit account UUID")
        else:
            canonical_uuid(self.account_id)
        return self


class AnalyticsQuestion(StrictModel):
    revision_id:StrictStr
    as_of:StrictStr
    family:Literal["PERFORMANCE_WINDOW","GAINS","ATTRIBUTION","RISK"]
    window:AnalyticsWindow
    frequency:Literal["DAILY","WEEKLY","MONTHLY"]|None
    scope:AnalyticsScope
    view:Literal["REQUESTED","DEFAULT"]
    synthetic_acknowledged:StrictBool

    _revision=field_validator("revision_id")(canonical_uuid)
    _date=field_validator("as_of")(iso_date)

    @model_validator(mode="after")
    def variant(self):
        if self.synthetic_acknowledged is not True:
            raise ValueError("Explicit fictional sandbox acknowledgement is required")
        if self.family=="RISK":
            if self.frequency is None:
                raise ValueError("Risk requires an explicit sampling frequency")
        elif self.frequency is not None or self.view!="REQUESTED" or self.window.rule=="MAX_AVAILABLE":
            raise ValueError("Frequency,default view and MAX_AVAILABLE apply only to risk")
        if self.view=="DEFAULT" and (self.window.rule!="TRAILING_MONTHS" or self.window.months!=36):
            raise ValueError("Default risk composition starts with the explicit36-month question")
        return self


class AnalyticsProofRequest(StrictModel):
    question:AnalyticsQuestion
    result_id:StrictStr=Field(pattern="^"+FAMILY+":"+GROUP+r":[0-9a-f]{64}:[0-9a-f]{64}$")
    expected_binding_digest:StrictStr=Field(pattern=r"^[0-9a-f]{64}$")
    expected_manifest_id:StrictStr=Field(pattern=r"^[0-9a-f]{64}$")
    expected_result_digest:StrictStr=Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def family_matches(self):
        family,group,*_=self.result_id.split(":")
        if family!=self.question.family or (family=="RISK")!=(group in ("INDEPENDENT","BENCHMARK")):
            raise ValueError("The proof reference must name the question's family and group")
        return self
