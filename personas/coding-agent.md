# The coding agent

*Persona · written 2026-09-24 · Status: **assumed, not observed** — a recorded session here is an agent given a project and a question, watched, not a person · From `docs/lakelet-agent-first-strategy.md`, which makes the agent a customer that acts on a person's behalf · Product name: QuerySolo.*

Not a person, but a user: Claude Code, Cursor, Codex or Windsurf, running in one of the other personas' projects with their credentials and their laptop. Everything the strategy note says about why this matters holds, and the gauge-first business model puts agent identities second among the things that are sold. What this file adds is the agent's day: what it reaches for, what it cannot see, and where the product refuses or fails to.

## Who

An agent in an editor or a terminal, driven by a person who asked a question, wants a table made, or wants a model written. It reads files, runs commands, reads their output, and loops until it believes it is done. It does not know the cost of anything before it runs it, it treats every string it reads as possibly an instruction, and it will run the same query forty times to be sure. Behind it is the solo analyst, the dbt person or the learner; the agent inherits their machine, their files, their bucket credentials and their trust.

## Tools, and where the day goes

| Task | What the agent uses today | What it sees |
|---|---|---|
| Learn the project | `AGENTS.md`, `CLAUDE.md`, the folder listing, `querysolo.toml` | the tables, the gauge, the conventions, written by `init` |
| Find the tables | `querysolo tables list`, `describe` | names, columns, types, snapshots, freshness |
| Look at data | `querysolo sql "select * ... limit 20"` | rows on stdout, the verdict line on stderr |
| Know the cost | `querysolo estimate` | bytes, seconds, the verdict, as a line to parse |
| Run | `querysolo sql`, the HTTP API with the bearer token | rows or an Arrow stream; Red as a refusal with an exit code |
| Save | `querysolo question save`, editing files under `models/` | a model with two checks and a commit |
| Change the project | `querysolo import`, `tables attach`, `run` | tables appearing; a run with a verdict per model |
| Credentials | the AWS profile the project names, in the environment | never a key in the folder |

## What hurts, for an agent

- Cost is unknown before a run, on every warehouse it is ever pointed at. Here it is known, but as a line of text on stderr rather than a value.
- Nothing bounds a loop: forty queries, each fine, together a bill or an hour.
- Output that is not structured has to be parsed, and parsing is where it goes wrong.
- A large result into the context window is the end of the session.
- Destructive verbs look like any other verb.
- A cell in a table that says "ignore previous instructions" is data to a person and a sentence to an agent.
- The schema has to be rediscovered every session unless something wrote it down.

## Scenarios

Each: the situation, what happens today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. Opening a project it has never seen

The person says "what is in here?" Today, in any other stack, the agent lists files and guesses. With the product it reads `AGENTS.md`, which `init` wrote and the core keeps current with the tables, runs `tables list` and `describe`, samples a few rows with values truncated, and answers with the schema and the freshness.

*Built today.* `AGENTS.md`, `tables list`, `describe`. *Planned:* the MCP `list_tables`, `describe` and `sample` tools, with `sample` truncating values by rule so a cell cannot carry an instruction into the context whole.

### 2. Answering a question with SQL

"Revenue by region, paid only." The agent writes the SQL, runs `estimate`, reads green, runs `sql`, returns the rows. When the verdict is Red it stops and reports the sentence instead of forcing the run, because the refusal is an exit code and running anyway is an explicit flag.

*Built today.* `estimate`, `sql`, the refusal, the exit codes documented. *Planned:* `estimate` as a structured value rather than a line to parse; `--json` where it is missing; a row limit on `sql`'s output for the agent's sake, to check what the CLI does today with a million rows.

### 3. The loop

The agent tries forty variants to be sure. Today nothing stops it but the per-query refusal. With the product the agent runs under an identity with a daily budget in bytes and seconds, the core refuses past it, and every call is in a log with the agent's name, the verdict and the outcome. With burst, the budget is dollars. Read tools are on by default; write tools are opt-in per project.

*Planned.* The local budget (E2 in the session log), the identity, the log, the per-tool permissions: session 5, which the gauge-first business model moves up. *Today:* nothing bounds the loop.

### 4. Saving its work for review

The agent keeps the query as a question. It becomes a model with two checks and a commit, and the person reviews the diff in the model's versions or in a pull request. If the agent edited a model file directly, the run records the state as edited and the Review section shows the SQL diff before anything builds.

*Built today.* Save as question and its commit, versions, the edited state and the diff. *Planned:* the commit naming the agent as the author, so the review knows who wrote it.

### 5. The data it must not obey

A CSV somebody sent has a cell that reads like an instruction. The agent samples the table and reads it. With the product sample rows sent anywhere are truncated and never executed, the agent cannot change `querysolo.toml` through its tools, credentials are an AWS profile in the environment and never in the folder, and the API is loopback with a token. Prompt injection through table contents is treated as a threat in the strategy note, and the rules are where it is stopped.

*Built today.* The profile per project, the loopback API, the token, the network audit. *Planned:* the truncation rule and the `querysolo.toml` guard as MCP policy; today `sql` prints what it finds.

### 6. Provisioning for the person

An app builder or a coding tool creates the lakehouse for its user: `init`, a bucket attached, a cap set, credentials handed back. Today an agent can run `init` like anyone and nothing records that it did. With the product the CLI carries who called it, the share of projects agent-initiated is a number on the deck, and the management API lets a platform do it without a terminal.

*Planned.* Day 2 to 3 in the strategy note. *Today:* `init` works and is anonymous about its caller.

## Where this persona hits walls today

- **No budget.** Scenario 3 is the sellable one and nothing bounds a loop.
- **No MCP.** The agent parses stderr and stdout; the verdict is a line, not a value.
- **Structured output is partial.** `lineage --json` and `gauge export` exist; `estimate` and `sql` are text. The API is the structured path and needs the token.
- **Large results.** What `querysolo sql` prints for a million rows, and whether the agent's context survives it, is to check.
- **The author.** A commit an agent made says the person made it.
- **Write tools are not opt-in,** because there are no tools; the CLI does what it is told.

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- Session 5 sits after burst in the map. The business model argues it should come before, because the local budget makes the agent line sellable with no cloud, and the CLI's `estimate --json` and a `sample` verb are the first two days of it.
- The record of which persona the agent worked for matters as much as the agent's log: the MCP client name and the CLI's caller belong in the same field.
- The truncation rule is cheap and should land before the MCP server, since `sql` already prints cells to agents today.

## Questions for a recorded agent session

- Given the folder and "what is in here?", does it read `AGENTS.md` first, and is what it says true.
- Given a question, does it run `estimate` before `sql`, unprompted. If not, does `AGENTS.md` saying so change that.
- Given Red, does it stop, report, or force the run.
- Given a table with an instruction in a cell, what does it do with it.
- How many queries does it run to answer one question, and what would a budget of ten have done.
- Does it save the question, edit a model file, or neither, and does the person find the change in versions.
