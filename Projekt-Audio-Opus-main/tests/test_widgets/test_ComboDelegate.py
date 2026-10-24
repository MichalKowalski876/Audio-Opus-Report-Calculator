import pytest

from PySide6 import QtWidgets, QtCore, QtGui

from GUI.Widgets.CrudTable.ComboDelegate import ComboDelegate


@pytest.fixture(scope="session")
def app():
    return (
        QtWidgets.QApplication.instance()
        or QtWidgets.QApplication([])
    )


@pytest.fixture
def delegate(app):
    return ComboDelegate(
        ["instant", "threshold", "none"]
    )


def test_create_editor(delegate):
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        QtCore.QModelIndex(),
    )

    assert isinstance(
        editor,
        QtWidgets.QComboBox
    )

    assert editor.count() == 3
    assert editor.itemText(0) == "instant"
    assert editor.itemText(1) == "threshold"
    assert editor.itemText(2) == "none"

    parent.close()


def test_create_editor_is_not_editable(delegate):
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        QtCore.QModelIndex(),
    )

    assert isinstance(
        editor,
        QtWidgets.QComboBox
    )

    assert not editor.isEditable()

    parent.close()


def test_set_editor_data(delegate):
    parent = QtWidgets.QWidget()

    model = QtGui.QStandardItemModel(1, 1)

    index = model.index(0, 0)

    model.setData(
        index,
        "threshold",
        QtCore.Qt.ItemDataRole.DisplayRole,
    )

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        index,
    )

    delegate.setEditorData(
        editor,
        index,
    )

    assert editor.currentText() == "threshold"

    parent.close()


def test_set_editor_data_unknown_value(delegate):
    parent = QtWidgets.QWidget()

    model = QtGui.QStandardItemModel(1, 1)

    index = model.index(0, 0)

    model.setData(
        index,
        "unknown",
        QtCore.Qt.ItemDataRole.DisplayRole,
    )

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        index,
    )

    editor.setCurrentIndex(0)

    delegate.setEditorData(
        editor,
        index,
    )

    assert editor.currentText() == "instant"

    parent.close()


def test_set_model_data(delegate):
    parent = QtWidgets.QWidget()

    model = QtGui.QStandardItemModel(1, 1)

    index = model.index(0, 0)

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        index,
    )

    editor.setCurrentText("none")

    delegate.setModelData(
        editor,
        model,
        index,
    )

    assert model.data(
        index,
        QtCore.Qt.ItemDataRole.DisplayRole,
    ) == "none"

    parent.close()
from PySide6 import QtWidgets, QtCore


class ComboDelegate(QtWidgets.QStyledItemDelegate):
    def __init__(
        self,
        options: list[str],
        parent=None,
    ):
        super().__init__(parent)
        self.options = options

    def createEditor(
        self,
        parent,
        option,
        index,
    ):
        editor = QtWidgets.QComboBox(parent)
        editor.addItems(self.options)
        editor.setEditable(False)

        return editor

    def setEditorData(
        self,
        editor,
        index,
    ):
        current_text = index.data(
            QtCore.Qt.ItemDataRole.DisplayRole
        )

        idx = editor.findText(
            str(current_text)
        )

        if idx >= 0:
            editor.setCurrentIndex(idx)

    def setModelData(
        self,
        editor,
        model,
        index,
    ):
        model.setData(
            index,
            editor.currentText(),
            QtCore.Qt.ItemDataRole.EditRole,
        )
