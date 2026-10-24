from PySide6 import QtCore, QtGui, QtWidgets


class BookItem(QtWidgets.QFrame):
    clicked = QtCore.Signal(dict)
    double_clicked = QtCore.Signal(dict)

    def __init__(self, product: dict):
        super().__init__()

        self.product = product
        self.selected = False

        self.setProperty("role", "BookItem")
        self.setProperty("selected", False)

        self.setCursor(
            QtGui.QCursor(
                QtCore.Qt.CursorShape.PointingHandCursor
            )
        )

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        title = QtWidgets.QLabel(
            str(product.get("title") or "Bez tytułu")
        )

        title.setObjectName("bookTitle")
        title.setProperty("role", "BookTitle")
        title.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )

        author = self.create_field(
            "Autor",
            product.get("author")
        )

        publisher = self.create_field(
            "Wydawnictwo / zleceniodawca",
            product.get("publisher")
        )

        isbn = self.create_field(
            "ISBN",
            product.get("isbn")
        )

        settlement_type = self.create_field(
            "Typ rozliczenia",
            product.get("settlement type")
        )

        cut = self.create_field(
            "Procent",
            product.get("cut"),
            "BookPositiveValue"
        )

        layout.addWidget(title)
        layout.addWidget(author)

        info_layout = QtWidgets.QGridLayout()
        info_layout.setHorizontalSpacing(30)
        info_layout.setVerticalSpacing(8)

        info_layout.addWidget(publisher, 0, 0)
        info_layout.addWidget(isbn, 0, 1)

        info_layout.addWidget(settlement_type, 1, 0)
        info_layout.addWidget(cut, 1, 1)

        # Próg pokazujemy tylko przy rozliczeniu "po progu".
        is_threshold = (
            str(product.get("settlement type") or "").strip().lower()
            == "threshold"
        )
        if is_threshold:
            threshold = self.create_field(
                "Próg",
                product.get("threshold"),
                "BookThresholdValue"
            )
            info_layout.addWidget(threshold, 2, 0)

        layout.addLayout(info_layout)

    def create_field(
        self,
        name: str,
        value,
        value_role: str = "BookValue"
    ):
        widget = QtWidgets.QWidget()

        widget.setAttribute(
            QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True
        )

        layout = QtWidgets.QHBoxLayout(widget)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        name_label = QtWidgets.QLabel(f"{name}:")
        name_label.setProperty("role", "BookField")

        value_label = QtWidgets.QLabel(
            str(value) if value not in (None, "") else "-"
        )

        value_label.setProperty(
            "role",
            value_role
        )

        layout.addWidget(name_label)
        layout.addWidget(value_label)
        layout.addStretch()

        return widget

    def set_selected(self, selected: bool):
        self.selected = selected

        self.setProperty(
            "selected",
            selected
        )

        self.style().unpolish(self)
        self.style().polish(self)
        self.update()

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.clicked.emit(
                self.product
            )

        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event):
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            self.double_clicked.emit(
                self.product
            )

        super().mouseDoubleClickEvent(event)

    def set_font_size(self, size: int):
        for label in self.findChildren(QtWidgets.QLabel):
            font = label.font()
            font.setPointSize(size)
            label.setFont(font)

        title = self.findChild(
            QtWidgets.QLabel,
            "bookTitle"
        )

        if title:
            title_font = title.font()
            title_font.setPointSize(size + 1)
            title.setFont(title_font)