"""
epoch/backend/config.py
-----------------------
Single place that loads config/config.yaml.

config.yaml is gitignored (it may hold API keys). setup_env.py copies
config.yaml.example to config.yaml. The example is the single source of
defaults: config.yaml is deep-merged over it, so a key added to the example
later (e.g. a new routing constant) also reaches an older config.yaml, and a
fresh clone without config.yaml still starts.
"""

import os
from functools import lru_cache

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "config.yaml")
EXAMPLE_PATH = os.path.join(ROOT, "config", "config.yaml.example")


def config_path() -> str:
    return CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH


def _read(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _deep_merge(base: dict, override: dict) -> dict:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


@lru_cache(maxsize=1)
def load_config() -> dict:
    defaults = _read(EXAMPLE_PATH)
    if config_path() == EXAMPLE_PATH:
        return defaults
    return _deep_merge(defaults, _read(CONFIG_PATH))


def api_key(name: str) -> str | None:
    """Return a configured API key, or None if unset or still the example placeholder."""
    value = (load_config().get("apis") or {}).get(name)
    if not value or not isinstance(value, str):
        return None
    if value.strip().upper().startswith("YOUR_"):
        return None
    return value.strip()
