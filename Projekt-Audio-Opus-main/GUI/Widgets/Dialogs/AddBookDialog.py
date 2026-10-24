from PySide6 import QtCore, QtGui, QtWidgets

from core import database_controller


class AddBookDialog(QtWidgets.QDialog):
    """Okno dodawania książki znalezionej w raporcie platformy.

    Pola są wstępnie wypełnione danymi z raportu (tytuł, ISBN, autor).
    Zwraca kod: Accepted (dodano książkę), SKIPPED (pominięto i przejdź do
    następnej) albo Rejected (zakończ dodawanie kolejnych książek).
    """

    SKIPPED = 2

    def __init__(self, entry: dict, index: int = 1, total: int = 1, parent=None):
        super().__init__(parent)
        self.entry = entry
        self.added_product_id: int | None = None

        title = "Dodawanie książki"
        if total > 1:
            title += f" ({index} z {total})"
        self.setWindowTitle(title)
        self.setMinimumWidth(440)

        layout = QtWidgets.QVBoxLayout(self)

        self.info_label = QtWidgets.QLabel(self._info_text(entry))
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)

        self.form_layout = QtWidgets.QFormLayout()
        layout.addLayout(self.form_layout)

        self.title_widget = QtWidgets.QLineEdit(
            str(entry.get("title") or "").strip()
        )
        self.title_widget.setPlaceholderText("Tytuł")
        self.form_layout.addRow("Tytuł:", self.title_widget)

        self.author_widget = QtWidgets.QLineEdit(
            str(entry.get("author") or "").strip()
        )
        self.author_widget.setPlaceholderText("Autor")
        self.form_layout.addRow("Autor:", self.author_widget)

        self.publisher_widget = QtWidgets.QComboBox()
        self.publisher_widget.addItem("", None)
        for client in database_controller.load_database("clients"):
            client_name = str(client.get("name") or "").strip()
            if client_name:
                self.publisher_widget.addItem(client_name, client.get("id"))
        self.form_layout.addRow("Wydawnictwo:", self.publisher_widget)

        self.cut_widget = QtWidgets.QLineEdit()
        self.cut_widget.setValidator(
            QtGui.QDoubleValidator(0.0, 100.0, 2, self.cut_widget)
        )
        self.cut_widget.setPlaceholderText("Procent")
        self.form_layout.addRow("Procent:", self.cut_widget)

        self.isbn_widget = QtWidgets.QLineEdit(
            str(entry.get("isbn") or "").strip()
        )
        self.isbn_widget.setPlaceholderText("ISBN")
        self.form_layout.addRow("ISBN:", self.isbn_widget)

        self.settlement_widget = QtWidgets.QComboBox()
        self.settlement_widget.addItems(["instant", "threshold"])
        self.form_layout.addRow("Typ rozliczenia:", self.settlement_widget)

        self.threshold_widget = QtWidgets.QLineEdit()
        self.threshold_widget.setValidator(
            QtGui.QDoubleValidator(0.0, 1e9, 2, self.threshold_widget)
        )
        self.threshold_widget.setPlaceholderText("Próg")
        self.form_layout.addRow("Próg:", self.threshold_widget)

        self.settlement_widget.currentTextChanged.connect(
            self.update_threshold_visibility
        )
        self.update_threshold_visibility()

        self.buttons = QtWidgets.QDialogButtonBox()
        self.add_button = self.buttons.addButton(
            "Dodaj",
            QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole,
        )
        self.add_button.setDefault(True)
        self.skip_button = self.buttons.addButton(
            "Pomiń i dalej" if index < total else "Pomiń",
            QtWidgets.QDialogButtonBox.ButtonRole.ActionRole,
        )
        self.stop_button = self.buttons.addButton(
            "Zakończ",
            QtWidgets.QDialogButtonBox.ButtonRole.RejectRole,
        )
        self.add_button.clicked.connect(self.save)
        self.skip_button.clicked.connect(self.skip)
        self.stop_button.clicked.connect(self.reject)
        layout.addWidget(self.buttons)

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
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(self._handle_enter_pressed)

        self.publisher_widget.setFocus()

    @staticmethod
    def _info_text(entry: dict) -> str:
        details = []
        platform = str(entry.get("platform") or "").strip()
        if platform:
            details.append(platform)
        try:
            details.append(f"netto {float(entry.get('net')):.2f} zł")
        except (TypeError, ValueError):
            pass

        text = "Tej książki nie ma w bazie."
        if details:
            text += " Znaleziona w raporcie: " + ", ".join(details) + "."
        return text

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        self.save()

    def update_threshold_visibility(self):
        is_threshold = (
            self.settlement_widget.currentText().strip().lower() == "threshold"
        )
        self.form_layout.setRowVisible(self.threshold_widget, is_threshold)
        if not is_threshold:
            self.threshold_widget.clear()

    def skip(self):
        self.done(self.SKIPPED)

    def save(self):
        title = self.title_widget.text().strip()
        if not title:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak tytułu",
                "Tytuł książki nie może być pusty.",
            )
            return

        settlement_type = self.settlement_widget.currentText().strip().lower()

        try:
            cut_value = float(
                self.cut_widget.text().strip().replace(",", ".") or 0
            )
        except ValueError:
            QtWidgets.QMessageBox.warning(
                self,
                "Nieprawidłowe dane",
                "Procent musi być liczbą.",
            )
            return

        threshold_value = 0.0
        if settlement_type == "threshold":
            try:
                threshold_value = float(
                    self.threshold_widget.text().strip().replace(",", ".") or 0
                )
            except ValueError:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Nieprawidłowe dane",
                    "Próg musi być liczbą.",
                )
                return

        author = self.author_widget.text().strip()
        publisher = self.publisher_widget.currentText().strip()
        if not publisher and author:
            # Brak wybranego wydawnictwa - książka trafia bezpośrednio od
            # autora, więc autor staje się klientem, do którego dopisze się
            # ta książka (nowy klient powstaje automatycznie przy zapisie).
            publisher = author

        try:
            self.added_product_id = database_controller.item_add(
                {
                    "title": title,
                    "author": author,
                    "publisher": publisher,
                    "cut": cut_value,
                    "isbn": self.isbn_widget.text().strip(),
                    "settlement type": settlement_type,
                    "threshold": threshold_value,
                    "streaming": [],
                },
                "products",
            )
        except Exception as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd dodawania książki",
                f"Nie udało się dodać książki do bazy: {error}",
            )
            return

        self.accept()
