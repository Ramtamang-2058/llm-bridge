"""
Settings loader.

Reads config.json and resolves all paths relative to the project root
(wherever this file actually lives), so nothing is hardcoded and the
same config works on Windows, Linux, and macOS.
"""
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CONFIG_PATH = PROJECT_ROOT / "config.json"

# Defaults used if a key is missing from config.json.
DEFAULTS = {
    "runtime": {
        "db_path": "tasks.db",
        "auth_dir": "auth",
    }
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def _load_config() -> dict:
    if not CONFIG_PATH.exists():
        return json.loads(json.dumps(DEFAULTS))
    with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
        user_cfg = json.load(fh)
    return _deep_merge(json.loads(json.dumps(DEFAULTS)), user_cfg)


CONFIG = _load_config()


def root_path(relative: str) -> Path:
    """Resolve a config path (possibly relative) against the project root."""
    p = Path(relative)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return p


def db_path() -> Path:
    return root_path(CONFIG["runtime"]["db_path"])


def auth_dir() -> Path:
    return root_path(CONFIG["runtime"]["auth_dir"])


def state_file_for(service_key: str) -> Path:
    return auth_dir() / CONFIG["services"][service_key]["state_file"]


def services() -> dict:
    return CONFIG["services"]
