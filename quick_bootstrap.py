# save as scripts/add_creatures_col.py and run: python scripts/add_creatures_col.py
from sqlalchemy import create_engine, text
from api.db.session import engine  # uses your configured DB URL
with engine.begin() as conn:
    conn.execute(text("ALTER TABLE cards ADD COLUMN creatures JSON"))
print("OK")
