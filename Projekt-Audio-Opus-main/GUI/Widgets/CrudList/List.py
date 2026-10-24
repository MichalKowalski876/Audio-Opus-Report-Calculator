import difflib
import re

from PySide6 import QtWidgets, QtCore
from core import database_controller
from GUI.style.theme_manager import ThemeManager


class List(QtWidgets.QWidget):
    selected = QtCore.Signal(dict)

    def __init__(self, database_name: str):
        super().__init__()

        self.database_name = database_name
        self.data = []
        self.item_id = None
        self.search_text = ""

        self.label = QtWidgets.QLabel(database_name.capitalize())

        self.list = QtWidgets.QTreeWidget()
        self.list.setColumnCount(2)
        self.list.header().hide()
        self.list.setRootIsDecorated(False)
        self.list.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        self.list.setIndentation(0)
        self.list.setUniformRowHeights(True)

        self.list.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )
        self.list.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)

        self._selection_accent = None
        self._update_selection_style()

        header = self.list.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            0,
            QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        header.setSectionResizeMode(
            1,
            QtWidgets.QHeaderView.ResizeMode.Fixed
        )

        self.list.setColumnWidth(1, 45)

        self.refresh_list()

        self.list.itemClicked.connect(self.on_item_clicked)

        self.setup_layout()

    def _update_selection_style(self):
        accent = ThemeManager.get_current_accent()
        if accent == self._selection_accent:
            return

        self._selection_accent = accent
        accent_hover = ThemeManager.get_accent_palette().hover
        self.list.setStyleSheet("""
            QTreeWidget {
                border: none;
                outline: none;
                background: transparent;
            }

            QTreeWidget::item {
                height: 36px;
                border: none;
                padding-left: 8px;
                padding-right: 8px;
            }

            QTreeWidget::item:hover {
                background-color: rgba(255, 255, 255, 0.06);
            }

            QTreeWidget::item:selected {
                background-color: %s;
                color: white;
            }

            QTreeWidget::item:selected:hover {
                background-color: %s;
            }
        """ % (accent, accent_hover))

    def paintEvent(self, event):
        self._update_selection_style()
        super().paintEvent(event)

    def changeEvent(self, event):
        if event.type() in (
            QtCore.QEvent.Type.StyleChange,
            QtCore.QEvent.Type.PaletteChange,
        ):
            self._update_selection_style()
        super().changeEvent(event)

    def refresh_list(self):
        self.data = database_controller.load_database(
            self.database_name
        )

        self.data.sort(
            key=lambda item: str(
                item.get("name") or ""
            ).casefold()
        )

        selected_id = self.item_id

        self.list.clear()

        selected_item = None

        for data in self.data:
            products = data.get("products", [])

            books_count = (
                len(products)
                if isinstance(products, list)
                else 0
            )

            item = QtWidgets.QTreeWidgetItem([
                str(data.get("name") or "-"),
                str(books_count),
            ])

            item.setData(
                0,
                QtCore.Qt.ItemDataRole.UserRole,
                data
            )

            item.setTextAlignment(
                0,
                QtCore.Qt.AlignmentFlag.AlignVCenter
                | QtCore.Qt.AlignmentFlag.AlignLeft
            )

            item.setTextAlignment(
                1,
                QtCore.Qt.AlignmentFlag.AlignVCenter
                | QtCore.Qt.AlignmentFlag.AlignRight
            )

            self.list.addTopLevelItem(item)

            if (
                    selected_id is not None
                    and str(data.get("id")) == str(selected_id)
            ):
                selected_item = item

        if selected_item is not None:
            self.list.setCurrentItem(selected_item)

        self.search(self.search_text)

    @staticmethod
    def _normalize_value(value):
        if value is None:
            return ""

        return re.sub(
            r"\s+",
            " ",
            re.sub(r"[^\wąćęłńóśźżA-Za-z0-9]+", " ", str(value)).strip()
        ).casefold()

    @classmethod
    def _matches_fuzzy(cls, query: str, searchable_text: str) -> bool:
        normalized_query = cls._normalize_value(query)
        if not normalized_query:
            return True

        normalized_text = cls._normalize_value(searchable_text)
        if not normalized_text:
            return False

        if normalized_query in normalized_text:
            return True

        query_tokens = [token for token in normalized_query.split() if token]
        text_tokens = [token for token in normalized_text.split() if token]

        for token in query_tokens:
            if any(token == other or token in other or other in token for other in text_tokens):
                return True

            if any(difflib.SequenceMatcher(None, token, other).ratio() >= 0.7 for other in text_tokens):
                return True

        if len(normalized_query) > 2:
            return difflib.SequenceMatcher(None, normalized_query, normalized_text).ratio() >= 0.55

        return False

    def search(self, search_text: str, use_fuzzy: bool = False):
        self.search_text = search_text
        normalized_text = search_text.strip()

        product_map = {}
        if self.database_name == "clients":
            products = database_controller.load_database("products")
            product_map = {
                str(product.get("id")): product
                for product in products
                if isinstance(product, dict)
            }

        for index in range(self.list.topLevelItemCount()):
            item = self.list.topLevelItem(index)
            data = item.data(0, QtCore.Qt.ItemDataRole.UserRole) or {}

            searchable_values = []
            for key, value in data.items():
                if key == "products" and isinstance(value, list):
                    for product_id in value:
                        product = product_map.get(str(product_id))
                        if isinstance(product, dict):
                            searchable_values.extend(
                                str(element)
                                for element in product.values()
                            )
                    continue

                if isinstance(value, list):
                    searchable_values.extend(str(element) for element in value)
                else:
                    searchable_values.append(str(value))

            searchable_text = " ".join(searchable_values)

            if not normalized_text:
                item.setHidden(False)
                continue

            match = (
                self._matches_fuzzy(normalized_text, searchable_text)
                if use_fuzzy
                else normalized_text.casefold() in searchable_text.casefold()
            )

            item.setHidden(not match)

    def on_item_clicked(self, item, column=0):
        data = item.data(
            0,
            QtCore.Qt.ItemDataRole.UserRole
        )

        if not data:
            return

        self.item_id = data["id"]

        self.selected.emit(data)

    def setup_layout(self):
        layout = QtWidgets.QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        layout.addWidget(
            self.label,
            alignment=QtCore.Qt.AlignmentFlag.AlignCenter
        )

        layout.addWidget(
            self.list,
            1
        )