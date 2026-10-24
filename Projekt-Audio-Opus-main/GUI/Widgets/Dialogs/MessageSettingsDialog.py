import os
import json
from PySide6 import QtWidgets, QtCore, QtGui

from core import database_controller

# Sciezka bezwzgledna wspolna z reszta aplikacji. Wczesniej "Databases"
# bylo liczone od katalogu uruchomienia, wiec program czytal i zapisywal
# konfiguracje w przypadkowym miejscu.
DB_DIR = database_controller.FOLDER
os.makedirs(DB_DIR, exist_ok=True)
MSG_CONFIG_FILE = os.path.join(DB_DIR, "msg_config.json")

DEFAULT_SUBJECT = "Zbiorczy raport rozliczeniowy Audio Opus"
DEFAULT_BODY = "Dzień dobry,\n\nW załączniku znajduje się aktualny raport rozliczeniowy wygenerowany przez system Audio Opus."
DEFAULT_FOOTER = "Pozdrawiamy,\nZespół Audio Opus"


class MessageSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Ustawienia treści wiadomości")
        self.setMinimumSize(650, 480)
        self.resize(650, 480)

        main_layout = QtWidgets.QVBoxLayout(self)

        msg_group = QtWidgets.QGroupBox("Szablon wiadomości")
        msg_layout = QtWidgets.QFormLayout()

        self.subject_input = QtWidgets.QLineEdit()
        self.body_input = QtWidgets.QTextEdit()
        self.body_input.setMinimumHeight(120)

        self.footer_input = QtWidgets.QTextEdit()
        self.footer_input.setMinimumHeight(70)
        self.footer_input.setPlaceholderText("np. Pozdrawiamy,\nZespół Audio Opus")

        msg_layout.addRow("Temat maila:", self.subject_input)
        msg_layout.addRow("Treść maila:", self.body_input)
        msg_layout.addRow("Stopka maila:", self.footer_input)
        msg_group.setLayout(msg_layout)

        main_layout.addWidget(msg_group)

        self.button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.save_settings)
        self.button_box.rejected.connect(self.reject)

        main_layout.addWidget(self.button_box)

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.enter_shortcut.activated.connect(self._handle_enter_pressed)

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(self._handle_enter_pressed)

        self.load_settings()

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        if self.body_input.hasFocus() or self.footer_input.hasFocus():
            return
        self.save_settings()

    def load_settings(self):
        if os.path.exists(MSG_CONFIG_FILE):
            try:
                with open(MSG_CONFIG_FILE, "r", encoding="utf-8") as f:
                    msg_config = json.load(f)
                    self.subject_input.setText(msg_config.get("EMAIL_SUBJECT", DEFAULT_SUBJECT))
                    self.body_input.setPlainText(msg_config.get("EMAIL_BODY", DEFAULT_BODY))
                    self.footer_input.setPlainText(msg_config.get("EMAIL_FOOTER", DEFAULT_FOOTER))
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Błąd", f"Nie udało się wczytać ustawień wiadomości: {e}")
        else:
            self.subject_input.setText(DEFAULT_SUBJECT)
            self.body_input.setPlainText(DEFAULT_BODY)
            self.footer_input.setPlainText(DEFAULT_FOOTER)

    def save_settings(self):
        msg_config = {
            "EMAIL_SUBJECT": self.subject_input.text().strip(),
            "EMAIL_BODY": self.body_input.toPlainText().strip(),
            "EMAIL_FOOTER": self.footer_input.toPlainText().strip()
        }

        try:
            with open(MSG_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(msg_config, f, indent=4, ensure_ascii=False)

            QtWidgets.QMessageBox.information(self, "Sukces", "Ustawienia wiadomości zostały pomyślnie zapisane!")
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Błąd", f"Wystąpił błąd podczas zapisywania: {e}")