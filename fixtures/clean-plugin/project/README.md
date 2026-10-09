# Team notes

A Claude Code plugin for the platform team.

- `/team-notes:changelog` drafts a changelog entry from the commits since the last tag.
- The `notes` MCP server saves and searches short team notes. The notes are stored in
  the plugin's data folder, on your own computer.
- A hook blocks shell commands that delete files recursively.

## Setup

Install the server's dependency once: `pip install -r requirements.txt`.

## Tests

Run `pytest` in this folder. The tests use a temporary database.
