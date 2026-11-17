"""CP4b-3: the benchmark selection domain model (`domain.benchmark_selection`; PD-0039 D5; tech plan 17.5, 17.14). Pure; no database.

The resolution rule (`risk/1.4` Ruling 5.6 (1.4)) is checked against hand-written cases and the Quant's R13 log: the selection in force at knowledge version S is the live SELECT or CLEAR with the latest POSITION
(its own sequence, or for a replacement the position of the record it corrects); a REVERSAL voids the record it names.
"""

import dataclasses
import datetime
import itertools
import sys
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from domain import benchmark_selection as bs  # noqa: E402
from domain.benchmark_selection import (  # noqa: E402
    BenchmarkSelection,
    BenchmarkSelectionError,
    Origin,
    RecordType,
    SelectionState,
    SequencedSelection,
    pin_of,
    resolve_selection,
)

D = datetime.date
P, Q = uuid.UUID(int=1), uuid.UUID(int=2)


def sid(n):
    return uuid.UUID(int=0xA000 + n)


def select(n, benchmark="SPX", on=D(2026, 1, 5), portfolio=P, **kw):
    return BenchmarkSelection(sid(n), portfolio, RecordType.SELECT, on, benchmark, None, Origin.USER_CHOSEN, **kw)


def clear(n, on=D(2026, 1, 5), portfolio=P, **kw):
    return BenchmarkSelection(sid(n), portfolio, RecordType.CLEAR, on, **kw)


def reversal(n, target, on=D(2026, 1, 5), portfolio=P):
    return BenchmarkSelection(sid(n), portfolio, RecordType.REVERSAL, on, reverses_selection_id=sid(target))


def seq(*pairs):
    return [SequencedSelection(s, row, atomic_with_seq=None) for s, row in pairs]  # a hand-built log states that each row was appended alone (the loader's explicit boundary fact)


class FieldRuleTests(unittest.TestCase):
    VALUES = {"benchmark_id": "SPX", "catalog_version": "v1", "origin": Origin.USER_CHOSEN, "reverses_selection_id": sid(90), "corrects_selection_id": sid(91)}

    def test_every_presence_combination_is_valid_exactly_when_the_rule_table_says_so(self):
        checked = 0
        for record_type in RecordType:
            for mask in itertools.product((False, True), repeat=len(bs.FIELDS)):
                kwargs = {f: self.VALUES[f] for f, on in zip(bs.FIELDS, mask) if on}
                rules = bs.FIELD_RULES[record_type]
                expected_ok = all((rules[f] != bs.REQUIRED or kwargs.get(f) is not None) and (rules[f] != bs.FORBIDDEN or kwargs.get(f) is None) for f in bs.FIELDS)
                try:
                    BenchmarkSelection(sid(1), P, record_type, D(2026, 1, 5), **kwargs)
                    ok = True
                except BenchmarkSelectionError:
                    ok = False
                self.assertEqual(ok, expected_ok, (record_type, kwargs))
                checked += 1
        self.assertEqual(checked, 3 * 32)

    def test_the_rule_table_has_a_rule_for_every_field_and_type(self):
        for record_type in RecordType:
            self.assertEqual(set(bs.FIELD_RULES[record_type]), set(bs.FIELDS))

    def test_benchmark_id_is_a_short_ascii_identifier(self):
        for good in ("SPX", "a", "0", "MSCI.ACWI", "csi-300", "SP500:TR", "A" * 64, "x_1"):
            self.assertTrue(bs.is_benchmark_id(good), good)
        for bad in ("", " ", "SPX ", " SPX", "SPX\n", "\nSPX", ".SPX", "_x", "-x", "A" * 65, "S P", "S\tP", "SPX/TR", "标普", "ＳＰＸ", "SPX​", None, 5):
            self.assertFalse(bs.is_benchmark_id(bad), repr(bad))
        with self.assertRaises(BenchmarkSelectionError):
            select(1, benchmark="SPX\n")

    def test_catalog_version_has_a_pattern_too(self):
        BenchmarkSelection(sid(1), P, RecordType.SELECT, D(2026, 1, 5), "SPX", "cat-1.0+x", Origin.USER_CHOSEN)
        for bad in ("", " ", "v 1", "v1\n", "A" * 65):
            with self.assertRaises(BenchmarkSelectionError, msg=repr(bad)):
                BenchmarkSelection(sid(1), P, RecordType.SELECT, D(2026, 1, 5), "SPX", bad, Origin.USER_CHOSEN)

    def test_selected_on_is_a_plain_date_in_range(self):
        for good in (D(1, 1, 1), D(9999, 12, 31), D(2026, 10, 2)):
            select(1, on=good)
        with self.assertRaises(BenchmarkSelectionError):
            select(1, on=datetime.datetime(2026, 1, 5, 12, 0))  # a datetime: the choice has a date, not a time of day
        with self.assertRaises(BenchmarkSelectionError):
            select(1, on="2026-01-05")

    def test_types_are_checked(self):
        with self.assertRaises(BenchmarkSelectionError):
            BenchmarkSelection("x", P, RecordType.CLEAR, D(2026, 1, 5))
        with self.assertRaises(BenchmarkSelectionError):
            BenchmarkSelection(sid(1), P, "CLEAR", D(2026, 1, 5))
        with self.assertRaises(BenchmarkSelectionError):
            BenchmarkSelection(sid(1), P, RecordType.SELECT, D(2026, 1, 5), "SPX", None, "USER_CHOSEN")

    def test_no_self_reference(self):
        with self.assertRaises(BenchmarkSelectionError):
            BenchmarkSelection(sid(1), P, RecordType.REVERSAL, D(2026, 1, 5), reverses_selection_id=sid(1))
        with self.assertRaises(BenchmarkSelectionError):
            select(1, corrects_selection_id=sid(1))

    def test_same_content_compares_every_field(self):
        self.assertTrue(select(1).has_same_content(select(1)))
        self.assertFalse(select(1).has_same_content(select(1, benchmark="NDX")))
        self.assertFalse(select(1).has_same_content(select(1, on=D(2026, 1, 6))))
        self.assertFalse(select(1).has_same_content(select(1, portfolio=Q)))


class CorrectionPairTests(unittest.TestCase):
    def test_a_pair_names_the_same_row_in_one_portfolio(self):
        bs.validate_correction_pair(reversal(2, 1), select(3, benchmark="NDX", corrects_selection_id=sid(1)))
        bs.validate_correction_pair(reversal(2, 1), clear(3, corrects_selection_id=sid(1)))

    def test_bad_pairs_are_refused(self):
        bad = [
            (select(2), select(3, corrects_selection_id=sid(1))),                                  # the first record is not a REVERSAL
            (reversal(2, 1), reversal(3, 1)),                                                       # the replacement is a REVERSAL
            (reversal(2, 1), select(3)),                                                            # the replacement corrects nothing
            (reversal(2, 1), select(3, corrects_selection_id=sid(9))),                              # it corrects another row
            (reversal(2, 1), select(3, portfolio=Q, corrects_selection_id=sid(1))),                 # another portfolio
        ]
        for rev, rep in bad:
            with self.assertRaises(BenchmarkSelectionError):
                bs.validate_correction_pair(rev, rep)


class ResolutionTests(unittest.TestCase):
    def test_no_rows_is_none(self):
        r = resolve_selection(P, [], 0)
        self.assertEqual((r.state, r.row, r.version), (SelectionState.NONE, None, 0))

    def test_the_latest_select_is_in_force_and_a_version_before_it_sees_the_earlier(self):
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 2, 1))))
        self.assertEqual(resolve_selection(P, rows, 2).row.selection.benchmark_id, "NDX")
        self.assertEqual(resolve_selection(P, rows, 1).row.selection.benchmark_id, "SPX")
        self.assertEqual(resolve_selection(P, rows, 0).state, SelectionState.NONE)

    def test_clear_means_no_benchmark_not_the_previous_one(self):
        rows = seq((1, select(1)), (2, clear(2, D(2026, 2, 1))))
        r = resolve_selection(P, rows, 2)
        self.assertEqual((r.state, r.row.selection.record_type), (SelectionState.CLEARED, RecordType.CLEAR))
        self.assertEqual(pin_of(r).benchmark_id, None)

    def test_a_reversal_withdraws_the_row_and_the_previous_live_one_is_in_force_again(self):
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 2, 1))), (3, reversal(3, 2, D(2026, 2, 2))))
        self.assertEqual(resolve_selection(P, rows, 3).row.selection.benchmark_id, "SPX")
        self.assertEqual(resolve_selection(P, rows, 2).row.selection.benchmark_id, "NDX")  # the reversal is not yet known at version 2

    def test_reversing_the_only_row_leaves_none(self):
        rows = seq((1, select(1)), (2, reversal(2, 1)))
        self.assertEqual(resolve_selection(P, rows, 2).state, SelectionState.NONE)

    def test_the_log_is_ordered_by_sequence_alone_and_the_date_is_only_data(self):
        # risk/1.1 Ruling 5.6 (1.1): the selection is the LATEST record up to the version. A record dated EARLIER than the previous one but appended LATER is the latest.
        rows = seq((1, select(1, "SPX", D(2026, 3, 1))), (2, select(2, "NDX", D(2026, 1, 5))))
        self.assertEqual(resolve_selection(P, rows, 2).row.selection.benchmark_id, "NDX")
        self.assertEqual(resolve_selection(P, rows, 1).row.selection.benchmark_id, "SPX")
        # equal dates: by sequence
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 1, 5))))
        self.assertEqual(resolve_selection(P, rows, 2).row.selection.benchmark_id, "NDX")

    def test_a_correction_is_the_latest_record_when_it_is_appended(self):
        # row 1 SPX, row 2 NDX (in force). The LATEST row (2) is found wrong and corrected: the replacement is the latest record and in force.
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 2, 1))),
                   (3, reversal(3, 2, D(2026, 2, 1))), (4, select(4, "CSI", D(2026, 2, 1), corrects_selection_id=sid(2))))
        self.assertEqual(resolve_selection(P, rows, 4).row.selection.benchmark_id, "CSI")
        # withdrawing the latest record WITHOUT a replacement leaves the latest of the remaining records (a withdrawn record is not "no selection"); the engine substitutes nothing else
        self.assertEqual(resolve_selection(P, rows[:3], 3).row.selection.benchmark_id, "SPX")
        # the Quant's fixture log has only SELECT and CLEAR records (a null benchmark clears): the latest wins, and a CLEAR is a record
        q1 = seq((1, select(1, "SPX")), (2, clear(2)), (3, select(3, "NOPE")), (4, select(4, "PR")), (5, select(5, "LATE")))
        self.assertEqual([resolve_selection(P, q1, v).state.value for v in (0, 1, 2, 3, 5)], ["NONE", "IN_FORCE", "CLEARED", "IN_FORCE", "IN_FORCE"])
        self.assertEqual([resolve_selection(P, q1, v).row and resolve_selection(P, q1, v).row.selection.benchmark_id for v in (1, 2, 3, 4, 5)], ["SPX", None, "NOPE", "PR", "LATE"])

    # -- risk/1.4 Ruling 5.6 (1.4) (CP4M-4): a replacement takes the position of the record it corrects ------------------------------------------------------------------

    def r13(self):
        """The Quant's R13 log (cp4_golden/1.2-part3): 1 SELECT US, 2 SELECT CN, 3 REVERSAL of 2, 4 CLEAR, 5 REVERSAL of 4, 6 SELECT CN, 7+8 REVERSAL of 1 replaced by ETF, 9+10 REVERSAL of 6 replaced by US2."""
        rows = seq((1, select(1, "US")), (2, select(2, "CN")), (3, reversal(3, 2)), (4, clear(4)), (5, reversal(5, 4)), (6, select(6, "CN")), (7, reversal(7, 1)),
                   (8, select(8, "ETF", corrects_selection_id=sid(1))), (9, reversal(9, 6)), (10, select(10, "US2", corrects_selection_id=sid(6))))
        # the loader's boundary facts (CP4M-9): 7 and 8 were appended by one transaction, and so were 9 and 10
        return [dataclasses.replace(r, atomic_with_seq={7: 8, 8: 7, 9: 10, 10: 9}.get(r.selection_seq)) for r in rows]

    def test_the_quants_r13_log_resolves_at_every_version(self):
        rows = self.r13()
        want = {0: ("NONE", None), 1: ("IN_FORCE", 1), 2: ("IN_FORCE", 2), 3: ("IN_FORCE", 1), 4: ("CLEARED", 4), 5: ("IN_FORCE", 1), 6: ("IN_FORCE", 6), 8: ("IN_FORCE", 6), 10: ("IN_FORCE", 10)}
        for version, (state, seq_in_force) in want.items():
            r = resolve_selection(P, rows, version)
            self.assertEqual((r.state.value, None if r.row is None else r.row.selection_seq), (state, seq_in_force), version)

    def test_a_version_that_cuts_a_correction_pair_is_not_pinnable(self):
        rows = self.r13()
        for version in (7, 9):  # the REVERSAL (seq 7, 9) without its replacement (seq 8, 10)
            with self.assertRaises(bs.SelectionVersionNotPinnableError, msg=version):
                resolve_selection(P, rows, version)
        # CP4M-9: the rows only up to the version (exactly what `load_selections` returns) are refused as well, with the SAME error, because each row states its same-transaction partner
        for version in (7, 9):
            with self.assertRaises(bs.SelectionVersionNotPinnableError, msg=version):
                resolve_selection(P, rows[:version], version)
        for version in (8, 10, 6):  # a boundary is a boundary with or without the rows above it
            self.assertEqual(resolve_selection(P, rows[:version], version).row.selection_seq, resolve_selection(P, rows, version).row.selection_seq)

    def test_the_boundary_fact_is_the_whole_check_for_a_truncated_log_and_is_not_part_of_a_pin_or_a_digest(self):
        rows = self.r13()
        with self.assertRaises(bs.SelectionVersionNotPinnableError):
            bs.check_pinnable(rows[:9], 9)
        bs.check_pinnable(rows[:8], 8)
        bs.check_pinnable(rows[:6], 6)
        # the fact is about the log, not the record: the same record with and without it has one row digest, so a pin never changes with how the log was loaded
        bare = SequencedSelection(rows[8].selection_seq, rows[8].selection)
        self.assertEqual((rows[8].digest, rows[8].to_obj()), (bare.digest, bare.to_obj()))
        self.assertEqual(bs.pin_of(resolve_selection(P, rows, 10)), bs.pin_of(resolve_selection(P, [dataclasses.replace(r, atomic_with_seq=None) for r in rows], 10)))
        # a loader that says every row was appended alone, while the rows above hold the replacement, contradicts itself: the consistency fallback still refuses
        bare_rows = [dataclasses.replace(r, atomic_with_seq=None) for r in rows]
        with self.assertRaises(bs.SelectionVersionNotPinnableError):
            resolve_selection(P, bare_rows, 7)
        # CP4M-10 point 6: a loader that states NOTHING is not "appended alone": a REVERSAL without the fact is refused at every version it is at or below, with the full log or a truncated one
        unstated = [SequencedSelection(r.selection_seq, r.selection) for r in rows]
        self.assertIs(unstated[0].atomic_with_seq, bs.NOT_STATED)
        for version in (3, 5, 8, 10):
            with self.assertRaises(bs.SelectionVersionNotPinnableError, msg=version):
                resolve_selection(P, unstated[:version], version)
        self.assertEqual(resolve_selection(P, unstated[:2], 2).row.selection_seq, 2)  # no REVERSAL at or below the version: nothing to judge
        self.assertIsNone(bs.pin_of(resolve_selection(P, unstated[:0], 0)).selection_id)
        # the store's old error name is the SAME class
        from persistence import benchmark_selection_store as store  # noqa: PLC0415

        self.assertIs(store.SelectionVersionNotABoundaryError, bs.SelectionVersionNotPinnableError)

    def test_the_replacement_of_an_old_record_keeps_the_old_position_and_the_latest_keeps_its_own(self):
        r = resolve_selection(P, self.r13(), 8)  # (R13-V8, mutation M-C29): the engine's old build resolved the ETF proxy (seq 8) here
        self.assertEqual((r.row.selection.benchmark_id, r.row.selection_seq, r.position), ("CN", 6, 6))
        r10 = resolve_selection(P, self.r13(), 10)  # (R13-V10) correcting the LATEST record puts the replacement in force
        self.assertEqual((r10.row.selection.benchmark_id, r10.row.selection_seq, r10.position), ("US2", 10, 6))

    def test_a_chain_of_corrections_is_followed_back_to_the_original_position(self):
        rows = seq((1, select(1, "A")), (2, select(2, "B")), (3, reversal(3, 1)), (4, select(4, "A2", corrects_selection_id=sid(1))), (5, reversal(5, 4)), (6, select(6, "A3", corrects_selection_id=sid(4))))
        r = resolve_selection(P, rows, 6)
        self.assertEqual((r.row.selection.benchmark_id, r.position), ("B", 2))  # A3 sits where A was (position 1): B (position 2) is later and stays in force
        rows2 = rows[:1] + seq((2, reversal(2, 1)), (3, select(3, "A2", corrects_selection_id=sid(1))), (4, reversal(4, 3)), (5, select(5, "A3", corrects_selection_id=sid(3))))
        r2 = resolve_selection(P, rows2, 5)
        self.assertEqual((r2.row.selection.benchmark_id, r2.row.selection_seq, r2.position), ("A3", 5, 1))

    def test_a_correction_of_a_clear_and_of_a_select_by_a_clear(self):
        rows = seq((1, select(1, "A")), (2, clear(2)), (3, reversal(3, 2)), (4, clear(4, corrects_selection_id=sid(2))))
        r = resolve_selection(P, rows, 4)
        self.assertEqual((r.state, r.row.selection_seq, r.position), (SelectionState.CLEARED, 4, 2))  # the replacement CLEAR sits where the wrong CLEAR was: still the latest

    def test_the_position_is_in_the_pin_only_when_it_differs_from_the_sequence(self):
        r = resolve_selection(P, self.r13(), 10)
        pin = pin_of(r)
        self.assertEqual((pin.selection_seq, pin.position), (10, 6))
        self.assertEqual(pin.to_obj()["position"], 6)
        plain = pin_of(resolve_selection(P, self.r13(), 6))
        self.assertIsNone(plain.position)
        self.assertNotIn("position", plain.to_obj())  # a record in its own position serialises exactly as before 1.4
        self.assertNotEqual(pin.digest, plain.digest)
        # the same row at another position is another pin
        import dataclasses  # noqa: PLC0415

        self.assertNotEqual(pin.digest, dataclasses.replace(pin, position=7).digest)

    def test_a_replacement_resubmitted_alone_or_with_a_missing_target_falls_back_to_its_own_sequence(self):
        rows = seq((5, select(5, "A", corrects_selection_id=sid(1))))  # the corrected row is not among the rows: its own sequence
        self.assertEqual(resolve_selection(P, rows, 5).position, 5)

    def test_rows_above_the_version_and_other_portfolios_are_handled(self):
        rows = seq((1, select(1)), (5, select(5, "NDX", D(2026, 3, 1))))
        self.assertEqual(resolve_selection(P, rows, 4).row.selection.benchmark_id, "SPX")
        with self.assertRaises(BenchmarkSelectionError):
            resolve_selection(P, seq((1, select(1, portfolio=Q))), 1)
        # a foreign row ABOVE the version is not looked at: only what is known at the version counts
        self.assertEqual(resolve_selection(P, seq((1, select(1)), (9, select(9, portfolio=Q))), 1).state, SelectionState.IN_FORCE)

    def test_duplicates_and_bad_versions_are_refused(self):
        with self.assertRaises(BenchmarkSelectionError):
            resolve_selection(P, seq((1, select(1)), (1, select(2))), 1)
        with self.assertRaises(BenchmarkSelectionError):
            resolve_selection(P, seq((1, select(1)), (2, select(1))), 2)
        for bad in (-1, True, 1.0, "1"):
            with self.assertRaises(ValueError):
                resolve_selection(P, [], bad)

    def test_the_order_the_rows_are_given_in_does_not_matter(self):
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 2, 1))), (3, reversal(3, 2, D(2026, 2, 2))), (4, select(4, "CSI", D(2026, 3, 1))))
        results = {resolve_selection(P, list(p), 4).row.selection.benchmark_id for p in itertools.permutations(rows)}
        self.assertEqual(results, {"CSI"})


class PinTests(unittest.TestCase):
    """The UAT-03 foundation: changing the selection changes the pin; the same selection at the same version gives the same pin."""

    def pins(self):
        rows = seq((1, select(1, "SPX", D(2026, 1, 5))), (2, select(2, "NDX", D(2026, 2, 1))), (3, reversal(3, 2, D(2026, 2, 2))), (4, clear(4, D(2026, 3, 1))))
        return {v: pin_of(resolve_selection(P, rows, v)) for v in (0, 1, 2, 3, 4)}

    def test_every_change_of_the_selection_changes_the_pin(self):
        pins = self.pins()
        self.assertEqual(len({p.digest for p in pins.values()}), 5)
        self.assertEqual([p.state for p in pins.values()], ["NONE", "IN_FORCE", "IN_FORCE", "IN_FORCE", "CLEARED"])
        self.assertEqual([p.benchmark_id for p in pins.values()], [None, "SPX", "NDX", "SPX", None])

    def test_a_pin_with_nothing_in_force_still_names_its_version(self):
        # everything withdrawn at version 2: NONE, and not the same question as version 0 (the knowledge differs)
        rows = seq((1, select(1)), (2, reversal(2, 1)))
        none_at_2 = pin_of(resolve_selection(P, rows, 2))
        none_at_0 = pin_of(resolve_selection(P, rows, 0))
        self.assertEqual((none_at_2.state, none_at_2.version, none_at_2.selection_id), ("NONE", 2, None))
        self.assertNotEqual(none_at_2.digest, none_at_0.digest)

    def test_the_pin_names_the_row_and_the_version(self):
        p = self.pins()[2]
        self.assertEqual((p.version, p.selection_id, p.selection_seq, p.record_type, p.origin, p.selected_on), (2, str(sid(2)), 2, "SELECT", "USER_CHOSEN", "2026-02-01"))
        self.assertEqual(p.to_obj()["schema"], bs.PIN_SCHEMA)

    def test_reversing_back_restores_the_row_but_not_the_version(self):
        pins = self.pins()
        self.assertEqual(pins[3].row_digest, pins[1].row_digest)      # the same SPX row is in force again
        self.assertEqual(pins[3].selection_id, pins[1].selection_id)
        self.assertNotEqual(pins[3].digest, pins[1].digest)           # but it is a different knowledge version: a different question

    def test_the_pin_is_deterministic(self):
        self.assertEqual(self.pins()[3].digest, self.pins()[3].digest)
        a = pin_of(resolve_selection(P, seq((1, select(1))), 1))
        b = pin_of(resolve_selection(P, seq((1, select(1))), 1))
        self.assertEqual(a, b)
        self.assertEqual(len(a.digest), 64)

    def test_a_change_of_any_stored_field_changes_the_row_digest(self):
        base = SequencedSelection(1, select(1)).digest
        for other in (select(1, "NDX"), select(1, on=D(2026, 1, 6)), BenchmarkSelection(sid(1), P, RecordType.SELECT, D(2026, 1, 5), "SPX", None, Origin.RECOMMENDATION_ACCEPTED),
                      BenchmarkSelection(sid(1), P, RecordType.SELECT, D(2026, 1, 5), "SPX", "c1", Origin.USER_CHOSEN)):
            self.assertNotEqual(SequencedSelection(1, other).digest, base)
        self.assertNotEqual(SequencedSelection(2, select(1)).digest, base)


class PureModuleTests(unittest.TestCase):
    def test_the_module_reads_no_clock_and_does_no_io(self):
        import ast  # noqa: PLC0415

        text = (Path(__file__).resolve().parents[2] / "src" / "domain" / "benchmark_selection.py").read_text(encoding="utf-8")
        imported = set()
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.Import):
                imported |= {a.name.split(".")[0] for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported <= {"__future__", "datetime", "hashlib", "json", "re", "uuid", "dataclasses", "enum", "typing"}, imported)
        self.assertNotIn(".now(", text)
        self.assertNotIn(".today(", text)


if __name__ == "__main__":
    unittest.main()
