"""Configuration loading with ``${ENV_VAR}`` interpolation.

The privacy guarantee is the product: the only outbound calls OpenBasin makes
are to the user's configured LLM and action targets. Configuration is therefore
the single place that decides where data may go — keep it explicit and local.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

_ENV_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def _interpolate(value: Any) -> Any:
    """Recursively replace ``${VAR}`` with ``os.environ[VAR]``.

    An undefined variable is left as an empty string rather than raising, so a
    partially-configured deployment still boots and reports the gap at use time.
    """
    if isinstance(value, str):
        return _ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: _interpolate(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_interpolate(v) for v in value]
    return value


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8080
    pipelines_dir: str = "pipelines"


class DBConfig(BaseModel):
    path: str = "/data/openbasin.db"


class LLMConfig(BaseModel):
    provider: str = "openai"
    model: str = "gpt-4o-mini"
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0.0
    timeout_seconds: float = 60.0


class DeviceConfig(BaseModel):
    device_id: str
    token: str
    aes_key: str = Field(..., description="base64-encoded 32-byte key.")


class Config(BaseModel):
    server: ServerConfig = Field(default_factory=ServerConfig)
    db: DBConfig = Field(default_factory=DBConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    devices: list[DeviceConfig] = Field(default_factory=list)
    secrets: dict[str, str] = Field(default_factory=dict)

    def device(self, device_id: str) -> DeviceConfig | None:
        return next((d for d in self.devices if d.device_id == device_id), None)

    def device_by_token(self, token: str) -> DeviceConfig | None:
        return next((d for d in self.devices if d.token == token and token), None)


def load_config(path: str | os.PathLike[str] = "config.yaml") -> Config:
    """Load and validate ``config.yaml``, interpolating environment variables."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config not found at {p}. Copy config.example.yaml to config.yaml and edit it."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return Config.model_validate(_interpolate(raw))
