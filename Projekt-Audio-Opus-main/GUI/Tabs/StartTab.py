from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from core import database_controller, report_generator
from GUI.style.theme_manager import ThemeManager
from platforms.report_viewer import list_book_reports, list_monthly_book_reports


WEEKDAYS = (
    "poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela",
)
MONTHS = (
    "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca",
    "sierpnia", "września", "października", "listopada", "grudnia",
)


def format_money(value):
    """Kwota w polskim zapisie: 1 253,37 zł."""
    text = f"{float(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"{text} zł"


def format_date(moment):
    return f"{WEEKDAYS[moment.weekday()]}, {moment.day} {MONTHS[moment.month - 1]} {moment.year}"


def greeting(moment):
    if moment.hour < 5 or moment.hour >= 18:
        return "Dobry wieczór"
    return "Dzień dobry"


class YearNetChart(QtWidgets.QWidget):
    """Poziome słupki z przychodem netto dla kolejnych lat."""

    ANIMATION_DURATION_MS = 450
    ROW_HEIGHT = 34

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values = {}
        self._target_values = {}
        self._progress = 1.0
        self._animation = QtCore.QVariantAnimation(self)
        self._animation.setDuration(self.ANIMATION_DURATION_MS)
        self._animation.setStartValue(0.0)
        self._animation.setEndValue(1.0)
        self._animation.setEasingCurve(QtCore.QEasingCurve.Type.OutCubic)
        self._animation.valueChanged.connect(self._on_progress)
        self._animation.finished.connect(self._on_finished)
        self.setMinimumHeight(120)
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

    def set_values(self, values):
        target_values = {
            str(key): float(value)
            for key, value in values.items()
            if float(value) > 0
        }
        if target_values == self._target_values:
            return

        self._animation.stop()
        self._target_values = target_values
        self._values = dict(target_values)
        self._progress = 0.0
        self._animation.start()
        self.update()

    @property
    def is_animating(self):
        return self._animation.state() == QtCore.QAbstractAnimation.State.Running

    def _on_progress(self, value):
        self._progress = float(value)
        self.update()

    def _on_finished(self):
        self._progress = 1.0
        self.update()

    def paintEvent(self, event):
        del event
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        palette = self.palette()
        text_color = palette.color(QtGui.QPalette.ColorRole.Text)
        muted = QtGui.QColor(text_color)
        muted.setAlphaF(0.55)

        if not self._values:
            painter.setPen(muted)
            painter.drawText(
                self.rect(),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                "Brak zaimportowanych raportów rocznych",
            )
            return

        accent = QtGui.QColor(ThemeManager.get_current_accent())
        track = QtGui.QColor(text_color)
        track.setAlphaF(0.07)
        older = QtGui.QColor(text_color)
        older.setAlphaF(0.28)

        metrics = painter.fontMetrics()
        rows = sorted(self._values.items(), reverse=True)
        latest_year = rows[0][0]
        maximum = max(self._values.values())
        label_width = max(metrics.horizontalAdvance(year) for year, _ in rows) + 14
        value_width = max(metrics.horizontalAdvance(format_money(v)) for _, v in rows) + 14
        bar_left = label_width
        bar_width = max(10, self.width() - label_width - value_width)
        bar_height = 10

        for index, (year, amount) in enumerate(rows):
            top = 6 + index * self.ROW_HEIGHT
            if top + self.ROW_HEIGHT > self.height() + 6:
                break
            center_y = top + self.ROW_HEIGHT / 2

            painter.setPen(text_color if year == latest_year else muted)
            painter.drawText(
                QtCore.QRectF(0, top, label_width, self.ROW_HEIGHT),
                QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignLeft,
                year,
            )

            bar_rect = QtCore.QRectF(bar_left, center_y - bar_height / 2, bar_width, bar_height)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(track)
            painter.drawRoundedRect(bar_rect, 3, 3)

            filled = bar_width * (amount / maximum) * self._progress
            if filled > 0.5:
                painter.setBrush(accent if year == latest_year else older)
                painter.drawRoundedRect(
                    QtCore.QRectF(bar_rect.left(), bar_rect.top(), max(filled, bar_height), bar_height),
                    3,
                    3,
                )

            painter.setPen(text_color if year == latest_year else muted)
            painter.drawText(
                QtCore.QRectF(bar_left + bar_width, top, value_width, self.ROW_HEIGHT),
                QtCore.Qt.AlignmentFlag.AlignVCenter | QtCore.Qt.AlignmentFlag.AlignRight,
                format_money(amount),
            )

    def sizeHint(self):
        return QtCore.QSize(360, max(120, len(self._values) * self.ROW_HEIGHT + 12))


class StartTab(QtWidgets.QWidget):
    """Ekran podsumowania i szybkiego dostępu do najczęstszych akcji."""

    refresh_requested = QtCore.Signal()

    def __init__(self, clients_tab, products_tab, streaming_tab, report_tab):
        super().__init__()
        self.setObjectName("startTab")

        self.clients_tab = clients_tab
        self.products_tab = products_tab
        self.streaming_tab = streaming_tab
        self.report_tab = report_tab
        self._count_labels = {}
        self._hint_labels = {}
        self._warnings = None
        self._recent_files = None
        self._refresh_timer = QtCore.QTimer(self)
        self._refresh_timer.setInterval(5000)
        self._refresh_timer.timeout.connect(self.refresh)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(28, 22, 28, 22)
        layout.setSpacing(18)

        layout.addLayout(self._build_header())

        summary_layout = QtWidgets.QHBoxLayout()
        summary_layout.setSpacing(12)
        for key, caption in (
            ("clients", "Klienci"),
            ("products", "Produkty"),
            ("reports", "Raporty miesięczne"),
            ("latest_net", "Przychód netto"),
            ("attention", "Do uzupełnienia"),
        ):
            summary_layout.addWidget(self._create_summary_card(key, caption), 1)
        layout.addLayout(summary_layout)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.setSpacing(12)

        chart_panel, chart_layout, self._chart_hint = self._create_panel("Przychód netto wg lat")
        self.platform_chart = YearNetChart()
        chart_layout.addWidget(self.platform_chart)
        content_layout.addWidget(chart_panel, 3)

        side_layout = QtWidgets.QVBoxLayout()
        side_layout.setSpacing(12)

        warnings_panel, warnings_layout, _ = self._create_panel("Wymaga uwagi")
        self._warnings_container = QtWidgets.QWidget()
        self._warnings_container.setObjectName("dashboardList")
        self._warnings_layout = QtWidgets.QGridLayout(self._warnings_container)
        self._warnings_layout.setContentsMargins(0, 0, 0, 0)
        self._warnings_layout.setHorizontalSpacing(12)
        self._warnings_layout.setVerticalSpacing(8)
        warnings_layout.addWidget(self._warnings_container)
        warnings_layout.addStretch()
        side_layout.addWidget(warnings_panel, 1)

        actions_panel, actions_layout, _ = self._create_panel("Szybkie akcje")
        actions_grid = QtWidgets.QGridLayout()
        actions_grid.setSpacing(8)
        actions = (
            ("Importuj raport", self.open_import_report, True),
            ("Utwórz rozliczenie", self._callback(self.report_tab, "open_settlement"), False),
            ("Dodaj klienta", self._callback(self.clients_tab, "add_client"), False),
            ("Dodaj produkt", self._callback(self.products_tab, "add_product"), False),
        )
        self._action_buttons = {}
        for index, (text, callback, primary) in enumerate(actions):
            button = QtWidgets.QPushButton(text)
            button.setObjectName("startAction")
            button.setProperty("primary", primary)
            button.setMinimumHeight(34)
            button.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(callback)
            actions_grid.addWidget(button, index // 2, index % 2)
            self._action_buttons[text] = button
        actions_layout.addLayout(actions_grid)
        side_layout.addWidget(actions_panel)

        content_layout.addLayout(side_layout, 2)
        layout.addLayout(content_layout)

        activity_panel, activity_layout, _ = self._create_panel("Rozliczenia i ostatnie pliki")
        self._settlement_info_label = QtWidgets.QLabel()
        self._settlement_info_label.setWordWrap(True)
        activity_layout.addWidget(self._settlement_info_label)

        self._files_container = QtWidgets.QWidget()
        self._files_container.setObjectName("dashboardList")
        self._files_layout = QtWidgets.QGridLayout(self._files_container)
        self._files_layout.setContentsMargins(0, 4, 0, 0)
        self._files_layout.setHorizontalSpacing(16)
        self._files_layout.setVerticalSpacing(6)
        activity_layout.addWidget(self._files_container)
        layout.addWidget(activity_panel)
        layout.addStretch()

        self.refresh()

    # --- budowanie widoku -------------------------------------------------

    def _build_header(self):
        header = QtWidgets.QHBoxLayout()
        header.setSpacing(12)

        title_block = QtWidgets.QVBoxLayout()
        title_block.setSpacing(2)
        now = datetime.now()
        self._title_label = QtWidgets.QLabel(greeting(now))
        self._title_label.setObjectName("dashboardTitle")
        title_block.addWidget(self._title_label)
        self._date_label = QtWidgets.QLabel(format_date(now))
        self._date_label.setObjectName("dashboardDate")
        title_block.addWidget(self._date_label)
        header.addLayout(title_block)
        header.addStretch()

        self._dashboard_status = QtWidgets.QLabel()
        self._dashboard_status.setObjectName("dashboardStatus")
        header.addWidget(self._dashboard_status, alignment=QtCore.Qt.AlignmentFlag.AlignBottom)
        return header

    @staticmethod
    def _create_panel(title):
        panel = QtWidgets.QFrame()
        panel.setObjectName("dashboardPanel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(18, 14, 18, 16)
        panel_layout.setSpacing(12)

        title_row = QtWidgets.QHBoxLayout()
        title_label = QtWidgets.QLabel(title)
        title_label.setObjectName("panelTitle")
        title_row.addWidget(title_label)
        title_row.addStretch()
        hint_label = QtWidgets.QLabel()
        hint_label.setObjectName("panelHint")
        title_row.addWidget(hint_label)
        panel_layout.addLayout(title_row)
        return panel, panel_layout, hint_label

    def _create_summary_card(self, key, caption):
        card = QtWidgets.QFrame()
        card.setObjectName("summaryCard")
        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(16, 12, 16, 12)
        card_layout.setSpacing(2)

        caption_label = QtWidgets.QLabel(caption)
        caption_label.setObjectName("summaryCaption")
        card_layout.addWidget(caption_label)

        value_label = QtWidgets.QLabel("0")
        value_label.setObjectName("summaryValue")
        card_layout.addWidget(value_label)

        hint_label = QtWidgets.QLabel()
        hint_label.setObjectName("summaryHint")
        card_layout.addWidget(hint_label)

        self._count_labels[key] = value_label
        self._hint_labels[key] = hint_label
        return card

    @staticmethod
    def _callback(widget, method_name):
        callback = getattr(widget, method_name, None)
        return callback if callable(callback) else lambda: None

    @staticmethod
    def _load_records(name):
        try:
            records = database_controller.load_database(name)
        except Exception:
            return []
        return records if isinstance(records, list) else []

    # --- odświeżanie danych -----------------------------------------------

    def refresh(self):
        now = datetime.now()
        self._title_label.setText(greeting(now))
        self._date_label.setText(format_date(now))

        clients = self._load_records("clients")
        products = self._load_records("products")
        monthly_reports = self._load_monthly_reports()
        yearly_reports = self._load_yearly_reports()

        missing_email = sum(not str(client.get("email") or "").strip() for client in clients)
        missing_isbn = sum(not str(product.get("isbn") or "").strip() for product in products)
        missing_platform = sum(not self._product_platforms(product) for product in products)

        warnings = [
            (caption, count)
            for caption, count in (
                ("Klienci bez adresu e-mail", missing_email),
                ("Produkty bez numeru ISBN", missing_isbn),
                ("Produkty bez przypisanej platformy", missing_platform),
            )
            if count
        ]

        self._set_value("clients", str(len(clients)), "w bazie")
        self._set_value("products", str(len(products)), "w katalogu")
        self._set_value("reports", str(len(monthly_reports)), "w archiwum")
        latest_year = self._latest_year(monthly_reports)
        self._set_value(
            "latest_net",
            format_money(self._latest_net_value(monthly_reports)),
            f"rok {latest_year}" if latest_year else "brak raportów",
        )
        self._set_value(
            "attention",
            str(len(warnings)),
            "wszystko w porządku" if not warnings else "sprawdź listę obok",
        )
        self._count_labels["attention"].setProperty("alert", bool(warnings))
        self._repolish(self._count_labels["attention"])

        year_totals = self._year_net_totals(yearly_reports)
        self.platform_chart.set_values(year_totals)
        self._chart_hint.setText(
            f"łącznie {format_money(sum(year_totals.values()))}" if year_totals else ""
        )

        self._show_warnings(warnings)
        self._settlement_info_label.setText(self._settlement_summary_text(monthly_reports))
        self._show_recent_files(self._recent_report_files())
        self._dashboard_status.setText(f"Zaktualizowano {now:%H:%M}")
        self.refresh_requested.emit()

    def _set_value(self, key, value, hint):
        self._count_labels[key].setText(value)
        self._hint_labels[key].setText(hint)

    @staticmethod
    def _repolish(widget):
        widget.style().unpolish(widget)
        widget.style().polish(widget)

    @staticmethod
    def _clear_grid(grid):
        while grid.count():
            item = grid.takeAt(0)
            if item.widget() is not None:
                item.widget().deleteLater()

    def _show_warnings(self, warnings):
        if warnings == self._warnings:
            return
        self._warnings = warnings
        self._clear_grid(self._warnings_layout)

        if not warnings:
            label = QtWidgets.QLabel("Dane są kompletne.")
            label.setObjectName("mutedText")
            self._warnings_layout.addWidget(label, 0, 0)
            return

        for row, (caption, count) in enumerate(warnings):
            caption_label = QtWidgets.QLabel(caption)
            caption_label.setWordWrap(True)
            count_label = QtWidgets.QLabel(str(count))
            count_label.setObjectName("warningCount")
            count_label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._warnings_layout.addWidget(caption_label, row, 0)
            self._warnings_layout.addWidget(count_label, row, 1)
        self._warnings_layout.setColumnStretch(0, 1)

    def _show_recent_files(self, files):
        if files == self._recent_files:
            return
        self._recent_files = files
        self._clear_grid(self._files_layout)

        if not files:
            label = QtWidgets.QLabel("Brak wygenerowanych raportów.")
            label.setObjectName("mutedText")
            self._files_layout.addWidget(label, 0, 0)
            return

        for row, (name, modified) in enumerate(files):
            name_label = QtWidgets.QLabel(name)
            date_label = QtWidgets.QLabel(f"{modified:%d.%m.%Y, %H:%M}")
            date_label.setObjectName("mutedText")
            date_label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
            self._files_layout.addWidget(name_label, row, 0)
            self._files_layout.addWidget(date_label, row, 1)
        self._files_layout.setColumnStretch(0, 1)

    def open_import_report(self):
        window = self.window()
        change_page = getattr(window, "change_page", None)
        if callable(change_page):
            change_page(self.streaming_tab, "Panel Platform")

        show_mode_selection = getattr(
            self.streaming_tab,
            "show_mode_selection",
            None,
        )
        if callable(show_mode_selection):
            show_mode_selection()

    # --- obliczenia -------------------------------------------------------

    @staticmethod
    def _product_platforms(product):
        platforms = product.get("streaming", [])
        if not isinstance(platforms, list):
            platforms = [platforms] if platforms else []
        return [
            str(platform).strip()
            for platform in platforms
            if str(platform).strip()
        ]

    @staticmethod
    def _year_net_totals(reports):
        if not reports:
            return {}

        years = {}
        for report in reports:
            year = str(report.year)
            years[year] = years.get(year, 0) + float(report.total_net or 0)
        return {
            year: round(amount, 2)
            for year, amount in sorted(years.items())
        }

    @staticmethod
    def _load_monthly_reports():
        try:
            return list_monthly_book_reports()
        except Exception:
            return []

    @staticmethod
    def _load_yearly_reports():
        try:
            return list_book_reports()
        except Exception:
            return []

    @classmethod
    def _report_count(cls):
        return len(cls._load_monthly_reports())

    @staticmethod
    def _latest_year(reports):
        if not reports:
            return None
        return max(int(report.year) for report in reports)

    @staticmethod
    def _settlement_summary_text(reports):
        if not reports:
            return "Brak zaimportowanych raportów miesięcznych."

        latest_year = max(int(report.year) for report in reports)
        latest_reports = [
            report for report in reports
            if int(report.year) == latest_year
        ]
        total_net = sum(float(report.total_net or 0) for report in latest_reports)
        total_gross = sum(
            float(report.total_gross or 0)
            for report in latest_reports
            if report.total_gross is not None
        )
        source_rows = sum(int(report.source_rows or 0) for report in latest_reports)
        return (
            f"Rok {latest_year}: netto {format_money(total_net)}, "
            f"brutto {format_money(total_gross)}, "
            f"pozycji źródłowych: {source_rows}."
        )

    @classmethod
    def _latest_net_text(cls, reports):
        return format_money(cls._latest_net_value(reports))

    @staticmethod
    def _latest_net_value(reports):
        if not reports:
            return 0.0
        latest_year = max(int(report.year) for report in reports)
        return sum(
            float(report.total_net or 0)
            for report in reports
            if int(report.year) == latest_year
        )

    @staticmethod
    def _recent_report_files(limit=5):
        folder = Path(report_generator.FOLDER)
        if not folder.exists():
            return []
        reports = sorted(
            (
                path for path in folder.rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".pdf", ".xlsx", ".txt"}
                and not path.name.startswith(("~$", "."))
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:limit]
        return [
            (path.name, datetime.fromtimestamp(path.stat().st_mtime))
            for path in reports
        ]

    # --- cykl życia -------------------------------------------------------

    def reload(self):
        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        self.refresh()
        self._refresh_timer.start()

    def hideEvent(self, event):
        self._refresh_timer.stop()
        super().hideEvent(event)
