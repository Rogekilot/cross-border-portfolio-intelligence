"""Shared provisioning of disposable guarded-F3 / account objects on a named PostgreSQL cluster.

Not a test module (the name does not match `test*.py`). Used by `guarded_pg_runner.py` (integration runner) and `dev_env.py`
(local development environment). Everything is created under ONE run prefix (`own`); every drop goes through `owned_name`,
which refuses any name that does not fully match that prefix. A role or database is recorded as created ONLY AFTER its
CREATE statement succeeded (review finding L-1), so cleanup can never drop an object this run did not create.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parents[1] / "src"
for entry in (str(SRC), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from persistence.connection import build_conninfo  # noqa: E402

KINDS = ("owner", "executor", "issuer", "legacy")
SESSION_OPTIONS = "-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=8000"
FLAGS = "NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS"
# Role login plans. PASSWORD: LOGIN with a random password; NOPASSWORD: LOGIN without a password (the cluster must trust the
# role over the private Unix socket, like the existing CP7 application role); NOLOGIN.
RUNNER_PLAN = dict(owner="NOLOGIN", executor="PASSWORD", issuer="PASSWORD", legacy="PASSWORD")


class Provisioner:
    def __init__(self, socket, database, admin_user, own):
        self.socket, self.database, self.admin_user, self.own = socket, database, admin_user, own
        self.db = own
        self.password = os.environ.get("FINWEB_IT_ADMIN_PASSWORD")
        self.created_roles, self.db_created = [], False
        self.connections, self.errors = [], []
        self.on_created = lambda kind, name: None   # hook: called after each successful CREATE (kind: "database"|"role"|"schema")

    # ---- naming / safety -------------------------------------------------
    def owned_name(self, name):
        if not re.fullmatch(re.escape(self.own) + r"(_[a-z0-9_]+)?", name):
            raise RuntimeError("REFUSED: not an object created by this run: " + name)
        return name

    # ---- connections -----------------------------------------------------
    def dsn(self, dbname, user, password=None, options=SESSION_OPTIONS):
        base = build_conninfo(socket=self.socket, dbname=dbname, user=user)
        extra = " passfile=/dev/null sslmode=disable gssencmode=disable connect_timeout=5 application_name=finweb_it_guarded"
        if password:
            extra += " password='" + password.replace("\\", "\\\\").replace("'", "\\'") + "'"
        if options:
            extra += " options='" + options + "'"
        return base + extra

    def admin(self, dbname):
        conn = psycopg.connect(self.dsn(dbname, self.admin_user, self.password, options="-c timezone=UTC"), autocommit=True)
        self.connections.append(conn)
        return conn

    # ---- provisioning ----------------------------------------------------
    def preflight(self):
        with self.admin(self.database) as conn:
            row = conn.execute("SELECT current_database(), current_user, r.rolsuper, r.rolcreaterole, r.rolcreatedb "
                               "FROM pg_roles r WHERE r.rolname=current_user").fetchone()
        if row[0] != self.database or row[1] != self.admin_user:
            raise RuntimeError("REFUSED: connected to %r as %r, expected %r as %r" % (row[0], row[1], self.database, self.admin_user))
        if not (row[2] and row[3] and row[4]):
            raise RuntimeError("REFUSED: admin role must be a superuser that can CREATE ROLE and CREATE DATABASE")
        # F1 R6 (design 1.2 rule 6): a cluster that holds a database in the reserved real-install namespace is the real cluster, and this
        # tool (socket-trusted superuser, password-less roles) is never pointed at it. A tripwire by name, not a fence.
        with self.admin(self.database) as conn:
            self.refuse_real_cluster([r[0] for r in conn.execute("SELECT datname FROM pg_database").fetchall()])

    @staticmethod
    def refuse_real_cluster(database_names):
        """Raise if any database name of the cluster is in the reserved real-install namespace (pure; the names are read by the caller)."""
        from persistence.connection import RESERVED_REAL_PREFIX, is_reserved_real_name
        found = sorted(n for n in database_names if is_reserved_real_name(n))
        if found:
            raise RuntimeError("REFUSED: the cluster holds a database in the reserved real-install namespace %r (%s); the test provisioner "
                               "never runs on the real cluster" % (RESERVED_REAL_PREFIX, ", ".join(found)))

    def refuse_if_prefix_exists(self):
        """A pre-existing object with this run's prefix means the random prefix collided: stop before creating anything."""
        with self.admin(self.database) as conn:
            found = conn.execute("SELECT (SELECT count(*) FROM pg_database WHERE datname LIKE %s),"
                                 "(SELECT count(*) FROM pg_roles WHERE rolname LIKE %s)", (self.own + "%", self.own + "%")).fetchone()
        if found != (0, 0):
            raise RuntimeError("REFUSED: objects with prefix %s already exist" % self.own)

    def create_database(self):
        self.owned_name(self.db)
        with self.admin(self.database) as conn:
            conn.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0 ENCODING 'UTF8' LOCALE_PROVIDER libc "
                                 "LC_COLLATE 'C' LC_CTYPE 'C'").format(sql.Identifier(self.db)))
            self.db_created = True
            self.on_created("database", self.db)
            conn.execute(sql.SQL("REVOKE CREATE, TEMPORARY ON DATABASE {} FROM PUBLIC").format(sql.Identifier(self.db)))
        with self.admin(self.db) as conn:
            conn.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")

    def create_role(self, conn, name, mode):
        """CREATE ROLE, then (and only then) record it. Returns the password or None."""
        self.owned_name(name)
        password = None
        if mode == "NOLOGIN":
            statement = sql.SQL("CREATE ROLE {} NOLOGIN " + FLAGS).format(sql.Identifier(name))
        elif mode == "NOPASSWORD":
            statement = sql.SQL("CREATE ROLE {} LOGIN " + FLAGS).format(sql.Identifier(name))
        elif mode == "PASSWORD":
            password = secrets.token_hex(16)
            statement = sql.SQL("CREATE ROLE {} LOGIN " + FLAGS + " PASSWORD {}").format(sql.Identifier(name), sql.Literal(password))
        else:
            raise ValueError(mode)
        conn.execute(statement)
        self.created_roles.append(name)     # L-1: only after CREATE ROLE succeeded
        self.on_created("role", name)
        return password

    def create_roles(self, tag, plan=RUNNER_PLAN):
        roles, passwords = {}, {}
        with self.admin(self.database) as conn:
            for kind in KINDS:
                name = self.owned_name("%s_%s_%s" % (self.own, tag, kind))
                password = self.create_role(conn, name, plan[kind])
                if password is not None:
                    passwords[kind] = password
                roles[kind] = name
        return roles, passwords

    def create_schema(self, schema, owner):
        with self.admin(self.db) as conn:
            conn.execute(sql.SQL("CREATE SCHEMA {} AUTHORIZATION {}").format(sql.Identifier(schema), sql.Identifier(owner)))
        self.on_created("schema", schema)

    def apply_migrations_as_owner(self, conn, schema, owner):
        from persistence.migrator import apply_migrations, load_migrations
        conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(owner)))
        conn.execute(sql.SQL("SET search_path TO {}, pg_temp").format(sql.Identifier(schema)))
        migrations = load_migrations()
        applied = apply_migrations(conn, migrations)
        history = conn.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall()
        if applied != [m.filename for m in migrations] or history != [(m.version, m.name, m.checksum) for m in migrations]:
            raise RuntimeError("migration history differs from the product migrations")

    def provision_f3(self, tag, *, http, r1=True, plan=RUNNER_PLAN):
        """F2 -> [HTTP add-on -> R1] in one new schema with four new roles; returns (schema, roles, passwords).

        `r1=False` exists only for the startup-refusal test; every schema meant to be served must keep the default."""
        from persistence.guarded_csv_report_store import install_guarded_csv_report
        from persistence.guarded_http_store import install_guarded_http
        from persistence.guarded_workspace_store import install_guarded_workspace
        from persistence.web_account_store import APP_GRANTS
        roles, passwords = self.create_roles(tag, plan)
        schema = self.owned_name("%s_%s" % (self.own, tag))
        self.create_schema(schema, roles["owner"])
        with self.admin(self.db) as conn:
            self.apply_migrations_as_owner(conn, schema, roles["owner"])
            install_guarded_workspace(conn, schema=schema, owner_role=roles["owner"], executor_role=roles["executor"],
                issuer_role=roles["issuer"], legacy_role=roles["legacy"])
            if http:
                install_guarded_http(conn, schema=schema, executor_role=roles["executor"])
                # Mandatory for every F3 schema: ReportAwareWorkspaceStore calls gh_csv_report_precheck on each guarded write.
                if r1:
                    install_guarded_csv_report(conn, schema=schema, executor_role=roles["executor"])
            quoted = '"' + schema + '"'
            conn.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(sql.Identifier(schema), sql.Identifier(roles["issuer"])))
            for kind in ("executor", "legacy"):
                for grant in APP_GRANTS:
                    conn.execute(grant.format(schema=quoted, role='"' + roles[kind] + '"'))
        return schema, roles, passwords

    def provision_account(self, tag):
        """Account schema for `web_api.account_dev`: the real migrations plus exactly APP_GRANTS for a NEW non-owner role."""
        from persistence.web_account_store import APP_GRANTS
        schema = self.owned_name("%s_%s" % (self.own, tag))
        owner = self.owned_name("%s_%s_owner" % (self.own, tag))
        app = self.owned_name("%s_%s_app" % (self.own, tag))
        with self.admin(self.database) as conn:
            self.create_role(conn, owner, "NOLOGIN")
            self.create_role(conn, app, "NOPASSWORD")
        self.create_schema(schema, owner)
        with self.admin(self.db) as conn:
            self.apply_migrations_as_owner(conn, schema, owner)
            quoted = '"' + schema + '"'
            for grant in APP_GRANTS:
                conn.execute(grant.format(schema=quoted, role='"' + app + '"'))
        return schema, owner, app

    def publish(self, conn, schema, profile):
        """Issuer session: publish the profile context and set generation-1 RIGHTS (what the guarded app needs)."""
        from persistence.guarded_http_store import RIGHTS
        published = conn.execute(sql.SQL("SELECT {}.gw_publish(%s)").format(sql.Identifier(schema)), (profile.snapshot_bytes,)).fetchone()[0]
        if published != profile.context_id:
            raise RuntimeError("published context differs from the profile context")
        conn.execute(sql.SQL("SELECT {}.gw_set_rights(%s,1,%s::jsonb,'NONE')").format(sql.Identifier(schema)),
            (profile.context_id, json.dumps(RIGHTS)))

    # ---- cleanup ---------------------------------------------------------
    def close_connections(self):
        for conn in self.connections:
            try:
                conn.close()
            except BaseException as exc:  # noqa: BLE001
                self.errors.append("close: " + repr(exc))
        self.connections.clear()

    def drop_objects(self, *, db_created, roles):
        """Drop the database (WITH FORCE) then the roles, newest first; every name must carry the run prefix; verify nothing is left."""
        try:
            with psycopg.connect(self.dsn(self.database, self.admin_user, self.password, options="-c timezone=UTC"), autocommit=True) as conn:
                if conn.execute("SELECT current_database()").fetchone()[0] != self.database:
                    raise RuntimeError("cleanup connected to the wrong database")
                if db_created:
                    self.owned_name(self.db)
                    conn.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=%s AND pid<>pg_backend_pid()", (self.db,))
                    conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(self.db)))
                for role in reversed(list(roles)):
                    conn.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(self.owned_name(role))))
                left_db = conn.execute("SELECT count(*) FROM pg_database WHERE datname LIKE %s", (self.own + "%",)).fetchone()[0]
                left_roles = conn.execute("SELECT count(*) FROM pg_roles WHERE rolname LIKE %s", (self.own + "%",)).fetchone()[0]
                if left_db or left_roles:
                    self.errors.append("cleanup left %d database(s) and %d role(s) with prefix %s" % (left_db, left_roles, self.own))
        except BaseException as exc:  # noqa: BLE001
            self.errors.append("cleanup: " + repr(exc))
            import traceback
            traceback.print_exc()
