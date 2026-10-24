from datetime import datetime

import pytest

from platforms.reports import (
    PLATFORM_REPORTS_ROOT,
    ReportFileError,
    ensure_current_year_reports_directory,
    ensure_platform_reports_root_directory,
    get_platform_report_path,
    list_trashed_reports,
    move_report_to_year,
    move_report_to_trash,
    permanently_delete_trashed_report,
    restore_report_from_trash,
    safe_platform_filename,
)


def test_default_root_is_inside_reports_directory():
    assert PLATFORM_REPORTS_ROOT.name == "Raporty Platform"
    assert PLATFORM_REPORTS_ROOT.parent.name == "Reports"


def test_creates_platform_reports_root_directory(tmp_path):
    reports_root = tmp_path / "Raporty Platform"

    result = ensure_platform_reports_root_directory(reports_root)

    assert result == reports_root
    assert reports_root.is_dir()


def test_creates_directory_for_current_year(tmp_path):
    directory = ensure_current_year_reports_directory(
        root_directory=tmp_path / "Raporty Platform",
        now=datetime(2030, 6, 1),
    )

    assert directory == tmp_path / "Raporty Platform" / "2030"
    assert directory.is_dir()


def test_platform_has_one_stable_excel_path_per_year(tmp_path):
    first_path = get_platform_report_path(
        "Legimi",
        root_directory=tmp_path,
        now=datetime(2030, 1, 1),
    )
    second_path = get_platform_report_path(
        "Legimi",
        root_directory=tmp_path,
        now=datetime(2030, 12, 31),
    )

    assert first_path == second_path
    assert first_path == tmp_path / "2030" / "Legimi.xlsx"


def test_platform_filename_is_safe():
    assert safe_platform_filename('Platforma: test/raport') == "Platforma_ test_raport"


def test_report_can_be_moved_to_year_detected_from_its_dates(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    source = reports_root / "2026" / "Storytel.xlsx"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"report from 2025")

    destination = move_report_to_year(
        source,
        2025,
        root_directory=reports_root,
    )

    assert destination == reports_root / "2025" / "Storytel.xlsx"
    assert destination.read_bytes() == b"report from 2025"
    assert not source.exists()


def test_moving_report_to_correct_year_never_overwrites_existing_file(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    source = reports_root / "2026" / "Storytel.xlsx"
    destination = reports_root / "2025" / "Storytel.xlsx"
    source.parent.mkdir(parents=True)
    destination.parent.mkdir(parents=True)
    source.write_bytes(b"new")
    destination.write_bytes(b"existing")

    with pytest.raises(ReportFileError, match="istnieje już raport"):
        move_report_to_year(source, 2025, root_directory=reports_root)

    assert source.read_bytes() == b"new"
    assert destination.read_bytes() == b"existing"


def test_report_can_be_moved_to_trash_and_restored(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    report_path = reports_root / "2030" / "Legimi.xlsx"
    report_path.parent.mkdir(parents=True)
    report_path.write_bytes(b"report")
    deleted_at = datetime(2030, 8, 31, 12, 30, 15, 123456)

    trashed = move_report_to_trash(
        report_path,
        root_directory=reports_root,
        now=deleted_at,
    )

    assert not report_path.exists()
    assert trashed.path == (
        reports_root
        / ".Kosz"
        / "20300831_123015_123456"
        / "2030"
        / "Legimi.xlsx"
    )
    assert trashed.path.read_bytes() == b"report"
    assert trashed.original_relative_path.as_posix() == "2030/Legimi.xlsx"
    assert list_trashed_reports(reports_root) == [trashed]

    restored_path = restore_report_from_trash(
        trashed.path,
        root_directory=reports_root,
    )

    assert restored_path == report_path
    assert restored_path.read_bytes() == b"report"
    assert list_trashed_reports(reports_root) == []


def test_restore_does_not_overwrite_existing_report(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    report_path = reports_root / "2030" / "Legimi.xlsx"
    report_path.parent.mkdir(parents=True)
    report_path.write_bytes(b"old")
    trashed = move_report_to_trash(report_path, root_directory=reports_root)
    report_path.write_bytes(b"new")

    with pytest.raises(ReportFileError, match="tej samej nazwie"):
        restore_report_from_trash(trashed.path, root_directory=reports_root)

    assert report_path.read_bytes() == b"new"
    assert trashed.path.read_bytes() == b"old"


def test_file_outside_reports_directory_cannot_be_deleted(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    reports_root.mkdir()
    outside_file = tmp_path / "outside.xlsx"
    outside_file.write_bytes(b"report")

    with pytest.raises(ReportFileError, match="katalogu raportów"):
        move_report_to_trash(outside_file, root_directory=reports_root)

    assert outside_file.exists()


def test_report_can_be_permanently_deleted_only_from_trash(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    report_path = reports_root / "2030" / "Legimi.xlsx"
    report_path.parent.mkdir(parents=True)
    report_path.write_bytes(b"report")
    trashed = move_report_to_trash(report_path, root_directory=reports_root)

    permanently_delete_trashed_report(
        trashed.path,
        root_directory=reports_root,
    )

    assert not trashed.path.exists()
    assert list_trashed_reports(reports_root) == []

    report_path.write_bytes(b"new report")
    with pytest.raises(ReportFileError, match="katalogu raportów"):
        permanently_delete_trashed_report(
            report_path,
            root_directory=reports_root,
        )
    assert report_path.exists()
