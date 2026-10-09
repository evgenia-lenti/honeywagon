# Honeywagon

Honeywagon is an on-demand audit tool for agentic AI artifacts built with Claude:
skills, plugins, MCP servers and Python agents. It shows, in plain language, what an
artifact can do and what it risks.

It is written for people who build these artifacts with AI without being programmers,
and for the developers who advise them.

The tool is advisory. It never blocks, never approves, and never modifies the project
it audits. The creator of a project decides what goes to production.

## Status

Under construction: step 2 of 6 is done. The repository has the design documents, the
fixtures with planted mistakes and the script that measures the tool against them.
There is nothing to run against a project yet.

## Requirements

- Python 3.11 or newer

## Setup

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

macOS and Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
```

## Running the checks

Windows (PowerShell):

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy
```

On macOS and Linux, use `.venv/bin/python` in place of `.venv\Scripts\python`.

## Fixtures and evaluation

[fixtures/](fixtures/) holds small fake projects with planted mistakes, and one
without any. The code there is wrong on purpose and every key in it is fake.

`evaluate.py` compares the tool's findings with the planted mistakes, per check and
per kind of project:

```powershell
.venv\Scripts\python evaluate.py
```

The tool has no checks yet, so every planted mistake is reported as missed.

## Design

The design lives in [docs/](docs/):

- [plan.md](docs/plan.md): implementation plan
- [tdd.md](docs/tdd.md): technical design
- [prd.md](docs/prd.md): requirements and scope of the first version
- [design.md](docs/design.md): background, catalogue of common mistakes, decisions

## License

[MIT](LICENSE)
