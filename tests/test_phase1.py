from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import SEED_CATEGORIES, SessionLocal
from app.main import app
from app.models import Category


def test_root_redirect_and_dashboard_load() -> None:
    with TestClient(app) as client:
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/dashboard"

        dashboard = client.get("/dashboard")
        assert dashboard.status_code == 200


def test_startup_seeds_expected_categories() -> None:
    with TestClient(app):
        with SessionLocal() as db:
            names = set(db.scalars(select(Category.name)).all())

    assert set(SEED_CATEGORIES).issubset(names)
