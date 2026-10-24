from PySide6 import QtWidgets

from core import database_controller
from GUI.Widgets.Buttons import db_display
from GUI.Widgets.confirm import confirm_yes_no


class RemoveTableButton(QtWidgets.QPushButton):
    def __init__(self, database_name: str, table, refresh_callback):
        super().__init__(
            f"Usuń {db_display.accusative_singular(database_name)}"
        )

        self.database_name = database_name
        self.table = table
        self.refresh_callback = refresh_callback

        self.clicked.connect(self.remove_item)

    def remove_item(self):
        if self.table.item_id is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Uwaga",
                "Najpierw wybierz wiersz."
            )
            return

        if self.database_name == "products":
            clients = database_controller.load_database("clients")

            for client in clients:
                if self.table.item_id in client.get("products", []):
                    QtWidgets.QMessageBox.warning(
                        self,
                        "Uwaga",
                        "Ten produkt jest przypisany do klienta.\nUsuń go od wszystkich klientów przed usunięciem."
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
            self.table.item_id,
            self.database_name
        )

        self.table.item_id = None
        self.refresh_callback()
        QtWidgets.QMessageBox.information(
            self,
            "Sukces",
            "Pozycja została usunięta."
        )

