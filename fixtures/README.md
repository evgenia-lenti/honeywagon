# Fixtures

Small fake projects that the audit tool is measured against.

**The code here is wrong on purpose.** Four of the fixtures contain planted mistakes:
excessive permissions, injection, hard-coded keys and more. Do not copy anything from
them, do not install them and do not run them. Every key and token in these folders is
fake and was never valid.

| Fixture | Kind | Planted mistakes |
| --- | --- | --- |
| `skill-release-notes` | skill | 5 |
| `plugin-team-helper` | plugin | 5 |
| `mcp-customer-db` | MCP server | 5 |
| `agent-support-triage` | agent | 5 |
| `clean-plugin` | plugin | 0 |

## Layout

Each fixture has two parts:

- `project/` is the project the tool audits. Nothing inside it says that it is a
  fixture, so that a checker cannot use that as a hint.
- `expected.json` lists the planted mistakes. It sits outside `project/` so that the
  tool never reads it as part of the audited project.

## `expected.json`

```json
{
  "schema_version": 1,
  "project_kind": "skill",
  "expected": [
    {
      "check_id": "perm-broad-bash",
      "file": ".claude/skills/release-notes/SKILL.md",
      "line": 4,
      "severity": "critical",
      "layer": "deterministic",
      "contains": "allowed-tools:"
    }
  ]
}
```

| Field | Meaning |
| --- | --- |
| `project_kind` | `skill`, `plugin`, `mcp_server` or `agent` |
| `check_id` | The check that should report the mistake |
| `file` | Path inside `project/`, with forward slashes |
| `line` | Line of the mistake, counted from 1 |
| `severity` | `critical`, `error`, `warning`, `suggestion` or `nitpick` |
| `layer` | `deterministic` if code can find it, `model` if it needs judgment |
| `contains` | Text that must be on that line. A test checks it, so a moved line is noticed. For a secret, only the name of the variable, never the value |

`clean-plugin` has an empty `expected` list. Any finding there is a false finding.

## Changing a fixture

When a file in `project/` changes, update the line numbers in `expected.json`. The
tests in `tests/test_fixtures.py` fail if a line no longer contains its `contains` text.

To compare the tool's output with the planted mistakes, run `evaluate.py` from the
repository root.
