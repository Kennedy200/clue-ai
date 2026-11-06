"""Password hashing, tokens, secret-at-rest encryption."""
import base64
import hashlib
import secrets

from argon2 import PasswordHasher
from cryptography.fernet import Fernet

from .config import get_settings

_ph = PasswordHasher()


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(h: str, pw: str) -> bool:
    try:
        return _ph.verify(h, pw)
    except Exception:
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def sha256(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def _fernet() -> Fernet:
    f = get_settings().storage_dir / ".secret"
    if not f.exists():
        f.write_bytes(base64.urlsafe_b64encode(secrets.token_bytes(32)))
    return Fernet(f.read_bytes())


def encrypt(s: str) -> str:
    return _fernet().encrypt(s.encode()).decode()


def decrypt(s: str) -> str:
    return _fernet().decrypt(s.encode()).decode()
