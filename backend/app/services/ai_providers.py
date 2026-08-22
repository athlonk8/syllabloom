from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import environment_value
from ..models import AppSetting
from ..schemas import AIProviderConfigUpdate

CODEX_CLI = "codex_cli"
OPENAI_COMPATIBLE = "openai_compatible"
DISABLED = "disabled"
SUPPORTED_PROVIDERS = {CODEX_CLI, OPENAI_COMPATIBLE, DISABLED}


class AIProviderConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class AIProviderConfig:
    provider: str
    base_url: str | None
    model: str | None
    api_key: str | None

    @property
    def is_network_provider(self) -> bool:
        return self.provider == OPENAI_COMPATIBLE


_ENVIRONMENT_KEYS = {
    "AI_PROVIDER": "AI_PROVIDER",
    "AI_BASE_URL": "AI_BASE_URL",
    "AI_MODEL": "AI_MODEL",
    "AI_API_KEY": "AI_API_KEY",
}


def _setting_value(db: Session, key: str, default: str | None = None) -> str | None:
    setting = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if setting is not None:
        return setting.value
    return environment_value(_ENVIRONMENT_KEYS[key], default)


def _upsert_setting(db: Session, key: str, value: str, *, is_secret: bool = False) -> None:
    setting = db.scalar(select(AppSetting).where(AppSetting.key == key))
    if setting is None:
        db.add(AppSetting(key=key, value=value, is_secret=is_secret))
        return
    setting.value = value
    setting.is_secret = is_secret


def normalize_openai_base_url(value: str) -> str:
    candidate = value.strip().rstrip("/")
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise AIProviderConfigurationError("OpenAI-compatible base URL must be a complete http(s) URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIProviderConfigurationError("Use a plain OpenAI-compatible base URL without credentials, query parameters, or fragments.")
    return candidate


def get_ai_provider_config(db: Session) -> AIProviderConfig:
    provider = (_setting_value(db, "AI_PROVIDER", CODEX_CLI) or CODEX_CLI).strip().lower()
    if provider not in SUPPORTED_PROVIDERS:
        raise AIProviderConfigurationError(
            "The local AI provider setting is invalid. Open Settings and choose Codex CLI, OpenAI-compatible, or Disabled."
        )
    base_url = (_setting_value(db, "AI_BASE_URL") or "").strip() or None
    model = (_setting_value(db, "AI_MODEL") or "").strip() or None
    api_key = _setting_value(db, "AI_API_KEY") or None
    if provider == OPENAI_COMPATIBLE:
        if not base_url or not model:
            raise AIProviderConfigurationError(
                "OpenAI-compatible feedback needs both a base URL and a model. Configure them in Settings first."
            )
        base_url = normalize_openai_base_url(base_url)
    return AIProviderConfig(provider=provider, base_url=base_url, model=model, api_key=api_key)


def save_ai_provider_config(db: Session, payload: AIProviderConfigUpdate) -> AIProviderConfig:
    _upsert_setting(db, "AI_PROVIDER", payload.provider)
    if payload.base_url is not None:
        _upsert_setting(db, "AI_BASE_URL", payload.base_url.strip().rstrip("/"))
    if payload.model is not None:
        _upsert_setting(db, "AI_MODEL", payload.model.strip())
    if payload.api_key is not None:
        _upsert_setting(db, "AI_API_KEY", payload.api_key.strip(), is_secret=True)
    elif payload.clear_api_key:
        _upsert_setting(db, "AI_API_KEY", "", is_secret=True)
    return get_ai_provider_config(db)


def public_ai_provider_config(db: Session) -> dict:
    config = get_ai_provider_config(db)
    return {
        "provider": config.provider,
        "base_url": config.base_url,
        "model": config.model,
        "api_key_configured": bool(config.api_key),
        "uses_network": config.is_network_provider,
    }
