from PySide6 import QtCore, QtWidgets

from platforms.report_viewer import BookReportDetails


def _amount_text(value: float | None) -> str:
    if value is None:
        return "—"
    return f"{value:,.2f}".replace(",", " ")


class ReportContentsDialog(QtWidgets.QDialog):
    def __init__(self, details: BookReportDetails, parent=None):
        super().__init__(parent)

        self.details = details
        report = details.report
        self.setWindowTitle(f"Raport książki – {report.title}")
        self.resize(900, 600)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(f"{report.title} – {report.year}")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        information = QtWidgets.QLabel(
            f"ISBN: {report.isbn or '—'}    |    "
            f"Klient: {report.client_name or '—'}"
        )
        information.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(information)

        self.summary_label = QtWidgets.QLabel("")
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        platform_filter_layout = QtWidgets.QHBoxLayout()
        platform_filter_layout.addWidget(QtWidgets.QLabel("Platforma:"))
        self.platform_filter = QtWidgets.QComboBox()
        self.platform_filter.setMinimumWidth(190)
        self.platform_filter.addItem("Wszystkie platformy", "")
        platform_names = sorted(
            {
                entry.platform_name
                for entry in details.entries
                if entry.platform_name
            },
            key=str.casefold,
        )
        for platform_name in platform_names:
            self.platform_filter.addItem(platform_name, platform_name)
        platform_filter_layout.addWidget(self.platform_filter)
        platform_filter_layout.addStretch()
        layout.addLayout(platform_filter_layout)

        self.report_table = QtWidgets.QTableWidget(len(details.entries), 5)
        self.report_table.setHorizontalHeaderLabels(
            ["Platforma", "Miesiąc", "Netto", "Brutto", "Pozycje źródłowe"]
        )
        self.report_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.report_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.report_table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.report_table.setAlternatingRowColors(True)
        self.report_table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.report_table.verticalHeader().setVisible(False)

        for row_index, entry in enumerate(details.entries):
            values = (
                entry.platform_name,
                entry.period,
                _amount_text(entry.net_amount),
                _amount_text(entry.gross_amount),
                entry.source_rows,
            )
            for column_index, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if column_index in (1, 2, 3, 4):
                    item.setTextAlignment(
                        QtCore.Qt.AlignmentFlag.AlignCenter
                    )
                self.report_table.setItem(row_index, column_index, item)

        header = self.report_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        for column in range(1, 5):
            header.setSectionResizeMode(
                column,
                QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
            )
        layout.addWidget(self.report_table, 1)

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
        visible_entries = []
        for row, entry in enumerate(self.details.entries):
            visible = not selected_platform or entry.platform_name == selected_platform
            self.report_table.setRowHidden(row, not visible)
            if visible:
                visible_entries.append(entry)

        platform_count = len(
            {entry.platform_name for entry in visible_entries if entry.platform_name}
        )
        month_count = len(
            {entry.period for entry in visible_entries if entry.period}
        )
        total_net = round(sum(entry.net_amount for entry in visible_entries), 2)
        gross_values = [
            entry.gross_amount
            for entry in visible_entries
            if entry.gross_amount is not None
        ]
        total_gross = round(sum(gross_values), 2) if gross_values else None
        self.summary_label.setText(
            f"Platformy: {platform_count}    |    "
            f"Miesiące: {month_count}    |    "
            f"Suma netto: {_amount_text(total_net)}    |    "
            f"Suma brutto: {_amount_text(total_gross)}"
        )
