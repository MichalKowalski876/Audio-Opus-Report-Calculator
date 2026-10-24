import pytest

from PySide6 import QtWidgets, QtGui

from GUI.Widgets.CrudTable.NumericDelegate import NumericDelegate


@pytest.fixture(scope="session")
def app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def test_create_int_editor(app):
    delegate = NumericDelegate(int)
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        None,
    )

    assert isinstance(editor, QtWidgets.QLineEdit)
    assert isinstance(editor.validator(), QtGui.QIntValidator)


def test_create_float_editor(app):
    delegate = NumericDelegate(float)
    parent = QtWidgets.QWidget()

    editor = delegate.createEditor(
        parent,
        QtWidgets.QStyleOptionViewItem(),
        None,
    )

    assert isinstance(editor, QtWidgets.QLineEdit)
    assert isinstance(editor.validator(), QtGui.QDoubleValidator)
    assert editor.validator().decimals() == 2
