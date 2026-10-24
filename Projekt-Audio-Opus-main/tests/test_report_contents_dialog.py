import pytest
from PySide6 import QtWidgets

from GUI.Widgets.Dialogs.ReportContentsDialog import ReportContentsDialog
from platforms.report_viewer import (
    BookReportDetails,
    BookReportEntry,
    BookReportSummary,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_dialog_displays_book_from_all_platforms():
    report = BookReportSummary(
        year=2026,
        product_id=1,
        title="Pierwsza książka",
        isbn="978-1",
        client_name="Klient A",
        total_net=30.0,
        total_gross=36.9,
        platforms_count=2,
        months_count=2,
        source_rows=5,
    )
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
                period="2026-08",
                net_amount=20.0,
                gross_amount=24.6,
                source_rows=3,
            ),
        ),
    )

    dialog = ReportContentsDialog(details)

    assert dialog.windowTitle() == "Raport książki – Pierwsza książka"
    assert dialog.report_table.rowCount() == 2
    assert dialog.report_table.item(0, 0).text() == "Legimi"
    assert dialog.report_table.item(0, 1).text() == "2026-07"
    assert dialog.report_table.item(1, 0).text() == "Storytel"
    assert dialog.report_table.item(1, 4).text() == "3"
    assert "Platformy: 2" in dialog.summary_label.text()
    assert "Suma netto: 30.00" in dialog.summary_label.text()

    dialog.platform_filter.setCurrentIndex(
        dialog.platform_filter.findData("Storytel")
    )

    assert dialog.report_table.isRowHidden(0)
    assert not dialog.report_table.isRowHidden(1)
    assert "Platformy: 1" in dialog.summary_label.text()
    assert "Miesiące: 1" in dialog.summary_label.text()
    assert "Suma netto: 20.00" in dialog.summary_label.text()

    dialog.close()
