from core.report_generator import _percent, build_settlement_html, compute_settlement_rows


CLIENT = {"id": 1, "name": "Klient", "cut": 20}


def item(product, revenue=100.0, **extra):
    return {
        "product": product,
        "platform": {"name": "Legimi"},
        "revenue": revenue,
        **extra,
    }


class TestPercentHelper:

    def test_drops_trailing_zeros(self):
        assert _percent(20) == "20%"
        assert _percent(100.0) == "100%"
        assert _percent(0) == "0%"

    def test_keeps_fractional_part(self):
        assert _percent(12.5) == "12,5%"

    def test_survives_garbage(self):
        assert _percent(None) == "0%"
        assert _percent("abc") == "0%"


class TestCommissionSource:

    def test_commission_comes_from_the_product(self):
        product = {"title": "A", "cut": 30, "settlement type": "instant"}

        _, rows = compute_settlement_rows(CLIENT, [item(product)])

        assert rows[0]["cut"] == 30.0
        assert rows[0]["fee"] == 30.0
        assert rows[0]["for_client"] == 70.0

    def test_zero_commission_on_product_is_respected(self):
        # 0% to świadomy wybór, nie brak danych - prowizja klienta nie wraca.
        product = {"title": "B", "cut": 0, "settlement type": "instant"}

        _, rows = compute_settlement_rows(CLIENT, [item(product)])

        assert rows[0]["cut"] == 0.0
        assert rows[0]["for_client"] == 100.0

    def test_manual_commission_overrides_the_product(self):
        product = {"title": "C", "cut": 30, "settlement type": "instant"}

        _, rows = compute_settlement_rows(CLIENT, [item(product, cut=12.5)])

        assert rows[0]["cut"] == 12.5
        assert rows[0]["fee"] == 12.5

    def test_empty_manual_commission_falls_back_to_the_product(self):
        product = {"title": "C", "cut": 30, "settlement type": "instant"}

        _, rows = compute_settlement_rows(CLIENT, [item(product, cut=None)])

        assert rows[0]["cut"] == 30.0

    def test_product_without_commission_uses_the_client(self):
        product = {"title": "D", "settlement type": "instant"}

        _, rows = compute_settlement_rows(CLIENT, [item(product)])

        assert rows[0]["cut"] == 20.0

    def test_polish_field_names_are_accepted(self):
        product = {"tytul": "E", "procent": "12,5", "typ rozliczenia": "od razu"}

        _, rows = compute_settlement_rows(CLIENT, [item(product)])

        assert rows[0]["cut"] == 12.5

    def test_commission_is_taken_from_amount_after_threshold(self):
        product = {
            "title": "F",
            "cut": 50,
            "settlement type": "threshold",
            "threshold": 40,
        }

        _, rows = compute_settlement_rows(CLIENT, [item(product)])

        assert rows[0]["net"] == 60.0
        assert rows[0]["fee"] == 30.0
        assert rows[0]["for_client"] == 30.0


class TestEffectiveCommission:

    def test_header_shows_the_single_rate_used(self):
        product = {"title": "A", "cut": 30, "settlement type": "instant"}

        effective, _ = compute_settlement_rows(CLIENT, [item(product)])

        assert effective == 30.0

    def test_header_averages_mixed_rates_by_amount(self):
        rows = [
            item({"title": "A", "cut": 40, "settlement type": "instant"}, 100.0),
            item({"title": "B", "cut": 10, "settlement type": "instant"}, 300.0),
        ]

        effective, _ = compute_settlement_rows(CLIENT, rows)

        # 40 zł + 30 zł prowizji z 400 zł przychodu.
        assert effective == 17.5

    def test_header_is_zero_without_items(self):
        effective, rows = compute_settlement_rows(CLIENT, [])

        assert effective == 0.0
        assert rows == []


class TestCommissionInHtml:

    def test_row_shows_its_own_rate(self):
        rows = [
            item({"title": "Ksiazka A", "cut": 30, "settlement type": "instant"}, 100.0),
            item({"title": "Ksiazka B", "cut": 10, "settlement type": "instant"}, 100.0),
        ]

        html = build_settlement_html(CLIENT, rows)

        assert "30%" in html
        assert "10%" in html
        # Nagłówek pokazuje stawkę skuteczną z całego rozliczenia.
        assert "<b>20%</b>" in html


class TestSettlementPeriodInHeader:
    """Nieregularny zakres dat musi być widoczny na dokumencie - inaczej
    klient nie wie, jaki okres obejmuje rozliczenie kwartalne."""

    def _items(self):
        return [item({"title": "A", "cut": 30, "settlement type": "instant"})]

    def test_period_is_printed_in_the_header(self):
        html = build_settlement_html(
            CLIENT,
            self._items(),
            period="IV kwartał 2025 (2025-10-02 – 2025-12-28)",
        )

        assert "Okres: IV kwartał 2025 (2025-10-02 – 2025-12-28)" in html

    def test_plain_month_is_printed_too(self):
        html = build_settlement_html(CLIENT, self._items(), period="Sierpień 2026")

        assert "Okres: Sierpień 2026" in html

    def test_header_stays_clean_without_a_period(self):
        html = build_settlement_html(CLIENT, self._items())

        assert "Okres:" not in html

    def test_blank_period_is_ignored(self):
        html = build_settlement_html(CLIENT, self._items(), period="   ")

        assert "Okres:" not in html

    def test_period_and_number_live_together(self):
        html = build_settlement_html(
            CLIENT, self._items(), number="2025/12/007", period="IV kwartał 2025"
        )

        assert "Nr 2025/12/007" in html
        assert "Okres: IV kwartał 2025" in html

