"""Configuration management for fm-clone (~/.fm-clone/)."""

import json
import os
from pathlib import Path

FM_DIR = Path.home() / ".fm-clone"
CONFIG_FILE = FM_DIR / "config"
SESSIONS_DIR = FM_DIR / "sessions"


def ensure_dirs():
    FM_DIR.mkdir(parents=True, exist_ok=True)
    SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    ensure_dirs()
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text())
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_config(cfg: dict):
    ensure_dirs()
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def get_default_model() -> str:
    cfg = load_config()
    return cfg.get("default_model", "system")


def set_default_model(model: str):
    cfg = load_config()
    cfg["default_model"] = model
    save_config(cfg)


def get_appearance() -> str:
    return load_config().get("appearance", "auto")


def set_appearance(mode: str):
    cfg = load_config()
    cfg["appearance"] = mode
    save_config(cfg)


def get_api_config() -> dict:
    return {
        "base_url": os.environ.get("FM_API_BASE", load_config().get("base_url", "https://api.openai.com/v1")),
        "api_key": os.environ.get("FM_API_KEY", os.environ.get("OPENAI_API_KEY", load_config().get("api_key", ""))),
        "model": os.environ.get("FM_MODEL", load_config().get("model", "gpt-4o-mini")),
        "system_model_name": load_config().get("system_model_name", "system"),
    }
