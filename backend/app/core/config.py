from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Lumen"
    app_env: str = "development"
    data_dir: str = "./data"
    processed_dataset_path: str = "./data/processed/lumen_cells.parquet"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
