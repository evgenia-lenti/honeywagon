import pytest

from servers import notes_server


@pytest.fixture(autouse=True)
def temporary_database(tmp_path, monkeypatch):
    monkeypatch.setattr(notes_server, "DB_PATH", str(tmp_path / "notes.db"))


def test_saved_note_is_found_by_search():
    notes_server.add_note("Deploy moved to Thursday")
    assert notes_server.search_notes("Thursday") == ["Deploy moved to Thursday"]


def test_search_returns_nothing_for_unknown_text():
    notes_server.add_note("Deploy moved to Thursday")
    assert notes_server.search_notes("Friday") == []


def test_empty_note_is_rejected():
    with pytest.raises(ValueError):
        notes_server.add_note("")


def test_search_limit_is_capped():
    for number in range(60):
        notes_server.add_note(f"note {number}")
    assert len(notes_server.search_notes("note", limit=500)) == 50


def test_template_is_read_by_name():
    assert notes_server.read_template("meeting.md").startswith("# Meeting")


def test_template_outside_the_folder_is_refused():
    with pytest.raises(ValueError):
        notes_server.read_template("../notes_server.py")
