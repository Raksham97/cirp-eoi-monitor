from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    database_url: str = 'sqlite+pysqlite:///./cirp_eoi.sqlite3'
    app_username: str = 'lawyer'
    app_password: str = ''
    ibbi_base_url: str = 'https://ibbi.gov.in'
    ibbi_resolution_plans_path: str = '/resolution-plans'
    daily_pages: int = 6
    monday_deep_pages: int = 40
    request_timeout_seconds: int = 30
    request_delay_seconds: float = 0.35
    max_pdf_mb: int = 20
    fetch_pdfs: bool = True
    log_level: str = 'INFO'


@lru_cache
def get_settings() -> Settings:
    return Settings()
