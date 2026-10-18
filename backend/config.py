"""
epoch/backend/config.py
-----------------------
Single place that loads config/config.yaml.

config.yaml is gitignored (it may hold API keys). setup_env.py copies
config.yaml.example to config.yaml; if that has not happened yet, we fall back
to the example so a fresh clone still starts.
"""

import os
from functools import lru_cache

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(ROOT, "config", "config.yaml")
EXAMPLE_PATH = os.path.join(ROOT, "config", "config.yaml.example")


def config_path() -> str:
    return CONFIG_PATH if os.path.exists(CONFIG_PATH) else EXAMPLE_PATH


@lru_cache(maxsize=1)
def load_config() -> dict:
    with open(config_path(), "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def api_key(name: str) -> str | None:
    """Return a configured API key, or None if unset or still the example placeholder."""
    value = (load_config().get("apis") or {}).get(name)
    if not value or not isinstance(value, str):
        return None
    if value.strip().upper().startswith("YOUR_"):
        return None
    return value.strip()
