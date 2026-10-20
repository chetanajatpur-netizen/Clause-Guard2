"""Application configuration via environment variables."""
from pathlib import Path
from pydantic_settings import BaseSettings


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_path(path_str: str) -> str:
    """Resolve a relative path against CWD or project root."""
    p = Path(path_str)
    if p.is_absolute() or p.exists():
        return str(p.resolve())
    candidate = PROJECT_ROOT / path_str
    if candidate.exists():
        return str(candidate.resolve())
    return path_str


class Settings(BaseSettings):
    """App settings loaded from environment variables."""

    database_url: str = "sqlite:///./clauseguard.db"
    classifier_backend: str = "legal_bert"
    model_path: str = "ml/artifacts/legal_bert"
    baseline_model_path: str = "ml/artifacts/baseline_model.joblib"
    sbert_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    max_file_size_mb: int = 10
    log_level: str = "INFO"
    metrics_path: str = "ml/artifacts/metrics.json"
    label_map_path: str = "ml/artifacts/label_map.json"
    cors_origins: str = "*"
    device: str = "cpu"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "protected_namespaces": ("settings_",),
    }

    def model_post_init(self, __context: object) -> None:
        """Resolve artifact paths to absolute locations if needed."""
        self.model_path = _resolve_path(self.model_path)
        self.baseline_model_path = _resolve_path(self.baseline_model_path)
        self.metrics_path = _resolve_path(self.metrics_path)
        self.label_map_path = _resolve_path(self.label_map_path)


settings = Settings()

