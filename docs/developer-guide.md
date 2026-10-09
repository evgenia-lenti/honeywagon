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

## Layout

```
src/honeywagon/
  cli.py              the `audit` command: arguments, output, exit code
  pipeline.py         one audit from start to end
  models.py           Finding, RunResult, Verdict, NotChecked, and the finding id
  files.py            reads the project's text files, lists what it did not read
  detect.py           decides the kinds of project
  frontmatter.py      reads the YAML block at the top of a Markdown file
  classify.py         confidence and proposed verdict
  datafiles.py        loads the files in data/
  checks/
    registry.py       joins each check's definition with its function
    secrets.py        secret-in-file
    permissions.py    perm-broad-bash
    hooks.py          hook-remote-code
  guard/
    redact.py         finds secrets and removes them from every output
  report/
    text_report.py    the report for a person
    json_report.py    the whole result as JSON
  data/
    checks.toml           severity, fix effort, kinds and options of each check
    secret_patterns.toml  the shapes of keys and tokens
    text/en.toml          every text the creator reads
tests/                unit tests, and the evaluation on the fixtures
fixtures/             fake projects with planted mistakes, see fixtures/README.md
evaluate.py           compares the tool's findings with the planted mistakes
```

## How one audit runs

`pipeline.run_audit(folder)` does these steps in order and returns a `RunResult`:

1. **Read.** `files.load_project` walks the folder and reads the text files into
   memory. Whatever it does not read becomes a `NotChecked` entry with a reason.
   The checks never touch the disk. They work on what was read.
2. **Detect.** `detect.detect` returns the kinds found: `plugin`, `skill`,
   `mcp_server`, `agent`. With no kind, no check runs and the verdict is
   `nothing_to_audit`.
3. **Check.** Every check whose `kinds` include a detected kind runs. A check yields
   `Hit` objects (file, line, the line's text) and, when it cannot parse a file,
   `NotChecked` objects.
4. **Build findings.** For each hit the pipeline takes the severity and fix effort
   from `checks.toml` and the title and consequence from `text/en.toml`. It passes
   the evidence through `guard.redact.safe_evidence` and computes the id.
5. **Classify.** `classify.confidence_of` sets the confidence and
   `classify.propose_verdict` applies the fixed rules.
6. **Report what was not covered.** The pipeline always adds the entries in
   `NOT_COVERED`: the layers and checks that do not exist yet.

`cli.main` then prints `report.render_text` or `report.render_json` and returns the
exit code.

## Rules the code must keep

These come from `CLAUDE.md`. The tests cover all of them except the first, which
holds because no code in the package writes a file.

- **The audited project is only read.** No function writes under the audited folder.
- **Every finding has evidence:** a file, a line and the text of that line.
- **No secret in any output.** Evidence always goes through `safe_evidence`. The
  finding id is computed from the redacted evidence.
- **Severity, confidence and verdict come from code and data,** never from a model.
- **What was not checked is reported.** A check that cannot parse a file yields a
  `NotChecked`. It does not skip the file silently.
- **The same input gives the same result.** Files are read in sorted order and
  findings are sorted. There is no timestamp in the result.
- **No text for the creator inside Python.** It goes into `data/text/en.toml`.
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

   from honeywagon.checks.registry import Hit, register
   from honeywagon.files import Project


   @register("example-check")
   def example_check(project: Project, options: Mapping[str, Any]) -> Iterator[Hit]:
       for file in project.named("SKILL.md"):
           for number, line in enumerate(file.lines, start=1):
               if "something wrong" in line:
                   yield Hit(file.path, number, line)
   ```

   The function only finds the place. It does not set the severity, the texts or the
   confidence, and it does not redact.

5. **Register the module.** If it is a new module, import it in
   `src/honeywagon/checks/__init__.py`. A definition in `checks.toml` with no
   registered function fails when the checks are loaded.

6. **Write the tests** in `tests/test_checks.py`: one where the mistake is found with
   the right file and line, and at least one correct variant that must not be flagged.

7. **Run the evaluation.** `evaluate.py --layer deterministic` must show the planted
   mistake as found and no false finding. `tests/test_fixture_evaluation.py` checks
   the same on every test run, and also that every check has a fixture.

8. **Update the documentation:** the table of checks in `docs/user-guide.md`, and the
   limits listed there if they changed.

## Tuning a check without code

Severity, fix effort, the kinds a check applies to, and its options are in
`checks.toml`. The patterns for keys are in `secret_patterns.toml`. The wording is in
`text/en.toml`. Changing these needs no Python, but run the tests and the evaluation
afterwards: a looser pattern can produce false findings on the clean fixture.

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

## Adding a language

Copy `data/text/en.toml` to `data/text/<language>.toml` and translate the values. The
keys stay the same. `render_text` already takes a `language` argument. The command has
no option to choose it yet.
