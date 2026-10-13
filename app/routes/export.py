from __future__ import annotations




from fastapi import APIRouter
from fastapi.responses import Response

from app.db import SessionLocal
from app.services.export import export_month_csv, export_receipt_pdf

router = APIRouter(tags=["export"])


@router.get("/export/csv")
def export_csv(year: int, month: int) -> Response:
    """Download the month's receipts as an accountant-ready CSV."""
    with SessionLocal() as db:
        content = export_month_csv(db, year=year, month=month)
    filename = f"kobokeeper-{year}-{month:02d}.csv"
    return Response(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/export/receipt/{receipt_id}/pdf")
def export_receipt_pdf_route(receipt_id: int) -> Response:
    """Download a single receipt as a PDF."""
    with SessionLocal() as db:
        try:
            pdf_bytes = export_receipt_pdf(db, receipt_id=receipt_id)
        except LookupError:
            return Response(content="Receipt not found", status_code=404, media_type="text/plain")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="receipt-{receipt_id}.pdf"'},
    )