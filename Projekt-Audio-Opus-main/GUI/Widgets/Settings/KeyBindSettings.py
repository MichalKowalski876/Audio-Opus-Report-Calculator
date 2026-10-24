from PySide6 import QtWidgets, QtCore, QtGui


class KeyBindSettings(QtWidgets.QWidget):
    shortcuts_changed = QtCore.Signal()

    def __init__(self, shortcut_manager, parent=None):
        super().__init__(parent)
        self.shortcut_manager = shortcut_manager
        self.init_ui()

        self.enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Return),
            self,
        )
        self.enter_shortcut.setContext(QtCore.Qt.ShortcutContext.WindowShortcut)
        self.enter_shortcut.activated.connect(self.save_shortcuts)

        self.numpad_enter_shortcut = QtGui.QShortcut(
            QtGui.QKeySequence(QtCore.Qt.Key.Key_Enter),
            self,
        )
        self.numpad_enter_shortcut.setContext(
            QtCore.Qt.ShortcutContext.WindowShortcut
        )
        self.numpad_enter_shortcut.activated.connect(self.save_shortcuts)

    def init_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title_label = QtWidgets.QLabel("Skróty klawiszowe")
        title_label.setProperty("role", "Title")
        layout.addWidget(title_label)

        form_layout = QtWidgets.QFormLayout()
        form_layout.setLabelAlignment(QtCore.Qt.AlignmentFlag.AlignRight)

        self.add_client_edit = QtWidgets.QKeySequenceEdit()
        self.add_client_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("add_client")
        )
        form_layout.addRow("Dodaj klienta:", self.add_client_edit)

        self.add_product_edit = QtWidgets.QKeySequenceEdit()
        self.add_product_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("add_product")
        )
        form_layout.addRow("Dodaj produkt:", self.add_product_edit)

        self.search_focus_edit = QtWidgets.QKeySequenceEdit()
        self.search_focus_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("search_focus")
        )
        form_layout.addRow("Szukaj / Wyszukiwanie:", self.search_focus_edit)

        self.send_report_edit = QtWidgets.QKeySequenceEdit()
        self.send_report_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("send_report")
        )
        form_layout.addRow("Wyślij raport na e-mail:", self.send_report_edit)

        self.open_calculator_edit = QtWidgets.QKeySequenceEdit()
        self.open_calculator_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("open_calculator")
        )
        form_layout.addRow("Otwórz kalkulator:", self.open_calculator_edit)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        form_layout.addRow(separator)

        self.switch_clients_edit = QtWidgets.QKeySequenceEdit()
        self.switch_clients_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_clients")
        )
        form_layout.addRow("Przełącz na klientów:", self.switch_clients_edit)

        self.switch_products_edit = QtWidgets.QKeySequenceEdit()
        self.switch_products_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_products")
        )
        form_layout.addRow("Przełącz na produkty:", self.switch_products_edit)

        self.switch_streaming_edit = QtWidgets.QKeySequenceEdit()
        self.switch_streaming_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_streaming")
        )
        form_layout.addRow("Przełącz na platformy:", self.switch_streaming_edit)

        self.switch_reports_edit = QtWidgets.QKeySequenceEdit()
        self.switch_reports_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_reports")
        )
        form_layout.addRow("Przełącz na raporty:", self.switch_reports_edit)

        layout.addLayout(form_layout)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        save_btn = QtWidgets.QPushButton("Zapisz skróty")
        save_btn.clicked.connect(self.save_shortcuts)
        button_layout.addWidget(save_btn)

        reset_btn = QtWidgets.QPushButton("Przywróć domyślne")
        reset_btn.clicked.connect(self.reset_defaults)
        button_layout.addWidget(reset_btn)

        layout.addLayout(button_layout)
        layout.addStretch()

    def reset_defaults(self):
        reply = QtWidgets.QMessageBox.question(
            self,
            "Przywróć domyślne",
            "Czy na pewno chcesz przywrócić domyślne skróty?\nWszystkie zmiany zostaną utracone.",
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        )
        if reply != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        for action, default_seq in self.shortcut_manager.defaults.items():
            seq = QtGui.QKeySequence(default_seq)
            self.shortcut_manager.set_shortcut(action, seq)

        self.load_shortcuts()
        QtWidgets.QMessageBox.information(
            self, "Przywrócono", "Przywrócono domyślne skróty."
        )

    def load_shortcuts(self):
        self.add_client_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("add_client")
        )
        self.add_product_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("add_product")
        )
        self.search_focus_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("search_focus")
        )
        self.send_report_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("send_report")
        )
        self.open_calculator_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("open_calculator")
        )
        self.switch_clients_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_clients")
        )
        self.switch_products_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_products")
        )
        self.switch_streaming_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_streaming")
        )
        self.switch_reports_edit.setKeySequence(
            self.shortcut_manager.get_shortcut("switch_reports")
        )

    def save_shortcuts(self):
        shortcuts = {
            "add_client": self.add_client_edit.keySequence(),
            "add_product": self.add_product_edit.keySequence(),
            "search_focus": self.search_focus_edit.keySequence(),
            "send_report": self.send_report_edit.keySequence(),
            "open_calculator": self.open_calculator_edit.keySequence(),
            "switch_clients": self.switch_clients_edit.keySequence(),
            "switch_products": self.switch_products_edit.keySequence(),
            "switch_streaming": self.switch_streaming_edit.keySequence(),
            "switch_reports": self.switch_reports_edit.keySequence(),
        }

        sequences = [seq for seq in shortcuts.values() if not seq.isEmpty()]
        seq_strings = [seq.toString() for seq in sequences]
        if len(seq_strings) != len(set(seq_strings)):
            QtWidgets.QMessageBox.warning(
                self,
                "Konflikt",
                "Skróty nie mogą być takie same.\n"
                "Proszę zmienić duplikujące się skróty.",
            )
            return

        errors = []
        for action, seq in shortcuts.items():
            success, msg = self.shortcut_manager.set_shortcut(action, seq)
            if not success:
                errors.append(f"- {action}: {msg}")

        if errors:
            QtWidgets.QMessageBox.warning(
                self,
                "Błąd zapisu",
                "Niektóre skróty nie zostały zapisane:\n" + "\n".join(errors),
            )
            return

        self.shortcut_manager.save()

        self.shortcuts_changed.emit()

        QtWidgets.QMessageBox.information(
            self, "Sukces", "Skróty zostały zapisane."
        )

    def showEvent(self, event):
        """Odświeża pola przy każdym otwarciu okna."""
        self.load_shortcuts()
        super().showEvent(event)