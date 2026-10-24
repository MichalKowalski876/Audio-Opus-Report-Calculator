import difflib
import re

from PySide6 import QtCore, QtWidgets, QtGui

from core import database_controller, paths

from GUI.Widgets.Buttons.Help.HelpButton import HelpButton
from GUI.Widgets.Buttons.Table.AddTableButton import AddTableButton
from GUI.Widgets.confirm import confirm_yes_no
from GUI.Widgets.Dialogs.EditProductDialog import EditProductDialog
from GUI.Widgets.Dialogs.TrashDialog import TrashDialog
from GUI.Widgets.Items.BookItem import BookItem
from GUI.Widgets.ScrollAreas.ZoomableScrollArea import ZoomableScrollArea


class ProductsTab(QtWidgets.QWidget):
    FUZZY_MATCH_THRESHOLD = 0.45

    def __init__(self):
        super().__init__()

        self.font_size = 10
        self.min_font_size = 8
        self.max_font_size = 40

        self.selected_product = None
        self.book_items = []
        self._selected_item_index = -1

        self.searchBar = QtWidgets.QLineEdit()
        self.searchBar.setFixedWidth(250)
        self.searchBar.setPlaceholderText("Szukaj tutaj...")
        self.searchBar.textChanged.connect(self.search)
        self.searchBar.returnPressed.connect(self.on_search_return_pressed)

        self.search_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence("Ctrl+F"),
            self,
        )
        self.search_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.search_shortcut.activated.connect(
            self._focus_product_search
        )

        self.delete_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete),
            self,
        )
        self.delete_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.delete_shortcut.activated.connect(
            self._remove_selected_product_with_delete
        )

        self.fuzzy_search_toggle = QtWidgets.QToolButton()
        self.fuzzy_search_toggle.setText("Fuzzy search")
        self.fuzzy_search_toggle.setCheckable(True)
        self.fuzzy_search_toggle.setChecked(True)
        self.fuzzy_search_toggle.setToolTip("Włącz lub wyłącz tryb fuzzy search")
        self.fuzzy_search_toggle.setCursor(
            QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        )
        self.fuzzy_search_toggle.setStyleSheet(
            """
            QToolButton {
                min-width: 112px;
                min-height: 30px;
                padding: 0 10px;
                border: 1px solid #555555;
                border-radius: 15px;
                background-color: transparent;
                color: #d6d6d6;
                font-weight: 600;
                text-align: left;
            }
            QToolButton:hover {
                border-color: #888888;
                background-color: rgba(255, 255, 255, 0.06);
            }
            QToolButton:checked {
                border-color: #2e9d4c;
                background-color: rgba(46, 157, 76, 0.18);
                color: #f0fff3;
            }
            QToolButton:checked:hover {
                background-color: rgba(46, 157, 76, 0.28);
            }
            """
        )
        self.fuzzy_search_toggle.toggled.connect(
            lambda _: self.search(self.searchBar.text())
        )

        self.help_button = HelpButton(
            "products",
            "Produkty"
        )

        self.add_button = AddTableButton(
            [
                "Tytuł",
                "Autor",
                "Wydawnictwo",
                "Procent",
                "ISBN",
                "Typ Rozliczenia",
                "Próg",
            ],
            "products",
            self.refresh_products,
            suggestions={
                "settlement type": [
                    "instant",
                    "threshold",
                ],
            },
            field_types={
                "cut": float,
                "threshold": float,
            },
        )

        self.add_button.setText("")
        self.add_button.setIcon(
            QtGui.QIcon(
                paths.resource_path(
                    "Assets",
                    "placeholders",
                    "add_product.png",
                )
            )
        )
        self.add_button.setIconSize(
            QtCore.QSize(18, 18)
        )
        self.add_button.setToolTip("Dodaj książkę")
        self.add_button.setFixedSize(28, 28)
        self.add_button.setProperty(
            "role",
            "AddButton"
        )

        self.remove_button = QtWidgets.QPushButton()
        self.remove_button.setText("")
        self.remove_button.setIcon(
            QtGui.QIcon(
                paths.resource_path(
                    "Assets",
                    "placeholders",
                    "remove_product.png",
                )
            )
        )
        self.remove_button.setIconSize(
            QtCore.QSize(18, 18)
        )
        self.remove_button.setToolTip("Usuń książkę")
        self.remove_button.setFixedSize(28, 28)
        self.remove_button.setProperty(
            "role",
            "RemoveButton"
        )
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(
            self.remove_selected_product
        )

        self.edit_button = QtWidgets.QPushButton(
            "Edytuj"
        )
        self.edit_button.setFixedWidth(90)
        self.edit_button.setEnabled(False)
        self.edit_button.clicked.connect(
            self.edit_selected_product
        )

        self.trash_button = QtWidgets.QPushButton(
            "Kosz"
        )
        self.trash_button.setToolTip("Pokaż usunięte książki")
        self.trash_button.clicked.connect(
            self.open_trash
        )

        self.products_container = QtWidgets.QWidget()

        self.products_layout = QtWidgets.QVBoxLayout(
            self.products_container
        )
        self.products_layout.setContentsMargins(
            0, 0, 0, 0
        )
        self.products_layout.setSpacing(4)
        self.products_layout.addStretch()

        self.products_scroll = ZoomableScrollArea()
        self.products_scroll.setWidgetResizable(True)
        self.products_scroll.setFrameShape(
            QtWidgets.QFrame.Shape.NoFrame
        )
        self.products_scroll.setWidget(
            self.products_container
        )
        self.products_scroll.zoom_requested.connect(
            self.on_zoom_requested
        )

        top_layout = QtWidgets.QHBoxLayout()
        top_layout.addStretch()
        top_layout.addWidget(
            self.help_button
        )

        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addStretch()
        search_layout.addWidget(
            self.searchBar
        )
        search_layout.addWidget(
            self.fuzzy_search_toggle
        )
        search_layout.addStretch()

        self.title_label = QtWidgets.QLabel(
            "Lista książek"
        )
        self.title_label.setProperty(
            "role",
            "SectionTitle"
        )

        header_layout = QtWidgets.QHBoxLayout()
        header_layout.addWidget(
            self.title_label
        )
        header_layout.addStretch()
        header_layout.addWidget(
            self.trash_button
        )
        header_layout.addWidget(
            self.edit_button
        )
        header_layout.addWidget(
            self.add_button
        )
        header_layout.addWidget(
            self.remove_button
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(top_layout)
        layout.addLayout(search_layout)
        layout.addLayout(header_layout)
        layout.addWidget(
            self.products_scroll,
            1
        )

        self.refresh_products()

    def reload(self):
        """Przeładowuje listę książek z bazy (po wczytaniu kopii bazy)."""
        self.refresh_products()

    def _remove_selected_product_with_delete(self):
        if self.searchBar.hasFocus():
            return
        if self.selected_product is not None:
            self.remove_selected_product()

    def _focus_product_search(self):
        if not self.isVisible():
            return
        self.searchBar.setFocus(QtCore.Qt.FocusReason.ShortcutFocusReason)
        self.searchBar.selectAll()

    def refresh_products(self):
        while self.products_layout.count() > 1:
            item = self.products_layout.takeAt(0)
            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.book_items.clear()
        self.selected_product = None

        self.edit_button.setEnabled(False)
        self.remove_button.setEnabled(False)

        products = database_controller.load_database(
            "products"
        )

        products.sort(
            key=lambda product: str(
                product.get("title") or ""
            ).casefold()
        )

        if not products:
            label = QtWidgets.QLabel(
                "Brak książek"
            )

            label.setAlignment(
                QtCore.Qt.AlignmentFlag.AlignCenter
            )

            self.products_layout.insertWidget(
                0,
                label
            )

            return

        for product in products:
            book_item = BookItem(product)

            book_item.set_font_size(
                self.font_size
            )

            book_item.clicked.connect(
                self.select_product
            )

            book_item.double_clicked.connect(
                self.edit_product
            )

            self.book_items.append(
                book_item
            )

            self.products_layout.insertWidget(
                self.products_layout.count() - 1,
                book_item
            )

        self.search(
            self.searchBar.text()
        )

    def _visible_book_items(self):
        return [
            book_item
            for book_item in self.book_items
            if book_item.isVisible()
        ]

    def keyPressEvent(self, event):
        if event.key() in (QtCore.Qt.Key.Key_Up, QtCore.Qt.Key.Key_Down):
            visible_items = self._visible_book_items()
            if not visible_items:
                return

            current_index = -1
            for index, item in enumerate(visible_items):
                if item is None:
                    continue
                if self.selected_product is not None and item.product == self.selected_product:
                    current_index = index
                    break

            if current_index == -1:
                current_index = 0 if event.key() == QtCore.Qt.Key.Key_Down else len(visible_items) - 1
            else:
                step = 1 if event.key() == QtCore.Qt.Key.Key_Down else -1
                current_index = (current_index + step) % len(visible_items)

            target_item = visible_items[current_index]
            self.select_product(target_item.product)
            event.accept()
            return

        super().keyPressEvent(event)

    def select_product(self, product: dict):
        self.selected_product = product

        selected_id = str(
            product.get("id")
        )

        for index, book_item in enumerate(self.book_items):
            item_id = str(
                book_item.product.get("id")
            )

            is_selected = item_id == selected_id
            book_item.set_selected(is_selected)
            if is_selected:
                self._selected_item_index = index

        self.edit_button.setEnabled(True)
        self.remove_button.setEnabled(True)

    @staticmethod
    def _normalize_for_search(value):
        if value is None:
            return ""

        return re.sub(
            r"\s+",
            " ",
            re.sub(r"[^\wąćęłńóśźżA-Za-z0-9]+", " ", str(value)).strip()
        ).casefold()

    @classmethod
    def _score_fuzzy_match(cls, query: str, searchable_text: str) -> float:
        normalized_query = cls._normalize_for_search(query)
        if not normalized_query:
            return 0.0

        normalized_text = cls._normalize_for_search(searchable_text)
        if not normalized_text:
            return 0.0

        query_tokens = [token for token in normalized_query.split() if token]
        text_tokens = [token for token in normalized_text.split() if token]

        if not query_tokens or not text_tokens:
            return 0.0

        token_scores = []
        for token in query_tokens:
            best_score = 0.0
            for other in text_tokens:
                if token == other:
                    similarity = 1.0
                elif other.startswith(token) or token.startswith(other):
                    similarity = 0.9
                elif token in other or other in token:
                    similarity = 0.8
                else:
                    similarity = difflib.SequenceMatcher(
                        None,
                        token,
                        other,
                    ).ratio()

                minimum_similarity = 0.78 if len(token) <= 3 else 0.68
                if similarity >= minimum_similarity:
                    best_score = max(best_score, similarity)

            token_scores.append(best_score)

        coverage = sum(token_scores) / len(token_scores)
        sequence_score = difflib.SequenceMatcher(
            None,
            normalized_query,
            normalized_text,
        ).ratio()
        contains_score = 1.0 if normalized_query in normalized_text else 0.0

        return (
            coverage * 0.7
            + sequence_score * 0.2
            + contains_score * 0.1
        )

    @classmethod
    def _matches_fuzzy(cls, query: str, searchable_text: str) -> bool:
        return (
            cls._score_fuzzy_match(query, searchable_text)
            >= cls.FUZZY_MATCH_THRESHOLD
        )

    def search(self, search_text: str):
        normalized_text = search_text.strip()
        best_score = -1.0
        best_item = None

        for book_item in self.book_items:
            product = book_item.product

            searchable_values = [
                str(product.get(field, ""))
                for field in (
                    "title",
                    "author",
                    "publisher",
                    "isbn",
                    "settlement type",
                    "threshold",
                    "cut",
                )
            ]

            searchable_text = " ".join(searchable_values)

            if not normalized_text:
                visible = True
                score = 0.0
            elif self.fuzzy_search_toggle.isChecked():
                score = self._score_fuzzy_match(normalized_text, searchable_text)
                visible = score >= self.FUZZY_MATCH_THRESHOLD
            else:
                score = 0.0 if normalized_text.casefold() in searchable_text.casefold() else -1.0
                visible = score >= 0.0

            if visible and score > best_score:
                best_score = score
                best_item = book_item

            if hasattr(book_item, "setProperty"):
                book_item.setProperty("recommended", False)
                book_item.style().unpolish(book_item)
                book_item.style().polish(book_item)

            book_item.setVisible(visible)

        if self.fuzzy_search_toggle.isChecked() and normalized_text and best_item is not None:
            self.select_product(best_item.product)
            if hasattr(best_item, "setProperty"):
                best_item.setProperty("recommended", True)
                best_item.style().unpolish(best_item)
                best_item.style().polish(best_item)
                best_item.update()

    def on_search_return_pressed(self):
        if self.fuzzy_search_toggle.isChecked() and self.selected_product is not None:
            self.edit_selected_product()

    def remove_selected_product(self):
        if self.selected_product is None:
            return

        product_title = str(
            self.selected_product.get(
                "title",
                "wybraną książkę"
            )
        )

        confirmed = confirm_yes_no(
            self,
            "Usuń książkę",
            (
                "Czy na pewno chcesz usunąć książkę:\n\n"
                f"{product_title}?"
            ),
        )

        if not confirmed:
            return

        product_id = self.selected_product.get(
            "id"
        )

        if product_id is None:
            return

        database_controller.item_remove(
            int(product_id),
            "products"
        )

        self.refresh_products()

    def open_trash(self):
        dialog = TrashDialog(
            "products",
            "Kosz - książki",
            lambda item: str(item.get("title") or f"Książka #{item.get('id')}"),
            self,
        )

        dialog.exec()

        self.refresh_products()

    def edit_selected_product(self):
        if self.selected_product is None:
            return

        self.edit_product(
            self.selected_product
        )

    def edit_product(self, product: dict):
        dialog = EditProductDialog(
            product,
            self
        )

        if dialog.exec():
            self.refresh_products()

    def on_zoom_requested(
        self,
        direction: int
    ):
        if direction > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def zoom_in(self):
        self.set_font_size(
            self.font_size + 1
        )

    def zoom_out(self):
        self.set_font_size(
            self.font_size - 1
        )

    def set_font_size(
        self,
        size: int
    ):
        size = max(
            self.min_font_size,
            min(
                size,
                self.max_font_size
            )
        )

        self.font_size = size

        for book_item in self.book_items:
            book_item.set_font_size(
                size
            )

        font = self.title_label.font()
        font.setPointSize(
            size + 2
        )
        font.setBold(True)

        self.title_label.setFont(
            font
        )

    def add_product(self):
        self.add_button.click()
