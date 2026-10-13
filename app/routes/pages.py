from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard_page(request: Request) -> HTMLResponse:
    """Render the dashboard placeholder page."""

    return templates.TemplateResponse(request=request, name="dashboard.html", context={})


@router.get("/upload", response_class=HTMLResponse)
def upload_page(request: Request) -> HTMLResponse:
    """Render the upload placeholder page."""

    return templates.TemplateResponse(request=request, name="upload.html", context={})
