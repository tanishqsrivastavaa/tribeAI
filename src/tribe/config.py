from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def config_dir() -> Path:
    override = os.environ.get("TRIBE_CONFIG_DIR")
    if override:
        return Path(override)
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "tribe"


def _config_path() -> Path:
    return config_dir() / "credentials.json"


def load_config() -> dict[str, Any]:
    try:
        data = json.loads(_config_path().read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def save_config(config: dict[str, Any]) -> None:
    path = _config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def apply_stored_keys(config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Populate provider key env vars from stored keys without overriding real env."""
    from .models import PROVIDERS

    config = load_config() if config is None else config
    keys = config.get("keys")
    if isinstance(keys, dict):
        for provider, key in keys.items():
            spec = PROVIDERS.get(provider)
            if spec and spec.api_key_env and key and not os.environ.get(spec.api_key_env):
                os.environ[spec.api_key_env] = key
    return config


def resolve_startup(
    provider: str | None, model: str | None
) -> tuple[str | None, str | None]:
    """Load stored keys into env and fill provider/model from the saved config."""
    config = apply_stored_keys()
    provider = provider or config.get("provider")
    if model is None and provider == config.get("provider"):
        model = config.get("model")
    return provider, model


def remember_credentials(
    provider: str, model: str | None = None, key: str | None = None
) -> None:
    config = load_config()
    if key:
        keys = config.get("keys")
        if not isinstance(keys, dict):
            keys = {}
        keys[provider] = key
        config["keys"] = keys
    config["provider"] = provider
    if model:
        config["model"] = model
    save_config(config)
