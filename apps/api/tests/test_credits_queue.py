import threading

import pytest
from sqlalchemy import func, select

from clue.core import credits
from clue.core.db import SessionLocal
from clue.jobs import queue
from clue.models import CreditLedger, User


def _user(db):
    u = User(email="c@example.com", password_hash="x")
    db.add(u)
    db.commit()
    return u


def test_reserve_settle_refund_and_never_negative(db):
    u = _user(db)
    credits.grant(db, u.id, 10, "t")
    credits.reserve(db, u.id, 6, "render", "job1")
    assert credits.balance(db, u.id) == 4
    credits.reserve(db, u.id, 6, "render", "job1")  # idempotent
    assert credits.balance(db, u.id) == 4
    with pytest.raises(credits.InsufficientCredits):
        credits.reserve(db, u.id, 5, "render", "job2")
    assert credits.balance(db, u.id) == 4
    credits.refund(db, u.id, "job1")
    credits.refund(db, u.id, "job1")  # double refund is a no-op
    assert credits.balance(db, u.id) == 10
    credits.reserve(db, u.id, 3, "x", "job3")
    credits.settle(db, u.id, "job3")
    credits.refund(db, u.id, "job3")  # cannot refund a settled spend
    assert credits.balance(db, u.id) == 7


def test_ledger_reconciles(db):
    u = _user(db)
    credits.grant(db, u.id, 20, "g")
    credits.reserve(db, u.id, 5, "r", "a")
    credits.reserve(db, u.id, 5, "r", "b")
    credits.refund(db, u.id, "b")
    total = db.scalar(select(func.sum(CreditLedger.delta)).where(CreditLedger.user_id == u.id))
    assert total == credits.balance(db, u.id) == 15


def test_concurrent_claim_no_double_processing(db):
    for i in range(20):
        queue.enqueue(db, "t", {"i": i})
    claimed: list[str] = []
    lock = threading.Lock()

    def work(name):
        with SessionLocal() as s:
            while (j := queue.claim(s, name)) is not None:
                with lock:
                    claimed.append(j.id)

    ts = [threading.Thread(target=work, args=(f"w{i}",)) for i in range(4)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(claimed) == 20 and len(set(claimed)) == 20


def test_priority_and_retry(db):
    low = queue.enqueue(db, "t", {}, priority=0)
    high = queue.enqueue(db, "t", {}, priority=5)
    assert queue.claim(db, "w").id == high.id
    assert queue.claim(db, "w").id == low.id
    assert queue.fail(db, low.id, "boom") == "queued"  # attempt 1 of 2
    assert queue.claim(db, "w").id == low.id
    assert queue.fail(db, low.id, "boom") == "failed"
