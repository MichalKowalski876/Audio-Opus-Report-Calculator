from PySide6 import QtWidgets

from GUI.Widgets.Buttons.Help.HelpButton import HelpButton
from GUI.Widgets.CrudList.CrudClientList import CrudClientList


class ClientsTab(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.list = CrudClientList("clients")

        self.list.list.selected.connect(
            self.on_client_selected
        )

        main_layout = QtWidgets.QVBoxLayout(self)

        header_layout = QtWidgets.QHBoxLayout()

        header_layout.addStretch()

        help_button = HelpButton("clients", "Klienci")
        header_layout.addWidget(help_button)

        main_layout.addLayout(header_layout)

        content_layout = QtWidgets.QHBoxLayout()
        content_layout.addWidget(self.list)

        main_layout.addLayout(content_layout)

    def reload(self):
        """Przeładowuje dane zakładki (po wczytaniu kopii bazy)."""
        self.list.reload()

    def on_client_selected(self, client):
        client_id = client["id"]

    def add_client(self):
        if hasattr(self.list, 'add_item'):
            self.list.add_item()
        else:
            add_button = getattr(self.list, 'add_button', None)
            if add_button is not None:
                add_button.click()