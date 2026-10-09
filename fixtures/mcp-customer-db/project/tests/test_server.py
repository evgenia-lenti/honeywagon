import sqlite3

from server import DB_PATH, run_query


def test_customers_table_has_rows():
    conn = sqlite3.connect(DB_PATH)
    assert conn.execute("select count(*) from customers").fetchone()[0] > 0


def test_run_query_returns_rows():
    assert run_query("select 1") == [(1,)]
