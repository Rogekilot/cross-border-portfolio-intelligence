"""Owner-scoped immutable workspace commands around the issued ledger/policy models.

No financial arithmetic lives here. Every confirmed or previewed ledger state is
replayed by the existing engine; previews roll their entire transaction back.
"""
from __future__ import annotations

import datetime as dt
import json
import uuid
from contextlib import nullcontext
from dataclasses import replace
from decimal import Decimal
from fractions import Fraction

import psycopg

from domain.benchmark_selection import BenchmarkSelection, Origin, RecordType
from domain.catalogs import BenchmarkCatalog, BenchmarkNotInCatalogError, CatalogError
from domain.currency import CurrencyCode, Money
from domain.ledger import EventType, FIELD_RULES, LedgerEvent, SplitRatio, validate_correction_pair
from domain.replay import SequencedEvent, reconstruct
from insight_service.sources import verify_source
from insights.contracts import InsightRefusal, UserLimit
from insights.evidence import semantic_key
from insights.registry import POLICY_SELECTORS
from marketdata.canonical import canonical_json, sha256_hex
from persistence import benchmark_selection_store as selections
from persistence import ledger_replay_store, ledger_store
from persistence.web_account_store import AccountStoreError, not_found


def _uuid(text):
    try:
        return uuid.UUID(text)
    except (ValueError, TypeError, AttributeError):
        not_found()


def _policies(raw):
    rows = json.loads(raw)
    if not isinstance(rows,list) or not all(isinstance(row,dict) for row in rows):
        raise ValueError("Stored policies must be an array of policy objects")
    out = []
    for row in rows:
        if set(row) != set(UserLimit.__dataclass_fields__):
            raise ValueError("Stored policies must explicitly contain every serialized policy field")
        row["limit"] = Fraction(row["limit"])
        row["effective_from"] = dt.date.fromisoformat(row["effective_from"])
        if row["effective_until"] is not None:
            row["effective_until"] = dt.date.fromisoformat(row["effective_until"])
        row["subject"] = tuple(row["subject"])
        out.append(UserLimit(**row))
    return tuple(out)


class WorkspaceStore:
    def __init__(self, store, world):
        self.store, self.world = store, world

    def _initial(self, conn, user_id, ident):
        row = conn.execute("SELECT s.request_json,s.snapshot_json,s.snapshot_sha256,s.ledger_version,s.created_at "
            "FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) WHERE p.user_id=%s AND s.portfolio_id=%s",
            (uuid.UUID(user_id), ident)).fetchone()
        if row is None:
            not_found()
        return row

    def _record(self, conn, user_id, ident, revision_id=None):
        initial = self._initial(conn, user_id, ident)  # ownership BEFORE revision/source access
        try:
            request = json.loads(initial[0])
            if not isinstance(request,dict):
                raise ValueError("not an object")
        except (ValueError,TypeError):
            raise AccountStoreError(503,"SAVED_SOURCE_DIFFERS","Saved source metadata cannot be decoded") from None
        current = conn.execute("SELECT revision_id FROM web_portfolio_revision WHERE portfolio_id=%s ORDER BY revision_seq DESC LIMIT 1", (ident,)).fetchone()
        head = ident if current is None else current[0]
        wanted = head if revision_id is None else _uuid(revision_id)
        if wanted == ident:
            return dict(revision_id=ident, current_revision_id=head, request=request, snapshot_json=initial[1],
                snapshot_sha256=initial[2], ledger_version=initial[3], selection_version=0, policies=(),
                policies_state="NOT_STATED", as_of=self.world.as_of, initial=True, created_at=initial[4])
        row = conn.execute("SELECT revision_id,as_of,ledger_version,selection_version,policies_json,policies_state,snapshot_json,snapshot_sha256,created_at,revision_seq "
            "FROM web_portfolio_revision WHERE portfolio_id=%s AND revision_id=%s", (ident, wanted)).fetchone()
        if row is None:
            not_found()
        try:
            policies = _policies(row[4])
            if row[5] not in ("NOT_STATED","NONE","ACTIVE") or (row[5]=="ACTIVE") != bool(policies):
                raise ValueError("Stored personal policy state contradicts its records")
        except (ValueError,TypeError,KeyError,AttributeError,ZeroDivisionError):
            raise AccountStoreError(503,"SAVED_RESULT_DIFFERS","Saved personal policy metadata cannot be decoded") from None
        return dict(revision_id=row[0], current_revision_id=head, request=request, snapshot_json=row[6], snapshot_sha256=row[7],
            ledger_version=row[2], selection_version=row[3], policies=policies, policies_state=row[5], as_of=row[1], initial=False, created_at=row[8],revision_seq=row[9])

    def _events(self, conn, ident, pin):
        if pin > ledger_replay_store.current_ledger_version(conn, ident):
            raise ValueError("uncommitted ledger pin")
        ledger_replay_store.require_committed_boundary(conn, ident, pin)
        columns = ",".join("e." + col for col in ledger_store.EVENT_COLUMNS)
        records = conn.execute("SELECT e.ledger_seq," + columns + " FROM ledger_event e JOIN account a USING(account_id) "
            "WHERE a.portfolio_id=%s AND e.ledger_seq<=%s ORDER BY e.ledger_seq", (ident, pin)).fetchall()
        return tuple(SequencedEvent(*ledger_store.row_to_event(tuple(row))) for row in records)

    def _item(self, conn, ident, record):
        request = record["request"]
        if (request.get("source_sha256") != self.world.input_sha256 or request.get("calendar_sha256") != self.world.calendar_sha256
                or request.get("as_of") != self.world.as_of.isoformat()
                or sha256_hex(record["snapshot_json"].encode()) != record["snapshot_sha256"]):
            raise AccountStoreError(503, "SAVED_SOURCE_DIFFERS", "Saved source identity cannot be reproduced by this version")
        try:
            events = self._events(conn, ident, record["ledger_version"])
            if record["initial"]:
                item = self.world.create(ident, request, ledger_events=events)
            else:
                # A benchmark preference does not create benchmark data or CP4 history.
                pin = selections.selection_pin(conn, ident, record["selection_version"]).to_obj()
                item = self.world.create(ident, request, ledger_events=events, as_of=record["as_of"], policies=record["policies"], workspace=True,benchmark_pin=pin)
            item = self.store._persisted(item)
            if item.snapshot_json != record["snapshot_json"]:
                raise ValueError("complete saved snapshot differs")
            return item, events
        except (ValueError, TypeError, KeyError, ArithmeticError) as error:
            raise AccountStoreError(503, "SAVED_RESULT_DIFFERS", "Saved ledger, policy or financial proof cannot be reproduced exactly") from error

    def read(self, user_id, portfolio_id, *, revision_id=None, connection=None):
        ident = _uuid(portfolio_id)
        context = self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            record = self._record(conn, user_id, ident, revision_id)
            return self._item(conn, ident, record)[0]

    def _targets(self, item):
        evidence = verify_source(item.source, allow_synthetic=True)
        if isinstance(evidence, InsightRefusal):
            raise ValueError(evidence.code)
        context = evidence.context()
        return [dict(source_kind=evidence.source_kind, metric_id=row["metric_id"], subject=row.get("subject", []),
                     semantic_key=semantic_key(evidence, row), scope_kind="PORTFOLIO", account_id=None,
                     unit=row.get("unit"), state=row["state"])
            for row in evidence.payload()["metrics"] if row["metric_id"] in POLICY_SELECTORS[evidence.source_kind]]

    def _catalog(self):
        try:
            catalog = self.world.benchmark_catalog_provider()
            if not isinstance(catalog,BenchmarkCatalog):
                raise CatalogError("The injected provider did not return a BenchmarkCatalog")
            return catalog
        except CatalogError:
            raise AccountStoreError(503,"BENCHMARK_CATALOG_UNAVAILABLE",
                "The admitted benchmark catalog is unavailable or malformed; no empty catalog or selection is substituted") from None

    def _workspace(self, conn, ident, record, item, events, *, catalog_metadata=True):
        initial = conn.execute("SELECT created_at FROM web_saved_sandbox WHERE portfolio_id=%s", (ident,)).fetchone()
        history = [dict(revision_id=str(ident),parent_revision_id=None,created_at=initial[0],operation="OPENING")]
        history += [dict(revision_id=str(row[0]),parent_revision_id=str(row[1]),created_at=row[2],operation=row[3])
            for row in conn.execute("SELECT revision_id,parent_revision_id,created_at,operation FROM web_portfolio_revision "
                "WHERE portfolio_id=%s ORDER BY revision_seq", (ident,)).fetchall()]
        # Accounts added after a historical pin must not appear in its workspace.
        account_rows = conn.execute("SELECT account_id,name FROM account WHERE portfolio_id=%s ORDER BY account_id", (ident,)).fetchall()
        visible_accounts = {uuid.uuid5(ident,"guest-account")}
        visible_accounts.update(uuid.uuid5(row[0],"account") for row in conn.execute(
            "SELECT operation_id FROM web_portfolio_revision WHERE portfolio_id=%s AND operation='ADD_ACCOUNT' AND revision_seq<=%s",
            (ident,record.get("revision_seq",0))).fetchall())
        visible_accounts.update(entry.event.account_id for entry in events)
        if record.get("preview_account_id") is not None:
            visible_accounts.add(record["preview_account_id"])
        account_rows = [row for row in account_rows if row[0] in visible_accounts]
        reversed_by = {entry.event.reverses_event_id: str(entry.event.event_id) for entry in events if entry.event.reverses_event_id}
        values = []
        for entry in events:
            event = entry.event
            value = dict(event_id=str(event.event_id),ledger_seq=entry.ledger_seq,event_type=event.event_type.value,
                account_id=str(event.account_id),event_date=event.event_date,currency=event.currency.code,
                listing_id=None if event.listing_id is None else str(event.listing_id),
                quantity=event.quantity, amount=None if event.amount is None else event.amount.amount,
                cost_basis=None if event.cost_basis is None else event.cost_basis.amount,
                bought_amount=None if event.bought_amount is None else dict(amount=event.bought_amount.amount,currency=event.bought_amount.currency.code),
                split_ratio=None if event.split_ratio is None else dict(new_units=event.split_ratio.new_units,old_units=event.split_ratio.old_units),
                counterparty_account_id=None if event.counterparty_account_id is None else str(event.counterparty_account_id),
                settlement_date=event.settlement_date,ex_date=event.ex_date,acquired_on=event.acquired_on,
                reverses_event_id=None if event.reverses_event_id is None else str(event.reverses_event_id),
                corrects_event_id=None if event.corrects_event_id is None else str(event.corrects_event_id),
                source_reference=event.source_reference,reversed_by=reversed_by.get(event.event_id))
            values.append(value)
        pin = selections.selection_pin(conn, ident, record["selection_version"]).to_obj()
        benchmark=dict(state={"NONE":"NOT_STATED","CLEARED":"NONE","IN_FORCE":"SELECTED"}[pin["state"]],pin=pin)
        if catalog_metadata:
            catalog=self._catalog()
            benchmark.update(catalog_id=catalog.catalog_id,entries=[entry.to_obj() for entry in catalog.entries],selection_available=bool(catalog.entries))
        return dict(schema_version="finweb.cp7/1",portfolio_id=str(ident),revision_id=str(record["revision_id"]),
            current_revision_id=str(record["current_revision_id"]),as_of=record["as_of"],fixture_as_of=self.world.as_of,
            history=history,accounts=[dict(account_id=str(row[0]),name=row[1]) for row in account_rows],
            ledger=dict(version=record["ledger_version"],events=values,current_state=reconstruct(events,record["as_of"],record["ledger_version"]).to_canonical_dict(),
                field_rules={kind.value:dict(rules) for kind,rules in FIELD_RULES.items()}),
            listings=self.world.capabilities()["listings"],
            policies=dict(state=record["policies_state"],items=[p.to_obj() for p in record["policies"]],targets=self._targets(item)),
            benchmark=benchmark)

    def workspace(self, user_id, portfolio_id, *, revision_id=None, connection=None):
        ident = _uuid(portfolio_id)
        context = self.store.connect() if connection is None else nullcontext(connection)
        with context as conn:
            record = self._record(conn,user_id,ident,revision_id)
            item, events = self._item(conn,ident,record)
            return self._workspace(conn,ident,record,item,events)

    def _event(self, body, operation_id, index, accounts, *, corrects=None):
        account = _uuid(body["account_id"])
        counterparty = None if body.get("counterparty_account_id") is None else _uuid(body["counterparty_account_id"])
        if account not in accounts or counterparty is not None and counterparty not in accounts:
            not_found()
        listing = None if body.get("listing_id") is None else _uuid(body["listing_id"])
        if listing is not None and listing not in self.world.listings.values():
            raise ValueError("Only the acknowledged fictional listings can be recorded in this sandbox")
        currency = CurrencyCode(body["currency"])
        def money(name):
            return None if body.get(name) is None else Money(Decimal(body[name]),currency)
        def day(name):
            return None if body.get(name) is None else dt.date.fromisoformat(body[name])
        bought, ratio = body.get("bought_amount"),body.get("split_ratio")
        return LedgerEvent(event_id=uuid.uuid5(operation_id,"event:"+str(index)),account_id=account,
            event_type=EventType(body["event_type"]),event_date=day("event_date"),currency=currency,
            listing_id=listing,quantity=None if body.get("quantity") is None else Decimal(body["quantity"]),
            amount=money("amount"),cost_basis=money("cost_basis"),
            bought_amount=None if bought is None else Money(Decimal(bought["amount"]),CurrencyCode(bought["currency"])),
            split_ratio=None if ratio is None else SplitRatio(Decimal(ratio["new_units"]),Decimal(ratio["old_units"])),
            counterparty_account_id=counterparty,settlement_date=day("settlement_date"),ex_date=day("ex_date"),acquired_on=day("acquired_on"),
            corrects_event_id=corrects,source_reference="CP7 web operation:"+str(operation_id)+":"+str(index))

    def _append(self, conn, ident, body, old_events):
        operation, op = body["operation"],uuid.UUID(body["operation_id"])
        inputs, targets = body["events"],body["target_event_ids"]
        accounts = {row[0] for row in conn.execute("SELECT account_id FROM account WHERE portfolio_id=%s",(ident,)).fetchall()}
        if operation == "ADD_ACCOUNT":
            name = body["account_name"]
            if inputs or targets or not name or not name.strip() or any(ord(char)<32 for char in name) or len(accounts)>=16:
                raise ValueError("New account needs a visible name, no events/targets, and capacity below sixteen")
            conn.execute("INSERT INTO account VALUES(%s,%s,%s)",(uuid.uuid5(op,"account"),ident,name.strip()))
            return
        if body["account_name"] is not None:
            raise ValueError("account_name only belongs to ADD_ACCOUNT")
        if operation == "APPEND" and (not inputs or targets):
            raise ValueError("APPEND needs event inputs and no targets")
        if operation == "CORRECT" and (not targets or len(inputs)!=len(targets)):
            raise ValueError("CORRECT pairs each target with one replacement")
        if operation == "REVERSE" and (not targets or inputs):
            raise ValueError("REVERSE needs only targets")
        known = {str(entry.event.event_id):entry.event for entry in old_events}
        batch = []
        for index, target_id in enumerate(targets):
            if target_id not in known:
                not_found()
            target = known[target_id]
            reversal = LedgerEvent(event_id=uuid.uuid5(op,"reversal:"+str(index)),account_id=target.account_id,
                event_type=EventType.REVERSAL,event_date=dt.date.fromisoformat(body["as_of"]),currency=target.currency,
                reverses_event_id=target.event_id,source_reference="CP7 web reversal:"+str(op)+":"+str(index))
            batch.append(reversal)
            if operation == "CORRECT":
                replacement = self._event(inputs[index],op,index,accounts,corrects=target.event_id)
                validate_correction_pair(reversal,replacement)
                batch.append(replacement)
        if operation == "APPEND":
            batch = [self._event(value,op,index,accounts) for index,value in enumerate(inputs)]
        ledger_store.append_batch(conn,batch)

    def _preferences(self, conn, ident, body, previous, item):
        if body["policies_confirmed"] is not True:
            raise ValueError("Policies require an explicit confirmation")
        targets = self._targets(item)
        policies, ids = [],set()
        for row in body["policies"]:
            if row["policy_id"] in ids:
                raise ValueError("Duplicate personal policy id")
            ids.add(row["policy_id"])
            key = (row["source_kind"],row["metric_id"],row["scope_kind"],row["account_id"],row["subject"],row["semantic_key"])
            if not any(key == (t["source_kind"],t["metric_id"],t["scope_kind"],t["account_id"],t["subject"],t["semantic_key"]) for t in targets):
                raise ValueError("Policy does not name an explicitly offered metric scope and semantic key")
            policies.append(UserLimit(**{**row,"portfolio_id":str(ident),"version":body["operation_id"],
                "subject":tuple(row["subject"]),"limit":Fraction(row["limit"]),"effective_from":dt.date.fromisoformat(row["effective_from"]),
                "effective_until":None if row["effective_until"] is None else dt.date.fromisoformat(row["effective_until"])}))
        benchmark = body["benchmark"]
        action = benchmark["action"]
        if action == "KEEP":
            if benchmark["benchmark_id"] is not None or benchmark["selected_on"] is not None:
                raise ValueError("KEEP does not declare a benchmark or date")
        else:
            if benchmark["selected_on"] is None or (action=="SELECT") != (benchmark["benchmark_id"] is not None):
                raise ValueError("An explicit selection/clear needs a selected_on date and appropriate benchmark id")
            catalog = self._catalog()
            selection = BenchmarkSelection(selection_id=uuid.uuid5(uuid.UUID(body["operation_id"]),"benchmark"),portfolio_id=ident,
                record_type=RecordType.SELECT if action=="SELECT" else RecordType.CLEAR,
                selected_on=dt.date.fromisoformat(benchmark["selected_on"]),benchmark_id=benchmark["benchmark_id"],
                origin=Origin.USER_CHOSEN if action=="SELECT" else None)
            selections.append_selection(conn,selection,catalog=catalog)
        return tuple(policies),"ACTIVE" if policies else "NONE",selections.current_selection_version(conn,ident)

    def command(self, user_id, portfolio_id, body, *, preferences=False, preview=False, connection=None, prepared_events=None, execution_scope=None):
        ident, operation_id = _uuid(portfolio_id),uuid.UUID(body["operation_id"])
        command_hash = sha256_hex(canonical_json(dict(kind="PREFERENCES" if preferences else "LEDGER",body=body)).encode())
        result = None
        try:
            context = self.store.connect() if connection is None else nullcontext(connection)
            with context as conn, conn.transaction():
                self._initial(conn,user_id,ident)
                conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",("finweb.web_revision.portfolio:"+self.store.schema+":"+str(ident),))
                existing = conn.execute("SELECT revision_id,command_sha256 FROM web_portfolio_revision WHERE portfolio_id=%s AND operation_id=%s",(ident,operation_id)).fetchone()
                if existing is not None:
                    if existing[1] != command_hash:
                        raise AccountStoreError(409,"IDEMPOTENCY_CONFLICT","This operation id already names different content")
                    record = self._record(conn,user_id,ident,str(existing[0]))
                    item,events = self._item(conn,ident,record)
                    value = dict(workspace=self._workspace(conn,ident,record,item,events),snapshot=item.snapshot())
                    if preview:
                        self._preview(value)
                    return value
                record = self._record(conn,user_id,ident)
                if str(record["revision_id"]) != body["expected_revision_id"]:
                    raise AccountStoreError(409,"STALE_REVISION","The saved workspace changed; reload before confirming")
                if conn.execute("SELECT count(*) FROM web_portfolio_revision WHERE portfolio_id=%s",(ident,)).fetchone()[0]>=1000:
                    raise AccountStoreError(429,"REVISION_CAPACITY_REACHED","Local workspace revision capacity reached")
                old_item,old_events = self._item(conn,ident,record)
                policies,state,selection_version = record["policies"],record["policies_state"],record["selection_version"]
                if preferences:
                    policies,state,selection_version = self._preferences(conn,ident,body,record,old_item)
                elif prepared_events is not None:
                    if body["operation"]!="APPEND":
                        raise ValueError("Prepared imported facts use only APPEND")
                    ledger_store.append_batch(conn,prepared_events)
                else:
                    self._append(conn,ident,body,old_events)
                # Validate deferred matching/atomicity rules in previews as well as commits.
                if execution_scope is None:
                    conn.execute("SET CONSTRAINTS ALL IMMEDIATE")
                else:
                    from persistence.guarded_workspace_context import validate_domain_constraints
                    validate_domain_constraints(conn, execution_scope)
                pin = ledger_replay_store.current_ledger_version(conn,ident)
                events = self._events(conn,ident,pin)
                day = dt.date.fromisoformat(body["as_of"])
                benchmark_pin = selections.selection_pin(conn,ident,selection_version).to_obj()
                item = self.store._persisted(self.world.create(ident,record["request"],ledger_events=events,as_of=day,policies=policies,workspace=True,benchmark_pin=benchmark_pin))
                revision_id = uuid.uuid5(operation_id,"revision")
                next_record = {**record,"revision_id":revision_id,"current_revision_id":revision_id,"ledger_version":pin,"selection_version":selection_version,
                    "policies":policies,"policies_state":state,"as_of":day,"initial":False,"snapshot_json":item.snapshot_json,
                    "snapshot_sha256":sha256_hex(item.snapshot_json.encode())}
                if not preview:
                    next_record["revision_seq"] = conn.execute("INSERT INTO web_portfolio_revision (revision_id,portfolio_id,parent_revision_id,operation_id,operation,command_sha256,as_of,ledger_version,selection_version,policies_json,policies_state,snapshot_json,snapshot_sha256,created_at) "
                        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING revision_seq",
                        (revision_id,ident,record["revision_id"],operation_id,"PREFERENCES" if preferences else body["operation"],command_hash,day,pin,selection_version,
                         canonical_json([p.to_obj() for p in policies]),state,item.snapshot_json,next_record["snapshot_sha256"],self.store.clock())).fetchone()[0]
                else:
                    next_record.update(revision_id=record["revision_id"],current_revision_id=record["current_revision_id"])
                    if body.get("operation")=="ADD_ACCOUNT":
                        # The preview account exists only until this transaction rolls back.
                        next_record["preview_account_id"] = uuid.uuid5(operation_id,"account")
                result = dict(workspace=self._workspace(conn,ident,next_record,item,events),snapshot=item.snapshot(),**({"preview":True} if preview else {}))
                if preview:
                    self._preview(result)
                    raise psycopg.Rollback()
        except BenchmarkNotInCatalogError:
            raise AccountStoreError(422,"BENCHMARK_NOT_ADMITTED","This benchmark is not in the admitted catalog; no choice was saved") from None
        except psycopg.IntegrityError:
            raise AccountStoreError(422,"WORKSPACE_COMMAND_REFUSED","The append-only ledger's matching or cross-event rules refused this command") from None
        except (ValueError,TypeError,KeyError,ArithmeticError,ledger_store.LedgerStoreError,selections.SelectionStoreError) as error:
            raise AccountStoreError(422,"WORKSPACE_COMMAND_REFUSED","The ledger or explicit preference rules refused this command: "+str(error).split("\n",1)[0][:250]) from None
        return result

    @staticmethod
    def _preview(value):
        value["preview"] = True
        value["snapshot"]["persisted"] = False
        notes = value["snapshot"]["limitations"]
        value["snapshot"]["limitations"] = [note for note in notes if not note.startswith("SAVED_SYNTHETIC_SANDBOX:")]
        value["snapshot"]["limitations"].insert(1,"PREVIEW_NOT_SAVED: rollback-only proposal; no stored artifact or committed proof pin.")
