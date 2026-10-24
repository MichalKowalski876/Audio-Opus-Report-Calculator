from PySide6 import QtWidgets, QtGui


class NumericDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, value_type=float, parent=None):
        super().__init__(parent)
        self.value_type = value_type

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QLineEdit(parent)

        if self.value_type is int:
            editor.setValidator(QtGui.QIntValidator(editor))
        else:
            validator = QtGui.QDoubleValidator(editor)
            validator.setDecimals(2)
            editor.setValidator(validator)

        return editor
