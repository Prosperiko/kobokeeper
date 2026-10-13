from __future__ import annotations


"""Export service implementation is added in later phases."""

"""Export services: accountant-ready CSV (per month) and PDF (per receipt).

Everything here runs against local data only — no network calls, no paid APIs.
The CSV uses a UTF-8 BOM so Excel opens it cleanly; the PDF uses only core
reportlab fonts, so the Naira sign is rendered as 'NGN' (Helvetica has no ₦
glyph — a deliberate portability choice, not an oversight).
"""


import csv
import io
from datetime import date, datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, LineItem, Receipt

CSV_HEADER = [
    "Date",
    "Vendor",
    "Category",
    "Item",
    "Qty",
    "Unit Price",
    "Amount",
    "Receipt Total",
    "Tax",
]


def _money(value: float | None) -> str:
    """Format an amount the way an accountant expects: NGN 12,500.00."""
    if value is None:
        return ""
    return f"NGN {value:,.2f}"


def export_month_csv(db: Session, year: int, month: int) -> str:
    """Return a CSV string for one month: one row per line item.

    Receipt-level fields repeat on every row so the sheet sorts and filters
    cleanly. A UTF-8 BOM (\\ufeff) is prepended so Excel detects encoding.
    """
    month_start = date(year, month, 1)
    next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)

    receipts = db.scalars(
        select(Receipt)
        .where(Receipt.date >= month_start, Receipt.date < next_month)
        .order_by(Receipt.date.asc(), Receipt.id.asc())
    ).all()

    category_names = {c.id: c.name for c in db.scalars(select(Category)).all()}

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADER)
    for receipt in receipts:
        category = category_names.get(receipt.category_id, "")
        items: list[LineItem] = receipt.line_items or []
        if not items:
            # Receipt with no line items still exports one summary row.
            writer.writerow(
                [
                    receipt.date.isoformat() if receipt.date else "",
                    receipt.vendor_name,
                    category,
                    "",
                    "",
                    "",
                    "",
                    receipt.total,
                    receipt.tax if receipt.tax is not None else "",
                ]
            )
            continue
        for item in items:
            writer.writerow(
                [
                    receipt.date.isoformat() if receipt.date else "",
                    receipt.vendor_name,
                    category,
                    item.name,
                    item.qty,
                    item.unit_price if item.unit_price is not None else "",
                    item.amount,
                    receipt.total,
                    receipt.tax if receipt.tax is not None else "",
                ]
            )
    return "\ufeff" + buffer.getvalue()


def export_receipt_pdf(db: Session, receipt_id: int) -> bytes:
    """Render a single receipt as a clean A4 PDF. Raises LookupError if missing."""
    receipt = db.get(Receipt, receipt_id)
    if receipt is None:
        raise LookupError(f"Receipt {receipt_id} not found")

    category_name = receipt.category.name if receipt.category else ""

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"KoboKeeper Receipt #{receipt.id}",
        author="KoboKeeper",
    )
    styles = getSampleStyleSheet()
    story = []

    story.append(Paragraph("KoboKeeper", styles["Title"]))
    story.append(Paragraph("Offline receipt export &middot; generated locally", styles["Normal"]))
    story.append(Paragraph(f"Generated: {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}", styles["Normal"]))
    story.append(Spacer(1, 6 * mm))

    meta = [
        ["Vendor", receipt.vendor_name],
        ["Date", receipt.date.isoformat() if receipt.date else "-"],
        ["Category", category_name or "-"],
        ["Currency", receipt.currency],
        ["Tax", _money(receipt.tax)],
    ]
    meta_table = Table(meta, colWidths=[35 * mm, 120 * mm])
    meta_table.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (0, -1), "Helvetica-Bold", 10),
                ("FONT", (1, 0), (1, -1), "Helvetica", 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(meta_table)
    story.append(Spacer(1, 6 * mm))

    items = receipt.line_items or []
    if items:
        table_data = [["Item", "Qty", "Unit Price", "Amount"]]
        for item in items:
            table_data.append(
                [
                    item.name,
                    f"{item.qty:g}",
                    _money(item.unit_price),
                    _money(item.amount),
                ]
            )
        table_data.append(["", "", "TOTAL", _money(receipt.total)])
        items_table = Table(table_data, colWidths=[85 * mm, 20 * mm, 35 * mm, 35 * mm])
        items_table.setStyle(
            TableStyle(
                [
                    ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 10),
                    ("FONT", (0, 1), (-1, -1), "Helvetica", 10),
                    ("FONT", (-2, -1), (-1, -1), "Helvetica-Bold", 10),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8e6f7")),
                    ("LINEABOVE", (0, -1), (-1, -1), 0.75, colors.HexColor("#4f46e5")),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(items_table)
    else:
        story.append(Paragraph(f"Total: {_money(receipt.total)}", styles["Heading3"]))

    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(
            "Extracted locally with an open-weight model (Gemma via Ollama). "
            "No receipt data ever left the machine that processed it.",
            styles["Italic"],
        )
    )

    doc.build(story)
    return buffer.getvalue()