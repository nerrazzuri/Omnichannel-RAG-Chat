"""
Database session configuration for SQLAlchemy.
"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from .models import Base
import os

# Database URL from environment
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./test.db")

connect_args = {}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

# Create engine
engine = create_engine(
    DATABASE_URL,
    poolclass=StaticPool,
    connect_args=connect_args,
    echo=True  # Set to False in production
)

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
