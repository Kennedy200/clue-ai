"""ULID-style sortable ids (26 chars, Crockford base32) and UTC helpers."""
import os
import time
from datetime import datetime, timezone

_A = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def new_id() -> str:
    n = (int(time.time() * 1000) << 80) | int.from_bytes(os.urandom(10), "big")
    return "".join(_A[(n >> (5 * i)) & 31] for i in range(25, -1, -1))


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
