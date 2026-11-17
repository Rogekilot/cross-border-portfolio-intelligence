"""Read-only owned revision and source context, isolated from historical snapshots."""
import datetime as dt
import hashlib
import uuid
from dataclasses import dataclass
from pathlib import Path

from domain.catalogs import BenchmarkCatalog,CatalogError,RiskFreeCatalog
from performance.ledger_view import inception_of
from performance.periods import WindowRule,WindowSpec,resolve_window
from performance.series import MaxAvailable
from persistence import benchmark_selection_store as selections
from persistence.web_account_store import AccountStoreError,not_found
from persistence.web_workspace_store import WorkspaceStore,_uuid
from risk_service.catalogs import load_risk_free_catalog

LIMITS=dict(calculation_days=3660,output_bytes=2000000,http_bytes=32768)
FIXTURE_ROOT=Path(__file__).with_name("fixtures")


class AnalyticsError(Exception):
    def __init__(self,status,code,detail,kind="REQUEST"):
        self.status,self.code,self.detail,self.kind=status,code,detail,kind


def specification(window):
    if window["rule"]=="MAX_AVAILABLE":
        return MaxAvailable()
    return WindowSpec(WindowRule(window["rule"]),window["months"],None if window["base"] is None else dt.date.fromisoformat(window["base"]))


def guard_span(events,pin,question,fixture_as_of):
    """A local work bound, not a modification of a financial window or cause."""
    end=dt.date.fromisoformat(question["as_of"])
    dates=[end,fixture_as_of]
    for entry in events:
        event=entry.event
        for name in ("event_date","settlement_date","ex_date","acquired_on"):
            day=getattr(event,name,None)
            if day is not None:
                dates.append(day)
    try:
        account=None if question["scope"]["account_id"] is None else uuid.UUID(question["scope"]["account_id"])
        inception=inception_of(events,pin,account)
        spec=specification(question["window"])
        specs=[WindowSpec(WindowRule.SINCE_INCEPTION) if isinstance(spec,MaxAvailable) else spec]
        if question["view"]=="DEFAULT":
            specs.append(WindowSpec(WindowRule.SINCE_INCEPTION))
        for window in specs:
            resolved=resolve_window(window,end,inception,"NOT_RECONSTRUCTABLE")
            declared=resolved.window or resolved.declared
            if declared is not None:
                dates.extend((declared.start,declared.end))
    except (ValueError,OverflowError):
        raise AnalyticsError(422,"ANALYTICS_REQUEST_REFUSED","The explicit date/window cannot be represented safely") from None
    if (max(dates)-min(dates)).days+1>LIMITS["calculation_days"]:
        raise AnalyticsError(422,"ANALYTICS_SPAN_LIMIT","This local analytics request spans more than3660 natural dates; choose an eligible revision/scope/window without clamping its history","RESOURCE")


def verify_fixture_bytes(world):
    try:
        for name,expected in (("quotes-v1.json",world.input_sha256),("calendar-v1.json",world.calendar_sha256)):
            if hashlib.sha256((FIXTURE_ROOT/name).read_bytes()).hexdigest()!=expected:
                raise ValueError("fixture bytes differ")
    except (OSError,ValueError):
        raise AnalyticsError(503,"ANALYTICS_SOURCE_DIFFERS","The original fictional quote/calendar bytes are unavailable or differ from this source context","SOURCE") from None


@dataclass(frozen=True)
class AnalyticsContext:
    portfolio_id:uuid.UUID
    record:dict
    events:tuple
    accounts:tuple
    reporting_currency:object
    world:object
    selection_rows:tuple
    benchmark_catalog:object=None
    risk_free_catalog:object=None


def _visible_accounts(conn,ident,pin,revision_seq):
    """Identity rows only: no stored JSON decoding or financial replay."""
    visible={uuid.uuid5(ident,"guest-account")}
    visible.update(row[0] for row in conn.execute("SELECT DISTINCT e.account_id FROM ledger_event e JOIN account a USING(account_id) "
        "WHERE a.portfolio_id=%s AND e.ledger_seq<=%s",(ident,pin)).fetchall())
    visible.update(uuid.uuid5(row[0],"account") for row in conn.execute(
        "SELECT operation_id FROM web_portfolio_revision WHERE portfolio_id=%s AND operation='ADD_ACCOUNT' AND revision_seq<=%s",
        (ident,revision_seq)).fetchall())
    return tuple(dict(account_id=str(row[0]),name=row[1]) for row in conn.execute(
        "SELECT account_id,name FROM account WHERE portfolio_id=%s ORDER BY account_id",(ident,)).fetchall() if row[0] in visible)


def load_context(conn,store,world,user_id,portfolio_id,question,*,group=None,risk_free_provider=None):
    ident=_uuid(portfolio_id)
    workspace=WorkspaceStore(store,world)
    # The sealed _record decodes initial source JSON before looking up a later
    # revision. Prove all requested identities here before entering that helper.
    initial=conn.execute("SELECT s.ledger_version FROM web_saved_sandbox s JOIN portfolio p USING(portfolio_id) "
        "WHERE p.user_id=%s AND s.portfolio_id=%s",(uuid.UUID(user_id),ident)).fetchone()
    if initial is None:
        not_found()
    requested=_uuid(question["revision_id"])
    pin,revision_seq=initial[0],0
    if requested!=ident:
        target=conn.execute("SELECT revision_id,as_of,ledger_version,revision_seq FROM web_portfolio_revision "
            "WHERE portfolio_id=%s AND revision_id=%s",(ident,requested)).fetchone()
        if target is None:
            not_found()
        pin,revision_seq=target[2],target[3]
    accounts=None
    if question["scope"]["account_id"] is not None:
        accounts=_visible_accounts(conn,ident,pin,revision_seq)
        if question["scope"]["account_id"] not in {row["account_id"] for row in accounts}:
            not_found()
    record=workspace._record(conn,user_id,ident,question["revision_id"])
    if record["as_of"].isoformat()!=question["as_of"]:
        raise AnalyticsError(409,"ANALYTICS_AS_OF_DIFFERS","The question's as-of date differs from the explicitly selected revision","BINDING")
    if accounts is None:
        accounts=_visible_accounts(conn,ident,record["ledger_version"],record.get("revision_seq",0))
    verify_fixture_bytes(world)  # portfolio/revision/scope before disk/provider access
    try:
        events=workspace._events(conn,ident,record["ledger_version"])
    except ValueError:
        raise AccountStoreError(503,"SAVED_SOURCE_DIFFERS","The revision's committed ledger boundary is unavailable") from None
    guard_span(events,record["ledger_version"] ,question,world.as_of)
    workspace._item(conn,ident,record)  # preserve old complete snapshot verification
    reporting=world.currency
    row=conn.execute("SELECT reporting_currency FROM portfolio WHERE portfolio_id=%s",(ident,)).fetchone()
    if row is None or row[0]!=reporting.code:
        raise AccountStoreError(503,"SAVED_SOURCE_DIFFERS","The saved reporting currency differs from the fictional source context")
    selection_rows=()
    benchmark_catalog=risk_free_catalog=None
    if question["family"]=="RISK":
        version=selections.current_selection_version(conn,ident)
        if record["selection_version"]>version:
            raise AccountStoreError(503,"SAVED_SOURCE_DIFFERS","The pinned benchmark selection is unavailable")
        selection_rows=selections.load_selections(conn,ident,record["selection_version"])
        try:
            risk_free_catalog=(load_risk_free_catalog if risk_free_provider is None else risk_free_provider)()
            if not isinstance(risk_free_catalog,RiskFreeCatalog):
                raise CatalogError("Invalid risk-free provider result")
            if group!="INDEPENDENT":
                benchmark_catalog=world.benchmark_catalog_provider()
                if not isinstance(benchmark_catalog,BenchmarkCatalog):
                    raise CatalogError("Invalid benchmark provider result")
        except CatalogError:
            raise AnalyticsError(503,"ANALYTICS_CATALOG_UNAVAILABLE","A required admitted catalog is unavailable or malformed; no empty catalog is substituted","SOURCE") from None
    return AnalyticsContext(ident,record,events,accounts,reporting,world,tuple(selection_rows),benchmark_catalog,risk_free_catalog)
