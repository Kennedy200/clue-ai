"""Tiny in-memory sliding-window limiter (single-process). Swap for Redis if you scale out."""
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)


def limit(bucket: str, max_calls: int, per_seconds: int):
    def dep(request: Request):
        key = f"{bucket}:{request.client.host if request.client else 'x'}"
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
