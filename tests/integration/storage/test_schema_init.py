import sqlite3

from notedesk.storage.schema import REQUIRED_TABLES, initialize_database


def test_initialize_database_creates_required_tables(tmp_path) -> None:
    db_path = tmp_path / "notedesk.db"

    initialize_database(db_path)

    with sqlite3.connect(db_path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }

    assert REQUIRED_TABLES.issubset(table_names)
