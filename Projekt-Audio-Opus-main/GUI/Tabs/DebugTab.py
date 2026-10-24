from PySide6 import QtWidgets


class DebugTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        debug_title = QtWidgets.QLabel("Debug")
        debug_title.setProperty("role", "Title")

        debug_description = QtWidgets.QLabel(
            "Panel Debug służy do testowania nowych i eksperymentalnych funkcji aplikacji. "
            "Pozwala sprawdzać ich działanie przed umieszczeniem ich w docelowych "
            "częściach programu. Raporty z poczty dodasz w panelu Platformy."
        )
        debug_description.setWordWrap(True)

        layout.addWidget(debug_title)
        layout.addWidget(debug_description)

        layout.addStretch()
