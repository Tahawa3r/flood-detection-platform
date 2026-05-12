"""
SQLAlchemy engine, session factory, and Base for ORM models.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

# SQLite requires check_same_thread=False for multi-threaded use
connect_args = {}
if settings.resolved_database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False

engine = create_engine(settings.resolved_database_url, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
