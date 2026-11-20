"""Configuración validada desde variables de entorno para beacon-sift-bot-telegram."""

from __future__ import annotations

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración del servicio leída desde `.env` o variables de entorno."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram_bot_token: str = ""
    telegram_admin_ids: str = ""
    allow_private_subscriptions: bool = False
    telegram_disable_web_preview: bool = True

    web_api_base_url: str = "http://127.0.0.1:8000"
    web_api_timeout_seconds: float = 10.0

    reverb_ws_url: str = "ws://127.0.0.1:8080"
    reverb_app_key: str = "beacon-sift-public-key"
    reverb_channel: str = "beacon.news"

    bot_db_path: str = "data/bot.db"
    bot_timezone: str = "Europe/Madrid"
    log_level: str = "INFO"

    @field_validator("web_api_base_url", "reverb_ws_url", mode="before")
    @classmethod
    def _strip_trailing_slash(cls, value: object) -> str:
        return str(value or "").strip().rstrip("/")

    @field_validator("log_level", mode="before")
    @classmethod
    def _normalize_log_level(cls, value: object) -> str:
        return str(value or "INFO").strip().upper()

    @property
    def admin_ids(self) -> set[int]:
        """Devuelve los IDs numéricos de administradores globales configurados."""
        ids: set[int] = set()
        for chunk in self.telegram_admin_ids.split(","):
            clean = chunk.strip()
            if not clean:
                continue
            try:
                ids.add(int(clean))
            except ValueError:
                continue
        return ids
