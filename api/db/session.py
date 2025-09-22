# api/db/session.py
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Use SQLite by default; override with env var if you like (e.g., Postgres URL)
DB_URL = os.getenv("CARDGEN_DB_URL", "sqlite:///./data/cards.db")

# SQLite needs check_same_thread=False for multithreaded CherryPy
connect_args = {"check_same_thread": False} if DB_URL.startswith("sqlite") else {}

engine = create_engine(DB_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
