from unittest.mock import patch

import pytest

from platforms.manual import (
    ManualReportError,
    add_streaming_platform,
    attach_platform_report,
    delete_streaming_platform,
    rename_streaming_platform,
)


def test_existing_platform_is_not_duplicated():
    existing = {
        "id": 3,
        "name": "Voices",
        "cut": 0,
        "integration": "voices",
    }
    with (
        patch(
            "platforms.manual.reports.database_controller.load_database",
            return_value=[existing],
        ),
        patch(
            "platforms.manual.reports.database_controller.item_add"
        ) as item_add,
    ):
        platform, created = add_streaming_platform("  voices ")

    assert platform is existing
    assert created is False
    item_add.assert_not_called()


def test_new_platform_is_added_without_automatic_integration():
    with (
        patch(
            "platforms.manual.reports.database_controller.load_database",
            return_value=[],
        ),
        patch(
            "platforms.manual.reports.database_controller.item_add",
            return_value=4,
        ) as item_add,
    ):
        platform, created = add_streaming_platform("Nowa Platforma")

    assert created is True
    assert platform == {
        "id": 4,
        "name": "Nowa Platforma",
        "cut": 0,
        "integration": "",
    }
    item_add.assert_called_once_with(
        {
            "name": "Nowa Platforma",
            "cut": 0,
            "integration": "",
        },
        "streamings",
    )


def test_platform_is_renamed_in_database_and_product_assignments():
    platform = {"id": 2, "name": "Storytel", "integration": "storytel"}
    products = [
        {"id": 1, "title": "Książka", "streaming": ["Storytel", "Legimi"]},
    ]
    with (
        patch(
            "platforms.manual.reports.database_controller.load_database",
            side_effect=lambda name: [platform] if name == "streamings" else products,
        ),
        patch(
            "platforms.manual.reports.database_controller.item_modify"
        ) as item_modify,
        patch(
            "platforms.manual.reports.database_controller.save_database"
        ) as save_database,
    ):
        renamed = rename_streaming_platform(2, " Storytel Polska ")

    assert renamed["name"] == "Storytel Polska"
    item_modify.assert_called_once_with(
        2, "name", "Storytel Polska", "streamings"
    )
    save_database.assert_called_once_with(
        "products",
        [
            {
                "id": 1,
                "title": "Książka",
                "streaming": ["Storytel Polska", "Legimi"],
            }
        ],
    )


def test_platform_name_cannot_duplicate_another_platform():
    platforms = [
        {"id": 1, "name": "Legimi"},
        {"id": 2, "name": "Storytel"},
    ]
    with (
        patch(
            "platforms.manual.reports.database_controller.load_database",
            return_value=platforms,
        ),
        patch(
            "platforms.manual.reports.database_controller.item_modify"
        ) as item_modify,
    ):
        with pytest.raises(ManualReportError, match="już na liście"):
            rename_streaming_platform(2, "legimi")

    item_modify.assert_not_called()


def test_platform_is_soft_deleted_and_removed_from_product_assignments():
    platform = {"id": 2, "name": "Storytel", "integration": "storytel"}
    products = [
        {"id": 1, "title": "Książka", "streaming": ["Storytel", "Legimi"]},
    ]
    with (
        patch(
            "platforms.manual.reports.database_controller.load_database",
            side_effect=lambda name: [platform] if name == "streamings" else products,
        ),
        patch(
            "platforms.manual.reports.database_controller.item_remove"
        ) as item_remove,
        patch(
            "platforms.manual.reports.database_controller.save_database"
        ) as save_database,
    ):
        deleted = delete_streaming_platform(2)

    assert deleted is platform
    item_remove.assert_called_once_with(2, "streamings")
    save_database.assert_called_once_with(
        "products",
        [{"id": 1, "title": "Książka", "streaming": ["Legimi"]}],
    )


def test_attached_report_replaces_previous_platform_file(tmp_path):
    reports_root = tmp_path / "Raporty Platform"
    year_directory = reports_root / "2030"
    year_directory.mkdir(parents=True)
    previous_report = year_directory / "Nowa Platforma.xlsx"
    previous_report.write_bytes(b"old report")

    source = tmp_path / "new-report.csv"
    source.write_bytes(b"new report")

    destination = attach_platform_report(
        source,
        "Nowa Platforma",
        2030,
        root_directory=reports_root,
    )

    assert destination == year_directory / "Nowa Platforma.csv"
    assert destination.read_bytes() == b"new report"
    assert not previous_report.exists()


def test_empty_report_is_rejected(tmp_path):
    source = tmp_path / "empty.xlsx"
    source.write_bytes(b"")

    with pytest.raises(ManualReportError, match="pusty"):
        attach_platform_report(
            source,
            "Legimi",
            2030,
            root_directory=tmp_path / "Raporty Platform",
        )
