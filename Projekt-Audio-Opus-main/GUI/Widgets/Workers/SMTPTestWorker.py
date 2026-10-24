import smtplib
from PySide6 import QtCore


class SMTPTestWorker(QtCore.QThread):

    finished_ok = QtCore.Signal(bool, str)  # success, message

    def __init__(self, server, port, email, password, parent=None):
        super().__init__(parent)
        self.server = server
        self.port = port
        self.email = email
        self.password = password

    def run(self):
        try:
            with smtplib.SMTP_SSL(self.server, self.port, timeout=10) as smtp:
                smtp.login(self.email, self.password)
            self.finished_ok.emit(True, "Połączenie i logowanie zakończone sukcesem.")

        except smtplib.SMTPAuthenticationError:
            self.finished_ok.emit(
                False,
                "Błąd uwierzytelniania: nieprawidłowy e-mail lub hasło.\n"
                "Sprawdź, czy nie potrzebujesz 'Hasła aplikacji' (App Password)."
            )
        except smtplib.SMTPConnectError:
            self.finished_ok.emit(False, "Nie udało się połączyć z serwerem SMTP. Sprawdź adres serwera i port.")
        except (TimeoutError, OSError) as e:
            self.finished_ok.emit(False, f"Błąd połączenia: {e}")
        except Exception as e:
            self.finished_ok.emit(False, f"Nieoczekiwany błąd: {e}")
