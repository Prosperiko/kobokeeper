from __future__ import annotations

from datetime import date

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Category, Receipt, Vendor
from app.services.vendor_memory import learn, lookup, normalize_vendor


def test_normalize_vendor() -> None:
    assert normalize_vendor(" Shop-Rite, Ikeja! ") == "shop rite ikeja"


def test_lookup_fuzzy_matches_alias() -> None:
    with SessionLocal() as db:
        food = db.scalar(select(Category).where(Category.name == "Food"))
        vendor = Vendor(name="Shoprite Ikeja", aliases=["Shop Rite"], default_category_id=food.id if food else None)
        db.add(vendor)
        db.commit()

        match, confidence = lookup(db, "shoprite, ikeja")

    assert match is not None
    assert match.name == "Shoprite Ikeja"
    assert confidence >= 0.75


def test_learn_adds_vendor_or_alias() -> None:
    with SessionLocal() as db:
        food = db.scalar(select(Category).where(Category.name == "Food"))
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
        db.add(receipt)
        db.flush()
        learn(db, receipt)
        db.commit()

        vendor = db.scalar(select(Vendor).where(Vendor.name == "Mega Chicken"))
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
        db.add(followup)
        db.flush()
        learn(db, followup)
        db.commit()

        db.refresh(vendor)
        assert any(normalize_vendor(alias) == "mega chicken" for alias in vendor.aliases)
