from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from core import backup_reminder
from core import database_controller
from GUI.Widgets.Settings.DataSettings import DataSettings


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_folder(tmp_path, monkeypatch):
    monkeypatch.setattr(database_controller, "FOLDER", str(tmp_path))
    monkeypatch.setattr(
        backup_reminder, "CONFIG_FILE", tmp_path / "backup_reminder_config.json"
    )


@pytest.fixture
def widget():
    w = DataSettings()
    yield w
    w.close()


def _db_path(tmp_path):
    return tmp_path / database_controller.DATABASE_FILENAME


@patch("PySide6.QtWidgets.QMessageBox.warning")
def test_export_without_database_warns(mock_warning, widget):
    widget.export_database()

    mock_warning.assert_called_once()


@patch("PySide6.QtWidgets.QMessageBox.information")
def test_export_copies_file(mock_info, widget, tmp_path):
    db_file = _db_path(tmp_path)
    db_file.write_bytes(b"SQLite format 3\x00fake-db-bytes")

    target = tmp_path / "backup.sqlite"

    with patch(
        "PySide6.QtWidgets.QFileDialog.getSaveFileName",
        return_value=(str(target), "Baza SQLite (*.sqlite)"),
    ):
        widget.export_database()

    assert target.read_bytes() == db_file.read_bytes()
    mock_info.assert_called_once()
    assert backup_reminder.should_remind() is False


@patch("PySide6.QtWidgets.QMessageBox.warning")
def test_import_rejects_non_sqlite_file(mock_warning, widget, tmp_path):
    bogus = tmp_path / "not_a_db.sqlite"
    bogus.write_text("hello")

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(bogus), "Baza SQLite (*.sqlite)"),
    ):
        widget.import_database()

    mock_warning.assert_called_once()
    assert not _db_path(tmp_path).exists()


@patch("GUI.Widgets.Settings.DataSettings.confirm_yes_no", return_value=False)
def test_import_cancelled_by_user_does_not_overwrite(mock_confirm, widget, tmp_path):
    source = tmp_path / "incoming.sqlite"
    source.write_bytes(b"SQLite format 3\x00new-data")

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(source), "Baza SQLite (*.sqlite)"),
    ):
        widget.import_database()

    assert not _db_path(tmp_path).exists()


@patch("GUI.Widgets.Settings.DataSettings.confirm_yes_no", return_value=True)
@patch("PySide6.QtWidgets.QMessageBox.information")
def test_import_confirmed_overwrites_database(mock_info, mock_confirm, widget, tmp_path):
    _db_path(tmp_path).write_bytes(b"SQLite format 3\x00old-data")

    source = tmp_path / "incoming.sqlite"
    source.write_bytes(b"SQLite format 3\x00new-data")

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(source), "Baza SQLite (*.sqlite)"),
    ):
        widget.import_database()

    assert _db_path(tmp_path).read_bytes() == source.read_bytes()
    mock_info.assert_called_once()


@patch("GUI.Widgets.Settings.DataSettings.confirm_yes_no", return_value=True)
@patch("PySide6.QtWidgets.QMessageBox.information")
def test_import_emits_data_imported_for_tab_refresh(mock_info, mock_confirm, widget, tmp_path):
    source = tmp_path / "incoming.sqlite"
    source.write_bytes(b"SQLite format 3\x00new-data")

    fired = []
    widget.data_imported.connect(lambda: fired.append(True))

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(source), "Baza SQLite (*.sqlite)"),
    ):
        widget.import_database()

    assert fired == [True]


@patch("PySide6.QtWidgets.QMessageBox.information")
def test_import_of_the_current_database_is_a_no_op(mock_info, widget, tmp_path):
    current = _db_path(tmp_path)
    current.write_bytes(b"SQLite format 3\x00live-data")

    fired = []
    widget.data_imported.connect(lambda: fired.append(True))

    with patch(
        "PySide6.QtWidgets.QFileDialog.getOpenFileName",
        return_value=(str(current), "Baza SQLite (*.sqlite)"),
    ), patch("GUI.Widgets.Settings.DataSettings.confirm_yes_no", return_value=True):
        widget.import_database()

    assert current.read_bytes() == b"SQLite format 3\x00live-data"
    assert fired == []
    mock_info.assert_called_once()
