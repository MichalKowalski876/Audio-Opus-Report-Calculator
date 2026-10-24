from PySide6.QtWidgets import QApplication, QAbstractItemView

from GUI.Widgets.CrudTable.Table import Table


def test_apply_settlement_rules_clears_only_threshold_for_instant():
    app = QApplication.instance() or QApplication([])

    table = Table(["Id", "Tytuł", "Procent", "Typ Rozliczenia", "Próg"], "products")

    item = {"title": "Book", "cut": 10, "settlement type": "instant", "threshold": 50}

    normalized = table.apply_settlement_rules(item)

    # Procent (prowizja AO) obowiązuje też przy "instant" - zostaje.
    assert normalized["cut"] == 10
    # Próg dotyczy tylko rozliczenia "po progu".
    assert normalized["threshold"] == 0.0


def test_apply_settlement_rules_keeps_values_for_threshold():
    app = QApplication.instance() or QApplication([])

    table = Table(["Id", "Tytuł", "Procent", "Typ Rozliczenia", "Próg"], "products")

    item = {"title": "Book", "cut": 15, "settlement type": "threshold", "threshold": 20}

    normalized = table.apply_settlement_rules(item)

    assert normalized["cut"] == 15
    assert normalized["threshold"] == 20


def test_table_uses_smooth_pixel_scrolling():
    app = QApplication.instance() or QApplication([])

    table = Table(["Id", "Tytuł", "ISBN"], "products")

    assert (
        table.table.verticalScrollMode()
        == QAbstractItemView.ScrollMode.ScrollPerPixel
    )
    assert (
        table.table.horizontalScrollMode()
        == QAbstractItemView.ScrollMode.ScrollPerPixel
    )
    assert table.table.verticalScrollBar().singleStep() == 12
    assert table.table.horizontalScrollBar().singleStep() == 12
