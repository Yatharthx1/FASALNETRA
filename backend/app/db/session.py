from collections.abc import Generator
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import settings
from backend.app.db.database import PG_ARGS

# Same database as the async case engine (db/database.py), opened with the sync driver
SYNC_DATABASE_URL = settings.db_url(sync=True)

# Ensure sqlite directory exists if local sqlite path is used
if SYNC_DATABASE_URL.startswith("sqlite"):
    db_path = SYNC_DATABASE_URL.replace("sqlite:///", "")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        SYNC_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(SYNC_DATABASE_URL, **PG_ARGS)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    # Import all models before create_all
    import backend.app.models.farmer  # noqa: F401
    import backend.app.models.ivr_session  # noqa: F401

    Base.metadata.create_all(bind=engine)

    # Lightweight auto-migration for SQLite development database
    if not settings.is_postgres:
        with engine.connect() as conn:
            res = conn.exec_driver_sql("PRAGMA table_info(farmers)").fetchall()
            existing_cols = {row[1] for row in res}
            if "active_flow" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE farmers ADD COLUMN active_flow VARCHAR(30) DEFAULT 'safe'")
            if "risk_score" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE farmers ADD COLUMN risk_score INTEGER DEFAULT 20")
            if "spray_booked" not in existing_cols:
                conn.exec_driver_sql("ALTER TABLE farmers ADD COLUMN spray_booked VARCHAR(10) DEFAULT 'no'")
            conn.commit()
