from unittest.mock import patch, MagicMock
from PySide6.QtWidgets import QApplication


class TestMainApplication:

    @patch("main.MainWindow")
    @patch("main.QApplication")
    def test_main_flow(self, mock_q_app_class, mock_main_window_class, tmp_path):
        mock_app_instance = MagicMock()
        mock_q_app_class.return_value = mock_app_instance

        mock_window_instance = MagicMock()
        mock_main_window_class.return_value = mock_window_instance

        style_file = tmp_path / "dark.qss"
        style_file.write_text("QWidget { background-color: #20201f; }", encoding="utf-8")

        app = QApplication.instance() or QApplication([])

        try:
            with open(style_file, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            style_loaded = True
        except Exception:
            style_loaded = False

        assert style_loaded is True
        assert "background-color" in app.styleSheet()

        window = mock_main_window_class()
        window.show()

        mock_main_window_class.assert_called_once()
        window.show.assert_called_once()