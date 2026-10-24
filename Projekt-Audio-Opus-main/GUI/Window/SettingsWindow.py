from PySide6 import QtWidgets, QtCore

from GUI.Widgets.Settings.KeyBindSettings import KeyBindSettings
from GUI.Widgets.Settings.SMTPSettingsPanel import SMTPSettings
from GUI.Widgets.Settings.AppearanceSettings import AppearanceSettings
from GUI.Widgets.Settings.DataSettings import DataSettings
from GUI.Widgets.Settings.DebugSettings import DebugSettings


class SettingsWindow(QtWidgets.QDialog):
    shortcuts_changed = QtCore.Signal()
    data_imported = QtCore.Signal()

    # Kolejność sekcji jest ustalana w __init__ (add_section) - "Dane" jest
    # zawsze trzecią dodawaną sekcją, więc jej indeks jest stały.
    DATA_SECTION_INDEX = 2

    def __init__(self, shortcut_manager, parent=None, initial_section=0):
        super().__init__(parent)

        self.shortcut_manager = shortcut_manager

        self.setWindowTitle("Ustawienia")
        self.resize(800, 500)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        sidebar_widget = QtWidgets.QWidget()
        sidebar_widget.setFixedWidth(200)

        self.sidebar = QtWidgets.QVBoxLayout(sidebar_widget)
        self.sidebar.setContentsMargins(0, 0, 0, 0)
        self.sidebar.setSpacing(8)

        self.section_buttons = []

        self.stack = QtWidgets.QStackedWidget()

        self.add_section("Wygląd", AppearanceSettings())
        self.add_section("E-mail", SMTPSettings())

        self.data_tab = DataSettings()
        self.data_tab.data_imported.connect(self.data_imported)
        self.data_section_index = self.add_section("Dane", self.data_tab)

        self.add_section("Debugowanie", DebugSettings())

        self.key_bind_tab = KeyBindSettings(self.shortcut_manager)
        self.key_bind_tab.shortcuts_changed.connect(self.shortcuts_changed)
        self.add_section("Skróty klawiszowe", self.key_bind_tab)

        self.sidebar.addStretch()

        vertical_line = QtWidgets.QFrame()
        vertical_line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        vertical_line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        vertical_line.setObjectName("verticalDivider")

        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(vertical_line)
        main_layout.addWidget(self.stack, 1)

        self.change_section(initial_section)

    def add_section(self, name, widget):
        index = self.stack.count()

        button = QtWidgets.QPushButton(name)
        button.setObjectName("sidebarSectionButton")
        button.setCheckable(True)

        button.clicked.connect(
            lambda checked, i=index: self.change_section(i)
        )

        self.section_buttons.append(button)

        self.sidebar.addWidget(button)

        self.stack.addWidget(widget)

        return index

    def change_section(self, index):
        self.stack.setCurrentIndex(index)

        for i, button in enumerate(self.section_buttons):
            button.setChecked(i == index)
