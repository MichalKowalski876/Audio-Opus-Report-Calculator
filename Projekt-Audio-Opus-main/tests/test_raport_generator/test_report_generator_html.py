import pytest
from datetime import datetime
from core.report_generator import DEFAULT_STYLE, build_settlement_html


class TestBuildSettlementHtml:

    @pytest.fixture
    def dummy_client(self):
        return {"id": 101, "name": "John Doe Records", "cut": "20.0"}

    def test_build_empty_items(self, dummy_client):
        now = datetime(2024, 5, 1, 14, 30)
        html = build_settlement_html(dummy_client, [], now=now)

        assert "John Doe Records" in html
        assert "Klient id 101" in html
        assert "2024-05-01 14:30" in html
        assert "Brak pozycji \u2014 dodaj produkt, aby uzupe\u0142ni\u0107 raport." in html

    def test_number_is_rendered_in_the_header_when_given(self, dummy_client):
        html = build_settlement_html(dummy_client, [], number="2026/09/001")
        assert "<b>Nr 2026/09/001</b>" in html

    def test_number_is_absent_when_not_given(self, dummy_client):
        html = build_settlement_html(dummy_client, [])
        assert "<b>Nr " not in html

    def test_build_instant_settlement(self, dummy_client):
        items = [
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Spotify"},
                "revenue": 100.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "Hit Track" in html
        assert "Spotify" in html
        assert "Od razu" in html
        assert "80,00\u00a0z\u0142" in html
        assert "20,00\u00a0z\u0142" in html

    def test_build_threshold_settlement_above_threshold(self, dummy_client):
        items = [
            {
                "product": {"tytul": "Album One", "typ rozliczenia": "próg", "prog": "50,00"},
                "platform": {"nazwa": "Tidal"},
                "revenue": 150.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "Album One" in html
        assert "Po progu" in html
        assert "50,00\u00a0z\u0142" in html
        assert "80,00\u00a0z\u0142" in html
        assert "20,00\u00a0z\u0142" in html

    def test_build_threshold_settlement_below_threshold(self, dummy_client):
        items = [
            {
                "product": {"title": "Indie Song", "settlement type": "threshold", "threshold": 200.0},
                "platform": {"name": "Apple Music"},
                "revenue": 150.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "0,00\u00a0z\u0142" in html

    def test_missing_client_data(self):
        items = []
        html = build_settlement_html(None, items)

        assert "\u2014" in html
        assert "<b>0%</b>" in html

    def test_gross_column_from_platform_report(self, dummy_client):
        items = [
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Legimi"},
                "revenue": 100.0,
                "revenue_gross": 123.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "BRUTTO" in html
        assert "123,00\u00a0z\u0142" in html

    def test_gross_follows_threshold_reduction(self, dummy_client):
        items = [
            {
                "product": {"title": "Album One", "settlement type": "threshold", "threshold": 50.0},
                "platform": {"name": "Storytel"},
                "revenue": 100.0,
                "revenue_gross": 123.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        # Netto spada ze 100 do 50, wiec brutto skalujemy tak samo: 123 -> 61,50.
        assert "50,00\u00a0z\u0142" in html
        assert "61,50\u00a0z\u0142" in html

    def test_gross_is_empty_when_not_imported(self, dummy_client):
        items = [
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Legimi"},
                "revenue": 100.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "BRUTTO" in html
        assert html.count("\u2014") >= 2

    def test_platform_subtotals_and_chart_for_multiple_platforms(self, dummy_client):
        items = [
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Legimi"},
                "revenue": 100.0
            },
            {
                "product": {"title": "Second Track", "settlement type": "instant"},
                "platform": {"name": "Legimi"},
                "revenue": 50.0
            },
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Storytel"},
                "revenue": 20.0
            },
        ]
        html = build_settlement_html(dummy_client, items)

        assert "Razem Legimi" in html
        # Storytel ma tylko jedna pozycje - podsumowanie bylo by jej powtorzeniem.
        assert "Razem Storytel" not in html
        # Suma platformy Legimi: 100 + 50.
        assert "150,00\u00a0z\u0142" in html
        assert "chart://platforms" in html

    def test_no_subtotals_and_no_chart_for_single_platform(self, dummy_client):
        items = [
            {
                "product": {"title": "Hit Track", "settlement type": "instant"},
                "platform": {"name": "Legimi"},
                "revenue": 100.0
            }
        ]
        html = build_settlement_html(dummy_client, items)

        assert "Razem Legimi" not in html
        assert "chart://platforms" not in html
        assert "RAZEM" in html

    def test_style_from_configuration_is_used(self, dummy_client):
        style = dict(DEFAULT_STYLE)
        style["red"] = "#00ff00"
        style["heading_font"] = "Verdana"
        style["company_name"] = "Testowe Wydawnictwo"

        html = build_settlement_html(dummy_client, [], style=style)

        assert "#00ff00" in html
        assert "face='Verdana'" in html
        assert "Testowe Wydawnictwo" in html
