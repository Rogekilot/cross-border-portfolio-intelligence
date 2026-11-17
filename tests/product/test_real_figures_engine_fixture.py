"""PD-0080: the engine-made document the real-mode key figures are proved on (`web/src/real-mode-engine-result.fixture.json`).

What is shown here, and how far it goes without the R8 wiring:

  * REGENERATION. The checked-in fixture is exactly what `real_figures_engine_fixture.records()` produces now from the real performance engine and invented
    inputs. A change of the engine (or of the invented inputs, or of the serialization) that changes the document fails this test until the fixture is
    regenerated on purpose and the client tests re-run.
  * THE SERIALIZATION PATH. `real_service.service._stage_real` stores `compute_for_portfolio(...).canonical_json().encode("utf-8")`. The fixture is made with the
    same `ComputationResult.canonical_json()` bytes, parsed the way the route parses the stored document. This is shown by reading the source (AST) of `_stage_real`
    and of `compute_for_portfolio`, and by the types at run time.
  * THE STORED PATH IN MEMORY (TR7F-L-4). `compute_for_portfolio` refuses synthetic market data (CP3-10), and `performance_kit`'s invented worlds are synthetic: the
    test calls it on one (with only the database read `_pin` replaced) and shows the refusal. It CAN run in memory on the non-synthetic kit of
    `test_performance_midpoint` (`market(None, real_quotes=True)`), and the test does that on ledgers of the `OPENING_POSITION` + `OPENING_CASH` shape `_write_root`
    writes, a BUY ledger and a suppressed one, and compares it with `engine.compute`: the rows are equal except `manifest_id`, and the manifest differs only in
    `detection_policy` and `split_detection`. Nothing of that output is stored or checked in (`synthetic: false` over an invented reading).
  * WHAT STAYS FIRST-RUN AT R8. The REAL create is not
    selected by any route until R8, so no stored instance of this document exists. What stays FIRST-RUN at R8: the document `_stage_real` stores for REAL_SOURCE data
    (real prices, `detection` and the policy citation in the manifest, the identity rows) read back through the route and shown by the screen. The rows the
    screen reads (`metrics[]`) are produced by the same `engine.compute` call; the manifest of the fixture lacks the detection citation `compute_for_portfolio`
    adds, which no figure reads.
"""
from __future__ import annotations

import ast
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import real_figures_engine_fixture as gen  # noqa: E402
import test_performance_midpoint as mp  # noqa: E402
from corporate_actions_service import split_confirmation as f8b  # noqa: E402
from performance import engine  # noqa: E402
from performance.manifest import ComputationResult  # noqa: E402
from performance_service import service as performance_service  # noqa: E402

SRC = HERE.parents[1] / "src"


def _function(path: Path, name: str) -> ast.FunctionDef:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(found) == 1, name
    return found[0]


def _dump(node: ast.AST) -> str:
    return ast.dump(node, annotate_fields=False)


class EngineFixtureTests(unittest.TestCase):
    def test_the_checked_in_fixture_is_what_the_engine_makes_now(self):
        stored = json.loads(gen.FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(stored, gen.records(), "regenerate web/src/real-mode-engine-result.fixture.json: python tests/product/real_figures_engine_fixture.py")
        # byte for byte too: the file is the generator's compact, key-sorted output plus the newline `print` adds
        self.assertEqual(gen.FIXTURE.read_text(encoding="utf-8"), json.dumps(gen.records(), sort_keys=True, separators=(",", ":")) + "\n")

    def test_the_regeneration_is_deterministic(self):
        self.assertEqual(gen.documents(), gen.documents())

    def test_the_four_cases_are_the_states_the_figures_must_handle(self):
        docs = gen.documents()
        state = lambda name, metric: [m["state"] for m in docs[name]["metrics"] if (m["metric_id"], m["view"]) == (metric, "REPORTING")]
        self.assertEqual(state("AVAILABLE", "portfolio_value"), ["AVAILABLE"])
        self.assertEqual(state("LIMITED", "portfolio_value"), ["LIMITED"])
        self.assertEqual(state("SUPPRESSED", "portfolio_value"), ["INSUFFICIENT_DATA"])
        self.assertEqual(state("SUPPRESSED", "portfolio_value_priced_holdings"), ["AVAILABLE"])       # the partial figure exists only here (Ruling 1.4a)
        for name in ("AVAILABLE", "LIMITED", "SUBCENT"):
            self.assertEqual(state(name, "portfolio_value_priced_holdings"), [], name)
        limited = next(m for m in docs["LIMITED"]["metrics"] if (m["metric_id"], m["view"]) == ("portfolio_value", "REPORTING"))
        self.assertEqual(limited["stale_weight_presented"], "0.555632726768")
        sub = {m["metric_id"]: m for m in docs["SUBCENT"]["metrics"] if m["view"] == "REPORTING"}
        self.assertEqual((sub["portfolio_value"]["value"], [line[1] for line in sub["portfolio_value"]["breakdown"]]), ("2.01", ["1.01", "1"]))
        self.assertEqual(sub["holding_value"]["value"], "1")                                            # the row alone says 1, the breakdown says 1.01
        # H-2: 3 shares and a recorded 1-for-2 split: the quantity is unresolved; the partial row has no value and stores counts of 0 and 0
        split = {(m["metric_id"], m["view"]): m for m in docs["SPLIT_UNRESOLVED"]["metrics"]}
        for key in (("portfolio_value", "REPORTING"), ("portfolio_value_priced_holdings", "REPORTING"), ("holding_value", "REPORTING")):
            self.assertEqual((split[key]["state"], split[key]["reason"], split[key]["value"]), ("INSUFFICIENT_DATA", "UNRESOLVED_CONVENTION", None), key)
        self.assertEqual(split[("portfolio_value_priced_holdings", "REPORTING")]["lineage"],
                         [["excluded_components", "0"], ["excluded_holdings", "0"], ["included_components", "0"]])
        # G-6: the accrued-dividend case, against the Quant's hand values (total 11228.21; parts 5128.21, 6000, 100)
        rec = {m["metric_id"]: m for m in docs["RECEIVABLE"]["metrics"] if m["view"] == "REPORTING"}
        self.assertEqual(rec["portfolio_value"]["value"], "11228.21")
        self.assertEqual([line[1] for line in rec["portfolio_value"]["breakdown"]], ["5128.21", "6000", "100"])
        (receivable_row,) = [m for m in docs["RECEIVABLE"]["metrics"] if (m["metric_id"], m["view"]) == ("receivable_value", "REPORTING")]
        self.assertEqual(receivable_row["value"], "100")
        account, event = receivable_row["subject"][0][1], receivable_row["subject"][1][1]
        self.assertEqual(rec["portfolio_value"]["breakdown"][2][0], f"receivable:{account}/{event}")
        for document in docs.values():
            self.assertEqual(sorted(document), ["manifest", "manifest_id", "metrics", "result_digest"])  # the keys of a ComputationResult, not of the CP5 result

    def test_the_documents_are_made_with_the_serialization_that_stage_real_stores(self):
        stage = _function(SRC / "real_service" / "service.py", "_stage_real")
        statements = [_dump(node) for node in ast.walk(stage)]
        # `result = performance_service.compute_for_portfolio(...)` then `issued = result.canonical_json().encode("utf-8")`
        compute_calls = [node for node in ast.walk(stage) if isinstance(node, ast.Call) and _dump(node.func) == _dump(ast.parse("performance_service.compute_for_portfolio", mode="eval").body)]
        self.assertEqual(len(compute_calls), 1)
        expected = _dump(ast.parse('result.canonical_json().encode("utf-8")', mode="eval").body)
        assigns = [node for node in ast.walk(stage) if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == ["issued"]]
        self.assertEqual([_dump(node.value) for node in assigns], [expected])
        self.assertIn("ComputationResult", " ".join(statements))                                        # `type(result) is ComputationResult` guards it
        # the generator parses exactly those bytes
        generator = _function(HERE / "real_figures_engine_fixture.py", "_document")
        self.assertIn(_dump(ast.parse('result.canonical_json().encode("utf-8")', mode="eval").body), [_dump(node) for node in ast.walk(generator)])
        # at run time: the engine's result is a ComputationResult, and the stored document is the parse of its canonical bytes
        w = gen.pk.world_w()
        result = gen._compute(gen.pk.example_w_ledger(w.h), gen.D(2025, 4, 2), w)
        self.assertIs(type(result), ComputationResult)
        self.assertEqual(gen._document(result), json.loads(result.canonical_json().encode("utf-8")))

    def test_compute_for_portfolio_calls_the_same_engine_function_the_generator_calls(self):
        call = _function(SRC / "performance_service" / "service.py", "compute_for_portfolio")
        names = [node.func.id for node in ast.walk(call) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
        self.assertEqual(names.count("compute"), 1)
        self.assertIs(performance_service.compute, engine.compute)
        self.assertTrue(any(isinstance(node, ast.Call) and getattr(node.func, "id", "") == "_finish" for node in ast.walk(call)))

    def test_result_is_assigned_exactly_once_in_stage_real_so_nothing_edits_it_before_it_is_stored(self):
        stage = _function(SRC / "real_service" / "service.py", "_stage_real")
        stores = [node for node in ast.walk(stage) if isinstance(node, ast.Name) and node.id == "result" and isinstance(node.ctx, (ast.Store, ast.Del))]
        self.assertEqual(len(stores), 1)
        stage_calls = [node for node in ast.walk(stage) if isinstance(node, ast.Call) and getattr(node.func, "attr", "") in ("replace", "_replace")]
        self.assertEqual(stage_calls, [])

    def test_the_service_on_the_in_memory_kit_returns_the_engines_rows_unchanged(self):
        """TR7F-L-4. `compute_for_portfolio` (with only `_pin` replaced) against `engine.compute` on the same ledgers, in memory, nothing stored. The ledgers include
        the `OPENING_POSITION` + `OPENING_CASH` shape `_write_root` writes, a BUY ledger, and a suppressed one that must keep its partial figure."""
        port = mp.market(None, real_quotes=True)
        self.assertFalse(port.contains_synthetic)
        docs = {}
        for name, ledger, day in self._ledgers():
            a, b = self._served(ledger, day, port), self._direct(ledger, day, port)
            self.assertEqual(self._without_id(a), self._without_id(b), name)                              # every row, none dropped, none changed
            differing = sorted(k for k in set(a["manifest"]) | set(b["manifest"]) if a["manifest"].get(k) != b["manifest"].get(k))
            self.assertEqual(differing, ["detection_policy", "split_detection"], name)
            self.assertEqual(sorted(a), sorted(b))
            self.assertFalse(a["manifest"]["synthetic"])                                                  # in memory only: never stored or checked in
            docs[name] = a
        kept = lambda name: {(m["metric_id"], m["view"], m["state"]) for m in docs[name]["metrics"]}
        self.assertIn(("portfolio_value", "REPORTING", "INSUFFICIENT_DATA"), kept("suppressed"))
        self.assertIn(("portfolio_value_priced_holdings", "REPORTING", "AVAILABLE"), kept("suppressed"))  # the partial figure survives `_finish`
        # TR7F2-L-2: a LIMITED NAV and its stale weight survive `_finish` (the Quant's F-1 condition)
        self.assertIn(("portfolio_value", "REPORTING", "LIMITED"), kept("stale"))
        nav = next(m for m in docs["stale"]["metrics"] if (m["metric_id"], m["view"]) == ("portfolio_value", "REPORTING"))
        self.assertIsInstance(nav["stale_weight_presented"], str)

    # ---- the in-memory comparison and its mutants (nothing is stored; the mutants live in memory only) -----------------------------------------
    def _ledgers(self):
        def opening():
            L = mp.pk.Ledger()
            L.add(mp.A1, gen.EventType.OPENING_POSITION, mp.D(2025, 2, 5), mp.USD, listing_id=mp.LISTING, quantity=gen.Decimal(50))
            L.add(mp.A1, gen.EventType.OPENING_CASH, mp.D(2025, 2, 5), mp.USD, amount=mp.Money(gen.Decimal("1000.004"), mp.USD))
            return L

        def suppressed():
            L = opening()
            L.add(mp.A1, gen.EventType.DEPOSIT, mp.D(2025, 2, 6), gen.CNH, amount=mp.Money(gen.Decimal(1000), gen.CNH))
            return L

        # the last close is 2025-02-07: as of 2025-02-12 the holding's price is three sessions old, so the total is LIMITED (STALE_DATA) with a stale weight
        return (("opening", opening(), mp.D(2025, 2, 7)), ("buy", mp.base_ledger(), mp.D(2025, 2, 7)), ("suppressed", suppressed(), mp.D(2025, 2, 7)),
                ("stale", opening(), mp.D(2025, 2, 12)))

    @staticmethod
    def _without_id(doc):
        return [{k: v for k, v in m.items() if k != "manifest_id"} for m in doc["metrics"]]

    def _served(self, ledger, day, port, finish=None):
        patches = [mock.patch.object(performance_service, "_pin", return_value=(ledger.version, tuple(ledger.rows)))]
        if finish is not None:
            patches.append(mock.patch.object(performance_service, "_finish", finish))
        with patches[0]:
            if len(patches) == 2:
                with patches[1]:
                    served = performance_service.compute_for_portfolio(None, mp.ca.PORTFOLIO, day, mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=mp.ca.POLICY)
            else:
                served = performance_service.compute_for_portfolio(None, mp.ca.PORTFOLIO, day, mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=mp.ca.POLICY)
        self.assertIs(type(served), ComputationResult)
        return json.loads(served.canonical_json())

    @staticmethod
    def _direct(ledger, day, port):
        direct = engine.compute(ledger.rows, ledger.version, day, mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, portfolio_id=mp.ca.PORTFOLIO, suppressions=())
        return json.loads(direct.canonical_json())

    def test_the_comparison_bites_on_in_memory_mutants_of_finish(self):
        """TR7F2-L-2. The mutants replace `_finish` in memory (never in a file): each must make the comparison fail on at least one ledger."""
        port = mp.market(None, real_quotes=True)
        real_finish = performance_service._finish

        class Doc:
            """A stand-in for the ComputationResult that `_finish` returned, with its canonical JSON edited."""
            def __init__(self, result, edit):
                self._result, self._edit = result, edit

            def canonical_json(self):
                doc = json.loads(self._result.canonical_json())
                self._edit(doc)
                return json.dumps(doc, sort_keys=True)

        def drop_weight(doc):
            for m in doc["metrics"]:
                m["stale_weight_presented"] = None

        def drop_partial(doc):
            doc["metrics"] = [m for m in doc["metrics"] if m["metric_id"] != "portfolio_value_priced_holdings"]

        def drop_first_row(doc):
            doc["metrics"] = doc["metrics"][1:]

        for label, edit in (("drops stale_weight_presented", drop_weight), ("drops the partial figure", drop_partial), ("drops a row", drop_first_row)):
            def mutant(result, *args, _edit=edit, **kw):
                done = real_finish(result, *args, **kw)
                return Doc(done, _edit)
            failures = 0
            for name, ledger, day in self._ledgers():
                with mock.patch.object(performance_service, "_pin", return_value=(ledger.version, tuple(ledger.rows))), \
                        mock.patch.object(performance_service, "_finish", mutant):
                    served = performance_service.compute_for_portfolio(None, mp.ca.PORTFOLIO, day, mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=mp.ca.POLICY)
                if self._without_id(json.loads(served.canonical_json())) != self._without_id(self._direct(ledger, day, port)):
                    failures += 1
            self.assertGreater(failures, 0, label)
        # the weight mutant is caught by the stale ledger in particular
        stale = [item for item in self._ledgers() if item[0] == "stale"][0]
        with mock.patch.object(performance_service, "_pin", return_value=(stale[1].version, tuple(stale[1].rows))), \
                mock.patch.object(performance_service, "_finish", lambda result, *a, **k: Doc(real_finish(result, *a, **k), drop_weight)):
            served = performance_service.compute_for_portfolio(None, mp.ca.PORTFOLIO, stale[2], mp.USD, port, mp.Ident(), mp.MARKET_CONVENTIONS, mp.PERF, policy=mp.ca.POLICY)
        self.assertNotEqual(self._without_id(json.loads(served.canonical_json())), self._without_id(self._direct(stale[1], stale[2], port)))

    def test_compute_for_portfolio_refuses_the_synthetic_kit_worlds_so_the_generator_calls_the_engine_directly(self):
        w = gen.pk.world_w()
        ledger = gen.pk.example_w_ledger(w.h)
        policy = f8b.ConfirmationPolicy(feed_sources=frozenset({"feed"}), filing_sources=frozenset({"filing"}))
        with mock.patch.object(performance_service, "_pin", return_value=(ledger.version, ledger.rows)):
            refused = performance_service.compute_for_portfolio(None, gen.PORTFOLIO, gen.D(2025, 4, 2), gen.USD, w.store, w.ident, w.market, gen.PERF, policy=policy)
        self.assertTrue(refused.manifest.synthetic)
        (row,) = refused.metrics
        self.assertIsNone(row.result.value)                                                              # no number
        self.assertIn("SYNTHETIC_MARKET_DATA_REFUSED", row.details)
        # and the engine-made documents are marked synthetic on every row, which is why that refusal applies to them
        for document in gen.documents().values():
            self.assertTrue(document["manifest"]["synthetic"])
            self.assertTrue(all(m["synthetic"] for m in document["metrics"]))


if __name__ == "__main__":
    unittest.main()
