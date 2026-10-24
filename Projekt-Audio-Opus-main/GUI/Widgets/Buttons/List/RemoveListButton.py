from PySide6 import QtWidgets

from core import database_controller
from GUI.Widgets.Buttons import db_display
from GUI.Widgets.confirm import confirm_yes_no


class RemoveListButton(QtWidgets.QPushButton):
    def __init__(self, database_name: str, list, refresh_callback):
        super().__init__(
            f"Usuń {db_display.accusative_singular(database_name)}"
        )

        self.database_name = database_name
        self.list = list
        self.refresh_callback = refresh_callback

        self.clicked.connect(self.remove_item)

    def remove_item(self):
        if self.list.item_id is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Uwaga",
                "Wybierz wiersz najpierw."
            )
            return

        confirmed = confirm_yes_no(
            self,
            "Potwierdzenie usunięcia",
            "Czy na pewno chcesz usunąć wybraną pozycję z "
            f"{db_display.genitive_plural(self.database_name)}?",
        )

        if not confirmed:
            return

        database_controller.item_remove(
            self.list.item_id,
            self.database_name
        )

        self.list.item_id = None
        self.refresh_callback()
        QtWidgets.QMessageBox.information(
            self,
            "Sukces",
            "Pozycja została usunięta."
        )