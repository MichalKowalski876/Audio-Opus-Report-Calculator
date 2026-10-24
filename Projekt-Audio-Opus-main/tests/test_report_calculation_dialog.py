from types import SimpleNamespace

import pytest
from PySide6 import QtCore, QtWidgets

from GUI.Widgets.Dialogs.ReportCalculationDialog import ReportCalculationDialog
from platforms.report_calculator import (
    ReportCalculationError,
    ReportFileCalculationStatus,
)


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def dialog(qapp, monkeypatch):
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.load_streaming_platforms",
        lambda: [
            {"id": 1, "name": "Legimi"},
            {"id": 2, "name": "Storytel"},
            {"id": 3, "name": "Voices"},
        ],
    )
    return ReportCalculationDialog()


def test_lists_platforms_checked_by_default(dialog):
    assert dialog.platforms_list.count() == 3
    assert dialog.select_all_checkbox.text() == ""
    assert dialog.select_all_checkbox.isChecked()
    assert dialog.selected_platform_names() == ["Legimi", "Storytel", "Voices"]
    assert not dialog.all_years_checkbox.isChecked()
    assert dialog.year_spin.isEnabled()


def test_select_all_checkbox_controls_every_platform(dialog):
    dialog.select_all_checkbox.setChecked(False)

    assert dialog.selected_platform_names() == []

    dialog.select_all_checkbox.setChecked(True)

    assert dialog.selected_platform_names() == ["Legimi", "Storytel", "Voices"]


def test_unchecking_platform_clears_select_all_checkbox(dialog):
    dialog.platforms_list.item(1).setCheckState(QtCore.Qt.CheckState.Unchecked)

    assert not dialog.select_all_checkbox.isChecked()
    assert dialog.selected_platform_names() == ["Legimi", "Voices"]


def test_calculation_receives_selected_platforms(dialog, monkeypatch):
    dialog.platforms_list.item(2).setCheckState(QtCore.Qt.CheckState.Unchecked)
    received = {}

    def calculate(year, selected_platform_names):
        received["year"] = year
        received["platforms"] = selected_platform_names
        return SimpleNamespace(
            year=year,
            report_files=2,
            included_rows=4,
            book_summary_rows=3,
            quarterly_rows=1,
            unmatched_books=0,
            database_path="db.sqlite",
        )

    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        calculate,
    )
    monkeypatch.setattr(QtWidgets.QMessageBox, "information", lambda *args: None)

    dialog.calculate()

    assert received == {
        "year": dialog.year_spin.value(),
        "platforms": ["Legimi", "Storytel"],
    }


def test_calculation_only_reports_missing_books_without_opening_add_dialog(
    dialog,
    monkeypatch,
):
    result = SimpleNamespace(
        year=dialog.year_spin.value(),
        report_files=1,
        included_rows=1,
        book_summary_rows=1,
        quarterly_rows=0,
        unmatched_books=1,
        unmatched_entries=({"title": "Nowa książka"},),
        database_path="db.sqlite",
    )
    messages = []
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        lambda *args, **kwargs: result,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda *args: messages.append(args[2]),
    )

    dialog.calculate()

    assert dialog.calculation_result is result
    assert "Uzupełnij bazę" in messages[0]


def test_all_years_calculates_each_year_and_merges_missing_books(
    dialog,
    monkeypatch,
):
    calls = []

    def calculate(year, selected_platform_names):
        calls.append((year, selected_platform_names))
        return SimpleNamespace(
            year=year,
            report_files=1,
            source_rows=1,
            included_rows=1,
            book_summary_rows=1,
            platform_summary_rows=1,
            quarterly_rows=0,
            unmatched_books=1,
            unmatched_entries=(
                {
                    "title": "Wspólna książka",
                    "isbn": "978-1",
                    "author": "Autor",
                    "platform": "Legimi",
                    "net": 10.0,
                    "source_files": (f"Raport-{year}.xlsx",),
                },
            ),
            database_path="db.sqlite",
        )

    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.available_report_years",
        lambda: (2025, 2026),
    )
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        calculate,
    )
    messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda *args: messages.append(args[2]),
    )

    dialog.all_years_checkbox.setChecked(True)
    assert not dialog.year_spin.isEnabled()
    dialog.calculate()

    assert calls == [
        (2025, ["Legimi", "Storytel", "Voices"]),
        (2026, ["Legimi", "Storytel", "Voices"]),
    ]
    result = dialog.calculation_result
    assert result.years == (2025, 2026)
    assert result.report_files == 2
    assert len(result.unmatched_entries) == 1
    assert result.unmatched_entries[0]["net"] == 20.0
    assert result.unmatched_entries[0]["report_links"] == (
        {"year": 2025, "source_files": ("Raport-2025.xlsx",)},
        {"year": 2026, "source_files": ("Raport-2026.xlsx",)},
    )
    assert "2025, 2026" in messages[0]


def test_success_message_lists_each_report_and_row_count(dialog, monkeypatch):
    result = SimpleNamespace(
        year=2026,
        report_files=1,
        included_rows=7,
        book_summary_rows=4,
        quarterly_rows=0,
        unmatched_books=0,
        database_path="db.sqlite",
        file_statuses=(
            ReportFileCalculationStatus(
                year=2026,
                platform_name="Legimi",
                source_file="Legimi.xlsx",
                calculated=True,
                rows=7,
            ),
        ),
    )
    messages = []
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        lambda *args, **kwargs: result,
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda *args: messages.append(args[2]),
    )

    dialog.calculate()

    assert "Legimi — Legimi.xlsx — PRZELICZONY — 7 pozycji" in messages[0]


def test_error_message_explains_how_to_fix_column_mapping(dialog, monkeypatch):
    status = ReportFileCalculationStatus(
        year=2026,
        platform_name="Nowa platforma",
        source_file="Nowy raport.xlsx",
        calculated=False,
        rows=0,
        message="Nie rozpoznano raportu.",
        action="Skonfiguruj kolumny raportu.",
    )

    def fail(*args, **kwargs):
        raise ReportCalculationError(
            "Nie udało się przeliczyć raportu.",
            file_statuses=(status,),
        )

    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        fail,
    )
    messages = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda *args: messages.append(args[2]),
    )

    dialog.calculate()

    assert dialog.calculation_result is None
    assert "Nowa platforma — Nowy raport.xlsx — NIE PRZELICZONO" in messages[0]
    assert "Powód: Nie rozpoznano raportu." in messages[0]
    assert "Co zrobić: Skonfiguruj kolumny raportu." in messages[0]


def test_partial_result_saves_valid_report_and_warns_about_invalid_one(
    dialog,
    monkeypatch,
):
    result = SimpleNamespace(
        year=2026,
        report_files=1,
        included_rows=3,
        book_summary_rows=2,
        quarterly_rows=0,
        unmatched_books=0,
        unmatched_entries=(),
        database_path="db.sqlite",
        file_statuses=(
            ReportFileCalculationStatus(
                year=2026,
                platform_name="Legimi",
                source_file="Legimi.xlsx",
                calculated=True,
                rows=3,
            ),
            ReportFileCalculationStatus(
                year=2026,
                platform_name="Voices",
                source_file="Voices.xlsx",
                calculated=False,
                rows=0,
                message="Nie rozpoznano raportu.",
                action="Skonfiguruj kolumny raportu.",
            ),
        ),
    )
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.ReportCalculationDialog.calculate_platform_reports",
        lambda *args, **kwargs: result,
    )
    warnings = []
    information = []
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "warning",
        lambda *args: warnings.append(args[2]),
    )
    monkeypatch.setattr(
        QtWidgets.QMessageBox,
        "information",
        lambda *args: information.append(args[2]),
    )

    dialog.calculate()

    assert dialog.calculation_result is result
    assert information == []
    assert "Legimi — Legimi.xlsx — PRZELICZONY — 3 pozycji" in warnings[0]
    assert "Voices — Voices.xlsx — NIE PRZELICZONO" in warnings[0]
    assert "Pozostałe raporty zostały zapisane" in warnings[0]
