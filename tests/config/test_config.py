from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from tribe import config


def _config_file() -> Path:
    return Path(os.environ["TRIBE_CONFIG_DIR"]) / "credentials.json"


def test_load_missing_config_returns_empty():
    assert config.load_config() == {}


def test_save_then_load_roundtrip():
    config.save_config({"provider": "groq", "keys": {"groq": "gsk_1"}})
    loaded = config.load_config()
    assert loaded["provider"] == "groq"
    assert loaded["keys"]["groq"] == "gsk_1"


def test_saved_file_is_owner_only():
    config.save_config({"provider": "groq"})
    mode = stat.S_IMODE(_config_file().stat().st_mode)
    assert mode == 0o600


def test_corrupt_config_is_ignored():
    path = _config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not valid json", encoding="utf-8")
    assert config.load_config() == {}


def test_remember_credentials_persists_key_provider_model():
    config.remember_credentials("groq", "llama-3.3-70b-versatile", "gsk_secret")
    loaded = config.load_config()
    assert loaded["provider"] == "groq"
    assert loaded["model"] == "llama-3.3-70b-versatile"
    assert loaded["keys"]["groq"] == "gsk_secret"


def test_remember_without_key_keeps_existing_key():
    config.remember_credentials("groq", "model-a", "gsk_secret")
    config.remember_credentials("groq", "model-b")  # no key this time
    loaded = config.load_config()
    assert loaded["keys"]["groq"] == "gsk_secret"
    assert loaded["model"] == "model-b"


def test_apply_stored_keys_sets_env():
    config.save_config({"keys": {"groq": "gsk_env"}})
    config.apply_stored_keys()
    assert os.environ["GROQ_API_KEY"] == "gsk_env"


def test_apply_stored_keys_does_not_override_existing_env():
    os.environ["GROQ_API_KEY"] = "from-shell"
    config.save_config({"keys": {"groq": "from-file"}})
    config.apply_stored_keys()
    assert os.environ["GROQ_API_KEY"] == "from-shell"


def test_resolve_startup_uses_stored_provider_and_model():
    config.save_config(
        {"provider": "groq", "model": "llama-x", "keys": {"groq": "gsk_r"}}
    )
    provider, model = config.resolve_startup(None, None)
    assert provider == "groq"
    assert model == "llama-x"
    assert os.environ["GROQ_API_KEY"] == "gsk_r"


def test_resolve_startup_flag_overrides_stored_provider():
    config.save_config({"provider": "groq", "model": "llama-x"})
    provider, model = config.resolve_startup("openai", None)
    assert provider == "openai"
    # stored model belongs to groq, so it is not carried onto openai
    assert model is None


def test_resolve_startup_keeps_stored_model_when_provider_matches():
    config.save_config({"provider": "groq", "model": "llama-x"})
    provider, model = config.resolve_startup("groq", None)
    assert (provider, model) == ("groq", "llama-x")


def test_resolve_startup_explicit_model_wins():
    config.save_config({"provider": "groq", "model": "llama-x"})
    _, model = config.resolve_startup("groq", "explicit-model")
    assert model == "explicit-model"
