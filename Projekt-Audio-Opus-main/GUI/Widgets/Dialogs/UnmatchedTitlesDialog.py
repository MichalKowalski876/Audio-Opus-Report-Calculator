from PySide6 import QtCore, QtGui, QtWidgets


class UnmatchedTitlesDialog(QtWidgets.QDialog):
    """Lista tytulow z raportu platformy, ktorych nie ma w bazie ksiazek.

    Uzytkownik zaznacza, ktore dopisac - dzieki temu po ponownym imporcie
    trafiaja one do rozliczenia zamiast byc po cichu pomijane."""

    def __init__(self, entries: list[dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tytuły spoza bazy książek")
        self.resize(620, 420)

        self.entries = entries

        info = QtWidgets.QLabel(
            "Te tytuły są w raportach platform, ale nie ma ich w bazie książek. "
            "Zaznacz te, które chcesz dopisać - resztę danych (autor, prowizja, próg) "
            "uzupełnisz później w zakładce z książkami."
        )
        info.setWordWrap(True)

        self.list_widget = QtWidgets.QListWidget()
        for entry in entries:
            label = str(entry.get("title", "")).strip() or "(bez nazwy)"

            details = []
            if entry.get("isbn"):
                details.append(f"ISBN {entry['isbn']}")
            if entry.get("platform"):
                details.append(str(entry["platform"]))
            try:
                details.append(f"{float(entry.get('net', 0)):.2f} zł")
            except (TypeError, ValueError):
                pass

            if details:
                label += "   ·   " + "   ·   ".join(details)

            list_item = QtWidgets.QListWidgetItem(label)
            list_item.setFlags(list_item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            list_item.setCheckState(QtCore.Qt.CheckState.Checked)
            list_item.setData(QtCore.Qt.ItemDataRole.UserRole, entry)
            self.list_widget.addItem(list_item)

        self.select_all_button = QtWidgets.QPushButton("Zaznacz wszystkie")
        self.select_all_button.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Checked))

        self.clear_all_button = QtWidgets.QPushButton("Odznacz wszystkie")
        self.clear_all_button.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Unchecked))

        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.addButton("Dodaj do bazy książek", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.button_box.addButton("Pomiń", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        selection_row = QtWidgets.QHBoxLayout()
        selection_row.addWidget(self.select_all_button)
        selection_row.addWidget(self.clear_all_button)
        selection_row.addStretch()

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(info)
        layout.addWidget(self.list_widget)
        layout.addLayout(selection_row)
        layout.addWidget(self.button_box)

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

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        self.accept()

    def _set_all(self, state):
        for row in range(self.list_widget.count()):
            self.list_widget.item(row).setCheckState(state)

    def selected_entries(self) -> list[dict]:
        selected = []
        for row in range(self.list_widget.count()):
            list_item = self.list_widget.item(row)
            if list_item.checkState() == QtCore.Qt.CheckState.Checked:
                selected.append(list_item.data(QtCore.Qt.ItemDataRole.UserRole))
        return selected