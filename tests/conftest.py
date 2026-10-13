from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import db
from app.main import app
from app.routes import api, pages


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    """Provide a TestClient backed by a temporary SQLite DB and upload dir."""

    test_db_url = f"sqlite:///{tmp_path / 'test.db'}"
    test_engine = create_engine(test_db_url, connect_args={"check_same_thread": False}, future=True)
    test_session_local = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, future=True)

    monkeypatch.setattr(db, "engine", test_engine)
    monkeypatch.setattr(db, "SessionLocal", test_session_local)
    monkeypatch.setattr(pages, "SessionLocal", test_session_local)
    monkeypatch.setattr(api, "SessionLocal", test_session_local)
    monkeypatch.setattr(api, "get_settings", lambda: SimpleNamespace(upload_dir=str(tmp_path / "uploads")))

    db.init_db()

    with TestClient(app) as test_client:
        yield test_client
