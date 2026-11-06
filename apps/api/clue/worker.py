"""Worker process: polls the DB queue and runs registered handlers."""
import logging
import os
import sys
import time
import traceback
from collections.abc import Callable

from clue.core import credits
from clue.core.db import SessionLocal
from clue.jobs import queue
from clue.jobs.registry import HANDLERS, handler  # noqa: F401  (re-exported)

log = logging.getLogger("clue.worker")


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
            msg = str(e) if getattr(e, "retryable", True) is False else f"{e.__class__.__name__}: {e}"
            status = queue.fail(db, job.id, msg, retry=getattr(e, "retryable", True))
            if status == "failed" and job.credit_ref and job.user_id:
                credits.refund(db, job.user_id, job.credit_ref)
        return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    import clue.jobs.handlers as handlers  # noqa: F401  (registers job handlers)

    if "--check" in sys.argv:
        print("handlers:", ",".join(sorted(HANDLERS)))
        return

    with SessionLocal() as db:
        handlers.recover_stale(db)
    wid = f"w{os.getpid()}"
    log.info("worker %s started", wid)
    last_bill = 0.0
    while True:
        if time.time() - last_bill > 300:  # subscription renewals and payment retries
            last_bill = time.time()
            try:
                from clue.core import billing

                with SessionLocal() as db:
                    billing.renew_due(db)
            except Exception:  # noqa: BLE001
                log.error("billing run failed: %s", traceback.format_exc())
        if not run_once(wid):
            time.sleep(1.0)


if __name__ == "__main__":
    main()
