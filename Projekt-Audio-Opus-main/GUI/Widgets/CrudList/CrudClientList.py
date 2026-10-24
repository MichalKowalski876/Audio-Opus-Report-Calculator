from PySide6 import QtCore, QtWidgets, QtGui

from core import database_controller, paths
from GUI.Widgets.Settings.ShortcutManager import ShortcutManager
from GUI.Widgets.Buttons.List.EditItemListButton import EditItemListButton
from GUI.Widgets.Buttons.List.AddListButton import AddListButton
from GUI.Widgets.Buttons.List.RemoveListButton import RemoveListButton
from GUI.Widgets.CrudList.List import List
from GUI.Widgets.Dialogs.EditClientDialog import EditClientDialog
from GUI.Widgets.Dialogs.TrashDialog import TrashDialog
from GUI.Widgets.Items.BookItem import BookItem
from GUI.Widgets.ScrollAreas.ZoomableScrollArea import ZoomableScrollArea


class CrudClientList(QtWidgets.QWidget):
    def __init__(self, database_name: str):
        super().__init__()

        self.font_size = 10
        self.min_font_size = 8
        self.max_font_size = 40

        self.database_name = database_name
        self.current_client = None

        self.list = List(database_name)
        self.list.label.setText("Klienci")

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Szukaj klienta...")
        self.search_input.textChanged.connect(self.list.search)

        search_sequence = ShortcutManager().get_shortcut("search_focus")
        self.search_shortcut = QtGui.QShortcut(
            search_sequence,
            self,
        )
        self.search_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.search_shortcut.activated.connect(
            self._focus_client_search
        )

        delete_shortcut = QtGui.QShortcut(QtCore.Qt.Key_Delete, self)
        delete_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        delete_shortcut.activated.connect(self._remove_selected_client_with_delete)

        self.add_button = AddListButton(
            database_name,
            self.list.refresh_list,
        )
        icon = QtGui.QIcon(
            paths.resource_path("Assets", "placeholders", "add_client.png")
        )

        self.add_button.setText("")
        self.add_button.setIcon(icon)
        self.add_button.setIconSize(QtCore.QSize(18, 18))
        self.add_button.setToolTip("Dodaj klienta")

        self.remove_button = RemoveListButton(
            database_name,
            self.list,
            self.list.refresh_list,
        )

        self.remove_button.setText("")
        self.remove_button.setIcon(
            QtGui.QIcon(
                paths.resource_path(
                    "Assets",
                    "placeholders",
                    "remove_client.png",
                )
            )
        )
        self.remove_button.setIconSize(
            QtCore.QSize(18, 18)
        )
        self.remove_button.setToolTip("Usuń klienta")

        self.trash_button = QtWidgets.QPushButton("Kosz")
        self.trash_button.setToolTip("Pokaż usuniętych klientów")
        self.trash_button.clicked.connect(self.open_trash)

        self.setup_left_panel()
        self.setup_details_panel()
        self.setup_products_panel()
        self.setup_main_layout()

        self.list.selected.connect(
            self.on_selected_item
        )

        self._connect_double_click_signal()

    def _connect_double_click_signal(self):
        signals_to_check = [
            "double_clicked",
            "doubleClicked",
            "itemDoubleClicked",
            "item_double_clicked"
        ]

        for sig in signals_to_check:
            if hasattr(self.list, sig):
                getattr(self.list, sig).connect(lambda *_: self.open_edit_window())
                return

        for sub_attr in ["list", "list_widget", "items_list"]:
            inner_obj = getattr(self.list, sub_attr, None)
            if inner_obj is not None:
                for sig in signals_to_check:
                    if hasattr(inner_obj, sig):
                        getattr(inner_obj, sig).connect(lambda *_: self.open_edit_window())
                        return

    def _remove_selected_client_with_delete(self):
        if self.search_input.hasFocus():
            return
        if self.list.list.hasFocus():
            self.remove_button.remove_item()

    def _focus_client_search(self):
        if not self.isVisible():
            return
        self.search_input.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.search_input.selectAll()

    def setup_left_panel(self):
        self.left_panel = QtWidgets.QWidget()
        self.left_panel.setFixedWidth(300)

        left_layout = QtWidgets.QVBoxLayout(
            self.left_panel
        )
        left_layout.setContentsMargins(
            8, 8, 12, 8
        )
        left_layout.setSpacing(6)

        self.list.label.hide()
        self.list.setFixedWidth(300)

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.setContentsMargins(
            4, 0, 4, 0
        )
        header_layout.setSpacing(8)

        clients_label = QtWidgets.QLabel(
            "Klienci"
        )

        self.add_button.setFixedSize(
            28, 28
        )
        self.remove_button.setFixedSize(
            28, 28
        )

        self.add_button.setProperty(
            "role",
            "AddButton"
        )
        self.remove_button.setProperty(
            "role",
            "RemoveButton"
        )

        header_layout.addWidget(
            clients_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.trash_button
        )
        header_layout.addWidget(
            self.add_button
        )
        header_layout.addWidget(
            self.remove_button
        )

        header_line = QtWidgets.QFrame()
        header_line.setFrameShape(
            QtWidgets.QFrame.Shape.HLine
        )
        header_line.setFrameShadow(
            QtWidgets.QFrame.Shadow.Sunken
        )

        left_layout.addLayout(
            header_layout
        )
        left_layout.addWidget(
            header_line
        )

        left_layout.addWidget(
            self.search_input
        )
        left_layout.addWidget(
            self.list,
            1
        )

        self.left_separator = QtWidgets.QFrame()
        self.left_separator.setFrameShape(
            QtWidgets.QFrame.Shape.VLine
        )
        self.left_separator.setFrameShadow(
            QtWidgets.QFrame.Shadow.Sunken
        )
        self.left_separator.setFixedWidth(2)

    def setup_details_panel(self):
        self.details = QtWidgets.QWidget()

        details_layout = QtWidgets.QVBoxLayout(
            self.details
        )
        details_layout.setContentsMargins(
            20, 8, 20, 8
        )
        details_layout.setSpacing(12)

        self.details_title = QtWidgets.QLabel(
            "Szczegóły klienta"
        )
        self.details_title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        title_line = QtWidgets.QFrame()
        title_line.setFrameShape(
            QtWidgets.QFrame.Shape.HLine
        )
        title_line.setFrameShadow(
            QtWidgets.QFrame.Shadow.Sunken
        )

        details_layout.addWidget(
            self.details_title
        )
        details_layout.addWidget(
            title_line
        )

        self.id_label = QtWidgets.QLabel()
        self.id_label.hide()

        self.name_label = QtWidgets.QLabel("-")
        self.email_label = QtWidgets.QLabel("-")
        self.books_count_label = QtWidgets.QLabel("0")

        self.name_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.email_label.setTextInteractionFlags(
            QtCore.Qt.TextInteractionFlag.TextSelectableByMouse
        )

        info_layout = QtWidgets.QGridLayout()
        info_layout.setHorizontalSpacing(8)
        info_layout.setVerticalSpacing(4)

        info_layout.setColumnStretch(0, 1)
        info_layout.setColumnStretch(1, 0)
        info_layout.setColumnStretch(2, 0)
        info_layout.setColumnStretch(3, 1)

        name_title = QtWidgets.QLabel(
            "Nazwa:"
        )
        email_title = QtWidgets.QLabel(
            "E-mail:"
        )
        books_title = QtWidgets.QLabel(
            "Liczba książek:"
        )

        name_title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
        )
        email_title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
        )
        books_title.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignRight
        )

        info_layout.addWidget(
            name_title,
            0,
            1
        )
        info_layout.addWidget(
            self.name_label,
            0,
            2
        )

        info_layout.addWidget(
            email_title,
            1,
            1
        )
        info_layout.addWidget(
            self.email_label,
            1,
            2
        )

        info_layout.addWidget(
            books_title,
            2,
            1
        )
        info_layout.addWidget(
            self.books_count_label,
            2,
            2
        )

        self.edit_button = EditItemListButton()
        self.edit_button.setText("Edytuj")
        self.edit_button.setFixedSize(
            130,
            38
        )
        self.edit_button.hide()

        self.edit_button.setProperty(
            "role",
            "EditButton"
        )

        self.edit_button.selected.connect(
            self.open_edit_window
        )

        client_row_layout = QtWidgets.QHBoxLayout()
        client_row_layout.setContentsMargins(
            0, 4, 0, 4
        )

        client_row_layout.addStretch(1)
        client_row_layout.addLayout(
            info_layout
        )
        client_row_layout.addSpacing(35)
        client_row_layout.addWidget(
            self.edit_button,
            alignment=QtCore.Qt.AlignmentFlag.AlignTop,
        )
        client_row_layout.addStretch(1)

        details_layout.addLayout(
            client_row_layout
        )

    def setup_products_panel(self):
        self.products_panel = QtWidgets.QWidget()

        self.products_panel.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        products_layout = QtWidgets.QVBoxLayout(
            self.products_panel
        )
        products_layout.setContentsMargins(
            20, 0, 20, 16
        )
        products_layout.setSpacing(8)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(
            QtWidgets.QFrame.Shape.HLine
        )
        separator.setFrameShadow(
            QtWidgets.QFrame.Shadow.Sunken
        )

        self.products_label = QtWidgets.QLabel(
            "Książki"
        )
        self.products_label.setProperty(
            "role",
            "SectionTitle"
        )
        self.products_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        self.products_container = QtWidgets.QWidget()

        self.products_container_layout = (
            QtWidgets.QVBoxLayout(
                self.products_container
            )
        )
        self.products_container_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.products_container_layout.setSpacing(4)
        self.products_container_layout.addStretch()

        self.products_scroll = ZoomableScrollArea()
        self.products_scroll.setWidgetResizable(
            True
        )
        self.products_scroll.setFrameShape(
            QtWidgets.QFrame.Shape.NoFrame
        )
        self.products_scroll.setWidget(
            self.products_container
        )

        self.products_scroll.zoom_requested.connect(
            self.on_zoom_requested
        )

        products_layout.addWidget(
            separator
        )
        products_layout.addWidget(
            self.products_label
        )
        products_layout.addWidget(
            self.products_scroll,
            1
        )

    def setup_main_layout(self):
        main_layout = QtWidgets.QHBoxLayout(
            self
        )
        main_layout.setContentsMargins(
            12, 12, 12, 12
        )
        main_layout.setSpacing(8)

        self.right_panel = QtWidgets.QWidget()

        right_layout = QtWidgets.QVBoxLayout(
            self.right_panel
        )
        right_layout.setContentsMargins(
            0, 0, 0, 0
        )
        right_layout.setSpacing(0)

        right_layout.addWidget(
            self.details
        )
        right_layout.addWidget(
            self.products_panel,
            1
        )

        main_layout.addWidget(
            self.left_panel
        )
        main_layout.addWidget(
            self.left_separator
        )
        main_layout.addWidget(
            self.right_panel,
            1
        )

    def on_selected_item(self, data: dict):
        self.current_client = data
        self.edit_button.show()

        self.id_label.setText(
            str(data.get("id", ""))
        )

        self.name_label.setText(
            str(data.get("name") or "-")
        )

        self.email_label.setText(
            str(data.get("email") or "-")
        )

        self.books_count_label.setText(
            str(
                len(
                    data.get(
                        "products",
                        []
                    )
                )
            )
        )

        self.refresh_products(
            data
        )

    def refresh_products(self, client_data: dict):
        while (
                self.products_container_layout.count()
                > 1
        ):
            item = (
                self.products_container_layout
                .takeAt(0)
            )

            if item.widget():
                item.widget().deleteLater()

        all_products = (
            database_controller.load_database(
                "products"
            )
        )

        products_by_id = {
            str(product.get("id")): product
            for product in all_products
        }

        client_products = []

        for product_id in client_data.get(
                "products",
                []
        ):
            product = products_by_id.get(
                str(product_id)
            )

            if product is not None:
                client_products.append(
                    product
                )

        client_products.sort(
            key=lambda product: str(
                product.get("title") or ""
            ).lower()
        )

        if not client_products:
            label = QtWidgets.QLabel(
                "Brak przypisanych książek"
            )
            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter
            )

            self.products_container_layout.insertWidget(
                0,
                label
            )
            return

        for product in client_products:
            book_item = BookItem(
                product
            )
            book_item.set_font_size(
                self.font_size
            )

            self.products_container_layout.insertWidget(
                self.products_container_layout.count() - 1,
                book_item
            )

    def reload(self):
        """Przeładowuje listę klientów z bazy (np. po wczytaniu kopii)."""
        self.list.refresh_list()
        self.refresh_selected_client()

    def refresh_selected_client(self):
        if self.current_client is None:
            return

        client_id = self.current_client.get(
            "id"
        )

        if client_id is None:
            return

        clients = database_controller.load_database(
            "clients"
        )

        updated_client = None

        for client in clients:
            if str(
                    client.get("id")
            ) == str(client_id):
                updated_client = client
                break

        if updated_client is None:
            return

        self.current_client = updated_client

        self.on_selected_item(
            updated_client
        )

    def open_edit_window(self):
        if self.current_client is None:
            return

        dialog = EditClientDialog(
            self.current_client,
            self.list.refresh_list,
        )

        if dialog.exec():
            self.refresh_selected_client()

    def open_trash(self):
        dialog = TrashDialog(
            self.database_name,
            "Kosz - klienci",
            lambda item: str(item.get("name") or f"Klient #{item.get('id')}"),
            self,
        )

        dialog.exec()

        self.list.refresh_list()

    def wheelEvent(self, event):
        if (
                event.modifiers()
                & QtCore.Qt.KeyboardModifier.ControlModifier
        ):
            delta = event.angleDelta().y()

            if delta > 0:
                self.zoom_in()
            elif delta < 0:
                self.zoom_out()

            event.accept()
            return

        super().wheelEvent(event)

    def set_font_size(self, size: int):
        size = max(
            self.min_font_size,
            min(
                size,
                self.max_font_size
            )
        )

        self.font_size = size

        font = self.font()
        font.setPointSize(size)
        self.setFont(font)

        self.products_label.setStyleSheet(
            f"""
            font-size: {size + 2}pt;
            font-weight: bold;
            """
        )

        for book_item in (
                self.products_container.findChildren(
                    BookItem
                )
        ):
            book_item.set_font_size(
                size
            )

    def zoom_in(self):
        self.set_font_size(
            self.font_size + 1
        )

    def zoom_out(self):
        self.set_font_size(
            self.font_size - 1
        )

    def on_zoom_requested(
            self,
            direction: int
    ):
        if direction > 0:
            self.zoom_in()
        else:
            self.zoom_out()
