from datetime import datetime

from PySide6 import QtWidgets, QtCore, QtGui

from platforms.manual import (
    ManualReportError,
    add_streaming_platform,
    attach_platform_report,
    load_streaming_platforms,
)
from platforms.xlsx_reports import XlsxReportError, detect_report_years


def prompt_add_streaming_platform(parent=None):
    """Pyta o nazwe i dodaje platforme wspolnym mechanizmem GUI."""
    platform_name, accepted = QtWidgets.QInputDialog.getText(
        parent,
        "Dodaj platformę",
        "Nazwa platformy:",
    )
    if not accepted:
        return None

    try:
        platform, created = add_streaming_platform(platform_name)
    except ManualReportError as error:
        QtWidgets.QMessageBox.warning(
            parent,
            "Dodawanie platformy",
            str(error),
        )
        return None

    selected_name = str(platform.get("name", ""))
    if created:
        QtWidgets.QMessageBox.information(
            parent,
            "Dodano platformę",
            f"Dodano platformę {selected_name}.",
        )
    else:
        QtWidgets.QMessageBox.information(
            parent,
            "Platforma już istnieje",
            f"Platforma {selected_name} znajduje się już na liście.",
        )
    return platform


class ManualPlatformReportDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, source_path=None):
        super().__init__(parent)

        self.attached_report_path = None
        self.source_path = source_path
        self.mail_window = None
        self.setWindowTitle("Ręczne dodawanie raportu")
        self.resize(580, 320)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QtWidgets.QLabel("Dodaj raport platformy")
        title.setProperty("role", "Title")
        layout.addWidget(title)

        description_text = (
            "Wybierz istniejącą platformę albo dodaj nową, następnie określ "
            "rok raportu i wskaż plik."
            if self.source_path is None
            else "Wybierz platformę i rok, aby dodać pobrany załącznik jako raport."
        )
        description = QtWidgets.QLabel(description_text)
        description.setWordWrap(True)
        layout.addWidget(description)

        form = QtWidgets.QFormLayout()
        form.setSpacing(10)

        platform_row = QtWidgets.QHBoxLayout()
        self.platform_combo = QtWidgets.QComboBox()
        self.platform_combo.setMinimumWidth(280)
        platform_row.addWidget(self.platform_combo, 1)

        self.add_platform_button = QtWidgets.QPushButton("Dodaj platformę")
        self.add_platform_button.clicked.connect(self.add_platform)
        platform_row.addWidget(self.add_platform_button)
        form.addRow("Platforma:", platform_row)

        self.year_spin = QtWidgets.QSpinBox()
        self.year_spin.setRange(1900, 9999)
        self.year_spin.setValue(datetime.now().year)
        form.addRow("Rok raportu:", self.year_spin)

        layout.addLayout(form)
        layout.addStretch()

        action_layout = QtWidgets.QHBoxLayout()
        action_layout.addStretch()

        self.attach_report_button = QtWidgets.QPushButton(
            "Załącz raport z pulpitu"
        )
        self.attach_report_button.setMinimumWidth(175)
        self.attach_report_button.clicked.connect(self.attach_report)
        action_layout.addWidget(self.attach_report_button)

        self.attach_mail_report_button = QtWidgets.QPushButton(
            "Załącz raport z maila"
        )
        self.attach_mail_report_button.setMinimumWidth(165)
        self.attach_mail_report_button.clicked.connect(
            self.open_mail_report_window
        )
        action_layout.addWidget(self.attach_mail_report_button)

        close_button = QtWidgets.QPushButton("Zamknij")
        close_button.clicked.connect(self.reject)
        action_layout.addWidget(close_button)
        layout.addLayout(action_layout)

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

        self.reload_platforms()

    def _handle_enter_pressed(self):
        if not self.isVisible():
            return
        if self.attach_report_button.isEnabled():
            self.attach_report()

    def reload_platforms(self, selected_name: str | None = None):
        try:
            platforms = load_streaming_platforms()
        except ManualReportError as error:
            QtWidgets.QMessageBox.warning(
                self,
                "Lista platform",
                str(error),
            )
            platforms = []

        self.platform_combo.clear()
        for platform in platforms:
            name = str(platform.get("name", "")).strip()
            if name:
                self.platform_combo.addItem(name, platform.get("id"))

        if selected_name:
            index = self.platform_combo.findText(selected_name)
            if index >= 0:
                self.platform_combo.setCurrentIndex(index)

        self.attach_report_button.setEnabled(self.platform_combo.count() > 0)

    def add_platform(self):
        platform = prompt_add_streaming_platform(self)
        if platform is None:
            return
        selected_name = str(platform.get("name", ""))
        self.reload_platforms(selected_name)

    def open_mail_report_window(self):
        from GUI.Window.MailDebugWindow import MailDebugWindow

        if self.mail_window is None:
            self.mail_window = MailDebugWindow(self)
            self.mail_window.report_selected.connect(
                self._attach_selected_mail_report
            )

        self.mail_window.show()
        self.mail_window.raise_()
        self.mail_window.activateWindow()

    def _attach_selected_mail_report(self, source_path):
        self.source_path = source_path
        self.attach_report()

    def attach_report(self):
        platform_name = self.platform_combo.currentText().strip()
        if not platform_name:
            QtWidgets.QMessageBox.warning(
                self,
                "Brak platformy",
                "Wybierz platformę albo dodaj nową.",
            )
            return

        source_path = self.source_path
        if source_path is None:
            source_path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Wybierz raport",
                "",
                (
                    "Pliki raportów (*.xlsx *.xls *.csv *.ods *.pdf *.zip);;"
                    "Wszystkie pliki (*.*)"
                ),
            )
            if not source_path:
                return

        selected_year = self.year_spin.value()
        try:
            content_years = detect_report_years(
                source_path,
                platform_key=platform_name,
            )
        except XlsxReportError:
            # Nowy układ raportu może nie mieć jeszcze konfiguracji kolumn.
            # Rok zostanie sprawdzony ponownie bezpośrednio po jej zapisaniu.
            content_years = ()

        if len(content_years) > 1:
            years_text = ", ".join(str(year) for year in content_years)
            QtWidgets.QMessageBox.critical(
                self,
                "Raport obejmuje kilka lat",
                (
                    f"W raporcie znaleziono dane z lat: {years_text}.\n\n"
                    "Jeden plik może być przypisany tylko do jednego roku. "
                    "Podziel raport na osobne pliki przed dodaniem."
                ),
            )
            return

        if content_years and content_years[0] != selected_year:
            detected_year = content_years[0]
            answer = QtWidgets.QMessageBox.question(
                self,
                "Nieprawidłowy rok raportu",
                (
                    f"Wybrano rok {selected_year}, ale daty w raporcie dotyczą "
                    f"roku {detected_year}.\n\n"
                    f"Zapisać raport w katalogu roku {detected_year}?"
                ),
                (
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.Cancel
                ),
                QtWidgets.QMessageBox.StandardButton.Yes,
            )
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
            selected_year = detected_year
            self.year_spin.setValue(detected_year)

        try:
            destination = attach_platform_report(
                source_path,
                platform_name,
                selected_year,
            )
        except ManualReportError as error:
            QtWidgets.QMessageBox.critical(
                self,
                "Błąd dodawania raportu",
                str(error),
            )
            return

        self.attached_report_path = destination
        QtWidgets.QMessageBox.information(
            self,
            "Dodano raport",
            f"Raport został zapisany jako:\n{destination}",
        )
        self.accept()
