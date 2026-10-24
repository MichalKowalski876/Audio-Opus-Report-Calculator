import os
import json
import keyring
from PySide6 import QtWidgets, QtCore, QtGui

from core import database_controller
from GUI.Widgets.Workers.SMTPTestWorker import SMTPTestWorker

DB_DIR = database_controller.FOLDER
os.makedirs(DB_DIR, exist_ok=True)
SMTP_CONFIG_FILE = os.path.join(DB_DIR, "smtp_config.json")
KEYRING_SERVICE = "Audio Opus SMTP"


class SMTPSettings(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)

        self._test_worker = None

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        title_label = QtWidgets.QLabel("Ustawienia SMTP")
        title_label.setProperty("role", "Title")
        main_layout.addWidget(title_label)

        smtp_group = QtWidgets.QGroupBox("Ustawienia serwera SMTP")
        smtp_layout = QtWidgets.QFormLayout()

        self.server_input = QtWidgets.QLineEdit()
        self.port_input = QtWidgets.QLineEdit()
        self.sender_email_input = QtWidgets.QLineEdit()
        self.sender_password_input = QtWidgets.QLineEdit()
        self.sender_password_input.setEchoMode(
            QtWidgets.QLineEdit.EchoMode.Password
        )

        smtp_layout.addRow("Serwer SMTP:", self.server_input)
        smtp_layout.addRow("Port SMTP:", self.port_input)
        smtp_layout.addRow("Twój E-mail:", self.sender_email_input)
        smtp_layout.addRow("Hasło (App Password):", self.sender_password_input)

        self.test_button = QtWidgets.QPushButton("Testuj połączenie")
        self.test_button.clicked.connect(self.test_connection)
        smtp_layout.addRow("", self.test_button)

        self.test_status_label = QtWidgets.QLabel("")
        self.test_status_label.setWordWrap(True)
        smtp_layout.addRow("", self.test_status_label)

        smtp_group.setLayout(smtp_layout)
        main_layout.addWidget(smtp_group)

        save_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Zapisz ustawienia")
        self.save_button.clicked.connect(self.save_settings)
        save_layout.addWidget(self.save_button)
        save_layout.addStretch()
        main_layout.addLayout(save_layout)

        main_layout.addStretch()

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.enter_shortcut.activated.connect(self.save_settings)

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(self.save_settings)

        self.load_settings()

    def _set_status_role(self, role: str):
        self.test_status_label.setProperty("role", role)
        self.test_status_label.style().unpolish(self.test_status_label)
        self.test_status_label.style().polish(self.test_status_label)

    def load_settings(self):
        if os.path.exists(SMTP_CONFIG_FILE):
            try:
                with open(SMTP_CONFIG_FILE, "r", encoding="utf-8") as f:
                    smtp_config = json.load(f)
                    self.server_input.setText(
                        smtp_config.get("SMTP_SERVER", "smtp.gmail.com")
                    )
                    self.port_input.setText(
                        str(smtp_config.get("SMTP_PORT", 465))
                    )
                    self.sender_email_input.setText(
                        smtp_config.get("SENDER_EMAIL", "")
                    )
                    sender_email = smtp_config.get("SENDER_EMAIL", "")
                    password = keyring.get_password(KEYRING_SERVICE, sender_email)
                    legacy_password = smtp_config.get("SENDER_PASSWORD")
                    if not password and legacy_password:
                        keyring.set_password(
                            KEYRING_SERVICE, sender_email, legacy_password
                        )
                        password = legacy_password
                        smtp_config.pop("SENDER_PASSWORD", None)
                        with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as config_file:
                            json.dump(smtp_config, config_file, indent=4, ensure_ascii=False)
                    self.sender_password_input.setText(password or "")
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, "Błąd", f"Nie udało się wczytać ustawień SMTP: {e}"
                )
        else:
            self.server_input.setText("smtp.gmail.com")
            self.port_input.setText("465")

    def test_connection(self):
        server = self.server_input.text().strip()
        port_text = self.port_input.text().strip()
        email = self.sender_email_input.text().strip()
        password = self.sender_password_input.text().strip()

        if not server or not port_text or not email or not password:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak danych",
                "Uzupełnij serwer, port, e-mail i hasło przed testowaniem połączenia.",
            )
            return

        try:
            port = int(port_text)
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Błąd", "Port musi być liczbą.")
            return

        self.test_button.setEnabled(False)
        self._set_status_role("")
        self.test_status_label.setText("Testowanie połączenia...")

        self._test_worker = SMTPTestWorker(server, port, email, password, self)
        self._test_worker.finished_ok.connect(self._on_test_finished)
        self._test_worker.start()

    def _on_test_finished(self, success: bool, message: str):
        self.test_button.setEnabled(True)

        self._set_status_role("Success" if success else "Error")

        self.test_status_label.setText(message)
        self._test_worker = None

    def save_settings(self):
        port_text = self.port_input.text().strip()

        if port_text:
            try:
                int(port_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(self, "Błąd", "Port musi być liczbą.")
                return

        smtp_config = {
            "SMTP_SERVER": self.server_input.text().strip(),
            "SMTP_PORT": port_text,
            "SENDER_EMAIL": self.sender_email_input.text().strip(),
        }
        sender_email = smtp_config["SENDER_EMAIL"]
        sender_password = self.sender_password_input.text().strip()

        try:
            if sender_email and sender_password:
                keyring.set_password(
                    KEYRING_SERVICE, sender_email, sender_password
                )
            with open(SMTP_CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(smtp_config, f, indent=4, ensure_ascii=False)

            QtWidgets.QMessageBox.information(
                self, "Sukces", "Ustawienia SMTP zostały pomyślnie zapisane!"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Błąd", f"Wystąpił błąd podczas zapisywania: {e}"
            )