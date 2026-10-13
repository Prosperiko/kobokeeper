from __future__ import annotations

from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal
from app.models import Category, LineItem, Receipt
from app.schemas import ReceiptData
from app.services.extractor import ExtractError, extract_receipt_data
from app.services.ocr import extract_text
from app.services.vendor_memory import learn, lookup

router = APIRouter(prefix="/api", tags=["api"])
templates = Jinja2Templates(directory="app/templates")

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".pdf"}


def _to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _receipt_defaults() -> ReceiptData:
    return ReceiptData(vendor="", date=None, currency="NGN", total=0.0, tax=None, items=[], suggested_category="Other")


@router.post("/extract", response_class=HTMLResponse)
async def extract_receipt(request: Request, receipt_file: UploadFile) -> HTMLResponse:
    """Run OCR + extraction for an uploaded file without persisting to DB yet."""

    suffix = Path(receipt_file.filename or "").suffix.lower()
    categories: list[Category]
    with SessionLocal() as db:
        categories = db.scalars(select(Category).order_by(Category.name.asc())).all()

    if suffix not in ALLOWED_EXTENSIONS:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "data": _receipt_defaults(),
                "categories": categories,
                "line_items": [],
                "warning": "Unsupported file type. Use .jpg, .jpeg, .png, .webp, or .pdf.",
                "raw_ocr_text": "",
                "image_path": "",
            },
            status_code=400,
        )

    settings = get_settings()
    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    safe_path = upload_dir / f"{uuid4().hex}{suffix}"
    content = await receipt_file.read()
    safe_path.write_bytes(content)

    try:
        ocr_text = extract_text(str(safe_path))
    except Exception:
        return templates.TemplateResponse(
            request=request,
            name="review.html",
            context={
                "data": _receipt_defaults(),
                "categories": categories,
                "line_items": [],
                "warning": "Could not read that file. Please try another image/PDF or fill the form manually.",
                "raw_ocr_text": "",
                "image_path": str(safe_path),
            },
            status_code=400,
        )

    try:
        data = extract_receipt_data(ocr_text=ocr_text)
        warning = None
    except ExtractError:
        data = _receipt_defaults()
        warning = "Extraction failed — fill in the receipt manually."

    with SessionLocal() as db:
        vendor_match, _confidence = lookup(db, data.vendor or "")
        if vendor_match and vendor_match.default_category:
            data.suggested_category = vendor_match.default_category.name

    return templates.TemplateResponse(
        request=request,
        name="review.html",
        context={
            "data": data,
            "categories": categories,
            "line_items": data.items,
            "warning": warning,
            "raw_ocr_text": ocr_text,
            "image_path": str(safe_path),
        },
    )


@router.get("/line-items/row", response_class=HTMLResponse)
def add_line_item_row(request: Request) -> HTMLResponse:
    """Return one blank line-item row fragment for HTMX dynamic append."""

    return templates.TemplateResponse(
        request=request,
        name="line_item_row.html",
        context={"item": {"name": "", "qty": 1, "unit_price": "", "amount": ""}},
    )


@router.post("/receipts/confirm")
async def confirm_receipt(request: Request) -> RedirectResponse:
    """Persist a reviewed receipt and update vendor memory from user-confirmed data."""

    form = await request.form()
    vendor_name = str(form.get("vendor_name", "")).strip()
    category_id = int(str(form.get("category_id", "0")) or 0) or None
    receipt_date_text = str(form.get("date", "")).strip()
    receipt_date = datetime.strptime(receipt_date_text, "%Y-%m-%d").date() if receipt_date_text else None
    currency = str(form.get("currency", "NGN")).strip() or "NGN"
    total = _to_float(str(form.get("total", "0")))
    tax_raw = str(form.get("tax", "")).strip()
    tax = _to_float(tax_raw) if tax_raw else None
    raw_ocr_text = str(form.get("raw_ocr_text", ""))
    image_path = str(form.get("image_path", "")) or None

    names = form.getlist("item_name")
    qtys = form.getlist("item_qty")
    unit_prices = form.getlist("item_unit_price")
    amounts = form.getlist("item_amount")

    with SessionLocal() as db:
        receipt = Receipt(
            vendor_name=vendor_name or "Unknown Vendor",
            date=receipt_date,
            currency=currency,
            total=total,
            tax=tax,
            category_id=category_id,
            raw_ocr_text=raw_ocr_text,
            image_path=image_path,
            status="confirmed",
        )
        db.add(receipt)
        db.flush()

        for idx, name in enumerate(names):
            cleaned_name = str(name).strip()
            if not cleaned_name:
                continue
            qty = _to_float(str(qtys[idx] if idx < len(qtys) else 1), default=1.0)
            unit_price_text = str(unit_prices[idx]) if idx < len(unit_prices) else ""
            amount_text = str(amounts[idx]) if idx < len(amounts) else "0"
            db.add(
                LineItem(
                    receipt_id=receipt.id,
                    name=cleaned_name,
                    qty=qty,
                    unit_price=_to_float(unit_price_text) if unit_price_text.strip() else None,
                    amount=_to_float(amount_text),
                )
            )

        learn(db, receipt)
        category_name = db.scalar(select(Category.name).where(Category.id == receipt.category_id)) or "Other"
        db.commit()

    flash = f"Receipt saved. KoboKeeper learned '{vendor_name or 'Unknown Vendor'}' → {category_name}."
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie("flash", quote(flash, safe=""), max_age=120, httponly=True, samesite="lax")
    return response


@router.get("/receipts/{receipt_id}/delete", response_class=HTMLResponse)
def delete_receipt(request: Request, receipt_id: int, confirm: bool = False) -> HTMLResponse:
    """Delete a receipt after user confirmation from HTMX UI."""

    if not confirm:
        return templates.TemplateResponse(
            request=request,
            name="delete_confirm.html",
            context={"receipt_id": receipt_id},
        )

    with SessionLocal() as db:
        receipt = db.get(Receipt, receipt_id)
        if receipt:
            db.delete(receipt)
            db.commit()
    return HTMLResponse("")
