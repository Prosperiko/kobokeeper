from __future__ import annotations

from datetime import date
from urllib.parse import unquote

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.db import SessionLocal
from app.models import Category, Receipt

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request, year: int | None = None, month: int | None = None) -> HTMLResponse:
    """Render dashboard with current month totals and recent receipts."""

    today = date.today()
    selected_year = year or today.year
    selected_month = month or today.month
    month_start = date(selected_year, selected_month, 1)
    next_month = date(selected_year + (1 if selected_month == 12 else 0), 1 if selected_month == 12 else selected_month + 1, 1)

    with SessionLocal() as db:
        monthly_total = (
            db.scalar(
                select(func.coalesce(func.sum(Receipt.total), 0.0)).where(
                    Receipt.date >= month_start,
                    Receipt.date < next_month,
                )
            )
            or 0.0
        )
        category_rows = db.execute(
            select(Category.name, func.coalesce(func.sum(Receipt.total), 0.0))
            .select_from(Category)
            .join(Receipt, Receipt.category_id == Category.id, isouter=True)
            .where(
                (Receipt.date.is_(None))
                | ((Receipt.date >= month_start) & (Receipt.date < next_month))
            )
            .group_by(Category.name)
            .order_by(Category.name)
        ).all()
        recent_receipts = db.scalars(select(Receipt).order_by(Receipt.created_at.desc()).limit(10)).all()

    category_totals = [
        {"name": row[0], "total": float(row[1] or 0.0)}
        for row in category_rows
        if float(row[1] or 0.0) > 0
    ]

    context = {
        "monthly_total": float(monthly_total),
        "category_totals": category_totals,
        "recent_receipts": recent_receipts,
        "year": selected_year,
        "month": selected_month,
        "flash": unquote(request.query_params.get("flash", "")) if request.query_params.get("flash") else None,
    }
    return templates.TemplateResponse(request=request, name="dashboard.html", context=context)


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    """Render the upload placeholder page."""

    return templates.TemplateResponse(
        request=request,
        name="upload.html",
        context={"flash": request.query_params.get("flash")},
    )
