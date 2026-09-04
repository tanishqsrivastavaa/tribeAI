from __future__ import annotations

import os

import pytest

from tribe.models import PROVIDERS

_PROVIDER_ENV = [p.api_key_env for p in PROVIDERS.values() if p.api_key_env]


@pytest.fixture(autouse=True)
def isolate_tribe_env(tmp_path):
    """Give each test its own config dir and a clean set of provider keys."""
    snapshot = dict(os.environ)
    os.environ["TRIBE_CONFIG_DIR"] = str(tmp_path / "tribe-config")
    for name in _PROVIDER_ENV:
        os.environ.pop(name, None)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(snapshot)
