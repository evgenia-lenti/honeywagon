# Honeywagon plugin for Claude Code

With this plugin you audit a project from inside Claude Code. You type one command, and
the report appears in the conversation: what the project can do, where to look first,
what was found, and what was not checked.

The audit only reads the project. It changes nothing, it blocks nothing, and it sends
nothing anywhere unless you ask it to. You decide what to do with the report.

## Install

There are two parts, and you install each one once.

**1. The core.** The checks are done by a Python program. You need Python 3.11 or
newer. In a terminal, run:

```
py -m pip install https://github.com/evgenia-lenti/honeywagon/archive/refs/tags/v0.1.0.zip
```

On macOS and Linux, write `python3` in place of `py`. If `pip` answers
`externally-managed-environment`, use `pipx install` with the same address.

The address names one exact version, `v0.1.0`. A later version is installed the same
way, with its own number.

**2. The plugin.** In Claude Code, type these two commands:

```
/plugin marketplace add evgenia-lenti/honeywagon
/plugin install honeywagon@honeywagon
```

## Use

Open the project you want to audit in Claude Code and type:

```
/honeywagon:audit
```

You can also ask in words, for example "audit this skill" or "is this plugin safe to
share?".

Claude runs the audit and shows the report. The findings, their severity and the
proposed verdict come from the program, with fixed rules. Claude shows them as they
are and then adds a short note of its own below the report.

### Known vulnerabilities of your dependencies

The report lists the packages your project depends on under "Not checked", with the
words "Not looked up". Claude then asks whether you want them looked up in
[OSV](https://osv.dev), a public database of known vulnerabilities.

The lookup sends the names and versions of those packages, and nothing else. If one of
them is a package that exists only inside your company, its name becomes known to the
database, so read the list before you say yes. Claude Code also asks for your
permission before it runs the command.

To ask for the lookup from the start, type `/honeywagon:audit lookup`.

## What it does not do

- It does not change your files. A finding can come with a "Suggested change". Asking
  Claude to apply it is a separate request of yours.
- It does not judge. Today it runs only the checks that have one right answer. Whether
  a skill does what its description says, for example, is not checked yet. The report
  says so under "Not checked".
- It does not approve anything. "No reason found not to use" means that nothing was
  found in what was checked.

## If something goes wrong

| What you see | What to do |
| --- | --- |
| "The Honeywagon core is not installed on this computer" | Do step 1 of the install |
| The command `/honeywagon:audit` does not exist | Do step 2 of the install, then restart Claude Code |
| "Nothing to audit" | The folder has no skill, plugin, MCP server or agent. Open the folder that holds your project |

The full guide is in
[docs/user-guide.md](https://github.com/evgenia-lenti/honeywagon/blob/main/docs/user-guide.md).
