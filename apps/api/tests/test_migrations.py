import os
import subprocess
import sys
import tempfile
from pathlib import Path


def test_fresh_database_builds_from_migrations_and_matches_the_models():
    """A new install runs every migration from nothing; the result must equal what the ORM models describe."""
    api_dir = Path(__file__).resolve().parents[1]
    with tempfile.TemporaryDirectory() as d:
        env = {**os.environ, "STORAGE_PATH": d, "PYTHONPATH": str(api_dir)}
        up = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=api_dir, env=env, capture_output=True, text=True, timeout=180)
        assert up.returncode == 0, up.stderr[-800:]
        code = (
            "from alembic.migration import MigrationContext\n"
            "from alembic.autogenerate import compare_metadata\n"
            "import clue.models\n"
            "from clue.core.db import Base, engine\n"
            "with engine.connect() as c:\n"
            "    diff = compare_metadata(MigrationContext.configure(c), Base.metadata)\n"
            "print('DRIFT', diff)\n"
            "assert not diff\n"
        )
        chk = subprocess.run([sys.executable, "-c", code], cwd=api_dir, env=env, capture_output=True, text=True, timeout=120)
        assert chk.returncode == 0, chk.stdout[-800:] + chk.stderr[-800:]
