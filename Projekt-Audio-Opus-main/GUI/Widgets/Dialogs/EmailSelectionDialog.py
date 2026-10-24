import os
import json
import re
import logging
from PySide6 import QtWidgets, QtCore, QtGui

from core import database_controller
from GUI.Widgets.Dialogs.CustomEmailsDialog import CUSTOM_EMAILS_FILE
from GUI.style.theme_manager import ThemeManager

logging.basicConfig(level=logging.WARNING)


class EmailSelectionDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, preselected_email=None):
        super().__init__(parent)
        self.setWindowTitle("Wybór odbiorców raportu")
        self.setMinimumSize(450, 450)

        # mail klienta wybranego w SettlementDialog jest od razu zaznaczony i wyróżniony.
        self.preselected_email = (preselected_email or "").strip().lower()

        layout = QtWidgets.QVBoxLayout(self)
        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(QtWidgets.QLabel("Zaznacz adresy z listy:"))

        self.btn_select_all = QtWidgets.QPushButton("Zaznacz wszystkie")
        self.btn_deselect_all = QtWidgets.QPushButton("Odznacz wszystkie")
        self.btn_select_all.clicked.connect(lambda: self._set_all_states(QtCore.Qt.CheckState.Checked))
        self.btn_deselect_all.clicked.connect(lambda: self._set_all_states(QtCore.Qt.CheckState.Unchecked))

        header_layout.addStretch()
        header_layout.addWidget(self.btn_select_all)
        header_layout.addWidget(self.btn_deselect_all)
        layout.addLayout(header_layout)

        self.list_widget = QtWidgets.QListWidget()
        layout.addWidget(self.list_widget)
        self.load_emails()

        layout.addWidget(QtWidgets.QLabel(
            "Dodatkowe adresy (oddziel przecinkiem, średnikiem lub Enterem):"
        ))
        self.manual_input = QtWidgets.QPlainTextEdit()
        self.manual_input.setFixedHeight(60)
        self.manual_input.setPlaceholderText("np. jan@example.com, anna@example.com")
        layout.addWidget(self.manual_input)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok |
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Ok).setText("OK")
        buttons.button(QtWidgets.QDialogButtonBox.StandardButton.Cancel).setText("Anuluj")
        buttons.accepted.connect(self.on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.selected_emails = []

    def load_emails(self):
        self.list_widget.clear()
        seen = set()
        client_entries = []

        try:
            for client in database_controller.load_database("clients"):
                email = (client.get("email") or "").strip()
                if email and email.lower() not in seen:
                    seen.add(email.lower())
                    client_entries.append((f"{email}  ({client.get('name', '')})", email))
        except Exception as e:
            logging.error(f"Błąd podczas ładowania klientów: {e}")

        # mail klienta wybranego w SettlementDialog trafia na górę listy, żeby był od razu widoczny
        if self.preselected_email:
            client_entries.sort(key=lambda entry: entry[1].strip().lower() != self.preselected_email)

        for label, email in client_entries:
            self._add_item(label, email)

        if os.path.exists(CUSTOM_EMAILS_FILE):
            try:
                with open(CUSTOM_EMAILS_FILE, "r", encoding="utf-8") as f:
                    for email in json.load(f):
                        email = email.strip()
                        if email and email.lower() not in seen:
                            seen.add(email.lower())
                            self._add_item(email, email)
            except Exception as e:
                logging.error(f"Błąd podczas ładowania własnych maili: {e}")

    def _add_item(self, label, email):
        item = QtWidgets.QListWidgetItem(label)
        item.setData(QtCore.Qt.ItemDataRole.UserRole, email)
        item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)

        is_preselected = bool(self.preselected_email) and email.strip().lower() == self.preselected_email
        item.setCheckState(QtCore.Qt.CheckState.Checked if is_preselected else QtCore.Qt.CheckState.Unchecked)

        if is_preselected:
            font = item.font()
            font.setBold(True)
            item.setFont(font)
            accent = ThemeManager.get_current_accent()
            item.setBackground(QtGui.QColor(accent))
            item.setForeground(QtGui.QColor("white"))
            item.setToolTip("Klient wybrany w raporcie")

        self.list_widget.addItem(item)

    def _set_all_states(self, state):
        for i in range(self.list_widget.count()):
            self.list_widget.item(i).setCheckState(state)

    def is_valid_email(self, email):
        pattern = r"^[\w\.-]+@[\w\.-]+\.\w+$"
        return re.match(pattern, email) is not None

    def on_accept(self):
        emails = [
            self.list_widget.item(i).data(QtCore.Qt.ItemDataRole.UserRole)
            for i in range(self.list_widget.count())
            if self.list_widget.item(i).checkState() == QtCore.Qt.CheckState.Checked
        ]
        raw_text = self.manual_input.toPlainText()
        manual_chunks = re.split(r'[;,\n\s]+', raw_text)

        invalid_emails = []

        for chunk in manual_chunks:
            email = chunk.strip()
            if email:
                if self.is_valid_email(email):
                    if email not in emails:
                        emails.append(email)
                else:
                    invalid_emails.append(email)

        if invalid_emails:
            QtWidgets.QMessageBox.warning(
                self,
                "Błędne adresy e-mail",
                f"Następujące adresy mają niepoprawny format i zostały zignorowane:\n\n{', '.join(invalid_emails)}"
            )
            return

        if not emails:
            QtWidgets.QMessageBox.warning(self, "Uwaga", "Wybierz lub wpisz przynajmniej jeden adres e-mail.")
            return

        self.selected_emails = emails
        self.accept()
