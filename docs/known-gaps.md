# Known gaps

What the tool does not see today, written down so that nothing is forgotten. A gap is
not a bug: what the tool reports is correct, but it is not the whole picture.

Each gap says whether the design already asks for it. "Not planned" means that no
document assigns it to a step yet, so someone has to decide when it is done.

When a gap is closed, delete its row. When a new one is found, add it here in the same
change that finds it.

## The code reader

| Gap | Example of what is missed | In the design? | What closes it |
| --- | --- | --- | --- |
| It looks inside each tool, not inside the functions the tool calls | A tool passes its input to a helper function, and the helper runs it in a shell | Not planned | Follow calls to functions defined in the same project |
| It does not read which tables and columns a tool touches. `data_scope` is always `unknown` | The report says "uses a database", not "reads name and email from customers" | Yes: requirement F31 in the PRD, `data_scope` in the TDD. Assigned to part 3c, before the risk map, which needs to know which tools change or delete data | Parse the SQL of constant queries. The TDD has an open question about SQL that is built in code |
| It understands only the `mcp`, `fastmcp` and `claude_agent_sdk` libraries, in Python | An MCP server in JavaScript, or an agent built with LangGraph, has no tools in the map | LangGraph and Google ADK are out of the first version. JavaScript is not planned | One reader per framework, behind the same `Analysis` |

## Configuration files

| Gap | Example of what is missed | In the design? | What closes it |
| --- | --- | --- | --- |
| MCP servers are read only from `.mcp.json` | A plugin that defines its servers inside `plugin.json` | Not planned | Read the `mcpServers` key of the manifest |
| Hooks are read only from `hooks.json` and settings files | A hook written in the frontmatter of a skill | Not planned | Read the `hooks` key of the frontmatter |
| Any-shell permission is checked only in `allowed-tools` of a `SKILL.md` | `Bash` in `permissions.allow` of a settings file, or in `allowed_tools` of an agent | Not planned | Feed these into `perm-broad-bash`, with a fixture |
| A plugin without a manifest is recognised as a skill, or not at all | A folder with `skills/` and `hooks/` and no `.claude-plugin/plugin.json` | Not planned | Detect the standard plugin layout |
| Symbolic links that point outside the project are refused, but no test proves it | — | Yes: security fixtures in step 5 | The symlink fixture of step 5 |

## Checks

| Gap | Example of what is missed | In the design? | What closes it |
| --- | --- | --- | --- |
| Keys are recognised by the shape of known providers | A password, or the key of a service that is not in `secret_patterns.toml` | Not planned | A rule for names such as `PASSWORD` and `TOKEN`, measured on the clean fixture for false findings |
| `perm-bypass-in-settings` has unit tests but no fixture. It is listed as the one exception in `tests/test_fixture_evaluation.py` | — | The rule in `CLAUDE.md` asks for a fixture | Plant it in a fixture and remove the exception |
| `test-real-database` knows only SQLite | A test that connects to PostgreSQL or MySQL on a real host | Not planned | Add the connect calls of other drivers to `checks.toml`, with a fixture |
| `ref-missing-file` knows two forms: `${CLAUDE_SKILL_DIR}/...` and Markdown links | A skill that says "run publish.sh" in plain text | Left out on purpose: a file name in a sentence may be a file of the user | Decide after seeing real skills |
| A suggested change exists for two cases only | Any-shell permission, a server without a version | Yes: the TDD wants one for every simple fix | Each needs a fact the code does not have: which commands the skill needs, which version is wanted |

## Waiting for a later step

These are decided and have a place. They are listed so that the list is complete.

| What | When |
| --- | --- |
| Data scope of each tool: database, tables, columns, read or write | Part 3c |
| A fixture with a vulnerable dependency, and the lookup in OSV | Part 3c |
| Whether and how mcpscan-cli is integrated, after measuring it on the fixtures | Part 3c |
| Risk map | Part 3c |
| Everything that needs judgment, including the dangerous combination of capabilities | Step 5 |
| Fixtures that attack the tool itself | Step 5 |
| Real fixtures, with their creator's permission | When one is available |
| Report text in a second language, and an option to choose it | Not scheduled. The structure is ready |
| Whether Bandit is used as an auxiliary scanner, as `design.md` mentions | Not decided |
