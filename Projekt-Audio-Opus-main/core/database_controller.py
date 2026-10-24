import json
import os
import re
import sqlite3
from datetime import datetime
from typing import Any, List

from core import paths

# Katalog na dane odczytu/zapisu.
FOLDER = paths.data_path("Databases")
DATABASE_FILENAME = "db.sqlite"

RELATIONAL_DATABASES = {"clients", "products"}

_NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _ensure_folder() -> None:
    os.makedirs(FOLDER, exist_ok=True)


def _database_path() -> str:
    return os.path.join(FOLDER, DATABASE_FILENAME)


def _get_conn() -> sqlite3.Connection:
    _ensure_folder()

    connection = sqlite3.connect(_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")

    # Nie korzystamy z globalnego cache.
    # Jest to ważne, gdy testy zmieniają FOLDER na katalog tymczasowy.
    _ensure_relational_schema(connection)

    return connection


def _validate_name(name: str) -> str:
    if not _NAME_RE.match(name):
        raise ValueError(
            "Invalid db_name; use only letters, digits and underscore"
        )
    return name


def _table_columns(
        connection: sqlite3.Connection,
        table: str,
) -> set[str]:
    return {
        str(row[1])
        for row in connection.execute(
            f'PRAGMA table_info("{table}")'
        )
    }


def _table_exists(
        connection: sqlite3.Connection,
        table: str,
) -> bool:
    return connection.execute(
        """
        SELECT 1
        FROM sqlite_master
        WHERE type = 'table' AND name = ?
        """,
        (table,),
    ).fetchone() is not None


def _is_legacy_json_table(
        connection: sqlite3.Connection,
        table: str,
) -> bool:
    return (
            _table_exists(connection, table)
            and _table_columns(connection, table) == {"id", "data"}
    )


def _create_relational_tables(
        connection: sqlite3.Connection,
) -> None:
    statements = (
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL DEFAULT '',
            email TEXT NOT NULL DEFAULT '',
            deleted_at TEXT
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            cut REAL NOT NULL DEFAULT 0,
            author TEXT NOT NULL DEFAULT '',
            isbn TEXT NOT NULL DEFAULT '',
            settlement_type TEXT NOT NULL DEFAULT 'instant',
            threshold REAL NOT NULL DEFAULT 0,
            client_id INTEGER,
            deleted_at TEXT,
            FOREIGN KEY (client_id)
                REFERENCES clients(id)
                ON DELETE SET NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS product_streamings (
            product_id INTEGER NOT NULL,
            platform_name TEXT NOT NULL COLLATE NOCASE,
            position INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (product_id, platform_name),
            FOREIGN KEY (product_id)
                REFERENCES products(id)
                ON DELETE CASCADE
        )
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_clients_name
            ON clients(name COLLATE NOCASE)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_client
            ON products(client_id)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_products_isbn
            ON products(isbn)
        """,
        """
        CREATE INDEX IF NOT EXISTS idx_product_streamings_platform
            ON product_streamings(platform_name COLLATE NOCASE)
        """,
    )

    for statement in statements:
        connection.execute(statement)


def _legacy_rows(
        connection: sqlite3.Connection,
        table: str,
) -> list[dict]:
    rows = connection.execute(
        f'SELECT id, data FROM "{table}" ORDER BY id'
    ).fetchall()

    result = []

    for row in rows:
        try:
            item = json.loads(row["data"])
        except (TypeError, json.JSONDecodeError) as error:
            raise RuntimeError(
                f"Nie udało się zmigrować rekordu "
                f"{table} ID {row['id']}: {error}"
            ) from error

        item["id"] = int(row["id"])
        result.append(item)

    return result


def _deleted_at(item: dict) -> str | None:
    if not item.get("_deleted"):
        return None

    return str(
        item.get("_deleted_at")
        or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


def _client_id_by_name(
        connection: sqlite3.Connection,
        name: object,
) -> int | None:
    client_name = str(name or "").strip()

    if not client_name:
        return None

    row = connection.execute(
        """
        SELECT id
        FROM clients
        WHERE name = ? COLLATE NOCASE
        ORDER BY (deleted_at IS NOT NULL), id
        LIMIT 1
        """,
        (client_name,),
    ).fetchone()

    return int(row["id"]) if row else None


def _resolve_client_id(
        connection: sqlite3.Connection,
        name: object,
) -> int | None:
    client_name = str(name or "").strip()

    if not client_name:
        return None

    client_id = _client_id_by_name(
        connection,
        client_name,
    )

    if client_id is not None:
        return client_id

    cursor = connection.execute(
        "INSERT INTO clients (name, email) VALUES (?, '')",
        (client_name,),
    )

    return int(cursor.lastrowid)


def _migrate_legacy_tables(
        connection: sqlite3.Connection,
) -> None:
    clients_are_legacy = _is_legacy_json_table(
        connection,
        "clients",
    )

    products_are_legacy = _is_legacy_json_table(
        connection,
        "products",
    )

    if not clients_are_legacy and not products_are_legacy:
        return

    legacy_clients = (
        _legacy_rows(connection, "clients")
        if clients_are_legacy
        else []
    )

    legacy_products = (
        _legacy_rows(connection, "products")
        if products_are_legacy
        else []
    )

    product_owners: dict[int, int] = {}

    for client in legacy_clients:
        client_id = int(client["id"])

        for product_id in client.get("products", []):
            try:
                product_owners[int(product_id)] = client_id
            except (TypeError, ValueError):
                continue

    connection.execute("BEGIN IMMEDIATE")

    with connection:
        if clients_are_legacy:
            connection.execute(
                'ALTER TABLE clients RENAME TO "_legacy_clients_json"'
            )

        if products_are_legacy:
            connection.execute(
                'ALTER TABLE products RENAME TO "_legacy_products_json"'
            )

        _create_relational_tables(connection)

        for client in legacy_clients:
            connection.execute(
                """
                INSERT INTO clients (
                    id,
                    name,
                    email,
                    deleted_at
                )
                VALUES (?, ?, ?, ?)
                """,
                (
                    int(client["id"]),
                    str(client.get("name") or "").strip(),
                    str(client.get("email") or "").strip(),
                    _deleted_at(client),
                ),
            )

        for product in legacy_products:
            product_id = int(product["id"])
            client_id = product_owners.get(product_id)

            if client_id is None:
                client_id = _resolve_client_id(
                    connection,
                    product.get("publisher"),
                )

            connection.execute(
                """
                INSERT INTO products (
                    id,
                    title,
                    cut,
                    author,
                    isbn,
                    settlement_type,
                    threshold,
                    client_id,
                    deleted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    product_id,
                    str(product.get("title") or "").strip(),
                    float(product.get("cut") or 0),
                    str(product.get("author") or "").strip(),
                    str(product.get("isbn") or "").strip(),
                    str(
                        product.get("settlement type")
                        or "instant"
                    ).strip(),
                    float(product.get("threshold") or 0),
                    client_id,
                    _deleted_at(product),
                ),
            )

            assigned_platforms = product.get(
                "streaming",
                [],
            )

            if not isinstance(assigned_platforms, list):
                assigned_platforms = (
                    [assigned_platforms]
                    if assigned_platforms
                    else []
                )

            for position, platform_name in enumerate(
                    assigned_platforms
            ):
                name = str(platform_name or "").strip()

                if name:
                    connection.execute(
                        """
                        INSERT OR IGNORE INTO product_streamings (
                            product_id,
                            platform_name,
                            position
                        )
                        VALUES (?, ?, ?)
                        """,
                        (
                            product_id,
                            name,
                            position,
                        ),
                    )

        if clients_are_legacy and not products_are_legacy:
            for product_id, client_id in product_owners.items():
                connection.execute(
                    """
                    UPDATE products
                    SET client_id = ?
                    WHERE id = ?
                    """,
                    (
                        client_id,
                        product_id,
                    ),
                )

        if clients_are_legacy:
            connection.execute(
                'DROP TABLE "_legacy_clients_json"'
            )

        if products_are_legacy:
            connection.execute(
                'DROP TABLE "_legacy_products_json"'
            )


def _relational_schema_ready(
        connection: sqlite3.Connection,
) -> bool:
    required_tables = {
        "clients",
        "products",
        "product_streamings",
    }

    existing_tables = {
        str(row["name"])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        )
    }

    if not required_tables <= existing_tables:
        return False

    if not {
               "id",
               "name",
               "email",
               "deleted_at",
           } <= _table_columns(connection, "clients"):
        return False

    if not {
               "id",
               "title",
               "cut",
               "author",
               "isbn",
               "settlement_type",
               "threshold",
               "client_id",
               "deleted_at",
           } <= _table_columns(connection, "products"):
        return False

    if not {
               "product_id",
               "platform_name",
               "position",
           } <= _table_columns(
        connection,
        "product_streamings",
    ):
        return False

    required_indexes = {
        "idx_clients_name",
        "idx_products_client",
        "idx_products_isbn",
        "idx_product_streamings_platform",
    }

    existing_indexes = {
        str(row["name"])
        for row in connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'index'
            """
        )
    }

    return required_indexes <= existing_indexes


def _ensure_relational_schema(
        connection: sqlite3.Connection,
) -> None:
    _migrate_legacy_tables(connection)

    if _relational_schema_ready(connection):
        return

    _create_relational_tables(connection)

    if "position" not in _table_columns(
            connection,
            "product_streamings",
    ):
        connection.execute(
            """
            ALTER TABLE product_streamings
            ADD COLUMN position INTEGER NOT NULL DEFAULT 0
            """
        )

    connection.commit()


def _ensure_table(
        connection: sqlite3.Connection,
        table: str,
) -> None:
    connection.execute(
        f'CREATE TABLE IF NOT EXISTS "{table}" '
        "(id INTEGER PRIMARY KEY, data TEXT NOT NULL)"
    )

    connection.commit()


def _json_path(db_name: str) -> str:
    return os.path.join(
        FOLDER,
        f"{db_name}.json",
    )


def _sync_json_from_sqlite(
        db_name: str,
        connection: sqlite3.Connection,
) -> None:
    if db_name in RELATIONAL_DATABASES:
        return

    rows = connection.execute(
        f'SELECT id, data FROM "{db_name}" ORDER BY id'
    ).fetchall()

    result = []

    for row in rows:
        item = json.loads(row["data"])
        item["id"] = row["id"]
        result.append(item)

    with open(
            _json_path(db_name),
            "w",
            encoding="utf-8",
    ) as file:
        json.dump(
            result,
            file,
            indent=4,
            ensure_ascii=False,
        )


def _import_json_to_sqlite_if_present(
        db_name: str,
        connection: sqlite3.Connection,
) -> None:
    if db_name in RELATIONAL_DATABASES:
        return

    path = _json_path(db_name)

    if not os.path.exists(path):
        return

    count = connection.execute(
        f'SELECT COUNT(1) FROM "{db_name}"'
    ).fetchone()[0]

    if count:
        return

    with open(
            path,
            "r",
            encoding="utf-8",
    ) as file:
        data = json.load(file)

    for item in data:
        item_id = item.get("id")

        payload = json.dumps(
            {
                key: value
                for key, value in item.items()
                if key != "id"
            },
            ensure_ascii=False,
        )

        if item_id is None:
            connection.execute(
                f'INSERT INTO "{db_name}" (data) VALUES (?)',
                (payload,),
            )
        else:
            connection.execute(
                f'INSERT INTO "{db_name}" (id, data) VALUES (?, ?)',
                (
                    int(item_id),
                    payload,
                ),
            )

    connection.commit()


def _prepare_table(
        table: str,
) -> sqlite3.Connection:
    connection = _get_conn()

    if table not in RELATIONAL_DATABASES:
        _ensure_table(
            connection,
            table,
        )

        _import_json_to_sqlite_if_present(
            table,
            connection,
        )

    return connection


def _number(value: object) -> int | float:
    number = float(value or 0)
    return int(number) if number.is_integer() else number


def _load_clients(
        connection: sqlite3.Connection,
        include_deleted: bool,
) -> list[dict]:
    products_map = {}
    for prow in connection.execute("SELECT id, client_id FROM products WHERE client_id IS NOT NULL").fetchall():
        products_map.setdefault(int(prow["client_id"]), []).append(int(prow["id"]))

    condition = "" if include_deleted else "WHERE deleted_at IS NULL"
    rows = connection.execute(
        f"SELECT id, name, email, deleted_at FROM clients {condition} ORDER BY id"
    ).fetchall()

    result = []
    for row in rows:
        client_id = int(row["id"])
        item = {
            "name": str(row["name"] or ""),
            "email": str(row["email"] or ""),
            "products": products_map.get(client_id, []),
        }
        if row["deleted_at"]:
            item["_deleted"] = True
            item["_deleted_at"] = str(row["deleted_at"])
        item["id"] = client_id
        result.append(item)
    return result


def _load_products(
        connection: sqlite3.Connection,
        include_deleted: bool,
) -> list[dict]:
    condition = "" if include_deleted else "WHERE p.deleted_at IS NULL"
    rows = connection.execute(
        f"""
        SELECT p.id, p.title, p.cut, p.author, p.isbn,
               p.settlement_type, p.threshold, p.deleted_at,
               COALESCE(c.name, '') AS publisher
        FROM products AS p
        LEFT JOIN clients AS c ON c.id = p.client_id
        {condition}
        ORDER BY p.id
        """
    ).fetchall()
    platform_rows = connection.execute(
        """
        SELECT product_id, platform_name
        FROM product_streamings
        ORDER BY product_id, position, platform_name COLLATE NOCASE
        """
    ).fetchall()
    platforms_by_product: dict[int, list[str]] = {}
    for platform in platform_rows:
        platforms_by_product.setdefault(
            int(platform["product_id"]), []
        ).append(str(platform["platform_name"]))

    result = []
    for row in rows:
        product_id = int(row["id"])
        item = {
            "title": str(row["title"] or ""),
            "cut": _number(row["cut"]),
            "author": str(row["author"] or ""),
            "publisher": str(row["publisher"] or ""),
            "isbn": str(row["isbn"] or ""),
            "settlement type": str(row["settlement_type"] or "instant"),
            "threshold": _number(row["threshold"]),
        }
        assigned_platforms = platforms_by_product.get(product_id, [])
        if assigned_platforms:
            item["streaming"] = assigned_platforms
        if row["deleted_at"]:
            item["_deleted"] = True
            item["_deleted_at"] = str(row["deleted_at"])
        item["id"] = product_id
        result.append(item)
    return result


def load_database(
        db_name: str = "clients",
        include_deleted: bool = False,
) -> List[Any]:
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        if table == "clients":
            return _load_clients(connection, include_deleted)
        if table == "products":
            return _load_products(connection, include_deleted)

        rows = connection.execute(
            f'SELECT id, data FROM "{table}" ORDER BY id'
        ).fetchall()
        result = []
        for row in rows:
            item = json.loads(row["data"])
            if not include_deleted and item.get("_deleted"):
                continue
            item["id"] = row["id"]
            result.append(item)
        return result
    finally:
        connection.close()


def _existing_deleted_at(
        connection: sqlite3.Connection,
        table: str,
        item_id: int,
) -> str | None:
    row = connection.execute(
        f'SELECT deleted_at FROM "{table}" WHERE id = ?',
        (item_id,),
    ).fetchone()
    return str(row["deleted_at"]) if row and row["deleted_at"] else None


def _item_deleted_at(
        connection: sqlite3.Connection,
        table: str,
        item: dict,
) -> str | None:
    if "_deleted" not in item:
        return _existing_deleted_at(connection, table, int(item["id"]))
    return _deleted_at(item)


def _save_clients(connection: sqlite3.Connection, data) -> None:
    client_ids = []
    assignments: dict[int, int] = {}
    for item in data:
        item_id = int(item["id"])
        client_ids.append(item_id)
        connection.execute(
            """
            INSERT INTO clients (id, name, email, deleted_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                email = excluded.email,
                deleted_at = excluded.deleted_at
            """,
            (
                item_id,
                str(item.get("name") or "").strip(),
                str(item.get("email") or "").strip(),
                _item_deleted_at(connection, "clients", item),
            ),
        )
        for product_id in item.get("products", []):
            product_id = int(product_id)
            previous_owner = assignments.get(product_id)
            if previous_owner is not None and previous_owner != item_id:
                raise ValueError(
                    f"Produkt {product_id} nie może należeć do dwóch klientów."
                )
            assignments[product_id] = item_id

    if client_ids:
        placeholders = ", ".join("?" for _ in client_ids)
        connection.execute(
            f"UPDATE products SET client_id = NULL "
            f"WHERE client_id IN ({placeholders})",
            client_ids,
        )
    for product_id, client_id in assignments.items():
        connection.execute(
            "UPDATE products SET client_id = ? WHERE id = ?",
            (client_id, product_id),
        )


def _save_products(connection: sqlite3.Connection, data) -> None:
    for item in data:
        item_id = int(item["id"])
        client_id = _resolve_client_id(connection, item.get("publisher"))
        connection.execute(
            """
            INSERT INTO products (
                id, title, cut, author, isbn, settlement_type,
                threshold, client_id, deleted_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                cut = excluded.cut,
                author = excluded.author,
                isbn = excluded.isbn,
                settlement_type = excluded.settlement_type,
                threshold = excluded.threshold,
                client_id = excluded.client_id,
                deleted_at = excluded.deleted_at
            """,
            (
                item_id,
                str(item.get("title") or "").strip(),
                float(item.get("cut") or 0),
                str(item.get("author") or "").strip(),
                str(item.get("isbn") or "").strip(),
                str(item.get("settlement type") or "instant").strip(),
                float(item.get("threshold") or 0),
                client_id,
                _item_deleted_at(connection, "products", item),
            ),
        )
        connection.execute(
            "DELETE FROM product_streamings WHERE product_id = ?",
            (item_id,),
        )
        assigned_platforms = item.get("streaming", [])
        if not isinstance(assigned_platforms, list):
            assigned_platforms = (
                [assigned_platforms] if assigned_platforms else []
            )
        for position, platform_name in enumerate(assigned_platforms):
            name = str(platform_name or "").strip()
            if name:
                connection.execute(
                    """
                    INSERT OR IGNORE INTO product_streamings (
                        product_id, platform_name, position
                    ) VALUES (?, ?, ?)
                    """,
                    (item_id, name, position),
                )


def save_database(db_name: str, data) -> None:
    # UPSERT zachowuje rekordy nieobecne w przekazanej liście, w tym kosz.
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        with connection:
            if table == "clients":
                _save_clients(connection, data)
                return
            if table == "products":
                _save_products(connection, data)
                return

            to_insert_no_id = []
            to_insert_with_id = []
            for item in data:
                item_id = item.get("id")
                payload = json.dumps(
                    {
                        key: value
                        for key, value in item.items()
                        if key != "id"
                    },
                    ensure_ascii=False,
                )
                if item_id is None:
                    to_insert_no_id.append((payload,))
                else:
                    to_insert_with_id.append((int(item_id), payload))

            if to_insert_no_id:
                connection.executemany(
                    f'INSERT INTO "{table}" (data) VALUES (?)',
                    to_insert_no_id
                )
            if to_insert_with_id:
                connection.executemany(
                    f'INSERT INTO "{table}" (id, data) VALUES (?, ?) '
                    "ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                    to_insert_with_id
                )

            _sync_json_from_sqlite(table, connection)
    finally:
        connection.close()


def item_add(item_data, db_name: str) -> int:
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        max_id = connection.execute(
            f'SELECT MAX(id) FROM "{table}"'
        ).fetchone()[0]
        new_id = 1 if max_id is None else int(max_id) + 1
    finally:
        connection.close()

    item = dict(item_data)
    item["id"] = new_id
    save_database(table, [item])
    return new_id


def item_remove(item_id: int, db_name: str) -> None:
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    deleted_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with connection:
            if table in RELATIONAL_DATABASES:
                connection.execute(
                    f'UPDATE "{table}" SET deleted_at = ? WHERE id = ?',
                    (deleted_at, item_id),
                )
                return

            row = connection.execute(
                f'SELECT data FROM "{table}" WHERE id = ?',
                (item_id,),
            ).fetchone()
            if not row:
                return
            item = json.loads(row["data"])
            item["_deleted"] = True
            item["_deleted_at"] = deleted_at
            connection.execute(
                f'UPDATE "{table}" SET data = ? WHERE id = ?',
                (json.dumps(item, ensure_ascii=False), item_id),
            )
            _sync_json_from_sqlite(table, connection)
    finally:
        connection.close()


def item_restore(item_id: int, db_name: str) -> None:
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        with connection:
            if table in RELATIONAL_DATABASES:
                connection.execute(
                    f'UPDATE "{table}" SET deleted_at = NULL WHERE id = ?',
                    (item_id,),
                )
                return

            row = connection.execute(
                f'SELECT data FROM "{table}" WHERE id = ?',
                (item_id,),
            ).fetchone()
            if not row:
                return
            item = json.loads(row["data"])
            item.pop("_deleted", None)
            item.pop("_deleted_at", None)
            connection.execute(
                f'UPDATE "{table}" SET data = ? WHERE id = ?',
                (json.dumps(item, ensure_ascii=False), item_id),
            )
            _sync_json_from_sqlite(table, connection)
    finally:
        connection.close()


def item_purge(item_id: int, db_name: str) -> None:
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        with connection:
            connection.execute(
                f'DELETE FROM "{table}" WHERE id = ?',
                (item_id,),
            )
            _sync_json_from_sqlite(table, connection)
    finally:
        connection.close()


def list_trash(db_name: str) -> List[Any]:
    table = _validate_name(db_name)
    return sorted(
        (
            item
            for item in load_database(table, include_deleted=True)
            if item.get("_deleted")
        ),
        key=lambda item: item.get("_deleted_at") or "",
        reverse=True,
    )


def item_modify(
        item_id: int,
        field: str,
        new_value,
        db_name: str,
) -> None:
    table = _validate_name(db_name)
    item = item_get(item_id, table)
    if item is None:
        return
    item[field] = new_value
    save_database(table, [item])


def item_get(item_id: int, db_name: str):
    table = _validate_name(db_name)
    connection = _prepare_table(table)
    try:
        if table == "clients":
            row = connection.execute(
                "SELECT id, name, email, deleted_at FROM clients WHERE id = ?", (item_id,)
            ).fetchone()
            if not row: return None
            product_ids = [
                int(p["id"]) for p in connection.execute(
                    "SELECT id FROM products WHERE client_id = ? ORDER BY id", (item_id,)
                ).fetchall()
            ]
            item = {
                "id": int(row["id"]),
                "name": str(row["name"] or ""),
                "email": str(row["email"] or ""),
                "products": product_ids,
            }
            if row["deleted_at"]:
                item["_deleted"] = True
                item["_deleted_at"] = str(row["deleted_at"])
            return item

        elif table == "products":
            row = connection.execute(
                """
                SELECT p.id, p.title, p.cut, p.author, p.isbn,
                       p.settlement_type, p.threshold, p.deleted_at,
                       COALESCE(c.name, '') AS publisher
                FROM products AS p
                LEFT JOIN clients AS c ON c.id = p.client_id
                WHERE p.id = ?
                """, (item_id,)
            ).fetchone()
            if not row: return None
            platforms = [
                str(p["platform_name"]) for p in connection.execute(
                    "SELECT platform_name FROM product_streamings WHERE product_id = ? ORDER BY position, platform_name COLLATE NOCASE",
                    (item_id,)
                ).fetchall()
            ]
            item = {
                "id": int(row["id"]),
                "title": str(row["title"] or ""),
                "cut": _number(row["cut"]),
                "author": str(row["author"] or ""),
                "publisher": str(row["publisher"] or ""),
                "isbn": str(row["isbn"] or ""),
                "settlement type": str(row["settlement_type"] or "instant"),
                "threshold": _number(row["threshold"]),
            }
            if platforms: item["streaming"] = platforms
            if row["deleted_at"]:
                item["_deleted"] = True
                item["_deleted_at"] = str(row["deleted_at"])
            return item

        else:
            row = connection.execute(f'SELECT data FROM "{table}" WHERE id = ?', (item_id,)).fetchone()
            if row:
                item = json.loads(row["data"])
                item["id"] = int(item_id)
                return item
            return None
    finally:
        connection.close()


def item_purge_all(db_name: str) -> int:
    """Usuwa trwale wszystkie elementy znajdujące się w koszu danej tabeli.

    Zwraca liczbę trwale usuniętych elementów. Elementy, które nie są
    oznaczone jako usunięte, pozostają bez zmian.
    """
    table = _validate_name(db_name)
    connection = _prepare_table(table)

    try:
        with connection:
            if table in RELATIONAL_DATABASES:
                cursor = connection.execute(
                    f'DELETE FROM "{table}" WHERE deleted_at IS NOT NULL'
                )
                return int(cursor.rowcount)

            rows = connection.execute(
                f'SELECT id, data FROM "{table}"'
            ).fetchall()

            trash_ids = []

            for row in rows:
                try:
                    item = json.loads(row["data"])
                except (TypeError, json.JSONDecodeError):
                    continue

                if item.get("_deleted"):
                    trash_ids.append(int(row["id"]))

            if not trash_ids:
                return 0

            placeholders = ", ".join("?" for _ in trash_ids)

            connection.execute(
                f'DELETE FROM "{table}" WHERE id IN ({placeholders})',
                trash_ids,
            )

            _sync_json_from_sqlite(table, connection)

            return len(trash_ids)

    finally:
        connection.close()
