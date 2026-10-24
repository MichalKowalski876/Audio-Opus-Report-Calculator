from datetime import datetime

from PySide6 import QtWidgets

from core import database_controller
from GUI.Widgets.Buttons import db_display
from GUI.Widgets.Dialogs.EditClientDialog import EditClientDialog


class AddListButton(QtWidgets.QPushButton):
    def __init__(
        self,
        database_name: str,
        refresh_callback,
    ):
        super().__init__(
            f"Dodaj {db_display.accusative_singular(database_name)}"
        )

        self.database_name = database_name
        self.refresh_callback = refresh_callback

        self.clicked.connect(
            self.add_button_logic
        )

    def add_button_logic(self):
        if self.database_name == "clients":
            self.open_add_client_dialog()
            return

        new_item = {
            "name": "Nowy element",
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        database_controller.item_add(
            new_item,
            self.database_name,
        )

        self.refresh_callback()

    def open_add_client_dialog(self):
        new_client = {
            "name": "",
            "email": "",
            "products": [],
            "created_at": datetime.now().isoformat(timespec="seconds"),
        }

        dialog = EditClientDialog(
            new_client,
            self.refresh_callback,
            self.window(),
            is_new=True,
        )
        dialog.exec()
