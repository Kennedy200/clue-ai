"""Local-disk storage with signed, expiring download tokens. S3 is an optional plugin later."""
from __future__ import annotations

import hashlib
import hmac
import time
from pathlib import Path

from .config import get_settings
from .security import _fernet  # reuse the local secret to derive the signing key


def root() -> Path:
    p = get_settings().storage_dir / "files"
    p.mkdir(parents=True, exist_ok=True)
    return p


def user_dir(user_id: str, sub: str = "") -> Path:
    p = root() / user_id / sub
    p.mkdir(parents=True, exist_ok=True)
    return p


def _key() -> bytes:
    _fernet()  # makes sure the local secret file exists
    return hashlib.sha256(b"clue-sign|" + (get_settings().storage_dir / ".secret").read_bytes()).digest()


def sign(rel_path: str, ttl: int = 3600) -> str:
    """Return 'exp.sig' token for a path relative to the storage root."""
    exp = int(time.time()) + ttl
    sig = hmac.new(_key(), f"{rel_path}|{exp}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{exp}.{sig}"


def verify(rel_path: str, token: str) -> bool:
    try:
        exp_s, sig = token.split(".", 1)
        if int(exp_s) < time.time():
            return False
    except ValueError:
        return False
    good = hmac.new(_key(), f"{rel_path}|{exp_s}".encode(), hashlib.sha256).hexdigest()[:32]
    return hmac.compare_digest(good, sig)


def safe_path(rel_path: str) -> Path:
    """Resolve a relative path inside the storage root; reject traversal."""
    base = root().resolve()
    p = (base / rel_path).resolve()
    if base != p and base not in p.parents:
        raise ValueError("path escapes storage")
    return p
