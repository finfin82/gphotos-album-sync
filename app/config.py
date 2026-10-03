from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    google_lang: str = "de"
    output_root: str = "/data/shared"
    http_port: int = 8090
    poll_seconds: int = 30
    chrome_binary: str = "/usr/bin/chromium"
    chromedriver_path: str = "/usr/bin/chromedriver"
    web_driver_wait: int = 25
    download_timeout: int = 1800
    queue_dir: str = "/queue"
    temp_dir: str = "/tmp/gp-downloads"
    profile_dir: str = "/profile"
    use_chrome_profile: bool = False
    skip_existing: bool = True
    headless: bool = True
    debug_dumps: bool = False
    wsl_inside: bool = True


def get_settings() -> Settings:
    return Settings()
