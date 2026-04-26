"""Application configuration.

Loads settings from environment variables and .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Lumen application settings."""

    app_name: str = "Lumen"
    app_env: str = "development"
    data_dir: str = "./data"
    processed_dataset_path: str = "./data/processed/lumen_cells.gpkg"

    # API Keys (for future use when real ingestion is implemented)
    eia_api_key: str = ""
    electricity_maps_api_key: str = ""
    openai_api_key: str = ""
    openai_query_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    maptiler_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="",  # Allow exact env var names like EIA_API_KEY
    )


settings = Settings()
