import json
from datetime import datetime, timedelta
from pathlib import Path

from core import paths


CONFIG_FILE = Path(paths.data_path("Databases", "backup_reminder_config.json"))

MAX_BACKUP_AGE = timedelta(days=28)

DEFAULT_CONFIG = {
    "last_backup_at": None
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


def record_backup():
    """Wywoływane po udanym eksporcie kopii bazy (Ustawienia -> Dane)."""

    config = load()
    config["last_backup_at"] = datetime.now().isoformat()
    save(config)


def should_remind():
    """True, gdy ostatnia kopia bazy jest starsza niż MAX_BACKUP_AGE
    (albo nigdy jej nie zrobiono)."""

    last_backup_at = load().get("last_backup_at")

    if not last_backup_at:
        return True

    try:
        last_backup_date = datetime.fromisoformat(last_backup_at)
    except ValueError:
        return True

    return datetime.now() - last_backup_date > MAX_BACKUP_AGE
