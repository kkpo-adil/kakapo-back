from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://kakapo:kakapo@localhost:5432/kakapo"
    UPLOAD_DIR: str = "./uploads"
    MAX_UPLOAD_SIZE_MB: int = 50
    APP_ENV: str = "development"

    @property
    def upload_path(self) -> Path:
        p = Path(self.UPLOAD_DIR)
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def max_upload_bytes(self) -> int:
        return self.MAX_UPLOAD_SIZE_MB * 1024 * 1024

    class Config:
        env_file = ".env"


settings = Settings()
