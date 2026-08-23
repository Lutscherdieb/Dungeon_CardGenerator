"""Engine, session and schema creation for the card store.

One SQLite file, one user, localhost -- so there is no connection pooling story
and no migration framework here. The card *shape* lives in ``cardgen.model`` and
is stored as JSON, so adding a field to the model needs no schema change at all;
only the handful of indexed columns below would ever need a migration.

Override the location with ``CARDGEN_DB_URL`` (the name the earlier REST sketch
used, kept so an existing local file still resolves).
"""

from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DEFAULT_DB_PATH = Path("data") / "cards.db"


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    """The configured database URL, defaulting to the local SQLite file."""
    configured = os.environ.get("CARDGEN_DB_URL")
    if configured:
        return configured
    return "sqlite:///{}".format(DEFAULT_DB_PATH.as_posix())


def make_engine(url: "str | None" = None):
    url = url or database_url()
    if url.startswith("sqlite:///") and not url.endswith(":memory:"):
        # create_engine will not make the directory for us, and a missing
        # data/ turns into an opaque "unable to open database file".
        path = Path(url[len("sqlite:///"):])
        path.parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, future=True, connect_args=connect_args)


engine = make_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db(target_engine=None) -> None:
    """Create any missing tables. Safe to call on every start."""
    from . import models  # noqa: F401  -- registers the mappings before create_all

    Base.metadata.create_all(bind=target_engine or engine)
