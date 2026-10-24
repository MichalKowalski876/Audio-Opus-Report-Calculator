from PySide6 import QtWidgets, QtCore, QtGui
from core import database_controller
from GUI.Widgets.Settings.ShortcutManager import ShortcutManager


class EditClientDialog(QtWidgets.QDialog):
    def __init__(
            self,
            client_data,
            refresh_callback,
            parent=None,
            is_new: bool = False,
    ):
        super().__init__(parent)
        self.client_data = client_data
        self.refresh_callback = refresh_callback
        self.is_new = is_new
        self.setWindowTitle(
            "Dodawanie klienta" if is_new else "Edytuj klienta"
        )
        self.setWindowFlags(
            self.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint
        )
        self.setModal(True)
        self.resize(600, 700)

        self.setup_ui()
        self.load_assigned_books()

        self.books_list.itemChanged.connect(self.on_book_item_changed)

        if self.is_new:
            self.name_edit.setFocus()

    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()
        self.name_edit = QtWidgets.QLineEdit(str(self.client_data.get("name", "")))
        self.name_edit.setPlaceholderText("Nazwa klienta / wydawnictwa")
        form_layout.addRow("Nazwa:", self.name_edit)

        self.email_edit = QtWidgets.QLineEdit(str(self.client_data.get("email", "")))
        self.email_edit.setPlaceholderText("Adres e-mail")
        form_layout.addRow("E-mail:", self.email_edit)
        layout.addLayout(form_layout)

        books_label = QtWidgets.QLabel("Przypisane książki:")
        books_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(books_label)

        info_label = QtWidgets.QLabel(
            "Zielone — przypisane do tego klienta  |  "
            "Czerwone — przypisane do innego klienta"
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Wyszukaj książkę (tytuł, autor)...")
        self.search_edit.textChanged.connect(self.filter_books)

        search_sequence = ShortcutManager().get_shortcut("search_focus")
        self.search_shortcut = QtGui.QShortcut(
            search_sequence,
            self,
        )
        self.search_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.search_shortcut.activated.connect(
            self._focus_book_search
        )

        layout.addWidget(self.search_edit)

        self.books_list = QtWidgets.QListWidget()
        self.books_list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.NoSelection)
        layout.addWidget(self.books_list)

        buttons_layout = QtWidgets.QHBoxLayout()
        self.cancel_button = QtWidgets.QPushButton("Anuluj")
        self.cancel_button.clicked.connect(self.reject)
        buttons_layout.addWidget(self.cancel_button)
        buttons_layout.addStretch()

        self.save_button = QtWidgets.QPushButton("Zapisz")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self.save)
        buttons_layout.addWidget(self.save_button)
        layout.addLayout(buttons_layout)

        # Skróty klawiszowe dla klawisza Enter
        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.enter_shortcut.activated.connect(self._handle_enter_pressed)

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.numpad_enter_shortcut.activated.connect(self._handle_enter_pressed)

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        self.save()

    def _focus_book_search(self):
        if not self.isVisible():
            return
        self.search_edit.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.search_edit.selectAll()

    def load_assigned_books(self):
        self.books_list.blockSignals(True)
        self.books_list.clear()

        all_books = database_controller.load_database("products")
        clients = database_controller.load_database("clients")
        current_client_id = self.client_data.get("id")

        product_owner = {}
        for client in clients:
            for product_id in client.get("products", []):
                product_owner[product_id] = client

        unassigned = []
        assigned_to_other = []
        assigned_to_current = []

        for book in all_books:
            book_id = book.get("id")
            owner = product_owner.get(book_id)

            if owner is None:
                unassigned.append(book)
            elif owner.get("id") == current_client_id:
                assigned_to_current.append(book)
            else:
                assigned_to_other.append(book)

        books = assigned_to_current + unassigned + assigned_to_other

        if not books:
            placeholder = QtWidgets.QListWidgetItem("Brak dostępnych książek.")
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            self.books_list.addItem(placeholder)
            self.books_list.blockSignals(False)
            return

        for book in books:
            book_id = book.get("id")
            title = str(book.get("title", "")).strip()
            author = str(book.get("author", "")).strip()
            owner = product_owner.get(book_id)

            item_text = title
            if author:
                item_text += f" — {author}"

            if owner is not None and owner.get("id") != current_client_id:
                owner_name = str(owner.get("name", "")).strip()
                if owner_name:
                    item_text += f"  [Wydawnictwo: {owner_name}]"

            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, book_id)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)

            if owner is not None and owner.get("id") == current_client_id:
                item.setCheckState(QtCore.Qt.CheckState.Checked)
            else:
                item.setCheckState(QtCore.Qt.CheckState.Unchecked)

            self.update_book_item_color(item, product_owner)
            self.books_list.addItem(item)

        self.books_list.blockSignals(False)

    def update_book_item_color(self, item, product_owner=None):
        product_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if product_id is None:
            return

        if product_owner is None:
            clients = database_controller.load_database("clients")
            product_owner = {}
            for client in clients:
                for assigned_product_id in client.get("products", []):
                    product_owner[assigned_product_id] = client

        current_client_id = self.client_data.get("id")
        owner = product_owner.get(product_id)

        if owner is None:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#ffffff")))
        elif owner.get("id") == current_client_id:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#5cff9d")))
        else:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#ff6b6b")))

    def on_book_item_changed(self, item):
        if item is None:
            return

        product_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if product_id is None:
            return

        if item.checkState() == QtCore.Qt.CheckState.Checked:
            item.setForeground(QtGui.QBrush(QtGui.QColor("#5cff9d")))
        else:
            clients = database_controller.load_database("clients")
            current_client_id = self.client_data.get("id")
            owner = None

            for client in clients:
                if product_id in client.get("products", []):
                    owner = client
                    break

            if owner is not None and owner.get("id") != current_client_id:
                item.setForeground(QtGui.QBrush(QtGui.QColor("#ff6b6b")))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor("#ffffff")))

    def save(self):
        self.client_data["name"] = self.name_edit.text().strip()
        self.client_data["email"] = self.email_edit.text().strip()

        if not self.client_data["name"]:
            QtWidgets.QMessageBox.warning(
                self, "Brak nazwy", "Nazwa klienta nie może być pusta."
            )
            return

        if self.is_new:
            # klient trafia do bazy dopiero po zatwierdzeniu okna
            # więc anuluj/Esc niczego nie tworzy
            self.client_data["id"] = database_controller.item_add(
                {
                    "name": self.client_data["name"],
                    "email": self.client_data["email"],
                    "products": [],
                    "created_at": self.client_data.get("created_at"),
                },
                "clients",
            )
            self.is_new = False

        selected_books = []
        for index in range(self.books_list.count()):
            item = self.books_list.item(index)
            if item is None:
                continue

            product_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
            if product_id is None:
                continue

            if item.checkState() == QtCore.Qt.CheckState.Checked:
                selected_books.append(product_id)

        current_client_id = self.client_data["id"]
        clients = database_controller.load_database("clients")

        for client in clients:
            if client.get("id") != current_client_id:
                client["products"] = [
                    assigned_product_id
                    for assigned_product_id in client.get("products", [])
                    if assigned_product_id not in selected_books
                ]

        self.client_data["products"] = selected_books

        for index, client in enumerate(clients):
            if client.get("id") == current_client_id:
                clients[index] = self.client_data
                break

        database_controller.save_database("clients", clients)

        products = database_controller.load_database("products")
        client_name = self.client_data["name"]

        for product in products:
            product_id = product.get("id")

            if product_id in selected_books:
                product["publisher"] = client_name
            elif (
                    product.get("publisher", "").strip() == client_name
                    and product_id not in selected_books
            ):
                product["publisher"] = ""

        database_controller.save_database("products", products)

        self.refresh_callback()
        self.accept()

    def filter_books(self, text):
        search_phrase = text.lower().strip()

        for index in range(self.books_list.count()):
            item = self.books_list.item(index)

            if item is None:
                continue

            if item.flags() & QtCore.Qt.ItemFlag.NoItemFlags:
                continue

            item_text = item.text().lower()

            if search_phrase in item_text:
                item.setHidden(False)
            else:
                item.setHidden(True)
