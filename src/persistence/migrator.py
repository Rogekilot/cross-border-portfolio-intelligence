"""A small migration runner for numbered plain-SQL files.

Rules:

- Files are `NNNN_name.sql` in `persistence/migrations/`, versions contiguous
  from 0001. A gap, a duplicate or a malformed `.sql` name is an error.
- The whole pending batch runs in ONE transaction (PostgreSQL DDL is
  transactional): either every pending file applies, or none does.
- Each applied file is recorded in `schema_migrations(version, name,
  checksum)`; the checksum is SHA-256 of the file's raw bytes. No timestamp
  is stored, so nothing here depends on the wall clock.
- If an already-applied file's checksum (or name) differs from disk, or an
  applied version has no file, or a pending version is older than an applied
  one, the runner raises before executing any migration SQL. Applied files
  are never edited; a change is a new file.
- Idempotent: with nothing pending it changes nothing and returns `[]`.
- A transaction-level advisory lock serializes concurrent runners.

Migration SQL must use unqualified names: objects land in the connection's
first `search_path` schema (the integration tests rely on this to run in a
disposable schema).

The connection is duck-typed (`execute`, `transaction`), i.e. a psycopg 3
connection; this module does not import the driver.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
_ADVISORY_LOCK_PREFIX = "finweb.migrator:"  # + current_schema(); no clock, no shared fixed key

CREATE_SCHEMA_MIGRATIONS_SQL = (
    "CREATE TABLE IF NOT EXISTS schema_migrations ("
    " version integer PRIMARY KEY CHECK (version > 0),"
    " name text NOT NULL,"
    " checksum text NOT NULL CHECK (length(checksum) = 64)"
    ")"
)


class MigrationError(Exception):
    """Base class for runner refusals."""


class MigrationFilesError(MigrationError):
    """The migration directory is malformed (bad name, gap, duplicate)."""


class MigrationChecksumError(MigrationError):
    """An applied migration no longer matches the file on disk."""


class MigrationHistoryError(MigrationError):
    """Applied history and files disagree (missing file, out-of-order)."""


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    filename: str
    sql: str
    checksum: str


def checksum_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_migrations(directory: Optional[Path] = None) -> List[Migration]:
    directory = Path(directory) if directory is not None else MIGRATIONS_DIR
    found: List[Migration] = []  # the manifest check (below) is mandatory for the real dir
    for filename in sorted(os.listdir(str(directory))):
        if not filename.endswith(".sql"):
            continue
        match = _FILENAME.match(filename)
        if match is None:
            raise MigrationFilesError(
                f"{filename!r} does not match NNNN_lowercase_name.sql"
            )
        data = (directory / filename).read_bytes()
        found.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                filename=filename,
                sql=data.decode("utf-8"),
                checksum=checksum_of(data),
            )
        )
    found.sort(key=lambda m: m.version)
    for index, migration in enumerate(found, start=1):
        if migration.version != index:
            raise MigrationFilesError(
                f"migration versions must be contiguous from 0001; expected "
                f"{index:04d}, found {migration.filename!r}"
            )
    if directory == MIGRATIONS_DIR or (directory / MANIFEST_NAME).exists():
        verify_manifest(found, read_manifest(directory))
    return found


class MigrationManifestError(MigrationError):
    """The repository's pinned checksums and the migration files disagree."""


MANIFEST_NAME = "CHECKSUMS"


def read_manifest(directory: Path) -> Dict[str, str]:
    """`CHECKSUMS`: one `<sha256>  <filename>` line per migration (shasum -a 256
    format). It pins every migration file in the repository, so an in-place edit of an
    applied (frozen) migration is caught by the default test suite and by the runner before
    it touches any database, not only by a database that recorded the old checksum.
    Adding a migration means adding a line; an existing line changing is a frozen-file
    violation and shows up in review as a modified line."""
    path = Path(directory) / MANIFEST_NAME
    if not path.exists():
        raise MigrationManifestError(f"{path} is missing")
    entries: Dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) != 2 or len(parts[0]) != 64:
            raise MigrationManifestError(f"{MANIFEST_NAME} line {number} is malformed")
        if parts[1] in entries:
            raise MigrationManifestError(f"{MANIFEST_NAME} lists {parts[1]} twice")
        entries[parts[1]] = parts[0]
    return entries


def verify_manifest(migrations: Sequence[Migration], manifest: Mapping[str, str]) -> None:
    files = {m.filename: m.checksum for m in migrations}
    for filename in sorted(files):
        if filename not in manifest:
            raise MigrationManifestError(
                f"{filename} is not pinned in {MANIFEST_NAME}: add its checksum line"
            )
        if manifest[filename] != files[filename]:
            raise MigrationManifestError(
                f"{filename} no longer matches {MANIFEST_NAME}: applied migrations are "
                "frozen; add a NEW migration instead of editing this one"
            )
    for filename in sorted(manifest):
        if filename not in files:
            raise MigrationManifestError(f"{MANIFEST_NAME} pins missing file {filename}")


def plan_migrations(
    migrations: Sequence[Migration], applied: Mapping[int, Tuple[str, str]]
) -> List[Migration]:
    """Pure planning step: returns the pending migrations in order, or raises.
    `applied` maps version -> (name, checksum)."""
    by_version = {m.version: m for m in migrations}
    for version in sorted(applied):
        name, checksum = applied[version]
        on_disk = by_version.get(version)
        if on_disk is None:
            raise MigrationHistoryError(
                f"migration {version:04d} ({name}) is applied but has no file"
            )
        if on_disk.checksum != checksum or on_disk.name != name:
            raise MigrationChecksumError(
                f"applied migration {version:04d} ({name}) no longer matches "
                f"{on_disk.filename}: applied files must never be edited; add "
                "a new migration instead"
            )
    pending = [m for m in migrations if m.version not in applied]
    if applied and pending and pending[0].version < max(applied):
        raise MigrationHistoryError(
            f"pending migration {pending[0].filename} is older than applied "
            f"version {max(applied):04d}"
        )
    return pending


def apply_migrations(
    conn: Any, migrations: Optional[Sequence[Migration]] = None
) -> List[str]:
    """Apply every pending migration in one transaction. Returns the applied
    filenames (empty when nothing was pending)."""
    if migrations is None:
        migrations = load_migrations()
    with conn.transaction():
        conn.execute(CREATE_SCHEMA_MIGRATIONS_SQL)
        # Schema-scoped key (R3-4): runners for DIFFERENT schemas (concurrent test runs, a
        # multi-schema host) must not serialize or deadlock on one database-wide key.
        conn.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s || current_schema(), 0))",
            (_ADVISORY_LOCK_PREFIX,),
        )
        rows = conn.execute(
            "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
        ).fetchall()
        applied = {row[0]: (row[1], row[2]) for row in rows}
        pending = plan_migrations(migrations, applied)
        for migration in pending:
            conn.execute(migration.sql)
            conn.execute(
                "INSERT INTO schema_migrations (version, name, checksum) "
                "VALUES (%s, %s, %s)",
                (migration.version, migration.name, migration.checksum),
            )
    return [m.filename for m in pending]
