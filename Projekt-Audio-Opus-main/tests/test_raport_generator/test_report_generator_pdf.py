import os
import pytest
from PySide6.QtGui import QGuiApplication
from core.report_generator import render_settlement_pdf_bytes, generate_settlement_pdf


@pytest.fixture(scope="session")
def q_app():
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication([])
    return app


@pytest.fixture
def dummy_client_and_items():
    client = {"id": 999, "name": "Test Company LLC", "cut": 15}
    items = []
    return client, items


class TestPdfGeneration:

    def test_render_settlement_pdf_bytes(self, q_app, dummy_client_and_items):
        client, items = dummy_client_and_items

        pdf_data = render_settlement_pdf_bytes(client, items)

        assert isinstance(pdf_data, bytes)
        assert len(pdf_data) > 0
        assert pdf_data.startswith(b"%PDF")

    def test_render_settlement_pdf_bytes_with_number(self, q_app, dummy_client_and_items):
        client, items = dummy_client_and_items

        pdf_data = render_settlement_pdf_bytes(client, items, number="2026/09/001")

        assert isinstance(pdf_data, bytes)
        assert pdf_data.startswith(b"%PDF")

    def test_generate_settlement_pdf_default_path_uses_number(
        self, q_app, dummy_client_and_items, tmp_path, monkeypatch
    ):
        client, items = dummy_client_and_items

        from core import report_generator
        test_folder = str(tmp_path / "NumberedReports") + "/"
        monkeypatch.setattr(report_generator, "FOLDER", test_folder)

        result_path = generate_settlement_pdf(client, items, number="2026/09/012")

        assert "rozliczenie_2026-09-012_" in result_path
        assert os.path.exists(result_path)

    def test_generate_settlement_pdf_custom_path(self, q_app, dummy_client_and_items, tmp_path):
        client, items = dummy_client_and_items
        save_path = str(tmp_path / "custom_folder" / "test_report.pdf")

        result_path = generate_settlement_pdf(client, items, save_path=save_path)

        assert result_path == save_path
        assert os.path.exists(result_path)
        assert os.path.getsize(result_path) > 0

        with open(result_path, "rb") as f:
            header = f.read(4)
            assert header == b"%PDF"

    def test_generate_settlement_pdf_default_path(self, q_app, dummy_client_and_items, tmp_path, monkeypatch):
        client, items = dummy_client_and_items

        from core import report_generator
        test_folder = str(tmp_path / "DefaultReports") + "/"
        monkeypatch.setattr(report_generator, "FOLDER", test_folder)

        result_path = generate_settlement_pdf(client, items)

        assert result_path.startswith(test_folder)
        assert "Test_Company_LLC" in result_path
        assert result_path.endswith(".pdf")
        assert os.path.exists(result_path)

    def test_generate_settlement_pdf_default_path_sanitizes_client_name(
        self, q_app, tmp_path, monkeypatch
    ):
        """Nazwa klienta ze znakami niedozwolonymi w nazwie pliku (np. z importu
        albo literówki) nie może rozjechać ścieżki zapisu raportu."""
        client = {"id": 1, "name": 'Klient/Ze:Znakami"Path*?', "cut": 10}

        from core import report_generator
        test_folder = str(tmp_path / "SafeNameReports")
        monkeypatch.setattr(report_generator, "FOLDER", test_folder)

        result_path = generate_settlement_pdf(client, [])

        # Ścieżka musi realnie leżeć w skonfigurowanym katalogu (bez sklejenia
        # bez separatora) i nie zawierać znaków ze sanityzowanej nazwy klienta.
        assert os.path.dirname(result_path) == test_folder
        assert os.path.exists(result_path)
        for character in '/:"*?':
            assert character not in os.path.basename(result_path)


class TestChartAndMetadata:

    @pytest.fixture
    def multi_platform_items(self):
        product = {"title": "Test Book", "settlement type": "instant"}
        return [
            {"product": product, "platform": {"name": "Legimi"}, "revenue": 100.0},
            {"product": product, "platform": {"name": "Storytel"}, "revenue": 40.0},
        ]

    def test_chart_is_built_for_several_platforms(self, q_app, multi_platform_items):
        from core.report_generator import build_platform_chart

        client = {"id": 1, "name": "Test", "cut": 10}
        image = build_platform_chart(client, multi_platform_items)

        assert image is not None
        assert not image.isNull()
        assert image.width() > 0

    def test_no_chart_for_single_platform(self, q_app):
        from core.report_generator import build_platform_chart

        client = {"id": 1, "name": "Test", "cut": 10}
        items = [{
            "product": {"title": "Test Book", "settlement type": "instant"},
            "platform": {"name": "Legimi"},
            "revenue": 100.0,
        }]

        assert build_platform_chart(client, items) is None

    def test_platform_totals_use_amounts_after_threshold(self, multi_platform_items):
        from core.report_generator import platform_totals

        client = {"id": 1, "name": "Test", "cut": 10}
        totals = platform_totals(client, multi_platform_items)

        assert list(totals) == ["Legimi", "Storytel"]
        assert totals["Legimi"] == 100.0
        assert totals["Storytel"] == 40.0

    def test_pdf_writer_gets_document_title(self, q_app, tmp_path):
        from core.report_generator import _make_pdf_writer

        writer = _make_pdf_writer(str(tmp_path / "meta.pdf"), title="Raport testowy")

        assert writer.title() == "Raport testowy"

    def test_report_with_chart_is_written_to_file(self, q_app, multi_platform_items, tmp_path):
        client = {"id": 1, "name": "Test Client", "cut": 10}
        save_path = str(tmp_path / "chart_report.pdf")

        result_path = generate_settlement_pdf(client, multi_platform_items, save_path=save_path)

        assert os.path.getsize(result_path) > 0
        with open(result_path, "rb") as file:
            assert file.read(4) == b"%PDF"
