from PySide6 import QtWidgets, QtCore, QtGui
from PySide6.QtWidgets import QHeaderView

from core import database_controller


class NumericDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, value_type=float, min_val=None, max_val=None, parent=None):
        super().__init__(parent)
        self.value_type = value_type
        self.min_val = min_val
        self.max_val = max_val

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)

        if self.value_type is int:
            validator = QtGui.QIntValidator(editor)
            if self.min_val is not None and self.max_val is not None:
                validator.setRange(self.min_val, self.max_val)
            editor.setValidator(validator)
        else:
            validator = QtGui.QDoubleValidator(editor)
            validator.setDecimals(2)
            if self.min_val is not None and self.max_val is not None:
                validator.setRange(self.min_val, self.max_val)
            editor.setValidator(validator)

        return editor


class ComboDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, options: list[str], parent=None):
        super().__init__(parent)
        self.options = options

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.addItems(self.options)
        editor.setEditable(False)
        return editor

    def setEditorData(self, editor, index):
        value = index.model().data(index, QtCore.Qt.ItemDataRole.DisplayRole)
        idx = editor.findText(str(value))
        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), QtCore.Qt.ItemDataRole.EditRole)


class ZoomableTableWidget(QtWidgets.QTableWidget):
    zoom_requested = QtCore.Signal(int)

    def wheelEvent(self, event):
        if event.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            self.zoom_requested.emit(1 if delta > 0 else -1)
            event.accept()
        else:
            super().wheelEvent(event)


class Table(QtWidgets.QWidget):
    FIELD_KEYS = {
        "tytuł": "title",
        "title": "title",
        "autor": "author",
        "author": "author",
        "wydawnictwo": "publisher",
        "wydawnictwo / zleceniodawca": "publisher",
        "publisher": "publisher",
        "procent": "cut",
        "cut": "cut",
        "isbn": "isbn",
        "typ rozliczenia": "settlement type",
        "settlement type": "settlement type",
        "próg": "threshold",
        "threshold": "threshold",
        "streaming": "streaming",
        "name": "name",
        "nazwa": "name",
    }

    def __init__(self, table_header: list[str], database_name: str):
        super().__init__()

        self.table_header = table_header
        self.database_name = database_name

        self.data = []
        self.item_id = None
        self.row_text_cache = []
        self._columns_sized = False

        self.font_size = 10
        self.min_font_size = 8
        self.max_font_size = 40

        self.field_keys = [self.get_field_key(h) for h in table_header]
        self.field_to_column = {
            key: idx for idx, key in enumerate(self.field_keys)
        }

        self.table = ZoomableTableWidget()
        self.table.zoom_requested.connect(self.on_zoom_requested)

        self.table.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding,
        )

        self.table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table.setVerticalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.verticalScrollBar().setSingleStep(12)
        self.table.horizontalScrollBar().setSingleStep(12)

        self.table.setColumnCount(len(self.table_header))
        self.table.setHorizontalHeaderLabels(self.table_header)

        for column, field_key in enumerate(self.field_keys):
            if field_key == "id":
                self.table.hideColumn(column)

            elif field_key in ("cut", "procent"):
                self.table.setItemDelegateForColumn(
                    column,
                    NumericDelegate(
                        value_type=int,
                        min_val=0,
                        max_val=100,
                        parent=self.table,
                    ),
                )

            elif field_key in ("threshold", "próg"):
                self.table.setItemDelegateForColumn(
                    column,
                    NumericDelegate(
                        value_type=float,
                        parent=self.table,
                    ),
                )

            elif field_key in ("settlement type", "typ rozliczenia"):
                self.table.setItemDelegateForColumn(
                    column,
                    ComboDelegate(
                        ["instant", "threshold"],
                        parent=self.table,
                    ),
                )

        horizontal_header = self.table.horizontalHeader()

        horizontal_header.setSectionResizeMode(QHeaderView.Interactive)
        horizontal_header.setStretchLastSection(True)

        self.set_font_size(self.font_size)

        self.refresh_table()

        self.table.itemChanged.connect(self.on_item_changed)
        self.table.cellClicked.connect(self.on_item_clicked)

        self.setup_layout()

    def on_zoom_requested(self, direction: int):
        if direction > 0:
            self.zoom_in()
        else:
            self.zoom_out()

    def set_font_size(self, size: int):
        size = max(self.min_font_size, min(size, self.max_font_size))
        self.font_size = size

        font = self.table.font()
        font.setPointSize(size)
        self.table.setFont(font)

        horizontal_header = self.table.horizontalHeader()
        horizontal_header.setStyleSheet(
            f"""
            QHeaderView::section {{
                font-size: {size}pt;
                font-weight: bold;
            }}
            """
        )

        vertical_header = self.table.verticalHeader()
        vertical_header.setStyleSheet(
            f"""
            QHeaderView::section {{
                font-size: {size}pt;
                font-weight: bold;
            }}
            """
        )

        horizontal_header.setMinimumHeight(size + 24)

        metrics = QtGui.QFontMetrics(font)
        row_height = metrics.height() + 8
        vertical_header.setDefaultSectionSize(row_height)
        vertical_header.setMinimumSectionSize(row_height)

    def zoom_in(self):
        self.set_font_size(self.font_size + 1)

    def zoom_out(self):
        self.set_font_size(self.font_size - 1)

    def get_field_key(self, header: str) -> str:
        normalized_header = header.strip().lower()
        return self.FIELD_KEYS.get(normalized_header, normalized_header)

    def get_selected_item_id(self):
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return None

        id_item = self.table.item(selected_row, 0)
        if id_item is None:
            return None

        return int(id_item.text())

    def get_selected_item_data(self):
        item_id = self.get_selected_item_id()
        if item_id is None:
            return None

        return database_controller.item_get(item_id, self.database_name)

    def apply_settlement_rules(self, item_data: dict) -> dict:
        normalized_item = dict(item_data)

        settlement_type = str(
            normalized_item.get("settlement type", "")
        ).strip().lower()

        if settlement_type == "instant":
            normalized_item["threshold"] = 0.0
            normalized_item.setdefault("cut", 0)

        elif settlement_type == "threshold":
            normalized_item.setdefault("cut", 0)
            normalized_item.setdefault("threshold", 0.0)

        return normalized_item

    def _update_row_text_cache(self, row: int):
        if not (0 <= row < len(self.row_text_cache)):
            return

        parts = []
        for column in range(self.table.columnCount()):
            item = self.table.item(row, column)
            if item is not None:
                parts.append(item.text().lower())

        self.row_text_cache[row] = " ".join(parts)

    def on_item_changed(self, item):
        row = item.row()
        column = item.column()

        id_item = self.table.item(row, 0)
        if id_item is None:
            return

        field_key = self.field_keys[column]
        val_text = item.text().strip()

        if field_key in ("cut", "procent") and val_text:
            try:
                val = int(val_text)
                if not (0 <= val <= 100):
                    raise ValueError()
            except ValueError:
                return

        item_id = int(id_item.text())

        if 0 <= row < len(self.data):
            item_data = dict(self.data[row])
        else:
            item_data = database_controller.item_get(
                item_id, self.database_name
            ) or {}

        item_data[field_key] = item.text()
        item_data = self.apply_settlement_rules(item_data)

        database_controller.item_modify(
            item_id,
            field_key,
            item_data[field_key],
            self.database_name,
        )

        if field_key in ("settlement type", "typ rozliczenia"):
            database_controller.item_modify(
                item_id,
                "cut",
                item_data.get("cut", 0),
                self.database_name,
            )
            database_controller.item_modify(
                item_id,
                "threshold",
                item_data.get("threshold", 0.0),
                self.database_name,
            )

            with QtCore.QSignalBlocker(self.table):
                for key in ("cut", "threshold"):
                    col = self.field_to_column.get(key)
                    if col is None:
                        continue

                    table_item = self.table.item(row, col)
                    if table_item is not None:
                        table_item.setText(str(item_data.get(key, "")))

        if 0 <= row < len(self.data):
            self.data[row] = item_data

        self._update_row_text_cache(row)

    def on_item_clicked(self, row, column):
        id_item = self.table.item(row, 0)
        if id_item is not None:
            self.item_id = int(id_item.text())

    def refresh_table(self):
        self.data = database_controller.load_database(self.database_name)

        table = self.table
        table.setUpdatesEnabled(False)

        try:
            with QtCore.QSignalBlocker(table):
                if table.rowCount() != len(self.data):
                    table.setRowCount(len(self.data))

                for row, item in enumerate(self.data):
                    for column, field_key in enumerate(self.field_keys):
                        value = item.get(field_key, "")

                        if isinstance(value, list):
                            value = ", ".join(
                                str(element) for element in value
                            )

                        text = str(value)
                        table_item = table.item(row, column)

                        if table_item is None:
                            table_item = QtWidgets.QTableWidgetItem(text)

                            if field_key == "id":
                                table_item.setFlags(
                                    table_item.flags()
                                    & ~QtCore.Qt.ItemFlag.ItemIsEditable
                                )

                            table.setItem(row, column, table_item)
                        else:
                            table_item.setText(text)

                self.row_text_cache = []
                for row in range(table.rowCount()):
                    parts = []
                    for column in range(table.columnCount()):
                        it = table.item(row, column)
                        if it is not None:
                            parts.append(it.text().lower())
                    self.row_text_cache.append(" ".join(parts))

        finally:
            table.setUpdatesEnabled(True)
            table.viewport().update()

        if not self._columns_sized:
            table.resizeColumnsToContents()
            self._columns_sized = True

    def search(self, search_text: str):
        normalized_text = search_text.strip().lower()
        hide = bool(normalized_text)

        for row, text in enumerate(self.row_text_cache):
            self.table.setRowHidden(
                row,
                hide and normalized_text not in text,
            )

    def setup_layout(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self.table, 1)
