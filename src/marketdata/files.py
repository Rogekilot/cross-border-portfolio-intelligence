"""Reading saved market-data files with hash verification (Tech Plan §15.3).

Layout under the data directory (default `data/marketdata/`, override with the
`FINWEB_MARKETDATA_DIR` environment variable at the call site, never read here):

    SOURCES.json
    files/<source_id>/<data_kind>/<YYYY-MM-DD>/<label>.<ext>
    files/<source_id>/<data_kind>/<YYYY-MM-DD>/<label>.<ext>.manifest.json
    releases/<release_id>.json

The store only READS. It verifies the SHA-256 and size of the exact payload bytes against
the manifest on every read, and refuses a mismatch. It reads no clock and no environment.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List

from marketdata.canonical import sha256_hex
from marketdata.manifest import (
    FileManifest,
    ManifestError,
    MarketDataRelease,
    SourceRegistry,
)

MANIFEST_SUFFIX = ".manifest.json"


class FileHashMismatchError(ValueError):
    """FILE_HASH_MISMATCH: payload bytes differ from the manifest (edited or corrupted)."""


class FileNotInStoreError(LookupError):
    pass


@dataclass(frozen=True)
class VerifiedFile:
    manifest: FileManifest
    payload: bytes
    path: Path


class FileStore:
    def __init__(self, root: Path):
        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def load_registry(self) -> SourceRegistry:
        path = self._root / "SOURCES.json"
        try:
            return SourceRegistry.from_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise ManifestError(f"missing source registry {path}") from None

    def load_release(self, release_id: str) -> MarketDataRelease:
        path = self._root / "releases" / f"{release_id}.json"
        try:
            release = MarketDataRelease.from_json(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise FileNotInStoreError(f"missing release {path}") from None
        if release.release_id != release_id:
            raise ManifestError("release file name does not match its content")
        return release

    def manifest_paths(self) -> List[Path]:
        base = self._root / "files"
        return sorted(base.rglob(f"*{MANIFEST_SUFFIX}")) if base.is_dir() else []

    def index(self) -> Dict[str, Path]:
        """file_sha256 -> manifest path, for every manifest present (sorted scan)."""
        found: Dict[str, Path] = {}
        for path in self.manifest_paths():
            manifest = FileManifest.from_json(path.read_text(encoding="utf-8"))
            if manifest.file_sha256 in found:
                raise ManifestError(f"two manifests claim file {manifest.file_sha256}")
            found[manifest.file_sha256] = path
        return found

    def read_verified(self, manifest_path: Path) -> VerifiedFile:
        manifest_path = Path(manifest_path)
        manifest = FileManifest.from_json(manifest_path.read_text(encoding="utf-8"))
        name = manifest_path.name
        if not name.endswith(MANIFEST_SUFFIX):
            raise ManifestError(f"{name} is not a manifest file name")
        payload_path = manifest_path.with_name(name[: -len(MANIFEST_SUFFIX)])
        if payload_path.name != manifest.payload_filename:
            raise ManifestError("manifest payload_filename does not match its file name")
        try:
            payload = payload_path.read_bytes()
        except FileNotFoundError:
            raise FileNotInStoreError(f"missing payload {payload_path}") from None
        if len(payload) != manifest.size_bytes or sha256_hex(payload) != manifest.file_sha256:
            raise FileHashMismatchError(
                f"FILE_HASH_MISMATCH: {payload_path} does not match its manifest "
                f"(expected {manifest.file_sha256})"
            )
        return VerifiedFile(manifest=manifest, payload=payload, path=payload_path)

    def read_by_hash(self, file_sha256: str) -> VerifiedFile:
        path = self.index().get(file_sha256)
        if path is None:
            raise FileNotInStoreError(f"no manifest for file {file_sha256}")
        verified = self.read_verified(path)
        return verified
