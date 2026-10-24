import pytest
from PySide6.QtWidgets import QApplication

from core import lectors
from core import calculator_config
from core import database_controller
from GUI.Widgets.Dialogs.CalculatorDialog import CalculatorDialog, LectorEditDialog


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(autouse=True)
def isolated_config_files(tmp_path, monkeypatch):
    monkeypatch.setattr(database_controller, "FOLDER", str(tmp_path))
    monkeypatch.setattr(
        calculator_config, "CONFIG_FILE", str(tmp_path / "calculator_config.json")
    )


@pytest.fixture
def dialog():
    return CalculatorDialog()


def test_initialization_defaults_to_fixed_commission(dialog):
    assert dialog.windowTitle() == "Kalkulatory"
    assert dialog.type_combo.currentData() == "instant"
    assert dialog.commission_stack.currentWidget() == dialog.fixed_page
    assert dialog.result_amount.text() == "0,00 zł"


def test_empty_amount_shows_placeholder_breakdown(dialog):
    dialog.amount_input.setText("")

    assert dialog.result_breakdown.text() == (
        "Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."
    )


def test_fixed_commission_updates_result_live(dialog):
    """Procent w "Od razu" to prowizja AO (jak "Procent" przy książce) -
    platforma dostaje wpisany procent, klient resztę."""
    dialog.amount_input.setText("10000")
    dialog.fixed_percent_input.setText("30")

    assert dialog.result_platform.text() == "3 000,00 zł"
    assert dialog.result_client.text() == "7 000,00 zł"
    assert "30%" in dialog.result_breakdown.text()


def test_fixed_commission_missing_percent_shows_hint(dialog):
    dialog.amount_input.setText("10000")
    dialog.fixed_percent_input.setText("")

    assert dialog.result_breakdown.text() == (
        "Podaj prowizję AO, aby zobaczyć wyliczenie."
    )
    assert dialog.result_client.text() == "0,00 zł"


def test_threshold_commission_without_selected_threshold_shows_hint(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )
    dialog.amount_input.setText("7000")

    assert dialog.commission_stack.currentWidget() == dialog.threshold_page
    assert dialog.result_breakdown.text() == (
        "Dodaj i wybierz próg z listy, aby zobaczyć wyliczenie."
    )


def _add_threshold(dialog, value, cut):
    dialog.threshold_value_input.setText(value)
    dialog.threshold_cut_input.setText(cut)
    dialog.add_threshold(
        dialog.threshold_value_input,
        dialog.threshold_cut_input,
        dialog.threshold_list,
    )


def _add_up_to_threshold(dialog, value, cut):
    dialog.up_to_threshold_value_input.setText(value)
    dialog.up_to_threshold_cut_input.setText(cut)
    dialog.add_threshold(
        dialog.up_to_threshold_value_input,
        dialog.up_to_threshold_cut_input,
        dialog.up_to_threshold_list,
    )


def test_add_threshold_and_calculate_excess_split(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )

    _add_threshold(dialog, "5000", "20")

    dialog.amount_input.setText("7000")

    assert dialog.threshold_list.count() == 1
    assert dialog.result_excess.text() == "2 000,00 zł"
    assert dialog.result_platform.text() == "400,00 zł"
    assert dialog.result_client.text() == "1 600,00 zł"


def test_amount_below_threshold_keeps_everything_at_platform(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )

    _add_threshold(dialog, "5000", "20")

    dialog.amount_input.setText("3000")

    assert dialog.result_client.text() == "0,00 zł"
    assert dialog.result_platform.text() == "0,00 zł"
    assert "nie przekracza progu" in dialog.result_breakdown.text()


def test_remove_selected_threshold(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )

    _add_threshold(dialog, "5000", "20")

    assert dialog.threshold_list.count() == 1

    dialog.remove_threshold(dialog.threshold_list)

    assert dialog.threshold_list.count() == 0


def test_add_threshold_rejects_invalid_percent(dialog, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.CalculatorDialog.QtWidgets.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )

    _add_threshold(dialog, "5000", "150")

    assert dialog.threshold_list.count() == 0
    assert len(warnings) == 1


def test_up_to_threshold_commission_splits_capped_amount(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("up_to_threshold")
    )

    assert dialog.commission_stack.currentWidget() == dialog.up_to_threshold_page

    _add_up_to_threshold(dialog, "5000", "20")

    dialog.amount_input.setText("7000")

    assert dialog.result_excess.text() == "2 000,00 zł"
    assert dialog.result_platform.text() == "1 000,00 zł"
    assert dialog.result_client.text() == "6 000,00 zł"


def test_threshold_result_updates_live_before_adding(dialog):
    """Wynik ma się liczyć na bieżąco, w trakcie wpisywania progu i procentu
    - bez konieczności klikania "Dodaj"."""
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )

    dialog.amount_input.setText("7000")
    dialog.threshold_value_input.setText("5000")
    dialog.threshold_cut_input.setText("20")

    assert dialog.threshold_list.count() == 0
    assert dialog.result_excess.text() == "2 000,00 zł"
    assert dialog.result_platform.text() == "400,00 zł"
    assert dialog.result_client.text() == "1 600,00 zł"


def test_combined_result_updates_live_before_adding(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("combined")
    )

    dialog.amount_input.setText("7000")
    dialog.combined_value_input.setText("5000")
    dialog.combined_below_input.setText("10")
    dialog.combined_above_input.setText("20")

    assert dialog.combined_list.count() == 0
    assert dialog.result_platform.text() == "900,00 zł"
    assert dialog.result_client.text() == "6 100,00 zł"


def _add_combined_threshold(dialog, value, below, above):
    dialog.combined_value_input.setText(value)
    dialog.combined_below_input.setText(below)
    dialog.combined_above_input.setText(above)
    dialog.add_combined_threshold()


def test_combined_commission_applies_both_percents(dialog):
    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("combined")
    )

    assert dialog.commission_stack.currentWidget() == dialog.combined_page

    _add_combined_threshold(dialog, "5000", "10", "20")

    dialog.amount_input.setText("7000")

    assert dialog.combined_list.count() == 1
    assert dialog.result_excess.text() == "2 000,00 zł"
    assert dialog.result_platform.text() == "900,00 zł"
    assert dialog.result_client.text() == "6 100,00 zł"
    assert "10%" in dialog.result_breakdown.text()
    assert "20%" in dialog.result_breakdown.text()


def test_combined_commission_rejects_invalid_percent(dialog, monkeypatch):
    warnings = []
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.CalculatorDialog.QtWidgets.QMessageBox.warning",
        lambda *args, **kwargs: warnings.append(args),
    )

    _add_combined_threshold(dialog, "5000", "150", "20")

    assert dialog.combined_list.count() == 0
    assert len(warnings) == 1


def test_threshold_lists_are_independent_per_type(dialog):
    """Progi 'Po progu' i 'Do progu' żyją na osobnych listach - dodanie
    progu w jednym trybie nie wpływa na listę drugiego trybu."""

    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("threshold")
    )

    _add_threshold(dialog, "5000", "20")

    dialog.type_combo.setCurrentIndex(
        dialog.type_combo.findData("up_to_threshold")
    )

    _add_up_to_threshold(dialog, "1000", "10")

    assert dialog.threshold_list.count() == 1
    assert dialog.up_to_threshold_list.count() == 1
    assert dialog.threshold_list.item(0).text() != dialog.up_to_threshold_list.item(0).text()


def test_clear_resets_everything(dialog):
    dialog.amount_input.setText("10000")
    dialog.fixed_percent_input.setText("30")

    dialog.clear()

    assert dialog.amount_input.text() == ""
    assert dialog.fixed_percent_input.text() == ""
    assert dialog.threshold_list.count() == 0
    assert dialog.up_to_threshold_list.count() == 0
    assert dialog.combined_list.count() == 0
    assert dialog.result_client.text() == "0,00 zł"
    assert dialog.result_breakdown.text() == (
        "Podaj kwotę rozliczenia, aby zobaczyć wyliczenie."
    )


# ==========================================================
# ZAKŁADKA LEKTORZY
# ==========================================================

def test_lectors_tab_loads_default_lectors(dialog):
    assert dialog.tabs.count() == 2
    assert dialog.lector_combo.count() == len(lectors.DEFAULT_LECTORS)
    assert dialog.lector_combo.itemText(0) == "Karolina"


def _select_lector(dialog, name):
    dialog.lector_combo.setCurrentIndex(dialog.lector_combo.findText(name))


def test_lector_cost_from_chars(dialog):
    _select_lector(dialog, "Wojtek Masiak")
    dialog.lector_amount_input.setText("210000")

    # 5,25 arkusza x (400 + 50) zł/arkusz = 2 362,50 zł netto.
    breakdown = dialog.lector_material_breakdown.text()
    assert "5,25 ark." in breakdown
    assert "4 godz. 23 min" in breakdown
    assert dialog.lector_result_lector.text() == "2 100,00 zł"
    assert dialog.lector_result_surcharge.text() == "262,50 zł"
    assert dialog.lector_result_net.text() == "2 362,50 zł"
    assert dialog.lector_result_gross.text() == "2 905,88 zł"
    assert "VAT 23%" in dialog.lector_vat_row_label.text()


def test_lector_one_sheet_matches_rate_card(dialog):
    _select_lector(dialog, "Wojtek Masiak")
    dialog.lector_amount_input.setText("40000")

    assert dialog.lector_result_net.text() == "450,00 zł"
    assert dialog.lector_result_vat.text() == "103,50 zł"
    assert dialog.lector_result_gross.text() == "553,50 zł"


def test_lector_vat_rate_comes_from_config(tmp_path, monkeypatch):
    calculator_config.save_vat_percent(8)

    d = CalculatorDialog()
    _select_lector(d, "Wojtek Masiak")
    d.lector_amount_input.setText("40000")

    # 1 arkusz: 450,00 netto, VAT 8% = 36,00, brutto 486,00.
    assert d._vat_percent == 8
    assert "VAT 8%" in d.lector_vat_row_label.text()
    assert d.lector_result_vat.text() == "36,00 zł"
    assert d.lector_result_gross.text() == "486,00 zł"


def test_lector_vat_input_shows_current_rate(dialog):
    assert dialog.lector_vat_input.text() == "23"


def test_changing_vat_input_saves_and_recalculates(dialog):
    _select_lector(dialog, "Wojtek Masiak")
    dialog.lector_amount_input.setText("40000")

    dialog.lector_vat_input.setText("8")
    dialog._on_vat_changed()

    assert dialog._vat_percent == 8
    assert calculator_config.load_vat_percent() == 8
    assert dialog.lector_result_vat.text() == "36,00 zł"
    assert dialog.lector_result_gross.text() == "486,00 zł"


def test_vat_input_normalizes_display(dialog):
    dialog.lector_vat_input.setText("7,50")
    dialog._on_vat_changed()

    assert dialog.lector_vat_input.text() == "7,5"


def test_empty_vat_input_reverts_without_saving(dialog):
    calculator_config.save_vat_percent(23)

    dialog.lector_vat_input.setText("")
    dialog._on_vat_changed()

    assert dialog.lector_vat_input.text() == "23"
    assert calculator_config.load_vat_percent() == 23


def test_lector_edit_dialog_has_no_vat_field():
    # VAT przeniesiony do Ustawienia -> Kalkulator, okno lektora go nie dotyka.
    dlg = LectorEditDialog(None, {"name": "X", "rate": 100.0, "surcharge": 0.0})

    assert not hasattr(dlg, "vat_input")

    dlg.accept()

    assert "vat_percent" not in dlg._result


def test_edit_lector_does_not_change_vat_rate(dialog, monkeypatch):
    _select_lector(dialog, "Wojtek Masiak")
    dialog.lector_amount_input.setText("40000")

    def fake_get_lector(cls, parent, lector=None):
        return {"name": "Wojtek Masiak", "rate": 400.0, "surcharge": 50.0}

    monkeypatch.setattr(
        LectorEditDialog, "get_lector", classmethod(fake_get_lector)
    )

    dialog.edit_lector()

    # VAT ładowany raz przy otwarciu kalkulatora - edycja lektora go nie rusza.
    assert dialog._vat_percent == calculator_config.DEFAULT_VAT_PERCENT
    assert dialog.lector_result_gross.text() == "553,50 zł"
    assert all("vat_percent" not in item for item in dialog._lectors)


def test_lector_empty_input_shows_placeholder(dialog):
    _select_lector(dialog, "Karolina")
    dialog.lector_amount_input.setText("")

    assert dialog.lector_result_net.text() == "0,00 zł"
    assert "Podaj objętość materiału" in dialog.lector_result_breakdown.text()


def test_add_lector_persists_and_appears(dialog, monkeypatch):
    monkeypatch.setattr(
        LectorEditDialog,
        "get_lector",
        classmethod(
            lambda cls, parent, lector=None: {
                "name": "Testowy Lektor",
                "rate": 500.0,
                "surcharge": 60.0,
            }
        ),
    )

    dialog.add_lector()

    assert dialog.lector_combo.findText("Testowy Lektor") >= 0
    assert any(
        item["name"] == "Testowy Lektor"
        for item in lectors.load_lectors()
    )


def test_edit_lector_updates_rate(dialog, monkeypatch):
    _select_lector(dialog, "Karolina")

    monkeypatch.setattr(
        LectorEditDialog,
        "get_lector",
        classmethod(
            lambda cls, parent, lector=None: {
                "name": "Karolina",
                "rate": 999.0,
                "surcharge": 0.0,
            }
        ),
    )

    dialog.edit_lector()

    saved = {item["name"]: item for item in lectors.load_lectors()}
    assert saved["Karolina"]["rate"] == 999.0


def test_remove_lector_drops_entry(dialog, monkeypatch):
    _select_lector(dialog, "Karolina")
    monkeypatch.setattr(
        "GUI.Widgets.Dialogs.CalculatorDialog.confirm_yes_no",
        lambda *args, **kwargs: True,
    )

    dialog.remove_lector()

    assert dialog.lector_combo.findText("Karolina") == -1
    assert all(
        item["name"] != "Karolina" for item in lectors.load_lectors()
    )


def test_clear_lector_resets_fields(dialog):
    _select_lector(dialog, "Karolina")
    dialog.lector_amount_input.setText("80000")

    dialog.clear_lector()

    assert dialog.lector_amount_input.text() == ""
    assert dialog.lector_result_gross.text() == "0,00 zł"


# ==========================================================
# Jednostka materiału (znaki / arkusze) + rozpiska
# ==========================================================

def _set_unit(dialog, data):
    dialog.material_unit_combo.setCurrentIndex(
        dialog.material_unit_combo.findData(data)
    )


def test_material_default_unit_is_chars(dialog):
    assert dialog.material_unit_combo.currentData() == "chars"
    assert dialog.material_unit_combo.count() == 2


def test_material_breakdown_lists_chars_sheets_time(dialog):
    dialog.lector_amount_input.setText("210000")

    text = dialog.lector_material_breakdown.text()
    assert "210 000 zzs" in text
    assert "5,25 ark." in text
    assert "4 godz. 23 min" in text
    assert "słów" not in text


def test_cost_input_in_sheets(dialog):
    _select_lector(dialog, "Wojtek Masiak")
    _set_unit(dialog, "sheets")
    dialog.lector_amount_input.setText("5,25")

    # 5,25 arkusza -> ten sam wynik co 210 000 zzs
    assert dialog.lector_result_net.text() == "2 362,50 zł"
    assert "210 000 zzs" in dialog.lector_material_breakdown.text()
