from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from app.config import get_settings

Base = declarative_base()

settings = get_settings()
engine = create_engine(settings.db_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)

SEED_CATEGORIES = [
    "Food",
    "Transport",
    "Software",
    "Utilities",
    "Rent",
    "Office Supplies",
    "Professional Services",
    "Other",
]


def get_db() -> Generator[Session, None, None]:
    """Yield a database session and ensure it is closed."""

    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create database tables and seed fixed categories."""

    from app.models import Category

    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        existing = set(db.scalars(select(Category.name)).all())
        missing = [Category(name=name) for name in SEED_CATEGORIES if name not in existing]
        if missing:
            db.add_all(missing)
            db.commit()
