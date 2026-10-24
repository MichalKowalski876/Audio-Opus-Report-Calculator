from PySide6 import QtWidgets, QtCore
from PySide6.QtGui import QAction, QGuiApplication, QShortcut

from GUI.style import branding

from GUI.Tabs.ClientsTab import ClientsTab
from GUI.Tabs.ProductsTab import ProductsTab
from GUI.Tabs.StreamingTab import StreamingTab
from GUI.Tabs.ReportTab import ReportTab
from GUI.Tabs.StartTab import StartTab
from GUI.Tabs.AssistantTab import AssistantTab
from GUI.Window.HelpWindow import HelpWindow
from GUI.Window.SettingsWindow import SettingsWindow
from GUI.Widgets.Settings.ShortcutManager import ShortcutManager
from GUI.Tabs.DebugTab import DebugTab
from core import backup_reminder
from core import debug_config
from core import paths


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, defer_show=False):
        super().__init__()
        self._defer_show = defer_show

        self.setWindowTitle("Projekt Audio Opus")
        self.setMinimumSize(900, 600)

        self.was_maximized_before_fullscreen = False
        self.load_window_state()

        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage("Gotowe")

        self.shortcut_manager = ShortcutManager()
        self.tab_shortcuts = []

        self.clients_tab = ClientsTab()
        self.products_tab = ProductsTab()
        self.streaming_tab = StreamingTab()
        self.report_tab = ReportTab()
        self.debug_tab = DebugTab()
        self.start_tab = StartTab(
            self.clients_tab,
            self.products_tab,
            self.streaming_tab,
            self.report_tab,
        )
        self.assistant_tab = AssistantTab()

        self.panel_label = QtWidgets.QLabel("Panele")
        self.panel_label.setObjectName("sidebarTitle")
        self.panel_label.setProperty("role", "Title")

        brand_widget = self._build_brand_header()

        brand_line = QtWidgets.QFrame()
        brand_line.setObjectName("sidebarDivider")
        brand_line.setFrameShape(QtWidgets.QFrame.HLine)
        brand_line.setFrameShadow(QtWidgets.QFrame.Plain)

        self.stack = QtWidgets.QStackedWidget()
        self.stack.addWidget(self.start_tab)
        self.stack.addWidget(self.clients_tab)
        self.stack.addWidget(self.products_tab)
        self.stack.addWidget(self.streaming_tab)
        self.stack.addWidget(self.report_tab)
        self.stack.addWidget(self.debug_tab)
        self.stack.addWidget(self.assistant_tab)

        self.page_title = QtWidgets.QLabel("Panel Klientów")
        self.page_title.setObjectName("pageTitle")
        self.page_title.setProperty("role", "Title")
        self.page_title.setContentsMargins(8, 0, 0, 0)

        top_line = QtWidgets.QFrame()
        top_line.setObjectName("sectionLine")
        top_line.setFrameShape(QtWidgets.QFrame.HLine)
        top_line.setFrameShadow(QtWidgets.QFrame.Plain)

        self.start_button = QtWidgets.QPushButton("Start")
        self.clients_button = QtWidgets.QPushButton("Klienci")
        self.products_button = QtWidgets.QPushButton("Produkty")
        self.streaming_button = QtWidgets.QPushButton("Platformy")
        self.report_button = QtWidgets.QPushButton("Raport")
        self.debug_button = QtWidgets.QPushButton("Debug")
        self.assistant_button = QtWidgets.QPushButton("Asystent")

        self.settings_button = QtWidgets.QPushButton("Ustawienia")
        self.help_button = QtWidgets.QPushButton("Pomoc")

        for button in (
            self.start_button,
            self.clients_button,
            self.products_button,
            self.streaming_button,
            self.report_button,
            self.settings_button,
            self.help_button,
            self.debug_button,
            self.assistant_button,
        ):
            button.setObjectName("navButton")
            button.setMinimumHeight(38)

        self.start_button.clicked.connect(
            lambda: self.change_page(self.start_tab, "Start")
        )

        self.clients_button.clicked.connect(
            lambda: self.change_page(self.clients_tab, "Panel Klientów")
        )

        self.products_button.clicked.connect(
            lambda: self.change_page(self.products_tab, "Panel Produktów")
        )

        self.streaming_button.clicked.connect(
            lambda: self.change_page(self.streaming_tab, "Panel Platform")
        )

        self.report_button.clicked.connect(
            lambda: self.change_page(self.report_tab, "Raporty")
        )

        self.debug_button.clicked.connect(
            lambda: self.change_page(self.debug_tab, "Debug")
        )

        self.assistant_button.clicked.connect(
            lambda: self.change_page(self.assistant_tab, "Asystent")
        )

        self.settings_button.clicked.connect(self.open_settings)
        self.help_button.clicked.connect(self.open_help)

        self.add_client_action = QAction("Dodaj klienta", self)
        self.add_client_action.setShortcut(self.shortcut_manager.get_shortcut("add_client"))
        self.add_client_action.triggered.connect(self.clients_tab.add_client)
        self.addAction(self.add_client_action)

        self.add_product_action = QAction("Dodaj produkt", self)
        self.add_product_action.setShortcut(self.shortcut_manager.get_shortcut("add_product"))
        self.add_product_action.triggered.connect(self.products_tab.add_product)
        self.addAction(self.add_product_action)

        self.send_report_action = QAction("Wyślij raport na e-mail", self)
        self.send_report_action.setShortcut(self.shortcut_manager.get_shortcut("send_report"))
        self.send_report_action.triggered.connect(self.report_tab.on_send_clicked)
        self.addAction(self.send_report_action)

        self.open_calculator_action = QAction("Otwórz kalkulator", self)
        self.open_calculator_action.setShortcut(self.shortcut_manager.get_shortcut("open_calculator"))
        self.open_calculator_action.triggered.connect(self.report_tab.open_commission_calculator)
        self.addAction(self.open_calculator_action)

        self.fullscreen_action = QAction("Pełny ekran", self)
        self.fullscreen_action.setShortcut("F11")
        self.fullscreen_action.triggered.connect(self.toggle_fullscreen)
        self.addAction(self.fullscreen_action)

        self.minimize_action = QAction("Minimalizuj okno", self)
        self.minimize_action.setShortcut("Ctrl+M")
        self.minimize_action.triggered.connect(self.minimize_window)
        self.addAction(self.minimize_action)

        sidebar = QtWidgets.QVBoxLayout()
        sidebar.setContentsMargins(10, 10, 10, 12)
        sidebar.setSpacing(3)

        sidebar.addWidget(brand_widget)
        sidebar.addWidget(brand_line)
        sidebar.addSpacing(4)
        sidebar.addWidget(self.panel_label)

        sidebar.addWidget(self.start_button)
        sidebar.addWidget(self.clients_button)
        sidebar.addWidget(self.products_button)
        sidebar.addWidget(self.streaming_button)
        sidebar.addWidget(self.report_button)
        sidebar.addWidget(self.debug_button)
        sidebar.addWidget(self.assistant_button)

        self.debug_button.setVisible(debug_config.is_enabled())

        sidebar.addStretch()

        bottom_line = QtWidgets.QFrame()
        bottom_line.setObjectName("sidebarDivider")
        bottom_line.setFrameShape(QtWidgets.QFrame.HLine)
        bottom_line.setFrameShadow(QtWidgets.QFrame.Plain)

        sidebar.addSpacing(4)
        sidebar.addWidget(bottom_line)
        sidebar.addSpacing(4)

        sidebar.addWidget(self.settings_button)
        sidebar.addWidget(self.help_button)

        sidebar_widget = QtWidgets.QWidget()
        sidebar_widget.setObjectName("sidebar")
        sidebar_widget.setLayout(sidebar)
        sidebar_widget.setFixedWidth(224)

        content = QtWidgets.QVBoxLayout()
        content.setContentsMargins(6, 10, 12, 12)
        content.setSpacing(10)

        content.addWidget(self.page_title)
        content.addWidget(top_line)
        content.addWidget(self.stack)

        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(sidebar_widget)
        layout.addLayout(content)

        container = QtWidgets.QWidget()
        container.setObjectName("appContainer")
        container.setLayout(layout)

        self._nav_buttons = {
            self.start_tab: self.start_button,
            self.clients_tab: self.clients_button,
            self.products_tab: self.products_button,
            self.streaming_tab: self.streaming_button,
            self.report_tab: self.report_button,
            self.debug_tab: self.debug_button,
            self.assistant_tab: self.assistant_button,
        }

        self.setCentralWidget(container)

        self.setup_tab_shortcuts()

        self.change_page(self.start_tab, "Start")

        QtCore.QTimer.singleShot(1500, self.maybe_show_backup_reminder)

    # ------------------------------------------------------------------ brand
    _BRAND_LOGO_HEIGHT = 30

    def _build_brand_header(self):
        """Nagłówek paska bocznego: znak + nazwa + podpis."""

        v_center = QtCore.Qt.AlignmentFlag.AlignVCenter

        widget = QtWidgets.QWidget()
        widget.setObjectName("brandWidget")

        row = QtWidgets.QHBoxLayout(widget)
        row.setContentsMargins(14, 14, 12, 14)
        row.setSpacing(12)
        row.setAlignment(v_center)

        self.brand_logo = QtWidgets.QLabel()
        self.brand_logo.setObjectName("brandLogo")
        self.brand_logo.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents
        )
        self._refresh_brand_logo()

        name = QtWidgets.QLabel("Audio Opus")
        name.setObjectName("brandName")
        caption = QtWidgets.QLabel("Panel zarządzania")
        caption.setObjectName("brandCaption")

        text_column = QtWidgets.QVBoxLayout()
        text_column.setContentsMargins(0, 0, 0, 0)
        text_column.setSpacing(3)
        text_column.addWidget(name)
        text_column.addWidget(caption)

        text_widget = QtWidgets.QWidget()
        text_widget.setLayout(text_column)

        # Wyrównanie w pionie: dorównujemy wysokość "pudełka" znaku do
        # wysokości bloku tekstu, żeby AlignVCenter złożył je środek w
        # środek niezależnie od fontu i skali ekranu.
        block_height = (
            name.sizeHint().height()
            + text_column.spacing()
            + caption.sizeHint().height()
        )
        logo_height = self.brand_logo.pixmap().deviceIndependentSize().height()
        top_pad = max(0, round((block_height - logo_height) / 2))
        self.brand_logo.setContentsMargins(0, top_pad, 0, 0)

        row.addWidget(self.brand_logo, 0, v_center)
        row.addWidget(text_widget, 0, v_center)
        row.addStretch()

        return widget

    def _refresh_brand_logo(self):
        """Rysuje znak w rozdzielczości aktualnego ekranu (ostrość na HiDPI)."""

        if getattr(self, "brand_logo", None) is None:
            return

        screen = self.screen() or QGuiApplication.primaryScreen()
        dpr = screen.devicePixelRatio() if screen is not None else 1.0
        self.brand_logo.setPixmap(
            branding.logo_pixmap(self._BRAND_LOGO_HEIGHT, dpr)
        )

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh_brand_logo()

    def show_status(self, message):
        self.statusBar().showMessage(message, 2500)

    def change_page(self, widget, title):
        self.stack.setCurrentWidget(widget)
        self.page_title.setText(title)
        self.show_status(f"Otwarto: {title}")
        for tab, button in self._nav_buttons.items():
            active = tab is widget
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
        self.update()

    def setup_tab_shortcuts(self):
        for shortcut in self.tab_shortcuts:
            shortcut.deleteLater()
        self.tab_shortcuts.clear()

        widgets = [
            (self.clients_tab, "Panel Klientów"),
            (self.products_tab, "Panel Produktów"),
            (self.streaming_tab, "Panel Platform"),
            (self.report_tab, "Raporty"),
        ]

        tab_mapping = [
            ("switch_clients", 0),
            ("switch_products", 1),
            ("switch_streaming", 2),
            ("switch_reports", 3),
        ]

        for action_name, index in tab_mapping:
            sequence = self.shortcut_manager.get_shortcut(action_name)
            if not sequence or sequence.isEmpty():
                continue

            shortcut = QShortcut(sequence, self)
            shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)

            widget, title = widgets[index]
            shortcut.activated.connect(
                lambda checked=False, w=widget, t=title: self.change_page(w, t)
            )
            self.tab_shortcuts.append(shortcut)

    def update_shortcuts(self):
        self.add_client_action.setShortcut(self.shortcut_manager.get_shortcut("add_client"))
        self.add_product_action.setShortcut(self.shortcut_manager.get_shortcut("add_product"))
        self.send_report_action.setShortcut(self.shortcut_manager.get_shortcut("send_report"))
        self.open_calculator_action.setShortcut(self.shortcut_manager.get_shortcut("open_calculator"))
        self.setup_tab_shortcuts()

    def open_settings(self, initial_section=0):
        settings_window = SettingsWindow(
            self.shortcut_manager, initial_section=initial_section
        )
        settings_window.shortcuts_changed.connect(self.update_shortcuts)
        settings_window.data_imported.connect(self.reload_databases)
        settings_window.exec()

        self.update_debug_visibility()

    def open_data_settings(self):
        self.open_settings(initial_section=SettingsWindow.DATA_SECTION_INDEX)

    def reload_databases(self):
        """Odświeża zakładki po wczytaniu kopii bazy (Ustawienia -> Dane)."""
        for tab in (self.clients_tab, self.products_tab, self.streaming_tab):
            reload_tab = getattr(tab, "reload", None)
            if not callable(reload_tab):
                continue
            try:
                reload_tab()
            except Exception as error:  # zła kopia nie może wywalić okna
                print(f"Nie udało się odświeżyć zakładki po wczytaniu danych: {error}")

        self.show_status("Wczytano dane z kopii bazy")

    def open_help(self):
        help_window = HelpWindow()
        help_window.exec()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            if self.was_maximized_before_fullscreen:
                self.showMaximized()
            else:
                self.showNormal()
        else:
            self.was_maximized_before_fullscreen = self.isMaximized()
            self.showFullScreen()

    def minimize_window(self):
        """Minimalizuje okno - dziala tez w trybie pelnoekranowym (brak
        paska tytulu), gdzie natywny przycisk minimalizacji jest niedostepny."""
        self.showMinimized()

    def load_window_state(self):
        # Okno zawsze startuje zmaksymalizowane - bez pamietania rozmiaru.
        if not self._defer_show:
            self.showMaximized()

    def maybe_show_backup_reminder(self):
        """Ostrzega, gdy ostatnia kopia zapasowa bazy jest starsza niż
        backup_reminder.MAX_BACKUP_AGE (albo nigdy jej nie zrobiono)."""

        if not backup_reminder.should_remind():
            return

        message_box = QtWidgets.QMessageBox(self)
        message_box.setIcon(QtWidgets.QMessageBox.Icon.Warning)
        message_box.setWindowTitle("Kopia zapasowa bazy danych")
        message_box.setText(
            "Kopia zapasowa bazy danych jest nieaktualna lub nie została "
            "jeszcze zrobiona.\n\n"
            "Po kliknięciu OK zostaniesz od razu przekierowany do sekcji "
            "Ustawienia -> Dane, gdzie możesz zrobić kopię."
        )
        message_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        message_box.exec()

        self.open_data_settings()

    def update_debug_visibility(self):
        enabled = debug_config.is_enabled()

        self.debug_button.setVisible(enabled)

        if not enabled and self.stack.currentWidget() is self.debug_tab:
            self.change_page(
                self.clients_tab,
                "Panel Klientów"
            )