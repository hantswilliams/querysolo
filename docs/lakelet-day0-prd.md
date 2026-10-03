# QuerySolo — Day 0 Product Requirements

*BRD + PRD · v0.1 · September 7, 2026 · Scope: initial release (private beta) and the pre-seed raise · Companion to lakelet-product-spec.md (phase map) and lakelet-v0-build-spec.md (stack) · Amended September 8, 2026 by `build-sessions/core-v0.5-plan.md` §8; where the two differ, the brief wins*

---

## Part A — Business requirements

### A1. Objective

Ship, by December 2026, a desktop app and CLI that ten design partners use weekly on real data, and that a founder can demonstrate end-to-end in four minutes. The release exists to produce three things the pre-seed needs: proof the gauge is trustworthy, proof the burst works with a hard cap, and ten people who will say so.

### A2. What the pre-seed round needs from this release

| Investor question | Day 0 must answer with |
|---|---|
| Does the gauge actually predict? | Estimate-vs-actual on partner workloads: 80% of queries within 2× on time, 1.5× on bytes; zero Green queries over 3 minutes. Shown as a chart, not claimed. |
| Does the burst work, and can the bill really not exceed the cap? | Ten consecutive Red → click → result runs on a partner's data, each under its cap, with the cap enforced by the worker at least once on a deliberately over-sized query. |
| Will non-developers use it? | Five people who do not write SQL each answered a question from their own CSV in the app, unassisted, in under ten minutes. Recorded. |
| Is this different from MotherDuck? | The data sits in the partner's own S3 bucket in Iceberg, and a Spark or Trino session reads it. One screenshot. |
| Will anyone pay? | Written statements from ≥5 partners that they would pay for a shared catalog, with the price they name. |

### A3. Users

**P1 — The solo data engineer.** 2–10 person company, one-person data team, currently paying $500–5K/month for a warehouse on under 1 TB. Writes SQL and dbt. Wants: to stop paying for idle compute, to keep working the way they already do. Fears: a toy that breaks under real data.

**P2 — The learner.** Building portfolio projects to get a lakehouse job; cannot afford warehouse credits. Wants: the real stack (Iceberg, dbt, DuckDB) on a laptop with nothing to configure. Fears: learning something nobody uses.

**P3 — The non-developer.** Founder, ops lead, product manager. Has a CSV or an export and a question. Wants: an answer today without asking the engineer. Fears: being wrong because the tool hid something.

P1 is the design partner; P2 is the launch audience; P3 is the test of the ask box. Day 0 must satisfy P1 completely and P3 well enough to record five successful sessions.

### A4. Design-partner program

- Ten partners, recruited from: the waitlist, DuckDB and dbt community members who describe warehouse bills under $5K/month, and MotherDuck users in the gap between the free tier and $250/month.
- Each partner: a 45-minute onboarding call, a shared Slack channel, weekly 20-minute check-in, free burst compute up to $50/month on QuerySolo's account, and their real bill in exchange.
- Partners agree to: a quote for the deck, a monthly usage export, and one recorded session.
- Success: ≥8 of 10 still active in week 8; ≥5 bursting weekly; ≥5 written willingness-to-pay statements.

### A5. Non-goals for Day 0

Team catalog, billing, scheduling, connectors, sharing, Windows desktop app, GCP/R2 backends, Lambda backend, warm pool, QuerySolo-hosted LLM, public repository. Each is placed in Day 1–3 in the product spec.

### A6. Constraints

- Three people, eight weeks of build after two weeks of spikes.
- Python core + Tauri shell per the v0 build spec; no Rust beyond the shell.
- Cloud spend during Day 0 under $1,500 total.
- No customer data at rest on any QuerySolo-controlled system.

---

## Part B — Product requirements

Each feature has: user stories, functional requirements (FR), acceptance criteria (AC), UX notes, error states, telemetry, and out-of-scope. Requirements use MUST / SHOULD / MAY.

---

### F0.1 — Bring data in: drop a file, get a table

**Stories**
- As P3, I drag a CSV onto the app and can ask questions about it immediately.
- As P1, I point QuerySolo at a folder of Parquet files and they become tables without an import step.
- As P1, I point QuerySolo at a Parquet prefix in my own bucket and it becomes an Iceberg table without copying a byte (brief D25).

**FR**
1. MUST accept drag-and-drop and file-picker input for `.csv`, `.tsv`, `.parquet`, `.json`/`.jsonl`, `.xlsx`.
2. MUST accept a folder; each file becomes a table, files with the same schema and a common prefix (e.g. `orders_2026_01.parquet`, `orders_2026_02.parquet`) SHOULD be offered as one table.
3. MUST create an Iceberg table in the project warehouse (`./warehouse` by default) registered in the local catalog, using DuckDB's readers and a single Iceberg commit.
4. MUST infer column types; MUST show the inferred schema before commit with a one-click "looks right" and per-column type override. The preview shows the inferred DuckDB type and the Iceberg type it becomes, with a note where the cast is lossy (brief D24, §3.7).
5. MUST show the gauge on the import itself (bytes, estimated time) and stream progress.
6. Re-dropping a file with the same name MUST offer Replace / Append / Create new.
7. SHOULD handle 2 GB CSV on a 16 GB laptop without exceeding memory (DuckDB streaming read → Parquet).

**AC**
- 200 MB CSV: table queryable in ≤ 10 s on a 2023 MacBook Pro. 2 GB CSV: ≤ 90 s, no crash, no swap thrash.
- Resulting table is readable by `pyiceberg` and by a second DuckDB process via `querysolo catalog serve`.
- Type inference: dates, timestamps, integers, decimals, booleans detected on the standard DuckDB sniffer test set; overrides persist.

**UX**
- Tables panel shows name, row count, size, and a small "local" or bucket icon. Import is a card in the same panel, not a modal.

**Errors**
- Unparseable file: show the first failing row and offer "treat as text." Never silently drop rows.
- Disk full: stop before commit; nothing half-written appears in the catalog.

**Telemetry (local always; shared only if opted in)**
- file type, size, rows, duration, inferred-type overrides count. Never file names or values.

---

### F0.2 — The ask box: English or SQL, show the work

**Stories**
- As P3, I type "revenue by month this year for the top five customers" and get a chart, and can see the SQL that made it.
- As P1, I type SQL and it just runs; I never see English-mode UI.
- As P3, when the SQL fails, QuerySolo tries once to fix it and tells me what it changed.

**FR**
1. One input. MUST auto-detect mode: input beginning with `select`, `with`, `create`, `insert`, `merge`, `explain`, `pragma`, `describe`, `show` (case-insensitive) is SQL; anything else is English. A visible toggle MUST allow override.
2. English MUST produce SQL streamed token-by-token into an editable editor beneath the input; the SQL MUST NOT execute until the gauge verdict appears and (for Green/Yellow) the user presses Run or Enter, or (Red) chooses local/burst.
3. Model context MUST include: catalog table names, columns and types; five sample rows per table (values truncated to 80 chars); the last three (question, SQL) pairs; DuckDB dialect notes; and the gauge verdict of the previous attempt if repairing.
4. Provider: MUST support Anthropic and OpenAI keys entered in Settings and stored in the OS keychain; MUST support a local Ollama endpoint; with no provider configured the English mode MUST be disabled with a one-line explanation and a link to Settings. Nothing MUST be sent to any network endpoint when no provider is configured.
5. On execution error, MUST offer one automatic repair (error text + failing SQL back to the model), show a diff of the change, and require a click to run the repaired SQL.
6. MUST show "sent to <provider>: schema of N tables, sample rows, your question" on first use, once.
7. SHOULD suggest three example questions for a newly imported table (generated from column names, not the model, so it works with no key).

**AC**
- Time to first SQL token ≤ 3 s on a typical connection; full SQL for a 3-table join in ≤ 8 s.
- On a fixed set of 30 P3-style questions against a sample dataset, ≥ 24 produce SQL that runs and returns the intended shape on the first or repaired attempt.
- SQL mode: no LLM call, no latency beyond the gauge.
- Keys are never written to disk in plaintext; verified by inspecting the config directory.

**UX**
- The editor is always visible and always editable; there is no "chat transcript" view. History is a list of previous (question, SQL) pairs in the left panel.
- Mode indicator is a small "SQL" / "Ask" chip on the input; it flips as you type.

**Errors**
- Provider error (401, 429, timeout): show the provider's message and keep the SQL editor usable. Never lose typed text.
- Model returns non-SQL: show it as a note, do not populate the editor, offer retry.

**Telemetry**
- mode, provider (name only), time-to-first-token, repair used (bool), run/not-run. Never the question or the SQL.

---

### F0.3 — The gauge: pre-flight verdict

**Stories**
- As anyone, before a query runs I know whether my laptop can handle it and roughly how long it will take.
- As P1, when it says Green I trust it, because it has never been badly wrong.
- As P3, when it says Red I understand why in one sentence.

**FR**
1. MUST compute within 150 ms of a 300 ms keystroke pause, for both SQL and generated SQL.
2. Inputs (architecture doc §4.1): `EXPLAIN (FORMAT JSON)`; Iceberg manifest stats with predicate and partition pruning; data locality and measured bandwidth (5-second probe at first use, cached 1 h, re-measured opportunistically); machine profile (RAM, `memory_limit`, cores, free disk, on battery); local history.
3. Outputs: bytes scanned, peak memory, wall time (local), wall time (burst), burst cost, verdict.
4. Verdict thresholds (initial, tunable in `querysolo.toml`):
   - Green: peak memory < 60% of `memory_limit` AND local wall < 60 s.
   - Yellow: spill expected OR 60 s ≤ local wall < 10 min.
   - Red: local wall ≥ 10 min OR remote scan > bandwidth × 10 min OR peak memory > free RAM + free disk.
5. MUST render one reasoning sentence naming the dominant factor (bandwidth, memory, or CPU) and the numbers behind it.
6. MUST record `(fingerprint, machine profile hash, estimate, actual)` for every execution in `.querysolo/history.db` with the schema in the brief §3.4, including the SQL text, which is stored locally and never shared (brief D7). The per-machine, per-operator-class correction after 20 recorded runs ships in session 10; trained models on shared data are Day 1 (brief M7).
7. MUST expose the history: a Gauge page listing recent runs with estimate vs actual and a scatter plot.
8. On battery, SHOULD add a note when local wall > 2 min ("~6 min on battery; plug in or burst").
9. Calibration sharing: first-run toggle, default on for the desktop app, default off for CLI; shares fingerprint hash, operator-class counts, estimate, actual, machine profile buckets. MUST NOT share SQL, table names, column names, or values.

**AC**
- On TPC-H SF10 and SF100 (local and S3) and on ≥ 3 partner workloads: ≥ 80% of queries within 2× on time; ≥ 80% within 1.5× on bytes; 0 Green queries exceeding 3 minutes.
- Verdict appears in ≤ 150 ms (p95) for queries against ≤ 20 tables with cached manifests; ≤ 800 ms when manifests must be fetched from S3.
- Correction factors reduce median absolute log-error by ≥ 20% after 50 runs on the same machine, measured on the partner set.

**UX**
- A single line under the input: a coloured dot, the verdict words ("Runs here", "Runs here, slowly", "Needs more machine"; brief D28), then "scans 2.1 GB · ~4 s" or the Red sentence with the burst offer. Hover/expand shows the three numbers and the plan summary.
- Colours: Green `1F8A5B`, Yellow `C98A12`, Red `D24B3A`, matching the landing page.

**Errors**
- Estimator failure MUST NOT block execution: show "couldn't estimate" in grey and let the user run locally; log the failure.

---

### F0.4 — Results, chart, save

**FR**
1. MUST stream results into a virtualised grid as Arrow batches; first 1,000 rows MUST render before the query completes.
2. MUST show row count, elapsed time, and (if burst) actual cost in the status line.
3. Auto-chart MUST appear when the result has exactly one date/category column and 1–3 numeric columns: line for dates, bar for categories. MUST be dismissible and MUST be swappable between line/bar/table.
4. Export MUST support CSV and Parquet; copy-as-Markdown SHOULD exist for P3.
5. "Save as question" MUST write a dbt model: `models/questions/<slug>.sql` plus a `schema.yml` entry with the title as description and two default checks, so it is committed (every save is a version, `versions-plan.md` G2 and G3, built September 12, 2026), human-readable and a valid dbt project from the first save; `last_run` lives in history, not in the file (brief D30, D16).
6. Saved questions MUST re-run with one click and show the gauge first.

**AC**
- 10M-row result scrolls without jank (60 fps on the reference laptop); memory bounded by the visible window plus a 10k-row buffer.
- Chart renders in ≤ 200 ms for 10k points.

**Out of scope**
- Chart customisation, pinned pages, dashboards.

---

### F0.5 — Burst: one click, hard cap

**Stories**
- As anyone, when the verdict is Red I click once, see the cap, watch it run, and get the result without configuring anything except my bucket.
- As P1, I can prove to my CFO that a burst cannot exceed the number I clicked.

**FR**
1. Prerequisites the app MUST walk through once: sign in (`querysolo login`), choose a burst region (defaults to the bucket's), connect a bucket (paste an S3 URI; QuerySolo shows the IAM policy to attach, scoped to that prefix).
2. Tables involved MUST be in a bucket; local-only tables MUST trigger "Publish first: orders is local-only (12 GB), ~9 min at your upload speed. Publish and burst?" with one click to do both.
3. Cap: MUST equal `ceil(estimated cost × 2)` to the next $0.10 below $1 and next $1 above; MUST be editable before the click; MUST be shown on the button ("Burst · ≤ $0.41").
4. Control plane MUST convert the cap to a wall-clock budget for the chosen worker size; the worker MUST kill DuckDB at the budget and return a partial-progress error with elapsed time, bytes read and cost so far.
5. Worker sizing: peak-memory estimate × 1.5 snapped to the Fargate ladder; MUST launch in the bucket's region.
6. Catalog lease (local-catalog users): the CLI/app MUST push involved table metadata to the control plane, which serves it to the worker; the worker commits back; the app replays the commit into the local catalog; the local catalog MUST refuse writes to leased tables for the lease duration and MUST show them as "leased" in the Tables panel.
7. Results: ≤ 50 MB MUST stream back as Arrow over HTTPS; larger MUST be written to `s3://<bucket>/_querysolo/results/<job_id>/` and registered as a temporary table; writes (`CREATE TABLE AS`, `INSERT`, `MERGE`, dbt) MUST commit directly to the target Iceberg tables.
8. Live status MUST show: state (starting / running / writing / done), elapsed time, running cost, bytes read so far.
9. Actual cost MUST be shown at completion and logged with the estimate.
10. Cancel MUST be available at all times and MUST stop billing within 10 s.
11. Security: single-use job token (JWT, TTL = job timeout) scoped to the job's tables; storage credentials vended per job, prefix-scoped, expiring with the job; workers have no inbound network; SQL text retained only for the job's duration.

**AC**
- Ten consecutive burst runs on a partner dataset complete under their caps; one deliberately over-cap query is killed by the worker within 5 s of the budget and returns a partial-progress error.
- Cold start to first byte read ≤ 75 s (p90) on Fargate; app shows a timer the whole time.
- Bill reconciliation: QuerySolo's logged actual cost matches AWS Cost Explorer for the account within 10% over the Day 0 period.
- Security review: token and credential scoping verified by attempting cross-table and post-expiry reads from a worker and confirming failure.

**UX**
- The Red line becomes a button. Clicking opens a small confirmation with the cap, the worker size, and the region; a second click starts it. No modal chains.

**Errors**
- Worker launch failure: retry once, then show the AWS error verbatim with a "run locally anyway" option.
- Cap hit: show partial-progress error with a "raise cap to $X and retry" button.
- Bucket permissions wrong: show which action failed (`ListObjects`, `GetObject`, `PutObject`) and the policy snippet to fix it.

**Telemetry**
- job id, region, worker size, estimate, cap, actual, wall time, bytes, outcome. Never SQL, never table names outside the control plane's job record (deleted at job end unless the user opts into history).

---

### F0.6 — CLI

**FR**
1. Commands: `querysolo init [dir]`, `querysolo sql "<q>" | -f file.sql`, `querysolo estimate "<q>"`, `querysolo run [dbt selectors] [--burst auto|never|all]`, `querysolo publish <table> --to s3://bucket/prefix`, `querysolo catalog serve [--port 8181]`, `querysolo catalog attach <rest-url>`, `querysolo login`, `querysolo burst status|cancel <job>`, `querysolo cost [--month]`, `querysolo gauge history`. Sequencing per the brief: core v0 ships `init import tables sql estimate catalog question gauge audit serve`; `querysolo ask` arrives in session 7 (M11); `run` in session 9; `publish`, `login`, `burst` and `cost` in session 8; `catalog attach` is Day 1 (D11).
2. `querysolo sql` MUST print the gauge line to stderr, then results to stdout as a table (TTY) or CSV/JSON (`--format`), so it pipes.
3. `querysolo run` MUST use dbt-duckdb, compile the project, estimate each model, print the DAG with verdicts, and honour `--burst auto` under `max_cost_per_run_usd` from `querysolo.toml` without prompting (for CI).
4. Exit codes: 0 success; 2 Red verdict refused (no burst permitted); 3 cap exceeded; 4 catalog conflict after retries. Core v0 ships 0, 1, 2 and 4; 3 arrives with burst (brief D23).
5. `querysolo.toml` per architecture doc §7.3, renamed.
6. `querysolo init` MUST write `.gitignore` (`warehouse/`, `.querysolo/`, `.DS_Store`) and a minimal `dbt_project.yml` when none exists (brief D14, D30).

**AC**
- All commands documented with `--help`; a 20-minute quickstart from `init` to a burst works on a clean macOS and Ubuntu machine.
- A GitHub Actions example runs `querysolo run --burst auto` with a $5 project cap.

---

### F0.7 — Local Iceberg REST catalog

**FR**
1. MUST implement the Iceberg REST spec subset DuckDB requires: config, list/create/drop namespaces, list/create/load/drop/rename tables, commit with requirements (optimistic concurrency), and credential vending stubs (local mode returns none).
2. MUST run embedded (in-process) by default and as a server via `querysolo catalog serve`. Embedded means a loopback HTTP server, uvicorn in a thread, in every process that opens a project; DuckDB's iceberg extension attaches to it over REST (brief D4).
3. Backed by SQLite in `./.querysolo/catalog.db`; the same code MUST run on Postgres (validated in a test, not shipped) so Day 2's team catalog is a config change.
4. `querysolo catalog attach` MUST work against Apache Polaris, Lakekeeper and Amazon S3 Tables REST endpoints for read and write. Deferred to Day 1 (brief D11, decision R2 of September 8, 2026).

**AC**
- Spark 3.5 and Trino read and write a QuerySolo-created table through `querysolo catalog serve` in a documented smoke test.
- Concurrent commits from two processes to the same table: one succeeds, the other retries and succeeds, no lost updates (test with 100 iterations).

---

### F0.8 — Desktop app shell

**FR**
1. Tauri 2 shell; Python core as a sidecar; localhost HTTP + Arrow IPC.
2. Launch to usable ≤ 1.5 s; sidecar readiness shown as a small status dot, not a splash screen.
3. Projects: open a folder; `querysolo.toml` created if missing; recent projects list.
4. Settings: model provider and key, bucket and region, calibration sharing toggle, `memory_limit`, threads.
5. Signed macOS DMG (notarised) and Linux AppImage; auto-update MAY be deferred to Day 1.
6. Keyboard: Cmd/Ctrl+Enter runs; Cmd/Ctrl+K focuses the ask box; Esc cancels a running query.

**AC**
- Fresh-machine install to first query ≤ 3 minutes with no terminal.
- App survives sidecar crash: shows "core restarted" and recovers state from disk.

---

### F0.9 — `querysolo mcp`: the agent surface

**Stories**
- As a developer using Claude Code, Cursor or Codex, I add one line of config and my agent can list my tables, estimate a query, run it, and burst with a cap I set.
- As a founder, I let an agent explore a CSV I dropped, and I can see afterwards exactly what it ran and what it cost.

**FR**
1. `querysolo mcp [--project <dir>]` MUST start a stdio MCP server over the same core as the CLI and app.
2. Tools: `list_tables`, `describe(table)`, `sample(table, n≤5)`, `estimate(sql)`, `query(sql)`, `burst(sql, cap_usd)`, `import_file(path)`, `save_question(title, sql)`, `lineage(table)`, `publish(table, uri)`. In Day 0 `lineage` is table level, from the dbt manifest and Iceberg snapshot history (brief D32); column level is Day 3. *Met September 16, 2026 at table level: `querysolo lineage`, `GET /api/lineage/{name}` and the app's lines (`versions-plan.md` step 4); the MCP tool is session 5's.*
3. Read tools MUST be enabled by default. `burst`, `import_file`, `save_question`, `publish` MUST be off until enabled per project in `querysolo.toml` (`[agents] allow = [...]`).
4. `burst` MUST require `cap_usd`; the control plane MUST refuse a burst without one. `QUERYSOLO_AGENT_CAP_USD` MUST set a per-agent, per-day ceiling; calls past it MUST return a refusal with the remaining budget, not an error.
5. Every call MUST be logged locally with agent/client name, tool, verdict, cost, duration and outcome; `querysolo agents log` MUST print it.
6. `save_question` from an agent MUST commit with a message naming the agent (`agent:claude · save question: …`).
7. `querysolo init` MUST write an `AGENTS.md` describing the project's tables, the gauge, the cap and conventions.
8. An agent MUST NOT be able to modify `querysolo.toml` or `AGENTS.md` through any tool.
9. Sample rows returned to a model MUST be truncated to 80 characters per value and MUST never be executed as SQL.

**AC**
- One-line configs for Claude Code, Cursor, Codex and Windsurf documented and tested; each can complete "drop this CSV, write three checks, save revenue by month" unassisted.
- A deliberately over-budget agent loop is refused at the cap within one call; the refusal names the remaining budget.
- Audit log reconciles with the control plane's metering for every burst.
- Ships in week 7 alongside burst; roughly one engineer-week since it wraps existing calls.

**Telemetry**
- MCP client name, tool, verdict, cost, refused (bool). Never SQL.

---

## Part C — Cross-cutting requirements

### C1. Performance budgets (reference machine: 2023 MacBook Pro, 16 GB, 190 Mbps)

| Interaction | Budget |
|---|---|
| Launch to usable | ≤ 1.5 s |
| Gauge after keystroke pause | ≤ 150 ms p95 (cached manifests) |
| Green query end-to-end overhead beyond DuckDB | ≤ 50 ms |
| English → first SQL token | ≤ 3 s |
| 200 MB CSV import | ≤ 10 s |
| Burst cold start to first read | ≤ 75 s p90 |

### C2. Privacy and security
- No customer data at rest on QuerySolo systems. Control plane stores job specs, metrics, and (during a job) leased table metadata.
- Keys in OS keychain. Calibration sharing opt-in per F0.3.9. A `PRIVACY.md` in the app describes every byte that leaves the machine. The local API requires a per-launch bearer token; the catalog endpoints are open on loopback in local mode (brief D22).

### C3. Accessibility and platforms
- macOS 13+ and Ubuntu 22.04+ desktop; Windows CLI only. Keyboard-navigable; visible focus; no colour-only meaning (verdict word always accompanies the dot).

### C4. Instrumentation for the fundraise
Tracked from the first partner install: weekly active partners, queries per partner per week, Green/Yellow/Red mix, estimate-vs-actual distribution, burst runs and caps, cap hits, publish events, ask-box success rate. A one-page "QuerySolo numbers" export updates the investor memo monthly.

---

## Part D — Delivery

### D1. Milestones

| Week | Deliverable | Owner |
|---|---|---|
| 1–2 | Spikes pass; Tauri shell + sidecar + grid scaffold | Founder / BE / FE |
| 3 | F0.1 import, F0.7 catalog embedded, F0.6 `init/sql/estimate` | BE |
| 4 | F0.3 gauge v1 with history; F0.4 grid + chart | BE / FE |
| 5 | F0.2 ask box with Anthropic/OpenAI/Ollama; F0.8 settings | FE / BE |
| 6 | F0.5 control plane + Fargate worker + cap; `publish` | Founder / BE |
| 7 | Catalog lease; results back; `run` with dbt DAG verdicts; F0.9 `querysolo mcp` | BE / FE |
| 8 | Signed installers; docs; partner onboarding; instrumentation export | All |
| 9–12 | Partner program: weekly calibration review, fixes, recorded P3 sessions, deck evidence | All |

### D2. The four-minute demo (scripted)
1. Open QuerySolo in an empty folder. Drop `orders.csv` (400 MB). Table appears; schema confirmed. *(30 s)*
2. Ask: "monthly revenue this year, top five customers." SQL streams in. Gauge: Green, 0.4 GB, ~2 s. Run. Chart. *(45 s)*
3. Point at the demo bucket, QuerySolo-owned and prepared with `tables attach` the way a partner's would be (brief D27, decision R5). Tables panel shows `events` (48 GB). Ask: "daily active users by country, last 90 days." Gauge: Red, one sentence, "Burst ~1.5 min, ≤ $0.41." *(30 s)*
4. Click. Confirm. Timer and running cost. Result streams back. Actual: $0.19. *(1.5 min)*
5. Gauge page: estimate vs actual scatter for the partner's last 200 runs. *(30 s)*
6. Terminal: `spark-sql` reads the same table through `querysolo catalog serve`. *(15 s)*

### D3. Risks specific to Day 0

| Risk | Signal | Response |
|---|---|---|
| DuckDB-Iceberg refuses `file://` | Step 1 of the brief | A minimal S3 subset inside the sidecar over local disk, if ever needed; MinIO is no longer maintained (brief D16) |
| Estimator under-calls Green | Spike 2 / partner data | Tighten Green thresholds; prefer Yellow; never ship a Green that misses |
| Fargate cold start makes Red feel slow | Spike 3 | Show the timer honestly; pull Lambda backend into Day 0 only if partners abandon bursts |
| Ask box quality varies by provider | 30-question test set | Ship provider-specific prompt variants; Anthropic as documented default |
| Partners churn in weeks 3–5 | Weekly actives | Founder does the check-ins personally; fix the top issue within the week |

### D4. Open decisions to close this week
1. Default state of calibration sharing on first run (this doc: on, with the toggle visible).
2. Whether Windows CLI is tested in Day 0 or deferred.
3. Trademark search result for "QuerySolo" before any partner sees the name in writing.
