from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app import db
from app.models import Category, Receipt, Vendor
from app.services.vendor_memory import learn, lookup, normalize_vendor


def test_normalize_vendor() -> None:
    assert normalize_vendor(" Shop-Rite, Ikeja! ") == "shop rite ikeja"


def test_lookup_fuzzy_matches_alias(client) -> None:
    with db.SessionLocal() as session:
        food = session.scalar(select(Category).where(Category.name == "Food"))
        vendor = Vendor(name="Shoprite Ikeja", aliases=["Shop Rite"], default_category_id=food.id if food else None)
        session.add(vendor)
        session.commit()

        match, confidence = lookup(session, "shoprite, ikeja")

    assert match is not None
    assert match.name == "Shoprite Ikeja"
    assert confidence >= 0.75


def test_learn_adds_vendor_or_alias(client) -> None:
    with db.SessionLocal() as session:
        food = session.scalar(select(Category).where(Category.name == "Food"))
        receipt = Receipt(
            vendor_name="Mega Chicken",
            date=date(2026, 10, 1),
            currency="NGN",
            total=5000.0,
            tax=None,
            category_id=food.id if food else None,
            raw_ocr_text="sample",
            status="confirmed",
        )
        session.add(receipt)
        session.flush()
        learn(session, receipt)
        session.commit()

        vendor = session.scalar(select(Vendor).where(Vendor.name == "Mega Chicken"))
        assert vendor is not None
        assert vendor.default_category_id == (food.id if food else None)

        followup = Receipt(
            vendor_name="Mega-Chicken",
            date=date(2026, 10, 2),
            currency="NGN",
            total=7000.0,
            tax=None,
            category_id=food.id if food else None,
            raw_ocr_text="sample2",
            status="confirmed",
        )
        session.add(followup)
        session.flush()
        learn(session, followup)
        session.commit()

        session.refresh(vendor)
        assert any(normalize_vendor(alias) == "mega chicken" for alias in vendor.aliases)
