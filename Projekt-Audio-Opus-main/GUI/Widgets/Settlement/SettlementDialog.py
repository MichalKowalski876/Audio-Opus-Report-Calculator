import os
from datetime import datetime
from PySide6 import QtWidgets, QtCore, QtGui, QtPdf, QtPdfWidgets
from core import database_controller
from core import report_generator
from core import settlement_numbers
from GUI.style.theme_manager import ThemeManager
from platforms.report_calculator import ReportCalculationError, relink_unmatched_rows
from platforms.reports import safe_platform_filename
from platforms.settlement_amounts import (
    ALL_PERIODS,
    SettlementAmountsError,
    available_periods,
    is_quarter,
    load_amounts,
    period_span,
)

REPORTS_FOLDER = report_generator.FOLDER

MONTH_NAMES = (
    "Styczeń", "Luty", "Marzec", "Kwiecień", "Maj", "Czerwiec",
    "Lipiec", "Sierpień", "Wrzesień", "Październik", "Listopad", "Grudzień",
)

QUARTER_NAMES = ("I", "II", "III", "IV")


class _QuickAddKeyFilter(QtCore.QObject):
    """Enter w polu szybkiego dodawania zawsze dodaje pozycję - również gdy
    otwarta jest lista podpowiedzi (domyślnie QCompleter w tej sytuacji Enter
    tylko chowa listę)."""

    def __init__(self, dialog):
        super().__init__(dialog)
        self._dialog = dialog

    def eventFilter(self, obj, event):
        if event.type() == QtCore.QEvent.Type.KeyPress and event.key() in (
            QtCore.Qt.Key.Key_Return,
            QtCore.Qt.Key.Key_Enter,
        ):
            self._dialog._commit_quick_add_from_field()
            return True
        return super().eventFilter(obj, event)


class SettlementDialog(QtWidgets.QDialog):

    def __init__(self, parent=None, email_mode=False, folder_output=None):
        super().__init__(parent)

        self.email_mode = email_mode
        self.folder_output = folder_output or REPORTS_FOLDER
        self.generated_file_path = None
        self.is_existing_file = False
        self.selected_client_email = None

        if self.email_mode:
            self.setWindowTitle("Wybór danych do wiadomości e-mail")
        else:
            self.setWindowTitle("Nowe rozliczenie")
        self.resize(1100, 640)

        self.clients = database_controller.load_database("clients")
        self.streamings = database_controller.load_database("streamings")
        self.products = database_controller.load_database("products")

        # Pozycje raportów dopasowuje się do książek przy „Przelicz raporty”.
        # Książka dodana później nie miałaby swoich kwot aż do ponownego
        # przeliczenia - dopinamy je tutaj, zanim zbudujemy listę pozycji.
        self._relink_report_rows()

        self.client_box = QtWidgets.QComboBox()
        self.client_box.addItem("", None)

        for client in sorted(
            self.clients, key=lambda c: str(c.get("name") or "").casefold()
        ):
            self.client_box.addItem(
                f"{client['name']}",
                client["id"]
            )

        self.period_box = QtWidgets.QComboBox()
        # Zakresy dat okresów kwartalnych - uzupełnia _build_period_box.
        self._period_spans = {}
        self._build_period_box()

        # Numer rozliczenia (RRRR/MM/NNN). Aplikacja podpowiada pierwszy wolny
        # numer w roku, ale można go nadpisać ręcznie - po ręcznej zmianie
        # przestajemy nadpisywać podpowiedź przy zmianie klienta/okresu.
        self.number_input = QtWidgets.QLineEdit()
        self.number_input.setPlaceholderText("RRRR/MM/NNN")
        self._number_touched = False
        self.number_input.textEdited.connect(self._on_number_edited)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels([
            "Produkt",
            "Platforma",
            "Netto (zł)",
            "Brutto (zł)",
            "Prowizja AO (%)"
        ])
        self.table.setRowCount(1)
        self.add_empty_row(0)

        table_header = self.table.horizontalHeader()
        table_header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        table_header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        table_header.setMinimumSectionSize(88)
        table_header.setDefaultAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        table_header.setFixedHeight(42)
        self.table.verticalHeader().setDefaultSectionSize(38)
        self.table.verticalHeader().setVisible(False)
        self.table.setWordWrap(False)
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.table.setMinimumHeight(150)
        self.table.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )

        self.remove_row_button = QtWidgets.QPushButton("Usuń zaznaczony wiersz")
        self.remove_row_button.setToolTip(
            "Możesz też nacisnąć klawisz Delete, gdy wiersz jest zaznaczony"
        )
        self.remove_row_button.clicked.connect(self.remove_selected_row)

        # Delete kasuje zaznaczony wiersz. Skrót jest przypięty do samej
        # tabeli z kontekstem WidgetShortcut (nie do całego okna) - dzięki
        # temu nie koliduje z Delete kasującym znak podczas edycji komórki
        # (Netto/Brutto/Prowizja): w trakcie edycji skupienie ma edytor
        # komórki, a nie tabela, więc skrót wtedy się nie uruchamia.
        self.delete_row_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete),
            self.table,
        )
        self.delete_row_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WidgetShortcut
        )
        self.delete_row_shortcut.activated.connect(self.remove_selected_row)

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Szukaj książki po tytule lub autorze...")
        self.search_input.setToolTip(
            "Wpisz tytuł i naciśnij Enter (albo kliknij podpowiedź z listy), "
            "żeby dodać pozycję do raportu"
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self._commit_quick_add_from_field)

        # Podpowiedzi szybkiego dodawania. Persistentny completer - model
        # podmieniamy w _build_product_search_completer(), nie tworzymy go od
        # nowa. Podpowiada, ale nic nie wpisuje na siłę (PopupCompletion),
        # a wybór pozycji zatwierdza dopiero Enter / klik.
        self._product_completer = QtWidgets.QCompleter(self)
        self._product_completer.setCaseSensitivity(
            QtCore.Qt.CaseSensitivity.CaseInsensitive
        )
        self._product_completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        self._product_completer.setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        self._product_completer.setMaxVisibleItems(12)
        self._product_completer.activated[str].connect(
            self._on_search_completion_activated
        )
        self.search_input.setCompleter(self._product_completer)

        # Enter w polu (także przy otwartej liście podpowiedzi) dodaje pozycję.
        # Domyślnie Qt przy otwartej liście łyka Enter i tylko ją chowa - stąd
        # własny filtr zdarzeń założony PO completerze, żeby złapać klawisz
        # pierwszy.
        self._search_key_filter = _QuickAddKeyFilter(self)
        self.search_input.installEventFilter(self._search_key_filter)

        self._quick_add_choices = []
        self._quick_add_by_label = {}
        self._quick_add_by_title = {}

        self.search_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+F"),
            self,
        )
        self.search_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.search_shortcut.activated.connect(
            self._focus_settlement_search
        )

        self._build_product_search_completer()

        if self.email_mode:
            self.generate_button = QtWidgets.QPushButton("Generuj PDF i załącz do e-maila")
        else:
            self.generate_button = QtWidgets.QPushButton("Generuj raport PDF")

        self.generate_button.setDefault(True)
        self.generate_button.clicked.connect(self.generate_report)
        self._style_primary_button(self.generate_button)

        if self.email_mode:
            self.attach_existing_button = QtWidgets.QPushButton("Załącz istniejący raport z komputera")
            self.attach_existing_button.clicked.connect(self.attach_existing_report)

        self.pdf_document = QtPdf.QPdfDocument(self)
        self.pdf_view = QtPdfWidgets.QPdfView(self)
        self.pdf_view.setPageMode(QtPdfWidgets.QPdfView.PageMode.MultiPage)
        self.pdf_view.setZoomMode(QtPdfWidgets.QPdfView.ZoomMode.FitToWidth)
        self.pdf_view.setDocument(self.pdf_document)
        self._pdf_buffer = None

        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(250)
        self._refresh_timer.timeout.connect(self._render_preview)

        self.client_box.currentIndexChanged.connect(self._on_client_changed)
        self.period_box.currentIndexChanged.connect(self._on_period_changed)
        self.table.itemChanged.connect(lambda _: self.schedule_preview())

        self.setup_layout()

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.enter_shortcut.activated.connect(
            self._handle_enter_pressed
        )

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(
            self._handle_enter_pressed
        )

        # Ustawia widok pod klienta zaznaczonego na starcie (podpowiedzi,
        # przełącznik "wszystkie książki") i wczytuje pozycje z bazy.
        self._on_client_changed()
        self._refresh_proposed_number()
        self._render_preview()

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        # Enter w polu szybkiego dodawania (albo w otwartej liście podpowiedzi)
        # dodaje pozycję - nie może uruchamiać generowania raportu.
        if self.search_input.hasFocus():
            return
        if self._product_completer.popup().isVisible():
            return
        self.generate_report()

    def _focus_settlement_search(self):
        if not self.isVisible():
            return
        self.search_input.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.search_input.selectAll()

    def _product_title(self, product):
        return (
                product.get("title") or product.get("tytul") or product.get("tytuł")
                or product.get("name") or product.get("nazwa")
                or f"(bez nazwy) #{product['id']}"
        )

    def _streaming_name(self, streaming):
        return (
                streaming.get("name") or streaming.get("nazwa")
                or streaming.get("title") or streaming.get("tytul") or streaming.get("tytuł")
                or f"(bez nazwy) #{streaming['id']}"
        )

    def _current_client_product_ids(self):
        """Zwraca zbiór ID książek przypisanych do aktualnie wybranego klienta."""
        client = self._current_client()
        if not client:
            return None
        return set(client.get("products", []))

    def _client_products(self):
        """Zwraca listę książek należących do aktualnie wybranego klienta.

        Gdy żaden klient nie jest wybrany, tabela zaczyna pusta zamiast
        pokazywać całą bazę."""
        owned_ids = self._current_client_product_ids()
        if owned_ids is None:
            return []
        return [product for product in self.products if product.get("id") in owned_ids]

    def _products_for_selection(self):
        """Książki dostępne w rozwijanych listach wierszy - zawsze cała baza.

        Wybór dowolnej książki i tak przenosi raport pod jej właściciela
        (_adopt_product_owner), więc nie ma potrzeby zawężać listy do
        jednego klienta."""
        return list(self.products)

    def _product_author(self, product):
        return str(
            product.get("author") or product.get("autor") or ""
        ).strip()

    def _product_label(self, product, with_author=True):
        """Etykieta książki na liście: "Tytuł — Autor" (albo sam tytuł, gdy
        brak autora). Autor rozróżnia pozycje o tym samym tytule."""
        title = str(self._product_title(product))
        author = self._product_author(product)
        if with_author and author:
            return f"{title} — {author}"
        return title

    def _product_owner_client_id(self, product_id):
        """ID klienta, do którego przypisana jest książka; None, gdy niczyja."""
        if product_id is None:
            return None
        for client in self.clients:
            if product_id in client.get("products", []):
                return client["id"]
        return None

    def _adopt_product_owner(self, product_id):
        """Jeśli wybrana książka należy do innego klienta - przełącza na niego.

        Zwraca True, gdy klient faktycznie się zmienił - wtedy tabela została
        przebudowana od nowa i wywołujący musi dopisać książkę ponownie.
        """
        owner_id = self._product_owner_client_id(product_id)
        if owner_id is None or owner_id == self.client_box.currentData():
            return False

        index = self.client_box.findData(owner_id)
        if index < 0:
            return False

        self.client_box.setCurrentIndex(index)
        return True

    # --- Kwoty rozliczeń z bazy SQLite ---

    def _relink_report_rows(self):
        """Dopina do książek pozycje raportów, które przy przeliczaniu nie
        miały jeszcze swojej książki w bazie. Błąd nie blokuje okna - najwyżej
        takie pozycje pozostaną niewidoczne, jak dotąd."""
        try:
            relink_unmatched_rows(products=self.products)
        except ReportCalculationError:
            pass

    def _period_label(self, period):
        """Czytelna nazwa okresu: miesiąc albo kwartał.

        Przy kwartale dopisujemy faktyczny zakres dat - platformy rozliczające
        się kwartalnie podają nieregularny przedział, a nie pełny kwartał."""
        period = str(period)
        year, _, rest = period.partition("-")

        if is_quarter(period):
            try:
                label = f"{QUARTER_NAMES[int(rest[1]) - 1]} kwartał {year}"
            except (IndexError, ValueError):
                return period
            span = self._period_spans.get(period)
            return f"{label} ({span})" if span else label

        try:
            return f"{MONTH_NAMES[int(rest) - 1]} {year}"
        except (IndexError, ValueError):
            return period

    def _load_period_spans(self, periods):
        """Faktyczne zakresy dat okresów kwartalnych (do etykiet i raportu)."""
        spans = {}
        for period in periods:
            if not is_quarter(period):
                continue
            try:
                span = period_span(period)
            except SettlementAmountsError:
                continue
            if span is not None:
                spans[period] = span
        return spans

    def _build_period_box(self, keep_selection=False):
        """Wypełnia listę okresów tym, co jest w bazie rozliczeń.

        Okresy bierzemy z samych danych, więc każdy nowo przeliczony raport
        (miesięczny albo kwartalny) sam dokłada swój okres do listy."""
        previous = self.period_box.currentData() if keep_selection else None

        try:
            periods = available_periods()
        except SettlementAmountsError:
            periods = []

        self._period_spans = self._load_period_spans(periods)

        self.period_box.blockSignals(True)
        self.period_box.clear()
        self.period_box.addItem("Wszystkie okresy", ALL_PERIODS)

        for year in sorted({period[:4] for period in periods}, reverse=True):
            self.period_box.addItem(f"{year} — cały rok", year)
            for period in periods:
                if period.startswith(year):
                    self.period_box.addItem(self._period_label(period), period)

        index = self.period_box.findData(previous) if previous else -1
        if index < 0 and periods:
            # Rozliczenia robi się co miesiąc, więc domyślnie pokazujemy
            # najświeższy miesiąc obecny w bazie.
            index = self.period_box.findData(periods[0])
        if index >= 0:
            self.period_box.setCurrentIndex(index)

        self.period_box.blockSignals(False)

    def showEvent(self, event):
        """Przy każdym otwarciu okna lista okresów czyta bazę od nowa."""
        super().showEvent(event)

        period = self._current_period()
        self._build_period_box(keep_selection=True)

        if self._current_period() != period:
            self._reload_from_database()

    def _current_period(self):
        return self.period_box.currentData() or ALL_PERIODS

    def _period_description(self):
        """Opis okresu drukowany na raporcie.

        Dla „wszystkich okresów” pusty - raport obejmuje wtedy wszystko, co
        jest w bazie, więc konkretny zakres nie istnieje."""
        if not self._current_period():
            return ""
        return self.period_box.currentText()

    def _on_number_edited(self, _text=None):
        self._number_touched = True

    def _settlement_number(self):
        return self.number_input.text().strip()

    def _refresh_proposed_number(self):
        """Podpowiada pierwszy wolny numer dla aktualnego okresu.

        Nie rusza pola, jeśli użytkownik wpisał numer ręcznie."""
        if self._number_touched:
            return
        try:
            proposed = settlement_numbers.next_number(self._current_period())
        except Exception:
            return
        self.number_input.blockSignals(True)
        self.number_input.setText(proposed)
        self.number_input.blockSignals(False)

    def _resolve_platform_id(self, amount):
        """Dopasowuje kwotę z bazy do platformy z listy rozwijanej."""
        for streaming in self.streamings:
            if "id" in streaming and streaming["id"] == amount.platform_id:
                return streaming["id"]

        streaming = (
            self._find_streaming(amount.platform_key)
            or self._find_streaming(amount.platform_name)
        )
        return streaming["id"] if streaming and "id" in streaming else None

    def _load_amounts(self, product_ids):
        """Kwoty netto/brutto książek z bazy: {id książki: {id platformy: kwota}}."""
        try:
            loaded = load_amounts(product_ids, self._current_period())
        except SettlementAmountsError:
            return {}

        result = {}
        for product_id, amounts in loaded.items():
            for amount in amounts:
                platform_id = self._resolve_platform_id(amount)
                if platform_id is None:
                    continue
                result.setdefault(product_id, {})[platform_id] = amount
        return result

    def _product_amounts(self, product_id):
        return self._load_amounts([product_id]).get(product_id, {})

    def _product_cut_text(self, product_id):
        """Prowizja AO przypisana do książki ("Procent" w bazie produktów)."""
        if product_id is None:
            return ""

        for product in self.products:
            if product.get("id") != product_id:
                continue
            value = product.get("cut", product.get("procent"))
            if value is None or str(value).strip() == "":
                return ""
            try:
                return f"{float(str(value).replace(',', '.')):g}"
            except (TypeError, ValueError):
                return ""
        return ""

    def _reload_from_database(self):
        """Wypełnia tabelę pozycjami klienta, które mają kwoty w wybranym okresie.

        Tabela jest widokiem bazy dla pary (klient, okres) - po zmianie
        którejkolwiek z nich budujemy ją od nowa."""
        products = [
            product for product in self._client_products() if "id" in product
        ]
        amounts = self._load_amounts([product["id"] for product in products])

        self.table.blockSignals(True)
        try:
            self.table.setRowCount(0)
            row = 0
            for product in products:
                platform_amounts = amounts.get(product["id"], {})
                for streaming in self.streamings:
                    amount = platform_amounts.get(streaming.get("id"))
                    if amount is None:
                        continue
                    self.table.insertRow(row)
                    self._add_row(
                        row,
                        product_id=product["id"],
                        platform_id=streaming["id"],
                        net=amount.net,
                        gross=amount.gross,
                    )
                    row += 1

            # Ostatni wiersz zostaje pusty, żeby dało się dopisać pozycję ręcznie.
            self.table.insertRow(row)
            self._add_row(row)
        finally:
            self.table.blockSignals(False)

        self.schedule_preview()

    def _fill_row_amounts(self, row):
        """Podstawia kwoty z bazy dla wskazanego wiersza tabeli."""
        product_box = self.table.cellWidget(row, 0)
        platform_box = self.table.cellWidget(row, 1)

        if not product_box or product_box.currentIndex() == 0:
            return
        if not platform_box or platform_box.currentIndex() == 0:
            return

        amount = self._product_amounts(product_box.currentData()).get(
            platform_box.currentData()
        )

        self._set_cell_text(row, 2, "0" if amount is None else f"{amount.net:.2f}")
        self._set_cell_text(
            row,
            3,
            "" if amount is None or amount.gross is None else f"{amount.gross:.2f}",
        )

    def _on_period_changed(self):
        """Po zmianie okresu tabela pokazuje kwoty z nowego miesiąca."""
        self._reload_from_database()
        self._refresh_proposed_number()

    def _on_client_changed(self):
        """Po zmianie klienta wczytujemy jego pozycje z bazy rozliczeń."""
        self._build_product_search_completer()
        # Przebudowuje całą tabelę, więc puste listy produktów też dostają
        # aktualny zestaw książek.
        self._reload_from_database()
        self._refresh_proposed_number()

    def _quick_add_catalog(self):
        """(etykieta, id) dla KAŻDEJ książki w bazie.

        Szybkie dodawanie podpowiada całą bazę, nie tylko książki wybranego
        klienta - inaczej nie dało się dopisać pozycji innego klienta bez
        ręcznego grzebania w ustawieniach. Zduplikowane tytuły rozróżniamy
        dopiskiem autora."""
        title_counts = {}
        for product in self.products:
            if "id" not in product:
                continue
            title = str(self._product_title(product)).strip()
            if title:
                key = title.casefold()
                title_counts[key] = title_counts.get(key, 0) + 1

        catalog = []
        for product in self.products:
            if "id" not in product:
                continue
            title = str(self._product_title(product)).strip()
            if not title:
                continue
            author = self._product_author(product)
            if author and title_counts.get(title.casefold(), 0) > 1:
                label = f"{title} — {author}"
            else:
                label = title
            catalog.append((label, product["id"]))

        catalog.sort(key=lambda item: item[0].casefold())
        return catalog

    def _build_product_search_completer(self):
        """Odświeża listę podpowiedzi szybkiego dodawania (cała baza książek)."""
        catalog = self._quick_add_catalog()
        self._quick_add_choices = catalog

        # Rozpoznawane formy wpisu: wyświetlana etykieta, "Tytuł — Autor"
        # (nawet gdy w podpowiedzi jest sam tytuł) oraz sam tytuł, o ile
        # jest jednoznaczny.
        self._quick_add_by_label = {
            label.casefold(): product_id for label, product_id in catalog
        }
        for product in self.products:
            if "id" not in product:
                continue
            full = self._product_label(product, with_author=True).strip().casefold()
            if full:
                self._quick_add_by_label.setdefault(full, product["id"])

        title_counts = {}
        for product in self.products:
            if "id" in product:
                key = str(self._product_title(product)).strip().casefold()
                if key:
                    title_counts[key] = title_counts.get(key, 0) + 1
        self._quick_add_by_title = {}
        for product in self.products:
            if "id" not in product:
                continue
            key = str(self._product_title(product)).strip().casefold()
            if key and title_counts.get(key) == 1:
                self._quick_add_by_title.setdefault(key, product["id"])

        model = QtCore.QStringListModel(
            [label for label, _ in catalog], self._product_completer
        )
        self._product_completer.setModel(model)

    def _on_search_completion_activated(self, title):
        """Po wybraniu podpowiedzi z listy dodajemy pozycję do raportu."""
        self.search_input.setText(title)
        self.add_product_from_search()

    def _find_product_id_by_title(self, text):
        """Dopasowuje wpisany tekst do książki z bazy - najpierw po pełnej
        etykiecie ("Tytuł — Autor"), potem po samym tytule, a na końcu po
        jednoznacznym fragmencie (jeśli pasuje dokładnie jedna pozycja - żeby
        nie podstawiać przypadkowej książki)."""
        key = str(text).strip().casefold()
        if not key:
            return None

        if key in self._quick_add_by_label:
            return self._quick_add_by_label[key]
        if key in self._quick_add_by_title:
            return self._quick_add_by_title[key]

        matches = {
            product_id
            for label, product_id in self._quick_add_choices
            if key in label.casefold()
        }
        if len(matches) == 1:
            return next(iter(matches))
        return None

    def _commit_quick_add_from_field(self):
        """Obsługa Enter w polu: jeśli lista podpowiedzi jest otwarta, bierze
        podświetloną pozycję, po czym dodaje ją do raportu."""
        popup = self._product_completer.popup()
        if popup is not None and popup.isVisible():
            suggestion = self._product_completer.currentCompletion().strip()
            if suggestion:
                self.search_input.setText(suggestion)
            popup.hide()

        self.add_product_from_search()

    def add_product_from_search(self):
        """Dodaje do raportu pozycję z pola szybkiego dodawania.

        Działa na Enter i po wybraniu podpowiedzi. Gdy wpisany tekst nie
        pasuje do żadnej książki, pole tylko mruga na czerwono - bez modalnego
        okna, które trzeba zamykać."""
        typed = self.search_input.text().strip()
        product_id = self._find_product_id_by_title(typed)

        if product_id is None:
            if typed:
                self._flash_search_error()
            return

        # Rozwijane listy w wierszach mają wszystkie książki, więc wystarczy
        # ją wskazać - resztę (przełączenie klienta) robi _handle_combo_changed.
        self._add_product_by_id(product_id)

        self.search_input.clear()
        self.search_input.setFocus()

    def _flash_search_error(self):
        """Krótki czerwony kontur pola - sygnał "nie ma takiej pozycji"."""
        self.search_input.setStyleSheet("QLineEdit { border: 1px solid #d64545; }")
        QtCore.QTimer.singleShot(
            1100, lambda: self.search_input.setStyleSheet("")
        )

    def _add_product_by_id(self, product_id):
        """Ustawia książkę w pustym wierszu na końcu tabeli, uruchamiając istniejącą logikę dodawania platform."""
        row = self.table.rowCount() - 1
        product_box = self.table.cellWidget(row, 0)
        if not product_box:
            return

        index = product_box.findData(product_id)
        if index < 0:
            return

        product_box.setCurrentIndex(index)

    def _make_combo_searchable(self, combo: QtWidgets.QComboBox):
        """Pozwala wyszukiwać pozycję na liście, wpisując dowolny jej fragment."""
        combo.setEditable(True)
        combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)

        completer = combo.completer()
        completer.setCompletionMode(
            QtWidgets.QCompleter.CompletionMode.PopupCompletion
        )
        completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

        # Jeśli po zakończeniu edycji wpisany tekst nie odpowiada żadnej
        # wybranej pozycji, przywracamy tekst aktualnie ustawionego elementu,
        # żeby w polu nie zostawał "wyszukiwany" fragment.
        combo.lineEdit().editingFinished.connect(
            lambda combo=combo: combo.lineEdit().setText(
                combo.itemText(combo.currentIndex())
            )
        )
        self._widen_combo_popup(combo)

    def _style_primary_button(self, button: QtWidgets.QPushButton):
        palette = ThemeManager.get_accent_palette()
        accent, accent_hover, accent_pressed = palette.base, palette.hover, palette.pressed

        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {accent};
                color: white;
                font-weight: bold;
                padding: 8px;
                border-radius: 4px;
                border: none;
            }}
            QPushButton:hover {{
                background-color: {accent_hover};
            }}
            QPushButton:pressed {{
                background-color: {accent_pressed};
            }}
        """)

    def _widen_combo_popup(self, combo: QtWidgets.QComboBox):

        MIN_POPUP_WIDTH = 220
        MAX_POPUP_WIDTH = 480
        EXTRA_PADDING = 40

        metrics = QtGui.QFontMetrics(combo.font())
        longest_text_width = max(
            (metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count())),
            default=0,
        )

        popup_width = max(MIN_POPUP_WIDTH, min(longest_text_width + EXTRA_PADDING, MAX_POPUP_WIDTH))
        combo.view().setMinimumWidth(popup_width)

    def _add_row(self, row, product_id=None, platform_id=None, net=None, gross=None):
        product_box = QtWidgets.QComboBox()
        product_box.addItem("")

        products_to_show = self._products_for_selection()
        if product_id is not None and not any(
                product.get("id") == product_id for product in products_to_show):
            # Wiersz odtwarzany z importu/istniejących danych może wskazywać na
            # książkę spoza listy klienta - trzeba ją mimo to udostępnić w polu,
            # żeby nie zgubić już przypisanej wartości.
            existing = next(
                (product for product in self.products if product.get("id") == product_id),
                None
            )
            if existing is not None:
                products_to_show = products_to_show + [existing]

        for product in products_to_show:
            if "id" not in product:
                continue
            product_box.addItem(
                self._product_label(product),
                product["id"]
            )

        self._make_combo_searchable(product_box)

        platform_box = QtWidgets.QComboBox()
        platform_box.addItem("")

        for streaming in self.streamings:
            if "id" not in streaming:
                continue
            platform_box.addItem(
                str(self._streaming_name(streaming)),
                streaming["id"]
            )

        self._make_combo_searchable(platform_box)

        if product_id is not None:
            product_index = product_box.findData(product_id)
            if product_index >= 0:
                product_box.setCurrentIndex(product_index)

        if platform_id is not None:
            platform_index = platform_box.findData(platform_id)
            if platform_index >= 0:
                platform_box.setCurrentIndex(platform_index)

        self.table.setCellWidget(row, 0, product_box)
        self.table.setCellWidget(row, 1, platform_box)

        self._set_cell_text(row, 2, "0" if net is None else f"{net:.2f}")
        # Brutto zostaje puste, dopoki baza nie poda tej kwoty.
        self._set_cell_text(row, 3, "" if gross is None else f"{gross:.2f}")
        self._set_cell_text(row, 4, self._product_cut_text(product_id))

        # Przypisujemy zdarzenia do nowej, wspólnej funkcji weryfikującej
        product_box.currentIndexChanged.connect(self._handle_combo_changed)
        platform_box.currentIndexChanged.connect(self._handle_combo_changed)

    def _set_cell_text(self, row, column, text):
        item = self.table.item(row, column)
        if item is None:
            self.table.setItem(row, column, QtWidgets.QTableWidgetItem(text))
        else:
            item.setText(text)

    def _find_streaming(self, platform_key):
        """Szuka platformy w bazie po kluczu integracji, potem po nazwie."""
        expected_key = str(platform_key or "").strip().casefold()
        for streaming in self.streamings:
            integration = str(streaming.get("integration") or "").strip().casefold()
            if integration and integration == expected_key:
                return streaming
        for streaming in self.streamings:
            name = str(streaming.get("name") or "").strip()
            if name.casefold() == expected_key:
                return streaming
            if safe_platform_filename(name).casefold() == expected_key:
                return streaming
        return None

    def _find_row(self, product_id, platform_id, skip_row=None):
        """Szuka wiersza z daną parą książka + platforma."""
        for row in range(self.table.rowCount()):
            if row == skip_row:
                continue
            product_box = self.table.cellWidget(row, 0)
            platform_box = self.table.cellWidget(row, 1)
            if not product_box or not platform_box:
                continue
            if (product_box.currentData() == product_id
                    and platform_box.currentData() == platform_id):
                return row
        return -1

    def _get_row_of_widget(self, widget):
        """Wyszukuje, w którym wierszu aktualnie znajduje się dany widget."""
        for i in range(self.table.rowCount()):
            if self.table.cellWidget(i, 0) == widget or self.table.cellWidget(i, 1) == widget:
                return i
        return -1

    def remove_selected_row(self):
        """Usuwa wiersz zaznaczony w tabeli."""
        row = self.table.currentRow()
        if row == -1:
            return

        self.table.removeRow(row)
        self._ensure_trailing_empty_row()
        self.schedule_preview()

    def _ensure_trailing_empty_row(self):
        """Dba o to, żeby na końcu tabeli zawsze był pusty wiersz do dodawania pozycji."""
        last_row = self.table.rowCount() - 1

        if last_row < 0:
            self.add_empty_row(0)
            return

        product_box = self.table.cellWidget(last_row, 0)
        platform_box = self.table.cellWidget(last_row, 1)

        product_filled = bool(product_box) and product_box.currentIndex() != 0
        platform_filled = bool(platform_box) and platform_box.currentIndex() != 0

        if product_filled or platform_filled:
            self.add_empty_row(self.table.rowCount())

    def _handle_combo_changed(self):
        """Dynamicznie obsługuje zmianę w rozwijanej liście dla dowolnego wiersza."""
        sender = self.sender()
        if not sender:
            return

        row = self._get_row_of_widget(sender)
        if row == -1:
            return

        product_box = self.table.cellWidget(row, 0)
        platform_box = self.table.cellWidget(row, 1)

        is_last_row = (row == self.table.rowCount() - 1)

        # Jeśli zmieniono książkę (produkt) w ostatnim wierszu
        if sender == product_box and is_last_row:
            product_id = product_box.currentData()

            # W trybie "wszystkie książki" wybrana pozycja może należeć do
            # innego klienta - raport ma trafić pod właściciela książki.
            if product_box.currentIndex() > 0 and self._adopt_product_owner(product_id):
                # Zmiana klienta przebudowała tabelę, więc ten wiersz już nie
                # istnieje - książkę dopisujemy do nowego, pustego wiersza.
                self._add_product_by_id(product_id)
                self.schedule_preview()
                return

            self.on_product_selected(row)
            self.schedule_preview()
            return

        # Jeśli to nie jest ostatni wiersz i oba boxy ustawiono na pustą pozycję, to usuń wiersz
        if not is_last_row:
            if product_box and product_box.currentIndex() == 0:
                if platform_box and platform_box.currentIndex() == 0:
                    self.table.removeRow(row)
                    self.schedule_preview()
                    return

            # Po zmianie platformy w gotowym wierszu kwoty ma podać baza.
            if sender == platform_box:
                self._fill_row_amounts(row)

            # Zmiana książki zmienia też przypisaną do niej prowizję.
            if sender == product_box:
                self._fill_row_amounts(row)
                self._set_cell_text(
                    row, 4, self._product_cut_text(product_box.currentData())
                )

        self.schedule_preview()

    def add_empty_row(self, row):
        if row >= self.table.rowCount():
            self.table.insertRow(row)
        self._add_row(row)

    def on_product_selected(self, row):
        """Tworzy wiersze platform po wybraniu produktu i wypełnia je z bazy."""
        if row != self.table.rowCount() - 1:
            return

        product_box = self.table.cellWidget(row, 0)
        if not product_box or product_box.currentIndex() <= 0:
            return

        product_id = product_box.currentData()
        amounts = self._product_amounts(product_id)

        all_platforms = [
            streaming["id"]
            for streaming in self.streamings
            if "id" in streaming
        ]
        # Domyślnie pokazujemy tylko platformy, które mają kwoty w bazie.
        # Gdy baza nie zna jeszcze tej książki, zostawiamy wszystkie
        # platformy do ręcznego uzupełnienia.
        platforms = [
            platform_id
            for platform_id in all_platforms
            if platform_id in amounts
        ] or all_platforms

        if not platforms:
            return

        # Książka może już być w rozliczeniu - wtedy tylko odświeżamy jej kwoty,
        # zamiast dopisywać drugi raz ten sam wiersz.
        existing = {
            platform_id: self._find_row(product_id, platform_id, skip_row=row)
            for platform_id in platforms
        }
        for platform_id, existing_row in existing.items():
            if existing_row != -1:
                self._fill_row_amounts(existing_row)

        platforms = [
            platform_id
            for platform_id in platforms
            if existing[platform_id] == -1
        ]

        if not platforms:
            product_box.blockSignals(True)
            product_box.setCurrentIndex(0)
            product_box.blockSignals(False)
            self.table.selectRow(next(iter(existing.values())))
            self.schedule_preview()
            return

        self.table.removeRow(row)

        for offset, platform_id in enumerate(platforms):
            amount = amounts.get(platform_id)
            self.table.insertRow(row + offset)
            self._add_row(
                row + offset,
                product_id=product_id,
                platform_id=platform_id,
                net=amount.net if amount else None,
                gross=amount.gross if amount else None,
            )

        empty_row = row + len(platforms)
        self.table.insertRow(empty_row)
        self.add_empty_row(empty_row)
        self.schedule_preview()

    def _row_cut(self, row, strict=True):
        """Czyta prowizję wpisaną w wierszu. Pusta komórka to brak nadpisania."""
        item = self.table.item(row, 4)
        text = item.text().replace(",", ".").strip() if item else ""

        if not text:
            return None

        try:
            cut = float(text)
        except ValueError:
            if strict:
                raise ValueError("Niepoprawna prowizja AO (%).")
            return None

        if not 0 <= cut <= 100:
            if strict:
                raise ValueError("Prowizja AO musi mieścić się w zakresie 0-100%.")
            return None

        return cut

    def collect_items(self, strict=True):
        items = []

        for row in range(self.table.rowCount()):
            product_box = self.table.cellWidget(row, 0)
            platform_box = self.table.cellWidget(row, 1)

            if not product_box or product_box.currentIndex() == 0:
                continue

            if not platform_box or platform_box.currentIndex() == 0:
                # W trybie strict wiersz z wybraną książką, ale bez platformy
                # był po cichu pomijany - pozycja znikała z gotowego raportu.
                if strict:
                    raise ValueError("Wybierz platformę dla każdej pozycji raportu.")
                continue

            table_item = self.table.item(row, 2)
            revenue_text = (
                table_item.text().replace(",", ".").strip()
                if table_item else "0"
            )

            try:
                revenue = float(revenue_text) if revenue_text else 0.0
            except ValueError:
                if strict:
                    raise ValueError("Niepoprawna kwota wypłaty.")
                else:
                    revenue = 0.0

            product = database_controller.item_get(product_box.currentData(), "products")
            platform = database_controller.item_get(platform_box.currentData(), "streamings")

            gross_item = self.table.item(row, 3)
            gross_text = (
                gross_item.text().replace(",", ".").strip()
                if gross_item else ""
            )

            try:
                revenue_gross = float(gross_text) if gross_text else None
            except ValueError:
                if strict:
                    raise ValueError("Niepoprawna kwota brutto.")
                revenue_gross = None

            items.append({
                "product": product,
                "platform": platform,
                "revenue_gross": revenue_gross,
                "revenue": revenue,
                # Pusta komórka oznacza "weź prowizję z książki".
                "cut": self._row_cut(row, strict)
            })

        return items

    def _current_client(self):
        if not self.clients:
            return None
        return database_controller.item_get(self.client_box.currentData(), "clients")

    def schedule_preview(self):
        self._refresh_timer.start()

    def _render_preview(self):
        client = self._current_client()
        try:
            items = self.collect_items(strict=False)
        except Exception:
            items = []

        try:
            data = report_generator.render_settlement_pdf_bytes(
                client, items, number=self._settlement_number(),
                period=self._period_description()
            )
        except Exception:
            return

        self._pdf_buffer = QtCore.QBuffer()
        self._pdf_buffer.setData(data)
        self._pdf_buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
        self.pdf_document.load(self._pdf_buffer)

    def _validated_number(self):
        """Zwraca kanoniczny numer rozliczenia albo None (i pokazuje komunikat).

        Pusty numer jest dozwolony - wtedy raport powstaje bez numeru.
        Numer już użyty wymaga potwierdzenia nadpisania wpisu."""
        raw = self._settlement_number()
        if not raw:
            return ""

        try:
            number = settlement_numbers.normalize_number(raw)
        except settlement_numbers.SettlementNumberError as error:
            QtWidgets.QMessageBox.warning(self, "Numer rozliczenia", str(error))
            return None

        existing = settlement_numbers.get(number)
        if existing is not None:
            details = existing.client_name or "—"
            answer = QtWidgets.QMessageBox.question(
                self,
                "Numer już użyty",
                f"Numer {number} jest już przypisany do rozliczenia "
                f"({details}, {existing.generated_at}).\n\n"
                "Nadpisać ten wpis?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return None

        return number

    def _record_settlement_number(self, number, client, items, file_path):
        """Zapisuje wystawiony numer do rejestru rozliczeń.

        Błąd zapisu nie przerywa procesu - PDF jest już wygenerowany."""
        if not number:
            return
        try:
            _, rows = report_generator.compute_settlement_rows(client, items)
            total_client = round(sum(row["for_client"] for row in rows), 2)
        except Exception:
            total_client = None
        try:
            settlement_numbers.record_settlement(
                number,
                period=self._current_period(),
                client_id=client.get("id") if client else None,
                client_name=str(client.get("name") or "") if client else "",
                total_client=total_client,
                pdf_filename=os.path.basename(file_path or ""),
            )
        except Exception as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Numer rozliczenia",
                f"Raport zapisano, ale nie udało się zapisać numeru w rejestrze:\n{error}",
            )

    def generate_report(self):
        if not self.clients:
            QtWidgets.QMessageBox.warning(self, "Uwaga", "Brak klientów w bazie.")
            return

        client = database_controller.item_get(self.client_box.currentData(), "clients")
        if client is None:
            QtWidgets.QMessageBox.warning(self, "Uwaga", "Wybierz klienta.")
            return

        try:
            items = self.collect_items()
        except ValueError as error:
            QtWidgets.QMessageBox.warning(self, "Uwaga", str(error))
            return

        if not items:
            QtWidgets.QMessageBox.warning(self, "Uwaga", "Dodaj przynajmniej jeden produkt.")
            return

        number = self._validated_number()
        if number is None:
            return

        try:
            client_name_safe = str(client["name"]).replace(" ", "_")
            if number:
                number_tag = settlement_numbers.number_to_filename_part(number)
                default_filename = (
                    "rozliczenie_" + number_tag + "_" + client_name_safe + ".pdf"
                )
            else:
                default_filename = "raport_" + client_name_safe + "_" + datetime.now().strftime(
                    "%Y-%m-%d_%H-%M-%S") + ".pdf"

            os.makedirs(self.folder_output, exist_ok=True)

            save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Wybierz miejsce zapisu raportu",
                os.path.join(self.folder_output, default_filename),
                "Pliki PDF (*.pdf)"
            )

            if not save_path:
                return

            if not save_path.lower().endswith(".pdf"):
                save_path += ".pdf"

            file_path = report_generator.generate_settlement_pdf(
                client, items, save_path=save_path, number=number,
                period=self._period_description()
            )
            self.generated_file_path = file_path
            self.is_existing_file = False
        except ValueError:
            QtWidgets.QMessageBox.warning(self, "Uwaga", "Prowizja klienta i platformy musi być liczbą.")
            return

        self._record_settlement_number(number, client, items, file_path)

        self.selected_client_email = (client.get("email") or "").strip() or None

        if not self.email_mode:
            QtWidgets.QMessageBox.information(self, "Gotowe", f"Zapisano raport:\n{file_path}")

        self.accept()

    def attach_existing_report(self):
        os.makedirs(self.folder_output, exist_ok=True)

        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Wybierz raport do wysłania",
            self.folder_output,
            "Pliki PDF (*.pdf)"
        )

        if not file_path:
            return

        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.critical(self, "Błąd", "Wybrany plik nie istnieje.")
            return

        self.generated_file_path = file_path
        self.is_existing_file = True

        client = self._current_client()
        self.selected_client_email = (client.get("email") or "").strip() if client else None

        self.accept()

    def setup_layout(self):
        left = QtWidgets.QVBoxLayout()
        left.addWidget(QtWidgets.QLabel("Klient:"))
        left.addWidget(self.client_box)
        left.addWidget(QtWidgets.QLabel("Okres rozliczenia:"))
        left.addWidget(self.period_box)
        left.addWidget(QtWidgets.QLabel("Numer rozliczenia:"))
        left.addWidget(self.number_input)
        left.addWidget(QtWidgets.QLabel("Szybkie dodawanie pozycji (szukaj po tytule):"))
        left.addWidget(self.search_input)

        left.addWidget(QtWidgets.QLabel(
            "Kwoty i prowizja pochodzą z bazy — każdą możesz nadpisać ręcznie:"
        ))
        left.addWidget(self.table)
        left.addWidget(self.remove_row_button)
        if self.email_mode:
            left.addWidget(self.attach_existing_button)
        left.addWidget(self.generate_button)

        left_widget = QtWidgets.QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(600)

        right = QtWidgets.QVBoxLayout()
        right.addWidget(QtWidgets.QLabel("Podgląd raportu:"))
        right.addWidget(self.pdf_view)
        right_widget = QtWidgets.QWidget()
        right_widget.setLayout(right)

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([600, 500])

        main = QtWidgets.QVBoxLayout(self)
        main.addWidget(splitter)
