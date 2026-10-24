from openpyxl import Workbook
from PySide6.QtWidgets import QApplication
import pytest

from GUI.Widgets.Reports import ExcelCellPickerPanel, ReportColumnMappingPanel
from platforms.column_mappings import load_platform_column_mappings
from platforms.xlsx_reports import QUARTERLY_REPORT


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def report_path(tmp_path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sprzedaż"
    sheet.append(
        ["Work Name", "EAN Code", "Statement Cycle", "Payable To Us", "Units"]
    )
    sheet.append(["Nowa książka", "9781234567890", "2026-07", "19,99", 7])
    path = tmp_path / "Nowa platforma.xlsx"
    workbook.save(path)
    return path


def test_panel_saves_manually_entered_column_names(report_path, tmp_path):
    database_path = tmp_path / "db.sqlite"
    panel = ReportColumnMappingPanel(database_path=database_path)
    saved_paths = []
    panel.mapping_saved.connect(saved_paths.append)
    panel.configure_report(report_path)
    panel.field_edits["title"].setText("Work Name")
    panel.field_edits["isbn"].setText("EAN Code")
    panel.field_edits["date_or_period"].setText("Statement Cycle")
    panel.field_edits["net"].setText("Payable To Us")
    panel.report_type_combo.setCurrentIndex(1)

    panel.save_configuration()

    mappings = load_platform_column_mappings(
        "nowa platforma",
        database_path=database_path,
    )
    assert saved_paths == [str(report_path)]
    assert len(mappings) == 1
    mapping = next(iter(mappings.values()))
    assert mapping.report_type == "monthly"
    assert mapping.columns == {"title": 0, "isbn": 1, "period": 2, "net": 3}
    panel.close()


def test_panel_saves_quarterly_mapping_with_quantity(report_path, tmp_path):
    database_path = tmp_path / "db.sqlite"
    panel = ReportColumnMappingPanel(database_path=database_path)
    panel.configure_report(report_path)
    panel.field_edits["title"].setText("Work Name")
    panel.field_edits["isbn"].setText("EAN Code")
    panel.field_edits["date_or_period"].setText("Statement Cycle")
    panel.field_edits["quantity"].setText("Units")
    panel.field_edits["net"].setText("Payable To Us")
    panel.report_type_combo.setCurrentIndex(
        panel.report_type_combo.findData(QUARTERLY_REPORT)
    )

    panel.save_configuration()

    mapping = next(
        iter(
            load_platform_column_mappings(
                "nowa platforma", database_path=database_path
            ).values()
        )
    )
    assert mapping.report_type == QUARTERLY_REPORT
    assert mapping.columns == {
        "title": 0,
        "isbn": 1,
        "period": 2,
        "net": 3,
        "quantity": 4,
    }
    panel.close()


def test_cell_picker_returns_clicked_cell_value(report_path, qapp):
    panel = ExcelCellPickerPanel()
    selected = []
    panel.cell_selected.connect(lambda *values: selected.append(values))
    panel.open_report(report_path, "Nazwa książki")
    qapp.processEvents()

    panel.table.cellClicked.emit(0, 0)

    assert selected == [("Work Name", "Sprzedaż", 1, 1)]
    panel.close()


def test_cell_picker_fits_column_to_longest_value(tmp_path, qapp):
    workbook = Workbook()
    sheet = workbook.active
    longest_value = "Bardzo długa nazwa kolumny raportu platformy Voices"
    sheet.append(["Nagłówek"])
    sheet.append([longest_value])
    report_path = tmp_path / "Voices.xlsx"
    workbook.save(report_path)

    panel = ExcelCellPickerPanel()
    panel.open_report(report_path, "Nazwa książki")
    qapp.processEvents()

    text_width = panel.table.fontMetrics().horizontalAdvance(longest_value)
    assert panel.table.columnWidth(0) >= text_width
    panel.close()


def test_selected_cell_populates_requested_field(report_path, tmp_path):
    panel = ReportColumnMappingPanel(database_path=tmp_path / "db.sqlite")
    panel.configure_report(report_path)

    accepted = panel.set_field_from_cell(
        "isbn",
        "EAN Code",
        "Sprzedaż",
        1,
        2,
    )

    assert accepted is True
    assert panel.field_edits["isbn"].text() == "EAN Code"
    assert panel.preferred_location() == ("Sprzedaż", 1)
    assert panel.selected_column_indexes["isbn"] == 1
    panel.close()


def test_different_header_rows_are_rejected_only_when_saving(
    report_path,
    tmp_path,
):
    database_path = tmp_path / "db.sqlite"
    panel = ReportColumnMappingPanel(database_path=database_path)
    saved_paths = []
    panel.mapping_saved.connect(saved_paths.append)
    panel.configure_report(report_path)

    assert panel.set_field_from_cell(
        "title", "Work Name", "Sprzedaż", 1, 1
    )
    assert panel.set_field_from_cell(
        "isbn", "9781234567890", "Sprzedaż", 2, 2
    )
    assert panel.set_field_from_cell(
        "date_or_period", "Statement Cycle", "Sprzedaż", 1, 3
    )
    assert panel.set_field_from_cell(
        "net", "Payable To Us", "Sprzedaż", 1, 4
    )

    assert panel.status_label.text() == ""
    assert panel.field_edits["isbn"].text() == "9781234567890"

    panel.save_configuration()

    assert saved_paths == []
    assert "jednego wiersza nagłówków" in panel.status_label.text()
    assert "wiersz 1" in panel.status_label.text()
    assert "wiersz 2" in panel.status_label.text()

    assert panel.set_field_from_cell(
        "isbn", "EAN Code", "Sprzedaż", 1, 2
    )
    panel.save_configuration()

    assert saved_paths == [str(report_path)]
    assert panel.status_label.text() == "Konfiguracja została zapisana."
    panel.close()


def test_manual_edit_forgets_previous_cell_location(report_path, tmp_path):
    panel = ReportColumnMappingPanel(database_path=tmp_path / "db.sqlite")
    panel.configure_report(report_path)
    panel.set_field_from_cell(
        "isbn", "9781234567890", "Sprzedaż", 2, 2
    )

    panel.field_edits["isbn"].setText("EAN Code")
    panel.field_edits["isbn"].textEdited.emit("EAN Code")

    assert "isbn" not in panel.selected_column_indexes
    assert "isbn" not in panel.selected_cell_locations
    assert panel.preferred_location() == (None, None)
    assert "odnaleziony" in panel.header_location_label.text()
    panel.close()
