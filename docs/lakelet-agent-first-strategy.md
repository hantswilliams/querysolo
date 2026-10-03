# QuerySolo — Agent-first: the Supabase playbook, applied

*Strategy note v0.1 · September 7, 2026 · Companion to the product spec, the Day 0 PRD and the financial plan*

## 1. What Supabase actually did

The growth story investors know is "vibe coding made Supabase the default backend." The mechanics behind it are specific and copyable.

| What Supabase did | Evidence |
|---|---|
| Became the backend that AI app builders emit by default | Lovable, Bolt.new, Vercel's v0 and Figma Make build on Supabase projects owned by their users. Lovable alone has ~8M users and creates 100K+ apps a day; Bolt has ~5M. [1] |
| Shipped an official MCP server so coding agents could drive it | Manage projects, schema, queries, branches and logs from Cursor, Claude Code, Windsurf and Copilot, with OAuth. [3][4] |
| Built "Supabase for Platforms": a management API plus a remote MCP server so a third-party tool can provision a Supabase project for its user programmatically | Lovable, Bolt and Baidu's MeDo have created millions of projects this way. [1] |
| Published an agents page with copy-paste prompts for editors and integrations for LangChain, CrewAI, AutoGen | Model-agnostic; every editor that speaks MCP. [4] |
| Measured and reported agent share | By the June 2026 Series F, more than 60% of new database launches were initiated by an AI tool, and the company reported a sixfold year-over-year increase in databases. 40,000+ new databases a day. [2][5] |

The pattern: the human developer stopped being the only customer. The AI tool became a customer that provisions on the human's behalf, and Supabase built the two surfaces that customer needs, an MCP server for agents in the loop and a provisioning API for platforms out of it, then made the docs legible to models.

## 2. Why this fits QuerySolo better than it fit Supabase

Supabase had to bolt agent safety on after the fact. QuerySolo's core feature is already an agent guardrail:

- **The gauge is an `estimate` tool.** Before an agent runs anything it can learn the cost and time. No warehouse offers this to an agent today; the incumbents meter afterwards.
- **The cap is a budget primitive.** `QUERYSOLO_AGENT_CAP_USD` is a per-agent, per-day ceiling the worker enforces. An autonomous loop cannot spend past it.
- **Git is the audit trail.** Anything an agent saves becomes a dbt model with tests and a commit that names the agent. The review flow already exists; it is a PR.
- **Local by default is privacy by default.** Agent plus local model plus local project means nothing leaves the laptop. Supabase cannot say this.

And the timing: as Supabase-backed apps mature they need analytics, and neither Lovable nor Bolt ships a warehouse. An app builder's user with a growing Postgres and a question is QuerySolo's P3 persona with a data source already attached.

## 3. The four surfaces

### 3.1 `querysolo mcp` (Day 0)
A stdio MCP server over the same core as the CLI and app. Tools: `list_tables`, `describe`, `sample`, `estimate`, `query`, `burst` (with a required `cap_usd`), `import_file`, `save_question`, `lineage`, `publish`. Read tools on by default; write tools (`import_file`, `save_question`, `publish`, `burst`) opt-in per project in `querysolo.toml`. Every call is logged with the agent name, the verdict, the cost and the outcome. Ships with a one-line config for Claude Code, Cursor, Codex and Windsurf.

### 3.2 Model-legible docs (Day 1)
`llms.txt` and `llms-full.txt` at the root of the docs site. An `AGENTS.md` in every project that `querysolo init` creates, describing the tables, the gauge, the cap and the conventions, so any coding agent that opens the folder knows how to behave. A published Claude Code skill and Cursor rules file. Copy-paste prompts on the site, the way Supabase's agents page does it: "Turn this CSV into an Iceberg table, write three checks, save a question for revenue by month."

### 3.3 Remote MCP with OAuth (Day 2)
Team tier. A hosted MCP endpoint that speaks to the team catalog with the same role and credential-vending model humans get, so an agent in a hosted tool (not just a local editor) can use a team's tables. Per-agent identities and budgets in the team settings.

### 3.4 QuerySolo for Platforms (Day 2–3)
The Supabase-for-Platforms move. A management API and remote MCP that lets a third-party tool provision a lakehouse for its user: create the project, attach the user's bucket, set the cap, hand back credentials. Targets, in order: AI app builders whose users outgrow their app database and need analytics; AI notebook and BI tools that want a local execution layer; dbt's own AI tooling. The pitch to a builder is one sentence: "your user's app already has data; give them a warehouse on their laptop with one call, and you never host it."

## 4. Distribution: who provisions QuerySolo on the human's behalf

| Channel | What they get | What QuerySolo gets | Phase |
|---|---|---|---|
| Coding agents in editors (Claude Code, Cursor, Codex, Windsurf) | A data tool that answers "what's in this CSV" and "how much will this query cost" without leaving the editor | The MAU funnel; every agent session is a local install | Day 0–1 |
| AI app builders (Lovable, Bolt, v0, Figma Make, Base44) | An analytics layer for the apps they generate, without hosting a warehouse | Provisioned projects at the builders' scale; the "60% of launches by AI" curve | Day 2–3 |
| The dbt ecosystem (Fivetran + dbt, 100K+ data teams) | A local runtime for the workflow they already sell, with a gauge | The second-wave engineers and a likely acquirer's attention | Day 1–2 |
| Course and tutorial authors | A lakehouse students can run for free with an agent helping | The learner cohort and the "default tool" trigger in the bull case | Day 1 |

## 5. Metrics (instrumented from Day 0)

- Share of projects created by `querysolo init` invoked from an agent versus a terminal or the app (user-agent header on the CLI; MCP client name).
- Share of queries submitted through MCP versus the ask box versus raw SQL.
- Agent burst runs, caps hit, and refused calls. A healthy number of refusals is proof the cap works.
- Questions saved by agents that a human later edited (the "reviewed the PR" signal).
- Per-platform provisioned projects once Platforms ships.

Target to put on the seed deck: 30% of new projects agent-initiated by mid-2028, on the way to Supabase's 60%.

## 6. Safety posture, stated once

Read-only by default. Writes and bursts are opt-in per project and always capped. Prefix-scoped, short-lived storage credentials, the same ones humans get. No SQL text leaves the machine unless the user opted into history. Prompt injection through table contents is treated as a first-class threat: sample rows sent to a model are truncated and never executed, and an agent's write tools cannot change `querysolo.toml`.

## 7. What changes in the other documents

- **Deck:** a new slide after "One box" titled "Built for people. Agents need it more." with the Supabase agent share, the MCP config, and the audit log. The Supabase analogy's "how it spreads" row becomes "default lakehouse for agents and the tools that build apps."
- **Day 0 PRD:** F0.9, `querysolo mcp`, added with acceptance criteria. About a week of work because it wraps the existing core.
- **Financial plan:** no change to the base case; the bull case now has a named mechanism instead of a hope.
- **Landing page:** already done (version G, "For agents").

## Sources
[1] Supabase, "Introducing Supabase for Platforms," Dec 5 2025. https://supabase.com/blog/introducing-supabase-for-platforms
[2] Supabase, "Lovable Cloud + Supabase," Sep 29 2025 (40,000+ new databases a day; 4.5M developers). https://supabase.com/blog/lovable-cloud-launch
[3] Gumloop docs, Supabase MCP server capabilities and OAuth. https://docs.gumloop.com/nodes/mcp/supabase
[4] Supabase, "Supabase for Agents." https://supabase.com/solutions/agents
[5] AI Wiki, Supabase entry citing the June 2026 Series F: >60% of new database launches initiated by an AI tool; sixfold YoY increase in databases. https://aiwiki.ai/wiki/supabase
