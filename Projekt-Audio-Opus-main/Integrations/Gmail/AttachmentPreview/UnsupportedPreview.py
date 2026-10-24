from PySide6 import QtWidgets, QtCore


class UnsupportedPreview(QtWidgets.QWidget):
    def __init__(self, filename, mime_type="", parent=None):
        super().__init__(parent)

        self.filename = filename
        self.mime_type = mime_type

        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        title = QtWidgets.QLabel(
            "Brak dostępnego podglądu"
        )

        title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        title.setProperty(
            "role",
            "Title"
        )

        info = QtWidgets.QLabel(
            f"Nie można wyświetlić podglądu pliku:\n"
            f"{self.filename}\n\n"
            f"Typ: {self.mime_type or 'nieznany'}\n\n"
            f"Możesz pobrać plik za pomocą przycisku "
            f"„Pobierz” w wiadomości."
        )

        info.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        info.setWordWrap(True)

        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(info)