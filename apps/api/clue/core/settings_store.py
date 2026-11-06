"""Key/value settings in the DB; secrets are encrypted with the local secret file.

Lookup order: DB value, then environment/.env, then default.
"""
from sqlalchemy.orm import Session

from clue.models import Setting

from .config import get_settings
from .security import decrypt, encrypt

SECRET_KEYS = {"openrouter_api_key"}


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    if row is not None and row.value:
        return decrypt(row.value) if row.encrypted else row.value
    env = getattr(get_settings(), key, None)
    return str(env) if env else default


def set_setting(db: Session, key: str, value: str) -> None:
    enc = key in SECRET_KEYS
    row = db.get(Setting, key) or Setting(key=key)
    row.value = encrypt(value) if (enc and value) else value
    row.encrypted = enc
    db.add(row)
    db.commit()
