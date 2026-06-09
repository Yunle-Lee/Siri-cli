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


def get_api_config(model: str = None) -> dict:
    cfg = load_config()
    api_key = os.environ.get("FM_API_KEY", os.environ.get("OPENAI_API_KEY", cfg.get("api_key", "")))
    default_base = os.environ.get("FM_API_BASE", cfg.get("base_url", "https://api.openai.com/v1"))
    default_model = os.environ.get("FM_MODEL", cfg.get("model", "gpt-4o-mini"))

    if model == "system":
        base_url = os.environ.get("FM_SYSTEM_URL", cfg.get("system_url", default_base))
        model_name = os.environ.get("FM_SYSTEM_MODEL", cfg.get("system_model", default_model))
    elif model == "pcc":
        base_url = os.environ.get("FM_PCC_URL", cfg.get("pcc_url", default_base))
        model_name = os.environ.get("FM_PCC_MODEL", cfg.get("pcc_model", default_model))
    else:
        base_url = default_base
        model_name = default_model

    return {"base_url": base_url, "api_key": api_key, "model": model_name}
