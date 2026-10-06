"""Application configuration via environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """App settings loaded from environment variables."""

    database_url: str = "postgresql://clauseguard:clauseguard@localhost:5432/clauseguard"
    model_path: str = "ml/artifacts/legal_bert"
    sbert_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_file_size_mb: int = 10
    log_level: str = "INFO"
    metrics_path: str = "ml/artifacts/metrics.json"
    label_map_path: str = "ml/artifacts/label_map.json"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
