"""
Application settings loaded from .env file.
"""

from pydantic_settings import BaseSettings
from typing import List


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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
