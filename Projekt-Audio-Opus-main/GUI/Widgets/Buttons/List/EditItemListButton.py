from PySide6 import QtWidgets, QtCore


class EditItemListButton(QtWidgets.QPushButton):
    selected = QtCore.Signal()

    def __init__(self):
        super().__init__()

        self.setText("Edit")

        self.clicked.connect(self.on_clicked)

    def on_clicked(self):
        self.selected.emit()