"""Actual PostgreSQL case for finding M-3: the guarded app refuses to start without the R1 report SQL.

CONFIG is injected only by `tests/product/guarded_pg_runner.py --modules startup`, which provisions a schema with F2 and the
HTTP add-on but WITHOUT R1 (`connect(role)`, `schema`, `executor_conninfo`, `executor_role`, `owner_role`). Without CONFIG
every test skips. The test installs R1 itself, as the schema owner, to show the same schema then starts.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from psycopg import sql  # noqa: E402

from persistence.guarded_csv_report_store import install_guarded_csv_report  # noqa: E402
from persistence.guarded_workspace_context import GuardedWorkspaceError  # noqa: E402
from persistence.web_account_store import WebAccountStore  # noqa: E402
from web_api import guarded_dev  # noqa: E402

CONFIG = None


class GuardedStartupRequiresReportSql(unittest.TestCase):
    def setUp(self):
        if CONFIG is None:
            self.skipTest("runner-provisioned F3 CONFIG without the CSV report SQL required")
        self.store = WebAccountStore(CONFIG["executor_conninfo"], CONFIG["schema"])

    def refusal(self):
        with self.assertRaises(GuardedWorkspaceError) as caught:
            guarded_dev.require_report_installed(self.store)
        self.assertEqual(caught.exception.code, "F3_CSV_REPORT_NOT_INSTALLED")

    def test_zz_sequence_refuses_without_r1_starts_with_it_and_refuses_again_without_execute(self):
        # 1. F2 + HTTP add-on only: R1 absent -> distinct startup refusal (not a storage error, not a later UNKNOWN).
        self.refusal()
        # 2. The owner installs R1: the same executor now passes.
        with CONFIG["connect"]("owner") as owner:
            install_guarded_csv_report(owner, schema=CONFIG["schema"], executor_role=CONFIG["executor_role"])
        guarded_dev.require_report_installed(self.store)
        # 3. R1 present but EXECUTE withdrawn from the executor on one function -> refused again.
        with CONFIG["connect"]("owner") as owner:
            owner.execute(sql.SQL("REVOKE EXECUTE ON FUNCTION {}.gh_csv_report_precheck(uuid,uuid) FROM {}").format(
                sql.Identifier(CONFIG["schema"]), sql.Identifier(CONFIG["executor_role"])))
        self.refusal()
        # 4. Restored -> passes; the per-request behaviour of the app is untouched by this check.
        with CONFIG["connect"]("owner") as owner:
            owner.execute(sql.SQL("GRANT EXECUTE ON FUNCTION {}.gh_csv_report_precheck(uuid,uuid) TO {}").format(
                sql.Identifier(CONFIG["schema"]), sql.Identifier(CONFIG["executor_role"])))
        guarded_dev.require_report_installed(self.store)


if __name__ == "__main__":
    unittest.main()
