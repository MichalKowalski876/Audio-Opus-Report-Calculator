from pathlib import Path

from core import paths


def test_bootstrap_copies_database_files_and_reports_once(tmp_path, monkeypatch):
    resource_root = tmp_path / "bundle"
    data_root = tmp_path / "user"
    database_source = resource_root / "Databases"
    reports_source = resource_root / "Reports" / "Raporty Platform" / "2026"
    database_source.mkdir(parents=True)
    reports_source.mkdir(parents=True)
    (database_source / "db.sqlite").write_bytes(b"seed database")
    (database_source / "theme_config.json").write_text(
        '{"theme": "dark"}',
        encoding="utf-8",
    )
    (database_source / "email_log.py").write_text(
        "nie kopiuj kodu",
        encoding="utf-8",
    )
    report_source = reports_source / "Voices.xlsx"
    report_source.write_bytes(b"seed report")

    monkeypatch.setattr(paths, "RESOURCE_ROOT", resource_root)
    monkeypatch.setattr(paths, "DATA_ROOT", data_root)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)

    paths.bootstrap_user_data()

    database_target = data_root / "Databases" / "db.sqlite"
    report_target = data_root / "Reports" / "Raporty Platform" / "2026" / "Voices.xlsx"
    assert database_target.read_bytes() == b"seed database"
    assert report_target.read_bytes() == b"seed report"
    assert not (data_root / "Databases" / "email_log.py").exists()

    database_target.write_bytes(b"user database")
    report_target.unlink()
    paths.bootstrap_user_data()

    assert database_target.read_bytes() == b"user database"
    assert not report_target.exists()


def test_data_directory_override_has_priority(tmp_path, monkeypatch):
    override = tmp_path / "dane testowe"
    monkeypatch.setenv(paths.DATA_DIRECTORY_ENV, str(override))
    monkeypatch.setattr(paths, "is_frozen", lambda: True)

    assert paths._data_root() == override.resolve()
    assert override.is_dir()
