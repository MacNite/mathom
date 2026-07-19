"""Password storage service. Uses Argon2id when available, scrypt fallback for minimal installs."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os

try:
    from argon2 import PasswordHasher
except ImportError:  # package is declared dependency; keep source-tree tests runnable
    PasswordHasher = None

MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256
_hasher = PasswordHasher() if PasswordHasher else None


def validate_password(password: str) -> None:
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be {MIN_PASSWORD_LENGTH}-{MAX_PASSWORD_LENGTH} characters")


def hash_password(password: str) -> str:
    validate_password(password)
    if _hasher:
        return _hasher.hash(password)
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1)
    return "scrypt$" + base64.b64encode(salt + digest).decode()


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        return False
    if _hasher and not password_hash.startswith("scrypt$"):
        try:
            return _hasher.verify(password_hash, password)
        except Exception:
            return False
    try:
        raw = base64.b64decode(password_hash.removeprefix("scrypt$"))
        salt, old = raw[:16], raw[16:]
        return hmac.compare_digest(
            hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1), old
        )
    except (ValueError, TypeError):
        return False
