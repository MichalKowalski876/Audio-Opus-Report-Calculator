from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from platforms.manual import ManualReportError, load_streaming_platforms
from platforms.report_calculator import (
    ReportCalculationError,
    available_report_years,
    calculate_platform_reports,
)
from platforms.products import normalize_isbn, normalize_title


@dataclass(frozen=True)
class BatchCalculationResult:
    database_path: Path
    years: tuple[int, ...]
    year: int | None
    report_files: int
    source_rows: int
    included_rows: int
    book_summary_rows: int
    platform_summary_rows: int
    unmatched_books: int
    quarterly_rows: int
    unmatched_entries: tuple[dict, ...]
    file_statuses: tuple[object, ...] = ()


class ReportCalculationDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.calculation_result = None
        self.platforms = []
        self.platform_load_error = None
        self.setWindowTitle("Przelicz raporty")
        self.resize(480, 430)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Przelicz raporty platform")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        description = QtWidgets.QLabel(
            "Wybierz rok albo wszystkie lata oraz platformy. Program odczyta "
            "raporty i zapisze miesięczne lub kwartalne rozliczenia w bazie SQLite."
        )
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QtWidgets.QFormLayout()
        self.year_spin = QtWidgets.QSpinBox()
        self.year_spin.setRange(1900, 9999)
        self.year_spin.setValue(datetime.now().year)
        form.addRow("Rok raportów:", self.year_spin)
        self.all_years_checkbox = QtWidgets.QCheckBox("Wszystkie lata")
        self.all_years_checkbox.toggled.connect(
            lambda checked: self.year_spin.setEnabled(not checked)
        )
        form.addRow("", self.all_years_checkbox)
        layout.addLayout(form)

        platforms_label = QtWidgets.QLabel("Platformy:")
        layout.addWidget(platforms_label)

        self.select_all_checkbox = QtWidgets.QCheckBox()
        self.select_all_checkbox.setToolTip("Zaznacz wszystkie platformy")
        self.select_all_checkbox.toggled.connect(self._set_all_platforms)
        layout.addWidget(self.select_all_checkbox)

        self.platforms_list = QtWidgets.QListWidget()
        self.platforms_list.setAlternatingRowColors(True)
        self.platforms_list.setMinimumHeight(130)
        self.platforms_list.itemChanged.connect(self._sync_select_all_checkbox)
        layout.addWidget(self.platforms_list)
        self._load_platforms()

        layout.addStretch()

        action_layout = QtWidgets.QHBoxLayout()
        action_layout.addStretch()

        self.calculate_button = QtWidgets.QPushButton("Przelicz")
        self.calculate_button.setMinimumWidth(140)
        self.calculate_button.clicked.connect(self.calculate)
        action_layout.addWidget(self.calculate_button)

        close_button = QtWidgets.QPushButton("Zamknij")
        close_button.clicked.connect(self.reject)
        action_layout.addWidget(close_button)
        layout.addLayout(action_layout)

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.enter_shortcut.activated.connect(self._handle_enter_pressed)

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(self._handle_enter_pressed)

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        if self.calculate_button.isEnabled():
            self.calculate()

    def _load_platforms(self):
        try:
            self.platforms = load_streaming_platforms()
        except ManualReportError as error:
            self.platform_load_error = str(error)
            self.platforms = []

        self.platforms_list.blockSignals(True)
        self.platforms_list.clear()
        for platform in self.platforms:
            name = str(platform.get("name") or "").strip()
            if not name:
                continue
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, name)
            item.setFlags(
                item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable
            )
            item.setCheckState(QtCore.Qt.CheckState.Checked)
            self.platforms_list.addItem(item)
        self.platforms_list.blockSignals(False)

        has_platforms = self.platforms_list.count() > 0
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(has_platforms)
        self.select_all_checkbox.blockSignals(False)

    def _set_all_platforms(self, checked):
        state = (
            QtCore.Qt.CheckState.Checked
            if checked
            else QtCore.Qt.CheckState.Unchecked
        )
        self.platforms_list.blockSignals(True)
        for row in range(self.platforms_list.count()):
            self.platforms_list.item(row).setCheckState(state)
        self.platforms_list.blockSignals(False)

    def _sync_select_all_checkbox(self, _item=None):
        all_checked = self.platforms_list.count() > 0 and all(
            self.platforms_list.item(row).checkState()
            == QtCore.Qt.CheckState.Checked
            for row in range(self.platforms_list.count())
        )
        self.select_all_checkbox.blockSignals(True)
        self.select_all_checkbox.setChecked(all_checked)
        self.select_all_checkbox.blockSignals(False)

    def selected_platform_names(self):
        return [
            self.platforms_list.item(row).data(QtCore.Qt.ItemDataRole.UserRole)
            for row in range(self.platforms_list.count())
            if self.platforms_list.item(row).checkState()
            == QtCore.Qt.CheckState.Checked
        ]

    def calculate(self):
        if self.platform_load_error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd odczytu platform",
                self.platform_load_error,
            )
            return

        selected_platforms = self.selected_platform_names()
        if not selected_platforms:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak wybranych platform",
                "Zaznacz co najmniej jedną platformę.",
            )
            return

        years = self._selected_years()
        if not years:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak raportów",
                "Nie znaleziono żadnego roku raportów do przeliczenia.",
            )
            return

        results = self._run_calculations(years, selected_platforms)
        if results is None:
            return
        result = self._combine_results(results)
        self.calculation_result = result
        unmatched_hint = (
            "\nUżyj przycisku „Uzupełnij bazę”, aby dodać "
            "nierozpoznane książki i klientów.\n"
            if result.unmatched_books
            else ""
        )
        file_statuses = tuple(getattr(result, "file_statuses", ()) or ())
        failed_reports = any(
            not bool(getattr(status, "calculated", False))
            for status in file_statuses
        )
        message = (
            f"{self._calculation_period_text(result)}\n\n"
            f"Pliki platform przeliczone poprawnie: {result.report_files}\n"
            f"Pozycje raportów: {result.included_rows}\n"
            f"Miesięczne pozycje książek: {result.book_summary_rows}\n"
            f"Rozliczenia kwartalne: {result.quarterly_rows}\n"
            f"Książki nierozpoznane w bazie: {result.unmatched_books}\n"
            f"{unmatched_hint}\n\n"
            "Raporty:\n"
            f"{self._report_status_text(file_statuses)}"
        )
        if failed_reports:
            message += (
                "\n\nPopraw raporty oznaczone jako nieprzeliczone i uruchom "
                "przeliczanie ponownie. Pozostałe raporty zostały zapisane."
            )
            QtWidgets.QMessageBox.warning(
                self,
                "Część raportów nie została przeliczona",
                message,
            )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Raporty przeliczone",
                message,
            )
        self.accept()

    def _selected_years(self):
        if not self.all_years_checkbox.isChecked():
            return (self.year_spin.value(),)
        try:
            return available_report_years()
        except ReportCalculationError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd odczytu lat raportów",
                str(error),
            )
            return ()

    def _run_calculations(self, years, selected_platforms):
        self.calculate_button.setEnabled(False)
        QtWidgets.QApplication.setOverrideCursor(
            QtCore.Qt.CursorShape.WaitCursor
        )
        try:
            results = []
            for year in years:
                try:
                    results.append(
                        calculate_platform_reports(
                            year,
                            selected_platform_names=selected_platforms,
                        )
                    )
                except ReportCalculationError as error:
                    earlier_statuses = tuple(
                        status
                        for result in results
                        for status in getattr(result, "file_statuses", ())
                    )
                    self._show_calculation_error(error, earlier_statuses)
                    return None
            return tuple(results)
        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd przeliczania raportów",
                f"Wystąpił nieoczekiwany błąd: {error}",
            )
            return None
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
            self.calculate_button.setEnabled(True)

    @staticmethod
    def _combine_results(results):
        if len(results) == 1:
            return results[0]

        entries = {}
        for result in results:
            for source_entry in result.unmatched_entries:
                isbn = normalize_isbn(source_entry.get("isbn"))
                title = normalize_title(source_entry.get("title"))
                key = ("isbn", isbn) if isbn else ("title", title)
                if not key[1]:
                    key = ("entry", result.year, len(entries))
                entry = entries.setdefault(
                    key,
                    {
                        **source_entry,
                        "net": 0.0,
                        "platforms": [],
                        "source_files": [],
                        "report_links": [],
                    },
                )
                entry["net"] += float(source_entry.get("net") or 0.0)
                for platform in str(source_entry.get("platform") or "").split(","):
                    platform = platform.strip()
                    if platform and platform not in entry["platforms"]:
                        entry["platforms"].append(platform)
                source_files = tuple(source_entry.get("source_files") or ())
                for source_file in source_files:
                    if source_file not in entry["source_files"]:
                        entry["source_files"].append(source_file)
                entry["report_links"].append(
                    {
                        "year": result.year,
                        "source_files": source_files,
                    }
                )

        unmatched_entries = tuple(
            {
                "title": entry.get("title", ""),
                "isbn": entry.get("isbn", ""),
                "author": entry.get("author", ""),
                "net": round(entry["net"], 2),
                "platform": ", ".join(entry["platforms"]),
                "source_files": tuple(entry["source_files"]),
                "report_links": tuple(entry["report_links"]),
            }
            for entry in entries.values()
        )
        years = tuple(result.year for result in results)
        return BatchCalculationResult(
            database_path=results[-1].database_path,
            years=years,
            year=None,
            report_files=sum(result.report_files for result in results),
            source_rows=sum(result.source_rows for result in results),
            included_rows=sum(result.included_rows for result in results),
            book_summary_rows=sum(result.book_summary_rows for result in results),
            platform_summary_rows=sum(
                result.platform_summary_rows for result in results
            ),
            unmatched_books=sum(result.unmatched_books for result in results),
            quarterly_rows=sum(result.quarterly_rows for result in results),
            unmatched_entries=unmatched_entries,
            file_statuses=tuple(
                status
                for result in results
                for status in getattr(result, "file_statuses", ())
            ),
        )

    @staticmethod
    def _report_status_text(file_statuses):
        statuses = tuple(file_statuses or ())
        if not statuses:
            return "Brak plików raportów dla wybranego zakresu."

        lines = []
        for status in statuses:
            platform = str(getattr(status, "platform_name", "") or "Platforma")
            source_file = str(getattr(status, "source_file", "") or "raport")
            year = getattr(status, "year", None)
            rows = int(getattr(status, "rows", 0) or 0)
            calculated = bool(getattr(status, "calculated", False))
            prefix = f"• {year} — " if year else "• "
            label = f"{prefix}{platform} — {source_file}"
            if calculated:
                lines.append(
                    f"{label} — PRZELICZONY — {rows} "
                    f"{ReportCalculationDialog._positions_word(rows)}"
                )
                continue

            lines.append(
                f"{label} — NIE PRZELICZONO — {rows} "
                f"{ReportCalculationDialog._positions_word(rows)} odczytanych"
            )
            message = str(getattr(status, "message", "") or "").strip()
            action = str(getattr(status, "action", "") or "").strip()
            if message:
                lines.append(f"  Powód: {message}")
            if action:
                lines.append(f"  Co zrobić: {action}")
        return "\n".join(lines)

    @staticmethod
    def _positions_word(count):
        return "pozycja" if count == 1 else "pozycji"

    def _show_calculation_error(self, error, earlier_statuses=()):
        statuses = tuple(earlier_statuses) + tuple(
            getattr(error, "file_statuses", ()) or ()
        )
        if not statuses:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd przeliczania raportów",
                str(error),
            )
            return

        QtWidgets.QMessageBox.warning(
            self,
            "Nie przeliczono wszystkich raportów",
            (
                "Wynik dla każdego raportu:\n\n"
                f"{self._report_status_text(statuses)}\n\n"
                "Popraw wskazane problemy i uruchom przeliczanie ponownie."
            ),
        )

    @staticmethod
    def _calculation_period_text(result):
        years = tuple(getattr(result, "years", ()) or ())
        if not years:
            return f"Przeliczono raporty za {result.year} rok."
        return "Przeliczono raporty za lata: " + ", ".join(map(str, years)) + "."
