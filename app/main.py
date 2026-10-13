from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.db import init_db
from app.routes.api import router as api_router
from app.routes.pages import router as pages_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Initialize persistent resources at startup."""

    init_db()
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application instance."""

    app = FastAPI(title="KoboKeeper", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.include_router(pages_router)
    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    def root_redirect() -> RedirectResponse:
        return RedirectResponse(url="/dashboard", status_code=307)

    return app


app = create_app()
