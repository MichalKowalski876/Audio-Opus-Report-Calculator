from PySide6 import QtWidgets


class HelpPage(QtWidgets.QScrollArea):
    def __init__(self, title: str, description: str = "", parent=None):
        super().__init__(parent)

        self.setWidgetResizable(True)
        self.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        self.content = QtWidgets.QWidget()
        self.setWidget(self.content)

        self.layout = QtWidgets.QVBoxLayout(self.content)
        self.layout.setContentsMargins(24, 20, 24, 20)
        self.layout.setSpacing(12)

        title_label = QtWidgets.QLabel(title)
        title_label.setProperty("role", "Title")

        self.layout.addWidget(title_label)

        if description:
            description_label = QtWidgets.QLabel(description)
            description_label.setWordWrap(True)

            self.layout.addWidget(description_label)

    def add_section(self, title: str, text: str = ""):
        group = QtWidgets.QGroupBox(title)
        group_layout = QtWidgets.QVBoxLayout(group)

        if text:
            label = QtWidgets.QLabel(text)
            label.setWordWrap(True)

            group_layout.addWidget(label)

        self.layout.addWidget(group)

        return group_layout

    def add_text(self, text: str):
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)

        self.layout.addWidget(label)

        return label

    def add_step(self, number: int, text: str):
        label = QtWidgets.QLabel(
            f"<b>{number}.</b> {text}"
        )

        label.setWordWrap(True)

        self.layout.addWidget(label)

        return label

    def finish(self):
        self.layout.addStretch()