"""Exact-byte CSV decoding and explicit native-field normalization."""
import base64
import binascii
import csv
import datetime as dt
import hashlib
import io
import re
from decimal import Decimal

from domain.ledger import numeric_bounds_violation

LIMITS=dict(file_bytes=16384,http_bytes=32768,logical_rows=128,columns=32,cell_bytes=2048,accepted_events=32,reports_per_portfolio=1000,report_bytes=2000000)
VERSION="csv/cp7-1"
FIELDS=frozenset("source_row_key account_id account_name event_type event_date currency listing_id symbol mic quantity amount cost_basis bought_amount bought_currency split_new split_old counterparty_account_id settlement_date ex_date acquired_on".split())
PROPOSAL_FIELDS=set("operation_id expected_revision_id as_of file_base64 filename kind source_namespace source_account_key snapshot_key new_account_name mapping constants corrections classifications format synthetic_acknowledged".split())


class CsvSourceError(ValueError):
    pass


def validate_proposal(value):
    """Strict persisted and wire contract, without edge-model constructor defaults."""
    import uuid
    def visible(text,maximum,*,trim=True):
        return type(text)is str and bool(text.strip()) and len(text)<=maximum and not any(ord(c)<32 for c in text) and (not trim or text==text.strip())
    if type(value)is not dict or set(value)!=PROPOSAL_FIELDS or value["synthetic_acknowledged"] is not True:
        raise ValueError("Explicit complete CSV proposal required")
    for field in ("operation_id","expected_revision_id"):
        if type(value[field])is not str or str(uuid.UUID(value[field]))!=value[field]:
            raise ValueError("Canonical UUID required")
    exact_date(value["as_of"],"ISO")
    if value["kind"] not in ("HOLDINGS","TRANSACTIONS") or not visible(value["source_namespace"],128) or not visible(value["filename"],120,trim=False):
        raise ValueError("Invalid explicit kind/source/filename")
    if type(value["file_base64"])is not str or len(value["file_base64"])>21848:
        raise ValueError("Bounded base64 source required")
    format=value["format"]
    if type(format)is not dict or set(format)!={"delimiter","date_format","decimal_separator","thousands_separator"}:
        raise ValueError("Explicit complete format required")
    if (format["delimiter"] not in (",",";","\t") or format["date_format"] not in ("ISO","DMY","MDY")
        or format["decimal_separator"] not in (".",",") or format["thousands_separator"] not in (None,",","."," ") or format["decimal_separator"]==format["thousands_separator"]):
        raise ValueError("Invalid explicit format")
    mapping,constants=value["mapping"],value["constants"]
    if type(mapping)is not dict or type(constants)is not dict or len(mapping)>22 or len(constants)>22 or (set(mapping)|set(constants))-FIELDS or set(mapping)&set(constants):
        raise ValueError("Invalid explicit field mapping")
    if any(type(index)is not int or not 0<=index<32 for index in mapping.values()) or any(type(cell)is not str or len(cell.encode())>2048 for cell in constants.values()):
        raise ValueError("Invalid indexed mapping/constants")
    for name in ("corrections","classifications"):
        rows=value[name]
        if type(rows)is not list or len(rows)>128:
            raise ValueError("Explicit bounded correction/classification list required")
        seen=set()
        for row in rows:
            wanted={"row_number","fields","reason"} if name=="corrections" else {"row_number","classification","reason"}
            if type(row)is not dict or set(row)!=wanted or type(row["row_number"])is not int or not 1<=row["row_number"]<=128 or row["row_number"] in seen or not visible(row["reason"],500,trim=False):
                raise ValueError("Invalid explicit row decision")
            seen.add(row["row_number"])
            if name=="classifications":
                if row["classification"] not in ("NON_DATA","OUT_OF_SCOPE"):
                    raise ValueError("Unknown explicit row classification")
            elif type(row["fields"])is not dict or not row["fields"] or len(row["fields"])>22 or set(row["fields"])-FIELDS or any(type(cell)is not str or len(cell.encode())>2048 for cell in row["fields"].values()):
                raise ValueError("Invalid explicit corrected fields")
    if value["kind"]=="HOLDINGS":
        if not visible(value["source_account_key"],128) or not visible(value["snapshot_key"],128) or not visible(value["new_account_name"],80):
            raise ValueError("Explicit new source account/snapshot/name required")
    elif any(value[field]is not None for field in ("source_account_key","snapshot_key","new_account_name")):
        raise ValueError("Transactions use owned existing row accounts")


def parse_source(encoded,filename,delimiter):
    try:
        raw=base64.b64decode(encoded,validate=True)
    except (ValueError,binascii.Error):
        raise CsvSourceError("CSV_BASE64_INVALID") from None
    if base64.b64encode(raw).decode()!=encoded:
        raise CsvSourceError("CSV_BASE64_NONCANONICAL")
    if not raw or len(raw)>LIMITS["file_bytes"]:
        raise CsvSourceError("CSV_FILE_SIZE")
    try:
        text=raw.decode("utf-8",errors="strict")
    except UnicodeDecodeError:
        raise CsvSourceError("CSV_UTF8_INVALID") from None
    if "\x00" in text:
        raise CsvSourceError("CSV_NUL_REFUSED")
    bom=text.startswith("\ufeff")
    if bom:
        text=text[1:]
    reader=csv.reader(io.StringIO(text,newline=""),delimiter=delimiter,quotechar='"',doublequote=True,
        escapechar=None,skipinitialspace=False,strict=True)
    try:
        header=next(reader)
        if not header or len(header)>32:
            raise CsvSourceError("CSV_HEADER_SIZE")
        if any(len(cell.encode("utf-8"))>2048 for cell in header):
            raise CsvSourceError("CSV_CELL_SIZE")
        rows=[]
        previous=reader.line_num
        for number,cells in enumerate(reader,1):
            if number>128 or len(cells)>32 or any(len(cell.encode("utf-8"))>2048 for cell in cells):
                raise CsvSourceError("CSV_ROW_COLUMN_CELL_LIMIT")
            rows.append(dict(row_number=number,physical_start=previous+1,physical_end=reader.line_num,cells=cells))
            previous=reader.line_num
    except StopIteration:
        raise CsvSourceError("CSV_EMPTY_FILE") from None
    except csv.Error:
        raise CsvSourceError("CSV_STRUCTURAL_ERROR") from None
    if not rows:
        raise CsvSourceError("CSV_NO_DATA_RECORDS")
    return dict(file_sha256=hashlib.sha256(raw).hexdigest(),byte_count=len(raw),bom=bom,
        columns=[dict(index=index,header=value) for index,value in enumerate(header)],rows=rows,limits=LIMITS.copy())


def exact_number(value,format,*,zero=False):
    decimal=format["decimal_separator"]
    group=format["thousands_separator"]
    pieces=value.split(decimal)
    if len(pieces)>2:
        raise ValueError("INVALID_DECIMAL_FORMAT")
    integer=pieces[0]
    if group is not None and group in integer:
        if not re.fullmatch(r"[1-9][0-9]{0,2}(?:"+re.escape(group)+r"[0-9]{3})+",integer):
            raise ValueError("INVALID_GROUPING")
        integer=integer.replace(group,"")
    fraction="" if len(pieces)==1 else pieces[1]
    normalized=integer+("."+fraction if len(pieces)==2 else "")
    if not re.fullmatch(r"(?:0|[1-9][0-9]{0,29})(?:\.[0-9]{1,24})?",normalized):
        raise ValueError("EXACT_DECIMAL_REQUIRED")
    number=Decimal(normalized)
    if number<0 or not zero and number==0 or numeric_bounds_violation(number):
        raise ValueError("NUMERIC_BOUND_OR_SIGN")
    return normalized


def exact_date(value,format):
    if format=="ISO":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}",value):
            raise ValueError("EXPLICIT_DATE_FORMAT_REQUIRED")
        day=dt.date.fromisoformat(value)
    else:
        if not re.fullmatch(r"[0-9]{2}/[0-9]{2}/[0-9]{4}",value):
            raise ValueError("EXPLICIT_DATE_FORMAT_REQUIRED")
        one,two,year=map(int,value.split("/"))
        day=dt.date(year,two,one) if format=="DMY" else dt.date(year,one,two)
    return day.isoformat()


def normalized_event(fields,proposal,accounts,listings,new_account_id):
    """Only explicit transformations; the domain constructor validates event shape."""
    kind=fields.get("event_type","")
    holdings=proposal["kind"]=="HOLDINGS"
    if holdings:
        kind={"POSITION":"OPENING_POSITION","CASH":"OPENING_CASH"}.get(kind,kind)
        if kind not in ("OPENING_POSITION","OPENING_CASH"):
            raise ValueError("HOLDINGS_REQUIRE_EXPLICIT_POSITION_OR_CASH")
        if fields.get("account_id") or fields.get("account_name") not in (None,"",proposal["new_account_name"]):
            raise ValueError("HOLDINGS_NEW_ACCOUNT_ONLY")
        account_id=new_account_id
    else:
        if kind in ("OPENING_POSITION","OPENING_CASH","REVERSAL"):
            raise ValueError("OPENINGS_USE_HOLDINGS_AND_REVERSALS_USE_B2")
        account_id=fields.get("account_id")
        name=fields.get("account_name")
        matches=[row["account_id"] for row in accounts if row["name"]==name] if name else []
        if not account_id:
            if len(matches)!=1:
                raise ValueError("EXPLICIT_UNAMBIGUOUS_OWNED_ACCOUNT_REQUIRED")
            account_id=matches[0]
        if account_id not in {row["account_id"] for row in accounts} or name and matches!=[account_id]:
            raise ValueError("ACCOUNT_ID_OR_NAME_CONFLICT")
    currency=fields.get("currency","")
    if not re.fullmatch(r"[A-Z]{3}",currency):
        raise ValueError("EXPLICIT_NATIVE_CURRENCY_REQUIRED")
    event=dict(event_type=kind,account_id=account_id,currency=currency,
        event_date=exact_date(fields.get("event_date",""),proposal["format"]["date_format"]))
    if holdings and event["event_date"]!="2026-01-02":
        raise ValueError("HOLDINGS_SNAPSHOT_DATE_UNSUPPORTED")
    identity={key:fields.get(key) for key in ("listing_id","symbol","mic") if fields.get(key)}
    if identity:
        matches=[row for row in listings if all(row.get(key)==value for key,value in identity.items())]
        if len(matches)!=1:
            raise ValueError("SECURITY_UNKNOWN_AMBIGUOUS_OR_CONFLICTING")
        event["listing_id"]=matches[0]["listing_id"]
    for field in ("quantity","amount","cost_basis"):
        if fields.get(field):
            event[field]=exact_number(fields[field],proposal["format"],zero=field=="cost_basis")
    for field in ("settlement_date","ex_date","acquired_on"):
        if fields.get(field):
            event[field]=exact_date(fields[field],proposal["format"]["date_format"])
    if fields.get("counterparty_account_id"):
        event["counterparty_account_id"]=fields["counterparty_account_id"]
    if fields.get("bought_amount") or fields.get("bought_currency"):
        if not re.fullmatch(r"[A-Z]{3}",fields.get("bought_currency","")):
            raise ValueError("EXPLICIT_BOUGHT_CURRENCY_REQUIRED")
        event["bought_amount"]=dict(amount=exact_number(fields.get("bought_amount",""),proposal["format"]),currency=fields["bought_currency"])
    if fields.get("split_new") or fields.get("split_old"):
        event["split_ratio"]=dict(new_units=exact_number(fields.get("split_new",""),proposal["format"]),old_units=exact_number(fields.get("split_old",""),proposal["format"]))
    return event
