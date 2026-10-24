import json
from datetime import datetime, timedelta

from core import backup_reminder


def test_backup_reminder_uses_persistent_data_path():
    assert backup_reminder.CONFIG_FILE.name == "backup_reminder_config.json"
    assert backup_reminder.CONFIG_FILE.parent.name == "Databases"


def test_backup_reminder_fires_when_no_backup_was_ever_made(tmp_path, monkeypatch):
    config_path = tmp_path / "backup_reminder_config.json"
    monkeypatch.setattr(backup_reminder, "CONFIG_FILE", config_path)

    assert backup_reminder.load() == backup_reminder.DEFAULT_CONFIG
    assert backup_reminder.should_remind() is True


def test_backup_reminder_stays_quiet_after_recent_backup(tmp_path, monkeypatch):
    config_path = tmp_path / "backup_reminder_config.json"
    monkeypatch.setattr(backup_reminder, "CONFIG_FILE", config_path)

    backup_reminder.record_backup()

    assert backup_reminder.should_remind() is False

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["last_backup_at"] is not None


def test_backup_reminder_fires_when_backup_older_than_28_days(tmp_path, monkeypatch):
    config_path = tmp_path / "backup_reminder_config.json"
    monkeypatch.setattr(backup_reminder, "CONFIG_FILE", config_path)

    stale_backup = datetime.now() - timedelta(days=29)
    backup_reminder.save({"last_backup_at": stale_backup.isoformat()})

    assert backup_reminder.should_remind() is True


def test_backup_reminder_stays_quiet_within_28_days(tmp_path, monkeypatch):
    config_path = tmp_path / "backup_reminder_config.json"
    monkeypatch.setattr(backup_reminder, "CONFIG_FILE", config_path)

    recent_backup = datetime.now() - timedelta(days=27)
    backup_reminder.save({"last_backup_at": recent_backup.isoformat()})

    assert backup_reminder.should_remind() is False
