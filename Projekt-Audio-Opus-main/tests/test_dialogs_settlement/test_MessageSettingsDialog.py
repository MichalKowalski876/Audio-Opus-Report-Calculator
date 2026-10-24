import json
from unittest.mock import mock_open, patch

import pytest
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Dialogs.MessageSettingsDialog import (
    MessageSettingsDialog,
    DEFAULT_SUBJECT,
    DEFAULT_BODY,
    DEFAULT_FOOTER,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


@pytest.fixture
def dialog():
    with patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.os.path.exists",
        return_value=False,
    ):
        dlg = MessageSettingsDialog()

    yield dlg
    dlg.close()


def test_initialization(dialog):
    assert dialog.windowTitle() == "Ustawienia treści wiadomości"
    assert dialog.minimumSize().width() == 650
    assert dialog.minimumSize().height() == 480

    assert dialog.subject_input.text() == DEFAULT_SUBJECT
    assert dialog.body_input.toPlainText() == DEFAULT_BODY
    assert dialog.footer_input.toPlainText() == DEFAULT_FOOTER


def test_load_settings(dialog):
    config = {
        "EMAIL_SUBJECT": "Testowy temat",
        "EMAIL_BODY": "Testowa treść",
        "EMAIL_FOOTER": "Testowa stopka",
    }

    with patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.os.path.exists",
        return_value=True,
    ), patch(
        "builtins.open",
        mock_open(read_data=json.dumps(config)),
    ):
        dialog.load_settings()

    assert dialog.subject_input.text() == "Testowy temat"
    assert dialog.body_input.toPlainText() == "Testowa treść"
    assert dialog.footer_input.toPlainText() == "Testowa stopka"


def test_load_settings_missing_values(dialog):
    config = {
        "EMAIL_SUBJECT": "Tylko temat",
    }

    with patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.os.path.exists",
        return_value=True,
    ), patch(
        "builtins.open",
        mock_open(read_data=json.dumps(config)),
    ):
        dialog.load_settings()

    assert dialog.subject_input.text() == "Tylko temat"
    assert dialog.body_input.toPlainText() == DEFAULT_BODY
    assert dialog.footer_input.toPlainText() == DEFAULT_FOOTER


def test_load_settings_error(dialog):
    with patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.os.path.exists",
        return_value=True,
    ), patch(
        "builtins.open",
        side_effect=Exception("Błąd pliku"),
    ), patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.QtWidgets.QMessageBox.warning"
    ) as mock_warning:

        dialog.load_settings()

    mock_warning.assert_called_once()


def test_save_settings(dialog):
    dialog.subject_input.setText("Nowy temat")
    dialog.body_input.setPlainText("Nowa treść")
    dialog.footer_input.setPlainText("Nowa stopka")

    with patch(
        "builtins.open",
        new_callable=mock_open,
    ) as mock_file, patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.json.dump"
    ) as mock_dump, patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.QtWidgets.QMessageBox.information"
    ) as mock_info, patch.object(
        dialog,
        "accept",
    ) as mock_accept:

        dialog.save_settings()

    expected = {
        "EMAIL_SUBJECT": "Nowy temat",
        "EMAIL_BODY": "Nowa treść",
        "EMAIL_FOOTER": "Nowa stopka",
    }

    mock_file.assert_called_once()
    mock_dump.assert_called_once_with(
        expected,
        mock_file.return_value.__enter__.return_value,
        indent=4,
        ensure_ascii=False,
    )

    mock_info.assert_called_once()
    mock_accept.assert_called_once()


def test_save_settings_strips_whitespace(dialog):
    dialog.subject_input.setText("  Temat  ")
    dialog.body_input.setPlainText("  Treść  ")
    dialog.footer_input.setPlainText("  Stopka  ")

    with patch(
        "builtins.open",
        new_callable=mock_open,
    ), patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.json.dump"
    ) as mock_dump, patch(
        # Bez tego save_settings otwiera prawdziwe modalne okno i test wisi.
        "GUI.Widgets.Dialogs.MessageSettingsDialog.QtWidgets.QMessageBox.information"
    ), patch.object(
        dialog,
        "accept",
    ):

        dialog.save_settings()

    assert mock_dump.call_args.args[0] == {
        "EMAIL_SUBJECT": "Temat",
        "EMAIL_BODY": "Treść",
        "EMAIL_FOOTER": "Stopka",
    }


def test_save_settings_error(dialog):
    with patch(
        "builtins.open",
        side_effect=Exception("Błąd zapisu"),
    ), patch(
        "GUI.Widgets.Dialogs.MessageSettingsDialog.QtWidgets.QMessageBox.critical"
    ) as mock_critical, patch.object(
        dialog,
        "accept",
    ) as mock_accept:

        dialog.save_settings()

    mock_critical.assert_called_once()
    mock_accept.assert_not_called()
