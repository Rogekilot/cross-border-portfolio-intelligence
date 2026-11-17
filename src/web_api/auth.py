"""Bounded stdlib password/session primitives; no credentials enter logs or URLs."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import threading
from dataclasses import dataclass

_TOKEN = re.compile(r"[A-Za-z0-9_-]{43}\Z")
_USERNAME = re.compile(r"[a-z][a-z0-9_.-]{2,31}\Z")
# OWASP's scrypt fallback profile; 128 MiB per operation, at most two concurrent.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 131072, 8, 1
_KDF_SLOTS = threading.BoundedSemaphore(2)


class PasswordCapacityError(RuntimeError):
    pass


def username(value):
    if not isinstance(value, str) or not value.isascii() or not _USERNAME.fullmatch(value.lower()):
        raise ValueError("Username must be 3–32 ASCII letters, digits, dot, underscore or hyphen, starting with a letter")
    return value.lower()


def password(value):
    if not isinstance(value, str) or len(value) < 15 or len(value.encode("utf-8")) > 128:
        raise ValueError("Password must have at least 15 characters and at most 128 UTF-8 bytes")
    return value


def _derive(value, salt):
    if not _KDF_SLOTS.acquire(blocking=False):
        raise PasswordCapacityError("Password hashing capacity reached")
    try:
        return hashlib.scrypt(value.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R,
                              p=SCRYPT_P, dklen=32, maxmem=256 * 1024 * 1024)
    finally:
        _KDF_SLOTS.release()


def password_hash(value):
    password(value)
    salt = secrets.token_bytes(16)
    return "scrypt$131072$8$1$" + salt.hex() + "$" + _derive(value, salt).hex()


def verify_password(value, encoded):
    """Unknown users pay the same bounded KDF cost; malformed storage fails closed."""
    salt = bytes(16)
    expected = bytes(32)
    valid = False
    if isinstance(encoded, str):
        parts = encoded.split("$")
        if len(parts) == 6 and parts[:4] == ["scrypt", "131072", "8", "1"]:
            try:
                salt, expected = bytes.fromhex(parts[4]), bytes.fromhex(parts[5])
                valid = len(salt) == 16 and len(expected) == 32
            except ValueError:
                pass
    if not valid:
        salt, expected = bytes(16), bytes(32)
    actual = _derive(value, salt)
    return hmac.compare_digest(actual, expected) and valid


def new_token():
    return secrets.token_urlsafe(32)


def valid_token(value):
    return isinstance(value, str) and _TOKEN.fullmatch(value) is not None


def digest_token(value):
    return hashlib.sha256(value.encode("ascii")).hexdigest()


def csrf_token(value):
    return hashlib.sha256(("finweb.cp7.csrf/1:" + value).encode("ascii")).hexdigest()


@dataclass(frozen=True)
class AuthSettings:
    """Production defaults require HTTPS; insecure cookies are a named local opt-in."""
    secure_cookie: bool = True
    local_development: bool = False
    session_seconds: int = 28800

    def __post_init__(self):
        if not self.secure_cookie and not self.local_development:
            raise ValueError("Insecure cookies require explicit local development opt-in")
        if not 60 <= self.session_seconds <= 28800:
            raise ValueError("Session lifetime must be between 60 seconds and eight hours")

    @classmethod
    def local(cls):
        return cls(secure_cookie=False, local_development=True)
