import pytest
from unittest.mock import patch
from PySide6 import QtWidgets
from PySide6.QtWidgets import QApplication

from core import backup_reminder
from GUI.Window.MainWindow import MainWindow
from GUI.Window.SettingsWindow import SettingsWindow


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()

    if app is None:
        app = QApplication([])

    yield app


def _stub_tab(**methods):
    """Pusta zakladka udajaca prawdziwa - MainWindow podpina do niej skroty."""
    widget = QtWidgets.QWidget()
    for name in methods:
        setattr(widget, name, methods[name])
    return widget


@pytest.fixture
def main_window():
    with (
        patch(
            "GUI.Window.MainWindow.ClientsTab",
            return_value=_stub_tab(add_client=lambda: None)
        ),
        patch(
            "GUI.Window.MainWindow.ProductsTab",
            return_value=_stub_tab(add_product=lambda: None)
        ),
        patch(
            "GUI.Window.MainWindow.StreamingTab",
            return_value=QtWidgets.QWidget()
        ),
        patch(
            "GUI.Window.MainWindow.ReportTab",
            return_value=_stub_tab(
                on_send_clicked=lambda: None,
                open_commission_calculator=lambda: None,
            )
        ),
        patch(
            "GUI.Window.MainWindow.DebugTab",
            return_value=QtWidgets.QWidget()
        ),
        patch(
            "GUI.Window.MainWindow.AssistantTab",
            return_value=QtWidgets.QWidget()
        ),
        patch(
            "GUI.Window.MainWindow.QtCore.QTimer.singleShot",
            return_value=None,
        ),
    ):
        window = MainWindow()
        yield window
        window.close()


def test_main_window_initialization(main_window):
    assert main_window.windowTitle() == "Projekt Audio Opus"
    assert main_window.isMaximized()
    assert main_window.stack.count() == 7
    assert main_window.page_title.text() == "Start"


def test_change_page_method(main_window):
    main_window.change_page(
        main_window.products_tab,
        "Panel Produktów Test"
    )

    assert main_window.stack.currentWidget() == main_window.products_tab
    assert main_window.page_title.text() == "Panel Produktów Test"


def test_navigation_buttons_clicks(main_window):
    main_window.products_button.click()

    assert main_window.stack.currentWidget() == main_window.products_tab
    assert main_window.page_title.text() == "Panel Produktów"

    main_window.streaming_button.click()

    assert main_window.stack.currentWidget() == main_window.streaming_tab
    assert main_window.page_title.text() == "Panel Platform"

    main_window.report_button.click()

    assert main_window.stack.currentWidget() == main_window.report_tab
    assert main_window.page_title.text() == "Raporty"

    main_window.clients_button.click()

    assert main_window.stack.currentWidget() == main_window.clients_tab
    assert main_window.page_title.text() == "Panel Klientów"


def test_ui_elements_properties(main_window):
    assert main_window.panel_label.property("role") == "Title"
    assert main_window.page_title.property("role") == "Title"
    assert main_window.page_title.objectName() == "pageTitle"


def test_backup_reminder_ok_opens_data_settings(main_window, tmp_path, monkeypatch):
    monkeypatch.setattr(
        backup_reminder, "CONFIG_FILE", tmp_path / "backup_reminder_config.json"
    )

    with (
        patch("PySide6.QtWidgets.QMessageBox.exec", return_value=None),
        patch.object(main_window, "open_data_settings") as mock_open,
    ):
        main_window.maybe_show_backup_reminder()

    mock_open.assert_called_once()


def test_backup_reminder_skipped_when_backup_recent(main_window, tmp_path, monkeypatch):
    monkeypatch.setattr(
        backup_reminder, "CONFIG_FILE", tmp_path / "backup_reminder_config.json"
    )
    backup_reminder.record_backup()

    with (
        patch("PySide6.QtWidgets.QMessageBox.exec") as mock_exec,
        patch.object(main_window, "open_data_settings") as mock_open,
    ):
        main_window.maybe_show_backup_reminder()

    mock_exec.assert_not_called()
    mock_open.assert_not_called()


def test_open_data_settings_opens_settings_on_data_section(main_window):
    with patch.object(main_window, "open_settings") as mock_open_settings:
        main_window.open_data_settings()

    mock_open_settings.assert_called_once_with(
        initial_section=SettingsWindow.DATA_SECTION_INDEX
    )
