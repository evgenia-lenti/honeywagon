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
  There is one thing it can ask the outside world, and only when you tell it to:
  whether the packages your project depends on have known security problems. For
  that it sends the names and versions of those packages, and nothing else.
- **It only advises.** It does not block anything and it does not approve anything.
  You decide what you do with the report, and you are responsible for what you put
  into use.
- **It does not see everything.** Every report ends with a list called "Not checked".
  A report with no findings means "nothing was found in what was checked". It does not
  mean that the project is safe.

### What it checks today

The tool does three things. It lists what your project can do, it points to the parts
that deserve attention first, and it looks for nineteen mistakes. More are being added.

Serious mistakes, which the report marks as critical:

| What it finds | Why it matters | What you can do |
| --- | --- | --- |
| A key or token written in a file, or in a header of an MCP server | Anyone who can read the file can use the key as if they were you | Ask the service to cancel that key and give you a new one. Keep the new key outside the project, in an environment variable. Deleting the line is not enough, because the old key stays in the project's history |
| A skill that allows any shell command | Whoever uses the skill lets Claude run any command on their computer without being asked | List only the commands the skill needs, for example `Bash(git log *)` in place of `Bash` |
| An agent that never asks before it acts | The agent runs every tool it has, including the ones that delete things, with no person approving | Use the normal permission mode. The report shows the exact change |
| A hook that downloads a script and runs it | A hook runs by itself. Whoever controls that web address can run commands on every computer that uses your project | Remove the hook, or keep the script inside the project where it can be read |
| Input of a tool that goes into a shell command | Whoever controls the input can add their own commands | Ask a developer. The command has to be built in a way that keeps the input apart |
| Input of a tool pasted into the text of a SQL statement | Whoever controls the input can change what the statement does: read other rows and tables, or change and delete data | Ask a developer. The values have to be passed apart from the statement, as parameters |
| Input of a tool that decides which file is opened | With `../` in the name, the tool can be pointed at any file the program can reach: keys, private files, or a file to overwrite | Ask a developer. The tool has to check that the file stays inside its own folder |
| Input of a tool that is loaded in a way that can run code | Formats such as `pickle` can carry instructions that run while the data is loaded | Ask a developer. Data from outside is read as JSON, never as `pickle` |
| A tool that runs any SQL it is given | The model can read, change or delete anything in the database | Ask a developer. The tool should offer specific questions with values, not free SQL |

Mistakes that make the project fail or misbehave, marked as error:

| What it finds | Why it matters | What you can do |
| --- | --- | --- |
| A tool that calls any address it is given | It can be pointed at internal systems that should not be reached | Ask a developer to limit the tool to the addresses it needs |
| A skill that points to a file that does not exist | The step fails, or Claude makes something up | Add the file, or remove the step |
| An MCP server that is reached without encryption | The address starts with `http` and not `https`, so whoever sits on the network in between can read and change everything, including a key | Use the `https` address of the server |
| The check of a server's identity is switched off | The code accepts a forged server, so what is sent can be read and changed on the way | Remove `verify=False`. If the server has its own certificate, ask a developer how to trust that one certificate |
| A test that opens the real database | Running the tests reads or changes real data | Ask a developer to make the tests use a temporary database |
| A dependency, or a downloaded MCP server, in a version with a known security problem | The problem is published, so anyone can look it up and try it against your project | Move to a version that fixes it. The report lists, for each problem, the versions that fix it. This is found only when the audit runs with the lookup switched on, and it is marked critical when the public database rates the problem as critical |

Unnecessary risks, marked as warning:

| What it finds | Why it matters | What you can do |
| --- | --- | --- |
| An MCP server downloaded without a fixed version | Each start may run a different version, with no warning | Add the version to the name, for example `name@1.2.3` |
| A path into one person's home folder | It works only on that person's computer | Use a path relative to the project |
| An agent with no limit on turns | A stuck agent keeps running and keeps costing | Set a limit |
| A settings file that asks for no permission prompts | New versions of Claude Code ignore this inside a project. Old versions obey it and run everything without asking | Remove it. The report shows the exact change |

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
Checks that ran: secret-in-file, perm-broad-bash, hook-remote-code, ...

Proposed verdict: Not recommended for use
Partial: only the deterministic layer ran, so the verdict covers only what code can check.
Because of: perm-broad-bash:6b6f70, secret-in-file:4ee8cb

What this project can do
  Claude may use these without asking
    Bash  (SKILL.md:4)  any use
    Read  (SKILL.md:4)  any use
    Grep  (SKILL.md:4)  any use

Where to look first
  A guide for attention, not a judgment. A part comes first because of what it can
  do, not because something is wrong with it.
  Look first
    SKILL.md  (skill)
      - lets Claude run any command without asking: Bash
      - lets Claude use tools without asking: Read, Grep

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

**What this project can do** is a list of facts, not of problems. Read it and ask
yourself whether you expected each line. It can have six parts:

| Part | What it lists |
| --- | --- |
| Claude may use these without asking | The tools your skill or agent allows in advance. "any use" means with no limit, "restricted" means only the listed commands |
| Tools in the code | Each tool that an MCP server or agent defines, what it touches (files, commands, network, database) and what kind of input it takes |
| MCP servers it starts or connects to | Each server, and the command that starts it or the address it is reached at |
| Hooks that run by themselves | Each hook, when it runs and what it runs |
| Agents | Each agent, whether it asks before acting, and whether it has a limit on turns |
| Permission mode set in settings | The mode that a settings file makes every session start in |

Each part appears only when the project has something of that kind.

A tool that "takes free-form input" does whatever text it is given: any command, any
SQL or any address. Such a tool is as powerful as the system behind it.

A tool that uses a database has one more line, which starts with `data:`. It says
which tables the tool reaches and what it does to them:

```
add_note  (server.py:38)  uses a database; takes values as input
    data: notes: writes customer_id, note  (database customers.db)
```

| What the line says | What it means |
| --- | --- |
| `notes: reads body, id` | The tool reads these columns of the table `notes` |
| `notes: writes all columns` | The tool adds or changes rows, and no column is left out |
| `notes: deletes rows` | The tool removes rows, or the whole table |
| `notes: creates or changes the table` | The tool changes the shape of the table |
| `reads, columns not known` | The table is certain, the columns are not |
| `decided by the input, not limited by the code` | The tool runs SQL that comes from its input, so it can reach whatever the database holds |
| `some SQL could not be read` | Part of the tool's SQL is put together while it runs. What is listed is true, and there may be more |
| `tables and columns could not be read` | None of the tool's SQL could be read |
| `database unknown` | The tool does not open the database itself, so the tool could not tell which one it is |

Ask yourself whether the tool needs every table and column on its line. A tool that
only shows notes has no reason to write to them.

**Where to look first** orders the parts of your project by how much each can do. It is
a guide for attention, not a judgment. A part is under "Look first" because of what it
can do, not because something is wrong with it. A correct project has parts under
"Look first" too: a hook always is, because it runs by itself.

| Group | When a part is listed there |
| --- | --- |
| Look first | A tool takes free-form input, runs commands, loads data in a way that can run code, or changes or deletes data. A hook. Any shell command is allowed. Something never asks before it acts |
| Look next | A tool uses the network or reads data. A file starts an MCP server. Tools are allowed without asking, with limits |
| Look last | A tool touches nothing outside the program |

Under each part are the reasons, with the names of the tools they come from. This
section never changes the verdict and it adds no finding.

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

Some findings have a fifth line, **Suggested change**. It is the line as it should
become. The tool writes it only when it is certain of the exact text.

**Not checked** lists what the tool did not look at, and why. Read it every time.

One line there is about your dependencies, the packages your project needs:

```
- requests 2.31.0, mcp 2.3.0: Not looked up. Run again with --lookup to ask the OSV
  database for known security problems. That sends these names and versions, and
  nothing else.
```

It names exactly what would be sent. If every name on it is a public package, the
lookup is safe to run. If one of them is a package that only your company has, its
name would become known to the database, so ask before you run it.

When the lookup did run, a line near the top of the report says what was sent:
`Sent to the OSV database: PyPI requests 2.31.0`.

Another line is about MCP servers that your project reaches over the network:

```
- team-wiki: Whether this server asks who is calling cannot be told from the
  configuration. A server that signs you in through the browser has no header here.
```

It is not a finding. The file that names the server does not show whether the server
checks who is calling, so ask whoever runs the server.

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
| `--lookup` | Also ask the OSV database about known security problems of the dependencies. Off unless you give it |

| Exit code | Meaning |
| --- | --- |
| `0` | No critical finding |
| `1` | At least one critical finding. A signal for scripts, not a block |
| `2` | Usage error, for example a folder that does not exist |

### Looking up dependencies

The tool reads which packages the project depends on from three places:

| Where | What it reads |
| --- | --- |
| `requirements.txt` and `requirements-*.txt` | Each line that names a package |
| `pyproject.toml` | `dependencies` and `optional-dependencies` of the `[project]` table |
| `.mcp.json` | A package that a server downloads at start, with `npx`, `bunx`, `pnpm`, `uvx` or `pipx` |

Only a dependency with one exact version can be looked up: `requests==2.31.0`,
`mcp-remote@0.1.15`. A dependency such as `requests>=2` or `some-server@latest` is
listed under "Not checked", by name.

Without `--lookup` nothing is sent, and the report lists the names and versions that a
lookup would send. With `--lookup` the tool asks [OSV](https://osv.dev), a public
database of known vulnerabilities, one question per package. Each question holds the
registry (PyPI or npm), the package name and the version. No code, no file name and
nothing else about the project is sent.

**Before you run `--lookup` on someone's project, read the list.** The name of a
package that exists only inside a company tells the database that such a package
exists. There is no way yet to leave one package out and look up the rest.

A package with a known problem becomes one finding, on the line that declares it. The
finding lists the id of each problem and, in brackets, the versions that fix it, as the
database gives them. A `-` in the brackets means that the database lists no fixed
version. The tool does not suggest a version to move to: look the ids up at
`osv.dev` and choose one that fixes all of them.

If the database does not answer, the audit still finishes, and the package is listed
under "Not checked".

### The JSON result

| Field | Content |
| --- | --- |
| `schema_version` | Version of this format. Now `2` |
| `tool_version` | Version of Honeywagon |
| `project_kinds` | Any of `plugin`, `skill`, `mcp_server`, `agent` |
| `layers_ran` | Now `deterministic`, or empty when there was nothing to audit |
| `checks_ran` | The ids of the checks that ran on this project |
| `looked_up` | The packages that were sent to the OSV database: registry, name and version. Empty without `--lookup` |
| `capability_map` | What the project can do: `capabilities`, `mcp_servers`, `hooks`, `agents`, `permission_modes` |
| `risk_map` | Where to look first: `groups`, each with `name` (the file), `kind`, `tier` and `reasons` |
| `findings` | The list of findings, most severe first |
| `verdict` | `key`, `text`, `partial`, and `triggered_by` with the ids of the findings that caused it |
| `not_checked` | A list of `what` and `reason` |

Each finding has `id`, `check_id`, `title`, `file`, `line`, `evidence`, `consequence`,
`severity`, `confidence`, `fix_effort`, `suggestion`, `origin` and `verification`.

- `id` is the check id and a short hash of the file path and the evidence. It has no
  line number, so it stays the same when lines above the finding are added or removed.
- `confidence` is `high` for everything the tool finds today, because every check is
  code with one right answer.
- `suggestion` is filled for two cases only: a key in a JSON file, where the value
  becomes a reference to an environment variable, and the bypass permission mode, in
  an agent or in a settings file.
- `verification` is empty today.

Each entry of `capabilities` has `name`, `kind` (`allowed_tool` or `tool`),
`declared_in` with file and line, `scope`, `touches`, `boundedness`, `data_scope`,
`requires_confirmation` and `unsafe_loading`, which is true for a tool that loads data
with a call such as `pickle.loads`.

- `touches` uses a closed list: `filesystem_read`, `filesystem_write`, `shell`,
  `network`, `database`, `secrets`, `external_content`.
- `boundedness` is `fixed` when the tool takes no input, `free_form` when its input
  becomes the whole command, SQL statement or address, or is pasted into a shell
  command or into the text of a SQL statement, and `parameterized` otherwise.
- `data_scope` has `status`, `database`, `database_variable` and `tables`. Each table
  entry has `table`, `action` (`read`, `write`, `delete` or `schema`) and `columns`.
  In `columns`, `*` means every column and an empty list means that the columns are
  not known, or that the action is on the table as a whole.

| `status` | Meaning |
| --- | --- |
| `none` | The tool uses no database |
| `known` | Every SQL statement of the tool was read |
| `partial` | Some statements were read. The others are put together in code |
| `any` | A statement, or a piece of one, comes from the tool's input, so the code sets no limit |
| `unknown` | The tool uses a database and no statement could be read. Also the value for a tool that is not code, such as `Bash` |

Each group of the `risk_map` has a `tier` (`high`, `medium` or `low`) and a list of
`reasons`. A reason has a `key`, its own `tier`, and `items`: the names of the tools,
hooks or servers it comes from. The group gets the highest tier among its reasons. The
report shows the tiers as "Look first", "Look next" and "Look last".

No secret appears in the capability map. Commands are redacted like evidence, and for
environment variables only the names are kept.

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

- **Nineteen checks.** The report lists the ones that ran under "Checks that ran".
- **A path from input is not reported when the tool makes a known containment
  check:** `is_relative_to`, `os.path.commonpath`, `os.path.basename` or
  `secure_filename`. The tool does not judge whether the check is written correctly.
  Only `open`, `read_text`, `read_bytes`, `write_text` and `write_bytes` are seen, not
  calls that delete or copy files.
- **Unsafe loading is reported only for the input of a tool.** `pickle.loads` on data
  that came from the network or from a file of someone else is not found.
- **Switched-off TLS verification is found in two forms:** `verify=False` on a request
  or a client, and `ssl._create_unverified_context()`.
- **For a remote MCP server the tool reports two things only:** an `http` address, and
  a key written in a header such as `Authorization` or `X-API-Key`. Whether the server
  asks who is calling is listed under "Not checked". A server that the project itself
  runs and opens to the network is not examined.
- **Dependencies are looked up only with `--lookup`,** and only the ones the project
  names itself, with one exact version. The packages that those packages bring with
  them are not looked up, and lock files such as `uv.lock` are not read. Neither is
  `package.json`.
- **A known problem in a dependency does not mean the project can be attacked through
  it.** The tool does not know whether the code uses the part of the package that has
  the problem. The severity follows the rating of the database, not the project.
- **Tables and columns come only from SQL written as constant text.** SQL that is put
  together in code, SQL inside a shell command, and queries made through an ORM such
  as SQLAlchemy or Django are not read. The report names the tools this happened to
  under "Not checked".
- **The database is named only when the tool opens it itself, and only for SQLite.**
  A tool that gets its connection from a helper function shows "database unknown".
- **In a statement over several tables, columns are listed only when each one names
  its table** (`c.email`, not `email`). Otherwise the tables are listed with "columns
  not known".
- **`execute` on any object is taken as SQL.** A tool that calls a method named
  `execute` on something that is not a database is listed as using one.
- **A number is not treated as input, but only on the same line.** `int(limit)` inside
  the statement is fine. `limit = int(limit)` on a line above, and then `limit` in the
  statement, is still reported as input pasted into SQL.
- **"Where to look first" is built from the capability map alone.** It does not know
  about authentication, personal data, secrets or content written by strangers, and it
  does not group files that belong to one feature. A script that a skill or a hook
  runs is not part of any group.
- **For files, the report says "reads files" or "writes files", not which files.**
- **Bypass mode in a project's settings file is a warning, not critical.** Claude Code
  2.1.257 and newer ignore `permissions.defaultMode: bypassPermissions` in project and
  local settings. In the code of an agent the same mode always takes effect, and
  there it is critical.
- **Keys are recognised by their shape.** The tool knows the key formats of Anthropic,
  OpenAI, GitHub, Slack, AWS, Google and Stripe, and private key blocks. A password or
  a key of another service is not found.
- **The code reader looks inside each tool, not inside the functions the tool
  calls.** A tool that passes its input to a helper function, which then runs a shell
  command, is not found. The report says so under "Not checked".
- **Only two SDKs are understood:** `mcp` (and the older `fastmcp`) for servers, and
  `claude_agent_sdk` for agents. Only Python. A server written in JavaScript is not
  detected.
- **Shell permissions are checked only in `allowed-tools` of `SKILL.md`.** The allow
  rules of `settings.json` are not read yet.
- **Hooks are read from `hooks.json`, `settings.json` and `settings.local.json`.** A
  hook written inside a skill's frontmatter is not read yet.
- **MCP servers are read from `.mcp.json`,** not from a server defined inside
  `plugin.json`.
- **The test check knows only SQLite.** A test that connects to another real database
  is not found.
- **Missing files are checked only for `${CLAUDE_SKILL_DIR}/...` paths and Markdown
  links** in `SKILL.md`. A file name written as plain text is not checked.
- **No model runs.** Nothing that needs judgment is checked. That includes whether a
  skill does what its description says, and whether private data, content from outside
  and a way out meet in one agent. The capability map gives you the facts to judge the
  second one yourself.

When a creator asks "is my project safe?", the honest answer from this report is:
"these things were checked, and here is the list of what was not".

The full list of what the tool does not see, and what is planned for each, is in
[known-gaps.md](known-gaps.md).
