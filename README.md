# Honeywagon

Honeywagon is an on-demand audit tool for agentic AI artifacts built with Claude:
skills, plugins, MCP servers and Python agents. It shows, in plain language, what an
artifact can do and what it risks.

It is written for people who build these artifacts with AI without being programmers,
and for the developers who advise them.

The tool is advisory. It never blocks, never approves, and never modifies the project
it audits. The creator of a project decides what goes to production.

## Status

Under construction: step 3 of 6, the deterministic core. The `audit` command lists
what a project can do (its tools, MCP servers, hooks and agents, and which tables each
tool reaches), points to the parts that deserve attention first, runs fifteen checks
written in code, and gives a report with a proposed verdict. Nothing that needs
judgment is checked yet, and the report says so under "not checked".

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

## Running an audit

```powershell
.venv\Scripts\audit <folder>
.venv\Scripts\audit <folder> --format json
```

The command only reads the folder, and it sends nothing anywhere. It exits with `1`
when it finds a critical problem, as a signal for scripts. It does not block anything.

To also look the project's dependencies up in the public [OSV](https://osv.dev)
database of known vulnerabilities, add `--lookup`. That sends the names and versions
of the dependencies, and nothing else:

```powershell
.venv\Scripts\audit <folder> --lookup
```

## Fixtures and evaluation

[fixtures/](fixtures/) holds small fake projects with planted mistakes, and one
without any. The code there is wrong on purpose and every key in it is fake.

`evaluate.py` compares the tool's findings with the planted mistakes, per check and
per kind of project:

```powershell
.venv\Scripts\python evaluate.py --layer deterministic
```

Today it finds all 17 planted mistakes that code can find, with no false finding. The
other 6 need judgment and wait for the checkers that use a model.

## Documentation

What works today:

- [user-guide.md](docs/user-guide.md): how to run an audit and read the report
- [developer-guide.md](docs/developer-guide.md): how the code is organised and how to
  add a check
- [known-gaps.md](docs/known-gaps.md): what the tool does not see yet

The design lives in [docs/](docs/):

- [plan.md](docs/plan.md): implementation plan
- [tdd.md](docs/tdd.md): technical design
- [prd.md](docs/prd.md): requirements and scope of the first version
- [design.md](docs/design.md): background, catalogue of common mistakes, decisions

## License

[MIT](LICENSE)
