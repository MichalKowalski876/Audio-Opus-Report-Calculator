from PySide6 import QtWidgets

from GUI.Widgets.Buttons.Table.AddTableButton import AddTableButton


def _app():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


def _form_with_settlement(initial_type):
    container = QtWidgets.QWidget()
    layout = QtWidgets.QFormLayout(container)

    settlement = QtWidgets.QComboBox()
    settlement.setEditable(True)
    settlement.addItems(["instant", "threshold"])
    settlement.setCurrentText(initial_type)

    threshold = QtWidgets.QLineEdit("50")

    layout.addRow("Typ Rozliczenia:", settlement)
    layout.addRow("Próg:", threshold)

    return container, layout, settlement, threshold


def test_threshold_row_hidden_and_cleared_for_instant():
    _app()
    _container, layout, settlement, threshold = _form_with_settlement("instant")

    AddTableButton._bind_threshold_visibility(layout, settlement, threshold)

    assert layout.isRowVisible(threshold) is False
    assert threshold.text() == ""


def test_threshold_row_visible_for_threshold():
    _app()
    _container, layout, settlement, threshold = _form_with_settlement("threshold")

    AddTableButton._bind_threshold_visibility(layout, settlement, threshold)

    assert layout.isRowVisible(threshold) is True
    assert threshold.text() == "50"


def test_threshold_row_follows_settlement_type_changes():
    _app()
    _container, layout, settlement, threshold = _form_with_settlement("instant")

    AddTableButton._bind_threshold_visibility(layout, settlement, threshold)

    settlement.setCurrentText("threshold")
    assert layout.isRowVisible(threshold) is True

    settlement.setCurrentText("instant")
    assert layout.isRowVisible(threshold) is False


def test_empty_settlement_type_hides_threshold():
    _app()
    _container, layout, settlement, threshold = _form_with_settlement("")

    AddTableButton._bind_threshold_visibility(layout, settlement, threshold)

    assert layout.isRowVisible(threshold) is False


def test_bind_is_noop_without_threshold_widget():
    _app()
    layout = QtWidgets.QFormLayout(QtWidgets.QWidget())
    settlement = QtWidgets.QComboBox()

    # Nie powinno rzucić wyjątku, gdy formularz nie ma pola "Próg".
    AddTableButton._bind_threshold_visibility(layout, settlement, None)
