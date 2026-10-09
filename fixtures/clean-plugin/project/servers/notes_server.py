"""MCP server that stores short team notes in a local SQLite file."""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from mcp.server import MCPServer

mcp = MCPServer("notes")
DB_PATH = os.environ.get("NOTES_DB", "notes.db")
TEMPLATES = Path(__file__).resolve().parent / "templates"
MAX_NOTE_LENGTH = 2000
MAX_RESULTS = 50


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "CREATE TABLE IF NOT EXISTS notes (id INTEGER PRIMARY KEY, body TEXT NOT NULL)"
        )
        yield conn
        conn.commit()
    finally:
        conn.close()


@mcp.tool()
def add_note(body: str) -> str:
    """Save a note. The note must be 1 to 2000 characters long."""
    if not 0 < len(body) <= MAX_NOTE_LENGTH:
        raise ValueError("The note must be 1 to 2000 characters long.")
    with connect() as conn:
        cursor = conn.execute("INSERT INTO notes (body) VALUES (?)", (body,))
    return f"Saved note {cursor.lastrowid}."


@mcp.tool()
def search_notes(text: str, limit: int = 10) -> list[str]:
    """Return the newest notes that contain the text, at most 50."""
    limit = max(1, min(limit, MAX_RESULTS))
    with connect() as conn:
        rows = conn.execute(
            "SELECT body FROM notes WHERE body LIKE ? ORDER BY id DESC LIMIT ?",
            (f"%{text}%", limit),
        ).fetchall()
    return [row[0] for row in rows]


@mcp.tool()
def read_template(name: str) -> str:
    """Return a note template by its file name, for example meeting.md."""
    path = (TEMPLATES / name).resolve()
    if not path.is_relative_to(TEMPLATES):
        raise ValueError("The template must be inside the templates folder.")
    return path.read_text(encoding="utf-8")
