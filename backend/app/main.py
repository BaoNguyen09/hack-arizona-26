"""Lumen API main application.

FastAPI application for renewable energy cost optimization.
Loads processed data on startup and exposes scoring endpoints.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.core.config import settings
from backend.app.data.processed_store import get_store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown events."""
    # Startup: load processed data
    # We are using deterministic county data, so we don't load the missing cells gpkg.
    # store = get_store()
    # try:
    #     store.load(settings.processed_dataset_path)
    #     print(f"Loaded {store.row_count} cells from {settings.processed_dataset_path}")
    # except FileNotFoundError:
    #     print(
    #         f"Warning: Processed dataset not found at {settings.processed_dataset_path}"
    #     )
    #     print("API will return errors until data is available.")
    # except ValueError as e:
    #     print(f"Warning: Processed dataset validation failed: {e}")

    yield

    # Shutdown: cleanup (if needed)
    pass


app = FastAPI(
    title=settings.app_name,
    description="Renewable energy cost optimization intelligence platform",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:5174",
        "http://localhost:5175",
        "http://localhost:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
