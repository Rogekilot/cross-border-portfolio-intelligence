"""E1 declarations/refusals over generated metadata; no market payload or database."""
import asyncio
import copy
import hashlib
import json
import sys
import tempfile
import unittest
import uuid
from contextlib import ExitStack
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import psycopg
from marketdata.canonical import canonical_json
from web_api import auth
from web_api.app import create_app
from web_api.real_requests import parse_create_gate
from web_api.real_source_contexts import (ConfiguredSourceDescriptor, MetadataFile, MetadataProvider,
    MODE, RealSourceError, inspect_configured_metadata, real_capabilities, validate_descriptor)

TOKEN = "T" * 43
ORIGIN = "http://127.0.0.1:5173"
GET = "/api/v1/real-source-contexts"
POST = "/api/v1/real-portfolios"


def intent(**changes):
    value = dict(operation_id=str(uuid.UUID(int=1)), mode=MODE, source_context_id="a"*64,
        expected_configuration_digest="b"*64, release_id="c"*64, as_of="2026-01-02",
        constructed_ledger_acknowledged=True)
    value.update(changes)
    return value


def metadata_objects():
    # Independent metadata declarations; the referenced quote payload is never created.
    registry = dict(sources=[dict(source_id="example.us", name="Generated declaration",
        upstream_provider="Generated test", independence_group="generated", terms_url=None,
        synthetic=False, terms_check=dict(checked_by="PRIVATE_CHECKER_NEVER_PUBLIC", checked_on="2026-01-01",
            permits_internal_development_use=True, notes="Generated metadata; not an actual source admission"))])
    manifest = dict(schema="finweb.marketdata.file_manifest/1", file_sha256="1"*64, size_bytes=123,
        payload_filename="NEVER_OPEN.csv", payload_format="generated_test_only", source_id="example.us",
        data_kind="QUOTE", market="US", retrieval_time="2026-01-02T23:00:00Z", retrieved_by="human",
        request=[], declared_adjustment="UNDECLARED", adjustment_anchor=None, declared_currency="USD",
        declared_delay="UNKNOWN", source_identifiers=[], script=dict(name=None,version=None,script_sha256=None),
        libraries=[], usage_scope="INTERNAL_DEVELOPMENT_ONLY", coverage=[])
    content = dict(schema="finweb.marketdata.release/1", name="Generated declaration only", files=["1"*64],
        source_precedence=["example.us"], conventions=[], created_for="E1 metadata test", convention_set_id="market-data/1.14")
    release = {**content, "release_id": hashlib.sha256(canonical_json(content).encode()).hexdigest()}
    return dict(SOURCE_REGISTRY=registry, RELEASE_DECLARATION=release, FILE_MANIFEST=manifest)


def metadata_provider(root, objects=None, context_id="a"*64):
    objects = metadata_objects() if objects is None else objects
    entries = []
    for role, obj in objects.items():
        raw = canonical_json(obj).encode()
        name = role.lower()+".json"
        (root/name).write_bytes(raw)
        entries.append(MetadataFile(name, hashlib.sha256(raw).hexdigest(), role))
    descriptor = ConfiguredSourceDescriptor(context_id, objects["RELEASE_DECLARATION"]["release_id"],
        ("example.us",), tuple(entries))
    return MetadataProvider(root, (descriptor,), tuple(entries))


async def raw_request(app, method, path, *, body=b"", query=b"", chunks=None, headers=None, reads=None):
    headers = headers if headers is not None else [("Origin", ORIGIN), ("Cookie", "finweb_session="+TOKEN),
        ("X-Finweb-CSRF", auth.csrf_token(TOKEN))]
    pairs = [(b"host", b"127.0.0.1:8000")]
    if method == "POST":
        pairs.append((b"content-type", b"application/json"))
    pairs += [(key.lower().encode(), value.encode()) for key,value in headers]
    chunks = list(chunks) if chunks is not None else [body]
    messages = [dict(type="http.request",body=part,more_body=index<len(chunks)-1) for index,part in enumerate(chunks)]
    sent = []
    async def receive():
        if reads is not None:
            reads.append(True)
        return messages.pop(0) if messages else dict(type="http.disconnect")
    async def send(message):
        sent.append(message)
    await app(dict(type="http",asgi=dict(version="3.0"),http_version="1.1",method=method,scheme="http",
        path=path,raw_path=path.encode(),query_string=query,root_path="",headers=pairs,
        client=("127.0.0.1",12345),server=("127.0.0.1",8000)),receive,send)
    start = next(row for row in sent if row["type"]=="http.response.start")
    data = b"".join(row.get("body",b"") for row in sent if row["type"]=="http.response.body")
    return start["status"],json.loads(data),dict(start["headers"])


class SessionOnlyStore:
    def __init__(self):
        self.lookups = []
        self.active = True
        self.failure = False

    def session_user(self, token):
        self.lookups.append(token)
        if self.failure:
            raise psycopg.OperationalError("PRIVATE_STORAGE_EXCEPTION")
        return dict(user_id=str(uuid.UUID(int=1)),username="fictional") if token==TOKEN and self.active else None

    def __getattr__(self,name):
        raise AssertionError("E1 touched another store method: "+name)


def gate_app(provider=None, store=None):
    store = SessionOnlyStore() if store is None else store
    if provider is None:
        return create_app(account_store=store,auth_settings=auth.AuthSettings.local(),enable_saved_synthetic=True),store
    with patch("web_api.real_routes.MetadataProvider",return_value=provider):
        app=create_app(account_store=store,auth_settings=auth.AuthSettings.local(),enable_saved_synthetic=True)
    return app,store


class SourceMetadataTests(unittest.TestCase):
    def test_default_no_io_and_never_financially_enabled(self):
        with patch("web_api.real_source_contexts.os.open",side_effect=AssertionError("filesystem read")):
            value=real_capabilities(MetadataProvider())
        self.assertEqual(value["contexts"],[]);self.assertEqual(value["approved_context_count"],0)
        self.assertEqual(value["state"],"BLOCKED")
        self.assertEqual({key for key,enabled in value["capabilities"].items() if enabled},{"source_metadata"})

    def test_exact_generated_metadata_is_only_configured_and_private_fields_absent(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));value=real_capabilities(provider)
        context=value["contexts"][0]
        self.assertEqual(context["status"],"CONFIGURED_NOT_VERIFIED")
        self.assertEqual(context["readiness_stage"],"METADATA_ONLY")
        self.assertFalse(context["financially_qualified"])
        self.assertEqual(context["payload_integrity"],"NOT_VERIFIED")
        for secret in (temp,"PRIVATE_CHECKER_NEVER_PUBLIC","NEVER_OPEN.csv","terms_check"):
            self.assertNotIn(secret,canonical_json(value))

    def test_strict_roles_empty_sources_files_and_duplicate_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));obj=provider.descriptors[0].to_obj()
            for changes in (dict(metadata_files=[]),dict(declared_source_ids=[]),dict(approved=True),
                    dict(metadata_files=[{}]*3),dict(metadata_files=obj["metadata_files"]*2),
                    dict(declared_source_ids=["example.us","example.us"])):
                with self.subTest(changes=changes),self.assertRaises(ValueError):
                    validate_descriptor({**obj,**changes})

    def test_all_roles_and_nested_metadata_reject_coherently_rehashed_bad_fields(self):
        mutations=[("SOURCE_REGISTRY",lambda row:row.update(approved=True)),
            ("SOURCE_REGISTRY",lambda row:row["sources"][0].pop("synthetic")),
            ("SOURCE_REGISTRY",lambda row:row["sources"][0]["terms_check"].pop("notes")),
            ("SOURCE_REGISTRY",lambda row:row["sources"][0]["terms_check"].update(permits_internal_development_use=False)),
            ("SOURCE_REGISTRY",lambda row:row["sources"][0].update(source_priority=True)),
            ("RELEASE_DECLARATION",lambda row:row.update(approved=True)),
            ("RELEASE_DECLARATION",lambda row:row.update(files=[])),
            ("FILE_MANIFEST",lambda row:row.update(approved=True)),
            ("FILE_MANIFEST",lambda row:row.update(size_bytes=True)),
            ("FILE_MANIFEST",lambda row:row["script"].update(approved=True)),
            ("FILE_MANIFEST",lambda row:row.pop("coverage")),
            ("FILE_MANIFEST",lambda row:row.update(data_kind="FX")),
            ("FILE_MANIFEST",lambda row:row.update(file_sha256="2"*64)),
            ("FILE_MANIFEST",lambda row:row.update(source_id="other.us")),
            ("FILE_MANIFEST",lambda row:row.update(payload_filename="../forbidden.csv"))]
        for role,mutate in mutations:
            with self.subTest(role=role,mutation=mutate),tempfile.TemporaryDirectory() as temp:
                objects=metadata_objects();mutate(objects[role]);provider=metadata_provider(Path(temp),objects)
                with self.assertRaises(RealSourceError) as caught:
                    real_capabilities(provider)
                self.assertEqual((caught.exception.status,caught.exception.code),(503,"REAL_SOURCE_CONFIGURATION_UNAVAILABLE"))

    def test_registry_and_release_empty_objects_never_match(self):
        for role in ("SOURCE_REGISTRY","FILE_MANIFEST"):
            with tempfile.TemporaryDirectory() as temp:
                objects=metadata_objects();objects[role]={}
                with self.assertRaises(RealSourceError):
                    real_capabilities(metadata_provider(Path(temp),objects))

    def test_every_call_rechecks_metadata_rights_and_bytes_no_cached_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);provider=metadata_provider(root);real_capabilities(provider)
            path=root/"source_registry.json";path.write_bytes(b"changed bytes")
            with self.assertRaises(RealSourceError):real_capabilities(provider)
            objects=metadata_objects();objects["SOURCE_REGISTRY"]["sources"][0]["terms_check"]["permits_internal_development_use"]=False
            with self.assertRaises(RealSourceError):real_capabilities(metadata_provider(root,objects))

    def test_missing_metadata_is_not_an_empty_context_and_is_sanitized(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));(Path(temp)/"file_manifest.json").unlink()
            with self.assertRaises(RealSourceError) as caught:real_capabilities(provider)
            self.assertNotIn(temp,str(caught.exception))

    def test_separate_allowlist_traversal_symlink_and_nonregular_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp,tempfile.TemporaryDirectory() as outside:
            root=Path(temp);provider=metadata_provider(root)
            with self.assertRaises(RealSourceError):real_capabilities(MetadataProvider(root,provider.descriptors,()))
            obj=provider.descriptors[0].to_obj();obj["metadata_files"][0]["relative_path"]="../escape"
            with self.assertRaises(ValueError):validate_descriptor(obj)
            target=Path(outside)/"registry.json";target.write_bytes((root/"source_registry.json").read_bytes())
            (root/"source_registry.json").unlink();(root/"source_registry.json").symlink_to(target)
            with self.assertRaises(RealSourceError):real_capabilities(provider)

    def test_bounded_file_aggregate_and_output_refuse_whole_response(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp))
            for name,value in (("MAX_FILE_BYTES",10),("MAX_METADATA_BYTES",10),("MAX_OUTPUT_BYTES",10)):
                with self.subTest(limit=name),patch("web_api.real_source_contexts."+name,value),self.assertRaises(RealSourceError):
                    real_capabilities(provider)

    def test_only_matching_post_descriptor_inspected_and_context_mixing_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));value=real_capabilities(provider)["contexts"][0]
            good=intent(expected_configuration_digest=value["configuration_digest"],release_id=value["declared_release_id"])
            other=copy.deepcopy(provider.descriptors[0].to_obj());other["context_id"]="d"*64
            other["metadata_files"][0]["relative_path"]="missing-unrelated.json"
            provider.descriptors+=(other,)
            for body,code in ((good,"REAL_PORTFOLIO_CREATION_DISABLED"),
                    ({**good,"expected_configuration_digest":"0"*64},"REAL_SOURCE_CONFIGURATION_DIFFERS"),
                    ({**good,"release_id":"0"*64},"REAL_SOURCE_CONFIGURATION_DIFFERS"),
                    ({**good,"source_context_id":"0"*64},"REAL_SOURCE_NOT_CONFIGURED")):
                with self.subTest(code=code),self.assertRaises(RealSourceError) as caught:provider.refuse(body)
                self.assertEqual(caught.exception.code,code)
            with self.assertRaises(RealSourceError):real_capabilities(provider)

    def test_contexts_are_sorted_unique_and_source_array_is_exact(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));one=provider.descriptors[0]
            two=ConfiguredSourceDescriptor("0"*64,one.declared_release_id,one.declared_source_ids,one.metadata_files)
            provider.descriptors=(one,two)
            self.assertEqual([v["context_id"] for v in real_capabilities(provider)["contexts"]],["0"*64,"a"*64])
            provider.descriptors=(one,one)
            with self.assertRaises(RealSourceError):real_capabilities(provider)


class RealGateRouteTests(unittest.TestCase):
    def setUp(self):
        self.app,self.store=gate_app()

    def call(self,method,path,**kwargs):
        return asyncio.run(raw_request(self.app,method,path,**kwargs))

    def test_default_get_post_and_repeat_are_blocked_not_financial_results(self):
        status,value,headers=self.call("GET",GET)
        self.assertEqual(status,200);self.assertEqual(value,real_capabilities(MetadataProvider()))
        self.assertEqual(headers[b"cache-control"],b"no-store");self.assertEqual(headers[b"x-content-type-options"],b"nosniff")
        self.assertNotIn(b"set-cookie",headers)
        for body in (intent(),intent(),intent(as_of="2026-01-03")):
            status,value,_=self.call("POST",POST,body=json.dumps(body).encode())
            self.assertEqual((status,value["error"]["code"]),(409,"REAL_SOURCE_NOT_CONFIGURED"))
            self.assertNotIn("state",value["error"])

    def test_strict_body_injection_types_missing_fields_and_duplicate_keys(self):
        for key in ("name","positions","cash","events","payload","path","url","owner_id","registry","quote","timestamp","approved","contains_synthetic"):
            with self.subTest(key=key):
                status,value,_=self.call("POST",POST,body=json.dumps({**intent(),key:"PRIVATE_INPUT"}).encode())
                self.assertEqual(status,422);self.assertNotIn("PRIVATE_INPUT",str(value))
        for key,value in (("operation_id",str(uuid.UUID(int=1)).upper()+"x"),("as_of","2026-02-30"),
                ("source_context_id","a"*64+"\n"),("constructed_ledger_acknowledged",1),("constructed_ledger_acknowledged",False)):
            with self.subTest(key=key),self.assertRaises(RealSourceError):parse_create_gate(json.dumps(intent(**{key:value})).encode())
        for raw in (b'{}',b'{"mode":"x","mode":"y"}',b'{"x":NaN}',b'\xff',b'[]'):
            status,value,_=self.call("POST",POST,body=raw);self.assertEqual(status,422)

    def test_authentication_precedes_query_body_and_provider(self):
        self.store.active=False
        for method,path,changes in (("GET",GET,dict(query=b"path=PRIVATE")),("GET",GET,dict(body=b"body")),
                ("POST",POST,dict(body=b"malformed JSON"))):
            with self.subTest(method=method),patch("web_api.real_source_contexts.os.open",side_effect=AssertionError("source read")):
                status,value,_=self.call(method,path,**changes)
                self.assertEqual((status,value["error"]["code"]),(401,"AUTHENTICATION_REQUIRED"))

    def test_get_rejects_every_query_and_stops_first_nonempty_stream_chunk(self):
        for query in (b"x=1",b"x=1&x=2",b"path=PRIVATE"):
            reads=[];status,value,_=self.call("GET",GET,query=query,body=b"ignored",reads=reads)
            self.assertEqual(status,422);self.assertEqual(reads,[]);self.assertNotIn("PRIVATE",str(value))
        reads=[];status,_value,_=self.call("GET",GET,chunks=[b"",b"x",b"never-consumed"],reads=reads)
        self.assertEqual(status,422);self.assertEqual(len(reads),2)

    def test_csrf_origin_duplicate_headers_and_malformed_json_do_not_bypass_auth(self):
        headers=[("Origin",ORIGIN),("Cookie","finweb_session="+TOKEN),("X-Finweb-CSRF",auth.csrf_token(TOKEN))]
        for changed in (headers[:2],headers+[("X-Finweb-CSRF",auth.csrf_token(TOKEN))],
                headers+[("Origin",ORIGIN)],[("Origin","https://invalid.example")]+headers[1:]):
            status,value,_=self.call("POST",POST,body=b"malformed",headers=changed)
            self.assertEqual(status,403)

    def test_existing_storage_and_disabled_mode_errors_stay_typed_and_private(self):
        self.store.failure=True
        status,value,_=self.call("GET",GET)
        self.assertEqual((status,value["error"]["code"]),(503,"ACCOUNT_STORAGE_UNAVAILABLE"))
        self.assertNotIn("PRIVATE_STORAGE_EXCEPTION",str(value))
        status,value,_=asyncio.run(raw_request(create_app(),"GET",GET))
        self.assertEqual((status,value["error"]["code"]),(503,"ACCOUNT_MODE_DISABLED"))

    def test_no_financial_or_payload_entry_reached_from_default_routes(self):
        targets=("marketdata.files.FileStore.read_by_hash","persistence.market_data_store.read_release",
            "marketdata.ingest.build_in_memory_market_data","marketdata.adapters.base.AdapterRegistry.for_manifest",
            "performance_service.service.compute_for_portfolio","persistence.web_account_store.WebAccountStore.create_portfolio")
        with ExitStack() as stack:
            for target in targets:stack.enter_context(patch(target,side_effect=AssertionError("E1 financial/payload entry")))
            self.assertEqual(self.call("GET",GET)[0],200)
            self.assertEqual(self.call("POST",POST,body=json.dumps(intent()).encode())[0],409)

    def test_configured_route_refusals_use_same_auth_and_no_qualified_response(self):
        with tempfile.TemporaryDirectory() as temp:
            provider=metadata_provider(Path(temp));app,_=gate_app(provider)
            status,value,_=asyncio.run(raw_request(app,"GET",GET));self.assertEqual(status,200)
            ctx=value["contexts"][0];body=intent(expected_configuration_digest=ctx["configuration_digest"],release_id=ctx["declared_release_id"])
            for changed,code in ((body,"REAL_PORTFOLIO_CREATION_DISABLED"),({**body,"release_id":"0"*64},"REAL_SOURCE_CONFIGURATION_DIFFERS")):
                status,value,_=asyncio.run(raw_request(app,"POST",POST,body=json.dumps(changed).encode()))
                self.assertEqual((status,value["error"]["code"]),(409,code))
            (Path(temp)/"file_manifest.json").write_bytes(b"changed")
            for method,path,raw in (("GET",GET,b""),("POST",POST,json.dumps(body).encode())):
                status,value,_=asyncio.run(raw_request(app,method,path,body=raw))
                self.assertEqual((status,value["error"]["code"]),(503,"REAL_SOURCE_CONFIGURATION_UNAVAILABLE"))
