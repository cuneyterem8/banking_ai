from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file="../.env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/banking_ai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    local_model_timeout_seconds: int = 30
    autogluon_preset: str = "good_quality"
    autogluon_time_limit_seconds: int = 180
    autogluon_num_bag_folds: int = 0
    autogluon_num_cpus: int = 1
    storage_dir: Path = Path("../storage")
    data_dir: Path = Path("data")
    skip_startup_training: bool = False
    force_retrain: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
