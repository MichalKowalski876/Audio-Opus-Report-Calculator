from PySide6 import QtWidgets, QtCore


class ComboDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(self, options: list[str], parent=None):
        super().__init__(parent)
        self.options = options

    def createEditor(self, parent, option, index):
        editor = QtWidgets.QComboBox(parent)
        editor.addItems(self.options)
        editor.setEditable(False)
        return editor

    def setEditorData(self, editor, index):
        current_text = index.data(
            QtCore.Qt.ItemDataRole.DisplayRole
        )

        idx = editor.findText(str(current_text))

        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(
            index,
            editor.currentText(),
            QtCore.Qt.ItemDataRole.EditRole,
        )

