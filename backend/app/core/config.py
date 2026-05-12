"""
Application settings loaded from .env file.
"""

from pathlib import Path
from typing import List

from pydantic_settings import BaseSettings


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _resolve_path(raw_path: str) -> str:
    path = Path(raw_path)
    if path.is_absolute():
        return str(path)
    return str((BACKEND_DIR / path).resolve())


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./app.db"
    DATA_DIR: str = "./data"
    MODELS_DIR: str = "./models_registry"
    GOOGLE_APPLICATION_CREDENTIALS: str = "./service_account.json"
    GDRIVE_FOLDER_ID: str = ""
    CORS_ORIGINS: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",")]

    @property
    def resolved_database_url(self) -> str:
        prefix = "sqlite:///"
        if self.DATABASE_URL.startswith(prefix):
            suffix = self.DATABASE_URL[len(prefix):]
            if suffix.startswith("./"):
                return f"{prefix}{_resolve_path(suffix)}"
        return self.DATABASE_URL

    @property
    def data_dir_path(self) -> str:
        return _resolve_path(self.DATA_DIR)

    @property
    def models_dir_path(self) -> str:
        return _resolve_path(self.MODELS_DIR)

    @property
    def credentials_path(self) -> str:
        return _resolve_path(self.GOOGLE_APPLICATION_CREDENTIALS)

    class Config:
        env_file = str(BACKEND_DIR / ".env")
        env_file_encoding = "utf-8"


settings = Settings()
