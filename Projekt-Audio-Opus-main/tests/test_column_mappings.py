from platforms.column_mappings import (
    layout_signature,
    load_platform_column_mappings,
    save_column_mapping,
)


HEADERS = ("Work Name", "EAN Code", "Statement Cycle", "Payable To Us")
COLUMNS = {"title": 0, "isbn": 1, "period": 2, "net": 3}


def test_mapping_roundtrip(tmp_path):
    database_path = tmp_path / "db.sqlite"

    saved = save_column_mapping(
        "Nowa platforma",
        HEADERS,
        "monthly",
        COLUMNS,
        database_path=database_path,
    )
    loaded = load_platform_column_mappings(
        "NOWA PLATFORMA",
        database_path=database_path,
    )

    assert saved.layout_signature == layout_signature(HEADERS)
    assert loaded[saved.layout_signature].columns == COLUMNS
    assert loaded[saved.layout_signature].headers == HEADERS


def test_same_layout_is_isolated_between_platforms(tmp_path):
    database_path = tmp_path / "db.sqlite"
    save_column_mapping(
        "Platforma A",
        HEADERS,
        "monthly",
        COLUMNS,
        database_path=database_path,
    )

    assert load_platform_column_mappings(
        "Platforma B",
        database_path=database_path,
    ) == {}


def test_saving_same_platform_and_layout_updates_mapping(tmp_path):
    database_path = tmp_path / "db.sqlite"
    save_column_mapping(
        "Platforma A",
        HEADERS,
        "monthly",
        COLUMNS,
        database_path=database_path,
    )
    updated_columns = {
        "title": 0,
        "isbn": 1,
        "transaction_date": 2,
        "net": 3,
    }
    saved = save_column_mapping(
        "Platforma A",
        HEADERS,
        "transaction",
        updated_columns,
        database_path=database_path,
    )

    loaded = load_platform_column_mappings(
        "Platforma A",
        database_path=database_path,
    )
    assert len(loaded) == 1
    assert loaded[saved.layout_signature].report_type == "transaction"
    assert loaded[saved.layout_signature].columns == updated_columns


def test_quarterly_mapping_accepts_period_and_quantity(tmp_path):
    database_path = tmp_path / "db.sqlite"
    columns = {
        "title": 0,
        "isbn": 1,
        "period": 2,
        "quantity": 3,
        "net": 4,
    }
    headers = (*HEADERS[:3], "Quantity", "Net")

    saved = save_column_mapping(
        "Storytel",
        headers,
        "quarterly",
        columns,
        database_path=database_path,
    )

    loaded = load_platform_column_mappings(
        "storytel",
        database_path=database_path,
    )[saved.layout_signature]
    assert loaded.report_type == "quarterly"
    assert loaded.columns == columns
