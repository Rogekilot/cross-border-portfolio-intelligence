"""Base case of the F1 R5 PostgreSQL tests. Not a test module.

Everything stored is invented and labelled synthetic. A `SYNTHETIC_TEST` context is published through the product tool with the digests of the
INVENTED WORLD the product's fictional create builds (`real_worlds.fictional_snapshot_fields`), its provenance candidate is registered and bound,
and the tests call the PRODUCT create, read, reproduce and list code (`real_workspace_service`) on the executor role's connection. The owner role
seeds the invented identity rows (E11: the executor has no identity grant; the real seed step is an owner-run step of R6's plan) and the app user
(a registration writes no portfolio, account or ledger row).

Labels used by the tests of this increment:
  "product path, shared tail on SYNTHETIC_TEST"  the product's create, read, reproduce or list code on an accepted commit of the fictional branch
  "crafted (E11)"                                  a state the owner role wrote in the test's own disposable database, labelled "E11 crafted probe,
                                                   not product evidence"
  "first run at R8"                                not run here
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import pg_market_kit as pk  # noqa: E402
from persistence import real_tails  # noqa: E402
from persistence.real_proposal import Member  # noqa: E402
from real_service import worlds as real_worlds  # noqa: E402
from real_service.service import ProvenanceLink, RealWorkspaceService  # noqa: E402
from real_provenance_case import ProvCase  # noqa: E402
from web_api import real_scoped_contract as contract  # noqa: E402

MD_TABLES = ("md_file", "md_release", "md_release_file", "md_quote", "md_fx_rate", "md_corporate_action", "md_benchmark", "md_benchmark_point",
             "md_adjusted_quote", "md_calendar", "md_series_exclusion", "md_risk_free", "md_risk_free_point")


class RecordingConnection:
    """A statement recorder: wraps the executor's connection and records the text of every statement sent through `execute`. The tail, the
    service and the services they call all send their SQL through `conn.execute`, so the record is complete for the path under test. (The
    BEGIN and COMMIT of `conn.transaction()` are sent by the driver and are not recorded; the tests that need them look at outcomes.)"""

    def __init__(self, conn):
        self._conn = conn
        self.statements = []

    def execute(self, query, params=None, **kw):
        text = query if isinstance(query, str) else query.as_string(self._conn)
        self.statements.append(" ".join(text.split()))
        return self._conn.execute(query, params, **kw)

    def __getattr__(self, name):
        return getattr(self._conn, name)

    # ---- queries over the record ----------------------------------------------------------------------------------------------------
    def matching(self, *needles):
        return [s for s in self.statements if all(n in s for n in needles)]

    def set_constraints(self):
        return [s for s in self.statements if s.upper().startswith("SET CONSTRAINTS")]

    def admits(self):
        return [s for s in self.statements if "rw_admit" in s]


def referenced_tables(statement):
    """The names a statement reads after FROM or JOIN, with the schema qualifier and the quotes stripped (technical TR5R observation: a matcher
    on a literal `FROM md_` would pass vacuously, because the store writes `FROM "s".md_quote`)."""
    import re
    names = []
    for match in re.finditer(r"\b(?:FROM|JOIN)\s+((?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*)(?:\s*\.\s*(?:\"[^\"]+\"|[A-Za-z_][A-Za-z0-9_]*))?)", statement, re.I):
        raw = match.group(1).replace('"', "")
        names.append(raw.split(".")[-1].strip())
    return names


def md_table_reads(statements):
    """The statements that read an `md_*` TABLE (not a function of the same stem)."""
    return [s for s in statements if any(name in MD_TABLES for name in referenced_tables(s))]


def rw_md_calls(statements):
    return [s for s in statements if any(name.startswith("rw_md_") for name in referenced_tables(s))]


PRODUCT = "product path, shared tail on SYNTHETIC_TEST"
CRAFTED = "E11 crafted probe, not product evidence"
AS_OF = real_worlds.FICTIONAL_DAY.isoformat()


class R5Case(ProvCase):
    INSTALL = "r5"
    W = 4

    def setUp(self):
        super().setUp()
        self.fictional = real_worlds.build_fictional_world(uuid.UUID(int=0))
        if self.count("listing") == 0:
            pk.insert_identity(self.owner, self.fictional.world.resolver)         # E11: owner-seeded identity rows
        self.executor = self.conn("executor")
        self.service = RealWorkspaceService(self.s, executor_role=self.inst.roles["executor"], connect=lambda: self.inst.connect("executor"))

    # ---- fixtures ------------------------------------------------------------------------------------------------------------------
    def fictional_live(self, *, valid_in=120.0, label=""):
        """A published `SYNTHETIC_TEST` context whose snapshot is the invented world's, with its provenance candidate registered and bound."""
        stub = Member("0" * 64, "0" * 64, real_worlds.FICTIONAL_SOURCE, None, "r5.adapter", "1")
        fields = real_worlds.fictional_snapshot_fields([stub], None)
        content = {k: v for k, v in fields.items() if k != "members"}
        return self.live("SYNTHETIC_TEST", valid_in=valid_in, label=label, source_id=real_worlds.FICTIONAL_SOURCE, content=content)

    def evidence(self):
        """The expiry evidence of a renewal of a context whose only member source is the invented world's."""
        import real_gateway_fixtures as fx
        return fx.hg4_shape(self.bound(), sources=(real_worlds.FICTIONAL_SOURCE,))

    def link(self, live):
        return ProvenanceLink(live.cand.context_sha256, live.cand.members, live.cand.witnesses)

    def new_owner(self):
        owner = uuid.uuid4()
        with self.owner.transaction():
            self.owner.execute(f"INSERT INTO {self.s}.app_user(user_id) VALUES(%s)", (owner,))
        return owner

    def intent(self, live, op=None, *, quantity="2", cash="20", name="invented probe root", as_of=AS_OF, listing=None):
        return {"schema_version": contract.CREATE_SCHEMA, "operation_id": str(op or uuid.uuid4()), "source_context_id": live.ctx,
                "expected_release_id": live.snap.content["release"]["release_id"], "name": name, "reporting_currency": "USD", "as_of": as_of,
                "constructed_ledger_acknowledged": True,
                "opening_positions": [{"listing_id": str(listing or self.fictional.listing_id), "quantity": quantity, "cost_basis": None, "acquired_on": None}],
                "opening_cash": {"currency": "USD", "amount": cash}}

    def create(self, live, owner, body=None, *, generation=1, conn=None, service=None):
        body = body or self.intent(live)
        return (service or self.service).create(conn or self.executor, owner=owner, body=body, generation=generation, link=self.link(live)), body

    # ---- counts ---------------------------------------------------------------------------------------------------------------------
    def tables_for(self, root_id):
        queries = {
            "portfolio": ("portfolio", "portfolio_id=%s"), "rw_root": ("rw_root", "portfolio_id=%s"), "rw_revision": ("rw_revision", "portfolio_id=%s"),
            "account": ("account", "portfolio_id=%s"), "rw_root_link": ("rw_root_link", "root_id=%s"), "rw_lease": ("rw_lease", "root_id=%s"),
            "rw_artifact": ("rw_artifact", "root_id=%s"), "rw_operation": ("rw_operation", "root_id=%s"), "rw_journal": ("rw_journal", "root_id=%s"),
            "ledger_event": ("ledger_event", "account_id IN (SELECT account_id FROM %s.account WHERE portfolio_id=%%s)" % self.s),
        }
        return {name: self.count(table, where, (root_id,)) for name, (table, where) in queries.items()}

    def assertNothingLeft(self, root_id):
        counts = self.tables_for(root_id)
        self.assertEqual(set(counts.values()), {0}, counts)

    def root_of(self, owner, body):
        from real_service.service import root_id_for
        return root_id_for(owner, uuid.UUID(body["operation_id"]))
