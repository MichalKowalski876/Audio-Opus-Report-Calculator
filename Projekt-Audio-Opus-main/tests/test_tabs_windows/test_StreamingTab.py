from types import SimpleNamespace
from unittest.mock import call, patch
from datetime import datetime
from pathlib import Path

import pytest
from PySide6 import QtCore, QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Tabs.StreamingTab import StreamingTab
from platforms.report_calculator import ImportedReportDeletionResult
from platforms.report_viewer import (
    BookReportDetails,
    BookReportEntry,
    BookReportSummary,
    MonthlyBookReportSummary,
    MonthlyReportTransaction,
    QuarterlyBookReportSummary,
)
from platforms.reports import PLATFORM_REPORTS_ROOT, TrashedReport
from platforms.xlsx_reports import ReportFileAnalysis


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def streaming_tab():
    platform = {
        "id": 1,
        "name": "Legimi",
        "cut": 0,
        "integration": "legimi",
    }

    with (
        patch("core.database_controller.load_database", return_value=[platform]),
        patch("core.database_controller.item_get", return_value=platform),
        patch("GUI.Tabs.StreamingTab.list_book_reports", return_value=[]),
        patch("GUI.Tabs.StreamingTab.list_monthly_book_reports", return_value=[]),
        patch("GUI.Tabs.StreamingTab.list_quarterly_book_reports", return_value=[]),
        patch("GUI.Tabs.StreamingTab.scan_report_directory", return_value=[]),
    ):
        tab = StreamingTab()
        yield tab
        tab.close()


def test_initialization(streaming_tab):
    assert isinstance(streaming_tab, QtWidgets.QWidget)
    assert isinstance(streaming_tab.layout(), QtWidgets.QVBoxLayout)
    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.mode_selection_page
    assert streaming_tab.calculation_mode_button.text() == "Przelicz Raporty"
    assert not hasattr(streaming_tab, "transaction_mode_button")
    assert not hasattr(streaming_tab, "automatic_page")
    assert not hasattr(streaming_tab, "download_button")
    assert streaming_tab.mode_stack.count() == 5
    assert not hasattr(streaming_tab, "transaction_page")
    assert streaming_tab.platform_reports_splitter.count() == 2
    assert streaming_tab.add_platform_button.text() == "Dodaj platformę"
    assert streaming_tab.edit_platform_button.text() == "Edytuj"
    assert streaming_tab.delete_platform_button.text() == "Usuń"
    assert not streaming_tab.edit_platform_button.isEnabled()
    assert not streaming_tab.delete_platform_button.isEnabled()
    assert streaming_tab.platforms_table.rowCount() == 1
    assert streaming_tab.platforms_table.item(0, 0).text() == "Legimi"
    assert streaming_tab.overview_monthly_button.isChecked()
    assert streaming_tab.overview_quarterly_button.text() == "Raporty kwartalne"
    assert streaming_tab.overview_reports_table.horizontalHeaderItem(2).text() == (
        "Miesiąc"
    )
    assert isinstance(streaming_tab.overview_book_filter, QtWidgets.QLineEdit)
    assert isinstance(streaming_tab.overview_isbn_filter, QtWidgets.QLineEdit)
    assert isinstance(streaming_tab.overview_period_filter, QtWidgets.QLineEdit)
    assert isinstance(streaming_tab.overview_client_filter, QtWidgets.QLineEdit)
    assert streaming_tab.overview_book_filter.placeholderText() == (
        "Filtruj po nazwie..."
    )
    assert streaming_tab.overview_client_filter.placeholderText() == (
        "Filtruj po kliencie..."
    )
    assert streaming_tab.overview_isbn_filter.placeholderText() == (
        "Filtruj po ISBN..."
    )
    assert streaming_tab.overview_period_filter.placeholderText() == (
        "Filtruj po miesiącu..."
    )
    assert streaming_tab.overview_period_filter_label.text() == "Miesiąc:"
    assert streaming_tab.help_button.text() == "?"
    assert streaming_tab.tutorial_toggle.text() == "Kroki"
    assert streaming_tab.tutorial_toggle.isCheckable()
    assert not streaming_tab.tutorial_toggle.isChecked()
    book_filter_index = streaming_tab.overview_filters_layout.indexOf(
        streaming_tab.overview_book_filter
    )
    isbn_filter_index = streaming_tab.overview_filters_layout.indexOf(
        streaming_tab.overview_isbn_filter
    )
    period_filter_index = streaming_tab.overview_filters_layout.indexOf(
        streaming_tab.overview_period_filter
    )
    client_filter_index = streaming_tab.overview_filters_layout.indexOf(
        streaming_tab.overview_client_filter
    )
    assert streaming_tab.overview_filters_layout.getItemPosition(
        book_filter_index
    ) == (1, 0, 1, 1)
    assert streaming_tab.overview_filters_layout.getItemPosition(
        isbn_filter_index
    ) == (1, 1, 1, 1)
    assert streaming_tab.overview_filters_layout.getItemPosition(
        period_filter_index
    ) == (1, 2, 1, 1)
    assert streaming_tab.overview_filters_layout.getItemPosition(
        client_filter_index
    ) == (1, 3, 1, 1)


def test_report_tutorial_restarts_steps_for_each_report_view(
    streaming_tab,
    qapp,
):
    streaming_tab.resize(1200, 760)
    streaming_tab.show()
    qapp.processEvents()
    assert streaming_tab.tutorial_toggle.geometry().left() < (
        streaming_tab.help_button.geometry().left()
    )
    button_gap = (
        streaming_tab.help_button.geometry().left()
        - streaming_tab.tutorial_toggle.geometry().right()
        - 1
    )
    assert 0 <= button_gap <= 10
    assert streaming_tab.tutorial_toggle.width() >= (
        streaming_tab.tutorial_toggle.sizeHint().width()
    )

    streaming_tab.tutorial_toggle.click()
    qapp.processEvents()

    tutorial = streaming_tab.report_tutorial
    assert tutorial.is_active
    assert tutorial.current_index == 0
    assert tutorial.current_target is streaming_tab.add_platform_button
    assert tutorial.bubble.step_label.text() == "Krok 1/2"
    assert tutorial.bubbles[1].step_label.text() == "Krok 2/2"
    assert not tutorial.halo.isHidden()
    assert not tutorial.bubble.isHidden()
    assert not tutorial.bubbles[1].isHidden()
    assert sum(not halo.isHidden() for halo in tutorial.halos) == 2
    assert tutorial.bubble.title_label.isHidden()
    assert tutorial.bubble.text_label.isHidden()

    QtWidgets.QApplication.sendEvent(
        tutorial.current_target,
        QtCore.QEvent(QtCore.QEvent.Type.Enter),
    )
    qapp.processEvents()
    assert not tutorial.bubble.title_label.isHidden()
    assert not tutorial.bubble.text_label.isHidden()

    QtWidgets.QApplication.sendEvent(
        tutorial.current_target,
        QtCore.QEvent(QtCore.QEvent.Type.Leave),
    )
    qapp.processEvents()
    assert tutorial.bubble.title_label.isHidden()
    assert tutorial.bubble.text_label.isHidden()

    with patch(
        "GUI.Tabs.StreamingTab.prompt_add_streaming_platform",
        return_value=None,
    ):
        streaming_tab.add_platform_button.click()
    qapp.processEvents()
    assert tutorial.current_index == 0
    assert tutorial.current_target is streaming_tab.add_platform_button
    assert not tutorial.bubbles[0].isHidden()
    assert not tutorial.bubbles[1].isHidden()

    streaming_tab.calculation_mode_button.click()
    qapp.processEvents()
    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.calculation_page
    assert tutorial.current_index == 0
    assert tutorial.current_target is streaming_tab.manual_add_report_button
    assert tutorial.bubble.step_label.text() == "Krok 1/3"
    assert tutorial.bubbles[1].step_label.text() == "Krok 2/3"
    assert tutorial.bubbles[2].step_label.text() == "Krok 3/3"
    assert all(not bubble.isHidden() for bubble in tutorial.bubbles[:3])
    assert sum(not halo.isHidden() for halo in tutorial.halos) == 3

    with patch(
        "GUI.Tabs.StreamingTab.ManualPlatformReportDialog.exec",
        return_value=0,
    ):
        streaming_tab.manual_add_report_button.click()
    qapp.processEvents()
    assert tutorial.current_index == 0
    assert tutorial.current_target is streaming_tab.manual_add_report_button
    assert all(not bubble.isHidden() for bubble in tutorial.bubbles[:3])

    report_path = PLATFORM_REPORTS_ROOT / "2026" / "Nieznany.xlsx"
    streaming_tab._report_file_analyses = [
        ReportFileAnalysis(path=report_path, recognized=False)
    ]
    streaming_tab.render_report_files()
    streaming_tab.report_files_table.selectRow(0)
    qapp.processEvents()
    assert streaming_tab.map_report_columns_button.isEnabled()

    streaming_tab.map_report_columns_button.click()
    qapp.processEvents()
    assert streaming_tab.mode_stack.currentWidget() is (
        streaming_tab.report_column_mapping_page
    )
    assert tutorial.current_index == 0
    assert tutorial.current_targets == tuple(
        streaming_tab.report_column_mapping_page.excel_buttons.values()
    )
    assert tutorial.bubble.step_label.text() == "Krok 1/2"
    assert tutorial.bubbles[1].step_label.text() == "Krok 2/2"
    assert not tutorial.bubbles[0].isHidden()
    assert not tutorial.bubbles[1].isHidden()
    assert sum(not halo.isHidden() for halo in tutorial.halos) == (
        len(streaming_tab.report_column_mapping_page.excel_buttons) + 1
    )

    excel_button = streaming_tab.report_column_mapping_page.excel_buttons["title"]
    with patch.object(
        streaming_tab.excel_cell_picker_page,
        "open_report",
    ):
        excel_button.click()
    qapp.processEvents()
    assert streaming_tab.mode_stack.currentWidget() is (
        streaming_tab.excel_cell_picker_page
    )
    assert tutorial.is_active
    assert tutorial.current_index == -1
    assert tutorial.halo.isHidden()
    assert tutorial.bubble.isHidden()

    streaming_tab.excel_cell_picker_page.cell_selected.emit(
        "Book title",
        "Sales",
        1,
        1,
    )
    qapp.processEvents()
    assert streaming_tab.mode_stack.currentWidget() is (
        streaming_tab.report_column_mapping_page
    )
    assert tutorial.current_index == 1
    assert tutorial.current_target is (
        streaming_tab.report_column_mapping_page.save_button
    )
    assert tutorial.bubbles[0].step_label.text() == "Krok 1/2"
    assert tutorial.bubbles[1].step_label.text() == "Krok 2/2"
    assert not tutorial.bubbles[0].isHidden()
    assert not tutorial.bubbles[1].isHidden()

    streaming_tab.report_column_mapping_page.mapping_saved.emit(str(report_path))
    qapp.processEvents()
    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.calculation_page
    assert tutorial.current_index == 2
    assert tutorial.current_target is streaming_tab.manual_calculate_reports_button
    assert tutorial.bubbles[0].step_label.text() == "Krok 1/3"
    assert tutorial.bubbles[1].step_label.text() == "Krok 2/3"
    assert tutorial.bubbles[2].step_label.text() == "Krok 3/3"
    assert all(not bubble.isHidden() for bubble in tutorial.bubbles[:3])

    streaming_tab.tutorial_toggle.click()
    qapp.processEvents()
    assert not tutorial.is_active
    assert not streaming_tab.tutorial_toggle.isChecked()
    assert tutorial.halo.isHidden()
    assert tutorial.bubble.isHidden()


def test_calculation_mode_opens_report_view_and_returns(
    streaming_tab,
    qapp,
):
    streaming_tab.calculation_mode_button.click()
    qapp.processEvents()

    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.calculation_page
    assert streaming_tab.manual_add_report_button.text() == "Dodaj raport"
    assert streaming_tab.manual_calculate_reports_button.text() == "Przelicz raporty"
    assert streaming_tab.complete_report_database_button.text() == "Uzupełnij bazę"
    assert not streaming_tab.complete_report_database_button.isEnabled()
    assert not hasattr(streaming_tab, "manual_report_list_button")
    assert streaming_tab.add_report_file_button is streaming_tab.manual_add_report_button
    assert streaming_tab.report_files_table.rowCount() == 0
    assert streaming_tab.map_report_columns_button.text() == "Dopasuj kolumny"
    assert streaming_tab.delete_report_file_button.text() == "Usuń"
    assert streaming_tab.show_report_trash_button.text() == "Kosz"
    assert streaming_tab.calculation_back_button.text() == "Wstecz"

    header_layout = streaming_tab.calculation_page.layout().itemAt(0).layout()
    assert header_layout.indexOf(
        streaming_tab.manual_calculate_reports_button
    ) < header_layout.indexOf(
        streaming_tab.complete_report_database_button
    ) < header_layout.indexOf(streaming_tab.map_report_columns_button)

    streaming_tab.calculation_back_button.click()
    qapp.processEvents()

    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.mode_selection_page


@patch("GUI.Tabs.StreamingTab.ManualPlatformReportDialog")
def test_add_report_button_opens_dialog_and_refreshes_reports(
    mock_dialog_class,
    streaming_tab,
):
    with (
        patch.object(streaming_tab, "refresh_report_files") as refresh_reports,
        patch.object(streaming_tab, "refresh_platform_list") as refresh_platforms,
    ):
        streaming_tab.manual_add_report_button.click()

    mock_dialog_class.assert_called_once_with(streaming_tab)
    mock_dialog_class.return_value.exec.assert_called_once_with()
    refresh_reports.assert_called_once_with()
    refresh_platforms.assert_called_once_with()


def test_main_page_platform_list_can_be_refreshed(streaming_tab):
    platforms = [
        {"id": 1, "name": "Legimi"},
        {"id": 2, "name": "Storytel"},
    ]
    with patch(
        "GUI.Tabs.StreamingTab.load_streaming_platforms",
        return_value=platforms,
    ):
        streaming_tab.refresh_platform_list()

    assert streaming_tab.platforms_table.rowCount() == 2
    assert streaming_tab.platforms_table.item(1, 0).text() == "Storytel"
    assert streaming_tab.platforms_table.horizontalHeader().sectionResizeMode(0) == (
        QtWidgets.QHeaderView.ResizeMode.Interactive
    )


@patch("GUI.Tabs.StreamingTab.prompt_add_streaming_platform")
def test_main_page_can_add_platform(mock_prompt, streaming_tab):
    platform = {"id": 2, "name": "Storytel"}
    mock_prompt.return_value = platform

    with patch.object(streaming_tab, "refresh_platform_list") as refresh:
        streaming_tab.add_platform_button.click()

    mock_prompt.assert_called_once_with(streaming_tab)
    refresh.assert_called_once_with()


def test_selecting_platform_enables_edit_and_delete(streaming_tab):
    streaming_tab.platforms_table.selectRow(0)

    assert streaming_tab.edit_platform_button.isEnabled()
    assert streaming_tab.delete_platform_button.isEnabled()


@patch("GUI.Tabs.StreamingTab.rename_streaming_platform")
@patch("GUI.Tabs.StreamingTab.QtWidgets.QInputDialog.getText")
def test_selected_platform_can_be_renamed(
    mock_get_text,
    mock_rename,
    streaming_tab,
):
    mock_get_text.return_value = ("Legimi Polska", True)
    mock_rename.return_value = {"id": 1, "name": "Legimi Polska"}
    streaming_tab.platforms_table.selectRow(0)

    with patch.object(streaming_tab, "refresh_platform_list") as refresh:
        streaming_tab.edit_platform_button.click()

    mock_get_text.assert_called_once()
    mock_rename.assert_called_once_with(1, "Legimi Polska")
    refresh.assert_called_once_with()


@patch("GUI.Tabs.StreamingTab.delete_streaming_platform")
def test_selected_platform_can_be_deleted(mock_delete, streaming_tab):
    streaming_tab.platforms_table.selectRow(0)
    with (
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ),
        patch.object(streaming_tab, "refresh_platform_list") as refresh,
    ):
        streaming_tab.delete_platform_button.click()

    mock_delete.assert_called_once_with(1)
    refresh.assert_called_once_with()


@patch("GUI.Tabs.StreamingTab.ReportCalculationDialog")
def test_manual_calculate_reports_button_opens_dialog(
    mock_dialog_class,
    streaming_tab,
):
    streaming_tab.manual_calculate_reports_button.click()

    mock_dialog_class.assert_called_once_with(streaming_tab)
    mock_dialog_class.return_value.exec.assert_called_once_with()


@patch("GUI.Tabs.StreamingTab.AddBookDialog")
@patch("GUI.Tabs.StreamingTab.ReportCalculationDialog")
def test_calculation_enables_database_completion_without_opening_book_dialog(
    mock_calculation_dialog_class,
    mock_add_book_dialog_class,
    streaming_tab,
):
    entry = {
        "title": "Nowa książka",
        "isbn": "9780000000001",
        "source_files": ("Raport.xlsx",),
    }
    mock_calculation_dialog_class.return_value.calculation_result = SimpleNamespace(
        year=2026,
        unmatched_entries=(entry,),
    )

    streaming_tab.manual_calculate_reports_button.click()

    mock_add_book_dialog_class.assert_not_called()
    assert streaming_tab.complete_report_database_button.isEnabled()
    assert streaming_tab._pending_unmatched_entries == [entry]
    assert "(1)" in streaming_tab.complete_report_database_button.toolTip()


@patch("GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information")
@patch("GUI.Tabs.StreamingTab.relink_unmatched_rows", return_value=1)
@patch("GUI.Tabs.StreamingTab.record_added_book")
@patch("GUI.Tabs.StreamingTab.AddBookDialog")
def test_database_completion_adds_detected_book_on_demand(
    mock_add_book_dialog_class,
    mock_record_added_book,
    mock_relink_unmatched_rows,
    mock_information,
    streaming_tab,
):
    entry = {
        "title": "Nowa książka",
        "isbn": "9780000000001",
        "source_files": ("Raport.xlsx",),
    }
    streaming_tab._pending_unmatched_entries = [entry]
    streaming_tab._pending_unmatched_year = 2026
    streaming_tab._update_complete_report_database_button()
    book_dialog = mock_add_book_dialog_class.return_value
    book_dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
    book_dialog.added_product_id = 41

    with (
        patch.object(streaming_tab, "_refresh_tabs_after_adding_books") as refresh_tabs,
        patch.object(streaming_tab, "refresh_overview_reports") as refresh_reports,
    ):
        streaming_tab.complete_report_database_button.click()

    mock_add_book_dialog_class.assert_called_once_with(entry, 1, 1, streaming_tab)
    mock_record_added_book.assert_called_once_with(
        2026,
        ("Raport.xlsx",),
        41,
    )
    mock_relink_unmatched_rows.assert_called_once_with()
    refresh_tabs.assert_called_once_with()
    refresh_reports.assert_called_once_with(show_errors=True)
    assert streaming_tab._pending_unmatched_entries == []
    assert not streaming_tab.complete_report_database_button.isEnabled()
    mock_information.assert_called_once()


@patch("GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information")
@patch("GUI.Tabs.StreamingTab.relink_unmatched_rows", return_value=2)
@patch("GUI.Tabs.StreamingTab.record_added_book")
@patch("GUI.Tabs.StreamingTab.AddBookDialog")
def test_database_completion_records_book_links_for_every_calculated_year(
    mock_add_book_dialog_class,
    mock_record_added_book,
    _mock_relink_unmatched_rows,
    _mock_information,
    streaming_tab,
):
    entry = {
        "title": "Nowa książka",
        "isbn": "9780000000001",
        "source_files": ("Raport-2025.xlsx", "Raport-2026.xlsx"),
        "report_links": (
            {"year": 2025, "source_files": ("Raport-2025.xlsx",)},
            {"year": 2026, "source_files": ("Raport-2026.xlsx",)},
        ),
    }
    streaming_tab._pending_unmatched_entries = [entry]
    streaming_tab._pending_unmatched_year = None
    streaming_tab._update_complete_report_database_button()
    book_dialog = mock_add_book_dialog_class.return_value
    book_dialog.exec.return_value = QtWidgets.QDialog.DialogCode.Accepted
    book_dialog.added_product_id = 52

    with (
        patch.object(streaming_tab, "_refresh_tabs_after_adding_books"),
        patch.object(streaming_tab, "refresh_overview_reports"),
    ):
        streaming_tab.complete_report_database_button.click()

    assert mock_record_added_book.call_args_list == [
        call(2025, ("Raport-2025.xlsx",), 52),
        call(2026, ("Raport-2026.xlsx",), 52),
    ]


def test_report_file_list_marks_recognized_and_unrecognized_reports(
    streaming_tab,
    qapp,
):
    analyses = [
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2026" / "Legimi.xlsx",
            recognized=True,
            platform_key="legimi",
            report_types=("transaction",),
            rows_count=12,
            message="Rozpoznano 12 pozycji.",
        ),
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2026" / "Nowa platforma.xlsx",
            recognized=False,
            message="Nie rozpoznano raportu.",
        ),
    ]
    with patch(
        "GUI.Tabs.StreamingTab.scan_report_directory",
        return_value=analyses,
    ) as scan_reports:
        streaming_tab.show_calculation_page()
        qapp.processEvents()

    scan_reports.assert_called_once_with(PLATFORM_REPORTS_ROOT)
    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.calculation_page
    assert streaming_tab.report_files_table.rowCount() == 2
    assert streaming_tab.report_files_table.item(0, 0).text() == "Rozpoznany"
    assert streaming_tab.report_files_table.item(0, 1).text() == str(
        Path("2026") / "Legimi.xlsx"
    )
    assert streaming_tab.report_files_table.item(0, 0).background().color().name() == (
        "#2e7d32"
    )
    assert streaming_tab.report_files_table.item(1, 0).text() == "Nierozpoznany"
    assert streaming_tab.report_files_table.item(1, 0).background().color().name() == (
        "#c62828"
    )
    assert streaming_tab.add_report_file_button is streaming_tab.manual_add_report_button
    assert streaming_tab.add_report_file_button.text() == "Dodaj raport"
    assert streaming_tab.manual_calculate_reports_button.text() == "Przelicz raporty"
    assert streaming_tab.map_report_columns_button.text() == "Dopasuj kolumny"
    assert not streaming_tab.map_report_columns_button.isEnabled()
    assert streaming_tab.delete_report_file_button.text() == "Usuń"
    assert streaming_tab.show_report_trash_button.text() == "Kosz"
    assert streaming_tab.report_year_filter.currentData() == ""
    assert streaming_tab.report_files_summary_label.text() == (
        "Rozpoznane: 1   |   Nierozpoznane: 1"
    )

    streaming_tab.calculation_back_button.click()
    qapp.processEvents()

    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.mode_selection_page


def test_mapping_button_is_available_for_every_excel_report(
    streaming_tab,
    qapp,
):
    analyses = [
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2026" / "Rozpoznany.xlsx",
            recognized=True,
        ),
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2026" / "Nieznany.xlsx",
            recognized=False,
        ),
    ]
    streaming_tab._report_file_analyses = analyses
    streaming_tab.refresh_report_year_filter()
    streaming_tab.render_report_files()

    streaming_tab.report_files_table.selectRow(0)
    qapp.processEvents()
    assert streaming_tab.map_report_columns_button.isEnabled()

    streaming_tab.report_files_table.selectRow(1)
    qapp.processEvents()
    assert streaming_tab.map_report_columns_button.isEnabled()


def test_mapping_button_opens_configuration_inside_tab(
    streaming_tab,
    qapp,
):
    analysis = ReportFileAnalysis(
        path=PLATFORM_REPORTS_ROOT / "2026" / "Nieznany.xlsx",
        recognized=False,
    )
    streaming_tab._report_file_analyses = [analysis]
    streaming_tab.refresh_report_year_filter()
    streaming_tab.render_report_files()
    streaming_tab.report_files_table.selectRow(0)
    qapp.processEvents()

    with patch.object(
        streaming_tab.report_column_mapping_page,
        "configure_report",
    ) as configure_report:
        streaming_tab.map_report_columns_button.click()

    configure_report.assert_called_once_with(analysis.path)
    assert (
        streaming_tab.mode_stack.currentWidget()
        is streaming_tab.report_column_mapping_page
    )


def test_excel_picker_populates_field_and_returns_to_configuration(
    streaming_tab,
):
    report_path = PLATFORM_REPORTS_ROOT / "2026" / "Nieznany.xlsx"
    mapping_page = streaming_tab.report_column_mapping_page
    mapping_page.report_path = report_path

    with patch.object(
        streaming_tab.excel_cell_picker_page,
        "open_report",
    ) as open_report:
        mapping_page.cell_pick_requested.emit("isbn")

    open_report.assert_called_once_with(
        report_path,
        "ISBN",
        preferred_sheet=None,
        preferred_row=None,
    )
    assert (
        streaming_tab.mode_stack.currentWidget()
        is streaming_tab.excel_cell_picker_page
    )

    streaming_tab.excel_cell_picker_page.cell_selected.emit(
        "EAN Code",
        "Sprzedaż",
        4,
        2,
    )

    assert mapping_page.field_edits["isbn"].text() == "EAN Code"
    assert mapping_page.preferred_location() == ("Sprzedaż", 4)
    assert streaming_tab.mode_stack.currentWidget() is mapping_page


def test_saved_mapping_refreshes_report_list(streaming_tab):
    with patch.object(streaming_tab, "refresh_report_files") as refresh_files:
        streaming_tab.on_report_column_mapping_saved("report.xlsx")

    refresh_files.assert_called_once_with()
    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.report_files_page


def test_saved_mapping_can_move_report_to_year_detected_from_dates(streaming_tab):
    report_path = PLATFORM_REPORTS_ROOT / "2026" / "Storytel.xlsx"
    analysis = ReportFileAnalysis(
        path=report_path,
        recognized=True,
        platform_key="storytel",
        report_types=("quarterly",),
        content_years=(2025,),
        rows_count=62,
    )
    destination = PLATFORM_REPORTS_ROOT / "2025" / "Storytel.xlsx"

    with (
        patch("GUI.Tabs.StreamingTab.analyze_report_file", return_value=analysis),
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ),
        patch(
            "GUI.Tabs.StreamingTab.move_report_to_year",
            return_value=destination,
        ) as move_report,
        patch("GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information"),
    ):
        result = streaming_tab.correct_report_year_assignment(report_path)

    move_report.assert_called_once_with(report_path, 2025)
    assert result == destination
    assert streaming_tab.report_column_mapping_page.report_path == destination


def test_report_file_list_can_be_filtered_by_year(streaming_tab):
    analyses = [
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2025" / "Legimi.xlsx",
            recognized=True,
        ),
        ReportFileAnalysis(
            path=PLATFORM_REPORTS_ROOT / "2026" / "Storytel.xlsx",
            recognized=True,
        ),
    ]
    with patch(
        "GUI.Tabs.StreamingTab.scan_report_directory",
        return_value=analyses,
    ):
        streaming_tab.show_report_files_page()

    assert [
        streaming_tab.report_year_filter.itemData(index)
        for index in range(streaming_tab.report_year_filter.count())
    ] == ["", "2026", "2025"]

    streaming_tab.report_year_filter.setCurrentIndex(
        streaming_tab.report_year_filter.findData("2025")
    )

    assert streaming_tab.report_files_table.rowCount() == 1
    assert streaming_tab.report_files_table.item(0, 1).text() == str(
        Path("2025") / "Legimi.xlsx"
    )


def test_calculation_page_has_one_add_report_button(streaming_tab):
    with patch.object(
        streaming_tab, "open_manual_report_dialog"
    ) as open_dialog:
        streaming_tab.add_report_file_button.click()

    open_dialog.assert_called_once_with()
    assert streaming_tab.add_report_file_button is streaming_tab.manual_add_report_button


def test_selected_report_is_moved_to_trash(streaming_tab, qapp):
    analysis = ReportFileAnalysis(
        path=PLATFORM_REPORTS_ROOT / "2026" / "Legimi.xlsx",
        recognized=True,
    )
    streaming_tab._report_file_analyses = [analysis]
    streaming_tab.refresh_report_year_filter()
    streaming_tab.render_report_files()
    streaming_tab.report_files_table.selectRow(0)
    qapp.processEvents()

    with (
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ),
        patch("GUI.Tabs.StreamingTab.move_report_to_trash") as move_to_trash,
        patch.object(streaming_tab, "refresh_report_files") as refresh_files,
    ):
        streaming_tab.delete_report_file_button.click()

    move_to_trash.assert_called_once_with(analysis.path)
    refresh_files.assert_called_once_with()


def test_report_can_be_restored_from_trash(streaming_tab, qapp):
    entry = TrashedReport(
        path=PLATFORM_REPORTS_ROOT / ".Kosz" / "batch" / "2026" / "Legimi.xlsx",
        original_relative_path=Path("2026") / "Legimi.xlsx",
        deleted_at=datetime(2026, 8, 31, 12, 0),
    )
    with patch(
        "GUI.Tabs.StreamingTab.list_trashed_reports",
        return_value=[entry],
    ):
        streaming_tab.show_report_trash_page()

    assert streaming_tab.mode_stack.currentWidget() is streaming_tab.report_trash_page
    assert streaming_tab.report_trash_table.rowCount() == 1
    assert streaming_tab.report_trash_table.item(0, 1).text() == "2026"
    streaming_tab.report_trash_table.selectRow(0)
    qapp.processEvents()

    restored_path = PLATFORM_REPORTS_ROOT / "2026" / "Legimi.xlsx"
    with (
        patch(
            "GUI.Tabs.StreamingTab.restore_report_from_trash",
            return_value=restored_path,
        ) as restore_report,
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information"
        ),
        patch.object(streaming_tab, "refresh_report_trash") as refresh_trash,
    ):
        streaming_tab.restore_report_button.click()

    restore_report.assert_called_once_with(entry.path)
    refresh_trash.assert_called_once_with()


def test_report_can_be_permanently_deleted_with_imported_sqlite_rows(
    streaming_tab,
    qapp,
):
    entry = TrashedReport(
        path=PLATFORM_REPORTS_ROOT / ".Kosz" / "batch" / "2099" / "Usunięty.xlsx",
        original_relative_path=Path("2099") / "Usunięty.xlsx",
        deleted_at=datetime(2099, 8, 31, 12, 0),
    )
    with patch(
        "GUI.Tabs.StreamingTab.list_trashed_reports",
        return_value=[entry],
    ):
        streaming_tab.show_report_trash_page()
    streaming_tab.report_trash_table.selectRow(0)
    qapp.processEvents()

    deletion = ImportedReportDeletionResult(
        transaction_rows=12,
        monthly_rows=3,
        source_rows=1,
    )
    with (
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ),
        patch(
            "GUI.Tabs.StreamingTab.delete_imported_report_data",
            return_value=deletion,
        ) as delete_sqlite_rows,
        patch(
            "GUI.Tabs.StreamingTab.permanently_delete_trashed_report"
        ) as delete_file,
        patch(
            "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information"
        ) as information,
        patch.object(streaming_tab, "refresh_report_trash") as refresh_trash,
    ):
        streaming_tab.permanently_delete_report_button.click()

    delete_sqlite_rows.assert_called_once_with(2099, "Usunięty.xlsx")
    delete_file.assert_called_once_with(entry.path)
    assert "Transakcje: 12" in information.call_args.args[2]
    assert "Raporty miesięczne: 3" in information.call_args.args[2]
    assert "Rozliczenia kwartalne: 0" in information.call_args.args[2]
    refresh_trash.assert_called_once_with()


def _sample_report(
    title="Pierwsza książka",
    isbn="978-1",
    year=2026,
    client_name="Klient A",
    product_id=1,
):
    return BookReportSummary(
        year=year,
        product_id=product_id,
        title=title,
        isbn=isbn,
        client_name=client_name,
        total_net=30.0,
        total_gross=36.9,
        platforms_count=2,
        months_count=2,
        source_rows=5,
    )


def _sample_monthly_report(
    title="Pierwsza książka",
    isbn="978-1",
    year=2026,
    period="2026-07",
    client_name="Klient A",
    product_id=1,
):
    return MonthlyBookReportSummary(
        year=year,
        period=period,
        product_id=product_id,
        title=title,
        isbn=isbn,
        client_name=client_name,
        total_net=10.0,
        total_gross=12.3,
        platforms_count=1,
        source_rows=2,
    )


def _sample_quarterly_report():
    return QuarterlyBookReportSummary(
        settlement_id=1,
        year=2026,
        quarter=4,
        period="2026-Q4",
        period_start="2026-10-01",
        period_end="2026-12-31",
        platform_name="Storytel",
        product_id=1,
        title="Pierwsza książka",
        isbn="978-1",
        client_name="Klient A",
        quantity=17.0,
        total_net=25.0,
        total_gross=30.75,
        source_rows=1,
    )


def test_quarterly_overview_shows_exact_range_and_filters_it(streaming_tab):
    streaming_tab._overview_quarterly_reports = [_sample_quarterly_report()]
    streaming_tab.set_overview_report_view("quarterly")

    assert streaming_tab.overview_period_filter_label.text() == "Kwartał / zakres:"
    assert not streaming_tab.overview_reports_table.isColumnHidden(5)
    assert streaming_tab.overview_reports_table.item(0, 2).text() == (
        "2026-10-01 – 2026-12-31"
    )
    assert streaming_tab.overview_reports_table.item(0, 4).text() == "Storytel"
    assert streaming_tab.overview_reports_table.item(0, 5).text() == "17"

    streaming_tab.overview_period_filter.setText("Q4")
    streaming_tab.filter_overview_reports()
    assert not streaming_tab.overview_reports_table.isRowHidden(0)

    streaming_tab.overview_period_filter.setText("2025")
    streaming_tab.filter_overview_reports()
    assert streaming_tab.overview_reports_table.isRowHidden(0)


def test_overview_filters_reports_by_client_and_book(streaming_tab):
    reports = [
        _sample_monthly_report(),
        _sample_monthly_report(
            title="Druga książka",
            isbn="978-2",
            client_name="Inny klient",
            product_id=2,
        ),
    ]

    with (
        patch(
            "GUI.Tabs.StreamingTab.list_monthly_book_reports",
            return_value=reports,
        ),
        patch(
            "GUI.Tabs.StreamingTab.list_book_reports",
            return_value=[],
        ),
    ):
        streaming_tab.refresh_overview_reports()

    streaming_tab.overview_client_filter.setText("Klient A")
    streaming_tab.overview_book_filter.setText("pier")
    streaming_tab.overview_isbn_filter.setText("9781")
    streaming_tab.overview_period_filter.setText("2026-07")

    streaming_tab.filter_overview_reports()

    assert not streaming_tab.overview_reports_table.isRowHidden(0)
    assert streaming_tab.overview_reports_table.isRowHidden(1)


def test_overview_filters_reports_by_client_and_book(streaming_tab):
    reports = [
        _sample_monthly_report(
            title="Pierwsza książka",
            isbn="978-1",
            client_name="Klient A",
            product_id=1,
        ),
        _sample_monthly_report(
            title="Druga książka",
            isbn="978-2",
            client_name="Inny klient",
            product_id=2,
        ),
    ]

    with (
        patch(
            "GUI.Tabs.StreamingTab.list_monthly_book_reports",
            return_value=reports,
        ),
        patch(
            "GUI.Tabs.StreamingTab.list_book_reports",
            return_value=[],
        ),
    ):
        streaming_tab.refresh_overview_reports()

    streaming_tab.overview_client_filter.setText("Klient A")
    streaming_tab.overview_book_filter.setText("pier")
    streaming_tab.overview_isbn_filter.setText("9781")
    streaming_tab.overview_period_filter.setText("2026-07")

    streaming_tab.filter_overview_reports()

    assert streaming_tab.overview_reports_table.rowCount() == 2
    assert not streaming_tab.overview_reports_table.isRowHidden(0)
    assert streaming_tab.overview_reports_table.isRowHidden(1)

def _sample_transaction():
    return MonthlyReportTransaction(
        transaction_id=10,
        platform_name="Legimi",
        transaction_date="2026-07-15",
        title="Pierwsza książka",
        isbn="978-1",
        client_name="Klient A",
        net_amount=10.0,
        gross_amount=12.3,
        source_type="imported_report",
        source_file="Legimi.xlsx",
    )


@patch("GUI.Tabs.StreamingTab.MonthlyReportTransactionsDialog")
@patch("GUI.Tabs.StreamingTab.list_monthly_report_transactions")
def test_monthly_report_double_click_opens_transaction_list(
    mock_list_transactions,
    mock_dialog_class,
    streaming_tab,
):
    report = _sample_monthly_report()
    mock_list_transactions.return_value = [_sample_transaction()]
    streaming_tab._overview_monthly_reports = [report]
    streaming_tab._fill_overview_reports_table()

    item = streaming_tab.overview_reports_table.item(0, 0)
    streaming_tab.overview_reports_table.itemDoubleClicked.emit(item)

    mock_list_transactions.assert_called_once_with(report)
    mock_dialog_class.assert_called_once_with(
        report,
        mock_list_transactions.return_value,
        streaming_tab,
    )
    mock_dialog_class.return_value.exec.assert_called_once_with()


@patch("GUI.Tabs.StreamingTab.list_monthly_report_transactions", return_value=[])
def test_monthly_report_without_transactions_shows_information(
    mock_list_transactions,
    streaming_tab,
):
    report = _sample_monthly_report()
    streaming_tab._overview_monthly_reports = [report]
    streaming_tab._fill_overview_reports_table()

    with patch(
        "GUI.Tabs.StreamingTab.QtWidgets.QMessageBox.information"
    ) as information:
        item = streaming_tab.overview_reports_table.item(0, 0)
        streaming_tab.overview_reports_table.itemDoubleClicked.emit(item)

    mock_list_transactions.assert_called_once_with(report)
    assert information.call_args.args[2] == (
        "Brak informacji o transakcjach z tego miesiąca."
    )


@patch("GUI.Tabs.StreamingTab.ReportContentsDialog")
@patch("GUI.Tabs.StreamingTab.load_book_report_details")
def test_yearly_report_double_click_opens_months_for_each_platform(
    mock_load_details,
    mock_dialog_class,
    streaming_tab,
):
    report = _sample_report()
    details = BookReportDetails(
        report=report,
        entries=(
            BookReportEntry(
                platform_name="Legimi",
                period="2026-07",
                net_amount=10.0,
                gross_amount=12.3,
                source_rows=2,
            ),
            BookReportEntry(
                platform_name="Storytel",
                period="2026-07",
                net_amount=20.0,
                gross_amount=24.6,
                source_rows=3,
            ),
        ),
    )
    mock_load_details.return_value = details
    streaming_tab._overview_yearly_reports = [report]
    streaming_tab.set_overview_report_view("yearly")

    item = streaming_tab.overview_reports_table.item(0, 0)
    streaming_tab.overview_reports_table.itemDoubleClicked.emit(item)

    mock_load_details.assert_called_once_with(report)
    mock_dialog_class.assert_called_once_with(details, streaming_tab)
    mock_dialog_class.return_value.exec.assert_called_once_with()
