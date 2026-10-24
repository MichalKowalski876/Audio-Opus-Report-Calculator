from unittest.mock import patch

import pytest
from PySide6.QtWidgets import QApplication

from GUI.Tabs.AssistantTab import AssistantTab
from core import assistant_client


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_assistant_reports_missing_ollama():
    with patch("GUI.Tabs.AssistantTab.shutil.which", return_value=None):
        tab = AssistantTab()
        tab.check_status()

    assert "nie jest zainstalowana" in tab.status_label.text()
    assert tab.setup_button.text() == "Zainstaluj Ollama"
    assert not tab.ask_button.isEnabled()
    tab.close()


def test_assistant_prompt_loads_application_guide():
    assert "Dopasuj kolumny" in assistant_client.SYSTEM_PROMPT
    assert "Wysylka e-mail" in assistant_client.SYSTEM_PROMPT
    assert "kopie bazy" in assistant_client.SYSTEM_PROMPT


def test_assistant_can_open_download_page():
    with (
        patch("GUI.Tabs.AssistantTab.shutil.which", return_value=None),
        patch("GUI.Tabs.AssistantTab.webbrowser.open") as open_browser,
    ):
        tab = AssistantTab()
        tab.check_status()
        tab.prepare_assistant()

    open_browser.assert_called_once_with("https://ollama.com/download")
    tab.close()


def test_answer_is_not_duplicated_in_setup_status():
    with patch("GUI.Tabs.AssistantTab.shutil.which", return_value=None):
        tab = AssistantTab()

    class FakeWorker:
        operation = "ask"

    tab._worker = FakeWorker()
    tab._on_worker_finished(True, "Instrukcja odpowiedzi")

    assert tab.status_label.text() == "Odpowiedź gotowa."
    assert tab.answer_box.toPlainText() == "Instrukcja odpowiedzi"
    assert "Instrukcja" not in tab.status_label.text()
    tab.close()
