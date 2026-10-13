from __future__ import annotations

"""Seed script implementation is added in later phases."""


"""Seed demo receipts across two months so the dashboard has life.

Run from the project root:
    python scripts/seed.py

Idempotent: safe to run repeatedly — it never duplicates and never calls
the LLM. The receipts are synthetic but realistic (Lagos vendors, NGN).
"""


from datetime import date
from pathlib import Path
import sys

# Allow running as `python scripts/seed.py` from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import SEED_CATEGORIES, SessionLocal
from app.models import Category, LineItem, Receipt


DEMO_RECEIPTS = [
    {
        "vendor_name": "ShopRite Alausa",
        "date": date(2026, 9, 27),
        "total": 18450.0,
        "tax": None,
        "category": "Food",
        "items": [
            {"name": "Groceries basket", "qty": 1, "unit_price": 18450.0, "amount": 18450.0},
        ],
    },
    {
        "vendor_name": "GIG Logistics",
        "date": date(2026, 10, 3),
        "total": 8700.0,
        "tax": None,
        "category": "Transport",
        "items": [
            {"name": "Parcel delivery Lagos-Ibadan", "qty": 1, "unit_price": 8700.0, "amount": 8700.0},
        ],
    },
    {
        "vendor_name": "Jumia Nigeria",
        "date": date(2026, 10, 8),
        "total": 42300.0,
        "tax": 3450.0,
        "category": "Office Supplies",
        "items": [
            {"name": "USB-C hub", "qty": 1, "unit_price": 22800.0, "amount": 22800.0},
            {"name": "Notebook pack", "qty": 3, "unit_price": 6500.0, "amount": 19500.0},
        ],
    },
]


def main() -> None:
    with SessionLocal() as db:
        # Ensure schema + seed categories exist even on a fresh database file.
        from app.db import Base

        Base.metadata.create_all(bind=db.get_bind())

        existing = {c.name: c for c in db.query(Category).all()}
        for name in SEED_CATEGORIES:
            if name not in existing:
                db.add(Category(name=name))
        db.commit()

        if db.query(Receipt).count() > 0:
            print("Receipts already seeded — skipping (delete kobokeeper.db to reseed).")
            return

        categories = {c.name: c for c in db.query(Category).all()}
        for entry in DEMO_RECEIPTS:
            receipt = Receipt(
                vendor_name=entry["vendor_name"],
                date=entry["date"],
                currency="NGN",
                total=entry["total"],
                tax=entry["tax"],
                category_id=categories[entry["category"]].id,
                raw_ocr_text="[seeded demo receipt — no OCR source]",
                image_path=None,
                status="confirmed",
            )
            db.add(receipt)
            db.flush()
            for item in entry["items"]:
                db.add(LineItem(receipt_id=receipt.id, **item))
        db.commit()
        print(f"Seeded {len(DEMO_RECEIPTS)} demo receipts.")


if __name__ == "__main__":
    main()