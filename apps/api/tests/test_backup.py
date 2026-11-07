import sqlite3
import tarfile

import pytest
from sqlalchemy import select

from clue import backup
from clue.core import credits, storage
from clue.core.config import get_settings
from clue.models import User
from tests.conftest import signup


def test_backup_restore_roundtrip_with_a_live_database(client, db, tmp_path):
    signup(client, "keep@example.com")
    u = db.scalar(select(User).where(User.email == "keep@example.com"))
    credits.grant(db, u.id, 77, "before backup")
    bal = credits.balance(db, u.id)
    f = storage.root() / u.id / "out.mp4"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_bytes(b"video-bytes" * 100)
    (storage.root() / "cache").mkdir(exist_ok=True)
    (storage.root() / "cache" / "skipme.bin").write_bytes(b"x")

    archive = backup.create(tmp_path / "out")  # taken while the app's connection is still open
    info = backup.verify(archive)
    assert info["tables"] >= 10 and info["db_revision"] is None or info["tables"] >= 10  # create_all test DB has no alembic table
    names = tarfile.open(archive).getnames()
    assert "db/clue.db" in names and "secret/.secret" in names and f"files/{u.id}/out.mp4" in names
    assert not any("skipme" in n for n in names)  # re-downloadable cache is left out

    # disaster: the user, their credits and their file are gone
    f.unlink()
    db.execute(User.__table__.delete())
    db.commit()

    target = tmp_path / "restored"
    backup.restore(archive, target)
    con = sqlite3.connect(target / "clue.db")
    assert con.execute("select email from users").fetchall() == [("keep@example.com",)]
    assert con.execute("select coalesce(sum(delta),0) from credit_ledger").fetchone()[0] == bal  # the ledger reconciles after restore
    assert (target / "files" / u.id / "out.mp4").read_bytes() == b"video-bytes" * 100
    assert (target / ".secret").read_bytes() == (get_settings().storage_dir / ".secret").read_bytes()


def test_a_damaged_backup_is_rejected_before_anything_is_touched(client, db, tmp_path):
    signup(client, "x@example.com")
    archive = backup.create(tmp_path / "out", media=False)
    bad = tmp_path / "bad.tar.gz"
    with tarfile.open(archive) as src, tarfile.open(bad, "w:gz") as dst:
        for m in src.getmembers():
            data = src.extractfile(m)
            if m.name == "db/clue.db":
                import io

                raw = data.read()
                raw = raw[:200] + b"BAD" + raw[203:]  # flip bytes inside the file
                m.size = len(raw)
                dst.addfile(m, io.BytesIO(raw))
            else:
                dst.addfile(m, data)
    target = tmp_path / "keepme"
    target.mkdir()
    (target / "precious.txt").write_text("do not lose me")
    with pytest.raises(SystemExit, match="damaged|integrity"):
        backup.restore(bad, target)
    assert (target / "precious.txt").read_text() == "do not lose me"  # untouched


def test_restore_moves_existing_data_aside_instead_of_deleting(client, db, tmp_path):
    signup(client, "y@example.com")
    archive = backup.create(tmp_path / "out", media=False)
    target = tmp_path / "live"
    target.mkdir()
    (target / "old.txt").write_text("old")
    backup.restore(archive, target)
    aside = [p for p in tmp_path.iterdir() if p.name.startswith("live.before-restore-")]
    assert len(aside) == 1 and (aside[0] / "old.txt").read_text() == "old"


def test_unsafe_archive_paths_are_refused(tmp_path):
    evil = tmp_path / "evil.tar.gz"
    import io

    with tarfile.open(evil, "w:gz") as t:
        info = tarfile.TarInfo("../escape.txt")
        info.size = 3
        t.addfile(info, io.BytesIO(b"bad"))
    with pytest.raises(SystemExit, match="unsafe"):
        backup.verify(evil)
