"""Worker process: polls the DB queue and runs registered handlers."""
import logging
import os
import time
import traceback
from collections.abc import Callable

from clue.core.db import SessionLocal
from clue.jobs import queue

log = logging.getLogger("clue.worker")
HANDLERS: dict[str, Callable] = {}


def handler(job_type: str):
    """Register a job handler: fn(db, job) -> result dict."""
    def deco(fn):
        HANDLERS[job_type] = fn
        return fn
    return deco


def run_once(worker_id: str) -> bool:
    """Claim and run one job. Returns True if a job was processed."""
    with SessionLocal() as db:
        job = queue.claim(db, worker_id, list(HANDLERS))
        if job is None:
            return False
        try:
            result = HANDLERS[job.type](db, job) or {}
            queue.finish(db, job.id, result)
        except Exception as e:  # noqa: BLE001
            log.error("job %s failed: %s", job.id, traceback.format_exc())
            queue.fail(db, job.id, f"{e.__class__.__name__}: {e}")
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    wid = f"w{os.getpid()}"
    log.info("worker %s started", wid)
    while True:
        if not run_once(wid):
            time.sleep(1.0)


if __name__ == "__main__":
    main()
