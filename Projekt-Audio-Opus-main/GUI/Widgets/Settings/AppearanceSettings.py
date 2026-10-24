from PySide6 import QtGui, QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.style.theme_manager import ThemeManager, accent_problem


class AppearanceSettings(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)

        title_label = QtWidgets.QLabel("Wygląd")
        title_label.setProperty("role", "Title")
        layout.addWidget(title_label)

        theme_group = QtWidgets.QGroupBox("Motyw")
        theme_layout = QtWidgets.QVBoxLayout(theme_group)

        self.dark_theme_checkbox = QtWidgets.QCheckBox()

        is_dark = ThemeManager.get_current_theme() == "dark"
        self.dark_theme_checkbox.setChecked(is_dark)
        self.update_theme_label(is_dark)

        self.dark_theme_checkbox.toggled.connect(
            self.on_theme_toggled
        )

        theme_layout.addWidget(self.dark_theme_checkbox)

        accent_group = QtWidgets.QGroupBox("Kolor przewodni")
        accent_layout = QtWidgets.QHBoxLayout(accent_group)

        self.accent_button = QtWidgets.QPushButton("Wybierz kolor")
        self.accent_button.clicked.connect(self.on_accent_clicked)

        self.accent_preview = QtWidgets.QLabel()
        self.accent_preview.setFixedSize(24, 24)
        self.accent_preview.setFrameShape(
            QtWidgets.QFrame.Shape.Box
        )
        self.accent_preview.setLineWidth(1)

        accent_layout.addWidget(self.accent_button)
        accent_layout.addWidget(self.accent_preview)

        layout.addWidget(theme_group)
        layout.addWidget(accent_group)

        layout.addStretch()

        self.update_accent_preview()

    def update_theme_label(self, is_dark: bool):
        self.dark_theme_checkbox.setText(
            "Ciemny motyw" if is_dark else "Jasny motyw"
        )

    def update_accent_preview(self):
        accent = ThemeManager.get_current_accent()

        self.accent_preview.setStyleSheet(
            f"""
            background: {accent};
            border: 1px solid #888888;
            border-radius: 4px;
            """
        )

    def on_theme_toggled(self, checked: bool):
        theme = "dark" if checked else "light"

        app = QApplication.instance()

        if app is not None:
            previous_accent = ThemeManager.get_current_accent()
            ThemeManager.apply_theme(app, theme)
            self.update_accent_preview()
            if ThemeManager.get_current_accent() != previous_accent:
                QtWidgets.QMessageBox.information(
                    self,
                    "Kolor przewodni",
                    "Dotychczasowy kolor przewodni byłby nieczytelny w tym motywie, "
                    "więc przywrócono kolor domyślny.",
                )

        self.update_theme_label(checked)

    def on_accent_clicked(self):
        color = QtWidgets.QColorDialog.getColor(
            QtGui.QColor(
                ThemeManager.get_current_accent()
            ),
            self,
            "Wybierz kolor przewodni"
        )

        if not color.isValid():
            return

        problem = accent_problem(color.name(), ThemeManager.get_current_theme())
        if problem:
            QtWidgets.QMessageBox.warning(
                self,
                "Niedozwolony kolor",
                f"{problem}\nWybierz inny kolor przewodni.",
            )
            return

        app = QApplication.instance()

        if app is not None:
            ThemeManager.apply_theme(
                app,
                accent=color.name()
            )

            self.update_accent_preview()