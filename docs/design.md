# Audit tool for vibe coded skills, agents and MCP servers

Oct 3, 2026 · @Evgenia

## Goal

The tool shows someone who does not read code what they have actually built and what they are risking. The goal is visibility, not fixing.

- **Who builds:** colleagues who are not developers and write with Claude.
- **What they build:** skills, agents, MCP servers and the settings around them.
- **The problem now:** they do not know what these do. Who will fix the findings is out of scope for now.
- **Who reads the report:** the creator, the person who decides whether it will be used, and the developers.

## What already exists

Mature scanners exist for MCP servers and skills, and it is worth integrating them as a first layer instead of rewriting them. The research was quick (one search per topic), so the list is not exhaustive.

| Tool | Target | What it does | Licence | Local or cloud |
| --- | --- | --- | --- | --- |
| [mcpscan-cli](https://pypi.org/project/mcpscan-cli/) | MCP servers and Claude Code projects | Tool poisoning, command injection, permissions, hooks, secrets, vulnerable SDKs | MIT | Entirely local, with no network and no telemetry |
| [Snyk agent-scan](https://github.com/snyk/agent-scan) (formerly mcp-scan by Invariant Labs) | Agents, MCP servers, skills | Prompt injection, untrusted content, private data, destructive capabilities | Apache-2.0 | Cloud: needs a Snyk account and sends settings, tool descriptions and skill content to their API |
| [Cisco mcp-scanner](https://appsecsanta.com/research/mcp-server-security-audit-2026) | MCP servers | Recognition of known patterns in tool descriptions | Apache-2.0 | Not confirmed |
| [mcp-audit](https://appsecsanta.com/mcp-audit) | MCP settings | Dangerous combinations across servers, Semgrep rules for MCP code | Apache-2.0 | Local, a single binary with no paid tier |
| [SkillScan](https://pypi.org/project/skillscan/) | Skills | Static check, behaviour prediction with an LLM, sandbox testing with decoy files | MIT | Local. The LLM stage needs your own provider, the sandbox needs Docker Desktop |
| [Mondoo AI Agent Skill Check](https://mondoo.com/ai-agent-security/) | Published skills | Check for malicious behaviour | Free service, licence not confirmed | Web service |

### Proposal

mcpscan-cli is the basis for the first layer, for four reasons:

- **It runs entirely locally.** No company data leaves the machine, so no approval is needed to use it at work.
- **It already covers part of the catalogue of mistakes:** wildcard permissions, bypassing confirmations, dangerous hooks, secrets in settings, remote servers without authentication.
- **It is deterministic and outputs JSON and SARIF,** so it fits the finding model and GitHub CI.
- **The MIT licence** allows integration in the public portfolio repo as well.

mcpscan-cli is the only dependency. The other tools in the table are not integrated:

- **SkillScan:** study material for the dynamic check with decoys, when phase 7 arrives. Its code is read, it does not become a dependency.
- **Snyk agent-scan:** an optional comparison, once, on the synthetic fixtures, to show what it finds and what ours finds. Never on company projects without approval, and never inside the tool.
- **mcp-audit:** not needed. The dangerous combinations across servers are computed by our own capability map.

Two reservations about mcpscan-cli: it has a single maintainer and is at beta stage, and as a static check with heuristic rules it does not see prompt injection through content. For this reason the version is pinned and the scanner goes behind an adapter, so that it can be replaced without changes to the rest of the tool.

For general vibe coded code there are also [hallucinot](https://github.com/jayj221/hallucinot) (deleted tests and assertions per commit) and [vibescore](https://socket.dev/npm/package/@marco-trotta1/vibescore) (stubs and placeholders by keyword).

## The gap

Almost all existing scanners assume a malicious third party: they check something before you install it. Here the creator is well-intentioned but does not know what they built.

Three things I did not find covered:

- **Capability map** in plain language: what each agent can read, write and send.
- **Unintentional risk:** excessive permissions, destructive actions without confirmation, data that leaves without intent.
- **Quality:** whether the skill activates when it should and whether it does what its description says.

## Architecture

One analysis produces a common set of findings, and three views filter it for a different reader.

### What it reads

The names of these files and the folders where they live are defined by Anthropic and may change in a new version of Claude Code. Before the code that reads them is written, the current documentation is checked to confirm that the table below still holds.

| File | What it reveals |
| --- | --- |
| `SKILL.md` and the skill's folder | What the description promises, what the scripts do |
| Agent definitions | Which tools each agent has |
| `.mcp.json` | Which MCP servers are connected, with which commands and keys |
| `settings.json` | Permissions and hooks that run automatically |
| `CLAUDE.md` | Standing instructions, often with keys or dangerous commands |
| MCP server code | What each tool does, whether it has auth, where it sends data |

### Three levels of checking

1. **Deterministic:** parsing of the files, capability map, secrets, permissions, hooks, and the existing scanners.
2. **LLM:** agreement of description with implementation, clarity of instructions, dangerous combinations of capabilities.
3. **Dynamic:** execution in a sandbox with decoys and hostile content, recording of what it touched.

### Finding model

Every finding carries all the levels together, so that the views do not disagree.

- **Stable ID**, for reference across the views and comparison of successive audits.
- **Technical:** file, line, rule, evidence, degree of confidence.
- **Consequence:** what can happen and to whom, in plain language. It is derived from the technical finding, never independently.
- **Severity:** seriousness and ease of exploitation.

### Three views

| Reader | Question | Content |
| --- | --- | --- |
| The decision maker | Is it used or not? | Verdict, the 3 to 5 top risks, what was not checked |
| Creator | What did I build and what am I risking? | Capability map, consequences without jargon |
| Developer | Where exactly and why? | Full list with file, line, evidence |

### Delivery

The tool runs on demand, whenever someone asks for it. It does not run automatically on pull requests, because colleagues do not necessarily work that way.

| Way | Who | What runs |
| --- | --- | --- |
| `/audit` in Claude Code or in the IDE | Creators and developers | The deterministic layer, in seconds |
| `/audit full` in Claude Code or in the IDE | Creators and developers | The checkers with the model as well, on the user's Claude subscription |
| Command-line command | Developers | The deterministic layer, and the measurements on the fixtures |

The core is a Python program, independent of Claude Code. The plugin is a layer around it, so that execution with LangGraph or Google ADK can also be added later.

The tool is advisory: it helps, it does not block. Responsibility for whatever goes to production stays with whoever puts it there, and the report always states which layers ran, so that they know what has not been checked.

## Implementation with agentic AI

The tool is built as a graph of agents on top of a deterministic base: code where there is a right answer, agents where judgment is needed. It also serves as a portfolio project.

### What stays plain code

- Parsing of the files and the capability map.
- Secrets, permissions, hooks and the running of the ready-made scanners.
- The verdict, from fixed rules over the findings, so that the same project always gets the same answer.

### The agents

| Agent | Role |
| --- | --- |
| Specialised checkers | One per group in the catalogue of mistakes. They receive the capability map and explore as many files as they need |
| Verifier | Does not see the checker's reasoning and tries to refute every finding. Whatever has no evidence in a file and line is rejected |
| Dynamic tester | Runs the skill or the agent in a sandbox with scenarios and hostile inputs, records what happened |
| Report writer | Translates the verified findings into the three views |

The flow of the graph:

1. Inventory (code).
2. Checkers in parallel.
3. Verifier.
4. Dynamic check for those findings that can be proven in practice.
5. Verdict (code) and report.

The shared state of the graph is the list of findings with their stable IDs.

### Design risks

- **The checker reads untrusted content.** It runs in Docker with no network, no keys, read-only, and treats whatever it reads as data.
- **Non-repeatability.** Two runs give different findings. The stable IDs and the verifier limit this.
- **Cost and time.** A limit on steps and tokens per run.

### What makes it a strong portfolio

- **Public repo with no company code.** The test fixtures are synthetic: skills, agents and MCP servers built on purpose with known mistakes from the catalogue. Real skills are added as fixtures only with their creator's permission.
- **Measurements.** Because the mistakes in the fixtures are known, it is measured how many were found and how many findings were false, with and without the verifier.
- **Documented decisions.** Why each component is code or an agent, and how the checker itself is protected.
- **Example report** in all three views for one fixture.

## Common vibe coder mistakes

The catalogue is the tool's initial list of checks. It is based on general knowledge and not on measurements from your own projects, so it needs verification against real fixtures.

### Permissions and scope

- An agent with all the tools, when it needs two or three.
- Unrestricted shell or wildcard permissions "so it does not keep asking".
- Bypassing confirmations altogether.
- Write access to a database or file system when reading is enough.
- Destructive actions (delete, send, deploy) without a human confirmation step.

### Secrets and data

- API keys and passwords inside `SKILL.md`, `CLAUDE.md`, `.mcp.json` or scripts.
- Keys with full permissions instead of restricted ones.
- A personal account or token of the creator that is shared with the whole team.
- Company or personal data sent to a third-party service without anyone knowing.
- Logs that record sensitive content.

### MCP servers

- A server reachable from the network without authentication.
- Tool input that passes directly into a shell, SQL or a file path.
- A tool that accepts any URL and calls it (SSRF).
- Unclear or misleading tool descriptions, with the result that the model calls the wrong tool.
- One generic tool of the "run whatever I tell you" kind instead of specific actions.
- Installing third-party MCP servers without checking and without a pinned version.

### Prompt injection

- The agent reads untrusted content (web pages, email, user files) and treats it as instructions.
- The dangerous combination in the same agent: private data, untrusted content and the ability to send to the outside.
- A skill that downloads instructions from an external URL at run time.

### Quality of skills and agents

- A description so general that the skill activates everywhere, or so narrow that it never activates.
- Contradictory or excessively long instructions, which the model follows partially.
- The description promises something the scripts do not do.
- References to files, commands or dependencies that do not exist.
- Scripts that work only on the creator's computer (absolute paths, local tools).
- No test case at all. "It worked once" is treated as evidence.
- No failure handling: what happens when a tool returns an error or an empty result.

### Fake functionality

- Hardcoded or sample data presented as real.
- Functions that always return success.
- Errors that are silently swallowed.
- Tests that check nothing or that were disabled so that they pass.
- Protections that the AI removed when it was asked to "fix the error".

### Process

- Whatever is built does not go into a repo, so there is no history and no possibility of checking.
- Nobody read the code before it was used by others.
- Copying skills and settings from the internet without reading them.
- No limit on cost or iterations for agents that run in a loop.

### Thirteen checkpoints

They complement the catalogue above. Each checkpoint becomes one or more checks in the registry.

| Checkpoint | What the tool checks | How |
| --- | --- | --- |
| 1. Test environment | Whether the tests run in a separate environment and test database. Whether they connect to a real database or real services. Whether there is a CI configuration that runs them | Code for settings and connections, the model for the judgment |
| 2. Existence of tests | Whether they exist, whether they cover every tool, whether they check real behaviour or always pass | Code for existence, the model for quality |
| 3. Performance | Tool calls inside a loop, results without a limit or pagination that fill the context, calls without a timeout, sequential execution where parallel is possible | The model, with help from the capability map |
| 4. Good practices | Conventions of the language and framework in use: tool descriptions, skill structure, correct use of the SDK | Code for whatever is formal, the model for the rest |
| 5. Security | The whole existing catalogue: secrets, injection, prompt injection, dangerous combinations | Code and the model |
| 6. Error handling | Errors that are swallowed, tools that return a generic message instead of a structured error, no provision for the failure of an external service, retries without a limit | Code for the patterns, the model for adequacy |
| 7. Scaling | State in memory or in local files, one shared token for all users, no provision for concurrent use or for rate limits | The model |
| 8. Unnecessary dependencies and our own code | Dependencies that are not used. A custom tool or MCP server for something that a ready-made, tested community tool already covers | Code for the unused ones, the model for the "a ready-made one exists" |
| 9. Data access scope | Which database, which tables, which columns and which fields access is given to, with which actions, and whether all of them are needed | Code for whatever is visible in the repo, the documents already in the repo (workshop notes, descriptions) for the rest |
| 10. Bounded or free-form tools | Whether each tool executes predefined queries and actions with parameters, or accepts free-form SQL, a command or an address composed by the agent | Code |
| 11. Validation | Checking of type, range and format on every tool argument and every user input, before it reaches a database, a file or an external service | Code for existence, the model for adequacy |
| 12. Authentication | Who can call the MCP server or the agent, and how they prove who they are | Code |
| 13. Authorization | Whether the agent acts with the permissions of the user who calls it or with a shared account that sees everything. Whether every action checks that the specific user is allowed to perform it | The model, with help from the capability map |

What changes in the design:

- **The capability map gains two new fields per tool.** The data scope (database, tables, columns, read or write) and the kind of tool: bounded, with parameters, or free-form.
- **Intent from the existing documents.** The repos already have documents that describe what they want to build, such as workshop notes. The tool reads them and compares them with what it finds, so that the "are all of them needed?" of checkpoint 9 can be answered. No extra file is asked of the colleagues.
- **Whatever is not visible in the repo is reported explicitly.** The permissions of the database account and the environment where the tests run are often defined outside the repo. There the tool writes "cannot be verified from the repo" and puts the question to the developer.
- **Checkpoint 8 also has an opposite side.** A ready-made community tool is preferred over our own, but only if it has been checked and has a pinned version. The catalogue already treats installing a third-party MCP server without checking as a mistake.
- **Performance, scaling and good practices are checked only in the agentic code,** in line with the scope.

### Reuse

It is checked in two specific forms. The general judgment "it could be more general" is not checked, because it produces noise and pushes towards premature generalisation.

| Form | What the tool checks | How |
| --- | --- | --- |
| Can someone else use it? | Absolute paths and user names in the code, a personal token instead of a setting, values of a specific project written into the skill instead of arguments, no description of how it is set up | Mostly code |
| Repetition within the same project | The same logic copied into many tools, the same instructions in many skills. Only plain copying, as `suggestion` | Code for detection, the model for the judgment |

Detecting similar artifacts in other repos of the company is out of scope at this phase.

### One responsibility per component

A tool, an agent, a skill or an MCP server that does many unrelated jobs needs more permissions and makes the choice harder for the model. The concentration of responsibilities in one agent is often also the cause of the dangerous combination (private data, untrusted content, output to the outside).

| Level | What a violation means | Signal the code finds |
| --- | --- | --- |
| Tool | One tool does many unrelated jobs | An argument such as `action` or `mode` that changes the behaviour, reading and writing in the same tool |
| Agent | One agent with many unrelated roles | The number of tools, and how many different kinds of access it concentrates |
| Skill | One skill for many unrelated jobs | A description with many unrelated activation triggers, a very long `SKILL.md` |
| MCP server | One server for unrelated systems | Tools that touch unrelated services or databases |

Rules:

- **Signal first, then judgment.** The code finds the signal from the capability map, and only then does the model judge whether it is a real problem. Without a signal no check is made.
- **Severity.** `suggestion` normally, `warning` when the concentration of responsibilities is what gives excessive permissions.
- **Out of scope:** the same principle at the level of functions and classes, which is a general code check.

## Differentiation ideas

The first two are the most open field. The rest already exist in some form and are integrated.

| Idea | What it does | State of the market |
| --- | --- | --- |
| Intent versus implementation | Checks whether scripts and permissions agree with the natural-language description | Mostly research, no ready-made tool for existing projects |
| Behaviour-based fake functionality | Detects code that looks like it works without working | The existing tools only look for keywords |
| Evidence in practice | Runs the agent in a sandbox and shows what it did | Exists for malicious skills (SkillScan) |
| Silent removals | Compares commits for protections that were lost | Exists for tests and APIs (hallucinot, RegressGuard) |
| Prevention | A ready-made template with rules and hooks so that the mistakes do not get written | Templates exist, not specifically for skills and MCP |

## First steps and open questions

The proposal is to start from the deterministic layer, because it gives the capability map without an LLM and without false positives.

1. Collecting 3 to 5 real projects of colleagues as test fixtures.
2. A parser for the configuration files and generation of the capability map.
3. Integration of one existing scanner as the first layer.
4. 10 to 15 high-confidence checks from the catalogue of mistakes.
5. Developer view first, then the other two on the same data.
6. LLM layer and dynamic check once the above have stabilised.

### Decisions

| Question | Decision | What it means for the tool |
| --- | --- | --- |
| Where they build them | Wherever they build them, everything goes into a repo: plugin, standalone skill or code. Every project has its own repo | One input, the repo, and one report per repo. The tool first recognises what it contains (plugin, skill, code) and chooses checks. It runs on demand inside Claude Code |
| Who gives the verdict | The creator, who is also responsible for whatever they put into production. The developer reads the report and warns them | The tool proposes a verdict with reasoning, it does not block on its own |
| Which mistakes appear in practice | It will show in the trials, the catalogue is enriched along the way | The checks are defined as data with their own ID, so that they can be added without a code change |
| Who fixes | The creator. The simple ones on their own with the ready-made changes, and they rerun the audit. For the complex ones they ask a developer for help | The tool automatically classifies every finding (severity, confidence, simple or complex). The developer corrects the classification where they disagree and points out the serious ones to the creator. The simple ones have instructions in plain language |

**Scope:** MCP servers, scripts around skills, tools and whatever concerns agentic AI, together with Python code that implements agents. The boundary is defined by what the code does and not by the language: the audit of general code is out of scope and no extension in that direction is planned.

For the Python code of the agents the tool needs:

- **Reading the code with AST** for the capability map: which tools are defined and what each one touches (files, network, shell, database).
- **Agent-specific checks:** model output that passes into `eval`, shell or SQL, tool arguments without checking, a loop without a limit on steps or cost, calls without a timeout, keys inside the code or the prompts.
- **Ready-made Python scanners as an auxiliary layer,** only on the agent's files: Bandit for dangerous calls, pip-audit for vulnerable dependencies.

**Frameworks (to be confirmed):** Claude Agent SDK, LangGraph and Google ADK. Each framework declares the agent's tools and limits in a different way, so recognition is done with one adapter per framework. All the adapters produce the same capability map, so that the checks from there on are shared.

| What the adapter looks for | Why |
| --- | --- |
| Where the tools are defined and which function each one runs | The basis of the capability map |
| Which tools are allowed and how permissions are granted | Excessive permissions, bypassing confirmations |
| Limit on steps, iterations or cost | Agents that run in a loop without a brake |
| Human confirmation points | Destructive actions without approval |
| Sub-agents and what they inherit | Permissions that pass silently to another agent |

Implementation order: the first projects are with Claude, so the adapter for the Claude Agent SDK is written first. LangGraph and Google ADK follow when real projects appear. A repo with an unknown framework is reported as "not checked".

Two consequences for the design:

- **Comparison between runs.** Since the creator fixes and reruns, the report shows what was closed, what remained and what newly appeared. The stable IDs allow this, and so it becomes visible whether a fix broke something else.
- **The views effectively become two.** The decision maker is the creator, so the proposed verdict is written in plain language at the top of the report. The developer sees the technical details below it, to know where to warn.

### Storing results

Every run is stored in a local history, on the computer of whoever ran it and outside the project. The tool writes nothing inside the project and sends findings nowhere.

- **The identity is the repo.** The history has one folder per repo and one per run.
- **Everyone has their own history.** The creator sees the progress of their project. The developers have read access to the repos and run the audit themselves, so their own history covers all the projects.
- **The statistics come from the developers' history,** with the command `audit stats`, per check and per repo.
- **The user's judgment is recorded.** If they say in the conversation that a finding is wrong, it goes into the history.

The statistics serve two purposes: improving the tool, and showing in which area the creator of each project needs training.

| Measurement | What it is used for |
| --- | --- |
| Share of findings judged wrong, per check | Which checks need fixing or removal |
| Problems that the developer found and the tool missed | Which new checks are missing from the catalogue |
| Most frequent mistakes overall and per repo | What needs training or prevention |
| Findings that were closed and in how many runs | How understandable the fix instructions are |
| Critical findings that stay open | Where a warning from a developer is needed |

Constraints:

- **Secrets are never written,** neither in the report nor in the history. Only their location is recorded.
- **The history contains a list of open weaknesses,** so it stays local and does not go into a shared space.
- **A creator's runs do not reach the developers.** The statistics are based on the runs that the developers themselves make.

### Automatic classification of findings

The tool classifies every finding on three axes and shows them in the report. It reports only what really exists and has evidence.

| Severity | What it means | Examples |
| --- | --- | --- |
| 🔴 Critical | Leak, destruction of data or execution of foreign commands. Must be fixed | Keys inside files, an MCP server on the network without authentication, input that passes into shell, `eval` or SQL, bypassing confirmations, a destructive action without approval, private data together with untrusted content and output to the outside |
| 🟠 Error | It does not do what it says or it will fail in practice | A description that does not agree with the scripts, references to files or commands that do not exist, fake functionality, a loop without a limit, no error handling |
| 🟡 Warning | Unnecessary risk or a maintenance problem | More tools or permissions than needed, a third-party MCP server without a pinned version, unclear tool descriptions, absolute paths, no test |
| 🔵 Suggestion | A better approach | A narrower activation description, splitting long instructions, specific tools instead of one generic tool |
| ⚪ Nitpick | Style and names, optional | Naming, formatting, spelling |

| Confidence | Where it comes from |
| --- | --- |
| High | A deterministic check, or confirmation in the sandbox |
| Medium | A finding from the LLM that passed the verifier with evidence in a file and line |
| Low | An indication without full evidence. It is shown collapsed and does not count towards the verdict |

| Fix | Criteria |
| --- | --- |
| Simple | A change at one point of configuration or text, with mechanical steps and without a change of logic. E.g. moving a key to an environment variable, narrowing a list of tools |
| Complex | A change of code logic, many files, or a security decision. E.g. adding authentication, splitting an agent, input checking |

Confidence replaces "right or wrong": the tool cannot know whether it made a mistake, it can say how sure it is. The developer corrects the classification where they disagree, and every correction is recorded as data for improving the rules.

### Presentation

The report appears in the Claude Code conversation and is also written to a file in the local history.

- **Proposed verdict at the top,** in plain language, with which layers ran.
- **Risk map** as "where to look first", and capability map.
- **Findings by severity,** each with file and line, confidence, consequence in plain language and evidence. No headings for empty categories. Nitpicks and low-confidence findings in brief.
- **Proposed change for the simple fixes.** The user can ask Claude to apply it. The tool does not change files.
- **What changed since the previous run,** and what was not checked.
- **Positives and summary at the end:** up to five things that were done right, and an overall assessment.
