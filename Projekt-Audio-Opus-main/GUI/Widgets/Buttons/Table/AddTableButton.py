from PySide6 import QtWidgets, QtGui, QtCore

from core import database_controller
from GUI.Widgets.Buttons import db_display


class AddTableButton(QtWidgets.QPushButton):
    FIELD_KEYS = {
        "id": "id",
        "name": "name",
        "nazwa": "name",
        "title": "title",
        "tytuł": "title",
        "author": "author",
        "autor": "author",
        "publisher": "publisher",
        "wydawnictwo": "publisher",
        "wydawnictwo / zleceniodawca": "publisher",
        "cut": "cut",
        "procent": "cut",
        "prowizja": "cut",
        "isbn": "isbn",
        "settlement type": "settlement type",
        "typ rozliczenia": "settlement type",
        "threshold": "threshold",
        "próg": "threshold",
        "streaming": "streaming",
        "platformy": "streaming",
    }

    def __init__(
        self,
        fields: list[str],
        database_name: str,
        refresh_callback,
        suggestions: dict[str, list[str]] = None,
        field_types: dict[str, type] = None,
    ):
        super().__init__(
            f"Dodaj {db_display.accusative_singular(database_name)}"
        )

        self.fields = fields
        self.database_name = database_name
        self.refresh_callback = refresh_callback
        self.suggestions = suggestions or {}
        self.field_types = field_types or {}
        self.extra_data = {}

        self.clicked.connect(self.add_item_button)

    def set_extra_data(self, extra_data: dict):
        self.extra_data = extra_data or {}

    def get_field_key(self, field: str) -> str:
        normalized_field = field.strip().lower()

        return self.FIELD_KEYS.get(
            normalized_field,
            normalized_field,
        )

    def create_input(self, field: str):
        field_key = self.get_field_key(field)
        if (
                self.database_name == "products"
                and field_key == "publisher"
        ):
            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.addItem("", None)

            clients = database_controller.load_database(
                "clients"
            )

            for client in clients:
                client_name = str(
                    client.get("name", "")
                ).strip()

                if client_name:
                    combo.addItem(
                        client_name,
                        client.get("id"),
                    )

            combo.setCurrentIndex(0)

            combo.setInsertPolicy(
                QtWidgets.QComboBox.InsertPolicy.NoInsert
            )

            if combo.lineEdit() is not None:
                combo.lineEdit().setPlaceholderText(
                    "Wybierz lub wpisz wydawnictwo..."
                )

            return combo

        options = self.suggestions.get(field_key)

        if options:
            combo = QtWidgets.QComboBox()
            combo.setEditable(True)
            combo.addItems(options)
            combo.setCurrentText("")

            if combo.lineEdit() is not None:
                combo.lineEdit().setPlaceholderText(field)

            return combo

        line_edit = QtWidgets.QLineEdit()
        line_edit.setPlaceholderText(field)

        field_type = self.field_types.get(field_key)

        if field_type is int:
            line_edit.setValidator(
                QtGui.QIntValidator(line_edit)
            )

        elif field_type is float:
            validator = QtGui.QDoubleValidator(line_edit)
            validator.setDecimals(2)

            line_edit.setValidator(validator)

        return line_edit

        line_edit = QtWidgets.QLineEdit()
        line_edit.setPlaceholderText(field)

        field_type = self.field_types.get(field_key)

        if field_type is int:
            line_edit.setValidator(
                QtGui.QIntValidator(line_edit)
            )

        elif field_type is float:
            validator = QtGui.QDoubleValidator(line_edit)
            validator.setDecimals(2)

            line_edit.setValidator(validator)

        return line_edit

    def read_input(self, widget, field_key: str):
        if isinstance(widget, QtWidgets.QComboBox):
            value = widget.currentText().strip()
        else:
            value = widget.text().strip()

        field_type = self.field_types.get(field_key)

        if value == "" or field_type is None:
            return value

        normalized_value = value.replace(",", ".")

        if field_type is int:
            return int(normalized_value)

        if field_type is float:
            return float(normalized_value)

        return value

    @staticmethod
    def _bind_threshold_visibility(layout, settlement_widget, threshold_widget):
        """Pokazuje pole "Próg" tylko dla rozliczenia "po progu".

        Dla "od razu" (albo pustego typu) pole jest chowane i czyszczone -
        próg nie ma tam żadnego zastosowania.
        """

        if (
            not isinstance(settlement_widget, QtWidgets.QComboBox)
            or threshold_widget is None
        ):
            return

        def sync_visibility(*_):
            is_threshold = (
                settlement_widget.currentText().strip().lower() == "threshold"
            )
            layout.setRowVisible(threshold_widget, is_threshold)
            if not is_threshold:
                threshold_widget.clear()

        settlement_widget.currentTextChanged.connect(sync_visibility)
        sync_visibility()

    def add_item_button(self):
        dialog_parent = (
            None
            if self.database_name == "products"
            else self
        )
        dialog = QtWidgets.QDialog(dialog_parent)
        dialog.setWindowFlags(
            dialog.windowFlags() | QtCore.Qt.WindowMinimizeButtonHint
        )
        dialog.setModal(False)
        dialog.setWindowModality(QtCore.Qt.WindowModality.NonModal)
        dialog.setWindowTitle(
            f"Dodaj {db_display.accusative_singular(self.database_name)}"
        )
        dialog.setMinimumWidth(400)

        layout = QtWidgets.QFormLayout(dialog)

        inputs = {}

        for field in self.fields:
            field_key = self.get_field_key(field)
            widget = self.create_input(field)

            layout.addRow(
                f"{field}:",
                widget,
            )

            inputs[field_key] = widget

        # Próg dotyczy wyłącznie rozliczenia "po progu" (threshold). Przy
        # "od razu" (instant) chowamy to pole - Procent (prowizja AO) zostaje,
        # bo report_generator liczy go dla obu typów rozliczenia.
        self._bind_threshold_visibility(
            layout,
            inputs.get("settlement type"),
            inputs.get("threshold"),
        )

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Save
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )

        save_button = buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Save
        )
        save_button.setText("Dodaj")

        cancel_button = buttons.button(
            QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        cancel_button.setText("Anuluj")

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        layout.addWidget(buttons)

        dialog_loop = QtCore.QEventLoop(dialog)
        dialog.finished.connect(dialog_loop.quit)
        dialog.show()
        dialog_loop.exec()

        if dialog.result() != QtWidgets.QDialog.DialogCode.Accepted:
            return

        item = {}

        try:
            for field_key, widget in inputs.items():
                item[field_key] = self.read_input(
                    widget,
                    field_key,
                )
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowe dane",
                "Pola liczbowe muszą zawierać poprawne liczby.",
            )
            return

        if self.database_name == "products":
            if not item.get("title"):
                QtWidgets.QMessageBox.warning(
                    self,
                    "Brak tytułu",
                    "Tytuł produktu nie może być pusty.",
                )
                return

            item.setdefault("streaming", [])

        item.update(self.extra_data)

        # Dodaj produkt i zapamiętaj jego ID.
        new_item_id = database_controller.item_add(
            item,
            self.database_name,
        )

        # Produkty są automatycznie przypisywane
        # do wybranego wydawnictwa/klienta.
        if self.database_name == "products":
            publisher_widget = inputs.get("publisher")

            if self.database_name == "products":
                publisher_widget = inputs.get("publisher")

                if (
                        publisher_widget is not None
                        and isinstance(
                    publisher_widget,
                    QtWidgets.QComboBox,
                )
                        and publisher_widget.currentData() is not None
                ):
                    publisher_id = publisher_widget.currentData()

                    clients = database_controller.load_database(
                        "clients"
                    )

                    for client in clients:
                        if client.get("id") == publisher_id:
                            products = client.get(
                                "products",
                                [],
                            )

                            if new_item_id not in products:
                                products.append(new_item_id)

                            client["products"] = products

                            break

                    database_controller.save_database(
                        "clients",
                        clients,
                    )

            publisher_id = publisher_widget.currentData()

            clients = database_controller.load_database(
                "clients"
            )

            for client in clients:
                if client.get("id") == publisher_id:
                    products = client.get(
                        "products",
                        [],
                    )

                    if new_item_id not in products:
                        products.append(new_item_id)

                    client["products"] = products

                    break

            database_controller.save_database(
                "clients",
                clients,
            )
        try:
            window = self.window()

            if hasattr(window, "clients_tab"):
                clients_tab = window.clients_tab

                if hasattr(clients_tab, "refresh_table"):
                    clients_tab.refresh_table()

                if hasattr(clients_tab, "refresh_selected_client"):
                    clients_tab.refresh_selected_client()

        except Exception as error:
            print(
                f"Nie udało się automatycznie odświeżyć klientów: {error}"
            )

        self.refresh_callback()