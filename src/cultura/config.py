"""Global configuration settings for CULTURA with zero-dependency .env parsing."""

import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel, Field


def _load_env_file(filepath: str = ".env") -> None:
    """Lightweight .env file loader that does not override existing environment."""
    env_path = Path(filepath)
    if not env_path.is_file():
        return
    try:
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


_load_env_file()


class Settings(BaseModel):
    """Application settings loaded from environment variables."""

    qloo_api_key: Optional[str] = Field(
        default_factory=lambda: os.getenv("QLOO_API_KEY"),
        description="Official Qloo API Key for live endpoints",
    )
    qloo_base_url: str = Field(
        default_factory=lambda: os.getenv("QLOO_BASE_URL", "https://hackathon.api.qloo.com"),
        description="Base URL for Qloo Hackathon REST API",
    )
    qloo_use_mock: bool = Field(
        default_factory=lambda: os.getenv("QLOO_USE_MOCK", "false").lower() in ("true", "1", "yes"),
        description="Force deterministic offline mock engine fallback",
    )
    request_timeout_seconds: float = Field(
        default_factory=lambda: float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10.0")),
        description="HTTP request timeout in seconds",
    )


# Singleton settings instance
settings = Settings()
