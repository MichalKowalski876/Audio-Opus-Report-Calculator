from unittest.mock import patch
from types import SimpleNamespace

import pytest
from PySide6.QtTest import QTest
from datetime import datetime
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from GUI.Tabs.StartTab import StartTab, format_date, format_money, greeting


@pytest.fixture(scope="session", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def dashboard():
    clients_tab = QWidget()
    clients_tab.add_client = lambda: None
    products_tab = QWidget()
    products_tab.add_product = lambda: None
    streaming_tab = QWidget()
    streaming_tab.show_mode_selection = lambda: None
    report_tab = QWidget()
    report_tab.open_settlement = lambda: None

    records = {
        "clients": [
            {"id": 1, "name": "Bez maila", "email": ""},
            {"id": 2, "name": "Klient", "email": "a@test.pl"},
        ],
        "products": [
                {"id": 1, "isbn": "", "streaming": ["Legimi", "Storytel"]},
            {"id": 2, "isbn": "123", "streaming": []},
        ],
    }

    with (
        patch(
            "GUI.Tabs.StartTab.database_controller.load_database",
            side_effect=lambda name: records[name],
        ),
        patch(
            "GUI.Tabs.StartTab.list_monthly_book_reports",
            return_value=[
                SimpleNamespace(
                    year=2026, product_id=1, title="A", isbn="", period="2026-08",
                    total_net=10, total_gross=12, source_rows=2,
                ),
                SimpleNamespace(
                    year=2026, product_id=2, title="B", isbn="", period="2026-08",
                    total_net=20, total_gross=24, source_rows=1,
                ),
                SimpleNamespace(
                    year=2026, product_id=1, title="A", isbn="", period="2026-07",
                    total_net=5, total_gross=6, source_rows=1,
                ),
                SimpleNamespace(
                    year=2026, product_id=2, title="B", isbn="", period="2026-07",
                    total_net=8, total_gross=9, source_rows=1,
                ),
            ],
        ),
        patch(
            "GUI.Tabs.StartTab.list_book_reports",
            return_value=[
                SimpleNamespace(year=2025, total_net=100),
                SimpleNamespace(year=2026, total_net=43),
            ],
        ),
        patch("GUI.Tabs.StartTab.report_generator.FOLDER", "/missing/reports"),
    ):
        widget = StartTab(clients_tab, products_tab, streaming_tab, report_tab)
        yield widget
        widget.close()


def test_dashboard_shows_key_metrics(dashboard):
    assert dashboard._count_labels["clients"].text() == "2"
    assert dashboard._count_labels["products"].text() == "2"
    assert dashboard._count_labels["reports"].text() == "4"
    assert dashboard._count_labels["latest_net"].text() == "43,00 zł"
    assert dashboard._hint_labels["latest_net"].text() == "rok 2026"
    assert "Rok 2026" in dashboard._settlement_info_label.text()
    assert "netto 43,00 zł" in dashboard._settlement_info_label.text()
    assert dashboard._count_labels["attention"].text() == "3"
    assert dashboard._warnings == [
        ("Klienci bez adresu e-mail", 1),
        ("Produkty bez numeru ISBN", 1),
        ("Produkty bez przypisanej platformy", 1),
    ]


def test_dashboard_chart_tracks_yearly_totals(dashboard):
    assert dashboard.platform_chart._values == {
        "2025": 100.0,
        "2026": 43.0,
    }
    assert dashboard._chart_hint.text() == "łącznie 143,00 zł"
    QTest.qWait(dashboard.platform_chart.ANIMATION_DURATION_MS + 100)
    assert not dashboard.platform_chart.is_animating


def test_dashboard_refreshes_automatically_when_visible(dashboard):
    assert dashboard._refresh_timer.interval() == 5000

    dashboard.show()
    QApplication.processEvents()

    assert dashboard._refresh_timer.isActive()

    dashboard.hide()
    assert not dashboard._refresh_timer.isActive()


def test_dashboard_shows_info_immediately_on_entry(dashboard):
    dashboard.show()
    QApplication.processEvents()

    assert dashboard._settlement_info_label.isVisible()
    assert dashboard._count_labels["clients"].text() == "2"
    assert dashboard._count_labels["latest_net"].text() == "43,00 zł"


def test_dashboard_without_reports_shows_empty_state(dashboard):
    assert "Brak wygenerowanych raportów" in dashboard._files_container.findChild(
        QLabel
    ).text()


def test_recent_files_skip_office_lock_files(tmp_path):
    (tmp_path / "Legimi.xlsx").write_text("x")
    (tmp_path / "~$Legimi.xlsx").write_text("x")
    with patch("GUI.Tabs.StartTab.report_generator.FOLDER", str(tmp_path)):
        names = [name for name, _ in StartTab._recent_report_files()]
    assert names == ["Legimi.xlsx"]


def test_polish_formatting():
    assert format_money(1253.37) == "1 253,37 zł"
    assert format_date(datetime(2026, 9, 24)) == "czwartek, 24 września 2026"
    assert greeting(datetime(2026, 9, 24, 9)) == "Dzień dobry"
    assert greeting(datetime(2026, 9, 24, 20)) == "Dobry wieczór"
