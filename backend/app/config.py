"""
Application settings for the local FastAPI IoT backend (Task 28).

Loads from environment / .env, with optional fallback to the
device mqtt_config.json in the repo root for local development.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Tuple

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent
GPIO_PINS: Tuple[int, ...] = (16, 42, 47)


def _load_device_mqtt_fallback() -> dict:
    path = REPO_ROOT / "mqtt_config.json"
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


_fallback = _load_device_mqtt_fallback()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mqtt_host: str = Field(
        default=_fallback.get("host", "q92a0c11.ala.us-east-1.emqxsl.com")
    )
    mqtt_port: int = Field(default=int(_fallback.get("port", 8883)))
    mqtt_username: str = Field(default=_fallback.get("username", "esp32"))
    mqtt_password: str = Field(default=_fallback.get("password", ""))
    mqtt_client_id: str = Field(default="esaatech-backend-local")
    mqtt_keepalive: int = Field(default=int(_fallback.get("keepalive", 60)))
    mqtt_ca_file: str = Field(
        default=str(REPO_ROOT / "emqxsl-ca.crt")
    )
    device_id: str = Field(default="esaatech-44b176ce2fe4")

    @property
    def ca_path(self) -> Path:
        path = Path(self.mqtt_ca_file)
        if not path.is_absolute():
            path = (BACKEND_DIR / path).resolve()
        return path

    def command_topic(self, pin: int) -> str:
        return f"devices/{self.device_id}/gpio/{pin}/command"

    def state_topic(self, pin: int) -> str:
        return f"devices/{self.device_id}/gpio/{pin}/state"

    def proximity_topic(self) -> str:
        return f"devices/{self.device_id}/telemetry/proximity"

    def state_filter(self) -> str:
        return f"devices/{self.device_id}/gpio/+/state"


@lru_cache
def get_settings() -> Settings:
    return Settings()
