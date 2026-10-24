from PySide6 import QtWidgets, QtCore, QtGui

from Integrations.Gmail.AttachmentPreview.ArchivePreview import ArchivePreview
from Integrations.Gmail.AttachmentPreview.ExcelPreview import ExcelPreview
from Integrations.Gmail.AttachmentPreview.ImagePreview import ImagePreview
from Integrations.Gmail.AttachmentPreview.PdfPreview import PdfPreview
from Integrations.Gmail.AttachmentPreview.TextPreview import TextPreview
from Integrations.Gmail.AttachmentPreview.UnsupportedPreview import UnsupportedPreview
from Integrations.Gmail.AttachmentPreview.WordPreview import WordPreview


IMAGE_EXTENSIONS = (
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".bmp",
)

EXCEL_EXTENSIONS = (
    ".xlsx",
    ".xlsm",
)

WORD_EXTENSIONS = (
    ".docx",
)

PDF_EXTENSIONS = (
    ".pdf",
)

TEXT_EXTENSIONS = (
    ".txt",
    ".csv",
    ".json",
    ".xml",
    ".log",
    ".md",
    ".ini",
    ".cfg",
    ".yaml",
    ".yml",
)

ARCHIVE_EXTENSIONS = (
    ".zip",
    ".rar",
)


class AttachmentPreviewWindow(QtWidgets.QDialog):
    def __init__(
        self,
        filename,
        data,
        mime_type="",
        parent=None
    ):
        super().__init__(parent)

        self.filename = filename
        self.data = data
        self.mime_type = mime_type

        self.setWindowTitle(
            f"Podgląd - {filename}"
        )

        self.resize(
            800,
            600
        )

        self.setMinimumSize(
            500,
            400
        )

        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowType.WindowMinMaxButtonsHint
        )

        self.create_ui()
        self.create_shortcuts()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        header_layout = QtWidgets.QHBoxLayout()

        title = QtWidgets.QLabel(
            self.filename
        )
        title.setProperty(
            "role",
            "Title"
        )

        self.fullscreen_button = QtWidgets.QPushButton()
        self.fullscreen_button.setFixedSize(
            36,
            32
        )
        self.fullscreen_button.setToolTip(
            "Pełny ekran (F11)"
        )

        fullscreen_icon = self.style().standardIcon(
            QtWidgets.QStyle.StandardPixmap.SP_TitleBarMaxButton
        )

        self.fullscreen_button.setIcon(
            fullscreen_icon
        )

        self.fullscreen_button.clicked.connect(
            self.toggle_fullscreen
        )

        header_layout.addWidget(
            title
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.fullscreen_button
        )

        info = QtWidgets.QLabel(
            f"Typ: {self.mime_type or 'nieznany'} | "
            f"Rozmiar: {self.format_file_size(len(self.data))}"
        )

        layout.addLayout(
            header_layout
        )

        layout.addWidget(
            info
        )

        preview = self.create_preview()

        layout.addWidget(
            preview,
            1
        )

    def create_shortcuts(self):
        self.fullscreen_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("F11"),
            self
        )

        self.fullscreen_shortcut.activated.connect(
            self.toggle_fullscreen
        )

        self.escape_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Escape"),
            self
        )

        self.escape_shortcut.activated.connect(
            self.exit_fullscreen
        )

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    def exit_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()

    def create_preview(self):
        extension = self.filename.lower()

        if extension.endswith(
            IMAGE_EXTENSIONS
        ):
            return ImagePreview(
                self.data,
                self
            )

        if extension.endswith(
            EXCEL_EXTENSIONS
        ):
            return ExcelPreview(
                self.data,
                self
            )

        if extension.endswith(
            WORD_EXTENSIONS
        ):
            return WordPreview(
                self.data,
                self
            )

        if extension.endswith(
            PDF_EXTENSIONS
        ):
            return PdfPreview(
                self.data,
                self
            )

        if extension.endswith(
            TEXT_EXTENSIONS
        ):
            return TextPreview(
                self.data,
                self
            )

        if extension.endswith(
            ARCHIVE_EXTENSIONS
        ):
            return ArchivePreview(
                self.filename,
                self.data,
                self
            )

        return UnsupportedPreview(
            self.filename,
            self.mime_type,
            self
        )

    def format_file_size(self, size):
        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"

        if size < 1024 * 1024 * 1024:
            return (
                f"{size / (1024 * 1024):.1f} MB"
            )

        return (
            f"{size / (1024 * 1024 * 1024):.1f} GB"
        )