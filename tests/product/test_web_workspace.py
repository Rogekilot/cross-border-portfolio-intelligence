"""Pure strict transport tests for manual facts and explicit personal choices."""
import datetime as dt
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src"))

from pydantic import ValidationError
from persistence.web_workspace_store import _policies
from web_api.workspace_requests import EventInput, LedgerCommand, PolicyInput


class WorkspaceTransportTests(unittest.TestCase):
    def test_persisted_policies_require_an_array_of_objects(self):
        self.assertEqual(_policies("[]"),())
        for value in ("{}","null","\"\"","0","[null]","[[]]","[3]","[{}]"):
            with self.subTest(value=value),self.assertRaises(ValueError):
                _policies(value)

    def event(self, **changes):
        value=dict(event_type="OPENING_POSITION",account_id=str(uuid.uuid4()),event_date="2026-01-02",
            currency="USD",listing_id=str(uuid.uuid4()),quantity="1")
        return EventInput(**{**value,**changes})

    def test_zero_cost_basis_is_valid_but_zero_amount_quantity_are_not(self):
        self.assertEqual(self.event(cost_basis="0").cost_basis,"0")
        for field in ("quantity","amount"):
            value = dict(event_type="BUY",account_id=str(uuid.uuid4()),event_date="2026-01-05",currency="USD",listing_id=str(uuid.uuid4()),quantity="1",amount="100")
            value[field]="0"
            with self.assertRaises(ValidationError):
                EventInput(**value)

    def test_numeric_strings_are_bounded_exact_and_no_float_or_exponent(self):
        for value in (1,1.5,"1e3","NaN","-1","01","1."+"1"*25,"1"+"0"*30):
            with self.subTest(value=value),self.assertRaises(ValidationError):
                self.event(quantity=value)

    def test_unknown_fields_and_unguarded_reversal_links_are_forbidden(self):
        for change in (dict(event_type="REVERSAL"),dict(corrects_event_id=str(uuid.uuid4())),dict(event_id=str(uuid.uuid4()))):
            value=dict(event_type="DEPOSIT",account_id=str(uuid.uuid4()),event_date="2026-01-05",currency="USD",amount="1")
            value.update(change)
            with self.assertRaises(ValidationError):
                EventInput(**value)

    def test_dates_are_explicit_and_duplicate_targets_refused(self):
        target=str(uuid.uuid4())
        for day in ("2026-1-5","2026-02-30"):
            with self.assertRaises(ValidationError):
                LedgerCommand(operation_id=str(uuid.uuid4()),expected_revision_id=str(uuid.uuid4()),as_of=day,operation="REVERSE",target_event_ids=[target])
        with self.assertRaises(ValidationError):
            LedgerCommand(operation_id=str(uuid.uuid4()),expected_revision_id=str(uuid.uuid4()),as_of="2026-01-05",operation="REVERSE",target_event_ids=[target,target])

    def test_policy_no_threshold_defaults_and_exact_fraction_only(self):
        value=dict(policy_id=str(uuid.uuid4()),source_kind="CP5",metric_id="largest_security_weight",semantic_key="explicit-semantic",
            scope_kind="PORTFOLIO",subject=[],direction="MAXIMUM",limit="1/3",effective_from="2026-01-02",evidence="I explicitly chose this personal limit")
        self.assertEqual(PolicyInput(**value).limit,"1/3")
        for change in (dict(limit=""),dict(limit=0.5),dict(limit="50%"),dict(limit="1/0"),dict(evidence=" ")):
            with self.assertRaises(ValidationError):
                PolicyInput(**{**value,**change})
