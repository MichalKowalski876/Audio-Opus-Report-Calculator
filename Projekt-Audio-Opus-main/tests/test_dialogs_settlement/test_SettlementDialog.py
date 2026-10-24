import pytest
from unittest.mock import patch, MagicMock
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWidgets import QApplication

from core import settlement_numbers
from GUI.Widgets.Settlement.SettlementDialog import SettlementDialog
from platforms.settlement_amounts import PlatformAmount


def amount(product_id, platform_id, name, net, gross=None, periods=("2026-08",)):
    return PlatformAmount(
        product_id=product_id,
        platform_id=platform_id,
        platform_key=name.casefold(),
        platform_name=name,
        net=net,
        gross=gross,
        periods=periods,
        entries=1,
    )


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolate_settlement_numbers(tmp_path, monkeypatch):
    """Rejestr numerów rozliczeń pisze do bazy - w testach kierujemy go na tmp."""
    monkeypatch.setattr(
        "core.settlement_numbers.DATABASE_PATH", tmp_path / "settlements.sqlite"
    )


@pytest.fixture
def mock_db():
    with patch("GUI.Widgets.Settlement.SettlementDialog.database_controller") as mock:
        mock.load_database.side_effect = lambda name: {
            "clients": [{"id": 1, "name": "Test Client", "products": [1]}],
            "streamings": [{"id": 1, "name": "Spotify"}],
            "products": [{"id": 1, "title": "Test Book"}]
        }.get(name, [])
        mock.item_get.side_effect = lambda item_id, db: {
            "clients": {"id": 1, "name": "Test Client", "cut": 50, "products": [1]},
            "streamings": {"id": 1, "name": "Spotify", "cut": 10},
            "products": {"id": 1, "title": "Test Book"}
        }.get(db)
        yield mock


@pytest.fixture
def mock_report_gen():
    with patch("GUI.Widgets.Settlement.SettlementDialog.report_generator") as mock:
        mock.render_settlement_pdf_bytes.return_value = b"%PDF-1.4 mock bytes"
        mock.generate_settlement_pdf.return_value = "Reports/raport_Test_Client.pdf"
        yield mock


@pytest.fixture
def mock_amounts():
    """Odcina okno od prawdziwej bazy rozliczen - testy podaja kwoty wprost."""
    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods"
    ) as periods, patch(
        "GUI.Widgets.Settlement.SettlementDialog.load_amounts"
    ) as amounts, patch(
        "GUI.Widgets.Settlement.SettlementDialog.period_span"
    ) as span, patch(
        # Dopinanie pozycji pisze do bazy - w testach nie może ruszać prawdziwej.
        "GUI.Widgets.Settlement.SettlementDialog.relink_unmatched_rows"
    ) as relink:
        periods.return_value = ["2026-08", "2026-07"]
        amounts.return_value = {}
        span.return_value = None
        relink.return_value = 0
        yield amounts


@pytest.fixture
def settlement_dialog(mock_db, mock_report_gen, mock_amounts):
    dialog = SettlementDialog(email_mode=False)
    yield dialog


@pytest.fixture
def settlement_dialog_email(mock_db, mock_report_gen, mock_amounts):
    dialog = SettlementDialog(email_mode=True)
    yield dialog


def test_initialization_standard(settlement_dialog):
    assert settlement_dialog.email_mode is False
    assert settlement_dialog.windowTitle() == "Nowe rozliczenie"
    assert settlement_dialog.client_box.count() == 2  # pusta pozycja + 1 klient
    assert settlement_dialog.table.rowCount() == 1
    assert settlement_dialog.generate_button.text() == "Generuj raport PDF"


def test_initialization_email_mode(settlement_dialog_email):
    assert settlement_dialog_email.email_mode is True
    assert settlement_dialog_email.windowTitle() == "Wybór danych do wiadomości e-mail"
    assert settlement_dialog_email.generate_button.text() == "Generuj PDF i załącz do e-maila"
    assert settlement_dialog_email.attach_existing_button is not None


def test_add_empty_row(settlement_dialog):
    initial_rows = settlement_dialog.table.rowCount()
    settlement_dialog.add_empty_row(initial_rows)
    assert settlement_dialog.table.rowCount() == initial_rows + 1


# ==========================================================
# Usuwanie wiersza klawiszem Delete
# ==========================================================

def test_delete_row_shortcut_is_scoped_to_the_table(settlement_dialog):
    """Kontekst WidgetShortcut przypięty do tabeli (nie do okna) - dzięki
    temu Delete w trakcie edycji komórki kasuje znak, a nie wiersz."""
    shortcut = settlement_dialog.delete_row_shortcut

    assert shortcut.parent() is settlement_dialog.table
    assert shortcut.context() == QtCore.Qt.ShortcutContext.WidgetShortcut
    assert shortcut.key() == QtGui.QKeySequence(QtCore.Qt.Key.Key_Delete)


def test_delete_key_removes_the_selected_row(settlement_dialog):
    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)
    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)

    # Wypełniony wiersz + pusty na końcu do dopisywania kolejnych pozycji.
    assert settlement_dialog.table.rowCount() == 2
    settlement_dialog.table.selectRow(0)

    settlement_dialog.delete_row_shortcut.activated.emit()

    # Wiersz zniknął, a pusty wiersz na końcu został zachowany.
    assert settlement_dialog.table.rowCount() == 1
    assert settlement_dialog.table.cellWidget(0, 0).currentIndex() == 0


def test_delete_key_without_a_selected_row_does_nothing(settlement_dialog):
    settlement_dialog.table.clearSelection()
    settlement_dialog.table.setCurrentCell(-1, -1)
    rows_before = settlement_dialog.table.rowCount()

    settlement_dialog.delete_row_shortcut.activated.emit()

    assert settlement_dialog.table.rowCount() == rows_before


def test_collect_items_empty(settlement_dialog):
    items = settlement_dialog.collect_items(strict=True)
    assert items == []


def test_selecting_book_creates_one_row_for_each_streaming_service(settlement_dialog, mock_db):
    mock_db.load_database.side_effect = lambda name: {
        "clients": [{"id": 1, "name": "Test Client"}],
        "streamings": [
            {"id": 1, "name": "Spotify"},
            {"id": 2, "name": "Legimi"},
            {"id": 3, "name": "Storytel"},
        ],
        "products": [{"id": 1, "title": "Test Book"}]
    }.get(name, [])

    # Refresh the dialog's streaming list with the expanded fixture.
    settlement_dialog.streamings = mock_db.load_database("streamings")

    product_box = settlement_dialog.table.cellWidget(0, 0)
    product_box.setCurrentIndex(1)

    assert settlement_dialog.table.rowCount() == 4

    platform_names = []
    for row in range(3):
        platform_box = settlement_dialog.table.cellWidget(row, 1)
        platform_names.append(platform_box.currentText())
        assert settlement_dialog.table.cellWidget(row, 0).currentData() == 1
        assert settlement_dialog.table.item(row, 2).text() == "0"

    assert platform_names == ["Spotify", "Legimi", "Storytel"]
    assert settlement_dialog.table.cellWidget(3, 0).currentIndex() == 0


def test_collect_items_valid(settlement_dialog):
    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)

    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)

    revenue_item = settlement_dialog.table.item(0, 2)
    if revenue_item is None:
        revenue_item = QtWidgets.QTableWidgetItem()
        settlement_dialog.table.setItem(0, 2, revenue_item)

    revenue_item.setText("150.50")

    items = settlement_dialog.collect_items(strict=True)
    assert len(items) == 1
    assert items[0]["revenue"] == 150.50
    assert items[0]["product"]["id"] == 1
    assert items[0]["platform"]["id"] == 1

def test_collect_items_invalid_revenue_strict(settlement_dialog):
    product_box = settlement_dialog.table.cellWidget(0, 0)

    product_box.setCurrentIndex(1)

    platform_box = settlement_dialog.table.cellWidget(0, 1)
    revenue_item = settlement_dialog.table.item(0, 2)

    platform_box.setCurrentIndex(1)
    revenue_item.setText("niepoprawna_kwota")

    with pytest.raises(ValueError, match="Niepoprawna kwota wypłaty."):
        settlement_dialog.collect_items(strict=True)


@patch("PySide6.QtWidgets.QMessageBox.warning")
def test_generate_report_no_items(mock_warning, settlement_dialog):
    settlement_dialog.generate_report()
    mock_warning.assert_called_once()


@patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("Reports/raport_Test.pdf", "PDF"))
@patch("os.makedirs")
def test_generate_report_success(mock_makedirs, mock_file_dialog, settlement_dialog, mock_report_gen):
    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)

    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)

    revenue_item = settlement_dialog.table.item(0, 2)
    if revenue_item is None:
        revenue_item = QtWidgets.QTableWidgetItem()
        settlement_dialog.table.setItem(0, 2, revenue_item)

    revenue_item.setText("200")

    with patch("PySide6.QtWidgets.QMessageBox.information"):
        settlement_dialog.generate_report()

    assert settlement_dialog.generated_file_path.startswith("Reports/raport_")
    assert settlement_dialog.generated_file_path.endswith(".pdf")
    assert settlement_dialog.is_existing_file is False
    mock_report_gen.generate_settlement_pdf.assert_called_once()


def test_number_field_is_prefilled_for_the_selected_period(settlement_dialog):
    # Okres startowy to 2026-08 (najnowszy z bazy), rejestr pusty -> 001.
    assert settlement_dialog.number_input.text() == "2026/08/001"


def test_manual_number_survives_period_change(settlement_dialog):
    settlement_dialog.number_input.setText("2026/08/042")
    settlement_dialog._on_number_edited()

    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-07")
    )

    assert settlement_dialog.number_input.text() == "2026/08/042"


@patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("Reports/out.pdf", "PDF"))
@patch("os.makedirs")
def test_number_is_passed_to_pdf_and_written_to_the_register(
    mock_makedirs, mock_file_dialog, settlement_dialog, mock_report_gen
):
    mock_report_gen.compute_settlement_rows.return_value = (0.0, [{"for_client": 321.0}])

    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)
    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)
    settlement_dialog.table.item(0, 2).setText("400")

    with patch("PySide6.QtWidgets.QMessageBox.information"):
        settlement_dialog.generate_report()

    _, kwargs = mock_report_gen.generate_settlement_pdf.call_args
    assert kwargs["number"] == "2026/08/001"

    record = settlement_numbers.get("2026/08/001")
    assert record is not None
    assert record.client_name == "Test Client"
    assert record.total_client == 321.0


@patch("PySide6.QtWidgets.QFileDialog.getSaveFileName", return_value=("Reports/out.pdf", "PDF"))
@patch("os.makedirs")
@patch("PySide6.QtWidgets.QMessageBox.warning")
def test_invalid_manual_number_blocks_generation(
    mock_warning, mock_makedirs, mock_file_dialog, settlement_dialog, mock_report_gen
):
    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)
    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)
    settlement_dialog.table.item(0, 2).setText("400")

    settlement_dialog.number_input.setText("nieprawidlowy")
    settlement_dialog._on_number_edited()

    settlement_dialog.generate_report()

    mock_warning.assert_called_once()
    mock_report_gen.generate_settlement_pdf.assert_not_called()


@patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=("Reports/existing.pdf", "PDF"))
@patch("os.path.exists", return_value=True)
@patch("os.makedirs")
def test_attach_existing_report_success(
    mock_makedirs,
    mock_exists,
    mock_file_dialog,
    settlement_dialog_email,
):
    settlement_dialog_email.attach_existing_report()

    assert settlement_dialog_email.generated_file_path == "Reports/existing.pdf"
    assert settlement_dialog_email.is_existing_file is True


@patch("PySide6.QtWidgets.QFileDialog.getOpenFileName", return_value=("Reports/nonexistent.pdf", "PDF"))
@patch("os.path.exists", return_value=False)
@patch("PySide6.QtWidgets.QMessageBox.critical")
@patch("os.makedirs")
def test_attach_existing_report_not_found(mock_makedirs, mock_critical, mock_exists, mock_file_dialog,
                                          settlement_dialog_email):
    settlement_dialog_email.attach_existing_report()
    mock_critical.assert_called_once()
    assert settlement_dialog_email.is_existing_file is False


def test_collect_items_without_gross(settlement_dialog):
    product_box = settlement_dialog.table.cellWidget(0, 0)
    platform_box = settlement_dialog.table.cellWidget(0, 1)

    product_box.setCurrentIndex(1)
    platform_box.setCurrentIndex(1)
    settlement_dialog.table.item(0, 2).setText("80")

    items = settlement_dialog.collect_items(strict=True)

    assert items[0]["revenue"] == 80.0
    assert items[0]["revenue_gross"] is None


def test_period_box_lists_months_from_database(settlement_dialog):
    labels = [
        settlement_dialog.period_box.itemText(index)
        for index in range(settlement_dialog.period_box.count())
    ]

    assert labels == [
        "Wszystkie okresy",
        "2026 — cały rok",
        "Sierpień 2026",
        "Lipiec 2026",
    ]
    # Rozliczenia robi się co miesiąc, więc startujemy od najnowszego.
    assert settlement_dialog.period_box.currentData() == "2026-08"


def test_selecting_book_fills_amounts_from_database(settlement_dialog, mock_amounts):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 69.99, 73.5)]}

    product_box = settlement_dialog.table.cellWidget(0, 0)
    product_box.setCurrentIndex(1)

    assert settlement_dialog.table.rowCount() == 2
    assert settlement_dialog.table.cellWidget(0, 0).currentData() == 1
    assert settlement_dialog.table.cellWidget(0, 1).currentData() == 1
    assert settlement_dialog.table.item(0, 2).text() == "69.99"
    assert settlement_dialog.table.item(0, 3).text() == "73.50"

    items = settlement_dialog.collect_items(strict=True)
    assert len(items) == 1
    assert items[0]["revenue"] == 69.99
    assert items[0]["revenue_gross"] == 73.5


def test_selecting_book_shows_only_platforms_with_amounts(settlement_dialog, mock_db, mock_amounts):
    settlement_dialog.streamings = [
        {"id": 1, "name": "Spotify"},
        {"id": 2, "name": "Legimi"},
        {"id": 3, "name": "Storytel"},
    ]
    mock_amounts.return_value = {1: [amount(1, 2, "Legimi", 23.33, 24.5)]}

    product_box = settlement_dialog.table.cellWidget(0, 0)
    product_box.setCurrentIndex(1)

    assert settlement_dialog.table.rowCount() == 2
    assert settlement_dialog.table.cellWidget(0, 1).currentText() == "Legimi"
    assert settlement_dialog.table.item(0, 2).text() == "23.33"


def test_search_adds_book_with_amounts_from_database(settlement_dialog, mock_amounts):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 12.5, 15.0)]}

    settlement_dialog.search_input.setText("Test Book")
    settlement_dialog.add_product_from_search()

    assert settlement_dialog.table.item(0, 2).text() == "12.50"
    assert settlement_dialog.table.item(0, 3).text() == "15.00"


def test_amounts_are_matched_by_platform_name_when_id_is_missing(settlement_dialog, mock_amounts):
    # Starsze wpisy w bazie nie mają id platformy - zostaje dopasowanie po nazwie.
    mock_amounts.return_value = {1: [amount(1, None, "Spotify", 8.0, 9.0)]}

    product_box = settlement_dialog.table.cellWidget(0, 0)
    product_box.setCurrentIndex(1)

    assert settlement_dialog.table.cellWidget(0, 1).currentData() == 1
    assert settlement_dialog.table.item(0, 2).text() == "8.00"


def test_dialog_opens_with_client_positions_from_database(
    mock_db, mock_report_gen, mock_amounts
):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 40.0, 48.0)]}

    dialog = SettlementDialog(email_mode=False)

    assert dialog.table.rowCount() == 2
    assert dialog.table.cellWidget(0, 0).currentData() == 1
    assert dialog.table.item(0, 2).text() == "40.00"
    # Ostatni wiersz zostaje pusty na ręczne dopisanie pozycji.
    assert dialog.table.cellWidget(1, 0).currentIndex() == 0


def test_changing_period_reloads_amounts(settlement_dialog, mock_amounts):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 69.99, 73.5)]}
    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)
    assert settlement_dialog.table.item(0, 2).text() == "69.99"

    mock_amounts.return_value = {
        1: [amount(1, 1, "Spotify", 20.0, 21.0, periods=("2026-07",))]
    }
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-07")
    )

    assert settlement_dialog.table.item(0, 2).text() == "20.00"
    assert settlement_dialog.table.item(0, 3).text() == "21.00"


def test_period_without_data_clears_positions(settlement_dialog, mock_amounts):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 69.99, 73.5)]}
    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)

    mock_amounts.return_value = {}
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-07")
    )

    assert settlement_dialog.table.rowCount() == 1
    assert settlement_dialog.collect_items(strict=True) == []


def test_dialog_survives_unreadable_database(mock_db, mock_report_gen):
    from GUI.Widgets.Settlement.SettlementDialog import (
        ReportCalculationError,
        SettlementAmountsError,
    )

    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        side_effect=SettlementAmountsError("brak bazy"),
    ), patch(
        "GUI.Widgets.Settlement.SettlementDialog.load_amounts",
        side_effect=SettlementAmountsError("brak bazy"),
    ), patch(
        "GUI.Widgets.Settlement.SettlementDialog.relink_unmatched_rows",
        side_effect=ReportCalculationError("brak bazy"),
    ):
        dialog = SettlementDialog(email_mode=False)

        assert dialog.period_box.count() == 1
        assert dialog.period_box.currentData() == ""
        assert dialog.table.rowCount() == 1


def test_adding_the_same_book_twice_refreshes_instead_of_duplicating(
    settlement_dialog, mock_amounts
):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 69.99, 73.5)]}

    settlement_dialog.search_input.setText("Test Book")
    settlement_dialog.add_product_from_search()
    assert settlement_dialog.table.rowCount() == 2

    settlement_dialog.table.item(0, 2).setText("1")
    settlement_dialog.search_input.setText("Test Book")
    settlement_dialog.add_product_from_search()

    assert settlement_dialog.table.rowCount() == 2
    assert settlement_dialog.table.item(0, 2).text() == "69.99"
    assert settlement_dialog.table.cellWidget(1, 0).currentIndex() == 0


def test_commission_column_is_prefilled_from_product(settlement_dialog, mock_amounts):
    settlement_dialog.products = [{"id": 1, "title": "Test Book", "cut": 30}]
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 100.0, 123.0)]}

    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)

    assert settlement_dialog.table.item(0, 4).text() == "30"

    items = settlement_dialog.collect_items(strict=True)
    assert items[0]["cut"] == 30.0


def test_commission_column_is_empty_for_product_without_one(settlement_dialog, mock_amounts):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 100.0)]}

    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)

    # Pusta komórka oznacza "prowizja nie jest nadpisana w rozliczeniu".
    assert settlement_dialog.table.item(0, 4).text() == ""
    assert settlement_dialog.collect_items(strict=True)[0]["cut"] is None


def test_commission_can_be_overridden_by_hand(settlement_dialog, mock_amounts):
    settlement_dialog.products = [{"id": 1, "title": "Test Book", "cut": 30}]
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 100.0)]}
    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)

    settlement_dialog.table.item(0, 4).setText("12,5")

    assert settlement_dialog.collect_items(strict=True)[0]["cut"] == 12.5


@pytest.mark.parametrize("text", ["abc", "150", "-5"])
def test_invalid_commission_is_rejected(settlement_dialog, mock_amounts, text):
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 100.0)]}
    settlement_dialog.table.cellWidget(0, 0).setCurrentIndex(1)
    settlement_dialog.table.item(0, 4).setText(text)

    with pytest.raises(ValueError, match="rowizja AO"):
        settlement_dialog.collect_items(strict=True)

    # Podgląd raportu nie może wybuchać na wpisywanym tekście.
    assert settlement_dialog.collect_items(strict=False)[0]["cut"] is None


def test_showing_the_dialog_picks_up_a_new_month(settlement_dialog):
    assert settlement_dialog.period_box.findData("2026-10") == -1

    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        return_value=["2026-10", "2026-08", "2026-07"],
    ):
        settlement_dialog.show()

    # Nowo przeliczony październik sam wchodzi na listę okresów.
    assert settlement_dialog.period_box.findData("2026-10") >= 0
    assert "Październik 2026" in [
        settlement_dialog.period_box.itemText(index)
        for index in range(settlement_dialog.period_box.count())
    ]
    # Okres wybrany przez użytkownika zostaje nietknięty.
    assert settlement_dialog.period_box.currentData() == "2026-08"


def test_showing_the_dialog_keeps_the_selected_period(settlement_dialog):
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-07")
    )

    settlement_dialog.show()

    assert settlement_dialog.period_box.currentData() == "2026-07"


def test_period_falls_back_to_newest_when_the_old_one_disappears(
    settlement_dialog, mock_amounts
):
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-07")
    )
    mock_amounts.return_value = {1: [amount(1, 1, "Spotify", 5.0)]}

    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        return_value=["2026-09"],
    ):
        settlement_dialog.show()

    assert settlement_dialog.period_box.currentData() == "2026-09"
    # Zmiana okresu ma odświeżyć pozycje.
    assert settlement_dialog.table.item(0, 2).text() == "5.00"


# ==========================================================
# Filtrowanie książek po kliencie + tryb "wszystkie książki"
# ==========================================================

_MULTI_CLIENT_DB = {
    "clients": [
        {"id": 1, "name": "Klient z książkami", "products": [10, 11]},
        {"id": 2, "name": "Klient bez książek", "products": []},
    ],
    "streamings": [{"id": 1, "name": "Spotify"}],
    "products": [
        {"id": 10, "title": "Alfa", "author": "Anna Autor"},
        {"id": 11, "title": "Beta", "author": ""},
        {"id": 12, "title": "Gamma", "author": "Grzegorz Ghost"},
    ],
}


@pytest.fixture
def multi_dialog(mock_report_gen, mock_amounts):
    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.database_controller"
    ) as mock:
        mock.load_database.side_effect = lambda name: [
            dict(row) for row in _MULTI_CLIENT_DB.get(name, [])
        ]
        mock.item_get.side_effect = lambda item_id, db: next(
            (dict(r) for r in _MULTI_CLIENT_DB.get(db, []) if r["id"] == item_id),
            None,
        )
        yield SettlementDialog(email_mode=False)


def _product_combo_labels(dialog, row=0):
    box = dialog.table.cellWidget(row, 0)
    return [box.itemText(i) for i in range(box.count()) if box.itemText(i)]


def test_product_combo_lists_every_book_with_author(multi_dialog):
    multi_dialog.client_box.setCurrentIndex(0)  # klient z książkami [10, 11]

    assert sorted(_product_combo_labels(multi_dialog)) == [
        "Alfa — Anna Autor",
        "Beta",  # bez autora - sam tytuł
        "Gamma — Grzegorz Ghost",
    ]


def test_selecting_book_keeps_product_id_so_author_follows(multi_dialog):
    multi_dialog.client_box.setCurrentIndex(0)

    box = multi_dialog.table.cellWidget(0, 0)
    idx = next(
        i for i in range(box.count()) if box.itemText(i) == "Gamma — Grzegorz Ghost"
    )
    box.setCurrentIndex(idx)

    # Dane pozycji to ID książki - raport pobiera po nim pełny rekord
    # (razem z autorem), niezależnie od tego, czy książka należy do klienta.
    assert box.currentData() == 12
    assert multi_dialog._find_product_id_by_title("Gamma — Grzegorz Ghost") == 12
    assert multi_dialog._find_product_id_by_title("gamma") == 12


def test_book_list_is_the_same_for_a_client_without_books(multi_dialog):
    multi_dialog.client_box.setCurrentIndex(1)  # klient bez książek

    assert len(_product_combo_labels(multi_dialog)) == 3


def test_book_list_does_not_shrink_when_switching_clients(multi_dialog):
    multi_dialog.client_box.setCurrentIndex(1)
    multi_dialog.client_box.setCurrentIndex(0)

    assert len(_product_combo_labels(multi_dialog)) == 3


_OWNED_DB = {
    "clients": [
        {"id": 1, "name": "Klient A", "products": [10, 11]},
        {"id": 2, "name": "Klient B", "products": [12]},
    ],
    "streamings": [{"id": 1, "name": "Spotify"}],
    "products": [
        {"id": 10, "title": "Alfa", "author": "AA"},
        {"id": 11, "title": "Beta", "author": "BB"},
        {"id": 12, "title": "Lustro iluzji", "author": "CC"},
        {"id": 13, "title": "Niczyja", "author": "DD"},
    ],
}


@pytest.fixture
def owned_dialog(mock_report_gen, mock_amounts):
    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.database_controller"
    ) as mock:
        mock.load_database.side_effect = lambda name: [
            dict(row) for row in _OWNED_DB.get(name, [])
        ]
        mock.item_get.side_effect = lambda item_id, db: next(
            (dict(r) for r in _OWNED_DB.get(db, []) if r["id"] == item_id),
            None,
        )
        yield SettlementDialog(email_mode=False)


def test_picking_other_clients_book_switches_client(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)  # Klient A

    box = owned_dialog.table.cellWidget(owned_dialog.table.rowCount() - 1, 0)
    idx = next(
        i for i in range(box.count()) if "Lustro iluzji" in box.itemText(i)
    )
    box.setCurrentIndex(idx)  # książka Klienta B

    assert owned_dialog.client_box.currentData() == 2


def test_picking_unowned_book_does_not_switch_client(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)  # Klient A

    box = owned_dialog.table.cellWidget(owned_dialog.table.rowCount() - 1, 0)
    idx = next(i for i in range(box.count()) if "Niczyja" in box.itemText(i))
    box.setCurrentIndex(idx)

    assert owned_dialog.client_box.currentData() == 1


# --- Szybkie dodawanie: podpowiedzi z całej bazy + Enter ---

def _completer_labels(dialog):
    model = dialog._product_completer.model()
    return [model.index(row, 0).data() for row in range(model.rowCount())]


def test_quick_add_suggests_every_book_not_only_client_books(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)  # Klient A, tylko Alfa/Beta

    labels = _completer_labels(owned_dialog)

    assert "Alfa" in labels
    assert "Lustro iluzji" in labels  # książka Klienta B
    assert "Niczyja" in labels        # niczyja


def test_quick_add_on_enter_adds_other_clients_book_and_switches_client(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)

    owned_dialog.search_input.setText("Lustro iluzji")
    owned_dialog.add_product_from_search()  # to co robi Enter

    assert owned_dialog.client_box.currentData() == 2
    assert owned_dialog.table.cellWidget(0, 0).currentData() == 12
    assert owned_dialog.search_input.text() == ""


def test_quick_add_resolves_unique_fragment(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)

    owned_dialog.search_input.setText("lustro")
    owned_dialog.add_product_from_search()

    assert owned_dialog.table.cellWidget(0, 0).currentData() == 12


def test_quick_add_enter_takes_highlighted_suggestion(owned_dialog):
    """Enter przy otwartej liście podpowiedzi bierze podświetloną pozycję."""
    owned_dialog.client_box.setCurrentIndex(1)

    owned_dialog.search_input.setText("lus")
    owned_dialog._product_completer.setCompletionPrefix("lus")
    owned_dialog._commit_quick_add_from_field()  # to co robi Enter w polu

    assert owned_dialog.table.cellWidget(0, 0).currentData() == 12


def test_quick_add_via_completer_activation(owned_dialog):
    """Klik/Enter na pozycji listy podpowiedzi (sygnał activated)."""
    owned_dialog.client_box.setCurrentIndex(1)

    owned_dialog._product_completer.activated[str].emit("Lustro iluzji")

    assert owned_dialog.client_box.currentData() == 2
    assert owned_dialog.table.cellWidget(0, 0).currentData() == 12


def test_quick_add_does_not_force_an_ambiguous_fragment(owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)
    rows_before = owned_dialog.table.rowCount()

    owned_dialog.search_input.setText("z")  # jest w "Lustro iluzji" i "Niczyja"
    owned_dialog.add_product_from_search()

    assert owned_dialog.table.rowCount() == rows_before
    assert owned_dialog.table.cellWidget(0, 0).currentIndex() == 0


@patch("PySide6.QtWidgets.QMessageBox.warning")
@patch("PySide6.QtWidgets.QMessageBox.information")
def test_quick_add_unknown_title_shows_no_modal(mock_info, mock_warning, owned_dialog):
    owned_dialog.client_box.setCurrentIndex(1)
    rows_before = owned_dialog.table.rowCount()

    owned_dialog.search_input.setText("tego tytułu nie ma w bazie")
    owned_dialog.add_product_from_search()

    mock_info.assert_not_called()
    mock_warning.assert_not_called()
    assert owned_dialog.table.rowCount() == rows_before
    # Wpisany tekst zostaje, żeby dało się go poprawić.
    assert owned_dialog.search_input.text() == "tego tytułu nie ma w bazie"


# ==========================================================
# Raporty dla nieregularnych dat (okresy kwartalne)
# ==========================================================


def _period_items(dialog):
    return [
        (dialog.period_box.itemText(index), dialog.period_box.itemData(index))
        for index in range(dialog.period_box.count())
    ]


def test_quarter_appears_on_the_period_list_with_its_date_range(
    mock_db, mock_report_gen, mock_amounts
):
    from platforms.settlement_amounts import PeriodSpan

    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        return_value=["2026-08", "2025-Q4"],
    ), patch(
        "GUI.Widgets.Settlement.SettlementDialog.period_span",
        return_value=PeriodSpan(start="2025-10-02", end="2025-12-28"),
    ):
        dialog = SettlementDialog(email_mode=False)

    assert _period_items(dialog) == [
        ("Wszystkie okresy", ""),
        ("2026 — cały rok", "2026"),
        ("Sierpień 2026", "2026-08"),
        ("2025 — cały rok", "2025"),
        ("IV kwartał 2025 (2025-10-02 – 2025-12-28)", "2025-Q4"),
    ]


def test_quarter_without_known_range_falls_back_to_plain_label(
    mock_db, mock_report_gen, mock_amounts
):
    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        return_value=["2025-Q1"],
    ), patch(
        "GUI.Widgets.Settlement.SettlementDialog.period_span",
        return_value=None,
    ):
        dialog = SettlementDialog(email_mode=False)

    assert dialog._period_label("2025-Q1") == "I kwartał 2025"


def test_selecting_a_quarter_loads_its_amounts(
    mock_db, mock_report_gen, mock_amounts
):
    from platforms.settlement_amounts import PeriodSpan

    mock_amounts.return_value = {
        1: [amount(1, 1, "Spotify", 8.0, 9.0, periods=("2025-Q4",))]
    }

    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.available_periods",
        return_value=["2025-Q4"],
    ), patch(
        "GUI.Widgets.Settlement.SettlementDialog.period_span",
        return_value=PeriodSpan(start="2025-10-02", end="2025-12-28"),
    ):
        dialog = SettlementDialog(email_mode=False)

    assert dialog._current_period() == "2025-Q4"
    assert dialog.table.item(0, 2).text() == "8.00"
    assert dialog.table.item(0, 3).text() == "9.00"

    items = dialog.collect_items(strict=True)
    assert items[0]["revenue"] == 8.0
    assert items[0]["revenue_gross"] == 9.0


def test_report_gets_the_period_description(settlement_dialog):
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("2026-08")
    )

    assert settlement_dialog._period_description() == "Sierpień 2026"


def test_all_periods_leave_the_description_empty(settlement_dialog):
    settlement_dialog.period_box.setCurrentIndex(
        settlement_dialog.period_box.findData("")
    )

    # Raport obejmuje wtedy wszystko, co jest w bazie - nie ma konkretnego zakresu.
    assert settlement_dialog._period_description() == ""



def test_opening_the_dialog_relinks_rows_to_later_added_books(
    mock_db, mock_report_gen, mock_amounts
):
    """Książka dodana po „Przelicz raporty” ma od razu widzieć swoje kwoty."""
    with patch(
        "GUI.Widgets.Settlement.SettlementDialog.relink_unmatched_rows",
        return_value=2,
    ) as relink:
        dialog = SettlementDialog(email_mode=False)

    relink.assert_called_once()
    # Dopinamy po tej samej liście książek, którą widzi okno.
    assert relink.call_args.kwargs["products"] == dialog.products
