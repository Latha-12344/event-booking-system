"""
SQLAlchemy engine, session factory, and dependency for FastAPI.

Connection pool is tuned for moderate concurrency:
- pool_size=20     : up to 20 persistent connections
- max_overflow=10  : allow 10 extra connections at peak
- pool_pre_ping=True : verify connections before use (handles DB restarts)
- pool_timeout=30  : raise error if no connection available within 30s
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=20,
    max_overflow=10,
    pool_pre_ping=True,
    pool_timeout=30,
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()