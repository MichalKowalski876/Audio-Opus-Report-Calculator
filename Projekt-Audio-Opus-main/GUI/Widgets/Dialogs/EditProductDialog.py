from PySide6 import QtCore, QtGui, QtWidgets

from core import database_controller


class EditProductDialog(QtWidgets.QDialog):
    def __init__(self, product: dict, parent=None):
        super().__init__(parent)

        self.product = product

        self.setWindowTitle("Edytuj książkę")
        self.setMinimumWidth(420)

        self.form_layout = QtWidgets.QFormLayout(self)

        self.title_widget = QtWidgets.QLineEdit(
            str(product.get("title", ""))
        )
        self.title_widget.setPlaceholderText("Tytuł")
        self.form_layout.addRow("Tytuł:", self.title_widget)

        self.author_widget = QtWidgets.QLineEdit(
            str(product.get("author", ""))
        )
        self.author_widget.setPlaceholderText("Autor")
        self.form_layout.addRow("Autor:", self.author_widget)

        self.publisher_widget = QtWidgets.QComboBox()

        clients = database_controller.load_database("clients")

        for client in clients:
            self.publisher_widget.addItem(
                str(client.get("name", "")),
                client.get("id")
            )

        current_publisher = str(
            product.get("publisher", "")
        ).strip()

        publisher_index = self.publisher_widget.findText(
            current_publisher
        )

        if publisher_index >= 0:
            self.publisher_widget.setCurrentIndex(
                publisher_index
            )

        self.form_layout.addRow(
            "Wydawnictwo:",
            self.publisher_widget
        )

        self.cut_widget = QtWidgets.QLineEdit(
            str(product.get("cut", ""))
        )

        self.cut_widget.setValidator(
            QtGui.QIntValidator(
                0,
                100,
                self.cut_widget
            )
        )

        self.cut_widget.setPlaceholderText("Procent")

        self.form_layout.addRow(
            "Procent:",
            self.cut_widget
        )

        self.isbn_widget = QtWidgets.QLineEdit(
            str(product.get("isbn", ""))
        )

        self.isbn_widget.setPlaceholderText("ISBN")

        self.form_layout.addRow(
            "ISBN:",
            self.isbn_widget
        )

        self.settlement_widget = QtWidgets.QComboBox()

        self.settlement_widget.addItems(
            [
                "instant",
                "threshold"
            ]
        )

        self.settlement_widget.setCurrentText(
            str(
                product.get(
                    "settlement type",
                    ""
                )
            ).strip()
            or "instant"
        )

        self.form_layout.addRow(
            "Typ rozliczenia:",
            self.settlement_widget
        )

        self.threshold_widget = QtWidgets.QLineEdit(
            str(product.get("threshold", ""))
        )

        self.threshold_widget.setValidator(
            QtGui.QDoubleValidator(
                0.0,
                1e9,
                2,
                self.threshold_widget
            )
        )

        self.threshold_widget.setPlaceholderText("Próg")

        self.form_layout.addRow(
            "Próg:",
            self.threshold_widget
        )

        self.settlement_widget.currentTextChanged.connect(
            self.update_editable_fields
        )

        self.update_editable_fields()

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        self.save_button = self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save
        )
        self.save_button.setText("Zapisz")
        self.save_button.setDefault(True)

        self.cancel_button = self.buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        self.cancel_button.setText("Anuluj")

        self.buttons.accepted.connect(
            self.save
        )

        self.buttons.rejected.connect(
            self.reject
        )

        self.form_layout.addWidget(
            self.buttons
        )

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.enter_shortcut.activated.connect(
            self._handle_enter_pressed
        )

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(
            self._handle_enter_pressed
        )

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        self.save()

    def update_editable_fields(self):
        is_threshold = (
            self.settlement_widget
            .currentText()
            .strip()
            .lower()
            == "threshold"
        )

        # Procent (prowizja AO) dotyczy obu typów rozliczenia - zostaje aktywny.
        # Próg ma sens tylko przy "threshold", więc dla "od razu" chowamy ten
        # wiersz formularza i zerujemy jego wartość.
        self.form_layout.setRowVisible(self.threshold_widget, is_threshold)

        if not is_threshold:
            self.threshold_widget.setText("0")

    def save(self):
        if not self.title_widget.text().strip():
            QtWidgets.QMessageBox.warning(
                self,
                "Brak tytułu",
                "Tytuł książki nie może być pusty."
            )
            return

        settlement_type = (
            self.settlement_widget
            .currentText()
            .strip()
            .lower()
        )

        # Procent (prowizja AO) obowiązuje przy obu typach rozliczenia.
        try:
            cut_value = int(
                self.cut_widget.text().strip()
                or 0
            )
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowe dane",
                "Procent musi być liczbą całkowitą."
            )
            return

        # Próg dotyczy tylko rozliczenia "po progu".
        threshold_value = 0.0

        if settlement_type == "threshold":
            try:
                threshold_value = float(
                    self.threshold_widget
                    .text()
                    .strip()
                    .replace(",", ".")
                    or 0
                )
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Nieprawidłowe dane",
                    "Próg musi być liczbą."
                )
                return

        values = {
            "title": self.title_widget.text().strip(),
            "author": self.author_widget.text().strip(),
            "publisher": self.publisher_widget.currentText().strip(),
            "isbn": self.isbn_widget.text().strip(),
            "cut": cut_value,
            "threshold": threshold_value,
            "settlement type": settlement_type,
        }

        product_id = int(
            self.product["id"]
        )

        for field_key, value in values.items():
            database_controller.item_modify(
                product_id,
                field_key,
                value,
                "products"
            )

        self.accept()