"""The FastAPI application and its dev-only instrumentation."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from data_reaper.core.config import get_settings
from data_reaper.core.di import (
    configure_dependencies,
    shutdown_infrastructure,
    startup_infrastructure,
)
from data_reaper.core.logging import setup_logging
from data_reaper.core.telemetry import API_TELEMETRY, setup_telemetry
from data_reaper.domain.exceptions import AppException
from data_reaper.presentation.api.dataset import router as dataset_router
from data_reaper.presentation.api.dataset_event import (
    router as dataset_event_router,
)
from data_reaper.presentation.api.dataset_import import (
    router as dataset_import_router,
)
from data_reaper.presentation.api.dataset_place import (
    router as dataset_place_router,
)
from data_reaper.presentation.api.exception_handler import (
    app_exception_handler,
)
from data_reaper.presentation.api.root import router as root_router
from data_reaper.presentation.api.user import router as user_router

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start infrastructure on startup and release it on shutdown."""
    await startup_infrastructure()
    yield
    await shutdown_infrastructure()


app = FastAPI(
    title=settings.app_name,
    description=settings.app_description,
    version=settings.app_version,
    docs_url=None if "production" == settings.app_env else "/docs",
    redoc_url=None if "production" == settings.app_env else "/redoc",
    openapi_url=None if "production" == settings.app_env else "/openapi.json",
    root_path=settings.root_path,
    lifespan=lifespan,
    telemetry=API_TELEMETRY,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allow_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def configure_app():
    """Build the app with its routers, handlers, and dependencies."""
    setup_logging()
    setup_metrics()
    setup_telemetry("data-reaper-api")

    configure_dependencies(app)
    app.add_exception_handler(AppException, app_exception_handler)
    for router in (
        root_router,
        user_router,
        dataset_router,
        dataset_import_router,
        dataset_place_router,
        dataset_event_router,
    ):
        app.include_router(router)

    logger.info("Data Reaper API routes configured.")


def setup_metrics():
    """Expose Prometheus metrics (development only).

    The instrumentator is a dev-only dependency, so it is imported here;
    the production image never installs it.
    """
    if "development" == settings.app_env:
        from prometheus_fastapi_instrumentator import Instrumentator

        logger.info("Prometheus instrumentation enabled (Development Mode)")
        Instrumentator().instrument(app).expose(app, endpoint="/metrics")


configure_app()
