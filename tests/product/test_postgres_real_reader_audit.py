"""F1 R3, PostgreSQL: the behavioural half of the reader audit (design 1 item 6, fact 11; the source half is `test_real_labels.py`).

A real root is a canonical `portfolio` row plus an S2 `rw_root` row; it has NO `web_saved_sandbox` row. Shown on a disposable TEST install
with a crafted root (E11 crafted: the owner role writes the `portfolio` row; never product evidence): the saved-sandbox readers that
fact 11 names start at `web_saved_sandbox`, so they neither list the root nor find it by its id, whoever asks, and the owner of the root
included. The control is a saved sandbox portfolio written the way the product writes one, which the same readers do find, so the
checks can fail.
"""
from __future__ import annotations

import contextlib
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import web_account_store as accounts, web_workspace_store as workspaces  # noqa: E402
from real_gateway_kit import GatewayCase, setUpModule, tearDownModule  # noqa: E402,F401


class OnConnection(accounts.WebAccountStore):
    """The product class with its `connect` replaced by a given connection (the disposable database's owner role, E11)."""

    def __init__(self, conn, schema):
        self.schema, self._conn = schema, conn

    def connect(self):
        return contextlib.nullcontext(self._conn)


class ReaderAuditTests(GatewayCase):
    INSTALL = "readeraudit"

    def setUp(self):
        super().setUp()
        self.reader = self.conn("owner")
        self.reader.execute(f'SET search_path TO "{self.s}", pg_temp')
        self.store = OnConnection(self.reader, self.s)
        self.snap, _valid, _ = self.publish(valid_in=300.0)               # the context a root-link row refers to

    def test_a_crafted_real_shaped_root_is_neither_listed_nor_found_by_the_saved_sandbox_readers(self):
        ctx = self.snap.context_id
        owner_id, root_id = self.craft_root(ctx)
        # the control comes first: a user with NO portfolio lists nothing, and the readers raise NotFound for an id that does not exist
        self.assertEqual(self.store.list_portfolios(str(owner_id)), [])
        for read in (lambda: workspaces.WorkspaceStore(self.store, None)._initial(self.reader, str(owner_id), root_id),
                     lambda: workspaces.WorkspaceStore(self.store, None)._initial(self.reader, str(owner_id), uuid.uuid4())):
            with self.assertRaises(accounts.AccountStoreError) as caught:
                read()
            self.assertEqual((caught.exception.status, caught.exception.code), (404, "NOT_FOUND"))
        # the root exists, owned by that user, in the canonical table the readers join to
        self.assertEqual(self.owner.execute(f"SELECT user_id FROM {self.s}.portfolio WHERE portfolio_id=%s", (root_id,)).fetchone()[0], owner_id)
        self.assertEqual(self.owner.execute(f"SELECT count(*) FROM {self.s}.web_saved_sandbox WHERE portfolio_id=%s", (root_id,)).fetchone()[0], 0)

    def test_the_control_a_saved_sandbox_row_is_found_by_the_same_readers(self):
        """So that the refusal above can fail: add the sandbox row the product's own create writes, and the readers find the portfolio."""
        ctx = self.snap.context_id
        owner_id, root_id = self.craft_root(ctx)
        columns = [r[0] for r in self.owner.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='web_saved_sandbox' ORDER BY ordinal_position", (self.s,)).fetchall()]
        self.assertIn("portfolio_id", columns)
        values = {"portfolio_id": root_id, "name": "control", "request_json": '{"as_of": "2026-01-02"}', "snapshot_json": "{}",
                  "snapshot_sha256": "0" * 64, "ledger_version": 1, "created_at": self.db_now(), "mode": "LOCAL_SYNTHETIC_ACCOUNT", "synthetic": True}
        usable = [c for c in columns if c in values]
        required = self.owner.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_schema=%s AND table_name='web_saved_sandbox' AND is_nullable='NO' "
            "AND column_default IS NULL", (self.s,)).fetchall()
        missing = {r[0] for r in required} - set(usable)
        if missing:
            self.skipTest("the control row needs columns this test does not know: %s" % sorted(missing))
        self.owner.execute(f"ALTER TABLE {self.s}.web_saved_sandbox DISABLE TRIGGER USER")
        try:
            self.owner.execute(f"INSERT INTO {self.s}.web_saved_sandbox({','.join(usable)}) VALUES ({','.join(['%s'] * len(usable))})", [values[c] for c in usable])
        finally:
            self.owner.execute(f"ALTER TABLE {self.s}.web_saved_sandbox ENABLE TRIGGER USER")
        listed = self.store.list_portfolios(str(owner_id))
        self.assertEqual([row["portfolio_id"] for row in listed], [str(root_id)])
        found = workspaces.WorkspaceStore(self.store, None)._initial(self.reader, str(owner_id), root_id)
        self.assertIsNotNone(found)
