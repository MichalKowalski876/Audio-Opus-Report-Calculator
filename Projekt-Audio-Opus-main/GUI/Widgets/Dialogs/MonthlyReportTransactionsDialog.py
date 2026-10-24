from PySide6 import QtCore, QtWidgets

from platforms.report_viewer import (
    MonthlyBookReportSummary,
    MonthlyReportTransaction,
)


def _amount_text(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ")


def _source_text(transaction: MonthlyReportTransaction) -> str:
    if transaction.source_file:
        return transaction.source_file
    if transaction.source_type == "imported_report":
        return "Raport platformy"
    return "—"


class MonthlyReportTransactionsDialog(QtWidgets.QDialog):
    def __init__(
        self,
        report: MonthlyBookReportSummary,
        transactions: list[MonthlyReportTransaction],
        parent=None,
    ):
        super().__init__(parent)

        self.report = report
        self.transactions = transactions
        self.setWindowTitle(f"Transakcje raportu – {report.title}")
        self.resize(1150, 620)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(f"{report.title} – {report.period}")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        self.information_label = QtWidgets.QLabel("")
        self.information_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(self.information_label)

        platform_filter_layout = QtWidgets.QHBoxLayout()
        platform_filter_layout.addWidget(QtWidgets.QLabel("Platforma:"))
        self.platform_filter = QtWidgets.QComboBox()
        self.platform_filter.setMinimumWidth(190)
        self.platform_filter.addItem("Wszystkie platformy", "")
        platform_names = sorted(
            {
                transaction.platform_name
                for transaction in transactions
                if transaction.platform_name
            },
            key=str.casefold,
        )
        for platform_name in platform_names:
            self.platform_filter.addItem(platform_name, platform_name)
        platform_filter_layout.addWidget(self.platform_filter)
        platform_filter_layout.addStretch()
        layout.addLayout(platform_filter_layout)

        self.transactions_table = QtWidgets.QTableWidget(len(transactions), 8)
        self.transactions_table.setHorizontalHeaderLabels(
            [
                "Data",
                "Platforma",
                "Nazwa książki",
                "ISBN",
                "Klient",
                "Netto",
                "Brutto",
                "Źródło",
            ]
        )
        self.transactions_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.transactions_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.transactions_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.transactions_table.setAlternatingRowColors(True)
        self.transactions_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.transactions_table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.transactions_table.verticalHeader().setVisible(False)

        for row, transaction in enumerate(transactions):
            values = (
                transaction.transaction_date,
                transaction.platform_name,
                transaction.title,
                transaction.isbn,
                transaction.client_name,
                _amount_text(transaction.net_amount),
                _amount_text(transaction.gross_amount),
                _source_text(transaction),
            )
            for column, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if column in (0, 5, 6):
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                self.transactions_table.setItem(row, column, item)

        header = self.transactions_table.horizontalHeader()
        header.setSectionResizeMode(
            2, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        for column in (0, 1, 3, 5, 6):
            header.setSectionResizeMode(
                column, QtWidgets.QHeaderView.ResizeMode.ResizeToContents
            )
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QtWidgets.QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.transactions_table, 1)

        self.platform_filter.currentIndexChanged.connect(
            self.filter_platform
        )
        self.filter_platform()

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        ).setText("Zamknij")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def filter_platform(self, *_):
        selected_platform = str(self.platform_filter.currentData() or "")
        visible_count = 0
        for row, transaction in enumerate(self.transactions):
            visible = (
                not selected_platform
                or transaction.platform_name == selected_platform
            )
            self.transactions_table.setRowHidden(row, not visible)
            visible_count += int(visible)

        count_text = str(visible_count)
        if selected_platform:
            count_text = f"{visible_count} z {len(self.transactions)}"
        self.information_label.setText(
            f"ISBN: {self.report.isbn or '—'}    |    "
            f"Klient: {self.report.client_name or '—'}    |    "
            f"Transakcje: {count_text}"
        )
