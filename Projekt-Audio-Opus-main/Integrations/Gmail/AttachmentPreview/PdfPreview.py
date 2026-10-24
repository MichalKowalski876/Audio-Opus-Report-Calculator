import os
import tempfile

from PySide6 import QtWidgets, QtPdf, QtPdfWidgets


class PdfPreview(QtWidgets.QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.data = data
        self.temp_path = None
        self.document = None

        self.destroyed.connect(
            self.cleanup_temp_file
        )

        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        try:
            with tempfile.NamedTemporaryFile(
                suffix=".pdf",
                delete=False
            ) as temp_file:
                temp_file.write(self.data)
                self.temp_path = temp_file.name

            self.document = QtPdf.QPdfDocument(
                self
            )

            error = self.document.load(
                self.temp_path
            )

            if error != QtPdf.QPdfDocument.Error.None_:
                raise RuntimeError(
                    f"Błąd podczas otwierania PDF: {error}"
                )

            self.pdf_view = QtPdfWidgets.QPdfView(
                self
            )

            self.pdf_view.setDocument(
                self.document
            )

            self.pdf_view.setPageMode(
                QtPdfWidgets.QPdfView.PageMode.MultiPage
            )

            self.pdf_view.setZoomMode(
                QtPdfWidgets.QPdfView.ZoomMode.FitToWidth
            )

            layout.addWidget(
                self.pdf_view
            )

        except Exception as error:
            self.cleanup_temp_file()

            error_label = QtWidgets.QLabel(
                "Nie udało się wyświetlić pliku PDF.\n\n"
                f"{error}"
            )

            error_label.setWordWrap(True)

            layout.addWidget(
                error_label
            )

    def cleanup_temp_file(self, *args):
        if self.document is not None:
            try:
                self.document.close()
            except Exception:
                pass

        if (
            self.temp_path
            and os.path.exists(self.temp_path)
        ):
            try:
                os.remove(
                    self.temp_path
                )
            except OSError:
                pass

        self.temp_path = None