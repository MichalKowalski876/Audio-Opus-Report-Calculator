import html
import tempfile
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path

from PySide6 import QtWidgets, QtCore, QtGui

from Integrations.Gmail.AttachmentPreview.AttachmentPreviewWindow import (
    AttachmentPreviewWindow
)
from Integrations.Gmail.Messages.gmail_messages import (
    get_messages,
    get_message,
    download_attachment,
)
from Integrations.Gmail.Config.gmail_auth import (
    has_gmail_credentials,
    has_gmail_authorization,
    authorize_gmail,
)


class MailListItemDelegate(QtWidgets.QStyledItemDelegate):
    def paint(self, painter, option, index):
        if (
            index.data(QtCore.Qt.ItemDataRole.UserRole + 1)
            and option.state & QtWidgets.QStyle.StateFlag.State_Selected
        ):
            option.palette.setColor(
                QtGui.QPalette.ColorRole.Highlight,
                QtGui.QColor("#4f9d59"),
            )
            option.palette.setColor(
                QtGui.QPalette.ColorRole.HighlightedText,
                QtGui.QColor("#ffffff"),
            )

        super().paint(painter, option, index)


class MailListItemWidget(QtWidgets.QWidget):
    def __init__(self, message, current_label, parent=None):
        super().__init__(parent)

        self.message = message
        self.current_label = current_label
        self.has_excel_attachment = any(
            self._is_excel_attachment(attachment)
            for attachment in (message.get("attachments") or [])
        )

        if self.has_excel_attachment:
            self.setObjectName("excelMessageWidget")
            self.setAutoFillBackground(True)
            self.setStyleSheet(
                """
                QWidget#excelMessageWidget {
                    background-color: #3c7444;
                    border: 1px solid #65c96f;
                    border-radius: 6px;
                }
                """
            )

        self.create_ui()

    @staticmethod
    def _is_excel_attachment(attachment):
        filename = str(attachment.get("filename", "")).lower()
        mime_type = str(attachment.get("mime_type", "")).lower()
        return filename.endswith((".xls", ".xlsx", ".xlsm", ".xlsb")) or (
            mime_type
            in {
                "application/vnd.ms-excel",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/vnd.ms-excel.sheet.macroenabled.12",
            }
        )

    @staticmethod
    def _message_has_excel_attachment(message):
        return any(
            MailListItemWidget._is_excel_attachment(attachment)
            for attachment in (message.get("attachments") or [])
        )

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        layout.setContentsMargins(
            10,
            8,
            10,
            8
        )

        layout.setSpacing(3)

        if self.has_excel_attachment:
            report_badge = QtWidgets.QLabel("RAPORT EXCEL")
            report_badge.setStyleSheet(
                """
                QLabel {
                    color: #7dff8b;
                    font-size: 10px;
                    font-weight: bold;
                }
                """
            )
            layout.addWidget(report_badge)

        subject = QtWidgets.QLabel(
            self.message.get(
                "subject",
                "(brak tematu)"
            )
        )

        subject.setStyleSheet("""
            QLabel {
                font-size: 14px;
                font-weight: bold;
            }
        """)

        if self.message.get("unread"):
            subject.setStyleSheet("""
                QLabel {
                    font-size: 14px;
                    font-weight: 800;
                    color: #e87525;
                }
            """)

        subject.setTextFormat(
            QtCore.Qt.TextFormat.PlainText
        )

        if self.current_label == "SENT":
            person = self.message.get(
                "recipient",
                "(brak odbiorcy)"
            )
        else:
            person = self.message.get(
                "sender",
                "(nieznany nadawca)"
            )

        person_label = QtWidgets.QLabel()

        person_label.setTextFormat(
            QtCore.Qt.TextFormat.RichText
        )

        person_label.setText(
            self.format_person(person)
        )

        preview_text = self.message.get(
            "preview",
            ""
        ).replace(
            "\n",
            " "
        ).strip()

        preview = QtWidgets.QLabel(
            preview_text
        )

        preview.setStyleSheet("""
            QLabel {
                color: #888888;
                font-size: 11px;
            }
        """)

        preview.setTextFormat(
            QtCore.Qt.TextFormat.PlainText
        )

        preview.setMaximumHeight(34)
        preview.setWordWrap(True)

        layout.addWidget(subject)
        layout.addWidget(person_label)

        if preview_text:
            layout.addSpacing(2)
            layout.addWidget(preview)

    def format_person(self, person):
        person = person.strip()

        if "<" in person and ">" in person:
            name, email = person.rsplit(
                "<",
                1
            )

            email = email.rstrip(">").strip()
            name = name.strip()

            return (
                f'<span style="color:#b8b8b8;">'
                f'{html.escape(name)}'
                f'</span> '
                f'<span style="color:#666666;">'
                f'&lt;{html.escape(email)}&gt;'
                f'</span>'
            )

        return (
            f'<span style="color:#b8b8b8;">'
            f'{html.escape(person)}'
            f'</span>'
        )

class AttachmentLoader(QtCore.QObject):
    finished = QtCore.Signal(bytes)
    error = QtCore.Signal(str)

    def __init__(self, message_id, attachment_id):
        super().__init__()

        self.message_id = message_id
        self.attachment_id = attachment_id

    @QtCore.Slot()
    def run(self):
        try:
            data = download_attachment(
                message_id=self.message_id,
                attachment_id=self.attachment_id
            )

            self.finished.emit(data)

        except Exception as error:
            self.error.emit(str(error))

class MailLoader(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(
        self,
        label,
        max_results=50,
        page_token=None,
        query="",
    ):
        super().__init__()

        self.label = label
        self.max_results = max_results
        self.page_token = page_token
        self.query = query

    @QtCore.Slot()
    def run(self):
        try:
            result = get_messages(
                max_results=self.max_results,
                label=self.label,
                page_token=self.page_token,
                query=self.query,
            )

            self.finished.emit(result)

        except Exception as error:
            self.error.emit(str(error))


class MessageDetailLoader(QtCore.QObject):
    finished = QtCore.Signal(object)
    error = QtCore.Signal(str)

    def __init__(self, message_id):
        super().__init__()
        self.message_id = message_id

    @QtCore.Slot()
    def run(self):
        try:
            message = get_message(
                self.message_id
            )

            self.finished.emit(message)

        except Exception as error:
            self.error.emit(str(error))

class GmailAuthWorker(QtCore.QObject):
    finished = QtCore.Signal()
    error = QtCore.Signal(str)

    @QtCore.Slot()
    def run(self):
        try:
            authorize_gmail()
            self.finished.emit()
        except Exception as error:
            self.error.emit(str(error))

class MailDebugWindow(QtWidgets.QDialog):
    report_selected = QtCore.Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Raporty z poczty Gmail")
        self.resize(1200, 700)
        self.setMinimumSize(900, 550)

        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowType.WindowMinMaxButtonsHint
        )

        self.messages = []

        self.page_size = 20
        self.current_page = 0
        self.page_tokens = [None]
        self.next_page_token = None

        # Cache stron osobno dla Odebranych i Wysłanych.
        # Klucz wewnętrzny to numer strony, wartość zawiera wiadomości
        # oraz token następnej strony.
        self.page_cache = {
            "INBOX": {},
            "SENT": {},
        }

        self.detail_thread = None
        self.detail_worker = None
        self.selected_message_id = None

        self.pending_message_id = None
        self.loading_message_id = None

        self.thread = None
        self.worker = None
        self.preview_thread = None
        self.preview_worker = None
        self.preview_loading = None

        self.preview_message = None
        self.preview_attachment = None

        self.auth_thread = None
        self.auth_worker = None

        self.current_label = "INBOX"
        self.search_query = ""
        self.global_search_query = ""
        self.date_filter = "Wszystkie"
        self.sort_order = "Najnowsze"

        self.create_ui()

        if (
                has_gmail_credentials()
                and has_gmail_authorization()
        ):
            self.show_mail_view()
        else:
            self.show_setup_view()

    def create_ui(self):
        self.main_layout = QtWidgets.QVBoxLayout(self)

        self.stack = QtWidgets.QStackedWidget()

        self.setup_page = self.create_setup_page()
        self.mail_page = QtWidgets.QWidget()

        self.stack.addWidget(
            self.setup_page
        )

        self.stack.addWidget(
            self.mail_page
        )

        self.main_layout.addWidget(
            self.stack
        )

        self.create_mail_ui(
            self.mail_page
        )

    def create_setup_page(self):
        page = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(
            60,
            60,
            60,
            60
        )

        layout.addStretch()

        container = QtWidgets.QWidget()

        container.setMaximumWidth(
            600
        )

        container_layout = QtWidgets.QVBoxLayout(
            container
        )

        container_layout.setSpacing(
            16
        )

        title = QtWidgets.QLabel(
            "Poczta Gmail"
        )

        title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        title.setStyleSheet(
            """
            font-size: 28px;
            font-weight: bold;
            """
        )

        subtitle = QtWidgets.QLabel(
            "Połącz konto Google"
        )

        subtitle.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        subtitle.setStyleSheet(
            """
            font-size: 18px;
            font-weight: bold;
            """
        )

        description = QtWidgets.QLabel(
            "Integracja Gmail nie została jeszcze "
            "skonfigurowana.\n\n"
            "Połącz konto Google, aby uzyskać dostęp "
            "do wiadomości oraz załączników bezpośrednio "
            "z aplikacji Audio Opus."
        )

        description.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        description.setWordWrap(
            True
        )

        self.connect_google_button = QtWidgets.QPushButton(
            "Połącz z Google"
        )

        self.connect_google_button.setMinimumHeight(
            42
        )

        self.connect_google_button.clicked.connect(
            self.connect_google
        )

        info = QtWidgets.QLabel(
            "Autoryzacja odbywa się przez Google OAuth 2.0"
        )

        info.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        info.setStyleSheet(
            """
            color: #888888;
            """
        )

        container_layout.addWidget(
            title
        )

        container_layout.addWidget(
            subtitle
        )

        container_layout.addWidget(
            description
        )

        container_layout.addSpacing(
            10
        )

        container_layout.addWidget(
            self.connect_google_button
        )

        container_layout.addWidget(
            info
        )

        layout.addWidget(
            container,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        layout.addStretch()

        return page

    def show_setup_view(self):
        self.stack.setCurrentWidget(
            self.setup_page
        )

    def show_mail_view(self):
        self.stack.setCurrentWidget(
            self.mail_page
        )

        self.load_messages()

    def connect_google(self):
        if self.auth_thread is not None:
            return

        if not has_gmail_credentials():
            QtWidgets.QMessageBox.warning(
                self,
                "Konfiguracja Gmail",
                "Brakuje konfiguracji Google OAuth dla aplikacji."
            )
            return

        self.connect_google_button.setEnabled(False)
        self.connect_google_button.setText(
            "Oczekiwanie na autoryzację..."
        )

        self.auth_thread = QtCore.QThread(self)
        self.auth_worker = GmailAuthWorker()

        self.auth_worker.moveToThread(
            self.auth_thread
        )

        self.auth_thread.started.connect(
            self.auth_worker.run
        )

        self.auth_worker.finished.connect(
            self.on_gmail_authorized
        )

        self.auth_worker.error.connect(
            self.on_gmail_auth_error
        )

        self.auth_worker.finished.connect(
            self.auth_thread.quit
        )

        self.auth_worker.error.connect(
            self.auth_thread.quit
        )

        self.auth_worker.finished.connect(
            self.auth_worker.deleteLater
        )

        self.auth_worker.error.connect(
            self.auth_worker.deleteLater
        )

        self.auth_thread.finished.connect(
            self.on_auth_thread_finished
        )

        self.auth_thread.start()

    def on_gmail_authorized(self):
        self.connect_google_button.setText(
            "Połączono"
        )

        self.show_mail_view()

    def on_gmail_auth_error(self, error):
        self.connect_google_button.setEnabled(True)
        self.connect_google_button.setText(
            "Połącz z Google"
        )

        QtWidgets.QMessageBox.critical(
            self,
            "Błąd autoryzacji Gmail",
            error
        )

    def on_auth_thread_finished(self):
        if self.auth_thread is not None:
            self.auth_thread.deleteLater()

        self.auth_thread = None
        self.auth_worker = None

    def create_mail_ui(self, parent):
        main_layout = QtWidgets.QVBoxLayout(parent)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        title = QtWidgets.QLabel("Poczta Gmail")
        title.setProperty("role", "Title")

        self.inbox_button = QtWidgets.QPushButton("Odebrane")
        self.inbox_button.setCheckable(True)
        self.inbox_button.setChecked(True)

        self.sent_button = QtWidgets.QPushButton("Wysłane")
        self.sent_button.setCheckable(True)

        self.folder_buttons = QtWidgets.QButtonGroup(self)
        self.folder_buttons.setExclusive(True)

        self.folder_buttons.addButton(
            self.inbox_button
        )

        self.folder_buttons.addButton(
            self.sent_button
        )

        self.inbox_button.clicked.connect(
            lambda: self.change_folder("INBOX")
        )

        self.sent_button.clicked.connect(
            lambda: self.change_folder("SENT")
        )

        self.refresh_button = QtWidgets.QPushButton(
            "Odśwież"
        )

        self.refresh_button.clicked.connect(
            self.refresh_messages
        )

        self.global_search_button = QtWidgets.QPushButton(
            "Szukaj w całej poczcie"
        )
        self.global_search_button.clicked.connect(
            self.search_globally
        )

        folder_layout = QtWidgets.QHBoxLayout()
        folder_layout.setSpacing(6)

        folder_layout.addWidget(self.inbox_button)
        folder_layout.addWidget(self.sent_button)

        folder_layout.addStretch()

        folder_layout.addWidget(
            self.refresh_button
        )

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText(
            "Szukaj w temacie, nadawcy i podglądzie..."
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setMinimumWidth(280)
        self.search_input.textChanged.connect(
            self.on_search_changed
        )
        self.search_input.returnPressed.connect(
            self.search_globally
        )

        self.date_filter_combo = QtWidgets.QComboBox()
        self.date_filter_combo.addItems([
            "Wszystkie",
            "Dzisiaj",
            "Ostatnie 7 dni",
            "Ostatnie 30 dni",
        ])
        self.date_filter_combo.currentTextChanged.connect(
            self.on_date_filter_changed
        )

        self.sort_combo = QtWidgets.QComboBox()
        self.sort_combo.addItems(["Najnowsze", "Najstarsze"])
        self.sort_combo.currentTextChanged.connect(
            self.on_sort_changed
        )

        self.status_label = QtWidgets.QLabel(
            "Pobieranie wiadomości..."
        )

        self.message_list = QtWidgets.QListWidget()
        self.message_list.setMinimumWidth(320)
        self.message_list.setItemDelegate(MailListItemDelegate(self.message_list))

        self.message_list.currentItemChanged.connect(
            self.on_message_selected
        )

        self.message_list_container = QtWidgets.QWidget()

        message_list_layout = QtWidgets.QVBoxLayout(
            self.message_list_container
        )
        message_list_layout.setContentsMargins(0, 0, 0, 0)

        message_list_layout.addWidget(
            self.message_list
        )

        pagination_layout = QtWidgets.QHBoxLayout()

        self.previous_page_button = QtWidgets.QPushButton()
        self.previous_page_button.setFixedSize(36, 32)
        self.previous_page_button.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ArrowBack
            )
        )
        self.previous_page_button.setToolTip("Poprzednia strona")
        self.previous_page_button.clicked.connect(
            self.previous_page
        )

        self.page_label = QtWidgets.QLabel("Strona 1")
        self.page_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.next_page_button = QtWidgets.QPushButton()
        self.next_page_button.setFixedSize(36, 32)
        self.next_page_button.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ArrowForward
            )
        )
        self.next_page_button.setToolTip("Następna strona")
        self.next_page_button.clicked.connect(
            self.next_page
        )

        pagination_layout.addWidget(
            self.previous_page_button
        )
        pagination_layout.addStretch()
        pagination_layout.addWidget(
            self.page_label
        )
        pagination_layout.addStretch()
        pagination_layout.addWidget(
            self.next_page_button
        )

        message_list_layout.addLayout(
            pagination_layout
        )

        self.update_pagination()

        self.loading_overlay = QtWidgets.QWidget(
            self.message_list_container
        )

        overlay_layout = QtWidgets.QVBoxLayout(
            self.loading_overlay
        )

        overlay_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.loading_label = QtWidgets.QLabel(
            "Pobieranie wiadomości..."
        )

        self.loading_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.loading_progress = QtWidgets.QProgressBar()

        self.loading_progress.setRange(
            0,
            0
        )

        self.loading_progress.setFixedWidth(
            180
        )

        overlay_layout.addStretch()
        overlay_layout.addWidget(
            self.loading_label
        )
        overlay_layout.addWidget(
            self.loading_progress,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )
        overlay_layout.addStretch()

        self.loading_overlay.hide()

        self.subject_label = QtWidgets.QLabel(
            "Wybierz wiadomość"
        )

        self.subject_label.setProperty(
            "role",
            "Title"
        )

        self.subject_label.setWordWrap(True)
        # Temat to zwykły tekst z nagłówka maila - nie interpretujemy go jako HTML.
        self.subject_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)

        self.sender_label = QtWidgets.QLabel()
        self.sender_label.setWordWrap(True)
        self.sender_label.setTextFormat(QtCore.Qt.TextFormat.RichText)

        self.recipient_label = QtWidgets.QLabel()
        self.recipient_label.setWordWrap(True)
        self.recipient_label.setTextFormat(QtCore.Qt.TextFormat.RichText)

        self.date_label = QtWidgets.QLabel()
        self.date_label.setTextFormat(QtCore.Qt.TextFormat.RichText)

        self.open_gmail_button = QtWidgets.QPushButton(
            "Otwórz w Gmailu"
        )
        self.open_gmail_button.setEnabled(False)
        self.open_gmail_button.clicked.connect(
            self.open_current_message_in_gmail
        )

        header_line = QtWidgets.QFrame()

        header_line.setFrameShape(
            QtWidgets.QFrame.Shape.HLine
        )

        header_line.setObjectName(
            "sectionLine"
        )

        self.body = QtWidgets.QTextEdit()
        self.body.setReadOnly(True)

        self.attachments_label = QtWidgets.QLabel("Załączniki")
        self.attachments_label.setProperty("role", "Title")
        self.attachments_label.hide()

        self.attachments_widget = QtWidgets.QWidget()

        self.attachments_layout = QtWidgets.QVBoxLayout(
            self.attachments_widget
        )

        self.attachments_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        self.attachments_layout.setSpacing(4)

        self.attachments_widget.hide()

        message_layout = QtWidgets.QVBoxLayout()

        message_layout.setContentsMargins(
            16,
            0,
            0,
            0
        )

        message_layout.setSpacing(8)

        message_layout.addWidget(
            self.subject_label
        )

        message_layout.addWidget(
            self.open_gmail_button
        )

        message_layout.addWidget(
            self.sender_label
        )

        message_layout.addWidget(
            self.recipient_label
        )

        message_layout.addWidget(
            self.date_label
        )

        message_layout.addWidget(
            header_line
        )

        message_layout.addWidget(
            self.body,
            1
        )

        message_layout.addWidget(
            self.attachments_label
        )

        message_layout.addWidget(
            self.attachments_widget
        )

        message_widget = QtWidgets.QWidget()
        message_widget.setLayout(message_layout)

        self.message_container = QtWidgets.QWidget()

        message_container_layout = QtWidgets.QVBoxLayout(
            self.message_container
        )

        message_container_layout.setContentsMargins(
            0,
            0,
            0,
            0
        )

        message_container_layout.addWidget(
            message_widget
        )

        self.message_loading_overlay = QtWidgets.QWidget(
            self.message_container
        )

        message_loading_layout = QtWidgets.QVBoxLayout(
            self.message_loading_overlay
        )

        message_loading_layout.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.message_loading_label = QtWidgets.QLabel(
            "Pobieranie wiadomości..."
        )

        self.message_loading_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.message_loading_progress = QtWidgets.QProgressBar()

        self.message_loading_progress.setRange(
            0,
            0
        )

        self.message_loading_progress.setFixedWidth(
            180
        )

        message_loading_layout.addStretch()

        message_loading_layout.addWidget(
            self.message_loading_label
        )

        message_loading_layout.addWidget(
            self.message_loading_progress,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        message_loading_layout.addStretch()

        self.message_loading_overlay.hide()

        splitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal
        )

        splitter.addWidget(
            self.message_list_container
        )

        splitter.addWidget(
            self.message_container
        )

        splitter.setStretchFactor(
            0,
            0
        )

        splitter.setStretchFactor(
            1,
            1
        )

        splitter.setSizes([
            350,
            650
        ])

        main_layout.addWidget(title)
        main_layout.addLayout(folder_layout)
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(self.search_input, 1)
        search_layout.addWidget(self.global_search_button)
        search_layout.addWidget(self.date_filter_combo)
        search_layout.addWidget(self.sort_combo)
        main_layout.addLayout(search_layout)
        main_layout.addWidget(self.status_label)
        main_layout.addWidget(splitter, 1)

    def show_message_loading(self):
        self.message_loading_overlay.setGeometry(
            self.message_container.rect()
        )

        self.message_loading_overlay.raise_()
        self.message_loading_overlay.show()

    def hide_message_loading(self):
        self.message_loading_overlay.hide()



    def change_folder(self, label):
        if self.current_label == label:
            return

        if self.thread is not None:
            return

        self.current_label = label
        self.search_input.clear()
        self.global_search_query = ""
        self.reset_pagination()

        self.message_list.clear()
        self.clear_message()

        self.load_messages()

    def load_messages(self, force_refresh=False):
        if self.thread is not None:
            return

        cache = self.page_cache.setdefault(
            self.current_label,
            {}
        )

        # Przy zwykłej nawigacji najpierw korzystamy z cache.
        # Przycisk Odśwież przekazuje force_refresh=True.
        if not force_refresh and self.current_page in cache:
            cached = cache[self.current_page]

            self.messages = cached["messages"]
            self.next_page_token = cached.get("next_page_token")

            self.message_list.clear()
            self.clear_message()
            self.fill_message_list()
            self.update_pagination()

            self.update_message_status()
            return

        self._load_messages_from_api()

    def refresh_messages(self):
        # Odświeżamy aktualną stronę z Gmail API i zastępujemy
        # jej wpis w cache świeżymi danymi.
        self.load_messages(force_refresh=True)

    def _load_messages_from_api(self):
        self.message_list.clear()
        self.clear_message()

        self.show_loading()

        self.refresh_button.setEnabled(False)
        self.inbox_button.setEnabled(False)
        self.sent_button.setEnabled(False)
        self.update_pagination()

        if self.current_label == "INBOX":
            folder_name = "odebranych"
        else:
            folder_name = "wysłanych"

        self.status_label.setText(
            f"Pobieranie wiadomości {folder_name}..."
        )

        self.thread = QtCore.QThread(self)

        self.worker = MailLoader(
            label=(
                None
                if self.global_search_query
                else self.current_label
            ),
            max_results=self.page_size,
            page_token=self.page_tokens[
                self.current_page
            ],
            query=self.global_search_query,
        )

        self.worker.moveToThread(
            self.thread
        )

        self.thread.started.connect(
            self.worker.run
        )

        self.worker.finished.connect(
            self.on_messages_loaded
        )

        self.worker.error.connect(
            self.on_load_error
        )

        self.worker.finished.connect(
            self.thread.quit
        )

        self.worker.error.connect(
            self.thread.quit
        )

        self.worker.finished.connect(
            self.worker.deleteLater
        )

        self.worker.error.connect(
            self.worker.deleteLater
        )

        self.thread.finished.connect(
            self.on_thread_finished
        )

        self.thread.start()

    def on_messages_loaded(self, result):
        self.hide_loading()

        self.messages = result.get(
            "messages",
            []
        )

        self.next_page_token = result.get(
            "next_page_token"
        )

        self.page_cache.setdefault(
            self.current_label,
            {}
        )[self.current_page] = {
            "messages": self.messages,
            "next_page_token": self.next_page_token,
        }

        self.fill_message_list()
        self.update_pagination()

        self.update_message_status()

    def on_load_error(self, error):
        self.hide_loading()

        self.status_label.setText(
            "Nie udało się pobrać wiadomości."
        )

        QtWidgets.QMessageBox.critical(
            self,
            "Błąd Gmail API",
            error
        )

    def on_thread_finished(self):
        if self.thread is not None:
            self.thread.deleteLater()

        self.thread = None
        self.worker = None

        self.refresh_button.setEnabled(True)
        self.inbox_button.setEnabled(True)
        self.sent_button.setEnabled(True)
        self.update_pagination()

    def reset_pagination(self):
        self.current_page = 0
        self.page_tokens = [None]
        self.next_page_token = None
        self.update_pagination()

    def search_globally(self):
        query = self.search_input.text().strip()

        if self.thread is not None:
            return

        if query == self.global_search_query:
            self.on_search_changed(query)
            return

        self.global_search_query = query
        self.search_query = query
        self.current_page = 0
        self.page_tokens = [None]
        self.next_page_token = None
        self.page_cache[self.current_label] = {}
        self.load_messages(force_refresh=True)

    def on_date_filter_changed(self, value):
        self.date_filter = value
        self.fill_message_list()
        self.update_message_status()

    def on_sort_changed(self, value):
        self.sort_order = value
        self.fill_message_list()

    def _message_is_in_date_filter(self, message):
        if self.date_filter == "Wszystkie":
            return True

        timestamp = message.get("timestamp", 0)
        if not timestamp:
            try:
                message_date = datetime.strptime(
                    message.get("date", ""),
                    "%d.%m.%Y %H:%M",
                )
            except ValueError:
                return False
        else:
            message_date = datetime.fromtimestamp(timestamp / 1000)

        now = datetime.now()

        if self.date_filter == "Dzisiaj":
            return message_date.date() == now.date()

        days = 7 if self.date_filter == "Ostatnie 7 dni" else 30
        return message_date >= now - timedelta(days=days)

    def open_current_message_in_gmail(self):
        if not self.selected_message_id:
            return

        message = next(
            (
                message
                for message in self.messages
                if message.get("id") == self.selected_message_id
            ),
            None,
        )

        if message is None:
            return

        thread_id = message.get("thread_id") or message["id"]
        folder = "sent" if self.current_label == "SENT" else "inbox"
        webbrowser.open(
            f"https://mail.google.com/mail/u/0/#"
            f"{folder}/{thread_id}"
        )

    def update_pagination(self):
        if not hasattr(
            self,
            "previous_page_button"
        ):
            return

        loading = self.thread is not None

        self.previous_page_button.setEnabled(
            self.current_page > 0
            and not loading
        )

        self.next_page_button.setEnabled(
            bool(self.next_page_token)
            and not loading
        )

        self.page_label.setText(
            f"Strona {self.current_page + 1}"
        )

    def previous_page(self):
        if (
            self.thread is not None
            or self.current_page <= 0
        ):
            return

        self.current_page -= 1
        self.load_messages()

    def next_page(self):
        if (
            self.thread is not None
            or not self.next_page_token
        ):
            return

        next_index = self.current_page + 1

        if len(self.page_tokens) <= next_index:
            self.page_tokens.append(
                self.next_page_token
            )
        else:
            self.page_tokens[next_index] = (
                self.next_page_token
            )

        self.current_page = next_index
        self.load_messages()

    def fill_message_list(self):
        self.message_list.setUpdatesEnabled(False)

        try:
            self.message_list.clear()

            for message in self.get_visible_messages():
                item = QtWidgets.QListWidgetItem()
                if MailListItemWidget._message_has_excel_attachment(message):
                    item.setBackground(QtGui.QColor("#3c7444"))
                    item.setData(
                        QtCore.Qt.ItemDataRole.UserRole + 1,
                        True,
                    )

                item.setData(
                    QtCore.Qt.ItemDataRole.UserRole,
                    message
                )

                widget = MailListItemWidget(
                    message=message,
                    current_label=self.current_label
                )

                item.setSizeHint(
                    QtCore.QSize(
                        320,
                        100
                    )
                )

                self.message_list.addItem(
                    item
                )

                self.message_list.setItemWidget(
                    item,
                    widget
                )

        finally:
            self.message_list.setUpdatesEnabled(True)

        # Nie pobieramy automatycznie pełnej treści pierwszego maila.
        # Użytkownik wybiera wiadomość ręcznie. Dzięki temu zakończenie
        # workera listy nie nakłada się na start workera szczegółów.
        self.message_list.setCurrentRow(-1)
        self.clear_message()

    @staticmethod
    def message_matches_query(message, query):
        if not query:
            return True

        searchable_text = " ".join(
            str(message.get(field, ""))
            for field in (
                "subject",
                "sender",
                "recipient",
                "date",
                "preview",
            )
        )

        return query.casefold() in searchable_text.casefold()

    def get_visible_messages(self):
        visible_messages = [
            message
            for message in self.messages
            if self.message_matches_query(
                message,
                self.search_query,
            )
            and self._message_is_in_date_filter(message)
        ]

        return sorted(
            visible_messages,
            key=lambda message: message.get("timestamp", 0),
            reverse=self.sort_order == "Najnowsze",
        )

    def on_search_changed(self, query):
        self.search_query = query.strip()
        self.fill_message_list()
        self.update_message_status()

    def update_message_status(self):
        visible_count = len(self.get_visible_messages())
        total_count = len(self.messages)

        if self.search_query:
            self.status_label.setText(
                f"Wyświetlono {visible_count} z {total_count} "
                "wiadomości na tej stronie"
            )
            return

        folder_name = (
            "odebranych"
            if self.current_label == "INBOX"
            else "wysłanych"
        )
        self.status_label.setText(
            f"Pobrano wiadomości {folder_name}: "
            f"{total_count} | "
            f"Strona {self.current_page + 1}"
        )


    def clear_message(self):
        self.selected_message_id = None

        # Gdy żadna wiadomość nie jest wybrana, panel szczegółów
        # nie może pozostać w stanie "Pobieranie wiadomości...".
        self.hide_message_loading()

        self.subject_label.setText(
            "Brak wybranej wiadomości"
        )

        self.sender_label.clear()
        self.recipient_label.clear()
        self.date_label.clear()
        self.body.clear()
        self.open_gmail_button.setEnabled(False)

        self.attachments_label.hide()
        self.attachments_widget.hide()

    def on_message_selected(
            self,
            current,
            previous
    ):
        if current is None:
            return

        message = current.data(
            QtCore.Qt.ItemDataRole.UserRole
        )

        if not message:
            return

        if message.get("loaded"):
            self.selected_message_id = message["id"]
            self.hide_message_loading()
            self.show_message_detail(message)
            return

        self.clear_message()

        self.selected_message_id = message["id"]

        self.show_message_loading()

        self.load_message_detail(
            message["id"]
        )

    def load_message_detail(self, message_id):
        if self.detail_thread is not None:
            self.pending_message_id = message_id
            return

        self.pending_message_id = None
        self.loading_message_id = message_id

        self.detail_thread = QtCore.QThread(self)

        self.detail_worker = MessageDetailLoader(
            message_id
        )

        self.detail_worker.moveToThread(
            self.detail_thread
        )

        self.detail_thread.started.connect(
            self.detail_worker.run
        )

        self.detail_worker.finished.connect(
            self.on_message_detail_loaded
        )

        self.detail_worker.error.connect(
            self.on_message_detail_error
        )

        self.detail_worker.finished.connect(
            self.detail_thread.quit
        )

        self.detail_worker.error.connect(
            self.detail_thread.quit
        )

        self.detail_worker.finished.connect(
            self.detail_worker.deleteLater
        )

        self.detail_worker.error.connect(
            self.detail_worker.deleteLater
        )

        self.detail_thread.finished.connect(
            self.on_detail_thread_finished
        )

        self.detail_thread.start()

    def on_message_detail_loaded(self, message):
        for current in self.messages:
            if current["id"] == message["id"]:
                current.update(message)
                break

        if self.selected_message_id != message["id"]:
            return

        self.show_message_detail(
            message
        )

    def on_message_detail_error(self, error):
        if self.selected_message_id != self.loading_message_id:
            return

        self.hide_message_loading()

        QtWidgets.QMessageBox.critical(
            self,
            "Błąd Gmail API",
            error
        )

    def on_detail_thread_finished(self):
        thread = self.detail_thread

        self.detail_thread = None
        self.detail_worker = None
        self.loading_message_id = None

        if thread is not None:
            thread.deleteLater()

        pending_message_id = self.pending_message_id
        self.pending_message_id = None

        if (
                pending_message_id
                and pending_message_id == self.selected_message_id
        ):
            message = next(
                (
                    message
                    for message in self.messages
                    if message["id"] == pending_message_id
                ),
                None
            )

            if message is None:
                return

            if message.get("loaded"):
                self.show_message_detail(
                    message
                )
                return

            self.load_message_detail(
                pending_message_id
            )

    def show_message_detail(self, message):
        self.hide_message_loading()
        self.open_gmail_button.setEnabled(True)

        self.subject_label.setText(
            message["subject"]
        )

        self.sender_label.setText(
            f"<b>Od:</b> "
            f"{html.escape(message['sender'])}"
        )

        self.recipient_label.setText(
            f"<b>Do:</b> "
            f"{html.escape(message['recipient'])}"
        )

        self.date_label.setText(
            f"<b>Data:</b> "
            f"{html.escape(message['date'])}"
        )

        self.body.setPlainText(
            message.get("body", "")
        )

        self.show_attachments(
            message
        )

    def show_attachments(self, message):
        while self.attachments_layout.count():
            item = self.attachments_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        attachments = message.get(
            "attachments",
            []
        )

        if not attachments:
            self.attachments_label.hide()
            self.attachments_widget.hide()
            return

        self.attachments_label.show()
        self.attachments_widget.show()

        for attachment in attachments:
            row = QtWidgets.QWidget()

            row_layout = QtWidgets.QHBoxLayout(row)
            row_layout.setContentsMargins(0, 0, 0, 0)

            size = attachment.get("size", 0)

            size_text = self.format_file_size(size)

            filename_label = QtWidgets.QLabel(
                f"{attachment['filename']} "
                f"({size_text})"
            )

            mime_label = QtWidgets.QLabel(
                attachment.get(
                    "mime_type",
                    ""
                )
            )

            download_button = QtWidgets.QPushButton(
                "Pobierz"
            )

            download_button.clicked.connect(
                lambda checked=False,
                       m=message,
                       a=attachment:
                self.download_file(m, a)
            )

            preview_button = QtWidgets.QPushButton(
                "Podgląd"
            )

            preview_button.clicked.connect(
                lambda checked=False,
                       m=message,
                       a=attachment:
                self.preview_file(m, a)
            )

            report_button = None
            if attachment["filename"].lower().endswith((".xlsx", ".xlsm")):
                report_button = QtWidgets.QPushButton("Dodaj jako raport")
                report_button.clicked.connect(
                    lambda checked=False,
                           m=message,
                           a=attachment:
                    self.add_attachment_as_report(m, a)
                )

            row_layout.addWidget(filename_label)
            row_layout.addWidget(mime_label)

            row_layout.addStretch()

            row_layout.addWidget(
                preview_button
            )

            if report_button is not None:
                row_layout.addWidget(report_button)

            row_layout.addWidget(
                download_button
            )

            self.attachments_layout.addWidget(row)

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "loading_overlay"):
            self.loading_overlay.setGeometry(
                self.message_list_container.rect()
            )

        if hasattr(
                self,
                "message_loading_overlay"
        ):
            self.message_loading_overlay.setGeometry(
                self.message_container.rect()
            )

    def download_file(self, message, attachment):
        filename = attachment["filename"]

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Zapisz załącznik",
            filename
        )

        if not path:
            return

        try:
            data = download_attachment(
                message_id=message["id"],
                attachment_id=attachment["attachment_id"]
            )

            with open(path, "wb") as file:
                file.write(data)

            QtWidgets.QMessageBox.information(
                self,
                "Pobrano plik",
                f"Zapisano plik:\n{path}"
            )

        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd pobierania",
                str(error)
            )

    def add_attachment_as_report(self, message, attachment):
        filename = attachment["filename"]
        suffix = Path(filename).suffix.lower()
        temporary_path = None

        try:
            data = download_attachment(
                message_id=message["id"],
                attachment_id=attachment["attachment_id"],
            )
            with tempfile.NamedTemporaryFile(
                prefix="audio_opus_gmail_",
                suffix=suffix,
                delete=False,
            ) as temporary_file:
                temporary_file.write(data)
                temporary_path = temporary_file.name

            self.report_selected.emit(temporary_path)
        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd dodawania raportu",
                str(error),
            )
        finally:
            if temporary_path:
                try:
                    Path(temporary_path).unlink(missing_ok=True)
                except OSError:
                    pass

    def format_file_size(self, size):
        if size < 1024:
            return f"{size} B"

        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"

        return f"{size / (1024 * 1024):.1f} MB"

    def show_loading(self):
        if self.current_label == "INBOX":
            text = "Pobieranie odebranych..."
        else:
            text = "Pobieranie wysłanych..."

        self.loading_label.setText(text)

        self.loading_overlay.setGeometry(
            self.message_list_container.rect()
        )

        self.loading_overlay.raise_()
        self.loading_overlay.show()

    def hide_loading(self):
        self.loading_overlay.hide()

    def closeEvent(self, event):
        for thread in (
                self.thread,
                self.preview_thread,
                self.detail_thread,
                self.auth_thread
        ):
            if thread is not None:
                thread.quit()
                thread.wait(5000)

        super().closeEvent(event)

    def on_preview_loaded(self, data):
        self.preview_loading.close()

        attachment = self.preview_attachment

        window = AttachmentPreviewWindow(
            filename=attachment["filename"],
            data=data,
            mime_type=attachment.get("mime_type", ""),
            parent=self
        )

        window.exec()

    def on_preview_error(self, error):
        self.preview_loading.close()

        QtWidgets.QMessageBox.critical(
            self,
            "Błąd podglądu",
            error
        )

    def on_preview_thread_finished(self):
        self.preview_thread.deleteLater()

        self.preview_thread = None
        self.preview_worker = None
        self.preview_loading = None

        self.preview_message = None
        self.preview_attachment = None

    def preview_file(self, message, attachment):
        self.preview_message = message
        self.preview_attachment = attachment

        self.preview_loading = QtWidgets.QProgressDialog(
            "Ładowanie podglądu...",
            None,
            0,
            0,
            self
        )

        self.preview_loading.setWindowTitle(
            "Podgląd załącznika"
        )

        self.preview_loading.setCancelButton(None)

        self.preview_loading.setMinimumDuration(0)

        self.preview_loading.setWindowModality(
            QtCore.Qt.WindowModality.WindowModal
        )
        self.preview_loading.show()

        QtWidgets.QApplication.processEvents()

        self.preview_thread = QtCore.QThread(self)

        self.preview_worker = AttachmentLoader(
            message_id=message["id"],
            attachment_id=attachment["attachment_id"]
        )

        self.preview_worker.moveToThread(
            self.preview_thread
        )

        self.preview_thread.started.connect(
            self.preview_worker.run
        )

        self.preview_worker.finished.connect(
            self.on_preview_loaded
        )

        self.preview_worker.error.connect(
            self.on_preview_error
        )

        self.preview_worker.finished.connect(
            self.preview_thread.quit
        )

        self.preview_worker.error.connect(
            self.preview_thread.quit
        )

        self.preview_worker.finished.connect(
            self.preview_worker.deleteLater
        )

        self.preview_worker.error.connect(
            self.preview_worker.deleteLater
        )

        self.preview_thread.finished.connect(
            self.on_preview_thread_finished
        )

        self.preview_thread.start()