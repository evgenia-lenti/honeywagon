# User guide

This guide describes what Honeywagon does today. The tool is still being built, so the
guide grows with it. Part 1 is for people who build skills, plugins, MCP servers and
agents with AI. Part 2 is for the developers who advise them.

## Part 1: for creators

### What Honeywagon is

Honeywagon reads a project you built with Claude and tells you, in plain language,
what it found that could hurt you or the people who use your project.

Three things are worth knowing before you use it:

- **It only reads.** It never changes your files and it never sends them anywhere.
- **It only advises.** It does not block anything and it does not approve anything.
  You decide what you do with the report, and you are responsible for what you put
  into use.
- **It does not see everything.** Every report ends with a list called "Not checked".
  A report with no findings means "nothing was found in what was checked". It does not
  mean that the project is safe.

### What it checks today

The tool looks for three mistakes so far. More are being added.

| What it finds | Why it matters | What you can do |
| --- | --- | --- |
| A key or token written in a file | Anyone who can read the file can use the key as if they were you | Ask the service to cancel that key and give you a new one. Keep the new key outside the project, in an environment variable. Deleting the line is not enough, because the old key stays in the project's history |
| A skill that allows any shell command | Whoever uses the skill lets Claude run any command on their computer without being asked | List only the commands the skill needs, for example `Bash(git log *)` in place of `Bash` |
| A hook that downloads a script and runs it | A hook runs by itself. Whoever controls that web address can run commands on every computer that uses your project | Remove the hook, or keep the script inside the project where it can be read |

### How to run it

Today the tool runs from a terminal, which is described in Part 2. If you do not use a
terminal, ask a developer to run it on your project and to go through the report with
you.

A command inside Claude Code, `/audit`, is planned. When it exists, you will run the
audit yourself from the conversation.

### How to read the report

A report looks like this:

```
Honeywagon audit
This report is advisory. It does not block or approve anything. The creator of the
project decides what goes to production.

Found in this project: skill
Layers that ran: deterministic
Checks that ran: secret-in-file, perm-broad-bash, hook-remote-code

Proposed verdict: Not recommended for use
Partial: only the deterministic layer ran, so the verdict covers only what code can check.
Because of: perm-broad-bash:6b6f70, secret-in-file:4ee8cb

Findings

  Critical
    The skill allows any shell command
      SKILL.md:4  [perm-broad-bash:6b6f70]  confidence: high  fix: simple
      > allowed-tools: Bash, Read, Grep
      Whoever uses the skill lets Claude run any command on their computer without
      being asked first.

Not checked
  - Dependencies: Known vulnerabilities of dependencies are not checked yet.
```

Read it from the top.

**Found in this project** says what the tool recognised: a skill, a plugin, an MCP
server or an agent. A project can be more than one of these.

**Proposed verdict** is the tool's suggestion. It is one of four:

| Verdict | What it means |
| --- | --- |
| Not recommended for use | At least one critical finding. Fix it before anyone uses the project |
| Fix before use | No critical finding, but at least one error |
| No reason found not to use | Nothing serious was found in what was checked |
| Nothing to audit | The folder has no skill, plugin, MCP server or agent, so nothing was checked |

**Partial** appears when only part of the tool ran. Today it always appears, because
the checks that need a model are not built yet.

**Because of** lists the findings that led to the verdict.

**Findings** are grouped by how serious they are:

| Severity | What it means |
| --- | --- |
| Critical | A leak, loss of data, or commands run by someone else. Must be fixed |
| Error | The project does not do what it says, or it will fail in practice |
| Warning | Unnecessary risk, or something hard to maintain |
| Suggestion | A better way to do it |
| Nitpick | Style and names. Optional |

Each finding has four lines:

1. A title in plain words.
2. Where it is: the file and the line number. After that, a short code in square
   brackets that names this finding, how sure the tool is (`confidence`), and whether
   the fix is `simple` (one change in one place) or `complex` (needs a developer).
3. After the `>` sign, the exact line from your file. This is the evidence. Keys are
   never shown in full: you see the first six characters and then `...REDACTED`.
4. What can happen because of it.

**Not checked** lists what the tool did not look at, and why. Read it every time.

### What to do with a finding

1. Open the file at the line the report gives.
2. If the fix is `simple`, make the change, or ask Claude to make it for you.
3. If the fix is `complex`, or you are not sure what the finding means, ask a
   developer before you change anything.
4. Run the audit again. A finding that is fixed disappears from the report.

If you believe a finding is wrong, tell a developer. A wrong finding is a mistake in
the tool, and reporting it helps fix it.

## Part 2: for developers who advise

### Install

Honeywagon needs Python 3.11 or newer. From the repository root:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
```

On macOS and Linux use `python3 -m venv .venv` and `.venv/bin/python`.

### Run

```powershell
.venv\Scripts\audit <folder>
.venv\Scripts\audit <folder> --format json
```

`<folder>` is the root of the project to audit. `python -m honeywagon <folder>` does
the same.

| Option | What it does |
| --- | --- |
| `--format text` | The report for a person. This is the default |
| `--format json` | The whole result, for a script |

| Exit code | Meaning |
| --- | --- |
| `0` | No critical finding |
| `1` | At least one critical finding. A signal for scripts, not a block |
| `2` | Usage error, for example a folder that does not exist |

### The JSON result

| Field | Content |
| --- | --- |
| `schema_version` | Version of this format. Now `1` |
| `tool_version` | Version of Honeywagon |
| `project_kinds` | Any of `plugin`, `skill`, `mcp_server`, `agent` |
| `layers_ran` | Now `deterministic`, or empty when there was nothing to audit |
| `checks_ran` | The ids of the checks that ran on this project |
| `findings` | The list of findings, most severe first |
| `verdict` | `key`, `text`, `partial`, and `triggered_by` with the ids of the findings that caused it |
| `not_checked` | A list of `what` and `reason` |

Each finding has `id`, `check_id`, `title`, `file`, `line`, `evidence`, `consequence`,
`severity`, `confidence`, `fix_effort`, `suggestion`, `origin` and `verification`.

- `id` is the check id and a short hash of the file path and the evidence. It has no
  line number, so it stays the same when lines above the finding are added or removed.
- `confidence` is `high` for everything the tool finds today, because every check is
  code with one right answer.
- `suggestion` and `verification` are empty today.

### How the tool recognises a project

| Kind | What it looks for |
| --- | --- |
| `plugin` | A `.claude-plugin/plugin.json` file |
| `skill` | A `SKILL.md` file, in a project with no plugin manifest |
| `mcp_server` | Python code that imports `mcp` or `fastmcp` |
| `agent` | Python code that imports `claude_agent_sdk` |

A plugin with no manifest is recognised as a skill if it has a `SKILL.md`, and is not
recognised at all if it has none.

### What the tool reads

It reads text files with these endings: `.md`, `.json`, `.py`, `.sh`, `.toml`, `.txt`,
`.yaml`, `.yml`, `.cfg`, `.ini`, `.env`. Every other file is listed under "Not
checked", and so is a file larger than 1 MB, a file that is not text, and a symbolic
link that points outside the project.

It skips these folders without listing them: `.git`, `node_modules`, `.venv`, `venv`,
`__pycache__` and the cache folders of pytest, mypy and ruff.

### Limits to keep in mind when you advise

- **Three checks only.** The report lists them under "Checks that ran". Injection,
  free-form tools, bypassed permissions, missing files and the rest are not checked
  yet, even though the project may have them.
- **Keys are recognised by their shape.** The tool knows the key formats of Anthropic,
  OpenAI, GitHub, Slack, AWS, Google and Stripe, and private key blocks. A password or
  a key of another service is not found.
- **Shell permissions are read only from `allowed-tools` in `SKILL.md`.** Permissions
  in `settings.json` and in agent definitions are not read yet.
- **Hooks are read from `hooks.json`, `settings.json` and `settings.local.json`.** A
  hook written inside a skill's frontmatter is not read yet.
- **Only Python code is recognised** as an MCP server or agent. A server written in
  JavaScript is not detected.
- **No model runs.** Nothing that needs judgment is checked, for example whether a
  skill does what its description says.

When a creator asks "is my project safe?", the honest answer from this report is:
"these three things were checked, and here is the list of what was not".
