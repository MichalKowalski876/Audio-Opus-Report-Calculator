import os
import json
from PySide6 import QtWidgets, QtGui

from core import database_controller
from GUI.Widgets.confirm import confirm_yes_no

# Sciezka bezwzgledna wspolna z reszta aplikacji. Wczesniej "Databases"
# bylo liczone od katalogu uruchomienia, wiec program czytal i zapisywal
# konfiguracje w przypadkowym miejscu.
DB_DIR = database_controller.FOLDER
os.makedirs(DB_DIR, exist_ok=True)
EMAIL_HISTORY_FILE = os.path.join(DB_DIR, "email_history.json")


class EmailHistoryDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Historia wysyłki e-maili")
        self.resize(700, 450)

        self.all_history = []

        layout = QtWidgets.QVBoxLayout(self)

        filters_layout = QtWidgets.QHBoxLayout()

        self.search_input = QtWidgets.QLineEdit()
        self.search_input.setPlaceholderText("Szukaj po adresie e-mail lub nazwie pliku...")
        self.search_input.textChanged.connect(self.apply_filters)

        self.status_filter = QtWidgets.QComboBox()
        self.status_filter.addItems(["Wszystkie statusy", "Sukces", "Błąd"])
        self.status_filter.currentIndexChanged.connect(self.apply_filters)

        filters_layout.addWidget(self.search_input, stretch=3)
        filters_layout.addWidget(self.status_filter, stretch=1)

        layout.addLayout(filters_layout)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Data", "Odbiorca", "Plik", "Status"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        layout.addWidget(self.table)

        self.result_count_label = QtWidgets.QLabel("")
        layout.addWidget(self.result_count_label)

        buttons_layout = QtWidgets.QHBoxLayout()

        self.refresh_button = QtWidgets.QPushButton("Odśwież")
        self.refresh_button.clicked.connect(self.load_history)

        self.clear_filters_button = QtWidgets.QPushButton("Wyczyść filtry")
        self.clear_filters_button.clicked.connect(self.clear_filters)

        self.clear_button = QtWidgets.QPushButton("Wyczyść historię")
        self.clear_button.clicked.connect(self.clear_history)

        buttons_layout.addWidget(self.refresh_button)
        buttons_layout.addWidget(self.clear_filters_button)
        buttons_layout.addStretch()
        buttons_layout.addWidget(self.clear_button)

        layout.addLayout(buttons_layout)

        self.load_history()

    def load_history(self):
        if not os.path.exists(EMAIL_HISTORY_FILE):
            self.all_history = []
        else:
            try:
                with open(EMAIL_HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.all_history = json.load(f)
            except Exception:
                self.all_history = []

        self.apply_filters()

    def apply_filters(self):
        search_text = self.search_input.text().strip().lower()
        status_selection = self.status_filter.currentText()

        filtered = []
        for entry in reversed(self.all_history):
            receiver = str(entry.get("receiver", "")).lower()
            file_name = os.path.basename(entry.get("file", "")).lower()

            if search_text and search_text not in receiver and search_text not in file_name:
                continue

            success = entry.get("success", False)
            if status_selection == "Sukces" and not success:
                continue
            if status_selection == "Błąd" and success:
                continue

            filtered.append(entry)

        self.populate_table(filtered)

    def populate_table(self, entries):
        self.table.setRowCount(0)

        for entry in entries:
            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(entry.get("timestamp", "")))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(entry.get("receiver", "")))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem(os.path.basename(entry.get("file", ""))))

            success = entry.get("success", False)
            status_item = QtWidgets.QTableWidgetItem("Sukces" if success else "Błąd")
            if not success:
                status_item.setForeground(QtGui.QColor("red"))
                if entry.get("error"):
                    status_item.setToolTip(entry["error"])

            self.table.setItem(row, 3, status_item)

        total = len(self.all_history)
        shown = len(entries)
        if shown == total:
            self.result_count_label.setText(f"Liczba wpisów: {total}")
        else:
            self.result_count_label.setText(f"Wyświetlono {shown} z {total} wpisów")

    def clear_filters(self):
        self.search_input.clear()
        self.status_filter.setCurrentIndex(0)

    def clear_history(self):
        confirmed = confirm_yes_no(
            self,
            "Potwierdzenie",
            "Czy na pewno chcesz wyczyścić całą historię wysyłki?",
        )

        if confirmed:
            try:
                with open(EMAIL_HISTORY_FILE, "w", encoding="utf-8") as f:
                    json.dump([], f, indent=4, ensure_ascii=False)
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Błąd", f"Nie udało się wyczyścić historii: {e}")

            self.load_history()