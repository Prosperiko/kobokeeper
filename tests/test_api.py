from __future__ import annotations

from sqlalchemy import select

from app import db
from app.models import Category, LineItem, Receipt, Vendor
from app.schemas import LineItemData, ReceiptData
from app.services.extractor import ExtractError


def _mock_receipt_data(vendor: str, category: str = "Food") -> ReceiptData:
    return ReceiptData(
        vendor=vendor,
        date="2026-10-10",
        currency="NGN",
        total=3500.0,
        tax=250.0,
        items=[LineItemData(name="Bread", qty=1, unit_price=3500.0, amount=3500.0)],
        suggested_category=category,
    )


def test_upload_confirm_learn_and_delete_flow(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.api.extract_text", lambda _path: "valid ocr text with enough characters")
    monkeypatch.setattr("app.routes.api.extract_receipt_data", lambda **_: _mock_receipt_data("Shoprite Ikeja", "Food"))

    extract_response = client.post(
        "/api/extract",
        files={"receipt_file": ("receipt.png", b"fake-image", "image/png")},
    )
    assert extract_response.status_code == 200
    assert "Shoprite Ikeja" in extract_response.text

    with db.SessionLocal() as session:
        food = session.scalar(select(Category).where(Category.name == "Food"))
        category_id = food.id if food else 1

    confirm_response = client.post(
        "/api/receipts/confirm",
        data={
            "vendor_name": "Shoprite Ikeja",
            "date": "2026-10-10",
            "currency": "NGN",
            "total": "3500",
            "tax": "250",
            "category_id": str(category_id),
            "raw_ocr_text": "valid ocr text with enough characters",
            "image_path": "/tmp/fake.png",
            "item_name": ["Bread"],
            "item_qty": ["1"],
            "item_unit_price": ["3500"],
            "item_amount": ["3500"],
        },
        follow_redirects=False,
    )
    assert confirm_response.status_code == 303
    assert confirm_response.headers["location"] == "/dashboard"
    assert "flash=" in confirm_response.headers.get("set-cookie", "")

    with db.SessionLocal() as session:
        receipt = session.scalar(select(Receipt).where(Receipt.vendor_name == "Shoprite Ikeja"))
        assert receipt is not None
        assert receipt.status == "confirmed"
        item = session.scalar(select(LineItem).where(LineItem.receipt_id == receipt.id))
        assert item is not None
        vendor = session.scalar(select(Vendor).where(Vendor.name == "Shoprite Ikeja"))
        assert vendor is not None

        delete_response = client.get(f"/api/receipts/{receipt.id}/delete?confirm=true")
        assert delete_response.status_code == 200

    with db.SessionLocal() as session:
        assert session.get(Receipt, receipt.id) is None


def test_extract_prefills_category_from_vendor_memory(client, monkeypatch) -> None:
    with db.SessionLocal() as session:
        food = session.scalar(select(Category).where(Category.name == "Food"))
        vendor = Vendor(name="Shoprite Ikeja", aliases=["Shop Rite"], default_category_id=food.id if food else None)
        session.add(vendor)
        session.commit()
        expected_id = food.id if food else 1

    monkeypatch.setattr("app.routes.api.extract_text", lambda _path: "valid ocr text with enough characters")
    monkeypatch.setattr("app.routes.api.extract_receipt_data", lambda **_: _mock_receipt_data("shop rite ikeja", "Other"))

    response = client.post(
        "/api/extract",
        files={"receipt_file": ("receipt.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 200
    assert f'option value="{expected_id}" selected' in response.text


def test_extract_rejects_extension_and_handles_ocr_errors(client, monkeypatch) -> None:
    unsupported = client.post(
        "/api/extract",
        files={"receipt_file": ("receipt.exe", b"fake-binary", "application/octet-stream")},
    )
    assert unsupported.status_code == 400
    assert "Unsupported file type" in unsupported.text

    monkeypatch.setattr("app.routes.api.extract_text", lambda _path: (_ for _ in ()).throw(RuntimeError("ocr fail")))
    failing = client.post(
        "/api/extract",
        files={"receipt_file": ("receipt.pdf", b"%PDF-fake", "application/pdf")},
    )
    assert failing.status_code == 400
    assert "Could not read that file" in failing.text


def test_extract_error_uses_manual_review_fallback(client, monkeypatch) -> None:
    monkeypatch.setattr("app.routes.api.extract_text", lambda _path: "valid ocr text with enough characters")
    monkeypatch.setattr(
        "app.routes.api.extract_receipt_data",
        lambda **_: (_ for _ in ()).throw(ExtractError("invalid", raw_text="bad raw")),
    )

    response = client.post(
        "/api/extract",
        files={"receipt_file": ("receipt.webp", b"fake-image", "image/webp")},
    )
    assert response.status_code == 200
    assert "Extraction failed" in response.text
