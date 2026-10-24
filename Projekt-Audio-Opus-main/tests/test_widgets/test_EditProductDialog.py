from unittest.mock import patch

from PySide6 import QtWidgets

from GUI.Widgets.Dialogs.EditProductDialog import EditProductDialog


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


LOAD_DATABASE = (
    "GUI.Widgets.Dialogs.EditProductDialog.database_controller.load_database"
)
ITEM_MODIFY = (
    "GUI.Widgets.Dialogs.EditProductDialog.database_controller.item_modify"
)


@patch(LOAD_DATABASE, return_value=[])
def test_threshold_row_hidden_for_instant(_load):
    _app()
    product = {
        "id": 1,
        "title": "Książka",
        "cut": 25,
        "settlement type": "instant",
        "threshold": 0,
    }

    dialog = EditProductDialog(product)

    assert dialog.form_layout.isRowVisible(dialog.threshold_widget) is False
    # Procent (prowizja AO) obowiązuje przy obu typach - zostaje aktywny.
    assert dialog.cut_widget.isEnabled() is True


@patch(LOAD_DATABASE, return_value=[])
def test_threshold_row_appears_after_switching_to_threshold(_load):
    _app()
    product = {
        "id": 2,
        "title": "Książka",
        "cut": 25,
        "settlement type": "instant",
        "threshold": 0,
    }

    dialog = EditProductDialog(product)
    dialog.settlement_widget.setCurrentText("threshold")

    assert dialog.form_layout.isRowVisible(dialog.threshold_widget) is True


@patch(ITEM_MODIFY)
@patch(LOAD_DATABASE, return_value=[])
def test_instant_save_keeps_commission_and_zeros_threshold(_load, item_modify):
    _app()
    product = {
        "id": 7,
        "title": "Książka",
        "cut": 0,
        "settlement type": "instant",
        "threshold": 0,
    }

    dialog = EditProductDialog(product)
    dialog.settlement_widget.setCurrentText("instant")
    dialog.cut_widget.setText("30")

    dialog.save()

    saved = {
        call.args[1]: call.args[2] for call in item_modify.call_args_list
    }
    assert saved["settlement type"] == "instant"
    assert saved["cut"] == 30
    assert saved["threshold"] == 0.0


@patch(ITEM_MODIFY)
@patch(LOAD_DATABASE, return_value=[])
def test_threshold_save_keeps_both_values(_load, item_modify):
    _app()
    product = {
        "id": 8,
        "title": "Książka",
        "cut": 10,
        "settlement type": "threshold",
        "threshold": 100,
    }

    dialog = EditProductDialog(product)
    dialog.settlement_widget.setCurrentText("threshold")
    dialog.cut_widget.setText("40")
    dialog.threshold_widget.setText("2500")

    dialog.save()

    saved = {
        call.args[1]: call.args[2] for call in item_modify.call_args_list
    }
    assert saved["settlement type"] == "threshold"
    assert saved["cut"] == 40
    assert saved["threshold"] == 2500.0
