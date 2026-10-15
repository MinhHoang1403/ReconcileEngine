"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.smartrecon_api.config import get_settings
from backend.smartrecon_api.routers.health import router as health_router


def create_app() -> FastAPI:
    """Create the HTTP app without embedding reconciliation business logic."""
    settings = get_settings()
    app = FastAPI(title="SmartRecon API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )
    app.include_router(health_router)
    return app


app = create_app()
