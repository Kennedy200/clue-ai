"""Backup and restore for the SQLite install.

  python -m clue.backup create [--out DIR] [--no-media]
  python -m clue.backup restore ARCHIVE [--to DIR]      (default: the configured storage folder)
  python -m clue.backup verify ARCHIVE

The database is copied with SQLite's online backup API, so it is consistent even while the app is running.
The archive also holds the encryption secret (without it the saved OpenRouter key cannot be read) and a manifest
of SHA-256 checksums. KEEP ARCHIVES PRIVATE: they contain that secret. On Postgres use pg_dump instead (see docs/RUNBOOK.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from clue.core.config import get_settings

SKIP_DIRS = {"models", "cache", "tmp", "screens", "sample", "uploads_tmp"}  # re-downloadable or scratch
SKIP_SUFFIX = (".log", ".db-wal", ".db-shm")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _head_revision() -> str:
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.set_main_option("script_location", str(Path(__file__).resolve().parents[1] / "alembic"))
        return ScriptDirectory.from_config(cfg).get_current_head() or ""
    except Exception:  # noqa: BLE001
        return ""


def create(out_dir: Path, media: bool = True) -> Path:
    s = get_settings()
    if not s.db_url.startswith("sqlite"):
        raise SystemExit("This tool backs up SQLite. For Postgres use pg_dump (docs/RUNBOOK.md).")
    from clue.core.security import _fernet

    _fernet()  # makes sure the secret file exists so the archive is always restorable
    store = s.storage_dir
    src_db = Path(s.db_url.removeprefix("sqlite:///"))
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    archive = out_dir / f"clue-backup-{stamp}.tar.gz"
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        snap = tmpd / "clue.db"
        src, dst = sqlite3.connect(src_db), sqlite3.connect(snap)
        with dst:
            src.backup(dst)  # consistent snapshot, safe while the app is writing
        src.close()
        dst.close()
        files: dict[str, Path] = {"db/clue.db": snap}
        if (store / ".secret").exists():
            files["secret/.secret"] = store / ".secret"
        if media and (store / "files").is_dir():
            for f in (store / "files").rglob("*"):
                rel = f.relative_to(store / "files")
                if f.is_file() and rel.parts[0] not in SKIP_DIRS and not f.name.endswith(SKIP_SUFFIX):
                    files[f"files/{rel.as_posix()}"] = f
        manifest = {"version": 1, "created": stamp, "alembic_head": _head_revision(), "media": media,
                    "files": {name: {"sha256": _sha(p), "bytes": p.stat().st_size} for name, p in files.items()}}
        mpath = tmpd / "manifest.json"
        mpath.write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(mpath, arcname="manifest.json")
            for name, p in files.items():
                tar.add(p, arcname=name)
    return archive


def verify(archive: Path) -> dict:
    """Check every checksum in the archive and that the database opens and passes SQLite's integrity check."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _extract(archive, root)
        return _check(root)


def _extract(archive: Path, dest: Path) -> None:
    with tarfile.open(archive, "r:gz") as tar:
        for m in tar.getmembers():  # refuse anything that could escape the folder
            if m.name.startswith(("/", "..")) or ".." in Path(m.name).parts or not (m.isfile() or m.isdir()):
                raise SystemExit(f"Refusing unsafe archive entry: {m.name}")
        tar.extractall(dest, filter="data")


def _check(root: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, meta in manifest["files"].items():
        p = root / name
        if not p.is_file() or _sha(p) != meta["sha256"]:
            raise SystemExit(f"Backup is damaged: {name} is missing or does not match its checksum.")
    con = sqlite3.connect(root / "db" / "clue.db")
    ok = con.execute("PRAGMA integrity_check").fetchone()[0]
    tables = con.execute("SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
    rev = None
    try:
        rev = con.execute("SELECT version_num FROM alembic_version").fetchone()
        rev = rev[0] if rev else None
    except sqlite3.Error:
        pass
    con.close()
    if ok != "ok":
        raise SystemExit(f"The database in this backup failed SQLite's integrity check: {ok}")
    return {"files": len(manifest["files"]), "tables": tables, "db_revision": rev, "created": manifest["created"], "media": manifest["media"]}


def restore(archive: Path, to: Path | None = None) -> Path:
    """Restore into `to` (default: the configured storage folder). Anything already there is moved aside, never deleted."""
    target = (to or get_settings().storage_dir).resolve()
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        _extract(archive, root)
        info = _check(root)  # nothing is touched until the archive is proven good
        if target.exists() and any(target.iterdir()):
            aside = target.with_name(f"{target.name}.before-restore-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}")
            shutil.move(str(target), str(aside))
            print(f"Existing data moved to {aside}")
        (target / "files").mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / "db" / "clue.db", target / "clue.db")
        if (root / "secret" / ".secret").exists():
            shutil.copy2(root / "secret" / ".secret", target / ".secret")
        if (root / "files").is_dir():
            shutil.copytree(root / "files", target / "files", dirs_exist_ok=True)
    print(f"Restored {info['files']} files into {target}")
    return target


def main() -> None:
    ap = argparse.ArgumentParser(prog="clue.backup")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create")
    c.add_argument("--out", default=str(get_settings().storage_dir.parent / "backups"))
    c.add_argument("--no-media", action="store_true")
    r = sub.add_parser("restore")
    r.add_argument("archive")
    r.add_argument("--to")
    v = sub.add_parser("verify")
    v.add_argument("archive")
    a = ap.parse_args()
    if a.cmd == "create":
        p = create(Path(a.out), media=not a.no_media)
        print(f"Backup written: {p} ({p.stat().st_size / 1e6:.1f} MB). It contains your secret key: keep it private.")
    elif a.cmd == "verify":
        print(json.dumps(verify(Path(a.archive)), indent=1))
    else:
        restore(Path(a.archive), Path(a.to) if a.to else None)


if __name__ == "__main__":
    sys.exit(main())
