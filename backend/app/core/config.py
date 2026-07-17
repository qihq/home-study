from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='APP_', extra='ignore')

    data_dir: Path = Path('/data')
    database_url: str = 'sqlite:////data/app.db'
    environment: str = 'development'
    frontend_dir: Path = Path('/app/frontend-dist')
    mimo_api_key: str | None = None
    mimo_api_base_url: str | None = 'https://api.xiaomimimo.com/v1'
    mimo_tts_model: str | None = 'mimo-v2.5-tts'
    mimo_tts_voice: str | None = 'Chloe'
    mimo_tts_speed: float = 1.0

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / 'uploads'

    @property
    def videos_dir(self) -> Path:
        return self.data_dir / 'videos'

    @property
    def tts_dir(self) -> Path:
        return self.data_dir / 'tts'

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / 'backups'

    def ensure_directories(self) -> None:
        for path in (self.data_dir, self.uploads_dir, self.videos_dir, self.tts_dir, self.backups_dir):
            path.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
