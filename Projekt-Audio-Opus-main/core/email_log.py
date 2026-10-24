import json
import logging
from datetime import datetime
from pathlib import Path

from core import paths

LOG_FILE = Path(paths.data_path("Databases", "email_log.json"))


def log_send(recipients, pdf_name: str, status: str, error_message: str | None = None) -> None:
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "recipients": recipients,
        "pdf_name": pdf_name,
        "status": status,
        "error_message": error_message,
    }

    logs = []
    if LOG_FILE.exists():
        try:
            with LOG_FILE.open("r", encoding="utf-8") as f:
                logs = json.load(f)
        except json.JSONDecodeError:
            logging.warning("email_log.json uszkodzony — nadpisuję nową listą.")
            logs = []

    logs.append(entry)

    with LOG_FILE.open("w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def get_all_logs() -> list:
    if not LOG_FILE.exists():
        return []
    with LOG_FILE.open("r", encoding="utf-8") as f:
        return json.load(f)