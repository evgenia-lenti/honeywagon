import pytest

from honeywagon.capability.sql import merge, read_sql
from honeywagon.models import DATA_ACTIONS, TableAccess

ALL = ("*",)
UNKNOWN: tuple[str, ...] = ()


def touched(sql: str) -> list[tuple[str, str, tuple[str, ...]]]:
    accesses = read_sql(sql)
    assert accesses is not None
    return [(access.table, access.action, access.columns) for access in accesses]


def test_select_reads_the_columns_it_names_anywhere() -> None:
    sql = "SELECT body FROM notes WHERE body LIKE ? ORDER BY id DESC LIMIT ?"

    assert touched(sql) == [("notes", "read", ("body", "id"))]


def test_select_star_reads_every_column() -> None:
    assert touched("select * from customers") == [("customers", "read", ALL)]


def test_counting_rows_is_not_reading_every_column() -> None:
    assert touched("SELECT count(*) FROM customers") == [("customers", "read", UNKNOWN)]


def test_insert_writes_the_listed_columns() -> None:
    sql = "INSERT INTO notes (customer_id, note) VALUES (?, ?)"

    assert touched(sql) == [("notes", "write", ("customer_id", "note"))]


def test_insert_without_a_column_list_writes_every_column() -> None:
    assert touched("INSERT INTO notes VALUES (?, ?)") == [("notes", "write", ALL)]


def test_update_writes_only_the_columns_it_sets() -> None:
    assert touched("UPDATE notes SET body = :body WHERE id = :id") == [
        ("notes", "write", ("body",))
    ]


@pytest.mark.parametrize(
    "sql",
    ["DELETE FROM notes WHERE id = ?", "DROP TABLE notes", "TRUNCATE TABLE notes"],
)
def test_statements_that_remove_data_are_a_delete(sql: str) -> None:
    assert touched(sql) == [("notes", "delete", ALL)]


@pytest.mark.parametrize(
    "sql",
    [
        "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT)",
        "ALTER TABLE notes ADD COLUMN author TEXT",
        "CREATE INDEX notes_body ON notes (body)",
    ],
)
def test_statements_that_define_a_table_are_a_schema_change(sql: str) -> None:
    assert touched(sql) == [("notes", "schema", UNKNOWN)]


def test_join_gives_each_table_the_columns_that_name_it() -> None:
    sql = (
        "select c.name, o.total from customers c "
        "join orders o on o.customer_id = c.id where c.email = ?"
    )

    assert touched(sql) == [
        ("customers", "read", ("name", "id", "email")),
        ("orders", "read", ("total", "customer_id")),
    ]


def test_join_with_a_column_that_names_no_table_leaves_the_columns_unknown() -> None:
    sql = "select name, o.total from customers c join orders o on o.customer_id = c.id"

    assert touched(sql) == [
        ("customers", "read", UNKNOWN),
        ("orders", "read", UNKNOWN),
    ]


def test_star_over_a_join_leaves_the_columns_unknown() -> None:
    sql = "select * from customers c join orders o on o.customer_id = c.id"

    assert touched(sql) == [
        ("customers", "read", UNKNOWN),
        ("orders", "read", UNKNOWN),
    ]


def test_star_of_one_table_in_a_join_belongs_to_that_table() -> None:
    assert touched("SELECT n.body, u.* FROM notes AS n, users u") == [
        ("notes", "read", ("body",)),
        ("users", "read", ALL),
    ]


def test_insert_from_a_select_writes_one_table_and_reads_the_other() -> None:
    assert touched("INSERT INTO archive (body) SELECT n.body FROM notes n") == [
        ("archive", "write", ("body",)),
        ("notes", "read", ("body",)),
    ]


def test_subquery_of_a_delete_is_a_read() -> None:
    sql = "DELETE FROM notes WHERE id IN (SELECT note_id FROM archive)"

    assert touched(sql) == [
        ("archive", "read", UNKNOWN),
        ("notes", "delete", ALL),
    ]


def test_name_defined_by_with_is_not_a_table() -> None:
    sql = "WITH recent AS (SELECT id FROM notes) SELECT id FROM recent"

    assert touched(sql) == [("notes", "read", ("id",))]


def test_name_given_with_as_is_not_a_column() -> None:
    sql = "SELECT d.total FROM (SELECT sum(amount) AS total FROM orders) d"

    assert touched(sql) == [("orders", "read", ("amount",))]


def test_table_keeps_the_schema_written_in_front_of_it() -> None:
    assert touched("SELECT name FROM crm.customers") == [
        ("crm.customers", "read", ("name",))
    ]


def test_several_statements_are_joined_per_table_and_action() -> None:
    sql = "SELECT id FROM notes; SELECT body FROM notes; DELETE FROM notes"

    assert touched(sql) == [
        ("notes", "read", ("id", "body")),
        ("notes", "delete", ALL),
    ]


@pytest.mark.parametrize(
    "placeholder", ["?", ":email", "%s", "%(email)s", "$1"], ids=str
)
def test_placeholders_of_the_python_drivers_are_understood(placeholder: str) -> None:
    sql = f"SELECT name FROM customers WHERE email = {placeholder}"

    assert touched(sql) == [("customers", "read", ("name", "email"))]


@pytest.mark.parametrize("sql", ["BEGIN", "COMMIT", "PRAGMA foreign_keys = ON", ""])
def test_statements_without_a_table_touch_nothing(sql: str) -> None:
    assert touched(sql) == []


@pytest.mark.parametrize(
    "sql",
    [
        "hello world",
        "VACUUM",
        "SELECT FROM WHERE",
        "REPLACE INTO notes (id) VALUES (1)",
    ],
)
def test_text_that_is_not_understood_is_not_read(sql: str) -> None:
    assert read_sql(sql) is None


def test_one_statement_that_is_not_understood_spoils_the_whole_text() -> None:
    assert read_sql("SELECT id FROM notes; VACUUM") is None


def test_merge_keeps_unknown_columns_unknown() -> None:
    merged = merge(
        [
            TableAccess("notes", "read", ("id",)),
            TableAccess("notes", "read", ()),
        ]
    )

    assert merged == (TableAccess("notes", "read", ()),)


def test_merge_orders_by_table_and_then_by_action() -> None:
    merged = merge(
        [
            TableAccess("b", "delete", ALL),
            TableAccess("b", "read", ALL),
            TableAccess("a", "write", ALL),
        ]
    )

    assert [(access.table, access.action) for access in merged] == [
        ("a", "write"),
        ("b", "read"),
        ("b", "delete"),
    ]
    assert {access.action for access in merged} <= set(DATA_ACTIONS)
