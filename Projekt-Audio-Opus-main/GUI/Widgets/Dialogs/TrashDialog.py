from PySide6 import QtCore, QtWidgets

from core import database_controller
from GUI.Widgets.confirm import confirm_yes_no


class TrashDialog(QtWidgets.QDialog):
    """Kosz dla jednej bazy danych (klienci, produkty...).

    Pozycje usuniete przez database_controller.item_remove nie znikaja od
    razu na trwale - trafiaja tutaj, skad mozna je przywrocic albo usunac
    bezpowrotnie.
    """

    def __init__(self, db_name: str, title: str, label_for_item, parent=None):
        super().__init__(parent)

        self.db_name = db_name
        self.label_for_item = label_for_item

        self.setWindowTitle(title)
        self.resize(520, 420)

        info = QtWidgets.QLabel(
            "Usunięte pozycje czekają tutaj, dopóki ich nie przywrócisz "
            "albo nie usuniesz trwale."
        )
        info.setWordWrap(True)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.itemSelectionChanged.connect(self._update_buttons)

        self.restore_button = QtWidgets.QPushButton("Przywróć")
        self.restore_button.setEnabled(False)
        self.restore_button.clicked.connect(self._restore_selected)

        self.purge_button = QtWidgets.QPushButton("Usuń trwale")
        self.purge_button.setEnabled(False)
        self.purge_button.clicked.connect(self._purge_selected)

        self.purge_all_button = QtWidgets.QPushButton("Usuń wszystko z kosza")
        self.purge_all_button.setEnabled(False)
        self.purge_all_button.clicked.connect(self._purge_all)

        close_button = QtWidgets.QPushButton("Zamknij")
        close_button.clicked.connect(self.accept)

        actions_layout = QtWidgets.QHBoxLayout()
        actions_layout.addWidget(self.restore_button)
        actions_layout.addWidget(self.purge_button)
        actions_layout.addWidget(self.purge_all_button)
        actions_layout.addStretch()
        actions_layout.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.list_widget, 1)
        layout.addLayout(actions_layout)

        self.refresh()

    def refresh(self):
        self.list_widget.clear()

        trashed_items = database_controller.list_trash(self.db_name)

        if not trashed_items:
            placeholder = QtWidgets.QListWidgetItem("Kosz jest pusty.")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self.list_widget.addItem(placeholder)
            self._update_buttons()
            return

        for item in trashed_items:
            label = self.label_for_item(item)
            deleted_at = item.get("_deleted_at")

            if deleted_at:
                label += f"   ·   usunięto {deleted_at}"

            list_item = QtWidgets.QListWidgetItem(label)
            list_item.setData(
                QtCore.Qt.ItemDataRole.UserRole,
                item,
            )
            self.list_widget.addItem(list_item)

        self._update_buttons()

    def _selected_item_id(self):
        current = self.list_widget.currentItem()

        if current is None:
            return None

        data = current.data(QtCore.Qt.ItemDataRole.UserRole)

        if not data:
            return None

        return data.get("id")

    def _update_buttons(self):
        has_selection = self._selected_item_id() is not None

        has_trash_items = bool(
            database_controller.list_trash(self.db_name)
        )

        self.restore_button.setEnabled(has_selection)
        self.purge_button.setEnabled(has_selection)
        self.purge_all_button.setEnabled(has_trash_items)

    def _restore_selected(self):
        item_id = self._selected_item_id()

        if item_id is None:
            return

        database_controller.item_restore(
            item_id,
            self.db_name,
        )

        self.refresh()

    def _purge_selected(self):
        item_id = self._selected_item_id()

        if item_id is None:
            return

        confirmed = confirm_yes_no(
            self,
            "Usuń trwale",
            "Tej operacji nie można cofnąć. Czy na pewno chcesz usunąć "
            "tę pozycję na stałe?",
        )

        if not confirmed:
            return

        database_controller.item_purge(
            item_id,
            self.db_name,
        )

        self.refresh()

    def _purge_all(self):
        trashed_items = database_controller.list_trash(self.db_name)

        if not trashed_items:
            return

        count = len(trashed_items)

        confirmed = confirm_yes_no(
            self,
            "Usuń wszystko z kosza",
            (
                "Tej operacji nie można cofnąć. Czy na pewno chcesz trwale "
                f"usunąć wszystkie elementy z kosza ({count})?"
            ),
        )

        if not confirmed:
            return

        database_controller.item_purge_all(self.db_name)

        self.refresh()