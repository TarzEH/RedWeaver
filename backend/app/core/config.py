"""App config from env."""
import os


def get_settings() -> "Settings":
    return Settings()


class Settings:
    """Application settings from environment."""

    def __init__(self) -> None:
        self.app_version = os.environ.get("REDWEAVER_APP_VERSION", "0.1.0")
