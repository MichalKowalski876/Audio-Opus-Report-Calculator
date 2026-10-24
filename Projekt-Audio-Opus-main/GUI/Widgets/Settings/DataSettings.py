import os
import shutil
from datetime import datetime

from PySide6 import QtCore, QtWidgets

from core import backup_reminder
from core import database_controller
from GUI.Widgets.confirm import confirm_yes_no


# Nagłówek pliku SQLite - pierwsze 16 bajtów każdej prawdziwej bazy.
_SQLITE_MAGIC = b"SQLite format 3\x00"


def _database_path() -> str:
    return os.path.join(database_controller.FOLDER, database_controller.DATABASE_FILENAME)


def _looks_like_sqlite(path: str) -> bool:
    try:
        with open(path, "rb") as file:
            return file.read(len(_SQLITE_MAGIC)) == _SQLITE_MAGIC
    except OSError:
        return False


class DataSettings(QtWidgets.QWidget):
    """Ręczna kopia zapasowa bazy (klienci, produkty, rozliczenia).

    Baza (db.sqlite) nie jest już śledzona w git, więc to jedyny sposób
    na przeniesienie danych między maszynami / zrobienie backupu przed
    ryzykowną zmianą.
    """

    # Emitowane po udanym wczytaniu kopii - główne okno odświeża zakładki.
    data_imported = QtCore.Signal()

    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title_label = QtWidgets.QLabel("Dane")
        title_label.setProperty("role", "Title")
        layout.addWidget(title_label)

        subtitle = QtWidgets.QLabel(
            "Kopia zapasowa bazy klientów, produktów i rozliczeń "
            "(Databases/db.sqlite)."
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        backup_group = QtWidgets.QGroupBox("Kopia zapasowa")
        backup_layout = QtWidgets.QVBoxLayout(backup_group)
        backup_layout.setSpacing(8)

        self.export_button = QtWidgets.QPushButton("Eksportuj kopię bazy...")
        self.export_button.setMinimumHeight(36)
        self.export_button.clicked.connect(self.export_database)
        backup_layout.addWidget(self.export_button)

        self.import_button = QtWidgets.QPushButton("Wczytaj kopię bazy...")
        self.import_button.setMinimumHeight(36)
        self.import_button.clicked.connect(self.import_database)
        backup_layout.addWidget(self.import_button)

        import_hint = QtWidgets.QLabel(
            "Wczytanie kopii NADPISUJE obecną bazę. Zrób najpierw eksport, "
            "jeśli chcesz zachować bieżące dane. Zakładki Klienci / Produkty / "
            "Platformy odświeżą się od razu."
        )
        import_hint.setWordWrap(True)
        import_hint.setStyleSheet("font-size: 11px; color: palette(mid);")
        backup_layout.addWidget(import_hint)

        layout.addWidget(backup_group)
        layout.addStretch()

    def export_database(self):
        source = _database_path()

        if not os.path.exists(source):
            QtWidgets.QMessageBox.warning(
                self,
                "Brak bazy",
                "Nie znaleziono pliku bazy do wyeksportowania."
            )
            return

        default_name = f"audio_opus_kopia_{datetime.now():%Y-%m-%d_%H-%M}.sqlite"

        target, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Eksportuj kopię bazy",
            default_name,
            "Baza SQLite (*.sqlite)"
        )

        if not target:
            return

        try:
            shutil.copy2(source, target)
        except OSError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd eksportu",
                f"Nie udało się zapisać kopii:\n{error}"
            )
            return

        backup_reminder.record_backup()

        QtWidgets.QMessageBox.information(
            self,
            "Gotowe",
            f"Zapisano kopię bazy:\n{target}"
        )

    def import_database(self):
        source, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Wczytaj kopię bazy",
            "",
            "Baza SQLite (*.sqlite)"
        )

        if not source:
            return

        if not _looks_like_sqlite(source):
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy plik",
                "Wybrany plik nie wygląda na bazę SQLite."
            )
            return

        confirmed = confirm_yes_no(
            self,
            "Potwierdzenie",
            "Wczytanie kopii NADPISZE obecną bazę - klientów, produkty "
            "i rozliczenia. Tej operacji nie da się cofnąć.\n\n"
            "Wczytać wybrany plik?"
        )

        if not confirmed:
            return

        target = _database_path()

        if os.path.abspath(source) == os.path.abspath(target):
            QtWidgets.QMessageBox.information(
                self,
                "To już jest bieżąca baza",
                "Wybrany plik to baza, z której program właśnie korzysta - "
                "nie ma czego wczytywać."
            )
            return

        try:
            os.makedirs(database_controller.FOLDER, exist_ok=True)
            shutil.copy2(source, target)
        except OSError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd wczytywania",
                f"Nie udało się wczytać kopii:\n{error}"
            )
            return

        self.data_imported.emit()

        QtWidgets.QMessageBox.information(
            self,
            "Gotowe",
            "Baza została wczytana, a zakładki odświeżone. Jeśli coś nie "
            "wygląda na zaktualizowane, uruchom program ponownie."
        )
