# QuerySolo — Product specification by phase

*Draft v0.1 · September 7, 2026 · Working product name: QuerySolo. Parent entity: TBD (generic C-corp). Supersedes "Burrow" in all earlier docs. · Amended September 8, 2026 by `build-sessions/core-v0.5-plan.md` §8; where the two differ, the brief wins*

This document says what QuerySolo is on Day 0, Day 1, Day 2 and Day 3, what each phase must prove, and which fundraising round each phase earns. Specs are written as user stories with acceptance criteria so an engineer can start from them and an investor can check them. Anything not listed for a phase is out of scope for that phase, on purpose.

---

## 0. Product principles (apply to every phase)

1. **Local by default.** Nothing leaves the laptop without a number on the screen and a click.
2. **Show the work.** English becomes SQL you can see. A verdict shows its reasoning in one line. A burst shows its cap before it starts and its actual cost after.
3. **Open at every layer of the data path.** Parquet, Iceberg, Iceberg REST, dbt. Leaving QuerySolo is pointing another engine at the bucket.
4. **One surface, two users.** Developers and non-developers use the same app; the app never asks which one you are.
5. **Nothing waits without a number.** Every spinner shows elapsed time and, where known, remaining time or cost.

---

## 1. The phase map

| | Day 0 | Day 1 | Day 2 | Day 3 |
|---|---|---|---|---|
| **Name** | Prove it works | Public open-source launch | Team product | Company product |
| **When** | Sep–Dec 2026 | Jan–Jun 2027 | Jul 2027 – Jun 2028 | Jul 2028 – Dec 2029 |
| **Users** | Founder + 10 design partners | Solo engineers, learners | 2–10 person data teams | Regulated / larger teams |
| **What ships** | Desktop app + CLI, gauge, local Iceberg, ask box, burst on AWS | Same, polished, installable in one command, public repo | Hosted team catalog, scheduling, billing, dbt DAG split runs, GCP/R2 | Self-hosted control plane, SSO, audit, SOC 2, connectors |
| **Revenue** | $0 | $0 (design partners burst free) | Seats + burst; ~$49K → $326K ARR | Self-hosted contracts; ~$1.35M ARR |
| **Round it earns** | **Pre-seed** ($1.5M) is raised *on* Day 0 | Pre-seed funds Day 1 | **Seed** (~$4M) is raised at the end of Day 2 | **Series A** is raised at the end of Day 3 |
| **Gate to next** | Spikes pass; 10 partners run real workloads | 2,000 MAU; 30 teams waitlisted with a real bill | 200 paying teams; NRR > 100%; one external curriculum defaults to QuerySolo | $1–3M ARR, 150%+ growth |

The rounds and the phases are the same thing viewed from two sides: a round buys the next phase, and a phase produces the evidence for the next round. The numbers come from the financial plan and from Carta's 2026 medians (pre-seed ~$1M, seed $4.1M at $24M post, Series A on $1–3M ARR).

---

## 2. Day 0 — Prove it works (Sep–Dec 2026)

**Purpose.** Turn the thesis into a thing a founder can demo in four minutes and ten design partners can use for a month. Pre-seed investors see this phase, not the next one, so it has to be real rather than polished.

**Team.** Founder + 2 engineers (backend/data, frontend). Eight-week plan in the v0 build spec.

### 2.1 Spikes (weeks 1–2) — not features, but they gate everything

| Spike | Pass condition |
|---|---|
| Local Iceberg writes through QuerySolo's own REST catalog (SQLite) to `file://` and `s3://` | `CREATE TABLE`, `INSERT`, `MERGE INTO` succeed from DuckDB 1.5.x on both; if `file://` fails, the local S3 shim works instead |
| Estimator accuracy on TPC-H SF10 and SF100, local and from S3 | 80% of queries within 2× on time and 1.5× on bytes; no Green query over 3 minutes |
| One Fargate worker against a 10 GB and a 100 GB Iceberg scan | Cold start, wall time and actual cost recorded; cost for the 100 GB scan under $1 |

### 2.2 Feature specs

**F0.1 — Open a folder or drop a file, get a table.**
*As anyone,* I drag a CSV, Parquet, Excel or JSON file onto QuerySolo and it becomes a queryable table without a dialog.
- Accept: file appears in the Tables panel within 10 s for files up to 2 GB; table is an Iceberg table in `./warehouse`; column types are inferred; a one-line summary shows rows, size and inferred types; a second drop of the same file offers "replace" or "append."
- Non-goals: connectors, scheduled imports, schema editing.

**F0.2 — The ask box.**
*As a non-developer,* I type a question in English and see the SQL it produced, then the result.
*As a developer,* I type SQL and get the result.
- Accept: input auto-detects SQL vs English (starts with a SQL keyword ⇒ SQL); English produces streaming SQL into an editable editor; the generated SQL runs only after the gauge verdict; the model sees table names, column names and types, five sample rows per table, and the previous three queries; the user supplies an Anthropic or OpenAI key, or points at a local Ollama model; no schema or data is sent anywhere unless a key is configured.
- Accept: on a SQL error, QuerySolo shows the error and offers one automatic repair attempt with the error in context.
- Non-goals: multi-turn chat memory beyond three queries; QuerySolo-hosted model.

**F0.3 — The gauge (pre-flight verdict).**
*As anyone,* before a query runs I see whether my machine can handle it.
- Accept: a verdict line appears within 150 ms of a keystroke pause: Green / Yellow / Red, bytes scanned, estimated time, and for Red the burst estimate and cap. Verdict reasoning is one sentence ("Red: scans 48 GB from s3://…, ~34 min at your 190 Mbps. Burst: ~1.5 min, ≤ $0.41."). Thresholds from the architecture doc §4.3.
- Accept: every execution records `(fingerprint, machine profile, estimate, actual)` locally; a per-machine correction factor is applied after 20 runs.
- Accept: a visible toggle on first run governs whether anonymised calibration pairs are shared with QuerySolo; SQL text is never shared.

**F0.4 — Results and chart.**
- Accept: results stream into a virtualised grid as Arrow batches; the first 1,000 rows render before the query completes; an auto-chart appears when the result has one date/category column and one to three numeric columns; export to CSV and Parquet; "Save as question" stores the SQL with a title in `./questions/`.

**F0.5 — Burst.**
*As anyone,* when the verdict is Red, I click once and the query runs in the cloud with a cost cap I saw first.
- Accept: the button shows the cap (estimate × 2, rounded up); the control plane launches a Fargate task in the bucket's region sized from the estimate; the worker enforces the cap as a wall-clock budget and returns a partial-progress error rather than exceeding it; results under 50 MB stream back inline, larger results land in `s3://<bucket>/_querysolo/results/<job>/` and register as a temporary table; a live timer and running cost are visible throughout; the actual cost appears at the end and is logged.
- Accept: tables that are local-only trigger the "publish first" prompt with an upload time estimate.
- Non-goals: Lambda backend, warm pool, GCP, spot.

**F0.6 — CLI.**
- `querysolo init`, `querysolo sql`, `querysolo estimate`, `querysolo run` (dbt via dbt-duckdb), `querysolo publish`, `querysolo login`, `querysolo burst status|cancel`, `querysolo cost`. Same core as the app; `querysolo.toml` as in the architecture doc §7.3. Works in CI with `--burst auto` under a per-project cap.

**F0.7 — Local catalog.**
- QuerySolo ships its own Iceberg REST catalog on SQLite inside the binary; `querysolo catalog serve` exposes it so Spark, Trino or DuckDB elsewhere can read QuerySolo tables; `querysolo catalog attach` points at Polaris, Lakekeeper or S3 Tables instead.

### 2.3 Day 0 exit criteria (what the pre-seed deck shows)

- Ten design partners running real dbt projects, at least five bursting weekly.
- Estimate-vs-actual within target on partner workloads, not just TPC-H.
- The four-minute demo: drop a file, ask a question, see Green, change the question, see Red, click, watch the cost, get the answer.
- Signed installers for macOS and Linux; Windows on the CLI only.

---

## 3. Day 1 — Public open-source launch (Jan–Jun 2027)

**Purpose.** Turn Day 0 into something 2,000 people install without talking to us. Pre-seed money funds this phase; the seed will be raised on what it produces.

**Team.** Founder + 3 engineers (add one), then a developer-relations hire mid-phase.

### 3.1 Feature specs

**F1.1 — One-command install.** `brew install querysolo`, `pipx install querysolo`, signed DMG/MSI with auto-update. Windows desktop app ships here.

**F1.2 — Public repository under Apache 2.0.** CLI, desktop app, local catalog, estimator. DCO sign-off. Issue templates that ask for the gauge line and the machine profile. A `CALIBRATION.md` that explains exactly what is and is not collected.

**F1.3 — The bill calculator on the landing page.** Paste last month's warehouse bill (or enter compute hours, storage, team size); get the QuerySolo version with the same structure as the deck's receipt. Every submission with a real number is a lead.

**F1.4 — dbt DAG view.** Compile the project, estimate each model, colour the DAG by verdict, show critical-path totals. Run locally, burst all, or split (Red models on workers, Green locally) when tables are reachable from the cloud.

**F1.5 — Gauge calibration v2.** Per-operator-class correction factors trained on the shared calibration pool; shipped as a model file the app downloads; a user can inspect their own estimate-vs-actual history.

**F1.6 — Lambda burst backend.** For jobs under 10 GB memory and 15 minutes, sub-second start. This is what makes Red feel instant for the common case.

**F1.7 — Saved questions become a page.** A saved question can be pinned; pinned questions render as a one-page grid with charts. This is the entire dashboard product in Day 1 and it should stay that simple.

**F1.8 — Import from DuckLake and native DuckDB.** `querysolo import --from ducklake|duckdb`. Cheap, and it removes the "but I already have tables" objection.

### 3.2 Day 1 exit criteria

- 2,000 monthly active users, 300+ GitHub stars, 30 teams on the waitlist with a real bill attached.
- One tutorial, course or book chapter that uses QuerySolo as its lakehouse.
- Design partners still active; at least five say in writing they would pay for a shared catalog.

---

## 4. Day 2 — Team product (Jul 2027 – Jun 2028)

**Purpose.** Turn free solo users into paying teams. Revenue starts here, and the seed is raised at the end of this phase on ~$150–300K ARR plus adoption.

**Team.** 5–6 people: founder, 4 engineers, DevRel.

### 4.1 Feature specs

**F2.1 — Team catalog (hosted).** Same Iceberg REST catalog code on Postgres, multi-tenant. `querysolo team create` → invite by email → every member's QuerySolo sees the same tables. Optimistic-concurrency commits; conflicts retried client-side. Credential vending: short-lived, prefix-scoped STS credentials on AWS; equivalents on GCS and R2. QuerySolo never stores data files.
- Accept: a second laptop sees a table within 5 s of the first laptop's commit; two laptops writing the same table both succeed or one retries cleanly; a revoked member loses access within 60 s.

**F2.2 — Billing.** Stripe. $24 per seat per month; burst at cost + 15% with per-run caps and a per-month team cap; invoice shows every burst run with its estimate and actual. Free tier stays local-only and unlimited.

**F2.3 — Scheduling and ops.** Scheduled dbt runs with `--burst auto`; compaction; snapshot expiry; freshness checks; a Slack/email alert when a test fails or a schedule misses.

**F2.4 — Split execution for dbt.** F1.4's split mode goes from "works" to "default": QuerySolo chooses per model, respects dependencies through the shared catalog, and reports the run's total cost and time against the all-local and all-burst alternatives.

**F2.5 — QuerySolo-hosted ask box.** Team tier includes a hosted model with a daily budget, so non-developers on a team never configure a key. Schema and sample rows are sent; SQL and results are not retained.

**F2.6 — Sharing.** A pinned page can be shared to teammates by link within the team. Not public.

**F2.7 — GCP (Cloud Run) and R2 (Fly Machines) burst backends.** The multi-cloud hedge, and a real answer when AWS ships its own serverless DuckDB.

**F2.8 — Warm pool.** Team tier keeps a small warm pool for sub-5-second bursts; priced into the seat.

### 4.2 Day 2 exit criteria (the seed deck)

- 200 paying teams, net revenue retention over 100% on the first cohort, ~$300K ARR run rate.
- 40,000 MAU; a second external curriculum; a named list of 20 MotherDuck-gap teams that converted.
- Estimate accuracy on team workloads within target for two consecutive quarters.
- Seed closed: ~$4M.

---

## 5. Day 3 — Company product (Jul 2028 – Dec 2029)

**Purpose.** Make QuerySolo buyable by a company, not just a team, without hiring a sales force before the product sells itself. Series A is raised at the end on $1–3M ARR.

**Team.** 8–10 people: add designer, second DevRel, one customer-success/sales hire, one security/infra engineer.

### 5.1 Feature specs

**F3.1 — Self-hosted control plane and catalog.** The hosted stack packaged for a customer's own AWS/GCP account (Terraform + one container image set). QuerySolo-managed upgrades. From $25K per year.

**F3.2 — SSO, roles and audit.** SAML/OIDC; table- and namespace-level roles; an audit log of every commit, burst and credential vend; export to the customer's SIEM.

**F3.3 — SOC 2 Type II.** Starts at the beginning of Day 3; complete before the first self-hosted renewal.

**F3.4 — Connectors.** Postgres, MySQL, Stripe, Google Sheets, S3 buckets of files, via an embedded open-source ingestion library rather than a QuerySolo-built connector framework. Incremental loads into Iceberg with the gauge shown on the load itself.

**F3.5 — Lineage.** From Iceberg commit history and dbt manifests: column-level where dbt provides it, table-level otherwise. Rendered in the catalog browser; exportable as OpenLineage. Table-level lineage from the dbt manifest and snapshot history arrives in Day 0 (brief D32); this item is the column-level and OpenLineage extension.

**F3.6 — Public pages.** A pinned page can be published read-only outside the team, with a QuerySolo-hosted cache so viewers never hit the customer's bucket.

**F3.7 — Rust core.** The estimator and catalog hot paths ported from Python; the sidecar becomes a static library inside the Tauri shell. "One binary" becomes literally true.

### 5.2 Day 3 exit criteria (the Series A deck)

- $1–3M ARR growing 150%+ year over year; five or more self-hosted customers at $25K+.
- 120,000+ MAU; 750+ paying teams.
- Gauge accuracy published as a benchmark others cite.
- A dbt adapter or an AI coding tool that defaults to QuerySolo for lakehouse projects (the bull-case trigger).

---

## 6. Fundraising alignment

| Round | Raised on | Amount | Buys | What the deck has to show |
|---|---|---|---|---|
| **Pre-seed** | Day 0 (now – Dec 2026) | $1.5M SAFE, ~$8M post cap | Day 1 and the first five months of Day 2: 3 → 5 people, cloud credits, OSS launch | The four-minute demo; ten design partners with real workloads; spikes passed; the Supabase analogy; the exit comps. Revenue: $0 and say so. |
| **Seed** | End of Day 2 (H1 2028) | ~$4M priced or SAFE, ~$20–24M post | Day 3: 5 → 10 people, SOC 2, self-hosted build, second cloud | 200 paying teams, NRR > 100%, ~$300K ARR, 40K MAU, two external curricula, calibration moat with a number on it. Traction story, not a revenue story. |
| **Series A** | End of Day 3 (2030) | Market: ~$19M median | Sales and success org, enterprise features, international | $1–3M ARR, 150%+ growth, five self-hosted logos, published gauge benchmark, the "default tool" partner. |

**Bridge risk.** Base-case cash runs out around month 17 (May 2028). If Day 2 slips a quarter, the seed conversation opens on ~$150K ARR rather than $300K. The evidence that carries the round in that case is MAU, design-partner retention and calibration accuracy, so those three numbers get instrumented from Day 0 and appear on every monthly investor update.

---

## 7. What is explicitly not on this roadmap

- A proprietary table format or catalog protocol.
- A QuerySolo notebook, BI tool or chart builder beyond pinned pages.
- A sales team before Day 3.
- Streaming ingestion or Kafka integration.
- A QuerySolo-hosted data lake. Data stays in the customer's bucket in every phase.

---

## 8. Open decisions

1. Default LLM behaviour in the free tier when no key is configured: disabled with a one-line explanation, or a QuerySolo-hosted trial with a daily cap.
2. Whether Windows gets the desktop app in Day 0 or Day 1 (this doc says Day 1).
3. Whether the warm pool (F2.8) is Team-only or also offered as a paid add-on for solo users.
4. Parent-entity name and the trademark filing for "QuerySolo" (US + EU, software and SaaS classes) before the Day 1 landing page.
