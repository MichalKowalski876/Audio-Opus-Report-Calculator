from pathlib import Path
from unittest.mock import patch

import pytest
from PySide6 import QtWidgets

from GUI.Widgets.Dialogs.ManualPlatformReportDialog import (
    ManualPlatformReportDialog,
)


@pytest.fixture(scope="module")
def qapp():
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication([])


@pytest.fixture
def dialog(qapp):
    with patch(
        "GUI.Widgets.Dialogs.ManualPlatformReportDialog.load_streaming_platforms",
        return_value=[{"id": 1, "name": "Storytel"}],
    ):
        value = ManualPlatformReportDialog()
    yield value
    value.close()


def test_attach_corrects_selected_year_from_report_dates(dialog, tmp_path):
    source = tmp_path / "report.xlsx"
    source.write_bytes(b"xlsx")
    destination = tmp_path / "Reports" / "Raporty Platform" / "2025" / "Storytel.xlsx"
    dialog.year_spin.setValue(2026)

    with (
        patch.object(
            QtWidgets.QFileDialog,
            "getOpenFileName",
            return_value=(str(source), ""),
        ),
        patch(
            "GUI.Widgets.Dialogs.ManualPlatformReportDialog.detect_report_years",
            return_value=(2025,),
        ),
        patch.object(
            QtWidgets.QMessageBox,
            "question",
            return_value=QtWidgets.QMessageBox.StandardButton.Yes,
        ),
        patch(
            "GUI.Widgets.Dialogs.ManualPlatformReportDialog.attach_platform_report",
            return_value=destination,
        ) as attach,
        patch.object(QtWidgets.QMessageBox, "information"),
    ):
        dialog.attach_report()

    attach.assert_called_once_with(str(source), "Storytel", 2025)
    assert dialog.year_spin.value() == 2025
    assert dialog.attached_report_path == destination


def test_attach_rejects_one_file_containing_multiple_years(dialog, tmp_path):
    source = tmp_path / "report.xlsx"
    source.write_bytes(b"xlsx")

    with (
        patch.object(
            QtWidgets.QFileDialog,
            "getOpenFileName",
            return_value=(str(source), ""),
        ),
        patch(
            "GUI.Widgets.Dialogs.ManualPlatformReportDialog.detect_report_years",
            return_value=(2025, 2026),
        ),
        patch.object(QtWidgets.QMessageBox, "critical") as critical,
        patch(
            "GUI.Widgets.Dialogs.ManualPlatformReportDialog.attach_platform_report"
        ) as attach,
    ):
        dialog.attach_report()

    attach.assert_not_called()
    assert "2025, 2026" in critical.call_args.args[2]
