from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from GUI.Widgets.Buttons.Help.HelpButton import HelpButton
from GUI.Widgets.Dialogs.AddBookDialog import AddBookDialog
from GUI.Widgets.Dialogs.ManualPlatformReportDialog import (
    ManualPlatformReportDialog,
    prompt_add_streaming_platform,
)
from GUI.Widgets.Dialogs.MonthlyReportTransactionsDialog import (
    MonthlyReportTransactionsDialog,
)
from GUI.Widgets.Dialogs.ReportCalculationDialog import (
    ReportCalculationDialog,
)
from GUI.Widgets.Dialogs.ReportContentsDialog import ReportContentsDialog
from GUI.Widgets.Reports import ExcelCellPickerPanel, ReportColumnMappingPanel
from GUI.Widgets.Tutorial import GuidedTutorial, TutorialStep
from core import database_controller
from platforms.manual import (
    ManualReportError,
    delete_streaming_platform,
    load_streaming_platforms,
    rename_streaming_platform,
)
from platforms.report_calculator import (
    ReportCalculationError,
    books_linked_to_report,
    delete_imported_report_data,
    forget_report_book_links,
    record_added_book,
    relink_unmatched_rows,
)
from platforms.report_viewer import (
    ReportViewerError,
    list_book_reports,
    list_monthly_book_reports,
    list_monthly_report_transactions,
    list_quarterly_book_reports,
    load_book_report_details,
)
from platforms.reports import (
    PLATFORM_REPORTS_ROOT,
    ReportFileError,
    list_trashed_reports,
    move_report_to_year,
    move_report_to_trash,
    permanently_delete_trashed_report,
    restore_report_from_trash,
)
from platforms.xlsx_reports import analyze_report_file, scan_report_directory


def _report_amount_text(value):
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ")


def _report_quantity_text(value):
    if value is None:
        return "—"
    number = float(value)
    return str(int(number)) if number.is_integer() else f"{number:g}"


class StreamingTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        # Debounce filtrów – O(rows) leci raz po ustaniu pisania,
        # a nie przy każdym znaku.
        self._overview_filter_timer = QtCore.QTimer(self)
        self._overview_filter_timer.setSingleShot(True)
        self._overview_filter_timer.setInterval(120)
        self._overview_filter_timer.timeout.connect(self.filter_overview_reports)

        # Cache znormalizowanych pól filtrowanych.
        self._overview_filter_cache = []
        self._pending_unmatched_entries = []
        self._pending_unmatched_year = None

        root_layout = QtWidgets.QVBoxLayout(self)
        root_layout.setContentsMargins(24, 20, 24, 20)
        root_layout.setSpacing(14)

        self.help_button = HelpButton("streamings", "Platformy")
        self.tutorial_toggle = QtWidgets.QPushButton("Kroki")
        self.tutorial_toggle.setCheckable(True)
        self.tutorial_toggle.setFixedHeight(30)
        self.tutorial_toggle.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Minimum,
            QtWidgets.QSizePolicy.Policy.Fixed,
        )
        self.tutorial_toggle.setStyleSheet("padding: 4px 10px;")
        self.tutorial_toggle.setToolTip(
            "Włącz lub wyłącz tutorial importu raportu"
        )

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.setSpacing(6)
        top_layout.addStretch()
        top_layout.addWidget(self.tutorial_toggle)
        top_layout.addWidget(self.help_button)
        root_layout.addLayout(top_layout)

        self.mode_stack = QtWidgets.QStackedWidget()
        self.mode_selection_page = self._create_mode_selection_page()
        self.calculation_page = self._create_calculation_page()
        # Zgodność ze starszą nawigacją: lista plików jest teraz bezpośrednio
        # ekranem „Przelicz Raporty”, a nie osobną stroną.
        self.report_files_page = self.calculation_page
        self.report_column_mapping_page = ReportColumnMappingPanel()
        self.excel_cell_picker_page = ExcelCellPickerPanel()
        self.report_trash_page = self._create_report_trash_page()
        self.mode_stack.addWidget(self.mode_selection_page)
        self.mode_stack.addWidget(self.calculation_page)
        self.mode_stack.addWidget(self.report_column_mapping_page)
        self.mode_stack.addWidget(self.excel_cell_picker_page)
        self.mode_stack.addWidget(self.report_trash_page)
        root_layout.addWidget(self.mode_stack, 1)

        self.report_column_mapping_page.back_requested.connect(
            self.show_report_files_page
        )
        self.report_column_mapping_page.cell_pick_requested.connect(
            self.show_excel_cell_picker
        )
        self.report_column_mapping_page.mapping_saved.connect(
            self.on_report_column_mapping_saved
        )
        self.excel_cell_picker_page.back_requested.connect(
            self.show_report_column_mapping_page
        )
        self.excel_cell_picker_page.cell_selected.connect(
            self.on_excel_header_cell_selected
        )

        self._report_tutorial_steps = {
            self.mode_selection_page: [
                TutorialStep(
                    self.add_platform_button,
                    "Dodaj platformę",
                    "Dodaj platformę, z której pochodzi raport.",
                ),
                TutorialStep(
                    self.calculation_mode_button,
                    "Przelicz Raporty",
                    "Przejdź do importowania i przeliczania raportów.",
                ),
            ],
            self.calculation_page: [
                TutorialStep(
                    self.manual_add_report_button,
                    "Dodaj raport",
                    "Wybierz platformę, rok i plik Excel.",
                ),
                TutorialStep(
                    self.map_report_columns_button,
                    "Dopasuj kolumny",
                    "Zaznacz czerwony raport i dopasuj jego kolumny.",
                ),
                TutorialStep(
                    self.manual_calculate_reports_button,
                    "Przelicz raport",
                    "Wybierz rok i platformy, a następnie przelicz raporty.",
                ),
            ],
            self.report_column_mapping_page: [
                TutorialStep(
                    tuple(self.report_column_mapping_page.excel_buttons.values()),
                    "Wybierz komórkę z Excela",
                    "Kliknij ikonę Excela i wskaż właściwy nagłówek.",
                ),
                TutorialStep(
                    self.report_column_mapping_page.save_button,
                    "Zapisz",
                    "Zapisz konfigurację kolumn raportu.",
                ),
            ],
        }
        self.report_tutorial = GuidedTutorial(self)
        self.tutorial_toggle.toggled.connect(self._toggle_report_tutorial)
        self.report_tutorial.active_changed.connect(
            self._sync_tutorial_toggle
        )
        self.add_platform_button.clicked.connect(
            self._advance_overview_tutorial
        )
        self.manual_add_report_button.clicked.connect(
            self._advance_calculation_tutorial
        )
        self.show_mode_selection()

    def _toggle_report_tutorial(self, enabled):
        if enabled:
            current_page = self.mode_stack.currentWidget()
            steps = self._report_tutorial_steps.get(
                current_page,
                [],
            )
            self.report_tutorial.set_steps(
                steps,
                show_all=True,
            )
            self.report_tutorial.start()
        else:
            self.report_tutorial.stop()

    def _sync_tutorial_toggle(self, enabled):
        blocker = QtCore.QSignalBlocker(self.tutorial_toggle)
        self.tutorial_toggle.setChecked(enabled)
        del blocker

    def _show_tutorial_steps_for(self, page, index=0):
        if not self.report_tutorial.is_active:
            return
        steps = self._report_tutorial_steps.get(page, [])
        if not steps:
            self.report_tutorial.pause()
            return
        self.report_tutorial.set_steps(
            steps,
            index=index,
            show_all=True,
        )

    def _advance_overview_tutorial(self):
        if (
            self.report_tutorial.is_active
            and self.mode_stack.currentWidget() is self.mode_selection_page
            and self.report_tutorial.current_index == 0
        ):
            self.report_tutorial.next()

    def _advance_calculation_tutorial(self):
        if (
            self.report_tutorial.is_active
            and self.mode_stack.currentWidget() is self.calculation_page
            and self.report_tutorial.current_index == 0
        ):
            self.report_tutorial.next()

    def _create_mode_selection_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.platform_reports_splitter = QtWidgets.QSplitter(
            QtCore.Qt.Orientation.Horizontal
        )
        self.platform_reports_splitter.setChildrenCollapsible(False)
        self._platform_splitter_user_resized = False

        self.platforms_panel = QtWidgets.QWidget()
        self.platforms_panel.setMinimumWidth(150)
        platforms_layout = QtWidgets.QVBoxLayout(self.platforms_panel)
        platforms_layout.setContentsMargins(0, 0, 10, 0)
        platforms_layout.setSpacing(10)

        platforms_title = QtWidgets.QLabel("Platformy")
        platforms_title.setProperty("role", "Title")
        platforms_layout.addWidget(platforms_title)

        self.add_platform_button = QtWidgets.QPushButton("Dodaj platformę")
        self.add_platform_button.clicked.connect(self.add_platform_from_overview)
        platforms_layout.addWidget(self.add_platform_button)

        platform_actions = QtWidgets.QHBoxLayout()
        platform_actions.setSpacing(6)
        self.edit_platform_button = QtWidgets.QPushButton("Edytuj")
        self.edit_platform_button.setEnabled(False)
        self.edit_platform_button.clicked.connect(self.edit_selected_platform)
        platform_actions.addWidget(self.edit_platform_button)
        self.delete_platform_button = QtWidgets.QPushButton("Usuń")
        self.delete_platform_button.setEnabled(False)
        self.delete_platform_button.clicked.connect(self.delete_selected_platform)
        platform_actions.addWidget(self.delete_platform_button)
        platforms_layout.addLayout(platform_actions)

        self.platforms_table = QtWidgets.QTableWidget(0, 1)
        self.platforms_table.setHorizontalHeaderLabels(["Nazwa platformy"])
        self.platforms_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.platforms_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.platforms_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.platforms_table.setAlternatingRowColors(True)
        self.platforms_table.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.platforms_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.platforms_table.verticalHeader().setVisible(False)
        self.platforms_table.horizontalHeader().setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Interactive,
        )
        self.platforms_table.horizontalHeader().setStretchLastSection(True)
        self.platforms_table.itemSelectionChanged.connect(
            self._update_platform_action_buttons
        )
        self.platforms_table.itemDoubleClicked.connect(
            self.edit_selected_platform
        )
        platforms_layout.addWidget(self.platforms_table, 1)

        self.platforms_status_label = QtWidgets.QLabel("")
        self.platforms_status_label.setWordWrap(True)
        self.platforms_status_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )
        self.platforms_status_label.hide()
        platforms_layout.addWidget(self.platforms_status_label)

        reports_panel = QtWidgets.QWidget()
        reports_layout = QtWidgets.QVBoxLayout(reports_panel)
        reports_layout.setContentsMargins(10, 0, 0, 0)
        reports_layout.setSpacing(10)

        reports_header = QtWidgets.QHBoxLayout()
        reports_title = QtWidgets.QLabel("Raporty")
        reports_title.setProperty("role", "Title")
        reports_header.addWidget(reports_title)
        reports_header.addStretch()

        self.calculation_mode_button = QtWidgets.QPushButton("Przelicz Raporty")
        self.calculation_mode_button.setProperty("role", "PlatformMode")
        self.calculation_mode_button.setMinimumWidth(180)
        self.calculation_mode_button.clicked.connect(self.show_calculation_page)
        reports_header.addWidget(self.calculation_mode_button)
        reports_layout.addLayout(reports_header)

        self.overview_reports_label = QtWidgets.QLabel("Raporty miesięczne")
        self.overview_reports_label.setProperty("role", "SectionTitle")
        reports_layout.addWidget(self.overview_reports_label)

        self.overview_filters_layout = QtWidgets.QGridLayout()
        self.overview_filters_layout.setHorizontalSpacing(12)
        self.overview_filters_layout.setVerticalSpacing(4)

        self.overview_book_filter = QtWidgets.QLineEdit()
        self.overview_book_filter.setPlaceholderText("Filtruj po nazwie...")
        self.overview_isbn_filter = QtWidgets.QLineEdit()
        self.overview_isbn_filter.setPlaceholderText("Filtruj po ISBN...")
        self.overview_period_filter = QtWidgets.QLineEdit()
        self.overview_period_filter.setPlaceholderText("Filtruj po miesiącu...")
        self.overview_client_filter = QtWidgets.QLineEdit()
        self.overview_client_filter.setPlaceholderText("Filtruj po kliencie...")

        overview_filter_fields = (
            ("Nazwa książki:", self.overview_book_filter),
            ("ISBN:", self.overview_isbn_filter),
            ("Miesiąc:", self.overview_period_filter),
            ("Klient:", self.overview_client_filter),
        )
        for column, (label_text, field) in enumerate(overview_filter_fields):
            label = QtWidgets.QLabel(label_text)
            self.overview_filters_layout.addWidget(label, 0, column)
            if field is self.overview_period_filter:
                self.overview_period_filter_label = label
            self.overview_filters_layout.addWidget(field, 1, column)
            self.overview_filters_layout.setColumnStretch(column, 1)
            field.textChanged.connect(self._schedule_overview_filter)
        reports_layout.addLayout(self.overview_filters_layout)

        self.overview_reports_table = QtWidgets.QTableWidget(0, 8)
        self.overview_reports_table.setHorizontalHeaderLabels(
            [
                "Nazwa książki",
                "ISBN",
                "Miesiąc",
                "Klient",
                "Platformy",
                "Ilość",
                "Netto",
                "Brutto",
            ]
        )
        self.overview_reports_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.overview_reports_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.overview_reports_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.overview_reports_table.setAlternatingRowColors(True)
        self.overview_reports_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.overview_reports_table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.overview_reports_table.verticalHeader().setVisible(False)
        self.overview_reports_table.itemDoubleClicked.connect(
            self.open_overview_report_details
        )
        overview_header = self.overview_reports_table.horizontalHeader()
        overview_header.setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Stretch,
        )
        overview_header.setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
        )
        overview_header.setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
        )
        overview_header.setSectionResizeMode(
            3,
            QtWidgets.QHeaderView.ResizeMode.Stretch,
        )
        for column in range(4, 8):
            overview_header.setSectionResizeMode(
                column,
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            )
        self.overview_reports_table.setColumnHidden(5, True)
        reports_layout.addWidget(self.overview_reports_table, 1)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(8)
        controls_layout.addWidget(QtWidgets.QLabel("Widok:"))

        self.overview_monthly_button = QtWidgets.QPushButton("Raporty miesięczne")
        self.overview_monthly_button.setCheckable(True)
        self.overview_yearly_button = QtWidgets.QPushButton("Raporty roczne")
        self.overview_yearly_button.setCheckable(True)
        self.overview_quarterly_button = QtWidgets.QPushButton("Raporty kwartalne")
        self.overview_quarterly_button.setCheckable(True)
        self.overview_view_group = QtWidgets.QButtonGroup(self)
        self.overview_view_group.setExclusive(True)
        self.overview_view_group.addButton(self.overview_monthly_button)
        self.overview_view_group.addButton(self.overview_yearly_button)
        self.overview_view_group.addButton(self.overview_quarterly_button)
        self.overview_monthly_button.setChecked(True)
        self.overview_monthly_button.clicked.connect(
            lambda _checked=False: self.set_overview_report_view("monthly")
        )
        self.overview_yearly_button.clicked.connect(
            lambda _checked=False: self.set_overview_report_view("yearly")
        )
        self.overview_quarterly_button.clicked.connect(
            lambda _checked=False: self.set_overview_report_view("quarterly")
        )
        controls_layout.addWidget(self.overview_monthly_button)
        controls_layout.addWidget(self.overview_yearly_button)
        controls_layout.addWidget(self.overview_quarterly_button)
        controls_layout.addStretch()
        reports_layout.addLayout(controls_layout)

        self._overview_monthly_reports = []
        self._overview_yearly_reports = []
        self._overview_quarterly_reports = []
        self._overview_report_view = "monthly"

        self.platform_reports_splitter.addWidget(self.platforms_panel)
        self.platform_reports_splitter.addWidget(reports_panel)
        self.platform_reports_splitter.setStretchFactor(0, 0)
        self.platform_reports_splitter.setStretchFactor(1, 1)
        self.platform_reports_splitter.setSizes([220, 780])
        self.platform_reports_splitter.splitterMoved.connect(
            self._on_platform_splitter_moved
        )
        layout.addWidget(self.platform_reports_splitter, 1)

        return page

    def _create_back_button(self, callback=None):
        button = QtWidgets.QPushButton("Wstecz")
        button.setIcon(
            self.style().standardIcon(
                QtWidgets.QStyle.StandardPixmap.SP_ArrowBack
            )
        )
        button.setMinimumWidth(110)
        button.clicked.connect(callback or self.show_mode_selection)
        return button

    def _create_calculation_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header_layout = QtWidgets.QHBoxLayout()
        self.calculation_back_button = self._create_back_button()
        self.report_files_back_button = self.calculation_back_button
        header_layout.addWidget(self.calculation_back_button)
        header_layout.addSpacing(8)

        title = QtWidgets.QLabel("Przelicz Raporty")
        title.setProperty("role", "Title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.manual_add_report_button = QtWidgets.QPushButton("Dodaj raport")
        self.manual_add_report_button.setMinimumWidth(160)
        self.manual_add_report_button.clicked.connect(
            self.open_manual_report_dialog
        )
        self.add_report_file_button = self.manual_add_report_button
        header_layout.addWidget(self.manual_add_report_button)

        self.manual_calculate_reports_button = QtWidgets.QPushButton(
            "Przelicz raporty"
        )
        self.manual_calculate_reports_button.setMinimumWidth(160)
        self.manual_calculate_reports_button.clicked.connect(
            self.open_report_calculation_dialog
        )
        header_layout.addWidget(self.manual_calculate_reports_button)

        self.complete_report_database_button = QtWidgets.QPushButton(
            "Uzupełnij bazę"
        )
        self.complete_report_database_button.setEnabled(False)
        self.complete_report_database_button.setToolTip(
            "Przycisk włączy się, gdy przeliczony raport zawiera "
            "książki lub klientów spoza bazy."
        )
        self.complete_report_database_button.clicked.connect(
            self.add_unmatched_report_books
        )
        header_layout.addWidget(self.complete_report_database_button)

        self.map_report_columns_button = QtWidgets.QPushButton("Dopasuj kolumny")
        self.map_report_columns_button.setEnabled(False)
        self.map_report_columns_button.clicked.connect(
            self.map_selected_report_columns
        )
        header_layout.addWidget(self.map_report_columns_button)

        self.delete_report_file_button = QtWidgets.QPushButton("Usuń")
        self.delete_report_file_button.setEnabled(False)
        self.delete_report_file_button.clicked.connect(
            self.delete_selected_report_file
        )
        header_layout.addWidget(self.delete_report_file_button)

        self.show_report_trash_button = QtWidgets.QPushButton("Kosz")
        self.show_report_trash_button.clicked.connect(
            self.show_report_trash_page
        )
        header_layout.addWidget(self.show_report_trash_button)

        layout.addLayout(header_layout)

        description = QtWidgets.QLabel(
            "Zielone raporty mają rozpoznany układ i mogą zostać przeliczone. "
            "Dla czerwonego raportu wybierz Dopasuj kolumny. Program zapamięta "
            "ustawienie dla platformy i tego układu Excela."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        filters_layout = QtWidgets.QHBoxLayout()
        filters_layout.addWidget(QtWidgets.QLabel("Rok:"))
        self.report_year_filter = QtWidgets.QComboBox()
        self.report_year_filter.setMinimumWidth(150)
        self.report_year_filter.addItem("Wszystkie lata", "")
        self.report_year_filter.currentIndexChanged.connect(
            self.render_report_files
        )
        filters_layout.addWidget(self.report_year_filter)
        filters_layout.addStretch()

        self.report_files_summary_label = QtWidgets.QLabel("")
        self.report_files_summary_label.setProperty("role", "SectionTitle")
        filters_layout.addWidget(self.report_files_summary_label)
        layout.addLayout(filters_layout)

        self.report_files_table = QtWidgets.QTableWidget(0, 6)
        self.report_files_table.setHorizontalHeaderLabels(
            ["Status", "Plik", "Rok", "Typ", "Pozycje", "Informacja"]
        )
        self.report_files_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.report_files_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.report_files_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.report_files_table.setAlternatingRowColors(False)
        self.report_files_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_files_table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_files_table.verticalHeader().setVisible(False)
        self.report_files_table.itemSelectionChanged.connect(
            self.on_report_file_selection_changed
        )

        table_header = self.report_files_table.horizontalHeader()
        table_header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
        )
        table_header.setSectionResizeMode(
            1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for column in (2, 3, 4):
            table_header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        table_header.setSectionResizeMode(
            5, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.report_files_table, 1)
        return page

    def _create_report_trash_page(self):
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)

        header_layout = QtWidgets.QHBoxLayout()
        self.report_trash_back_button = self._create_back_button(
            self.show_report_files_page
        )
        header_layout.addWidget(self.report_trash_back_button)
        header_layout.addSpacing(8)

        title = QtWidgets.QLabel("Kosz raportów")
        title.setProperty("role", "Title")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.restore_report_button = QtWidgets.QPushButton("Przywróć")
        self.restore_report_button.setEnabled(False)
        self.restore_report_button.clicked.connect(
            self.restore_selected_report
        )
        header_layout.addWidget(self.restore_report_button)

        self.permanently_delete_report_button = QtWidgets.QPushButton(
            "Usuń trwale"
        )
        self.permanently_delete_report_button.setEnabled(False)
        self.permanently_delete_report_button.clicked.connect(
            self.permanently_delete_selected_report
        )
        header_layout.addWidget(self.permanently_delete_report_button)

        layout.addLayout(header_layout)

        description = QtWidgets.QLabel(
            "Usunięte raporty można przywrócić do ich pierwotnego katalogu."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        self.report_trash_summary_label = QtWidgets.QLabel("")
        self.report_trash_summary_label.setProperty("role", "SectionTitle")
        layout.addWidget(self.report_trash_summary_label)

        self.report_trash_table = QtWidgets.QTableWidget(0, 4)
        self.report_trash_table.setHorizontalHeaderLabels(
            ["Plik", "Rok", "Usunięto", "Pierwotna lokalizacja"]
        )
        self.report_trash_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.report_trash_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.report_trash_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.report_trash_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_trash_table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_trash_table.verticalHeader().setVisible(False)
        self.report_trash_table.itemSelectionChanged.connect(
            self.on_report_trash_selection_changed
        )

        trash_header = self.report_trash_table.horizontalHeader()
        trash_header.setSectionResizeMode(
            0, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for column in (1, 2):
            trash_header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        trash_header.setSectionResizeMode(
            3, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        layout.addWidget(self.report_trash_table, 1)
        return page

    def show_mode_selection(self):
        self.refresh_platform_list()
        self.refresh_overview_reports(show_errors=False)
        self.mode_stack.setCurrentWidget(self.mode_selection_page)
        self._show_tutorial_steps_for(self.mode_selection_page)

    def show_calculation_page(self):
        self.refresh_report_files()
        self.mode_stack.setCurrentWidget(self.calculation_page)
        self._show_tutorial_steps_for(self.calculation_page)

    def show_report_files_page(self):
        self.show_calculation_page()

    def show_report_trash_page(self):
        self.refresh_report_trash()
        self.mode_stack.setCurrentWidget(self.report_trash_page)
        if self.report_tutorial.is_active:
            self.report_tutorial.pause()

    @staticmethod
    def _report_type_text(report_types):
        labels = {
            "transaction": "Transakcje",
            "monthly": "Miesięczny",
            "quarterly": "Kwartalny",
        }
        return " + ".join(labels.get(value, value) for value in report_types) or "—"

    def refresh_report_files(self):
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            analyses = scan_report_directory(PLATFORM_REPORTS_ROOT)
        except Exception as error:
            analyses = []
            QtWidgets.QMessageBox.warning(
                self,
                "Lista raportów",
                f"Nie udało się sprawdzić katalogu raportów: {error}",
            )
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        self._report_file_analyses = analyses
        self.refresh_report_year_filter()
        self.render_report_files()

    @staticmethod
    def _report_file_year(path):
        try:
            relative_path = Path(path).relative_to(PLATFORM_REPORTS_ROOT)
        except ValueError:
            relative_path = Path(path)
        return next(
            (
                part
                for part in relative_path.parts
                if part.isdigit() and len(part) == 4
            ),
            "",
        )

    def refresh_report_year_filter(self):
        selected_year = self.report_year_filter.currentData()

        # Jedno przejście po analizach – _report_file_year jest względnie
        # kosztowne (Path.relative_to + skan części), a wcześniej było
        # wywoływane dwa razy na każdy plik.
        years = set()
        for analysis in self._report_file_analyses:
            year = self._report_file_year(analysis.path)
            if year:
                years.add(year)
        years = sorted(years, reverse=True)

        self.report_year_filter.blockSignals(True)
        self.report_year_filter.clear()
        self.report_year_filter.addItem("Wszystkie lata", "")
        for year in years:
            self.report_year_filter.addItem(year, year)
        selected_index = self.report_year_filter.findData(selected_year)
        self.report_year_filter.setCurrentIndex(max(0, selected_index))
        self.report_year_filter.blockSignals(False)

    def render_report_files(self):
        selected_year = self.report_year_filter.currentData()
        all_analyses = getattr(self, "_report_file_analyses", [])

        analyses = []
        for analysis in all_analyses:
            year = self._report_file_year(analysis.path)
            if selected_year and year != selected_year:
                continue
            analyses.append((analysis, year))

        table = self.report_files_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.clearSelection()
            if table.rowCount() != len(analyses):
                table.setRowCount(len(analyses))

            recognized_count = 0
            background_ok = QtGui.QColor("#2e7d32")
            background_bad = QtGui.QColor("#c62828")
            foreground = QtGui.QColor("#ffffff")
            center = QtCore.Qt.AlignmentFlag.AlignCenter
            left_vcenter = (
                    QtCore.Qt.AlignmentFlag.AlignLeft
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            user_role = QtCore.Qt.ItemDataRole.UserRole

            for row, (analysis, year) in enumerate(analyses):
                if analysis.recognized:
                    recognized_count += 1
                try:
                    relative_path = analysis.path.relative_to(
                        PLATFORM_REPORTS_ROOT
                    )
                except ValueError:
                    relative_path = Path(analysis.path.name)

                values = (
                    "Rozpoznany" if analysis.recognized else "Nierozpoznany",
                    str(relative_path),
                    year or "—",
                    self._report_type_text(analysis.report_types),
                    analysis.rows_count,
                    analysis.message,
                )
                background = (
                    background_ok if analysis.recognized else background_bad
                )
                tooltip = f"{analysis.path}\n{analysis.message}"
                path_str = str(analysis.path)

                for column, value in enumerate(values):
                    item = table.item(row, column)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem()
                        table.setItem(row, column, item)

                    item.setText(str(value))
                    item.setBackground(background)
                    item.setForeground(foreground)
                    item.setToolTip(tooltip)
                    item.setData(user_role, path_str)

                    if column in (0, 2, 3, 4):
                        item.setTextAlignment(center)
                    else:
                        item.setTextAlignment(left_vcenter)

            total = len(analyses)
            rejected_count = total - recognized_count
            self.report_files_summary_label.setText(
                f"Rozpoznane: {recognized_count}   "
                f"|   Nierozpoznane: {rejected_count}"
            )
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        self.on_report_file_selection_changed()

    def on_report_file_selection_changed(self):
        analysis = self._selected_report_file_analysis()
        self.delete_report_file_button.setEnabled(analysis is not None)
        self.map_report_columns_button.setEnabled(
            analysis is not None
            and analysis.path.suffix.lower()
            in {".xlsx", ".xlsm", ".xltx", ".xltm"}
        )

    def _selected_report_file_analysis(self):
        path = self._selected_report_file_path()
        if path is None:
            return None
        expected = str(path).casefold()
        return next(
            (
                analysis
                for analysis in getattr(self, "_report_file_analyses", [])
                if str(analysis.path).casefold() == expected
            ),
            None,
        )

    def _selected_report_file_path(self):
        selected_rows = self.report_files_table.selectionModel().selectedRows()
        item = (
            self.report_files_table.item(selected_rows[0].row(), 0)
            if selected_rows
            else None
        )
        if item is None:
            return None
        value = item.data(QtCore.Qt.ItemDataRole.UserRole)
        return Path(value) if value else None

    def add_report_from_report_list(self):
        self.open_manual_report_dialog()
        self.refresh_report_files()

    def map_selected_report_columns(self):
        analysis = self._selected_report_file_analysis()
        if analysis is None:
            return
        self.report_column_mapping_page.configure_report(analysis.path)
        self.mode_stack.setCurrentWidget(self.report_column_mapping_page)
        self._show_tutorial_steps_for(self.report_column_mapping_page)

    def show_report_column_mapping_page(self):
        if self.report_column_mapping_page.report_path is None:
            self.show_report_files_page()
            return
        self.mode_stack.setCurrentWidget(self.report_column_mapping_page)
        self._show_tutorial_steps_for(self.report_column_mapping_page)

    def show_excel_cell_picker(self, field_name):
        report_path = self.report_column_mapping_page.report_path
        if report_path is None:
            return
        preferred_sheet, preferred_row = (
            self.report_column_mapping_page.preferred_location()
        )
        self._pending_mapping_field = field_name
        self.excel_cell_picker_page.open_report(
            report_path,
            self.report_column_mapping_page.field_label(field_name),
            preferred_sheet=preferred_sheet,
            preferred_row=preferred_row,
        )
        self.mode_stack.setCurrentWidget(self.excel_cell_picker_page)
        if self.report_tutorial.is_active:
            self.report_tutorial.pause()

    def on_excel_header_cell_selected(
            self,
            value,
            sheet_name,
            row_number,
            column_number,
    ):
        field_name = getattr(self, "_pending_mapping_field", None)
        if field_name:
            self.report_column_mapping_page.set_field_from_cell(
                field_name,
                value,
                sheet_name,
                row_number,
                column_number,
            )
        self.mode_stack.setCurrentWidget(self.report_column_mapping_page)
        self._show_tutorial_steps_for(
            self.report_column_mapping_page,
            index=1,
        )

    def on_report_column_mapping_saved(self, report_path):
        self.correct_report_year_assignment(Path(report_path))
        self.refresh_report_files()
        self.mode_stack.setCurrentWidget(self.calculation_page)
        self._show_tutorial_steps_for(self.calculation_page, index=2)

    def correct_report_year_assignment(self, report_path):
        """Po konfiguracji proponuje przeniesienie raportu do właściwego roku."""
        analysis = analyze_report_file(report_path)
        content_years = analysis.content_years
        if not content_years:
            return Path(report_path)
        if len(content_years) > 1:
            years_text = ", ".join(str(year) for year in content_years)
            QtWidgets.QMessageBox.warning(
                self,
                "Raport obejmuje kilka lat",
                (
                    f"Raport zawiera dane z lat: {years_text}. Jeden plik może "
                    "być przypisany tylko do jednego roku. Podziel raport na "
                    "osobne pliki przed przeliczeniem."
                ),
            )
            return Path(report_path)

        detected_year = content_years[0]
        assigned_year = self._report_file_year(report_path)
        if assigned_year == str(detected_year):
            return Path(report_path)

        answer = QtWidgets.QMessageBox.question(
            self,
            "Nieprawidłowy rok raportu",
            (
                f"Raport jest przypisany do roku {assigned_year or 'nieznanego'}, "
                f"ale jego daty dotyczą roku {detected_year}.\n\n"
                f"Przenieść raport do katalogu {detected_year}?"
            ),
            (
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No
            ),
            QtWidgets.QMessageBox.StandardButton.Yes,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return Path(report_path)

        try:
            destination = move_report_to_year(report_path, detected_year)
        except ReportFileError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Zmiana roku raportu",
                str(error),
            )
            return Path(report_path)

        self.report_column_mapping_page.report_path = destination
        QtWidgets.QMessageBox.information(
            self,
            "Poprawiono rok raportu",
            f"Raport został przeniesiony do katalogu roku {detected_year}.",
        )
        return destination

    def delete_selected_report_file(self):
        report_path = self._selected_report_file_path()
        if report_path is None:
            return
        answer = QtWidgets.QMessageBox.question(
            self,
            "Usuń raport",
            f"Przenieść raport {report_path.name} do kosza?",
            (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
            ),
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        try:
            move_report_to_trash(report_path)
        except ReportFileError as error:
            QtWidgets.QMessageBox.critical(self, "Usuwanie raportu", str(error))
            return
        self.refresh_report_files()

    def refresh_report_trash(self):
        try:
            entries = list_trashed_reports()
        except ReportFileError as error:
            entries = []
            QtWidgets.QMessageBox.warning(self, "Kosz raportów", str(error))

        table = self.report_trash_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.clearSelection()
            if table.rowCount() != len(entries):
                table.setRowCount(len(entries))

            center = QtCore.Qt.AlignmentFlag.AlignCenter
            user_role = QtCore.Qt.ItemDataRole.UserRole

            for row, entry in enumerate(entries):
                year = next(
                    (
                        part
                        for part in entry.original_relative_path.parts
                        if part.isdigit() and len(part) == 4
                    ),
                    "—",
                )
                deleted_at = (
                    entry.deleted_at.strftime("%Y-%m-%d %H:%M:%S")
                    if entry.deleted_at
                    else "—"
                )
                values = (
                    entry.original_relative_path.name,
                    year,
                    deleted_at,
                    str(entry.original_relative_path),
                )
                entry_path_str = str(entry.path)
                for column, value in enumerate(values):
                    item = table.item(row, column)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem()
                        table.setItem(row, column, item)
                    item.setText(str(value))
                    item.setData(user_role, entry_path_str)
                    if column in (1, 2):
                        item.setTextAlignment(center)
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        self.report_trash_summary_label.setText(
            f"Raporty w koszu: {len(entries)}"
        )
        self.on_report_trash_selection_changed()

    def on_report_trash_selection_changed(self):
        has_selection = bool(
            self.report_trash_table.selectionModel().selectedRows()
        )
        self.restore_report_button.setEnabled(has_selection)
        self.permanently_delete_report_button.setEnabled(has_selection)

    def _selected_trashed_report(self):
        selected_rows = self.report_trash_table.selectionModel().selectedRows()
        if not selected_rows:
            return None, None
        row = selected_rows[0].row()
        path_item = self.report_trash_table.item(row, 0)
        original_path_item = self.report_trash_table.item(row, 3)
        if path_item is None or original_path_item is None:
            return None, None
        trash_path = path_item.data(QtCore.Qt.ItemDataRole.UserRole)
        return (
            Path(trash_path) if trash_path else None,
            Path(original_path_item.text()),
        )

    def restore_selected_report(self):
        trash_path, _original_relative_path = self._selected_trashed_report()
        if trash_path is None:
            return
        try:
            restored_path = restore_report_from_trash(trash_path)
        except ReportFileError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Przywracanie raportu",
                str(error),
            )
            return
        QtWidgets.QMessageBox.information(
            self,
            "Przywrócono raport",
            f"Raport został przywrócony jako:\n{restored_path}",
        )
        self.refresh_report_trash()

    def permanently_delete_selected_report(self):
        trash_path, original_relative_path = self._selected_trashed_report()
        if trash_path is None or original_relative_path is None:
            return
        active_report_path = PLATFORM_REPORTS_ROOT / original_relative_path
        if active_report_path.exists():
            QtWidgets.QMessageBox.warning(
                self,
                "Usuwanie raportu",
                (
                    "W pierwotnym katalogu istnieje już nowszy raport o tej "
                    "samej nazwie. Nie można bezpiecznie ustalić, do którego "
                    "pliku należą dane SQLite, więc operacja została przerwana."
                ),
            )
            return
        report_year = next(
            (
                int(part)
                for part in original_relative_path.parts
                if part.isdigit() and len(part) == 4
            ),
            None,
        )
        if report_year is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Usuwanie raportu",
                "Nie można ustalić roku raportu, więc operacja została przerwana.",
            )
            return

        answer = QtWidgets.QMessageBox.question(
            self,
            "Usuń raport trwale",
            (
                f"Trwale usunąć raport {original_relative_path.name}?\n\n"
                "Usunięty zostanie plik oraz wszystkie dane zaimportowane z "
                "niego do SQLite. Dane z pozostałych raportów pozostaną "
                "bez zmian. Tej "
                "operacji nie można cofnąć."
            ),
            (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
            ),
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        remove_books = False
        exclusive_books: list[dict] = []
        try:
            linked_books = books_linked_to_report(
                report_year, original_relative_path.name
            )
        except ReportCalculationError:
            linked_books = ()
        for linked in linked_books:
            if not linked.exclusive:
                continue
            product = database_controller.item_get(linked.product_id, "products")
            if product is not None:
                exclusive_books.append(product)

        if exclusive_books:
            titles = "\n".join(
                f"- {book.get('title') or 'bez tytułu'}" for book in exclusive_books
            )
            books_answer = QtWidgets.QMessageBox.question(
                self,
                "Usunąć dopisane książki?",
                (
                    "Do bazy zostały dopisane następujące książki wyłącznie na "
                    f"podstawie tego raportu:\n\n{titles}\n\n"
                    "Czy usunąć je też z bazy? Trafią do kosza produktów, "
                    "skąd można je przywrócić."
                ),
                (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
                ),
                QtWidgets.QMessageBox.StandardButton.No,
            )
            remove_books = books_answer == QtWidgets.QMessageBox.StandardButton.Yes

        try:
            deletion = delete_imported_report_data(
                report_year,
                original_relative_path.name,
            )
        except ReportCalculationError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Usuwanie danych raportu",
                str(error),
            )
            return

        try:
            permanently_delete_trashed_report(trash_path)
        except ReportFileError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Usuwanie raportu",
                (
                    f"Dane raportu usunięto z SQLite, ale nie udało się "
                    f"usunąć pliku z kosza:\n{error}"
                ),
            )
            return

        removed_books = 0
        if remove_books:
            for book in exclusive_books:
                try:
                    database_controller.item_remove(book["id"], "products")
                    removed_books += 1
                except Exception:
                    pass
        try:
            forget_report_book_links(report_year, original_relative_path.name)
        except ReportCalculationError:
            pass

        removed_line = (
            f"Usunięte książki: {removed_books}\n" if exclusive_books else ""
        )
        QtWidgets.QMessageBox.information(
            self,
            "Usunięto raport",
            (
                "Raport został trwale usunięty.\n"
                f"Transakcje: {deletion.transaction_rows}\n"
                f"Raporty miesięczne: {deletion.monthly_rows}\n"
                f"Rozliczenia kwartalne: {deletion.quarterly_rows}\n"
                f"{removed_line}"
            ),
        )
        self.refresh_report_trash()

    def open_manual_report_dialog(self):
        dialog = ManualPlatformReportDialog(self)
        dialog.exec()

        self.refresh_report_files()
        self.refresh_overview_reports(show_errors=True)
        self.refresh_platform_list()

    def reload(self):
        """Przeładowuje dane zakładki (po wczytaniu kopii bazy)."""
        self.refresh_platform_list()
        self.refresh_overview_reports(show_errors=False)

    def refresh_platform_list(self):
        try:
            platforms = load_streaming_platforms()
            error_message = ""
        except ManualReportError as error:
            platforms = []
            error_message = str(error)

        selected_id = None
        selected_items = self.platforms_table.selectedItems()
        if selected_items:
            selected_platform = selected_items[0].data(
                QtCore.Qt.ItemDataRole.UserRole
            )
            if isinstance(selected_platform, dict):
                selected_id = selected_platform.get("id")

        table = self.platforms_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.clearSelection()
            if table.rowCount() != len(platforms):
                table.setRowCount(len(platforms))

            user_role = QtCore.Qt.ItemDataRole.UserRole
            selected_row = None

            for row, platform in enumerate(platforms):
                platform_name = str(platform.get("name") or "Bez nazwy")
                item = table.item(row, 0)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    table.setItem(row, 0, item)
                item.setText(platform_name)
                item.setData(user_role, platform)

                if (
                        selected_id is not None
                        and platform.get("id") == selected_id
                ):
                    selected_row = row
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        if selected_row is not None:
            self.platforms_table.selectRow(selected_row)
        self._update_platform_action_buttons()

        status_message = error_message
        if not platforms and not status_message:
            status_message = "Brak platform w bazie danych"
        self.platforms_status_label.setText(status_message)
        self.platforms_status_label.setVisible(bool(status_message))

        QtCore.QTimer.singleShot(0, self._resize_platform_panel_to_contents)

    def add_platform_from_overview(self):
        platform = prompt_add_streaming_platform(self)
        if platform is None:
            return
        self.refresh_platform_list()
        self._select_platform_by_id(platform.get("id"))

    def _select_platform_by_id(self, platform_id):
        for row in range(self.platforms_table.rowCount()):
            item = self.platforms_table.item(row, 0)
            item_platform = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if isinstance(item_platform, dict) and item_platform.get("id") == platform_id:
                self.platforms_table.selectRow(row)
                break

    def _selected_platform(self):
        selected_items = self.platforms_table.selectedItems()
        if not selected_items:
            return None
        platform = selected_items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        return platform if isinstance(platform, dict) else None

    def _update_platform_action_buttons(self):
        has_selection = self._selected_platform() is not None
        self.edit_platform_button.setEnabled(has_selection)
        self.delete_platform_button.setEnabled(has_selection)

    def edit_selected_platform(self, *_):
        platform = self._selected_platform()
        if platform is None:
            return
        current_name = str(platform.get("name") or "").strip()
        new_name, accepted = QtWidgets.QInputDialog.getText(
            self,
            "Edytuj platformę",
            "Nazwa platformy:",
            text=current_name,
        )
        if not accepted:
            return
        try:
            renamed = rename_streaming_platform(platform.get("id"), new_name)
        except ManualReportError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Edycja platformy",
                str(error),
            )
            return

        self.refresh_platform_list()
        self._select_platform_by_id(renamed.get("id"))

    def delete_selected_platform(self):
        platform = self._selected_platform()
        if platform is None:
            return
        platform_name = str(platform.get("name") or "wybraną platformę").strip()
        answer = QtWidgets.QMessageBox.question(
            self,
            "Usuń platformę",
            (
                f"Czy na pewno chcesz usunąć platformę {platform_name}?\n\n"
                "Zniknie ona z listy i z przypisań książek. Istniejące "
                "raporty oraz rozliczenia pozostaną w historii."
            ),
            (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No
            ),
            QtWidgets.QMessageBox.StandardButton.No,
        )
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            delete_streaming_platform(platform.get("id"))
        except ManualReportError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Usuwanie platformy",
                str(error),
            )
            return
        self.refresh_platform_list()

    def _on_platform_splitter_moved(self, _position, _index):
        self._platform_splitter_user_resized = True

    def _resize_platform_panel_to_contents(self):
        if self._platform_splitter_user_resized:
            return
        content_width = max(0, self.platforms_table.sizeHintForColumn(0))
        header_width = max(
            0,
            self.platforms_table.horizontalHeader().sectionSizeHint(0),
        )
        column_width = max(
            130,
            min(340, max(content_width, header_width) + 16),
        )
        self.platforms_table.setColumnWidth(0, column_width)
        panel_width = column_width + 34
        total_width = max(self.platform_reports_splitter.width(), 760)
        self.platform_reports_splitter.setSizes(
            [panel_width, max(420, total_width - panel_width)]
        )

    def refresh_overview_reports(self, show_errors=True):
        try:
            yearly_reports = list_book_reports()
            monthly_reports = list_monthly_book_reports()
            quarterly_reports = list_quarterly_book_reports()
        except ReportViewerError as error:
            yearly_reports = []
            monthly_reports = []
            quarterly_reports = []
            if show_errors:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Lista raportów",
                    str(error),
                )

        self._overview_yearly_reports = yearly_reports
        self._overview_monthly_reports = monthly_reports
        self._overview_quarterly_reports = quarterly_reports
        self._fill_overview_reports_table()

    def set_overview_report_view(self, view):
        self._overview_report_view = (
            view if view in {"monthly", "yearly", "quarterly"} else "monthly"
        )
        self.overview_monthly_button.setChecked(
            self._overview_report_view == "monthly"
        )
        self.overview_yearly_button.setChecked(
            self._overview_report_view == "yearly"
        )
        self.overview_quarterly_button.setChecked(
            self._overview_report_view == "quarterly"
        )
        yearly_view = self._overview_report_view == "yearly"
        quarterly_view = self._overview_report_view == "quarterly"
        self.overview_period_filter_label.setText(
            (
                "Rok:"
                if yearly_view
                else ("Kwartał / zakres:" if quarterly_view else "Miesiąc:")
            )
        )
        self.overview_period_filter.setPlaceholderText(
            (
                "Filtruj po roku..."
                if yearly_view
                else (
                    "Filtruj po kwartale lub dacie..."
                    if quarterly_view
                    else "Filtruj po miesiącu..."
                )
            )
        )
        if yearly_view:
            current_period = self.overview_period_filter.text().strip()
            if len(current_period) >= 4 and current_period[:4].isdigit():
                self.overview_period_filter.setText(current_period[:4])
        self._fill_overview_reports_table()

    def _fill_overview_reports_table(self):
        monthly_view = self._overview_report_view == "monthly"
        quarterly_view = self._overview_report_view == "quarterly"
        if monthly_view:
            reports = self._overview_monthly_reports
        elif quarterly_view:
            reports = self._overview_quarterly_reports
        else:
            reports = self._overview_yearly_reports

        table = self.overview_reports_table
        table.setUpdatesEnabled(False)
        table.blockSignals(True)
        try:
            table.clearSelection()
            if table.rowCount() != len(reports):
                table.setRowCount(len(reports))
            headers = [
                "Nazwa książki",
                "ISBN",
                (
                    "Miesiąc"
                    if monthly_view
                    else ("Zakres dat" if quarterly_view else "Rok")
                ),
                "Klient",
                "Platforma" if quarterly_view else "Platformy",
                "Ilość",
                "Netto",
                "Brutto",
            ]
            table.setHorizontalHeaderLabels(headers)
            table.setColumnHidden(5, not quarterly_view)

            center = QtCore.Qt.AlignmentFlag.AlignCenter
            user_role = QtCore.Qt.ItemDataRole.UserRole

            filter_cache = []
            for row, report in enumerate(reports):
                if quarterly_view:
                    period_text = f"{report.period_start} – {report.period_end}"
                    values = (
                        report.title,
                        report.isbn,
                        period_text,
                        report.client_name,
                        report.platform_name,
                        _report_quantity_text(report.quantity),
                        _report_amount_text(report.total_net),
                        _report_amount_text(report.total_gross),
                    )
                    filter_period = (
                        f"{report.period} {report.period_start} {report.period_end}"
                    )
                else:
                    values = (
                        report.title,
                        report.isbn,
                        report.period if monthly_view else report.year,
                        report.client_name,
                        report.platforms_count,
                        "",
                        _report_amount_text(report.total_net),
                        _report_amount_text(report.total_gross),
                    )
                    filter_period = str(
                        report.period if monthly_view else report.year
                    )
                for column, value in enumerate(values):
                    item = table.item(row, column)
                    if item is None:
                        item = QtWidgets.QTableWidgetItem()
                        table.setItem(row, column, item)
                    item.setText(str(value))
                    if column == 0:
                        item.setData(user_role, report)
                    if column in (2, 4, 5, 6, 7):
                        item.setTextAlignment(center)

                filter_cache.append((
                    str(report.client_name).casefold(),
                    str(report.title).casefold(),
                    "".join(
                        ch
                        for ch in str(report.isbn).casefold()
                        if ch.isalnum()
                    ),
                    filter_period.casefold(),
                ))

            self._overview_filter_cache = filter_cache
        finally:
            table.blockSignals(False)
            table.setUpdatesEnabled(True)
            table.viewport().update()

        self.filter_overview_reports()

    def _schedule_overview_filter(self, *_):
        self._overview_filter_timer.start()

    def filter_overview_reports(self, *_):
        client_filter = self.overview_client_filter.text().strip().casefold()
        book_filter = self.overview_book_filter.text().strip().casefold()
        isbn_filter = "".join(
            character
            for character in self.overview_isbn_filter.text().casefold()
            if character.isalnum()
        )
        period_filter = self.overview_period_filter.text().strip().casefold()

        table = self.overview_reports_table
        cache = self._overview_filter_cache
        has_filter = bool(
            client_filter or book_filter or isbn_filter or period_filter
        )

        table.setUpdatesEnabled(False)
        try:
            visible_rows = 0
            for row, (client, title, isbn, period) in enumerate(cache):
                matches = (
                        client_filter in client
                        and book_filter in title
                        and isbn_filter in isbn
                        and period_filter in period
                )
                table.setRowHidden(row, not matches)
                visible_rows += int(matches)
        finally:
            table.setUpdatesEnabled(True)

        total_rows = len(cache)
        report_kind = {
            "monthly": "Raporty miesięczne",
            "quarterly": "Raporty kwartalne",
            "yearly": "Raporty roczne",
        }.get(self._overview_report_view, "Raporty miesięczne")
        if has_filter:
            self.overview_reports_label.setText(
                f"{report_kind} ({visible_rows} z {total_rows})"
            )
        else:
            self.overview_reports_label.setText(
                f"{report_kind} ({total_rows})"
            )

    def open_overview_report_details(self, item):
        report_item = self.overview_reports_table.item(item.row(), 0)
        report = (
            report_item.data(QtCore.Qt.ItemDataRole.UserRole)
            if report_item is not None
            else None
        )
        if report is None:
            return

        if self._overview_report_view == "yearly":
            self.open_yearly_report_months(report)
            return
        if self._overview_report_view == "quarterly":
            return

        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            transactions = list_monthly_report_transactions(report)
        except ReportViewerError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Transakcje raportu miesięcznego",
                str(error),
            )
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        if not transactions:
            QtWidgets.QMessageBox.information(
                self,
                "Transakcje raportu miesięcznego",
                "Brak informacji o transakcjach z tego miesiąca.",
            )
            return

        dialog = MonthlyReportTransactionsDialog(report, transactions, self)
        dialog.exec()

    def open_yearly_report_months(self, report):
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            details = load_book_report_details(report)
        except ReportViewerError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Szczegóły raportu rocznego",
                str(error),
            )
            return
        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Szczegóły raportu rocznego",
                f"Nie udało się odczytać raportu: {error}",
            )
            return
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

        dialog = ReportContentsDialog(details, self)
        dialog.exec()

    def _refresh_tabs_after_adding_books(self):
        """Nowe książki z raportów - odśwież zakładki książek i klientów."""
        window = self.window()
        for tab_name, method_names in (
            ("products_tab", ("reload",)),
            ("clients_tab", ("reload",)),
        ):
            tab = getattr(window, tab_name, None)
            for method_name in method_names:
                refresh = getattr(tab, method_name, None)
                if callable(refresh):
                    try:
                        refresh()
                    except Exception as error:
                        print(f"Nie udało się odświeżyć zakładki {tab_name}: {error}")

    def open_report_calculation_dialog(self):
        dialog = ReportCalculationDialog(self)
        dialog.exec()
        result = dialog.calculation_result
        if result is not None:
            self._pending_unmatched_entries = list(
                getattr(result, "unmatched_entries", None) or ()
            )
            self._pending_unmatched_year = result.year
            self._update_complete_report_database_button()
        self.refresh_report_files()
        self.refresh_overview_reports(show_errors=True)

    def _update_complete_report_database_button(self):
        count = len(self._pending_unmatched_entries)
        self.complete_report_database_button.setEnabled(count > 0)
        if count:
            self.complete_report_database_button.setToolTip(
                f"Dodaj brakujące książki i klientów ({count})."
            )
        else:
            self.complete_report_database_button.setToolTip(
                "Przycisk włączy się, gdy przeliczony raport zawiera "
                "książki lub klientów spoza bazy."
            )

    def add_unmatched_report_books(self):
        """Uruchamia na żądanie dodawanie książek wykrytych w raporcie."""
        entries = list(self._pending_unmatched_entries)
        if not entries:
            self._update_complete_report_database_button()
            return

        remaining = []
        added = 0
        stopped = False
        total = len(entries)

        for index, entry in enumerate(entries, start=1):
            dialog = AddBookDialog(entry, index, total, self)
            outcome = dialog.exec()

            if outcome == QtWidgets.QDialog.DialogCode.Accepted:
                added += 1
                if dialog.added_product_id is not None:
                    try:
                        report_links = tuple(entry.get("report_links") or ())
                        if report_links:
                            for link in report_links:
                                record_added_book(
                                    link.get("year"),
                                    link.get("source_files") or (),
                                    dialog.added_product_id,
                                )
                        else:
                            record_added_book(
                                self._pending_unmatched_year,
                                entry.get("source_files") or (),
                                dialog.added_product_id,
                            )
                    except ReportCalculationError as error:
                        print(
                            "Nie udało się zapisać powiązania książki "
                            f"z raportem: {error}"
                        )
            elif outcome == AddBookDialog.SKIPPED:
                remaining.append(entry)
            else:
                stopped = True
                remaining.append(entry)
                remaining.extend(entries[index:])
                break

        self._pending_unmatched_entries = remaining
        self._update_complete_report_database_button()

        if added:
            try:
                relink_unmatched_rows()
            except ReportCalculationError as error:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Uzupełnianie bazy",
                    "Książki zostały dodane, ale nie udało się powiązać "
                    f"ich z raportami: {error}",
                )
            self._refresh_tabs_after_adding_books()
            self.refresh_overview_reports(show_errors=True)

        if not stopped:
            message = f"Dodano książki: {added}."
            if remaining:
                message += f" Pozostało do uzupełnienia: {len(remaining)}."
            QtWidgets.QMessageBox.information(
                self,
                "Uzupełnianie bazy",
                message,
            )
