from PySide6 import QtWidgets


class TextPreview(QtWidgets.QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.data = data

        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        text_edit = QtWidgets.QPlainTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(
            self.decode_text()
        )

        layout.addWidget(text_edit)

    def decode_text(self):
        encodings = [
            "utf-8",
            "utf-8-sig",
            "cp1250",
            "latin-1",
        ]

        for encoding in encodings:
            try:
                return self.data.decode(encoding)

            except UnicodeDecodeError:
                continue

        return (
            "Nie udało się odczytać tego pliku jako tekstu."
        )