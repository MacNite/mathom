"""Password storage service using Argon2id with a portable scrypt fallback.

argon2-cffi is the production dependency. The fallback keeps source-tree and
minimal installs usable while preserving a modern, memory-hard password hash.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from importlib import import_module
from typing import Any

try:
    _hasher: Any = import_module("argon2").PasswordHasher()
except ImportError:  # pragma: no cover - production installs include argon2-cffi
    _hasher = None


MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256


def validate_password(password: str) -> None:
    """Reject passwords outside the bounded local-password policy."""
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")


def hash_password(password: str) -> str:
    """Return an Argon2id password hash, or scrypt when Argon2 is unavailable."""
    validate_password(password)
    if _hasher is not None:
        return _hasher.hash(password)
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt + digest).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    """Verify the password using the algorithm recorded in the stored hash."""
    if not password_hash:
        return False
    if _hasher is not None and not password_hash.startswith("scrypt$"):
        try:
            return bool(_hasher.verify(password_hash, password))
        except Exception:
            return False
    try:
        raw = base64.b64decode(password_hash.removeprefix("scrypt$"))
        salt, expected = raw[:16], raw[16:]
        actual = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
