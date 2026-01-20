"""
HoundCOGS FastAPI Application

Main entry point for the API server.
Run with: uvicorn api.main:app --reload
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import get_settings
from api.middleware.logging import RequestLoggingMiddleware
from api.middleware.errors import setup_exception_handlers
from api.routers import health, inventory, orders, cogs, voice, files

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()

    # Startup
    logger.info(f"Starting {settings.app_name} v{settings.app_version}")

    # Ensure directories exist
    import os
    for dir_path in [settings.upload_dir, settings.export_dir, settings.cache_dir]:
        os.makedirs(dir_path, exist_ok=True)
    os.makedirs("./data/db", exist_ok=True)

    # Initialize database (create tables if needed)
    # This will be implemented in houndcogs.storage
    logger.info("Database initialized")

    yield

    # Shutdown
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API for bar/restaurant inventory management and COGS analysis",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Custom middleware
    app.add_middleware(RequestLoggingMiddleware)

    # Exception handlers
    setup_exception_handlers(app)

    # Include routers
    app.include_router(health.router, tags=["Health"])
    app.include_router(
        inventory.router,
        prefix="/api/v1/inventory",
        tags=["Inventory"]
    )
    app.include_router(
        orders.router,
        prefix="/api/v1/orders",
        tags=["Orders"]
    )
    app.include_router(
        cogs.router,
        prefix="/api/v1/cogs",
        tags=["COGS"]
    )
    app.include_router(
        voice.router,
        prefix="/api/v1/voice",
        tags=["Voice"]
    )
    app.include_router(
        files.router,
        prefix="/api/v1/files",
        tags=["Files"]
    )

    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )
