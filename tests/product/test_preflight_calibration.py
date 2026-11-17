"""F1 R6: CALIBRATION of the preflight's outcome classifier against a scram-only PostgreSQL server (design 1.2 rule 7; technical TR3-L2, TR6R).

OPT-IN, SKIPPED BY DEFAULT. This test is not run by the default suite, by the PostgreSQL integration run, or on the development machine. It runs in the
owner's Fin-Web cloud environment (PostgreSQL 17.11, running as root), after the R6 code is committed and pushed there (PD-0075 item 2). It
CALIBRATES ONLY: it starts its OWN throwaway cluster in a temporary directory with INVENTED roles and passwords, listens on a Unix socket in that
directory only (`listen_addresses` empty), writes its own `pg_hba.conf` with scram-sha-256 rows, reads what libpq and the server say for each kind of
refusal, and removes the cluster. It touches no existing cluster and needs no real credential and nothing from the development machine.

HOW TO RUN (in the cloud environment, repository checked out, `uv` available, PostgreSQL 17 server binaries installed):

    FINWEB_PREFLIGHT_CALIBRATION=1 \\
    [FINWEB_CAL_PG_BIN=/usr/lib/postgresql/17/bin] \\
    [FINWEB_CAL_OS_USER=postgres] \\
    uv run --no-cache --no-sync --frozen --offline python -m unittest tests.product.test_preflight_calibration -v

`FINWEB_CAL_PG_BIN` names the directory holding `initdb` and `pg_ctl` (default: the output of `pg_config --bindir`, else the PATH). PostgreSQL
refuses to run as root, so when this test runs as root it runs the server's own programs (`initdb`, `pg_ctl`) as the OS user `FINWEB_CAL_OS_USER`
(default `postgres`) through `runuser`, and hands the temporary directory to that user. The probe and the test's own connections run as the caller.
The test prints each message it observed (to standard error) so that the owner can read exactly what the classifier was calibrated against.

WHAT IT SHOWS. (1) With no password supplied, a scram-only server's refusal is classified CHALLENGED (Pass A and Pass B) for a role with a password, a
role with none, and a role that was never created (the server does not reveal which). (2) A `reject` row and a missing `replication` row classify
REJECTED. (3) A wrong password classifies CHALLENGED. (4) A missing socket is OTHER. (5) Every required attempt of 5.3 (d) against this cluster is
CHALLENGED or REJECTED, so the accepting side of the probe passes. (6) Pass B sees a credential the caller's environment holds (PGPASSWORD): CONNECTED.
(7) A server that does not use scram makes the tool's own `require_auth` connection fail with the code PF_REQUIRE_AUTH. (8) PD-0076 choice E, the last
five tests of the module, same variable and cluster: the `withdraw` connection's `require_auth=!password` refuses a server whose `pg_hba.conf` uses
`password` (cleartext) and sends no PasswordMessage (shown on the wire by a stand-in server; the control with no demand does send it); connects to a
scram server with the right invented password; and, as recorded contrast, ALLOWS an md5 server and a trust server, which `scram-sha-256` would stop.
If any message differs from the
classifier's patterns the corresponding test FAILS: the patterns are then corrected by a reviewed change, never by loosening this test.
"""
from __future__ import annotations

import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = Path(__file__).resolve().parent
for entry in (str(HERE.parents[1] / "src"), str(HERE)):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from persistence import real_preflight as pf  # noqa: E402

OPT_IN = os.environ.get("FINWEB_PREFLIGHT_CALIBRATION") == "1"
SUPER, LOGIN, NOPW, REJECTED, NEVER = "cal_super", "cal_login", "cal_nopw", "cal_rejected", "cal_never_created"


def note(text):
    sys.stderr.write("calibration: %s\n" % text)


def pg_bin():
    explicit = os.environ.get("FINWEB_CAL_PG_BIN")
    if explicit:
        return explicit
    try:
        done = subprocess.run(["pg_config", "--bindir"], capture_output=True, text=True, timeout=10, check=False)
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return None


@unittest.skipUnless(OPT_IN, "opt-in calibration: set FINWEB_PREFLIGHT_CALIBRATION=1 (runs in the owner's cloud environment, starts its own throwaway cluster)")
class ScramOnlyCalibration(unittest.TestCase):
    cluster_dir = None
    started = False

    # ---- the throwaway cluster ----------------------------------------------------------------------------------------
    @classmethod
    def server_program(cls, name, *args):
        binary = pg_bin()
        program = os.path.join(binary, name) if binary else name
        command = [program, *args]
        if os.geteuid() == 0:
            command = ["runuser", "-u", os.environ.get("FINWEB_CAL_OS_USER", "postgres"), "--", *command]
        done = subprocess.run(command, capture_output=True, text=True, timeout=120, check=False)
        if done.returncode != 0:
            raise RuntimeError("%s failed (%d): %s" % (name, done.returncode, (done.stderr or done.stdout).strip()[:400]))
        return done.stdout

    @classmethod
    def give_to_server_user(cls, path):
        if os.geteuid() == 0:
            import pwd
            entry = pwd.getpwnam(os.environ.get("FINWEB_CAL_OS_USER", "postgres"))
            os.chown(path, entry.pw_uid, entry.pw_gid)

    @classmethod
    def write_hba(cls, rows):
        path = os.path.join(cls.data, "pg_hba.conf")
        with open(path, "w", encoding="utf8") as handle:
            handle.write("\n".join(rows) + "\n")
        cls.give_to_server_user(path)
        cls.server_program("pg_ctl", "-D", cls.data, "reload")
        import time
        time.sleep(1.0)             # the reload is a signal; give the postmaster a moment

    @classmethod
    def setUpClass(cls):
        cls.cluster_dir = tempfile.mkdtemp(prefix="finweb-cal-", dir="/tmp")
        os.chmod(cls.cluster_dir, 0o700)
        cls.give_to_server_user(cls.cluster_dir)
        cls.data = os.path.join(cls.cluster_dir, "data")
        cls.port = str(20000 + secrets.randbelow(30000))
        cls.super_password = secrets.token_hex(12)
        pwfile = os.path.join(cls.cluster_dir, "pw")
        with open(pwfile, "w", encoding="utf8") as handle:
            handle.write(cls.super_password + "\n")
        os.chmod(pwfile, 0o600)
        cls.give_to_server_user(pwfile)
        try:
            cls.server_program("initdb", "-D", cls.data, "-U", SUPER, "--auth=scram-sha-256", "--pwfile=" + pwfile, "-E", "UTF8", "--locale=C")
            options = "-c listen_addresses='' -c unix_socket_directories='%s' -c port=%s -c max_prepared_transactions=0" % (cls.cluster_dir, cls.port)
            cls.server_program("pg_ctl", "-D", cls.data, "-o", options, "-w", "-l", os.path.join(cls.cluster_dir, "log"), "start")
            cls.started = True
            cls.write_hba(["local all all scram-sha-256"])
            cls.passwords = {LOGIN: secrets.token_hex(12), REJECTED: secrets.token_hex(12)}
            with cls.connect(SUPER, cls.super_password) as conn:
                conn.execute("SET password_encryption = 'scram-sha-256'")
                for role in (LOGIN, REJECTED):
                    conn.execute("CREATE ROLE %s LOGIN PASSWORD '%s'" % (role, cls.passwords[role]))
                conn.execute("CREATE ROLE %s LOGIN" % NOPW)
        except BaseException:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.started:
            try:
                cls.server_program("pg_ctl", "-D", cls.data, "-m", "immediate", "-w", "stop")
            except RuntimeError as error:
                note("could not stop the throwaway cluster: %s" % error)
            cls.started = False
        if cls.cluster_dir:
            shutil.rmtree(cls.cluster_dir, ignore_errors=True)
            cls.cluster_dir = None

    @classmethod
    def connect(cls, user, password, database="postgres"):
        import psycopg
        return psycopg.connect(host=cls.cluster_dir, port=cls.port, user=user, password=password, dbname=database, passfile="/dev/null",
                               sslmode="disable", gssencmode="disable", connect_timeout=5, autocommit=True)

    def prober(self, **environ):
        prober = pf.Prober(self.cluster_dir, self.port, environ=environ)
        self.addCleanup(prober.close)
        return prober

    def attempt(self, role, database, probe_pass, replication=False, **environ):
        result = self.prober(**environ).attempt(role, database, probe_pass, replication)
        note("%s -> %s on %s %s%s: %r" % (role, result.outcome, database, "pass " + probe_pass, " replication" if replication else "", result.message))
        return result

    # ---- the calibration -------------------------------------------------------------------------------------------------
    def test_no_password_is_challenged_for_every_kind_of_role_in_both_passes(self):
        self.write_hba(["local all all scram-sha-256"])
        for probe_pass in ("A", "B"):
            for role in (LOGIN, NOPW, NEVER):
                self.assertEqual(self.attempt(role, "postgres", probe_pass).outcome, pf.CHALLENGED, (role, probe_pass))

    def test_a_reject_row_and_a_missing_replication_row_are_rejected(self):
        self.write_hba(["local all %s reject" % REJECTED, "local all all scram-sha-256"])
        self.assertEqual(self.attempt(REJECTED, "postgres", "A").outcome, pf.REJECTED)
        self.assertEqual(self.attempt(SUPER, "replication", "A", True).outcome, pf.REJECTED)     # `all` does not match a replication connection
        self.assertEqual(self.attempt(SUPER, "replication", "B", True).outcome, pf.REJECTED)

    def test_no_row_for_a_database_is_rejected(self):
        self.write_hba(["local postgres all scram-sha-256"])
        self.assertEqual(self.attempt(LOGIN, "template1", "A").outcome, pf.REJECTED)
        self.write_hba(["local all all scram-sha-256"])

    def test_a_wrong_password_is_challenged(self):
        import psycopg
        self.write_hba(["local all all scram-sha-256"])
        with self.assertRaises(psycopg.OperationalError) as context:
            self.connect(LOGIN, "not-the-password").close()
        note("wrong password -> %r" % str(context.exception).strip().splitlines()[-1])
        self.assertEqual(pf.classify_attempt(False, str(context.exception)), pf.CHALLENGED)

    def test_a_missing_socket_is_other(self):
        prober = pf.Prober(os.path.join(self.cluster_dir, "absent"), self.port, environ={})
        self.addCleanup(prober.close)
        result = prober.attempt(LOGIN, "postgres", "A", False)
        note("missing socket -> %s %r" % (result.outcome, result.message))
        self.assertEqual(result.outcome, pf.OTHER)

    def test_every_required_attempt_against_this_cluster_is_challenged_or_rejected(self):
        self.write_hba(["local all all scram-sha-256"])
        roles = tuple(pf.RoleFact(name, login=True, superuser=(name == SUPER), replication=(name == SUPER)) for name in (SUPER, LOGIN, NOPW, REJECTED))
        databases = (("postgres", True), ("template1", True))
        required = pf.required_attempts(roles, databases, NEVER)
        self.assertGreater(len(required), 16)
        for result in self.prober().run(required):
            note("%s" % (result,))
            self.assertIn(result.outcome, (pf.CHALLENGED, pf.REJECTED), result)

    def test_pass_b_sees_a_credential_the_callers_environment_holds(self):
        self.write_hba(["local all all scram-sha-256"])
        result = self.attempt(LOGIN, "postgres", "B", PGPASSWORD=self.passwords[LOGIN])
        self.assertEqual(result.outcome, pf.CONNECTED)
        self.assertEqual(self.attempt(LOGIN, "postgres", "A", PGPASSWORD=self.passwords[LOGIN]).outcome, pf.CHALLENGED)     # Pass A scrubs it

    def test_a_server_that_does_not_use_scram_fails_the_tools_own_require_auth_connection(self):
        import psycopg
        self.write_hba(["local all all trust"])
        socket = os.path.join(self.cluster_dir, ".s.PGSQL." + self.port)
        try:
            with self.assertRaises(psycopg.Error) as context:
                pf.connect_with_prompt(socket, "postgres", LOGIN, require_auth=pf.GATED_REQUIRE_AUTH, prompt=lambda role: self.passwords[LOGIN]).close()
            note("trust server with require_auth -> %r" % str(context.exception).strip().splitlines()[-1])
            self.assertEqual(pf.classify_own_connection_error(str(context.exception)), pf.PF_REQUIRE_AUTH)
        finally:
            self.write_hba(["local all all scram-sha-256"])
        with pf.connect_with_prompt(socket, "postgres", LOGIN, require_auth=pf.GATED_REQUIRE_AUTH, prompt=lambda role: self.passwords[LOGIN]) as conn:
            self.assertEqual(conn.execute("SELECT 1").fetchone(), (1,))

    # ---- PD-0076 choice E: the `withdraw` connection's `require_auth=!password` against a server ------------------------------
    # Same opt-in variable, same throwaway cluster, invented roles and passwords only. They show what libpq's negated demand does with each kind of
    # server; nothing here is a real credential or a real tool. Run in the cloud with the rest of this module (see the header).
    def withdraw_connect(self, user, password, database="postgres", **override):
        require = override.get("require_auth", pf.WITHDRAW_REQUIRE_AUTH)
        socket = os.path.join(self.cluster_dir, ".s.PGSQL." + self.port)
        return pf.connect_with_prompt(socket, database, user, require_auth=require, prompt=lambda role: password)

    def md5_role(self):
        """A role whose stored verifier is MD5 (a deprecated form PostgreSQL 17 still accepts), invented, dropped afterwards."""
        name, password = "cal_md5", secrets.token_hex(12)
        with self.connect(SUPER, self.super_password) as conn:
            conn.execute("DROP ROLE IF EXISTS %s" % name)
            conn.execute("SET password_encryption = 'md5'")
            conn.execute("CREATE ROLE %s LOGIN PASSWORD '%s'" % (name, password))

        def drop():
            with self.connect(SUPER, self.super_password) as conn:
                conn.execute("DROP ROLE IF EXISTS %s" % name)
        self.addCleanup(drop)
        return name, password

    def test_withdraw_demand_is_the_negated_cleartext_password_method(self):
        self.assertEqual(pf.WITHDRAW_REQUIRE_AUTH, "!password")

    def test_withdraw_refuses_a_cleartext_password_server_and_the_password_is_not_sent(self):
        """(1) A cluster whose hba uses `password` asks for the password in clear. libpq's `require_auth=!password` refuses the request. The control,
        the same server and role with no demand, connects: so the server really did ask, and the refusal is the demand's."""
        import psycopg
        self.write_hba(["local all all password"])
        try:
            with self.assertRaises(psycopg.OperationalError) as context:
                self.withdraw_connect(LOGIN, self.passwords[LOGIN]).close()
            message = str(context.exception).strip().splitlines()[-1]
            note("cleartext-password server with require_auth=!password -> %r" % message)
            self.assertEqual(pf.classify_own_connection_error(str(context.exception)), pf.PF_REQUIRE_AUTH)
            self.assertNotIn(self.passwords[LOGIN], str(context.exception))
            with self.withdraw_connect(LOGIN, self.passwords[LOGIN], require_auth=None) as conn:          # CONTROL: no demand, the server is answered
                self.assertEqual(conn.execute("SELECT 1").fetchone(), (1,))
        finally:
            self.write_hba(["local all all scram-sha-256"])

    def test_the_withdraw_connection_sends_no_password_message_to_a_server_that_asks_for_cleartext(self):
        """(1, continued) On the wire. A stand-in server on a Unix socket in the temporary directory answers the startup packet with
        AuthenticationCleartextPassword and records every byte that follows. With `!password` libpq closes without a PasswordMessage ('p'): the
        recorded bytes are empty, so the invented password never left the client. The control (no demand) does send one."""
        import socket as socket_module
        import threading
        import psycopg
        invented = "invented-" + secrets.token_hex(6)

        def serve(demand):
            path = os.path.join(self.cluster_dir, ".s.PGSQL.%d" % (int(self.port) + 1))
            if os.path.exists(path):
                os.unlink(path)
            listener = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_STREAM)
            listener.bind(path)
            listener.listen(1)
            listener.settimeout(20)
            seen = {"startup": b"", "after": b""}

            def run():
                try:
                    connection, _ = listener.accept()
                except OSError:
                    return
                with connection:
                    connection.settimeout(5)
                    seen["startup"] = connection.recv(4096)
                    connection.sendall(b"R" + (8).to_bytes(4, "big") + (3).to_bytes(4, "big"))          # AuthenticationCleartextPassword
                    try:
                        while True:
                            chunk = connection.recv(4096)
                            if not chunk:
                                break
                            seen["after"] += chunk
                            if chunk[:1] == b"p":
                                connection.sendall(b"E" + (4 + len(b"SFATAL\0C28P01\0Mstand-in\0\0")).to_bytes(4, "big") + b"SFATAL\0C28P01\0Mstand-in\0\0")
                                break
                    except (socket_module.timeout, OSError):
                        pass
            thread = threading.Thread(target=run, daemon=True)
            thread.start()
            try:
                with self.assertRaises(psycopg.OperationalError) as context:
                    pf.connect_with_prompt(path, "postgres", LOGIN, require_auth=demand, prompt=lambda role: invented).close()
            finally:
                thread.join(10)
                listener.close()
                if os.path.exists(path):
                    os.unlink(path)
            return seen, str(context.exception)

        seen, message = serve(pf.WITHDRAW_REQUIRE_AUTH)
        note("stand-in cleartext server, require_auth=!password -> startup %d bytes, after %r, %r" % (len(seen["startup"]), seen["after"], message.strip()[-120:]))
        self.assertIn(b"user", seen["startup"])                      # the startup packet arrived: the server did ask
        self.assertIn(seen["after"], (b"", b"X\x00\x00\x00\x04"))    # nothing followed it but, at most, a Terminate: no PasswordMessage ('p')
        self.assertNotIn(invented.encode(), seen["after"])
        self.assertEqual(pf.classify_own_connection_error(message), pf.PF_REQUIRE_AUTH)
        seen, _message = serve(None)
        self.assertTrue(seen["after"].startswith(b"p"), seen["after"])          # CONTROL: with no demand the same client DOES answer in clear
        self.assertIn(invented.encode(), seen["after"])

    def test_withdraw_connects_to_a_scram_server_with_the_right_password(self):
        """(2) A scram cluster: a withdrawal is not stopped. A wrong password is still refused, by the server and not by the demand."""
        import psycopg
        self.write_hba(["local all all scram-sha-256"])
        with self.withdraw_connect(LOGIN, self.passwords[LOGIN]) as conn:
            self.assertEqual(conn.execute("SELECT current_user").fetchone(), (LOGIN,))
        with self.assertRaises(psycopg.OperationalError) as context:
            self.withdraw_connect(LOGIN, "not-the-password").close()
        note("scram server, wrong password -> %r" % str(context.exception).strip().splitlines()[-1])
        self.assertEqual(pf.classify_attempt(False, str(context.exception)), pf.CHALLENGED)
        self.assertEqual(pf.classify_own_connection_error(str(context.exception)), pf.PF_CONNECT_FAILED)

    def test_contrast_md5_and_trust_what_the_negated_demand_allows_and_what_the_scram_demand_would_stop(self):
        """(3) RECORDED AND ASSERTED. `!password` refuses ONLY a request for a cleartext password. It therefore ALLOWS an md5 server (the client answers
        with an MD5 digest, not the password) and a trust server (nothing is asked). `require_auth=scram-sha-256`, the gated commands' demand, would
        stop both: that is choice E's trade, one more thing that could stop a withdrawal versus a weaker guarantee."""
        import psycopg
        name, password = self.md5_role()
        try:
            self.write_hba(["local all all md5"])
            with self.withdraw_connect(name, password) as conn:                    # md5 hba, md5 verifier: an MD5 exchange
                self.assertEqual(conn.execute("SELECT current_user").fetchone(), (name,))
            note("md5 server, md5 verifier, require_auth=!password -> connected (the demand does not refuse an MD5 exchange)")
            with self.assertRaises(psycopg.OperationalError) as context:
                self.withdraw_connect(name, password, require_auth=pf.GATED_REQUIRE_AUTH).close()
            note("md5 server with require_auth=scram-sha-256 -> %r" % str(context.exception).strip().splitlines()[-1])
            self.assertEqual(pf.classify_own_connection_error(str(context.exception)), pf.PF_REQUIRE_AUTH)
            self.write_hba(["local all all trust"])
            with self.withdraw_connect(LOGIN, "any-invented-text") as conn:        # trust: no request at all; the password is not sent
                self.assertEqual(conn.execute("SELECT current_user").fetchone(), (LOGIN,))
            note("trust server, require_auth=!password -> connected (nothing is asked, so nothing is refused)")
            with self.assertRaises(psycopg.OperationalError):
                self.withdraw_connect(LOGIN, "any-invented-text", require_auth=pf.GATED_REQUIRE_AUTH).close()
        finally:
            self.write_hba(["local all all scram-sha-256"])


if __name__ == "__main__":
    unittest.main()
