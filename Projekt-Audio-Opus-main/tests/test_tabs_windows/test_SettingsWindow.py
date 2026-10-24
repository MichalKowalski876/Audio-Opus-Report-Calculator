import pytest
from unittest.mock import MagicMock, patch

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from GUI.Widgets.Settings.AppearanceSettings import AppearanceSettings
from GUI.Widgets.Settings.ShortcutManager import ShortcutManager
from GUI.Window.SettingsWindow import SettingsWindow


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def mock_theme_manager():
    """ThemeManager pamietajacy ostatnio ustawiony akcent - podglad koloru
    czyta go z powrotem przez get_current_accent()."""
    with patch(
        "GUI.Widgets.Settings.AppearanceSettings.ThemeManager"
    ) as mock:
        state = {"theme": "dark", "accent": "#ff0000"}

        def apply_theme(app, theme=None, accent=None):
            if theme is not None:
                state["theme"] = theme
            if accent is not None:
                state["accent"] = accent

        mock.apply_theme.side_effect = apply_theme
        mock.get_current_theme.side_effect = lambda: state["theme"]
        mock.get_current_accent.side_effect = lambda: state["accent"]
        yield mock


@pytest.fixture
def appearance(mock_theme_manager):
    widget = AppearanceSettings()
    yield widget
    widget.close()


def test_appearance_initialization(appearance):
    assert appearance.dark_theme_checkbox.isChecked()
    assert appearance.dark_theme_checkbox.text() == "Ciemny motyw"
    assert "#ff0000" in appearance.accent_preview.styleSheet()


def test_on_theme_toggled(appearance, mock_theme_manager, qapp):
    appearance.on_theme_toggled(False)

    mock_theme_manager.apply_theme.assert_called_with(qapp, "light")
    assert appearance.dark_theme_checkbox.text() == "Jasny motyw"

    appearance.on_theme_toggled(True)

    mock_theme_manager.apply_theme.assert_called_with(qapp, "dark")
    assert appearance.dark_theme_checkbox.text() == "Ciemny motyw"


@patch("PySide6.QtWidgets.QColorDialog.getColor")
def test_on_accent_clicked_valid_color(
    mock_get_color,
    appearance,
    mock_theme_manager,
    qapp,
):
    color = MagicMock()
    color.isValid.return_value = True
    color.name.return_value = "#2e7dff"
    mock_get_color.return_value = color

    appearance.on_accent_clicked()

    mock_theme_manager.apply_theme.assert_called_with(qapp, accent="#2e7dff")
    assert "#2e7dff" in appearance.accent_preview.styleSheet()


@patch("PySide6.QtWidgets.QColorDialog.getColor")
def test_on_accent_clicked_invalid_color(
    mock_get_color,
    appearance,
    mock_theme_manager,
):
    color = MagicMock()
    color.isValid.return_value = False
    mock_get_color.return_value = color

    appearance.on_accent_clicked()

    mock_theme_manager.apply_theme.assert_not_called()


@patch("PySide6.QtWidgets.QMessageBox.warning")
@patch("PySide6.QtWidgets.QColorDialog.getColor")
def test_on_accent_clicked_rejects_white_in_dark_theme(
    mock_get_color,
    mock_warning,
    appearance,
    mock_theme_manager,
):
    color = MagicMock()
    color.isValid.return_value = True
    color.name.return_value = "#ffffff"
    mock_get_color.return_value = color

    appearance.on_accent_clicked()

    mock_theme_manager.apply_theme.assert_not_called()
    mock_warning.assert_called_once()
    assert "#ff0000" in appearance.accent_preview.styleSheet()


@patch("PySide6.QtWidgets.QMessageBox.warning")
@patch("PySide6.QtWidgets.QColorDialog.getColor")
def test_on_accent_clicked_rejects_black_in_light_theme(
    mock_get_color,
    mock_warning,
    appearance,
    mock_theme_manager,
    qapp,
):
    appearance.on_theme_toggled(False)
    mock_theme_manager.apply_theme.reset_mock()
    color = MagicMock()
    color.isValid.return_value = True
    color.name.return_value = "#000000"
    mock_get_color.return_value = color

    appearance.on_accent_clicked()

    mock_theme_manager.apply_theme.assert_not_called()
    mock_warning.assert_called_once()


@pytest.fixture
def settings_window(mock_theme_manager):
    manager = ShortcutManager(QSettings("AudioOpusTest", "SettingsWindowTest"))
    window = SettingsWindow(manager)
    yield window
    window.close()


def test_settings_window_sections(settings_window):
    assert settings_window.stack.count() == 5
    assert len(settings_window.section_buttons) == 5
    assert settings_window.stack.currentIndex() == 0
    assert settings_window.section_buttons[0].isChecked()


def test_change_section(settings_window):
    settings_window.change_section(2)

    assert settings_window.stack.currentIndex() == 2
    assert settings_window.section_buttons[2].isChecked()
    assert not settings_window.section_buttons[0].isChecked()


def test_section_button_switches_page(settings_window):
    last_index = len(settings_window.section_buttons) - 1
    settings_window.section_buttons[last_index].click()

    assert settings_window.stack.currentIndex() == last_index
    assert settings_window.stack.currentWidget() is settings_window.key_bind_tab


def test_data_section_index_matches_data_tab(settings_window):
    assert SettingsWindow.DATA_SECTION_INDEX == settings_window.data_section_index
    assert (
        settings_window.stack.widget(SettingsWindow.DATA_SECTION_INDEX)
        is settings_window.data_tab
    )


def test_initial_section_opens_data_tab(mock_theme_manager):
    manager = ShortcutManager(QSettings("AudioOpusTest", "SettingsWindowTest"))
    window = SettingsWindow(
        manager, initial_section=SettingsWindow.DATA_SECTION_INDEX
    )

    assert window.stack.currentWidget() is window.data_tab
    assert window.section_buttons[SettingsWindow.DATA_SECTION_INDEX].isChecked()

    window.close()
