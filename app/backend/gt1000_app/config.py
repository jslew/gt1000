from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
OPENAI_BASE_URL_ENV = "OPENAI_BASE_URL"
OPENAI_REASONING_EFFORT_ENV = "OPENAI_REASONING_EFFORT"
OPENAI_TEXT_VERBOSITY_ENV = "OPENAI_TEXT_VERBOSITY"


def config_dir() -> Path:
    return Path(os.environ.get("GT1000_APP_CONFIG_DIR", Path.home() / ".gt1000-app"))


def config_path() -> Path:
    return config_dir() / "config.json"


@dataclass
class AppConfig:
    provider: str = "ollama"
    model: str = "llama3.2"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    ollama_base_url: str = "http://127.0.0.1:11434"
    system_prompt_extra: str = ""
    openai_reasoning_effort: str = "low"
    openai_text_verbosity: str = "low"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        return cls(
            provider=str(data.get("provider", "ollama")),
            model=str(data.get("model", "llama3.2")),
            openai_api_key=data.get("openaiApiKey") or data.get("openai_api_key"),
            openai_base_url=str(data.get("openaiBaseUrl", data.get("openai_base_url", "https://api.openai.com/v1"))),
            ollama_base_url=str(data.get("ollamaBaseUrl", data.get("ollama_base_url", "http://127.0.0.1:11434"))),
            system_prompt_extra=str(data.get("systemPromptExtra", data.get("system_prompt_extra", ""))),
            openai_reasoning_effort=str(
                data.get("openaiReasoningEffort", data.get("openai_reasoning_effort", "low"))
            ),
            openai_text_verbosity=str(
                data.get("openaiTextVerbosity", data.get("openai_text_verbosity", "low"))
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "openaiApiKey": self.openai_api_key,
            "openaiBaseUrl": self.openai_base_url,
            "ollamaBaseUrl": self.ollama_base_url,
            "systemPromptExtra": self.system_prompt_extra,
            "openaiReasoningEffort": self.openai_reasoning_effort,
            "openaiTextVerbosity": self.openai_text_verbosity,
        }

    def public_dict(self) -> dict[str, Any]:
        data = self.to_dict()
        if openai_api_key_from_env():
            data["openaiApiKey"] = "***"
            data["openaiApiKeyFromEnv"] = True
        elif data.get("openaiApiKey"):
            data["openaiApiKey"] = "***"
            data["openaiApiKeyFromEnv"] = False
        else:
            data["openaiApiKeyFromEnv"] = False
        return data


def openai_api_key_from_env() -> str | None:
    value = os.environ.get(OPENAI_API_KEY_ENV, "").strip()
    return value or None


def apply_env_overrides(config: AppConfig) -> AppConfig:
    env_key = openai_api_key_from_env()
    env_base = os.environ.get(OPENAI_BASE_URL_ENV, "").strip()
    if env_key:
        config = replace(config, openai_api_key=env_key)
    if env_base:
        config = replace(config, openai_base_url=env_base)
    env_reasoning = os.environ.get(OPENAI_REASONING_EFFORT_ENV, "").strip()
    if env_reasoning:
        config = replace(config, openai_reasoning_effort=env_reasoning)
    env_verbosity = os.environ.get(OPENAI_TEXT_VERBOSITY_ENV, "").strip()
    if env_verbosity:
        config = replace(config, openai_text_verbosity=env_verbosity)
    return config


def load_config(path: Path | None = None) -> AppConfig:
    resolved = path or config_path()
    if not resolved.is_file():
        return apply_env_overrides(AppConfig())
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return apply_env_overrides(AppConfig())
    if not isinstance(data, dict):
        return apply_env_overrides(AppConfig())
    return apply_env_overrides(AppConfig.from_dict(data))


def load_config_file_only(path: Path | None = None) -> AppConfig:
    resolved = path or config_path()
    if not resolved.is_file():
        return AppConfig()
    try:
        data = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return AppConfig()
    if not isinstance(data, dict):
        return AppConfig()
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    resolved = path or config_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    existing = load_config_file_only(resolved)
    merged = apply_env_overrides(config).to_dict()
    if merged.get("openaiApiKey") == "***":
        merged["openaiApiKey"] = existing.openai_api_key
    env_key = openai_api_key_from_env()
    if env_key and merged.get("openaiApiKey") == env_key:
        merged["openaiApiKey"] = existing.openai_api_key
    resolved.write_text(json.dumps(merged, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return resolved
