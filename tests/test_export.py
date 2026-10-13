from __future__ import annotations

"""Export tests are added in later phases."""

"""Export service tests. Fully self-contained: own in-memory SQLite,
no Ollama, no conftest dependencies."""


from datetime import date

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app.models import Category, LineItem, Receipt
from app.services.export import export_month_csv, export_receipt_pdf


def _db_with_receipt() -> Session:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = Session(engine)
    food = Category(name="Food")
    db.add_all([food])
    db.flush()
    receipt = Receipt(
        vendor_name="ShopRite",
        date=date(2026, 10, 2),
        currency="NGN",
        total=12500.0,
        tax=None,
        category_id=food.id,
        raw_ocr_text="ocr text",
    )
    db.add(receipt)
    db.flush()
    db.add(LineItem(receipt_id=receipt.id, name="Groceries", qty=1, unit_price=None, amount=12500.0))
    db.commit()
    return db


def test_csv_export_has_bom_and_rows() -> None:
    db = _db_with_receipt()
    content = export_month_csv(db, 2026, 10)
    assert content.startswith("\ufeff")
    assert "Date,Vendor,Category,Item" in content
    assert "ShopRite" in content
    assert "Food" in content
    assert "12500" in content


def test_csv_export_wrong_month_is_empty() -> None:
    db = _db_with_receipt()
    content = export_month_csv(db, 2026, 11)
    assert "ShopRite" not in content


def test_pdf_export_non_trivial() -> None:
    db = _db_with_receipt()
    receipt = db.query(Receipt).one()
    pdf = export_receipt_pdf(db, receipt.id)
    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 1000


def test_pdf_export_missing_receipt_raises() -> None:
    db = _db_with_receipt()
    try:
        export_receipt_pdf(db, 999)
    except LookupError:
        return
    raise AssertionError("expected LookupError for missing receipt")