import json
from pathlib import Path

from core import paths


CONFIG_FILE = Path(paths.data_path("Databases", "debug_config.json"))

DEFAULT_CONFIG = {
    "enabled": False
}


def load():
    if not CONFIG_FILE.exists():
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        return {
            **DEFAULT_CONFIG,
            **data
        }
    except (json.JSONDecodeError, OSError):
        return DEFAULT_CONFIG.copy()


def save(config):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)


def is_enabled():
    return load().get("enabled", False)


def set_enabled(enabled):
    config = load()
    config["enabled"] = enabled
    save(config)
