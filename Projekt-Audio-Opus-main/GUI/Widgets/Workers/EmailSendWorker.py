from PySide6 import QtCore
from core import email_sender

class EmailSendWorker(QtCore.QThread):
    finished_ok = QtCore.Signal(bool, str)

    def __init__(self, recipients: list[str], attachment_path: str,
                 subject: str | None = None, body: str | None = None, parent=None):
        super().__init__(parent)
        self.recipients = recipients
        self.attachment_path = attachment_path
        self.subject = subject
        self.body = body
        self.results = {}

    def run(self):
        try:
            self.results = email_sender.send_report_email(
                self.recipients,
                self.attachment_path,
                custom_subject=self.subject,
                custom_body=self.body,
            )
            successes = [email for email, (ok, _) in self.results.items() if ok]
            failures = [email for email, (ok, _) in self.results.items() if not ok]

            if self.results and not failures:
                self.finished_ok.emit(True, "Raport został pomyślnie wysłany do wszystkich odbiorców.")
            elif not successes:
                self.finished_ok.emit(
                    False,
                    "Nie udało się wysłać e-maila. Sprawdź dane uwierzytelniające w ustawieniach."
                )
            else:
                self.finished_ok.emit(
                    False,
                    f"Wysłano do {len(successes)} z {len(self.results)} odbiorców. "
                    f"Nie udało się wysłać do: {', '.join(failures)}."
                )
        except Exception as e:
            self.finished_ok.emit(False, f"Wystąpił błąd podczas wysyłania: {e}")
