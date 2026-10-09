# Developer guide

For whoever works on Honeywagon's code. It describes only what is built today. The
full design, including what is not built yet, is in [tdd.md](tdd.md). The rules and
the current step are in [CLAUDE.md](../CLAUDE.md).

## Setup

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

Run all of these before a review:

```powershell
.venv\Scripts\python -m pytest
.venv\Scripts\python -m ruff check .
.venv\Scripts\python -m ruff format --check .
.venv\Scripts\python -m mypy
.venv\Scripts\python evaluate.py --layer deterministic
```

`ruff format .` without `--check` rewrites the files in the project's style.

The package has two runtime dependencies: `pyyaml`, for the frontmatter of Markdown
files, and `sqlglot`, to read SQL. `sqlglot` is held to one major version in
`pyproject.toml`, because it has renamed classes between major versions.

## Layout

```
src/honeywagon/
  cli.py              the `audit` command: arguments, output, exit code
  pipeline.py         one audit from start to end
  models.py           Finding, RunResult, Verdict, NotChecked, and the finding id
  files.py            reads the project's text files, lists what it did not read
  detect.py           decides the kinds of project
  frontmatter.py      reads the YAML block at the top of a Markdown file
  triage.py           the risk map: which parts to look at first
  classify.py         confidence and proposed verdict
  datafiles.py        loads the files in data/
  capability/
    __init__.py       Analysis (what the checks read) and the capability map
    config_files.py   allowed tools, MCP servers and hooks from configuration files
    python_code.py    tools, what they touch, and agent options, from Python code
    sql.py            tables, actions and columns of one SQL text (uses sqlglot)
    data_scope.py     the data a tool reaches, from the SQL it runs
  checks/
    registry.py       joins each check's definition with its function
    secrets.py        secret-in-file, also for a key in a header of an MCP server
    permissions.py    perm-broad-bash
    agents.py         perm-bypass-permissions, perm-bypass-in-settings,
                      agent-no-turn-limit
    hooks.py          hook-remote-code
    tools.py          inject-shell, inject-sql, inject-path,
                      inject-deserialization, tool-free-form-sql,
                      mcp-fetch-any-url
    network.py        net-tls-off
    mcp_servers.py    mcp-unpinned-server, mcp-plain-http
    dependencies.py   dep-security
    references.py     ref-missing-file
    portability.py    port-absolute-path
    project_tests.py  test-real-database
  deps/
    manifests.py      the dependencies a project declares, with file and line
    osv.py            the lookup of known vulnerabilities, the only network use
  guard/
    redact.py         finds secrets and removes them from every output
  report/
    text_report.py    the report for a person
    json_report.py    the whole result as JSON
  data/
    checks.toml           severity, fix effort, kinds and options of each check
    secret_patterns.toml  the shapes of keys and tokens
    builtin_tools.toml    what each built-in Claude Code tool touches
    python_calls.toml     the Python calls the code reader recognises
    dependencies.toml     the launchers that download a package, and their registry
    risk.toml             the tier of each reason in the risk map
    text/en.toml          every text the creator reads
tests/                unit tests, and the evaluation on the fixtures
fixtures/             fake projects with planted mistakes, see fixtures/README.md
evaluate.py           compares the tool's findings with the planted mistakes
```

## How one audit runs

`pipeline.run_audit(folder, lookup=None)` does these steps in order and returns a
`RunResult`:

1. **Read.** `files.load_project` walks the folder and reads the text files into
   memory. Whatever it does not read becomes a `NotChecked` entry with a reason.
   The checks never touch the disk. They work on what was read.
2. **Detect.** `detect.detect` returns the kinds found: `plugin`, `skill`,
   `mcp_server`, `agent`. With no kind, no check runs and the verdict is
   `nothing_to_audit`.
3. **Analyse.** `capability.analyse` reads the configuration files and parses the
   Python code once, into an `Analysis`. `capability.capability_map` turns it into
   the `CapabilityMap` of the result. A file that cannot be parsed becomes a
   `NotChecked` entry here, so the checks do not deal with broken files.
   `triage.risk_map` then builds the `RiskMap` from the capability map alone.
4. **Check.** Every check whose `kinds` include a detected kind runs on the
   `Analysis` and yields `Hit` objects: file, line, the line's text and, rarely, a
   suggested change.
5. **Build findings.** For each hit the pipeline takes the severity and fix effort
   from `checks.toml` and the title and consequence from `text/en.toml`. It passes
   the evidence and the suggestion through `guard.redact.safe_evidence` and computes
   the id.
6. **Classify.** `classify.confidence_of` sets the confidence and
   `classify.propose_verdict` applies the fixed rules.
7. **Report what was not covered.** The pipeline always adds the entries in
   `NOT_COVERED`: the layers and checks that do not exist yet. It also names the tools
   whose SQL could not be read.

`cli.main` then prints `report.render_text` or `report.render_json` and returns the
exit code.

## The analysis and the capability map

There are two views of the same facts, and the difference matters:

- **`Analysis`** is internal. It holds raw text from the audited project: hook
  commands, MCP server arguments, parsed Python. The checks read it. It never goes
  into an output.
- **`CapabilityMap`** is the public summary in the result and in the report. Every
  command in it has passed through `safe_evidence`, and for environment variables it
  keeps only the names.

What the `Analysis` offers a check:

| Attribute | What it holds |
| --- | --- |
| `project` | The files that were read: `files`, `named(...)`, `with_suffix(...)`, `exists(path)` |
| `allowed_tools` | Each entry of `allowed-tools` in a `SKILL.md`, with its line |
| `mcp_servers` | Each server of a `.mcp.json`: name, command and arguments or address, names of environment variables, and the headers of a remote server with their values |
| `hooks` | Each command hook: event, command, line |
| `permission_modes` | The `permissions.defaultMode` of each settings file that sets one |
| `python` | Each parsed Python file. `module.calls("sqlite3.connect")` yields the calls to one function, with import aliases resolved. `module.tls_off` holds the lines where TLS verification is switched off |
| `tools` | Each tool defined in Python, with its `effects` |
| `agent_options` | Each `ClaudeAgentOptions(...)` call, with its keywords and their lines |

An `Effect` is one call inside a tool that reaches outside the program. It has a
`touch` (`shell`, `database`, `network`, `filesystem_read`, `filesystem_write`), a
`line`, and `input`: how much of the command, SQL statement or address comes from the
tool's input.

| `input` | Meaning | Example |
| --- | --- | --- |
| `none` | The input does not reach it | `conn.execute("SELECT 1")` |
| `part` | The input is a piece of it | `urlopen(f"https://api.example.com/{item}")` |
| `whole` | The input is all of it | `conn.execute(sql)` where `sql` is the tool's argument |

The code reader follows an input through local names (`query = sql`, `query += ...`),
and through the single dict that an Agent SDK tool receives (`args["sql"]`). It does
not follow it into another function. A value inside `int(...)` or `float(...)` does
not count as input. The calls it recognises are listed in `data/python_calls.toml`.

A database effect has two more facts:

- `statement` is the SQL when it is written as constant text, directly or through a
  name that is assigned once (`QUERY = "..."` at the top of the file, or in the tool).
- `built_text` says that the SQL is put together in code: an f-string, `+`, `%` or
  `.format`. `effect.input_in_text` is true when input of the tool is pasted into a
  shell command or into such a statement. `inject-sql` and `inject-shell` read it.

A tool also has:

- `databases`: the target of each `sqlite3.connect(...)` call inside it, as a name
  written in the code or as the environment variable it is read from.
- `unsafe_loads`: each call that rebuilds objects from bytes or text, such as
  `pickle.loads`, with how much of what it loads comes from the tool's input.
- `path_checked`: whether the tool makes one of the calls that keep a path inside its
  folder. `inject-path` stays silent for such a tool.

**A secret that has no known shape.** `safe_evidence` hides keys by the shapes in
`secret_patterns.toml`. A key that is known by where it stands, such as the value of
an `Authorization` header, would pass through it. A check that reports such a key
hides it itself with `guard.redact.mask(line, secret)` before it yields the hit.
`guard.redact.address(url)` does the same for an address: it drops the user name and
password in front of the host and whatever follows a question mark.

## The data scope

`capability/data_scope.py` turns the database effects of one tool into the
`DataScope` of its entry in the map:

1. A statement that is the tool's input, or has input pasted into it, makes the
   status `any`.
2. Every other statement with a `statement` text goes to `sql.read_sql`, which returns
   one `TableAccess` per table and action, or `None` when the text is not understood.
3. The status is `known` when every statement was read, `partial` when some were,
   `unknown` when none was, and `none` when the tool has no database call at all.

`capability/sql.py` is the only module that imports `sqlglot`. It parses the text and
never runs it. Its rules are deliberately narrow, so that what it reports is certain:

- The dialect is not known, so it tries the default one, then SQLite, MySQL and
  PostgreSQL. The placeholders of the Python drivers (`%s`, `%(name)s`, `$1`) are
  replaced by `?` first.
- A statement it does not recognise makes the whole text unread. It does not guess.
- With one table in a statement, every column belongs to that table. With several, a
  column is counted only when it names its table or its alias, and a single column
  that does not makes the columns of every table unknown.
- A name defined by `WITH` is not a table. A name given with `AS` is not a column.

Table, column and database names pass through `safe_evidence` before they enter the
map, like every other text taken from the audited project.

## The risk map

`triage.risk_map(capability_map)` returns one `RiskGroup` per file that gives
capabilities. It reads only the capability map, so it runs before the checks and knows
nothing about findings. It produces no finding and it does not change the verdict.

Each fact in the map becomes a reason on the file it is declared in: a tool with
free-form input, a hook, a server that is started, and so on. `data/risk.toml` gives
each reason a tier. A group gets the highest tier among its reasons, and its `kind` is
the first of `triage.KINDS` that applies to the file.

To add a reason: add its key and tier to `risk.toml`, its text to `[risk_reasons]` in
`text/en.toml`, and the condition to `triage.py`. A test checks that the two files
have the same keys.

## Rules the code must keep

These come from `CLAUDE.md`. The tests cover all of them except the first, which
holds because no code in the package writes a file.

- **The audited project is only read.** No function writes under the audited folder.
- **Every finding has evidence:** a file, a line and the text of that line.
- **No secret in any output.** Evidence always goes through `safe_evidence`. The
  finding id is computed from the redacted evidence.
- **Severity, confidence and verdict come from code and data,** never from a model.
- **What was not checked is reported.** A file that cannot be parsed becomes a
  `NotChecked` entry in the analysis. It is not skipped silently.
- **The same input gives the same result.** Files are read in sorted order and
  findings are sorted. There is no timestamp in the result.
- **No text for the creator inside Python.** It goes into `data/text/en.toml`.
- **Nothing leaves the machine unless the person asks.** The lookup of dependencies
  runs only when a lookup is passed to `run_audit`, and it sends package names and
  versions only.
- **The core does not import or assume Claude Code.** It knows the file formats of
  the artifacts it audits, and nothing about where it runs.

## How to add a check

Follow these steps in order. The example adds a check with the id `example-check`.

1. **Plant the mistake in a fixture.** Add the mistake to a file under
   `fixtures/<name>/project/` and add an entry to that fixture's `expected.json` with
   `"layer": "deterministic"`. If the fixtures already have this mistake, skip this.
   The clean fixture should hold a correct version of the same thing.

2. **Define the check** in `src/honeywagon/data/checks.toml`:

   ```toml
   [example-check]
   severity = "error"
   fix_effort = "simple"
   kinds = ["plugin", "skill"]
   # Any other key is an option that the function receives.
   ```

3. **Write its texts** in `src/honeywagon/data/text/en.toml`, in plain language for a
   reader who is not a programmer:

   ```toml
   [checks.example-check]
   title = "What is wrong, in a few words"
   consequence = "What can happen because of it, and to whom."
   ```

4. **Write the function** in a module under `src/honeywagon/checks/`:

   ```python
   from collections.abc import Iterator, Mapping
   from typing import Any

   from honeywagon.capability import Analysis
   from honeywagon.checks.registry import Hit, register


   @register("example-check")
   def example_check(analysis: Analysis, options: Mapping[str, Any]) -> Iterator[Hit]:
       for file in analysis.project.named("SKILL.md"):
           for number, line in enumerate(file.lines, start=1):
               if "something wrong" in line:
                   yield Hit(file.path, number, line)
   ```

   The function only finds the place. It does not set the severity, the texts or the
   confidence, and it does not redact. If the check needs a fact that the analysis
   does not have yet, add it to `capability/` and not to the check, so that the
   capability map and the other checks can use it too.

   `Hit` takes an optional fourth value, the suggested change. Set it only when the
   code knows the exact line as it should become.

   Two more optional values exist for a check whose result depends on what it found.
   `severity` replaces the severity of the definition for that one hit. `values` fills
   the places marked `{name}` in the consequence text of the check. `dep-security`
   uses both: the severity follows the rating of the vulnerability, and the text
   lists the ids that were found.

5. **Register the module.** If it is a new module, import it in
   `src/honeywagon/checks/__init__.py`. A definition in `checks.toml` with no
   registered function fails when the checks are loaded.

6. **Write the tests** in `tests/test_checks.py` or `tests/test_checks_more.py`: one
   where the mistake is found with the right file and line, and at least one correct
   variant that must not be flagged.

7. **Run the evaluation.** `evaluate.py --layer deterministic` must show the planted
   mistake as found and no false finding. `tests/test_fixture_evaluation.py` checks
   the same on every test run, and also that every check has a fixture.

8. **Update the documentation:** the table of checks in `docs/user-guide.md`, and the
   limits listed there if they changed. Add to `docs/known-gaps.md` whatever the new
   check does not see, and delete the rows it closes.

## Tuning a check without code

Severity, fix effort, the kinds a check applies to, and its options are in
`checks.toml`. The patterns for keys are in `secret_patterns.toml`. The Python calls
that count as shell, network or database are in `python_calls.toml`. The tier of each
reason in the risk map is in `risk.toml`. The wording is in `text/en.toml`. Changing
these needs no Python, but run the tests and the evaluation afterwards: a looser
pattern can produce false findings on the clean fixture.

## Dependencies and the lookup

`deps/manifests.py` reads the dependencies into `analysis.dependencies`: registry,
name, exact version or `None`, file and line. `deps/osv.py` holds the lookup.

The lookup is a **parameter**, not something the core does by itself:

```python
Lookup = Callable[[str, str, str], tuple[Advisory, ...] | None]

run_audit(folder)                      # nothing is sent anywhere
run_audit(folder, osv_lookup)          # asks api.osv.dev
run_audit(folder, recorded_lookup())   # answers from fixtures/advisories.json
```

A lookup takes registry, name and version and returns the advisories of that version,
an empty tuple when there are none, or `None` when it failed. `analyse` calls it once
per package with an exact version and keeps the answers in `analysis.advisories`. The
check `dep-security` only reads those answers.

- `cli.main` passes `osv_lookup` only when the command has `--lookup`.
- `osv_lookup` is the only code in the package that opens a network connection. It
  talks to one address, written in the module, with a time limit, and it returns
  `None` on any failure. It does not raise.
- The database lists one vulnerability under several ids (`GHSA-...`, `PYSEC-...`).
  `advisories_from` joins them through their aliases.
- The pipeline records what was sent in `RunResult.looked_up`, and what was not looked
  up in `not_checked`, with the reason.

**Tests never use the network.** `tests/conftest.py` replaces `urlopen` for every
test with a function that fails. A test that needs an answer passes its own lookup,
or replaces `urlopen` with a fake that plays back a recorded response.

## The evaluation

`evaluate.py` runs the core on every fixture and compares the findings with each
fixture's `expected.json`. A finding matches a planted mistake when the check id and
the file are the same and the line is within three lines.

- **found:** a planted mistake that was reported.
- **missed:** a planted mistake that was not reported.
- **false:** a finding that matches no planted mistake. On `clean-plugin` every
  finding is false.

The numbers are shown per check, per kind of project and per fixture, never as one
total. `--layer deterministic` counts only the mistakes that code is expected to find.

The evaluation gives the core the recorded answers of the OSV database in
`fixtures/advisories.json`, so it needs no network and gives the same numbers on every
run. `--online` asks the database itself, to see whether something new was published.
`--record` asks it and rewrites the file. A test checks that every dependency of the
fixtures has a recorded answer.

## Adding a language

Copy `data/text/en.toml` to `data/text/<language>.toml` and translate the values. The
keys stay the same. `render_text` already takes a `language` argument. The command has
no option to choose it yet.
