"""
Database session configuration for SQLAlchemy with robust connection handling.

Behavior:
- Uses DATABASE_URL from environment, defaults to SQLite file for development.
- Retries connection to the configured database on startup.
- If a non-SQLite database is unreachable after retries, falls back to SQLite
  to ensure the app starts without noisy warnings.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .models import Base
import os
import time
import logging

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

def _create_engine_for_url(url: str):
    """Create a SQLAlchemy engine appropriate for the given URL."""
    if url.startswith("sqlite"):
        return create_engine(
            url,
            poolclass=StaticPool,
            connect_args={"check_same_thread": False},
            echo=True,  # Set to False in production
        )
    # Non-SQLite: use default pooling and pre_ping
    return create_engine(
        url,
        echo=True,  # Set to False in production
        pool_pre_ping=True,
    )

def _try_connect(test_engine, attempts: int = 10, delay_seconds: float = 1.0) -> bool:
    """Try to connect to the database a few times to allow container warmup."""
    for i in range(1, attempts + 1):
        try:
            with test_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                return True
        except Exception as e:
            if i == attempts:
                break
            time.sleep(delay_seconds)
    return False

# Create primary engine; retry; fallback to SQLite if needed
engine = _create_engine_for_url(DATABASE_URL)
if not DATABASE_URL.startswith("sqlite"):
    if not _try_connect(engine):
        logger.warning(
            f"Primary DB unreachable at {DATABASE_URL}. Falling back to SQLite (./test.db) for development."
        )
        DATABASE_URL = "sqlite:///./test.db"
        engine = _create_engine_for_url(DATABASE_URL)
        # No retry needed for local SQLite, but attempt once to create file
        _try_connect(engine, attempts=1)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def _ensure_sqlite_migrations() -> None:
    """Minimal migration shim for SQLite to keep local dev DB in sync.

    Adds missing columns introduced after initial creation without destroying data.
    """
    if not DATABASE_URL.startswith("sqlite"):
        return
    try:
        with engine.connect() as conn:
            # Check conversations table exists
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='conversations'"))
            if result.fetchone() is None:
                return
            # Inspect columns
            cols = conn.execute(text("PRAGMA table_info(conversations)")).fetchall()
            col_names = {row[1] for row in cols}
            if 'channel_context' not in col_names:
                conn.execute(text("ALTER TABLE conversations ADD COLUMN channel_context JSON"))
    except Exception:
        # Do not block app start on shim failure
        pass

_initialized = False

def get_db() -> Session:
    """Get database session."""
    global _initialized
    if not _initialized:
        try:
            _ensure_sqlite_migrations()
            Base.metadata.create_all(bind=engine)
        finally:
            _initialized = True
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def create_tables():
    """Create all tables."""
    Base.metadata.create_all(bind=engine)

def drop_tables():
    """Drop all tables."""
    Base.metadata.drop_all(bind=engine)
