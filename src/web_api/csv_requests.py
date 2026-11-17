"""Bounded exact CSV transport; parsing/business validation live outside the edge."""
from typing import Literal

from pydantic import Field,StrictBool,StrictInt,StrictStr,field_validator,model_validator
from web_api.app import StrictModel
from web_api.workspace_requests import CommandBase
from portfolio_import.csv_source import validate_proposal

FIELDS=frozenset("source_row_key account_id account_name event_type event_date currency listing_id symbol mic quantity amount cost_basis bought_amount bought_currency split_new split_old counterparty_account_id settlement_date ex_date acquired_on".split())


class ParseCsvRequest(StrictModel):
    file_base64:StrictStr=Field(max_length=21848)
    filename:StrictStr=Field(min_length=1,max_length=120)
    delimiter:Literal[",",";","\t"]
    synthetic_acknowledged:StrictBool

    @model_validator(mode="after")
    def acknowledged(self):
        if self.synthetic_acknowledged is not True:
            raise ValueError("Explicit fictional sandbox acknowledgement is required")
        if any(ord(char)<32 for char in self.filename):
            raise ValueError("Filename must be visible provenance text")
        return self


class CsvFormat(StrictModel):
    delimiter:Literal[",",";","\t"]
    date_format:Literal["ISO","DMY","MDY"]
    decimal_separator:Literal[".",","]
    thousands_separator:Literal[",","."," "]|None

    @model_validator(mode="after")
    def separators(self):
        if self.decimal_separator==self.thousands_separator:
            raise ValueError("Decimal and grouping separators must differ")
        return self


class CsvCorrection(StrictModel):
    row_number:StrictInt=Field(ge=1,le=128)
    fields:dict[StrictStr,StrictStr]=Field(min_length=1,max_length=22)
    reason:StrictStr=Field(min_length=1,max_length=500)


class CsvClassification(StrictModel):
    row_number:StrictInt=Field(ge=1,le=128)
    classification:Literal["NON_DATA","OUT_OF_SCOPE"]
    reason:StrictStr=Field(min_length=1,max_length=500)


class ImportProposal(CommandBase):
    file_base64:StrictStr=Field(max_length=21848)
    filename:StrictStr=Field(min_length=1,max_length=120)
    kind:Literal["HOLDINGS","TRANSACTIONS"]
    source_namespace:StrictStr=Field(min_length=1,max_length=128)
    source_account_key:StrictStr|None=None
    snapshot_key:StrictStr|None=None
    new_account_name:StrictStr|None=Field(default=None,max_length=80)
    mapping:dict[StrictStr,StrictInt]=Field(max_length=22)
    constants:dict[StrictStr,StrictStr]=Field(default_factory=dict,max_length=22)
    corrections:list[CsvCorrection]=Field(default_factory=list,max_length=128)
    classifications:list[CsvClassification]=Field(default_factory=list,max_length=128)
    format:CsvFormat
    synthetic_acknowledged:StrictBool

    @model_validator(mode="after")
    def shape(self):
        validate_proposal(self.model_dump())
        if not self.synthetic_acknowledged:
            raise ValueError("Explicit fictional sandbox acknowledgement is required")
        if (set(self.mapping)|set(self.constants))-FIELDS or set(self.mapping)&set(self.constants):
            raise ValueError("Canonical fields must be known and cannot be both mapped and constant")
        if any(index<0 or index>=32 for index in self.mapping.values()):
            raise ValueError("Column indexes must lie between0 and31")
        for rows in (self.corrections,self.classifications):
            if len({row.row_number for row in rows})!=len(rows):
                raise ValueError("Each row may have one correction/classification record")
            for row in rows:
                if not row.reason.strip() or any(ord(char)<32 for char in row.reason):
                    raise ValueError("Explicit visible reasons are required")
        for row in self.corrections:
            if set(row.fields)-FIELDS:
                raise ValueError("Unknown correction field")
        for value in (self.source_namespace,self.source_account_key,self.snapshot_key):
            if value is not None and (not value or value!=value.strip() or len(value)>128 or any(ord(char)<32 for char in value)):
                raise ValueError("Stable source keys must be bounded visible text without surrounding whitespace")
        if any(ord(char)<32 for char in self.filename):
            raise ValueError("Filename must be visible provenance text")
        for value in list(self.constants.values())+[value for correction in self.corrections for value in correction.fields.values()]:
            if len(value.encode("utf-8"))>2048:
                raise ValueError("Mapped/corrected cells are limited to2048 UTF-8 bytes")
        if self.kind=="HOLDINGS":
            if not self.source_account_key or not self.snapshot_key or not self.new_account_name or self.new_account_name!=self.new_account_name.strip() or any(ord(c)<32 for c in self.new_account_name):
                raise ValueError("Holdings require an explicit new account name,source account key and snapshot key")
        elif any(value is not None for value in (self.source_account_key,self.snapshot_key,self.new_account_name)):
            raise ValueError("Transactions use explicit owned row accounts,not a new snapshot account")
        return self


class CommitCsvRequest(StrictModel):
    proposal:ImportProposal
    preview_receipt:StrictStr=Field(min_length=64,max_length=64,pattern=r"^[0-9a-f]{64}$")
