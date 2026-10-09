# PRD: Audit tool for agentic AI

Oct 3, 2026 · @Evgenia

## Summary

An open-source tool that checks skills, plugins, MCP servers and agents built with Claude, and shows in plain language what they can do and what they risk. It is aimed at teams where non-programmers build such artifacts with AI and the developers help them see what they risk.

The tool runs on demand, with one command inside Claude Code or the IDE, and from the command line. Findings are classified automatically and shown in the conversation, with a proposed change where the fix is simple.

Related documents: the design ("Audit tool for vibe coded skills, agents and MCP servers"), the "Implementation plan" and the TDD.

## Problem and opportunity

Colleagues who are not developers use Claude to build skills, agents and MCP servers that are used by others. They do not know exactly what they built: which permissions they granted, where the data goes, whether what they describe is what is executed.

Today the check is done by developers by hand, after the artifact has already been built, and often after it has already been used.

### Why the existing tools are not enough

There are mature scanners for MCP servers and skills (mcpscan-cli, Snyk agent-scan, Cisco mcp-scanner, SkillScan). Almost all of them assume a malicious third party and check something before you install it. Here the creator is well-meaning but inexperienced, and three things remain uncovered:

- **Capability map** in plain language: what each artifact can read, write and send.
- **Unintended risk:** excessive permissions, destructive actions without confirmation, data that leaves without intent.
- **Quality:** whether the artifact does what its description says.

The market research was brief, so the gap is an estimate and not a certainty.

## Users

| User | Who they are | What they need |
| --- | --- | --- |
| Creator | A colleague with no programming knowledge, who builds with Claude and is responsible for whatever they put into production | To understand what they built and what it risks, and to fix the simple things themselves |
| Developer | Reads the reports and warns the creator about anything that is dangerous. Does not approve and does not block | To see exactly where each problem is and why, with evidence, and a proposed verdict |
| External user | Anyone who downloads the open tool | To run it locally without accounts and without sending data anywhere |

The decision and the responsibility belong to the creator. The tool proposes and gives reasons, and the developer warns.

## Goals and non-goals

### Goals

- **Visibility.** Every artifact has a capability map that a non-programmer can also understand.
- **Reliable findings.** Every finding has evidence in a file and line. Few and certain findings are preferred over many and uncertain ones.
- **Checking without effort.** The audit runs with one command inside Claude Code, whenever someone asks for it.
- **Learning from use.** The developers' corrections improve the checks.
- **Portfolio.** A public agentic project with measurable results.

### Non-goals

- **Audit of general code.** The tool checks only agentic artifacts and the code that implements them. No extension is planned.
- **Automatic approval or rejection.** The tool is advisory. It does not block and does not require a full run before approval.
- **Automatic fixing of complex problems.** It proposes a ready-made change only for simple fixes.
- **Employee evaluation.** The statistics are produced per repo and serve to improve the tool and to train the creator, not for grading.
- **Detecting malicious third parties.** This is covered by the existing scanners, which are integrated as the first layer.

## Use cases

### The creator checks their project

1. The colleague has built a skill with Claude. They type `/audit` inside Claude Code.
2. Within seconds they see in the conversation what their skill can do and what it risks, with the findings in plain language.
3. For the simple fixes they see the proposed change and ask Claude to apply it.
4. They run `/audit` again and see what was closed.
5. Before giving it to others, they run `/audit full` for a fuller check.

### The developer warns

1. They have read access to the colleagues' repos. They open one of them and run `/audit full`.
2. They read the proposed verdict and the findings, starting from the risk map.
3. If a finding is wrong, they say so in the conversation and it is recorded.
4. They point out the serious findings to the creator, and help with the complex fixes when asked. The decision stays with the creator.

### The developer improves the tool

The history of their own runs covers all the projects. From it they produce statistics per check and per repo, and see which checks need fixing and which creator needs training in which area.

### The external user

They install the plugin or the command, and run the audit on their own computer. Without a subscription or API key only the deterministic layer runs.

## Functional requirements

The priorities: P0 is necessary for the first useful version, P1 for use at work, P2 comes later.

### Input and detection

| ID | Requirement | Pri. |
| --- | --- | --- |
| F1 | Accepts a folder or repo. One repo is one project | P0 |
| F2 | Detects the type: skill, plugin, MCP server, agent in Python | P0 |
| F3 | Supports Claude projects: `SKILL.md`, `.mcp.json`, `settings.json`, `CLAUDE.md`, Claude Agent SDK | P0 |
| F4 | Whatever it does not detect or does not check, it reports explicitly as "not checked" | P0 |
| F5 | Supports agents in LangGraph and Google ADK | P2 |

### Analysis

| ID | Requirement | Pri. |
| --- | --- | --- |
| F6 | Produces a capability map: which tools exist and what each one touches | P0 |
| F7 | Deterministic layer: its own checks and an integrated scanner | P0 |
| F8 | Model-based layer: specialised checkers per group of mistakes | P0 |
| F9 | Independent verifier that rejects findings without evidence | P0 |
| F10 | Before each run the user chooses whether the model-based layer runs | P0 |
| F11 | Dynamic testing in a sandbox with decoys | P2 |

### Findings and classification

| ID | Requirement | Pri. |
| --- | --- | --- |
| F12 | Every finding has a stable ID, file, line, evidence and a consequence in plain language | P0 |
| F13 | Automatic classification into severity (Critical, Error, Warning, Suggestion, Nitpick) | P0 |
| F14 | Automatic confidence (high, medium, low) from the path that produced the finding | P0 |
| F15 | Automatic labelling of the fix as simple or complex | P1 |
| F16 | Proposed verdict from fixed rules, with reasoning | P0 |
| F17 | Checks are defined as data, so that they can be added without changing the core | P1 |

### Presentation

| ID | Requirement | Pri. |
| --- | --- | --- |
| F18 | Output in JSON with a stable schema and in a readable form | P0 |
| F19 | Report inside the Claude Code conversation, with the proposed verdict in plain language at the top | P0 |
| F20 | For the simple fixes, a proposed change that the user can ask Claude to apply. The tool does not change files | P1 |
| F21 | Comparison with the previous run of the same repo: what was closed, what remained, what is new | P1 |
| F22 | The report states which layers ran | P0 |
| F23 | Positives and a summary at the end, without headings for empty categories | P1 |

### Ways of running

| ID | Requirement | Pri. |
| --- | --- | --- |
| F24 | Plugin for Claude Code, with `/audit` for a quick check and `/audit full` for a full one. It also works inside the IDE | P0 |
| F25 | Command-line command, for the deterministic layer and for the measurements | P0 |
| F26 | The model-based layer runs inside the user's session, with their subscription, without an API key | P0 |
| F27 | The core is independent of Claude Code, so that running with LangGraph or Google ADK can be added later | P1 |

### Statistics and learning

| ID | Requirement | Pri. |
| --- | --- | --- |
| F28 | Every run is stored in a local history, on the computer of whoever ran it and outside the project | P1 |
| F29 | Statistics per check and per repo from the local history | P1 |
| F30 | The user marks a finding as wrong or correct inside the conversation, and their judgment is recorded | P1 |

### Check coverage

They come from the thirteen checkpoints and from the existing skills (WARM, first-five, triage, zombies).

| ID | Requirement | Pri. |
| --- | --- | --- |
| F31 | The capability map shows, for each tool, which database, tables and columns it has access to, and with which actions | P0 |
| F32 | Each tool is labelled as fixed, parameterised, or free-form (it accepts SQL, a command or an address composed by the agent) | P0 |
| F33 | Check of authentication and authorization: who is calling, and with whose permissions the agent acts | P0 |
| F34 | Check of input validation and error handling in every tool | P0 |
| F35 | Check for calls to methods or tools and references to files or variables that do not exist | P0 |
| F36 | Whatever cannot be verified from the repo (account permissions in the database, the environment of the tests) is reported explicitly as a question to the developer | P0 |
| F37 | Check that tests exist and of the environment where they run, with emphasis on the use of a real database | P1 |
| F38 | When tests are missing, specific suggestions per tool using the ZOMBIES method. The tool does not write the tests | P1 |
| F39 | Dependency check using the WARM method, for third-party packages, MCP servers and plugins | P1 |
| F40 | Check for the reverse too: our own code where a ready-made, tested tool exists | P1 |
| F41 | Risk map per feature in the report, as "where to look first" | P1 |
| F42 | The creator's intent is read from the documents that already exist in the repo (workshop notes, descriptions) and compared with what was found. No extra file is asked for | P1 |
| F43 | Checks of performance, scaling and good practices, only in the agentic code | P2 |

Reuse:

| ID | Requirement | Pri. |
| --- | --- | --- |
| F44 | Check that the artifact can be used by someone else: without absolute paths, personal tokens or project-specific values inside the code | P0 |
| F45 | Check for outright duplication of logic or instructions within the same project | P2 |

Detecting similar artifacts in other repos of the company is out of scope at this stage.

One responsibility per component:

| ID | Requirement | Pri. |
| --- | --- | --- |
| F46 | Check for a tool, agent, skill or MCP server that gathers many unrelated responsibilities, based on measurable signals from the capability map | P1 |

The same principle at the level of functions and classes is out of scope.

## Non-functional requirements

| ID | Requirement |
| --- | --- |
| N1 | **Local execution.** The deterministic layer does not send code or project content anywhere. The only exception is the dependency check, which queries a public database sending only the package name and version. It runs only when it is asked for with a parameter, because the name of a private package would otherwise leave the machine without anyone deciding it. Without the parameter the report lists what would be sent. The model-based layer sends data only to the model provider |
| N2 | **Security of the checker.** It only reads, inside the project folder, without network. Whatever it reads it treats as data and not as instructions. The restrictions are enforced by code |
| N3 | **No secret in the output.** Not in the report, not in the statistics, not in logs. Only the location is recorded |
| N4 | **Nothing inside the project, nothing to third parties.** The tool does not write files in the project and does not send findings to a third-party system. The history stays on the computer of whoever runs the tool. The tool only reads and does not change files |
| N5 | **Repeatability.** The deterministic layer and the verdict give the same result for the same input |
| N6 | **Speed.** The deterministic layer finishes in seconds, so that nobody has to wait |
| N7 | **Cost limit.** Every run with a model has an upper limit on steps and tokens |
| N8 | **Resilience.** If a checker fails, the report is still produced, with an explicit note on what was not completed |
| N9 | **Clean public repo.** No company code, addresses or keys. Fixtures are synthetic, or real skills used with their creator's permission |
| N10 | **Licence.** Open source, compatible with the licences of the tools it integrates |

## Success metrics

The targets with a number are initial proposals and are revised after the first measurements.

### Quality of the tool, on the synthetic fixtures

| Metric | Target |
| --- | --- |
| Planted mistakes found, per check type | At least 80% in each type, not only overall |
| Findings in the clean fixture | No Critical or Error |
| False findings with and without the verifier | Measurable reduction, without losing correct ones |
| Attack fixture against the checker | Reported as a finding, not executed |

### Usefulness at work

| Metric | What it shows |
| --- | --- |
| Findings the developer rejects, per check | Which checks need fixing |
| Problems the developer found and the tool missed | Which checks are missing |
| Simple fixes approved without changes | When approval stops being needed |
| Runs until a finding is closed | How understandable the instructions are |
| Full runs relative to quick ones | How often the full run is requested, which is not mandatory |

## Versions

The first version must be simple and be finished quickly. Whatever is left out is added later, without changing the core. Where this section differs from the priorities of the requirements, this section applies.

### First version

| Part | What it contains |
| --- | --- |
| Core in Python | Project type detection, capability map, code-based checks, known vulnerabilities of dependencies on request, simple risk map, classification and proposed verdict |
| Plugin for Claude Code | `/audit` for a quick check and `/audit full` for a full one, with the report in the conversation |
| Six checkers as subagents | Access, data flow, intent versus implementation, reliability with suggestions for tests (ZOMBIES), practices, performance and scaling |
| Verifier | Independent subagent per finding |
| Protection of the checker | Read-only tools and plugin hooks |
| Intent from existing documents | The checker reads the workshop notes and the descriptions that already exist in the repo |
| Dynamic tester | For MCP servers and for scripts that accompany skills, in a sandbox with decoys. Without a model and without any credential inside the sandbox |
| Fixtures and comparison | Synthetic and real fixtures, with measurement of the deterministic layer |

### Later

| Part | Why not now |
| --- | --- |
| Runner with the Agent SDK and model-based measurements | Needs an API key and a separate program. In the first version the quality of the checkers is judged from use |
| Local history, statistics, run comparison | They are not needed to produce a useful report |
| Dynamic testing of skills and agents | Needs a model. It will be designed so that the credential stays outside the sandbox |
| Local MCP server for the core tools | Makes sense when there are many runners |
| Full WARM | The first three questions need work per package ecosystem |
| Checking and running with LangGraph and Google ADK | The first projects are with Claude |

Outside the design for now: fix examples per check, and fix suggestions from similar old findings (RAG).

Without model-based measurements, the checkers that rely on judgment (practices, performance, scaling) may produce noise. That is why in the first version their findings do not go above `warning` and are shown in a separate "Observations" section, below the rest.

## Risks and open questions

### Risks

| Risk | Mitigation |
| --- | --- |
| Many false findings, so users ignore the tool | Verifier, evidence in every finding, low confidence collapsed, measurement per check |
| The judgment checks (performance, scaling, practices) produce noise | They go in last, start as `suggestion`, and stay only if the measurements justify it |
| The scope slides towards general code checking | Every new check applies only to agentic code. Whatever else exists in the repo is reported as "not checked" |
| False sense of security from a clean result | The report always states what was not checked, what cannot be verified from the repo, and which layers ran |
| The checker is led astray by the content it reads | Read-only, hooks, Docker without network, attack fixture in the tests |
| The creator fixes superficially through AI, or writes tests that always pass | Every fix goes through the audit again, and the run comparison shows whether something else broke. The fake functionality check also runs on the new tests |
| The workshop documents are old or unclear, and the comparison produces wrong differences | Every difference is shown as a question to the creator, with the excerpt of the document next to it, not as an error |
| Cost of the model-based layer | Deterministic by default, full only when requested, a limit per run, priority to the high-risk groups |
| Dependence on a scanner with a single maintainer | Pinned version, adapter that allows replacement |
| Changes in the Claude formats and in the SDKs | Pinned versions that are supported, tests on the fixtures |
| The local history contains a list of open weaknesses | It stays on the computer of whoever ran the audit, outside the project. Secrets are never written |

Running on demand adds one risk: the tool helps only if someone runs it. That is why the developers run it too, on the repos where they have read access, so that the check does not depend only on the creator's initiative.

### Open questions

- [ ] In which language are the reports for the colleagues written, Greek or English?
- [ ] What does the tool do when a repo has no document describing what they want to build?
- [ ] Does the rule "if it is small we write it, a substantial integration we take ready-made" need a more specific threshold?
- [ ] How is the plugin distributed to the colleagues and how is it updated when a new version comes out?
- [ ] If the colleagues start working with pull requests, is it worth adding a check there too?
