from PySide6 import QtWidgets

from GUI.Window.HelpWindow import HelpWindow


class HelpButton(QtWidgets.QPushButton):
    def __init__(self, section_id: str, about_text: str, parent=None):
        super().__init__("?", parent)

        self.section_id = section_id
        self.about = about_text

        self.setFixedSize(30, 30)
        self.setToolTip(about_text)
        self.setProperty("role", "Help")

        self.clicked.connect(self.open_help)

    def open_help(self):
        window = HelpWindow(self.window())
        window.open_section(self.section_id)
        window.exec()