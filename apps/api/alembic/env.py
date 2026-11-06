from alembic import context

import clue.models  # noqa: F401  (register tables)
from clue.core.db import Base, engine

target_metadata = Base.metadata


def run_migrations_online() -> None:
    with engine.connect() as conn:
        context.configure(connection=conn, target_metadata=target_metadata, render_as_batch=True)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
