import os
import json
import re
from datetime import datetime
from pathlib import Path
from PySide6 import QtWidgets
from PySide6.QtWidgets import QFileDialog

from core import paths
from core import report_generator
from GUI.Widgets.Buttons.Help.HelpButton import HelpButton
from GUI.Widgets.Settlement.SettlementDialog import SettlementDialog
from GUI.Widgets.Dialogs.CalculatorDialog import (
    CalculatorDialog
)
from GUI.Widgets.Dialogs.MessageSettingsDialog import (
    MessageSettingsDialog,
    MSG_CONFIG_FILE,
    DEFAULT_SUBJECT as SETTINGS_DEFAULT_SUBJECT,
    DEFAULT_BODY as SETTINGS_DEFAULT_BODY,
    DEFAULT_FOOTER,
)
from GUI.Widgets.Settings.SMTPSettingsPanel import SMTP_CONFIG_FILE
from GUI.Widgets.Dialogs.CustomEmailsDialog import CustomEmailsDialog
from GUI.Widgets.Dialogs.EmailHistoryDialog import EmailHistoryDialog, EMAIL_HISTORY_FILE
from GUI.Widgets.Dialogs.EmailSelectionDialog import EmailSelectionDialog
from GUI.Widgets.Dialogs.SendConfirmationDialog import SendConfirmationDialog
from GUI.Widgets.Workers.EmailSendWorker import EmailSendWorker


DEFAULT_SUBJECT = "Raport rozliczeniowy"
DEFAULT_BODY = "W załączniku przesyłamy raport rozliczeniowy."
EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Plik z zapamiętanymi ostrzeżeniami odznaczonymi jako "Nie pokazuj ponownie".
UI_WARNINGS_FILE = Path(paths.data_path("Databases", "ui_warnings.json"))
MISSING_CLIENT_EMAIL_WARNING = "missing_client_email"

class ReportTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.folder_output = report_generator.FOLDER

        outer_layout = QtWidgets.QVBoxLayout(self)
        outer_layout.setContentsMargins(24, 20, 24, 20)
        outer_layout.setSpacing(16)
        reports_group = QtWidgets.QGroupBox("Raporty")
        report_help_button = HelpButton("reports", "Raporty")

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(report_help_button)
        outer_layout.addLayout(top_layout)

        reports_layout = QtWidgets.QHBoxLayout()
        reports_layout.setSpacing(10)

        self.pdf_button = QtWidgets.QPushButton(
            "Nowe rozliczenie (PDF)"
        )
        self.pdf_button.clicked.connect(
            self.open_settlement
        )

        self.commission_button = QtWidgets.QPushButton(
            "Kalkulatory"
        )
        self.commission_button.clicked.connect(
            self.open_commission_calculator
        )

        # Wszystkie przyciski mają identyczne proporcje.
        reports_layout.addWidget(
            self.pdf_button,
            1
        )

        reports_layout.addWidget(
            self.commission_button,
            1
        )

        reports_group.setLayout(
            reports_layout
        )

        outer_layout.addWidget(
            reports_group
        )

        title_label = QtWidgets.QLabel("Raport rozliczeniowy na e-mail")
        title_label.setProperty("role", "Title")
        outer_layout.addWidget(title_label)

        subtitle_label = QtWidgets.QLabel(
            "Wygeneruj raport PDF na podstawie rozliczenia, wybierz odbiorców i wyślij go po potwierdzeniu."
        )
        outer_layout.addWidget(subtitle_label)

        send_group = QtWidgets.QGroupBox("Wysyłka raportu")
        send_layout = QtWidgets.QVBoxLayout()
        send_layout.setSpacing(10)

        self.send_button = QtWidgets.QPushButton("Wybierz dane i wyślij raport")
        self.send_button.clicked.connect(self.on_send_clicked)
        send_layout.addWidget(self.send_button)

        send_group.setLayout(send_layout)
        outer_layout.addWidget(send_group)

        tools_group = QtWidgets.QGroupBox(
            "Narzędzia i ustawienia"
        )

        tools_layout = QtWidgets.QHBoxLayout()
        tools_layout.setSpacing(10)

        self.settings_button = QtWidgets.QPushButton(
            "Ustawienia treści wiadomości"
        )
        self.settings_button.clicked.connect(
            self.open_settings
        )

        self.manage_emails_button = QtWidgets.QPushButton(
            "Własne adresy e-mail"
        )
        self.manage_emails_button.clicked.connect(
            self.open_custom_emails_manager
        )

        self.history_button = QtWidgets.QPushButton(
            "Historia wysyłki"
        )
        self.history_button.clicked.connect(
            self.open_email_history
        )

        tools_layout.addWidget(
            self.settings_button,
            1
        )

        tools_layout.addWidget(
            self.manage_emails_button,
            1
        )

        tools_layout.addWidget(
            self.history_button,
            1
        )

        tools_group.setLayout(
            tools_layout
        )

        outer_layout.addWidget(
            tools_group
        )

        progress_layout = QtWidgets.QVBoxLayout()
        progress_layout.setSpacing(6)

        self.progress_label = QtWidgets.QLabel("")
        self.progress_label.hide()
        progress_layout.addWidget(self.progress_label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.hide()
        progress_layout.addWidget(self.progress_bar)

        outer_layout.addLayout(progress_layout)
        outer_layout.addStretch()

        self._send_worker = None
        self._pending_report_path = None
        self._pending_is_existing_file = False
        self._pending_recipients = []

    def open_settings(self):
        dialog = MessageSettingsDialog(self)
        dialog.exec()

    def open_custom_emails_manager(self):
        dialog = CustomEmailsDialog(self)
        dialog.exec()

    def open_email_history(self):
        dialog = EmailHistoryDialog(self)
        dialog.exec()

    def is_valid_email_format(self, email: str) -> bool:
        return bool(EMAIL_REGEX.match(email))

    def load_email_content(self):
        subject = SETTINGS_DEFAULT_SUBJECT
        body = SETTINGS_DEFAULT_BODY
        footer = DEFAULT_FOOTER

        if os.path.exists(MSG_CONFIG_FILE):
            try:
                with open(MSG_CONFIG_FILE, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    subject = config.get("EMAIL_SUBJECT", subject)
                    body = config.get("EMAIL_BODY", body)
                    footer = config.get("EMAIL_FOOTER", footer)
            except Exception as e:
                print(f"Nie udało się wczytać treści wiadomości z ustawień: {e}")

        if footer.strip():
            full_body = body + "\n\n--\n" + footer
        else:
            full_body = body

        return subject, full_body

    def log_email_history(self, receiver_email, file_path, success, error=None):
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "receiver": receiver_email,
            "file": os.path.basename(file_path) if file_path else "",
            "success": success,
            "error": str(error) if error else ""
        }

        history = []
        if os.path.exists(EMAIL_HISTORY_FILE):
            try:
                with open(EMAIL_HISTORY_FILE, "r", encoding="utf-8") as f:
                    history = json.load(f)
            except Exception as e:
                print(f"Nie udało się wczytać istniejącej historii: {e}")
                history = []

        history.append(entry)

        try:
            with open(EMAIL_HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Nie udało się zapisać historii wysyłki: {e}")

    def _is_warning_hidden(self, key):
        if not UI_WARNINGS_FILE.exists():
            return False
        try:
            with open(UI_WARNINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return bool(data.get(key, False))
        except (json.JSONDecodeError, OSError) as e:
            print(f"Nie udało się odczytać ustawień ostrzeżeń: {e}")
            return False

    def _hide_warning(self, key):
        data = {}
        if UI_WARNINGS_FILE.exists():
            try:
                with open(UI_WARNINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Nie udało się odczytać ustawień ostrzeżeń: {e}")
                data = {}

        data[key] = True

        try:
            with open(UI_WARNINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
        except OSError as e:
            print(f"Nie udało się zapisać ustawień ostrzeżeń: {e}")

    def _warn_missing_client_email(self):
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        box.setWindowTitle("Brak adresu e-mail klienta")
        box.setText(
            "Wybrany klient nie ma jeszcze dodanego swojego adresu e-mail.\n\n"
            "Możesz mimo to wysłać raport, wpisując adres ręcznie lub wybrać go z listy odbiorców."
        )
        box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)

        checkbox = QtWidgets.QCheckBox("Nie pokazuj ponownie")
        box.setCheckBox(checkbox)

        box.exec()

        if checkbox.isChecked():
            self._hide_warning(MISSING_CLIENT_EMAIL_WARNING)

    def on_send_clicked(self):
        if not os.path.exists(SMTP_CONFIG_FILE):
            QtWidgets.QMessageBox.warning(self, "Brak ustawień",
                                          "Proszę najpierw kliknąć 'Ustawienia SMTP i wiadomości', aby skonfigurować pocztę wychodzącą.")
            return

        dialog = SettlementDialog(self, email_mode=True)
        result = dialog.exec()

        if result != QtWidgets.QDialog.DialogCode.Accepted:
            return

        report_path = getattr(dialog, 'generated_file_path', None)
        is_existing_file = getattr(dialog, 'is_existing_file', False)

        if not report_path or not os.path.exists(report_path):
            QtWidgets.QMessageBox.critical(self, "Błąd",
                                           "Nie udało się odnaleźć pliku PDF. Wysyłanie przerwane.")
            return

        preselected_email = getattr(dialog, 'selected_client_email', None)

        if not preselected_email and not self._is_warning_hidden(MISSING_CLIENT_EMAIL_WARNING):
            self._warn_missing_client_email()

        selection_dialog = EmailSelectionDialog(self, preselected_email=preselected_email)
        if selection_dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            self._cleanup_report_file(report_path, is_existing_file)
            return

        recipients = selection_dialog.selected_emails

        invalid_emails = [email for email in recipients if not self.is_valid_email_format(email)]
        if invalid_emails:
            QtWidgets.QMessageBox.warning(
                self, "Błąd",
                "Następujące adresy e-mail wyglądają na niepoprawne:\n" +
                "\n".join(invalid_emails) +
                "\n\nSprawdź format (np. jan.kowalski@gmail.com) i spróbuj ponownie."
            )
            self._cleanup_report_file(report_path, is_existing_file)
            return

        subject, body = self.load_email_content()
        attachment_name = os.path.basename(report_path)

        confirm_dialog = SendConfirmationDialog(recipients, attachment_name, subject, body, self)
        if confirm_dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            self._cleanup_report_file(report_path, is_existing_file)
            return

        final_subject = confirm_dialog.subject_input.text()
        subject_override = final_subject if final_subject != subject else None

        final_body = confirm_dialog.body_preview.toPlainText()
        body_override = final_body if final_body != body else None

        self._pending_report_path = report_path
        self._pending_is_existing_file = is_existing_file
        self._pending_recipients = recipients

        self.send_button.setEnabled(False)
        self.progress_label.setText(f"Wysyłanie raportu do {len(recipients)} odbiorców...")
        self.progress_label.show()
        self.progress_bar.show()

        self._send_worker = EmailSendWorker(recipients, report_path, subject=subject_override, body=body_override,
                                            parent=self)
        self._send_worker.finished_ok.connect(self.on_send_finished)
        self._send_worker.start()

    def on_send_finished(self, success: bool, message: str):
        self.progress_label.hide()
        self.progress_bar.hide()
        self.send_button.setEnabled(True)

        results = getattr(self._send_worker, "results", {}) or {}

        for recipient in self._pending_recipients:
            recipient_success, recipient_error = results.get(
                recipient, (success, None if success else message)
            )
            self.log_email_history(
                recipient, self._pending_report_path, recipient_success, error=recipient_error
            )

        if success:
            QtWidgets.QMessageBox.information(self, "Sukces", message)
        else:
            QtWidgets.QMessageBox.critical(self, "Błąd", message)

        self._cleanup_report_file(self._pending_report_path, self._pending_is_existing_file)

        self._pending_report_path = None
        self._pending_is_existing_file = False
        self._pending_recipients = []
        self._send_worker = None

    def _cleanup_report_file(self, report_path, is_existing_file):
        if report_path and not is_existing_file and os.path.exists(report_path):
            try:
                os.remove(report_path)
            except Exception as e:
                print(f"Nie udało się usunąć pliku tymczasowego: {e}")

    def open_settlement(self):
        dialog = SettlementDialog(
            self,
            folder_output=self.folder_output
        )
        dialog.exec()

    def open_commission_calculator(self):
        dialog = CalculatorDialog(self)
        dialog.exec()

