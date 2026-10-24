from PySide6 import QtWidgets


def book_is_on_platform(product: dict, platform_name: str) -> bool:
    assigned_platforms = product.get("streaming", [])
    if not isinstance(assigned_platforms, list):
        assigned_platforms = [assigned_platforms] if assigned_platforms else []

    expected_name = platform_name.strip().casefold()
    return any(
        str(name).strip().casefold() == expected_name
        for name in assigned_platforms
    )


class PlatformBooksDialog(QtWidgets.QDialog):
    def __init__(self, platform_name: str, products: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Książki na platformie – {platform_name}")
        self.resize(760, 480)

        platform_books = sorted(
            (
                product
                for product in products
                if isinstance(product, dict)
                and book_is_on_platform(product, platform_name)
            ),
            key=lambda product: str(product.get("title", "")).casefold(),
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QtWidgets.QLabel(f"Książki dostępne na platformie {platform_name}")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        if platform_books:
            summary = QtWidgets.QLabel(
                f"Liczba przypisanych książek: {len(platform_books)}"
            )
        else:
            summary = QtWidgets.QLabel(
                "Do tej platformy nie przypisano jeszcze żadnych książek."
            )
        summary.setWordWrap(True)
        layout.addWidget(summary)

        self.books_table = QtWidgets.QTableWidget(len(platform_books), 3)
        self.books_table.setHorizontalHeaderLabels(["Tytuł", "Autor", "ISBN"])
        self.books_table.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.books_table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.books_table.setAlternatingRowColors(True)
        self.books_table.verticalHeader().setVisible(False)

        for row, product in enumerate(platform_books):
            values = (
                product.get("title", ""),
                product.get("author", ""),
                product.get("isbn", ""),
            )
            for column, value in enumerate(values):
                self.books_table.setItem(
                    row,
                    column,
                    QtWidgets.QTableWidgetItem(str(value or "")),
                )

        header = self.books_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(
            2,
            QtWidgets.QHeaderView.ResizeMode.ResizeToContents,
        )
        layout.addWidget(self.books_table, 1)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        )
        buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Close
        ).setText("Zamknij")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
