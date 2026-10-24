from unittest.mock import MagicMock

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QApplication

from GUI.Tabs.ProductsTab import ProductsTab


def test_products_tab_fuzzy_search_toggle():
    app = QApplication.instance() or QApplication([])

    tab = ProductsTab()
    tab.book_items = [MagicMock()]
    tab.book_items[0].product = {
        "title": "Ildefons Rozrabia",
        "author": "Karolina Bast",
        "publisher": "Audio Opus",
        "isbn": "978-83-68950-01-4",
    }

    tab.search("ildfns")
    assert tab.book_items[0].setVisible.call_args[0][0] is True

    tab.fuzzy_search_toggle.setChecked(False)
    tab.search("ildfns")
    assert tab.book_items[0].setVisible.call_args[0][0] is False

    app.processEvents()


def test_products_tab_marks_best_fuzzy_match():
    app = QApplication.instance() or QApplication([])
    tab = ProductsTab()

    good_match = MagicMock()
    good_match.product = {
        "title": "Ildefons Rozrabia",
        "author": "Karolina Bast",
        "publisher": "Audio Opus",
        "isbn": "978-83-68950-01-4",
    }
    bad_match = MagicMock()
    bad_match.product = {
        "title": "Zwykła książka",
        "author": "Jan Kowalski",
        "publisher": "Inna firma",
        "isbn": "000-00-00000-00-0",
    }

    tab.book_items = [bad_match, good_match]
    tab.fuzzy_search_toggle.setChecked(True)

    tab.search("ildfns")

    good_calls = [call.args for call in good_match.setProperty.call_args_list]
    bad_calls = [call.args for call in bad_match.setProperty.call_args_list]

    assert ("recommended", True) in good_calls
    assert ("recommended", False) in bad_calls
    assert tab.selected_product == good_match.product

    app.processEvents()


def test_products_tab_enter_opens_best_fuzzy_match_for_edit():
    app = QApplication.instance() or QApplication([])
    tab = ProductsTab()

    good_match = MagicMock()
    good_match.product = {
        "title": "Ildefons Rozrabia",
        "author": "Karolina Bast",
        "publisher": "Audio Opus",
        "isbn": "978-83-68950-01-4",
    }
    bad_match = MagicMock()
    bad_match.product = {
        "title": "Zwykła książka",
        "author": "Jan Kowalski",
        "publisher": "Inna firma",
        "isbn": "000-00-00000-00-0",
    }

    tab.book_items = [bad_match, good_match]
    tab.fuzzy_search_toggle.setChecked(True)
    tab.search("ildfns")

    tab.edit_selected_product = MagicMock()
    tab.on_search_return_pressed()

    tab.edit_selected_product.assert_called_once_with()
    assert tab.selected_product == good_match.product

    app.processEvents()


def test_products_tab_arrow_key_moves_between_visible_results():
    app = QApplication.instance() or QApplication([])
    tab = ProductsTab()

    first = MagicMock()
    first.product = {"id": 1, "title": "A"}
    second = MagicMock()
    second.product = {"id": 2, "title": "B"}
    third = MagicMock()
    third.product = {"id": 3, "title": "C"}

    tab.book_items = [first, second, third]
    for item in tab.book_items:
        item.isVisible.return_value = True
        item.set_selected = MagicMock()

    tab.select_product(first.product)
    event = QtGui.QKeyEvent(
        QtGui.QKeyEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Down,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    tab.keyPressEvent(event)

    assert tab.selected_product == second.product

    event = QtGui.QKeyEvent(
        QtGui.QKeyEvent.Type.KeyPress,
        QtCore.Qt.Key.Key_Up,
        QtCore.Qt.KeyboardModifier.NoModifier,
    )
    tab.keyPressEvent(event)

    assert tab.selected_product == first.product

    app.processEvents()
