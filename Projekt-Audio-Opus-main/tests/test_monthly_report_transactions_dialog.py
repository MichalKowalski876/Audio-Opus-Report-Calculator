import pytest
from PySide6 import QtWidgets

from GUI.Widgets.Dialogs.MonthlyReportTransactionsDialog import (
    MonthlyReportTransactionsDialog,
)
from platforms.report_viewer import (
    MonthlyBookReportSummary,
    MonthlyReportTransaction,
)


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    yield app


def test_dialog_displays_monthly_transactions():
    report = MonthlyBookReportSummary(
        year=2026,
        period="2026-07",
        product_id=1,
        title="Pierwsza książka",
        isbn="978-1",
        client_name="Klient A",
        total_net=10.0,
        total_gross=12.3,
        platforms_count=1,
        source_rows=2,
    )
    transactions = [
        MonthlyReportTransaction(
            transaction_id=1,
            platform_name="Legimi",
            transaction_date="2026-07-15",
            title="Pierwsza książka",
            isbn="978-1",
            client_name="Klient A",
            net_amount=10.0,
            gross_amount=12.3,
            source_type="imported_report",
            source_file="Legimi.xlsx",
        ),
        MonthlyReportTransaction(
            transaction_id=2,
            platform_name="Storytel",
            transaction_date="2026-07-20",
            title="Pierwsza książka",
            isbn="978-1",
            client_name="Klient A",
            net_amount=20.0,
            gross_amount=24.6,
            source_type="imported_report",
            source_file="Storytel.xlsx",
        ),
    ]

    dialog = MonthlyReportTransactionsDialog(report, transactions)

    assert dialog.windowTitle() == "Transakcje raportu – Pierwsza książka"
    assert dialog.transactions_table.rowCount() == 2
    assert dialog.transactions_table.item(0, 0).text() == "2026-07-15"
    assert dialog.transactions_table.item(0, 1).text() == "Legimi"
    assert dialog.transactions_table.item(0, 5).text() == "10.00"
    assert dialog.transactions_table.item(0, 7).text() == "Legimi.xlsx"

    dialog.platform_filter.setCurrentIndex(
        dialog.platform_filter.findData("Storytel")
    )

    assert dialog.transactions_table.isRowHidden(0)
    assert not dialog.transactions_table.isRowHidden(1)
    assert "Transakcje: 1 z 2" in dialog.information_label.text()

    dialog.close()
