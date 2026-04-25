"""Lumen API main application.

FastAPI application for renewable energy cost optimization.
Loads processed data on startup and exposes scoring endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.app.api.routes import router
from backend.app.core.config import settings
from backend.app.data.processed_store import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: load processed data
    store = get_store()
    try:
        store.load(settings.processed_dataset_path)
        print(f"Loaded {store.row_count} cells from {settings.processed_dataset_path}")
    except FileNotFoundError:
        print(
            f"Warning: Processed dataset not found at {settings.processed_dataset_path}"
        )
        print("API will return errors until data is available.")
    except ValueError as e:
        print(f"Warning: Processed dataset validation failed: {e}")

    yield

    # Shutdown: cleanup (if needed)
    pass


app = FastAPI(
    title=settings.app_name,
    description="Renewable energy cost optimization intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)
