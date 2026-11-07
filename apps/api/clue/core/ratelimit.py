"""Tiny in-memory sliding-window limiter (single-process). Swap for Redis if you scale out."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)


def client_ip(request: Request) -> str:
    """Behind Caddy/Next every connection comes from the proxy, so use the forwarded client address.
    The API must only be reachable through the proxy (it binds to 127.0.0.1 in the Docker files)."""
    from clue.core.config import get_settings

    fwd = request.headers.get("x-forwarded-for", "")
    if get_settings().trust_proxy and fwd:
        return fwd.split(",")[0].strip()[:45]
    return request.client.host if request.client else "x"


def limit(bucket: str, max_calls: int, per_seconds: int):
    def dep(request: Request):
        key = f"{bucket}:{client_ip(request)}"
        now = time.time()
        q = _hits[key]
        while q and now - q[0] > per_seconds:
            q.popleft()
        if len(q) >= max_calls:
            raise HTTPException(429, "Too many attempts. Please wait a minute and try again.")
        q.append(now)
    return dep


def reset() -> None:
    _hits.clear()
