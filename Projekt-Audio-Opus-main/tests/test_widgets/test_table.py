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
    return ComboDelegate(["instant", "threshold", "none"])


def test_create_editor(delegate):
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        QtCore.QModelIndex(),
    )

    assert isinstance(editor, QtWidgets.QComboBox)
    assert editor.count() == 3
    assert [editor.itemText(i) for i in range(3)] == [
        "instant",
        "threshold",
        "none",
    ]

    parent.close()


def test_editor_is_not_editable(delegate):
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        QtCore.QModelIndex(),
    )

    assert not editor.isEditable()

    parent.close()


def test_set_editor_data(delegate):
    parent = QtWidgets.QWidget()
    model = QtGui.QStandardItemModel(1, 1)
    index = model.index(0, 0)

    model.setData(index, "threshold")

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        index,
    )

    delegate.setEditorData(editor, index)

    assert editor.currentText() == "threshold"

    parent.close()


def test_set_editor_data_unknown_value(delegate):
    parent = QtWidgets.QWidget()
    model = QtGui.QStandardItemModel(1, 1)
    index = model.index(0, 0)

    model.setData(index, "unknown")

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        index,
    )

    delegate.setEditorData(editor, index)

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
    delegate.setModelData(editor, model, index)

    assert model.data(
        index,
        QtCore.Qt.ItemDataRole.DisplayRole,
    ) == "none"

    parent.close()
