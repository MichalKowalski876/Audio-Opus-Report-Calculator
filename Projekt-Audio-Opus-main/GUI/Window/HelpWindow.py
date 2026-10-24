from PySide6 import QtWidgets

from GUI.Widgets.Help.EmailHelp import EmailHelp
from GUI.Widgets.Help.IntroductionHelp import IntroductionHelp
from GUI.Widgets.Help.ClientsHelp import ClientsHelp
from GUI.Widgets.Help.ProductsHelp import ProductsHelp
from GUI.Widgets.Help.ReportHelp import ReportHelp
from GUI.Widgets.Help.StreamingHelp import StreamingHelp


class HelpWindow(QtWidgets.QDialog):
    def __init__(self, parent=None, section_id="introduction"):
        super().__init__(parent)

        self.setWindowTitle("Pomoc")
        self.resize(900, 600)

        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(16)

        sidebar_widget = QtWidgets.QWidget()
        sidebar_widget.setFixedWidth(200)

        self.sidebar = QtWidgets.QVBoxLayout(sidebar_widget)
        self.sidebar.setContentsMargins(0, 0, 0, 0)
        self.sidebar.setSpacing(8)

        self.section_buttons = []
        self.sections = {}

        self.stack = QtWidgets.QStackedWidget()

        self.add_section(
            "introduction",
            "Wprowadzenie",
            IntroductionHelp()
        )

        self.add_section(
            "clients",
            "Klienci",
            ClientsHelp()
        )

        self.add_section(
            "products",
            "Produkty",
            ProductsHelp()
        )

        self.add_section(
            "streamings",
            "Platformy",
            StreamingHelp()
        )

        self.add_section(
            "reports",
            "Raporty",
            ReportHelp()
        )

        self.add_section(
            "email",
            "Email",
            EmailHelp()
        )

        self.sidebar.addStretch()

        vertical_line = QtWidgets.QFrame()
        vertical_line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        vertical_line.setFrameShadow(QtWidgets.QFrame.Shadow.Plain)
        vertical_line.setObjectName("verticalDivider")

        main_layout.addWidget(sidebar_widget)
        main_layout.addWidget(vertical_line)
        main_layout.addWidget(self.stack, 1)

        self.open_section(section_id)

    def add_section(self, section_id, name, widget):
        index = self.stack.count()

        self.sections[section_id] = index

        button = QtWidgets.QPushButton(name)
        button.setObjectName("sidebarSectionButton")
        button.setCheckable(True)

        button.clicked.connect(
            lambda checked, i=index: self.change_section(i)
        )

        self.section_buttons.append(button)

        self.sidebar.addWidget(button)
        self.stack.addWidget(widget)

    def change_section(self, index):
        self.stack.setCurrentIndex(index)

        for i, button in enumerate(self.section_buttons):
            button.setChecked(i == index)

    def open_section(self, section_id):
        index = self.sections.get(section_id)

        if index is None:
            index = 0

        self.change_section(index)
