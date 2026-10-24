from PySide6 import QtWidgets

from GUI.Widgets.Buttons.Table.AddTableButton import AddTableButton
from GUI.Widgets.Buttons.Table.RemoveTableButton import RemoveTableButton
from GUI.Widgets.CrudTable.Table import Table


class CrudTable(QtWidgets.QWidget):
    def __init__(
            self,
            table_header: list[str],
            database_name: str,
            suggestions: dict[str, list[str]] = None,
            field_types: dict[str, type] = None,
    ):
        super().__init__()

        self.table = Table(table_header, database_name)

        self.add_button = AddTableButton(
            table_header[1:],
            database_name,
            self.table.refresh_table,
            suggestions,
            field_types
        )

        self.remove_button = RemoveTableButton(
            database_name,
            self.table,
            self.table.refresh_table
        )
        self.add_button.setText("+")
        self.remove_button.setText("-")
        self.add_button.setFixedSize(28, 28)
        self.remove_button.setFixedSize(28, 28)

        self.add_button.setProperty("role", "AddButton")
        self.remove_button.setProperty("role", "RemoveButton")

        buttons_layout = QtWidgets.QHBoxLayout()
        buttons_layout.addWidget(self.add_button)
        buttons_layout.addWidget(self.remove_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addLayout(buttons_layout)

    def search(self, text):
        self.table.search(text)