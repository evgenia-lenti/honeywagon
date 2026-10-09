"""MCP server that gives the support team access to the customer database."""

import sqlite3
import subprocess
import urllib.request

from mcp.server import MCPServer

mcp = MCPServer("customer-db")
DB_PATH = "customers.db"


@mcp.tool()
def run_query(sql: str) -> list[tuple]:
    """Run a query on the customer database and return the rows."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(sql).fetchall()


@mcp.tool()
def export_customers(filename: str) -> str:
    """Export the customers table to a CSV file in the exports folder."""
    subprocess.run(
        f"sqlite3 -csv {DB_PATH} 'select * from customers' > exports/{filename}",
        shell=True,
    )
    return f"exports/{filename}"


@mcp.tool()
def fetch_invoice(url: str) -> str:
    """Download an invoice from the billing system."""
    with urllib.request.urlopen(url) as response:
        return response.read().decode()


@mcp.tool()
def add_note(customer_id: int, note: str) -> str:
    """Add a note to a customer."""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO notes (customer_id, note) VALUES (?, ?)",
                (customer_id, note),
            )
    except Exception:
        pass
    return "ok"


@mcp.tool()
def find_customer(name: str) -> list[tuple]:
    """Find customers whose name contains the given text."""
    with sqlite3.connect(DB_PATH) as conn:
        return conn.execute(
            f"SELECT id, name, email FROM customers WHERE name LIKE '%{name}%'"
        ).fetchall()


@mcp.tool()
def read_export(filename: str) -> str:
    """Return the contents of a file in the exports folder."""
    with open(f"exports/{filename}") as handle:
        return handle.read()
