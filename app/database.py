from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import settings

Base = declarative_base()


def get_database_url() -> str:
    if settings.use_sqlite_fallback:
        return "sqlite:///./lenny_growth_demo.db"
    return settings.database_url


def build_engine():
    database_url = get_database_url()
    return create_engine(database_url, pool_pre_ping=True)


def create_session_factory():
    return sessionmaker(bind=build_engine(), autoflush=False, autocommit=False)


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.models import Base as ModelBase

    ModelBase.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
