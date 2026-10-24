from PySide6 import QtWidgets


def confirm_yes_no(parent, title: str, text: str, default_no: bool = True) -> bool:

    box = QtWidgets.QMessageBox(parent)
    box.setIcon(QtWidgets.QMessageBox.Icon.Question)
    box.setWindowTitle(title)
    box.setText(text)

    yes_button = box.addButton("Tak", QtWidgets.QMessageBox.ButtonRole.YesRole)
    no_button = box.addButton("Nie", QtWidgets.QMessageBox.ButtonRole.NoRole)

    box.setDefaultButton(no_button if default_no else yes_button)

    box.exec()

    return box.clickedButton() is yes_button
