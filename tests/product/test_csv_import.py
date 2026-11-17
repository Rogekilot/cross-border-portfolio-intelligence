"""Pure exact-byte/parser/export boundaries; no DB or real personal files."""
import base64
import datetime as dt
import hashlib
import sys
import unittest
import uuid
from decimal import Decimal
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from domain.currency import CurrencyCode,Money
from domain.ledger import EventType,LedgerEvent
from persistence.web_account_store import AccountStoreError
from persistence.web_csv_store import _bounded_report_text,_facts,protected_csv
from portfolio_import.csv_source import CsvSourceError,exact_date,exact_number,parse_source

FORMAT=dict(delimiter=",",date_format="ISO",decimal_separator=".",thousands_separator=None)


class CsvPureTests(unittest.TestCase):
    def parse(self,raw,delimiter=","):
        return parse_source(base64.b64encode(raw).decode(),"fictional.csv",delimiter)

    def test_original_bom_bytes_and_duplicate_headers_indexed_embedded_lines(self):
        raw=b'\xef\xbb\xbfa,a,\r\n"one, two","line1\nline2",3\r\n'
        got=self.parse(raw)
        self.assertTrue(got["bom"])
        self.assertEqual(got["file_sha256"],hashlib.sha256(raw).hexdigest())
        self.assertEqual([c["header"] for c in got["columns"]],["a","a",""])
        self.assertEqual(got["rows"][0]["cells"],["one, two","line1\nline2","3"])
        self.assertEqual((got["rows"][0]["physical_start"],got["rows"][0]["physical_end"]),(2,3))

    def test_explicit_delimiter_not_sniffed(self):
        self.assertEqual(len(self.parse(b"a;b\n1;2\n",";")["columns"]),2)
        self.assertEqual(len(self.parse(b"a;b\n1;2\n",",")["columns"]),1)

    def test_bad_utf8_structural_nul_empty_and_limits_refuse(self):
        for raw in (b"\xff",b"a\n\"unclosed",b"a\n\x00",b"",b"a\n",b"a\n"+b"x"*2049,b"a\n"+b"x\n"*129,b"a"*16385):
            with self.subTest(raw=raw[:20]),self.assertRaises(CsvSourceError):
                self.parse(raw)

    def test_bad_base64_and_noncanonical_padding_refuse(self):
        for value in ("!","YQ=","YR=="):
            with self.assertRaises(CsvSourceError):
                parse_source(value,"fictional.csv",",")

    def test_blank_and_ragged_records_are_retained(self):
        got=self.parse(b"a,b\n\n1\n2,3\n")
        self.assertEqual([row["cells"] for row in got["rows"]],[[],["1"],["2","3"]])

    def test_exact_numeric_conventions_no_guess_or_rounding(self):
        self.assertEqual(exact_number("1,234.50",{**FORMAT,"thousands_separator":","}),"1234.50")
        self.assertEqual(exact_number("1.234,50",{**FORMAT,"decimal_separator":",","thousands_separator":"."}),"1234.50")
        self.assertEqual(exact_number("0",FORMAT,zero=True),"0")
        for value in ("0","-1","1e3","NaN","+1"," 1","01","1.0000000000000000000000000","1"+"0"*30):
            with self.subTest(value=value),self.assertRaises(ValueError):
                exact_number(value,FORMAT)
        with self.assertRaises(ValueError):
            exact_number("12,34.5",{**FORMAT,"thousands_separator":","})

    def test_date_format_is_explicit_and_calendar_validated(self):
        self.assertEqual(exact_date("01/02/2026","DMY"),"2026-02-01")
        self.assertEqual(exact_date("01/02/2026","MDY"),"2026-01-02")
        for value in ("01/02/2026","2026-2-1","2026-02-30"):
            with self.assertRaises(ValueError):
                exact_date(value,"ISO")

    def test_financial_fingerprint_excludes_derived_ids_but_retains_zero_basis(self):
        first=LedgerEvent(uuid.uuid4(),uuid.uuid4(),EventType.OPENING_POSITION,dt.date(2026,1,2),CurrencyCode("USD"),listing_id=uuid.uuid4(),quantity=Decimal("2"))
        from dataclasses import replace
        second=replace(first,event_id=uuid.uuid4(),account_id=uuid.uuid4(),source_reference="other operation")
        self.assertEqual(_facts(first,True),_facts(second,True))
        self.assertNotEqual(_facts(first,True),_facts(replace(first,cost_basis=Money(Decimal(0),CurrencyCode("USD"))),True))

    def test_csv_text_protection_is_disclosed_without_changing_known_negative_numbers(self):
        text=protected_csv([dict(reason=" =1+2",symbol="@SUM(1)",amount="-2.50",quantity="1",control="\ntext")])
        self.assertIn("' =1+2",text)
        self.assertIn("'@SUM(1)",text)
        self.assertIn('"-2.50"',text)
        self.assertIn("'\ntext",text)

    def test_report_bound_reserves_final_metadata_and_counts_utf8_bytes(self):
        report=dict(persisted=False,status="READY",revision_id=None,created_at=None,counts=dict(imported=0),payload="")
        baseline=len(_bounded_report_text(report,prospective=True).encode())
        report["payload"]="a"*(2000000-baseline)
        self.assertEqual(len(_bounded_report_text(report,prospective=True).encode()),2000000)
        report["payload"]+="界"
        with self.assertRaises(AccountStoreError) as error:
            _bounded_report_text(report,prospective=True)
        self.assertEqual((error.exception.status,error.exception.code),(422,"CSV_REPORT_TOO_LARGE"))
