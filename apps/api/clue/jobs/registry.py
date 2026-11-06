"""Job handler registry. Kept in its own module so it is a single instance even when the worker runs as __main__."""
from collections.abc import Callable

HANDLERS: dict[str, Callable] = {}


def handler(job_type: str):
    """Register a job handler: fn(db, job) -> result dict."""
    def deco(fn):
        HANDLERS[job_type] = fn
        return fn
    return deco
