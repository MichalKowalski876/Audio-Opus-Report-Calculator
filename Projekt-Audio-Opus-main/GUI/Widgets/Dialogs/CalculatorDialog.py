from PySide6 import QtWidgets
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression, Qt

from core import commission_math
from core import sheet_math
from core import lectors
from core import calculator_config
from GUI.Widgets.confirm import confirm_yes_no


class CalculatorDialog(QtWidgets.QDialog):

    def __init__(self, parent=None):
        super().__init__(parent)

        # Stawka VAT (%) z konfiguracji - wczytana raz, przy otwarciu okna.
        # Ustawiona przed setup_ui(), bo kalkulator lektorów korzysta z niej
        # już przy pierwszym wyliczeniu.
        self._vat_percent = calculator_config.load_vat_percent()

        # Wypełniane w reload_lectors(); pusta lista, żeby wcześniejsze
        # wywołania (np. z walidatorów) nie wybuchały.
        self._lectors = []

        # ======================================================
        # OKNO
        # ======================================================

        self.setWindowTitle("Kalkulatory")

        # Stała szerokość okna - przełączanie zakładek ani typów prowizji
        # jej nie zmienia. Wysokość można regulować, a zawartość każdej
        # zakładki siedzi w obszarze przewijania, więc pełny wynik jest
        # dostępny nawet na niskim ekranie.
        self.setFixedWidth(580)
        self.setMinimumHeight(560)
        self.resize(580, 760)

        self.setup_ui()
        self.setup_validators()

        # Domyślnie: prowizja stała
        self.on_type_changed()

        # Lista lektorów + pierwsze wyliczenie kosztu nagrania.
        self.reload_lectors()

    # ==========================================================
    # INTERFEJS
    # ==========================================================

    def setup_ui(self):

        dialog_layout = QtWidgets.QVBoxLayout(self)

        dialog_layout.setContentsMargins(0, 0, 0, 0)

        self.tabs = QtWidgets.QTabWidget()

        dialog_layout.addWidget(self.tabs)

        # ======================================================
        # ZAKŁADKA: PROWIZJA
        # ======================================================

        commission_page = QtWidgets.QWidget()

        main_layout = QtWidgets.QVBoxLayout(commission_page)

        main_layout.setContentsMargins(
            24,
            24,
            24,
            24
        )

        main_layout.setSpacing(14)

        # ======================================================
        # TYTUŁ
        # ======================================================

        title = QtWidgets.QLabel(
            "Kalkulator prowizji"
        )

        title.setProperty(
            "role",
            "Title"
        )

        main_layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "Oblicz kwotę należną klientowi oraz udział platformy."
        )

        subtitle.setWordWrap(True)

        main_layout.addWidget(
            subtitle
        )

        # ======================================================
        # KWOTA ROZLICZENIA
        # ======================================================

        amount_group = QtWidgets.QGroupBox(
            "Kwota rozliczenia"
        )

        amount_layout = QtWidgets.QFormLayout()

        amount_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        amount_layout.setSpacing(8)

        self.amount_input = QtWidgets.QLineEdit()

        self.amount_input.setPlaceholderText(
            "np. 10000,00"
        )

        self.amount_input.setMinimumHeight(
            38
        )

        amount_layout.addRow(
            "Kwota:",
            self.amount_input
        )

        amount_group.setLayout(
            amount_layout
        )

        main_layout.addWidget(
            amount_group
        )

        # ======================================================
        # RODZAJ PROWIZJI
        # ======================================================

        commission_group = QtWidgets.QGroupBox(
            "Rodzaj prowizji"
        )

        commission_layout = QtWidgets.QVBoxLayout()

        commission_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        commission_layout.setSpacing(8)

        # ======================================================
        # TYP
        # ======================================================

        type_layout = QtWidgets.QFormLayout()

        type_layout.setSpacing(8)

        self.type_combo = QtWidgets.QComboBox()

        # Typy rozliczenia zgodne z produktami (EditProductDialog /
        # report_generator.compute_settlement_rows): "instant" i "threshold".
        self.type_combo.addItem(
            "Od razu",
            "instant"
        )

        self.type_combo.addItem(
            "Po progu",
            "threshold"
        )

        self.type_combo.addItem(
            "Do progu",
            "up_to_threshold"
        )

        self.type_combo.addItem(
            "Do i po progu",
            "combined"
        )

        self.type_combo.setMinimumHeight(
            38
        )

        self.type_combo.currentIndexChanged.connect(
            self.on_type_changed
        )

        type_layout.addRow(
            "Typ:",
            self.type_combo
        )

        commission_layout.addLayout(
            type_layout
        )

        # ======================================================
        # STAŁY OBSZAR NA USTAWIENIA PROWIZJI
        # ======================================================

        self.commission_pages = QtWidgets.QWidget()

        # Wszystkie strony mają dokładnie tyle samo miejsca.
        self.commission_pages.setFixedHeight(
            250
        )

        self.commission_stack = QtWidgets.QStackedLayout(
            self.commission_pages
        )

        self.commission_stack.setContentsMargins(
            0,
            0,
            0,
            0
        )

        # ======================================================
        # STRONA: PROWIZJA STAŁA
        # ======================================================

        self.fixed_page = QtWidgets.QWidget()

        fixed_layout = QtWidgets.QFormLayout(
            self.fixed_page
        )

        fixed_layout.setContentsMargins(
            8,
            8,
            8,
            8
        )

        fixed_layout.setSpacing(
            10
        )

        self.fixed_percent_input = QtWidgets.QLineEdit()

        self.fixed_percent_input.setPlaceholderText(
            "np. 30"
        )

        self.fixed_percent_input.setMinimumHeight(
            38
        )

        fixed_layout.addRow(
            "Prowizja AO:",
            self.fixed_percent_input
        )

        fixed_info = QtWidgets.QLabel(
            "Procent kwoty rozliczenia pobierany przez platformę (AO) - "
            "tak samo jak Procent przy książce. Reszta trafia do klienta."
        )

        fixed_info.setWordWrap(True)

        fixed_info.setStyleSheet(
            "font-size: 11px;"
        )

        fixed_layout.addRow(
            "",
            fixed_info
        )

        self.commission_stack.addWidget(
            self.fixed_page
        )

        # ======================================================
        # STRONA: PO PROGU
        # ======================================================
        #
        # Każdy typ progowy ("Po progu" / "Do progu") ma własną, osobną
        # listę progów (_build_threshold_page) - progi dodane w jednym
        # trybie nie mieszają się z progami drugiego trybu, więc nie
        # trzeba ich dodatkowo oznaczać.
        # ======================================================

        (
            self.threshold_page,
            self.threshold_value_input,
            self.threshold_cut_input,
            self.add_threshold_button,
            self.threshold_list,
            self.remove_threshold_button
        ) = self._build_threshold_page(
            "Prowizja platformy liczona jest od nadwyżki ponad próg - "
            "kwota do progu w całości zostaje u platformy."
        )

        self.add_threshold_button.clicked.connect(
            lambda: self.add_threshold(
                self.threshold_value_input,
                self.threshold_cut_input,
                self.threshold_list
            )
        )

        self.remove_threshold_button.clicked.connect(
            lambda: self.remove_threshold(
                self.threshold_list
            )
        )

        self.threshold_list.currentItemChanged.connect(
            lambda current, previous: self.calculate()
        )

        self.commission_stack.addWidget(
            self.threshold_page
        )

        # ======================================================
        # STRONA: DO PROGU
        # ======================================================

        (
            self.up_to_threshold_page,
            self.up_to_threshold_value_input,
            self.up_to_threshold_cut_input,
            self.add_up_to_threshold_button,
            self.up_to_threshold_list,
            self.remove_up_to_threshold_button
        ) = self._build_threshold_page(
            "Prowizja platformy liczona jest od kwoty do progu - nadwyżka "
            "ponad próg w całości trafia do klienta."
        )

        self.add_up_to_threshold_button.clicked.connect(
            lambda: self.add_threshold(
                self.up_to_threshold_value_input,
                self.up_to_threshold_cut_input,
                self.up_to_threshold_list
            )
        )

        self.remove_up_to_threshold_button.clicked.connect(
            lambda: self.remove_threshold(
                self.up_to_threshold_list
            )
        )

        self.up_to_threshold_list.currentItemChanged.connect(
            lambda current, previous: self.calculate()
        )

        self.commission_stack.addWidget(
            self.up_to_threshold_page
        )

        # ======================================================
        # STRONA: DO I PO PROGU
        # ======================================================

        (
            self.combined_page,
            self.combined_value_input,
            self.combined_below_input,
            self.combined_above_input,
            self.add_combined_button,
            self.combined_list,
            self.remove_combined_button
        ) = self._build_combined_threshold_page(
            "Jeden próg, dwie prowizje: część kwoty do progu liczona jest "
            "wg pierwszego procentu, a nadwyżka ponad próg wg drugiego - "
            "obie części nakładają się na siebie w jednym wyniku."
        )

        self.add_combined_button.clicked.connect(
            self.add_combined_threshold
        )

        self.remove_combined_button.clicked.connect(
            lambda: self.remove_threshold(
                self.combined_list
            )
        )

        self.combined_list.currentItemChanged.connect(
            lambda current, previous: self.calculate()
        )

        self.commission_stack.addWidget(
            self.combined_page
        )

        commission_layout.addWidget(
            self.commission_pages
        )

        commission_group.setLayout(
            commission_layout
        )

        main_layout.addWidget(
            commission_group
        )

        # ======================================================
        # WYNIK
        # ======================================================

        result_group = QtWidgets.QGroupBox(
            "Wynik"
        )

        result_layout = QtWidgets.QFormLayout()

        result_layout.setContentsMargins(
            12,
            12,
            12,
            12
        )

        result_layout.setSpacing(
            6
        )

        self.result_amount = QtWidgets.QLabel(
            "0,00 zł"
        )

        self.result_excess = QtWidgets.QLabel(
            "0,00 zł"
        )

        self.result_client = QtWidgets.QLabel(
            "0,00 zł"
        )

        self.result_platform = QtWidgets.QLabel(
            "0,00 zł"
        )

        bold_font = self.result_client.font()

        bold_font.setBold(True)

        self.result_client.setFont(
            bold_font
        )

        self.result_platform.setFont(
            bold_font
        )

        result_layout.addRow(
            "Kwota rozliczenia:",
            self.result_amount
        )

        result_layout.addRow(
            "Nadwyżka ponad próg:",
            self.result_excess
        )

        result_layout.addRow(
            "Dla klienta:",
            self.result_client
        )

        result_layout.addRow(
            "Dla platformy:",
            self.result_platform
        )

        self.result_breakdown = QtWidgets.QLabel(
            "Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."
        )

        self.result_breakdown.setWordWrap(True)

        self.result_breakdown.setStyleSheet(
            "font-size: 11px; color: palette(mid);"
        )

        result_layout.addRow(
            self.result_breakdown
        )

        result_group.setLayout(
            result_layout
        )

        main_layout.addWidget(
            result_group
        )

        # ======================================================
        # PRZYCISKI
        # ======================================================

        buttons_layout = QtWidgets.QHBoxLayout()

        buttons_layout.setSpacing(
            10
        )

        self.clear_button = QtWidgets.QPushButton(
            "Wyczyść"
        )

        self.calculate_button = QtWidgets.QPushButton(
            "Oblicz"
        )

        self.clear_button.setMinimumHeight(
            36
        )

        self.calculate_button.setMinimumHeight(
            36
        )

        self.clear_button.clicked.connect(
            self.clear
        )

        self.calculate_button.clicked.connect(
            self.calculate
        )

        buttons_layout.addWidget(
            self.clear_button
        )

        buttons_layout.addStretch()

        buttons_layout.addWidget(
            self.calculate_button
        )

        main_layout.addLayout(
            buttons_layout
        )

        # ======================================================
        # AUTOMATYCZNE OBLICZANIE
        # ======================================================

        self.amount_input.textChanged.connect(
            self.calculate
        )

        self.fixed_percent_input.textChanged.connect(
            self.calculate
        )

        self.tabs.addTab(self._scrollable(commission_page), "Prowizja")

        # ======================================================
        # ZAKŁADKA: LEKTORZY
        # ======================================================

        self.tabs.addTab(self._scrollable(self.build_lectors_page()), "Lektorzy")

    # ==========================================================
    # STRONA Z PROGAMI (WSPÓLNA DLA "PO PROGU" I "DO PROGU")
    # ==========================================================

    def _build_info_label(self, text):
        """Buduje wyróżnioną (nie wtopioną w tło) etykietę z krótkim opisem
        zasady - wyraźne tło i obramowanie zamiast przygaszonego koloru
        tekstu, żeby było to czytelne także w ciemnym motywie."""

        label = QtWidgets.QLabel(
            text
        )

        label.setWordWrap(True)

        label.setStyleSheet(
            "font-size: 11px;"
            "padding: 6px;"
            "border: 1px solid palette(mid);"
            "border-radius: 4px;"
            "background-color: palette(alternate-base);"
        )

        return label

    def _build_threshold_page(self, info_text):
        """Buduje stronę z własną listą progów: pola do dodania progu
        (wartość, % platformy, przycisk "Dodaj"), listę zapisanych progów
        i przycisk usuwania zaznaczonego.

        Wywoływane osobno dla "Po progu" i "Do progu", żeby każdy tryb miał
        swoją listę - progi jednego trybu nie mieszają się wtedy z progami
        drugiego. `info_text` tłumaczy krótko zasadę danego trybu.
        """

        page = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout(page)

        layout.setContentsMargins(
            8,
            2,
            8,
            2
        )

        layout.setSpacing(
            6
        )

        layout.addWidget(
            self._build_info_label(info_text)
        )

        # ------------------------------------------------------
        # DODAWANIE NOWEGO PROGU
        # ------------------------------------------------------
        #
        # Liczba progów jest edytowalna: można dodać dowolnie
        # wiele progów, a następnie wybrać jeden z listy, który
        # ma zostać użyty w obliczeniu.
        # ------------------------------------------------------

        add_row_layout = QtWidgets.QHBoxLayout()

        add_row_layout.setSpacing(
            6
        )

        value_input = QtWidgets.QLineEdit()

        value_input.setPlaceholderText(
            "Próg, np. 5000"
        )

        value_input.setMinimumHeight(
            34
        )

        cut_input = QtWidgets.QLineEdit()

        cut_input.setPlaceholderText(
            "% platformy, np. 20"
        )

        cut_input.setMinimumHeight(
            34
        )

        # Podgląd na żywo - wynik liczy się już podczas wpisywania progu
        # i procentu, jeszcze przed kliknięciem "Dodaj" (patrz
        # _resolve_threshold_data).
        value_input.textChanged.connect(
            self.calculate
        )

        cut_input.textChanged.connect(
            self.calculate
        )

        add_button = QtWidgets.QPushButton(
            "Dodaj"
        )

        add_button.setMinimumHeight(
            34
        )

        add_row_layout.addWidget(
            value_input
        )

        add_row_layout.addWidget(
            cut_input
        )

        add_row_layout.addWidget(
            add_button
        )

        layout.addLayout(
            add_row_layout
        )

        # ------------------------------------------------------
        # LISTA ZAPISANYCH PROGÓW
        # ------------------------------------------------------

        list_widget = QtWidgets.QListWidget()

        list_widget.setMaximumHeight(
            80
        )

        layout.addWidget(
            list_widget
        )

        remove_row_layout = QtWidgets.QHBoxLayout()

        remove_row_layout.addStretch()

        remove_button = QtWidgets.QPushButton(
            "Usuń zaznaczony"
        )

        remove_row_layout.addWidget(
            remove_button
        )

        layout.addLayout(
            remove_row_layout
        )

        return (
            page,
            value_input,
            cut_input,
            add_button,
            list_widget,
            remove_button
        )

    # ==========================================================
    # STRONA "DO I PO PROGU" (JEDEN PRÓG, DWIE PROWIZJE)
    # ==========================================================

    def _build_combined_threshold_page(self, info_text):
        """Buduje stronę trybu "Do i po progu": każdy próg ma dwie osobne
        prowizje platformy - jedną dla części kwoty do progu, drugą dla
        nadwyżki ponad próg. Obie części nakładają się na siebie w jednym
        wyliczeniu (commission_math.split_combined)."""

        page = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout(page)

        layout.setContentsMargins(
            8,
            2,
            8,
            2
        )

        layout.setSpacing(
            6
        )

        layout.addWidget(
            self._build_info_label(info_text)
        )

        # ------------------------------------------------------
        # DODAWANIE NOWEGO PROGU (WARTOŚĆ PROGU)
        # ------------------------------------------------------

        value_input = QtWidgets.QLineEdit()

        value_input.setPlaceholderText(
            "Próg, np. 5000"
        )

        value_input.setMinimumHeight(
            34
        )

        layout.addWidget(
            value_input
        )

        # ------------------------------------------------------
        # DWIE PROWIZJE: DO PROGU I PO PROGU
        # ------------------------------------------------------

        percents_row_layout = QtWidgets.QHBoxLayout()

        percents_row_layout.setSpacing(
            6
        )

        below_input = QtWidgets.QLineEdit()

        below_input.setPlaceholderText(
            "Do progu %, np. 10"
        )

        below_input.setMinimumHeight(
            34
        )

        above_input = QtWidgets.QLineEdit()

        above_input.setPlaceholderText(
            "Po progu %, np. 20"
        )

        above_input.setMinimumHeight(
            34
        )

        # Podgląd na żywo - wynik liczy się już podczas wpisywania progu
        # i obu procentów, jeszcze przed kliknięciem "Dodaj" (patrz
        # _resolve_combined_data).
        value_input.textChanged.connect(
            self.calculate
        )

        below_input.textChanged.connect(
            self.calculate
        )

        above_input.textChanged.connect(
            self.calculate
        )

        add_button = QtWidgets.QPushButton(
            "Dodaj"
        )

        add_button.setMinimumHeight(
            34
        )

        percents_row_layout.addWidget(
            below_input
        )

        percents_row_layout.addWidget(
            above_input
        )

        percents_row_layout.addWidget(
            add_button
        )

        layout.addLayout(
            percents_row_layout
        )

        # ------------------------------------------------------
        # LISTA ZAPISANYCH PROGÓW
        # ------------------------------------------------------

        list_widget = QtWidgets.QListWidget()

        list_widget.setMaximumHeight(
            70
        )

        layout.addWidget(
            list_widget
        )

        remove_row_layout = QtWidgets.QHBoxLayout()

        remove_row_layout.addStretch()

        remove_button = QtWidgets.QPushButton(
            "Usuń zaznaczony"
        )

        remove_row_layout.addWidget(
            remove_button
        )

        layout.addLayout(
            remove_row_layout
        )

        return (
            page,
            value_input,
            below_input,
            above_input,
            add_button,
            list_widget,
            remove_button
        )

    # ==========================================================
    # OBSZAR PRZEWIJANIA ZAKŁADKI
    # ==========================================================

    def _scrollable(self, page):
        """Owija stronę zakładki w pionowy obszar przewijania.

        Dzięki temu pełna zawartość (łącznie z całym blokiem "Wynik")
        jest osiągalna także wtedy, gdy okno nie mieści się na ekranie.
        """

        scroll = QtWidgets.QScrollArea()

        scroll.setWidget(page)

        scroll.setWidgetResizable(True)

        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        return scroll

    # ==========================================================
    # ZAKŁADKA LEKTORZY – INTERFEJS
    # ==========================================================
    #
    # Kalkulator przelicza materiał (znaki ze spacjami albo arkusze
    # wydawnicze) na czas nagrania i koszt lektora. Stawki brane są
    # z edytowalnej listy lektorów (lectors.py -> Databases/lectors.json).
    #
    #   1 arkusz wydawniczy = 40 000 znaków ze spacjami
    #   lektor czyta arkusz w ok. 50 min (tylko informacyjnie)
    #   stawka lektora i narzut Audio Opus podane są za arkusz wydawniczy
    #   1 pełny arkusz = pełna stawka, niepełny - proporcjonalnie
    # ==========================================================

    def build_lectors_page(self):

        page = QtWidgets.QWidget()

        layout = QtWidgets.QVBoxLayout(page)

        layout.setContentsMargins(24, 24, 24, 24)

        layout.setSpacing(14)

        title = QtWidgets.QLabel(
            "Kalkulator lektorów"
        )

        title.setProperty(
            "role",
            "Title"
        )

        layout.addWidget(title)

        subtitle = QtWidgets.QLabel(
            "1 arkusz wydawniczy = 40 000 znaków ze spacjami "
            "(lektor czyta arkusz w ok. 50 minut). Stawki podane są "
            "za arkusz wydawniczy; 1 pełny arkusz = pełna stawka, "
            "niepełny arkusz liczony jest proporcjonalnie."
        )

        subtitle.setWordWrap(True)

        layout.addWidget(subtitle)

        # ------------------------------------------------------
        # MATERIAŁ
        # ------------------------------------------------------

        material_group = QtWidgets.QGroupBox(
            "Materiał"
        )

        material_layout = QtWidgets.QFormLayout()

        material_layout.setContentsMargins(12, 12, 12, 12)

        material_layout.setSpacing(8)

        # Jednostka, w której podajemy objętość materiału. Nominalnie
        # znaki ze spacjami; można przełączyć na arkusze - kalkulator
        # i tak wszystko sprowadza do znaków (1 arkusz = 40 000 zzs).
        self.material_unit_combo = QtWidgets.QComboBox()
        self.material_unit_combo.addItem("Znaki ze spacjami", "chars")
        self.material_unit_combo.addItem("Arkusze wydawnicze", "sheets")
        self.material_unit_combo.setMinimumHeight(38)
        self.material_unit_combo.currentIndexChanged.connect(
            self._on_material_unit_changed
        )

        material_layout.addRow("Jednostka:", self.material_unit_combo)

        self.lector_amount_input = QtWidgets.QLineEdit()

        self.lector_amount_input.setPlaceholderText("np. 210000")

        self.lector_amount_input.setMinimumHeight(38)

        self.lector_amount_input.textChanged.connect(
            self.calculate_lector
        )

        material_layout.addRow("Ilość:", self.lector_amount_input)

        # Przeliczenie wpisanej objętości na arkusze + czas - widoczne
        # od razu, jeszcze przed wybraniem lektora.
        self.lector_material_breakdown = QtWidgets.QLabel("")
        self.lector_material_breakdown.setTextFormat(
            Qt.TextFormat.PlainText
        )
        self.lector_material_breakdown.setFixedHeight(56)
        self.lector_material_breakdown.setAlignment(
            Qt.AlignmentFlag.AlignTop
        )
        self.lector_material_breakdown.setStyleSheet(
            "font-size: 11px; color: palette(mid);"
        )
        material_layout.addRow("Przeliczenie:", self.lector_material_breakdown)

        material_group.setLayout(material_layout)

        layout.addWidget(material_group)

        # ------------------------------------------------------
        # LEKTOR
        # ------------------------------------------------------

        lector_group = QtWidgets.QGroupBox(
            "Lektor"
        )

        lector_layout = QtWidgets.QVBoxLayout()

        lector_layout.setContentsMargins(12, 12, 12, 12)

        lector_layout.setSpacing(8)

        self.lector_combo = QtWidgets.QComboBox()

        self.lector_combo.setMinimumHeight(38)

        self.lector_combo.currentIndexChanged.connect(
            self.on_lector_selected
        )

        lector_layout.addWidget(self.lector_combo)

        self.lector_rate_label = QtWidgets.QLabel("")

        self.lector_rate_label.setWordWrap(True)

        self.lector_rate_label.setStyleSheet(
            "font-size: 11px; color: palette(mid);"
        )

        lector_layout.addWidget(self.lector_rate_label)

        lector_buttons = QtWidgets.QHBoxLayout()

        lector_buttons.setSpacing(6)

        self.add_lector_button = QtWidgets.QPushButton("Dodaj")

        self.edit_lector_button = QtWidgets.QPushButton("Edytuj")

        self.remove_lector_button = QtWidgets.QPushButton("Usuń")

        for button in (
            self.add_lector_button,
            self.edit_lector_button,
            self.remove_lector_button
        ):
            button.setMinimumHeight(34)
            lector_buttons.addWidget(button)

        self.add_lector_button.clicked.connect(self.add_lector)

        self.edit_lector_button.clicked.connect(self.edit_lector)

        self.remove_lector_button.clicked.connect(self.remove_lector)

        lector_layout.addLayout(lector_buttons)

        lector_group.setLayout(lector_layout)

        layout.addWidget(lector_group)

        # ------------------------------------------------------
        # WYNIK
        # ------------------------------------------------------

        result_group = QtWidgets.QGroupBox(
            "Wynik"
        )

        result_layout = QtWidgets.QFormLayout()

        result_layout.setContentsMargins(12, 12, 12, 12)

        result_layout.setSpacing(6)

        # Stawka VAT - globalna dla kalkulatora, więc edytowalna od razu tu,
        # przy wyniku, zamiast schowana w ustawieniach albo przy lektorze.
        self.lector_vat_input = QtWidgets.QLineEdit()

        self.lector_vat_input.setFixedWidth(64)

        self.lector_vat_input.setMinimumHeight(32)

        self.lector_vat_input.setText(self._format_vat_text())

        self.lector_vat_input.editingFinished.connect(self._on_vat_changed)

        result_layout.addRow("Stawka VAT (%):", self.lector_vat_input)

        self.lector_result_lector = QtWidgets.QLabel("0,00 zł")

        self.lector_result_surcharge = QtWidgets.QLabel("0,00 zł")

        self.lector_result_net = QtWidgets.QLabel("0,00 zł")

        self.lector_result_vat = QtWidgets.QLabel("0,00 zł")

        self.lector_result_gross = QtWidgets.QLabel("0,00 zł")

        bold_font = self.lector_result_net.font()

        bold_font.setBold(True)

        self.lector_result_net.setFont(bold_font)

        self.lector_result_gross.setFont(bold_font)

        result_layout.addRow(
            "Wynagrodzenie lektora (netto):",
            self.lector_result_lector
        )

        result_layout.addRow(
            "Narzut Audio Opus (netto):",
            self.lector_result_surcharge
        )

        result_layout.addRow(
            "Netto dla klienta:",
            self.lector_result_net
        )

        self.lector_vat_row_label = QtWidgets.QLabel("VAT:")

        result_layout.addRow(
            self.lector_vat_row_label,
            self.lector_result_vat
        )

        result_layout.addRow(
            "Brutto dla klienta:",
            self.lector_result_gross
        )

        self.lector_result_breakdown = QtWidgets.QLabel(
            "Podaj objętość materiału, aby zobaczyć wyliczenie."
        )

        self.lector_result_breakdown.setWordWrap(True)

        self.lector_result_breakdown.setStyleSheet(
            "font-size: 11px; color: palette(mid);"
        )

        result_layout.addRow(self.lector_result_breakdown)

        result_group.setLayout(result_layout)

        layout.addWidget(result_group)

        # ------------------------------------------------------
        # PRZYCISKI
        # ------------------------------------------------------

        buttons_layout = QtWidgets.QHBoxLayout()

        buttons_layout.setSpacing(6)

        buttons_layout.addStretch()

        self.lector_clear_button = QtWidgets.QPushButton("Wyczyść")

        self.lector_clear_button.setMinimumHeight(36)

        self.lector_clear_button.clicked.connect(self.clear_lector)

        buttons_layout.addWidget(self.lector_clear_button)

        layout.addLayout(buttons_layout)

        layout.addStretch()

        self.setup_lector_validators()

        return page

    # ==========================================================
    # ZAKŁADKA LEKTORZY – WALIDACJA
    # ==========================================================

    def setup_lector_validators(self):

        # Walidator pola "Ilość" zależy od jednostki - ustawia go
        # _on_material_unit_changed, które wołamy raz na starcie.
        self._on_material_unit_changed()

        percent_regex = QRegularExpression(
            r"^(100([,.]0{0,2})?|([0-9]{0,2})([,.]\d{0,2})?)$"
        )

        self.lector_vat_input.setValidator(
            QRegularExpressionValidator(percent_regex, self)
        )

    # ==========================================================
    # ZAKŁADKA LEKTORZY – LISTA LEKTORÓW
    # ==========================================================

    def reload_lectors(self, select_name=None):
        """Wczytuje listę lektorów z pliku i odświeża listę rozwijaną."""

        self._lectors = lectors.load_lectors()

        self.lector_combo.blockSignals(True)

        self.lector_combo.clear()

        for lector in self._lectors:

            self.lector_combo.addItem(lector["name"], lector)

        self.lector_combo.blockSignals(False)

        if select_name is not None:

            index = self.lector_combo.findText(select_name)

            if index >= 0:
                self.lector_combo.setCurrentIndex(index)

        self.on_lector_selected()

    def current_lector(self):
        """Zwraca słownik aktualnie wybranego lektora albo None.

        Lista rozwijana jest zapełniana z self._lectors w tej samej
        kolejności, więc indeks w combo odpowiada wprost pozycji na
        liście. Dzięki temu edycja / usuwanie działa na tym samym
        obiekcie, który potem zapisujemy na dysk.
        """

        index = self.lector_combo.currentIndex()

        if index < 0 or index >= len(self._lectors):
            return None

        return self._lectors[index]

    def add_lector(self):

        data = LectorEditDialog.get_lector(self)

        if data is None:
            return

        if any(
            existing["name"].lower() == data["name"].lower()
            for existing in self._lectors
        ):
            QtWidgets.QMessageBox.information(
                self,
                "Lektor już istnieje",
                "Lektor o takiej nazwie jest już na liście."
            )
            return

        saved = lectors.add_lector(data)

        self.reload_lectors(select_name=saved["name"])

    def edit_lector(self):

        lector = self.current_lector()

        if lector is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak lektora",
                "Najpierw wybierz lektora z listy."
            )
            return

        data = LectorEditDialog.get_lector(self, lector)

        if data is None:
            return

        if any(
            existing is not lector
            and existing["name"].lower() == data["name"].lower()
            for existing in self._lectors
        ):
            QtWidgets.QMessageBox.information(
                self,
                "Lektor już istnieje",
                "Inny lektor ma już taką nazwę."
            )
            return

        lectors.update_lector(lector["id"], data)

        self.reload_lectors(select_name=data["name"])

    def remove_lector(self):

        lector = self.current_lector()

        if lector is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak lektora",
                "Najpierw wybierz lektora z listy."
            )
            return

        confirmed = confirm_yes_no(
            self,
            "Potwierdzenie usunięcia",
            f"Czy na pewno usunąć lektora:\n{lector['name']}?"
        )

        if not confirmed:
            return

        lectors.remove_lector(lector["id"])

        self.reload_lectors()

    # ==========================================================
    # ZAKŁADKA LEKTORZY – REAKCJE NA ZMIANY
    # ==========================================================

    def on_lector_selected(self):

        lector = self.current_lector()

        if lector is None:
            self.lector_rate_label.setText(
                "Dodaj lektora, aby policzyć koszt nagrania."
            )
        else:
            self.lector_rate_label.setText(
                "Stawka lektora: "
                + sheet_math.format_rate(lector["rate"])
                + "  ·  narzut Audio Opus: "
                + sheet_math.format_rate(lector["surcharge"])
            )

        self.calculate_lector()

    # ==========================================================
    # ZAKŁADKA LEKTORZY – GŁÓWNE OBLICZENIE
    # ==========================================================

    # ==========================================================
    # ZAKŁADKA LEKTORZY – JEDNOSTKA MATERIAŁU
    # ==========================================================

    def _material_unit(self):
        return self.material_unit_combo.currentData()

    def _material_chars(self):
        """Sprowadza wpisaną objętość do znaków ze spacjami. None, gdy pusto."""
        value = commission_math.parse_number(self.lector_amount_input.text())

        if value is None or value < 0:
            return None

        if self._material_unit() == "sheets":
            return sheet_math.chars_from_sheets(value)
        return value

    def _on_material_unit_changed(self, _index=None):
        if self._material_unit() == "sheets":
            self.lector_amount_input.setPlaceholderText("np. 5,25")
            regex = r"^\d{0,9}([,.]\d{0,3})?$"
        else:
            self.lector_amount_input.setPlaceholderText("np. 210000")
            regex = r"^\d{0,12}$"

        self.lector_amount_input.setValidator(
            QRegularExpressionValidator(QRegularExpression(regex), self)
        )

        self.calculate_lector()

    def _update_material_breakdown(self):
        """Rozpisuje wpisaną objętość na znaki, arkusze i czas nagrania
        - niezależnie od tego, czy wybrano lektora."""

        chars = self._material_chars()

        if chars is None or chars <= 0:
            self.lector_material_breakdown.setText("")
            return

        sheets = sheet_math.sheets_from_chars(chars)
        minutes = sheet_math.reading_minutes(sheets)

        self.lector_material_breakdown.setText(
            "•  " + sheet_math.format_chars(chars) + "\n"
            "•  " + sheet_math.format_sheets(sheets) + "  (arkusze wydawnicze)\n"
            "•  ok. " + sheet_math.format_duration(minutes) + " nagrania"
        )

    def _format_vat_text(self):
        # format_percent() zwraca np. "23%" - odcinamy znak procentu,
        # bo pole jest edytowalne (sam symbol % stoi obok, poza polem).
        return commission_math.format_percent(self._vat_percent)[:-1]

    def _on_vat_changed(self):
        """Zmiana stawki VAT wpisanej przy wyniku - waliduje, zapisuje do
        konfiguracji i od razu przelicza."""

        value = commission_math.parse_number(self.lector_vat_input.text())

        if value is None or value < 0 or value > 100:
            self.lector_vat_input.setText(self._format_vat_text())
            return

        try:
            calculator_config.save_vat_percent(value)
        except OSError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd zapisu",
                f"Nie udało się zapisać stawki VAT:\n{error}"
            )
            return

        self._vat_percent = value

        self.lector_vat_input.setText(self._format_vat_text())

        self.calculate_lector()

    def calculate_lector(self):

        self._update_material_breakdown()

        chars = self._material_chars()

        lector = self.current_lector()

        if chars is None or chars <= 0 or lector is None:

            self.show_lector_result(None, lector)

            return

        sheets = sheet_math.sheets_from_chars(chars)

        result = sheet_math.calculate_cost(
            sheets,
            lector["rate"],
            lector["surcharge"],
            vat_rate=self._vat_percent
        )

        self.show_lector_result(result, lector)

    def show_lector_result(self, result, lector):

        if result is None:

            for label in (
                self.lector_result_lector,
                self.lector_result_surcharge,
                self.lector_result_net,
                self.lector_result_vat,
                self.lector_result_gross
            ):
                label.setText("0,00 zł")

            self.lector_vat_row_label.setText("VAT:")

            if lector is None:
                self.lector_result_breakdown.setText(
                    "Dodaj i wybierz lektora, aby zobaczyć wyliczenie."
                )
            else:
                self.lector_result_breakdown.setText(
                    "Podaj objętość materiału, aby zobaczyć wyliczenie."
                )

            return

        self.lector_result_lector.setText(
            commission_math.format_money(result["lector_amount"])
        )

        self.lector_result_surcharge.setText(
            commission_math.format_money(result["surcharge_amount"])
        )

        self.lector_result_net.setText(
            commission_math.format_money(result["client_net"])
        )

        self.lector_vat_row_label.setText(
            "VAT "
            + commission_math.format_percent(result["vat_rate"])
            + ":"
        )

        self.lector_result_vat.setText(
            commission_math.format_money(result["vat_amount"])
        )

        self.lector_result_gross.setText(
            commission_math.format_money(result["client_gross"])
        )

        self.lector_result_breakdown.setText(
            sheet_math.describe_cost(
                result,
                lector["name"] if lector else ""
            )
        )

    def clear_lector(self):

        self.material_unit_combo.setCurrentIndex(0)

        self.lector_amount_input.clear()

        self.lector_material_breakdown.setText("")

        self.show_lector_result(None, self.current_lector())

    # ==========================================================
    # WALIDACJA PÓL
    # ==========================================================

    def setup_validators(self):

        # ------------------------------------------------------
        # LICZBY
        # ------------------------------------------------------
        #
        # Dozwolone:
        #
        # 5000
        # 5000,50
        # 5000.50
        #
        # Litery są zablokowane.
        # ------------------------------------------------------

        number_regex = QRegularExpression(
            r"^\d{0,12}([,.]\d{0,2})?$"
        )

        number_validator = QRegularExpressionValidator(
            number_regex,
            self
        )

        self.amount_input.setValidator(
            number_validator
        )

        self.threshold_value_input.setValidator(
            number_validator
        )

        self.up_to_threshold_value_input.setValidator(
            number_validator
        )

        self.combined_value_input.setValidator(
            number_validator
        )

        # ------------------------------------------------------
        # PROCENTY
        # ------------------------------------------------------

        percent_regex = QRegularExpression(
            r"^(100([,.]0{0,2})?|([0-9]{0,2})([,.]\d{0,2})?)$"
        )

        percent_validator = QRegularExpressionValidator(
            percent_regex,
            self
        )

        self.fixed_percent_input.setValidator(
            percent_validator
        )

        self.threshold_cut_input.setValidator(
            percent_validator
        )

        self.up_to_threshold_cut_input.setValidator(
            percent_validator
        )

        self.combined_below_input.setValidator(
            percent_validator
        )

        self.combined_above_input.setValidator(
            percent_validator
        )

    # ==========================================================
    # ZMIANA TYPU PROWIZJI
    # ==========================================================

    def on_type_changed(self):

        commission_type = (
            self.type_combo.currentData()
        )

        if commission_type == "instant":

            self.commission_stack.setCurrentWidget(
                self.fixed_page
            )

        elif commission_type == "up_to_threshold":

            self.commission_stack.setCurrentWidget(
                self.up_to_threshold_page
            )

        elif commission_type == "combined":

            self.commission_stack.setCurrentWidget(
                self.combined_page
            )

        else:

            self.commission_stack.setCurrentWidget(
                self.threshold_page
            )

        self.calculate()

    # ==========================================================
    # GŁÓWNE OBLICZENIE
    # ==========================================================

    def calculate(self):

        amount = commission_math.parse_number(
            self.amount_input.text()
        )

        commission_type = (
            self.type_combo.currentData()
        )

        if amount is None or amount < 0:

            self.show_result(
                amount=0,
                client_amount=0,
                platform_amount=0,
                excess=0,
                breakdown="Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."
            )

            return

        # ======================================================
        # OD RAZU
        # ======================================================

        if commission_type == "instant":

            result = self.calculate_fixed(
                amount
            )

        # ======================================================
        # DO I PO PROGU
        # ======================================================

        elif commission_type == "combined":

            result = self.calculate_combined(
                amount
            )

        # ======================================================
        # PO PROGU / DO PROGU
        # ======================================================

        else:

            result = self.calculate_threshold(
                amount,
                commission_type
            )

        if result is None:

            self.show_result(
                amount=amount,
                client_amount=0,
                platform_amount=0,
                excess=0,
                breakdown="Prowizja AO musi być w zakresie 0-100%."
            )

            return

        client_amount = result["client_amount"]

        platform_amount = result["platform_amount"]

        excess = result["excess"]

        breakdown = self.build_breakdown(
            commission_type,
            amount,
            client_amount,
            platform_amount,
            excess
        )

        self.show_result(
            amount=amount,
            client_amount=client_amount,
            platform_amount=platform_amount,
            excess=excess,
            breakdown=breakdown
        )

    # ==========================================================
    # OPIS WYLICZENIA (TEKST)
    # ==========================================================

    def build_breakdown(
        self,
        commission_type,
        amount,
        client_amount,
        platform_amount,
        excess
    ):

        if amount <= 0:

            return "Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."

        # ------------------------------------------------------
        # OD RAZU
        # ------------------------------------------------------

        if commission_type == "instant":

            percent = commission_math.parse_number(
                self.fixed_percent_input.text()
            )

            if percent is None:

                return "Podaj prowizję AO, aby zobaczyć wyliczenie."

            return commission_math.describe_fixed(
                amount,
                percent,
                client_amount,
                platform_amount
            )

        # ------------------------------------------------------
        # DO I PO PROGU
        # ------------------------------------------------------

        if commission_type == "combined":

            data = self._resolve_combined_data()

            if data is None:

                return "Dodaj i wybierz próg z listy, aby zobaczyć wyliczenie."

            split = commission_math.split_combined(
                amount,
                data["threshold"],
                data["below"],
                data["above"]
            )

            return commission_math.describe_combined(
                amount,
                data["threshold"],
                data["below"],
                data["above"],
                client_amount,
                platform_amount,
                excess,
                split["platform_below"],
                split["platform_above"]
            )

        # ------------------------------------------------------
        # PO PROGU / DO PROGU
        # ------------------------------------------------------

        value_input, cut_input, list_widget = self._threshold_widgets(
            commission_type
        )

        data = self._resolve_threshold_data(
            value_input,
            cut_input,
            list_widget
        )

        if data is None:

            return "Dodaj i wybierz próg z listy, aby zobaczyć wyliczenie."

        if commission_type == "up_to_threshold":

            return commission_math.describe_up_to_threshold(
                amount,
                data["threshold"],
                data["cut"],
                client_amount,
                platform_amount,
                excess
            )

        return commission_math.describe_threshold(
            amount,
            data["threshold"],
            data["cut"],
            client_amount,
            platform_amount,
            excess
        )

    # ==========================================================
    # PROWIZJA STAŁA
    # ==========================================================
    #
    # Wyliczenie zostało przeniesione do commission_math.split_fixed,
    # żeby dało się je testować bez GUI. Tutaj tylko odczytujemy
    # wartość z pola i przekazujemy dalej.
    # ==========================================================

    def calculate_fixed(
        self,
        amount
    ):

        percent = commission_math.parse_number(
            self.fixed_percent_input.text()
        )

        if percent is None:

            return {
                "client_amount": 0,
                "platform_amount": 0,
                "excess": 0
            }

        return commission_math.split_fixed(
            amount,
            percent
        )

    # ==========================================================
    # PROWIZJA PROGOWA
    # ==========================================================
    #
    # "Po progu": prog jako odliczenie, prowizja liczona od nadwyzki -
    # commission_math.split_threshold, ta sama logika, co w produktach /
    # report_generator.py (compute_settlement_rows).
    #
    # "Do progu": prowizja liczona od kwoty do progu, a nadwyzka ponad
    # prog w calosci trafia do klienta - commission_math.split_up_to_
    # threshold.
    # ==========================================================

    def _threshold_widgets(self, commission_type):
        """Zwraca (pole wartości progu, pole procentu, listę) właściwe dla
        trybu "threshold" (Po progu) albo "up_to_threshold" (Do progu)."""

        if commission_type == "up_to_threshold":

            return (
                self.up_to_threshold_value_input,
                self.up_to_threshold_cut_input,
                self.up_to_threshold_list
            )

        return (
            self.threshold_value_input,
            self.threshold_cut_input,
            self.threshold_list
        )

    def _resolve_threshold_data(self, value_input, cut_input, list_widget):
        """Zwraca dane progu do obliczenia.

        Jeśli pola "nowy próg" zawierają kompletne, poprawne wartości, wynik
        liczy się na żywo z nich - jeszcze przed kliknięciem "Dodaj". W
        przeciwnym razie liczy się próg zaznaczony na liście zapisanych
        progów. Zwraca None, gdy nie ma ani jednego, ani drugiego.
        """

        threshold = commission_math.parse_number(
            value_input.text()
        )

        cut_percent = commission_math.parse_number(
            cut_input.text()
        )

        if (
            threshold is not None and threshold >= 0
            and cut_percent is not None and 0 <= cut_percent <= 100
        ):

            return {
                "threshold": threshold,
                "cut": cut_percent
            }

        item = list_widget.currentItem()

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

    def calculate_threshold(
        self,
        amount,
        commission_type
    ):

        value_input, cut_input, list_widget = self._threshold_widgets(
            commission_type
        )

        data = self._resolve_threshold_data(
            value_input,
            cut_input,
            list_widget
        )

        # ------------------------------------------------------
        # BRAK PODANEGO / WYBRANEGO PROGU
        # ------------------------------------------------------

        if data is None:

            return {
                "client_amount": 0,
                "platform_amount": 0,
                "excess": 0
            }

        if commission_type == "up_to_threshold":

            return commission_math.split_up_to_threshold(
                amount,
                data["threshold"],
                data["cut"]
            )

        return commission_math.split_threshold(
            amount,
            data["threshold"],
            data["cut"]
        )

    # ==========================================================
    # PROWIZJA "DO I PO PROGU" (JEDEN PRÓG, DWIE PROWIZJE)
    # ==========================================================
    #
    # commission_math.split_combined - część kwoty do progu liczona wg
    # pierwszej prowizji, nadwyżka ponad próg wg drugiej.
    # ==========================================================

    def _resolve_combined_data(self):
        """Odpowiednik _resolve_threshold_data dla trybu "Do i po progu" -
        podgląd na żywo z pól "nowy próg" (próg + dwa procenty), jeśli są
        kompletne i poprawne, w przeciwnym razie próg wybrany z listy."""

        threshold = commission_math.parse_number(
            self.combined_value_input.text()
        )

        below_percent = commission_math.parse_number(
            self.combined_below_input.text()
        )

        above_percent = commission_math.parse_number(
            self.combined_above_input.text()
        )

        if (
            threshold is not None and threshold >= 0
            and below_percent is not None and 0 <= below_percent <= 100
            and above_percent is not None and 0 <= above_percent <= 100
        ):

            return {
                "threshold": threshold,
                "below": below_percent,
                "above": above_percent
            }

        item = self.combined_list.currentItem()

        if item is None:
            return None

        return item.data(
            Qt.ItemDataRole.UserRole
        )

    def calculate_combined(
        self,
        amount
    ):

        data = self._resolve_combined_data()

        # ------------------------------------------------------
        # BRAK PODANEGO / WYBRANEGO PROGU
        # ------------------------------------------------------

        if data is None:

            return {
                "client_amount": 0,
                "platform_amount": 0,
                "excess": 0
            }

        return commission_math.split_combined(
            amount,
            data["threshold"],
            data["below"],
            data["above"]
        )

    # ==========================================================
    # DODANIE PROGU DO LISTY
    # ==========================================================

    def add_threshold(self, value_input, cut_input, list_widget):

        threshold = commission_math.parse_number(
            value_input.text()
        )

        cut_percent = commission_math.parse_number(
            cut_input.text()
        )

        if threshold is None or threshold < 0:

            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy próg",
                "Podaj prawidłową kwotę progu."
            )

            return

        if cut_percent is None or cut_percent < 0 or cut_percent > 100:

            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy procent",
                "Podaj procent platformy w zakresie 0-100."
            )

            return

        item = QtWidgets.QListWidgetItem(
            "Próg: "
            + commission_math.format_money(threshold)
            + " — platforma "
            + commission_math.format_percent(cut_percent)
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            {
                "threshold": threshold,
                "cut": cut_percent
            }
        )

        list_widget.addItem(
            item
        )

        list_widget.setCurrentItem(
            item
        )

        value_input.clear()

        cut_input.clear()

        self.calculate()

    # ==========================================================
    # DODANIE PROGU "DO I PO PROGU" DO LISTY
    # ==========================================================

    def add_combined_threshold(self):

        threshold = commission_math.parse_number(
            self.combined_value_input.text()
        )

        below_percent = commission_math.parse_number(
            self.combined_below_input.text()
        )

        above_percent = commission_math.parse_number(
            self.combined_above_input.text()
        )

        if threshold is None or threshold < 0:

            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy próg",
                "Podaj prawidłową kwotę progu."
            )

            return

        if below_percent is None or below_percent < 0 or below_percent > 100:

            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy procent",
                "Podaj procent platformy do progu w zakresie 0-100."
            )

            return

        if above_percent is None or above_percent < 0 or above_percent > 100:

            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy procent",
                "Podaj procent platformy po progu w zakresie 0-100."
            )

            return

        item = QtWidgets.QListWidgetItem(
            "Próg: "
            + commission_math.format_money(threshold)
            + " — do progu "
            + commission_math.format_percent(below_percent)
            + ", po progu "
            + commission_math.format_percent(above_percent)
        )

        item.setData(
            Qt.ItemDataRole.UserRole,
            {
                "threshold": threshold,
                "below": below_percent,
                "above": above_percent
            }
        )

        self.combined_list.addItem(
            item
        )

        self.combined_list.setCurrentItem(
            item
        )

        self.combined_value_input.clear()

        self.combined_below_input.clear()

        self.combined_above_input.clear()

        self.calculate()

    # ==========================================================
    # USUNIĘCIE ZAZNACZONEGO PROGU
    # ==========================================================

    def remove_threshold(self, list_widget):

        row = list_widget.currentRow()

        if row < 0:
            return

        list_widget.takeItem(
            row
        )

        self.calculate()

    # ==========================================================
    # POKAZANIE WYNIKU
    # ==========================================================

    def show_result(
        self,
        amount,
        client_amount,
        platform_amount,
        excess,
        breakdown=""
    ):

        self.result_amount.setText(
            commission_math.format_money(
                amount
            )
        )

        self.result_excess.setText(
            commission_math.format_money(
                excess
            )
        )

        self.result_client.setText(
            commission_math.format_money(
                client_amount
            )
        )

        self.result_platform.setText(
            commission_math.format_money(
                platform_amount
            )
        )

        self.result_breakdown.setText(
            breakdown
        )

    # ==========================================================
    # WYCZYŚĆ
    # ==========================================================

    def clear(self):

        self.amount_input.clear()

        self.fixed_percent_input.clear()

        self.threshold_value_input.clear()

        self.threshold_cut_input.clear()

        self.threshold_list.clear()

        self.up_to_threshold_value_input.clear()

        self.up_to_threshold_cut_input.clear()

        self.up_to_threshold_list.clear()

        self.combined_value_input.clear()

        self.combined_below_input.clear()

        self.combined_above_input.clear()

        self.combined_list.clear()

        self.show_result(
            amount=0,
            client_amount=0,
            platform_amount=0,
            excess=0,
            breakdown="Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."
        )


# ==========================================================
# OKNO DODAWANIA / EDYCJI LEKTORA
# ==========================================================
#
# Stawki lektorów zmieniają się w czasie, dlatego są edytowalne.
# To małe okno służy zarówno do dodania nowego lektora, jak i do
# zmiany stawek istniejącego. Kwoty podawane są za arkusz wydawniczy.
#
# Stawka VAT (wspólna dla wszystkich lektorów) jest teraz w
# Ustawienia -> Kalkulator, nie tutaj.
# ==========================================================

class LectorEditDialog(QtWidgets.QDialog):

    def __init__(self, parent=None, lector=None):
        super().__init__(parent)

        self.setWindowTitle(
            "Edytuj lektora" if lector else "Dodaj lektora"
        )

        self.setMinimumWidth(360)

        layout = QtWidgets.QVBoxLayout(self)

        layout.setContentsMargins(20, 20, 20, 20)

        layout.setSpacing(12)

        form = QtWidgets.QFormLayout()

        form.setSpacing(8)

        self.name_input = QtWidgets.QLineEdit()

        self.name_input.setMinimumHeight(36)

        self.rate_input = QtWidgets.QLineEdit()

        self.rate_input.setMinimumHeight(36)

        self.rate_input.setPlaceholderText("np. 400")

        self.surcharge_input = QtWidgets.QLineEdit()

        self.surcharge_input.setMinimumHeight(36)

        self.surcharge_input.setPlaceholderText("np. 50")

        money_regex = QRegularExpression(
            r"^\d{0,7}([,.]\d{0,2})?$"
        )

        money_validator = QRegularExpressionValidator(money_regex, self)

        self.rate_input.setValidator(money_validator)

        self.surcharge_input.setValidator(money_validator)

        form.addRow("Lektor:", self.name_input)

        form.addRow("Stawka lektora (zł/arkusz netto):", self.rate_input)

        form.addRow("Narzut Audio Opus (zł/arkusz netto):", self.surcharge_input)

        layout.addLayout(form)

        hint = QtWidgets.QLabel(
            "Kwoty netto za arkusz wydawniczy (40 000 znaków ze spacjami). "
            "Stawkę VAT zmienisz w Ustawienia -> Kalkulator."
        )

        hint.setWordWrap(True)

        hint.setStyleSheet("font-size: 11px; color: palette(mid);")

        layout.addWidget(hint)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        buttons.accepted.connect(self.accept)

        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        if lector:
            self.name_input.setText(lector["name"])
            self.rate_input.setText(_money_to_text(lector["rate"]))
            self.surcharge_input.setText(_money_to_text(lector["surcharge"]))

    def accept(self):

        name = self.name_input.text().strip()

        rate = commission_math.parse_number(self.rate_input.text())

        surcharge = commission_math.parse_number(self.surcharge_input.text())

        if not name:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak nazwy",
                "Podaj nazwę lektora."
            )
            return

        if rate is None or rate < 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowa stawka",
                "Podaj prawidłową stawkę lektora (zł za arkusz)."
            )
            return

        if surcharge is None or surcharge < 0:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowy narzut",
                "Podaj prawidłowy narzut Audio Opus (zł za arkusz)."
            )
            return

        self._result = {
            "name": name,
            "rate": rate,
            "surcharge": surcharge,
        }

        super().accept()

    @classmethod
    def get_lector(cls, parent, lector=None):
        """Otwiera okno i zwraca słownik lektora albo None (anulowano)."""

        dialog = cls(parent, lector)

        if dialog.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            return dialog._result

        return None


def _money_to_text(value):
    """Zamienia liczbę na tekst do pola formularza (bez zbędnych zer)."""

    text = f"{float(value):.2f}".rstrip("0").rstrip(".")

    return text.replace(".", ",")