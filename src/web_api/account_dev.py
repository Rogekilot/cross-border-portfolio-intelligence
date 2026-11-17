"""Explicit local account-review entry point; no migration or owner credentials.

Root provisions a schema and grants separately, then sets FINWEB_CP7_PG_SOCKET,
FINWEB_CP7_PG_DATABASE, FINWEB_CP7_PG_USER and FINWEB_CP7_PG_SCHEMA. The existing
guest-only launcher stays unchanged. No .env, passwords or secret files are read.
"""
import os

from persistence.connection import build_conninfo
from persistence.web_account_store import WebAccountStore
from web_api.app import create_app
from web_api.auth import AuthSettings

required = ("FINWEB_CP7_PG_SOCKET", "FINWEB_CP7_PG_DATABASE", "FINWEB_CP7_PG_USER", "FINWEB_CP7_PG_SCHEMA")
if any(not os.environ.get(key) for key in required):
    raise RuntimeError("Explicit local CP7 PostgreSQL socket/database/non-owner role/schema configuration is required")

store = WebAccountStore(build_conninfo(socket=os.environ[required[0]], dbname=os.environ[required[1]],
    user=os.environ[required[2]]), os.environ[required[3]])
app = create_app(enable_local_guest=True, enable_saved_synthetic=True,
                 account_store=store, auth_settings=AuthSettings.local())
