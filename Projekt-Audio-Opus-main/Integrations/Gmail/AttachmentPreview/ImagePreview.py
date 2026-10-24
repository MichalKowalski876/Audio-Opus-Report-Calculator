from PySide6 import QtWidgets, QtCore, QtGui


class ImagePreview(QtWidgets.QWidget):
    def __init__(self, data, parent=None):
        super().__init__(parent)

        self.data = data

        self.create_ui()

    def create_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        pixmap = QtGui.QPixmap()

        if not pixmap.loadFromData(self.data):
            error = QtWidgets.QLabel(
                "Nie udało się wyświetlić obrazu."
            )

            layout.addWidget(error)
            return

        image_label = QtWidgets.QLabel()

        image_label.setAlignment(
            QtCore.Qt.AlignmentFlag.AlignCenter
        )

        image_label.setPixmap(
            pixmap.scaled(
                750,
                500,
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
        )

        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(image_label)

        layout.addWidget(scroll)