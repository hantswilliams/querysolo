# QuerySolo — v0 build spec

*Draft v0.1 · September 7, 2026 · Companion to lakelet-architecture.md and the pitch deck · Amended September 8, 2026 by `build-sessions/core-v0.5-plan.md` §8; where the two differ, the brief wins*

Two constraints drive every choice here: **speed to build** (a demoable v0 in eight weeks with three people) and **speed of the product** (the thing has to feel instant, because "faster than your warehouse" is the pitch). Where those pull against long-term architecture, v0 takes the fast path and the doc says what gets replaced later.

---

## 1. Who v0 is for

Two users share one app:

- **The developer** writes SQL and dbt, wants the gauge inline, uses the CLI in CI.
- **The non-developer** (founder, ops lead, analyst-adjacent PM) has a CSV, a Postgres export or a Stripe dump and a question. They will never type `SELECT`.

The mistake would be two products. The design that serves both is the one that made AI chat tools land with everyone: **a text box that accepts anything, and shows its work.** Type English, get SQL you can see and edit. Type SQL, get results. Either way the gauge runs first. The developer ignores the English; the non-developer ignores the SQL. Same surface.

This is closer to "Cursor for data" than "ChatGPT for data": the conversation is on the left, but the artifact it produces (query, result, chart) is always on the right, always editable, never hidden behind a chat bubble.

## 2. The v0 surface

```
┌──────────────────────────────────────────────────────────────────┐
│ ● QuerySolo           acme-analytics ▾            [Team: not set up] │
├───────────────┬──────────────────────────────────────────────────┤
│ Tables        │  Ask or write SQL                                 │
│  orders  38GB │  ┌──────────────────────────────────────────────┐ │
│  customers    │  │ revenue by month for 2026, top 5 customers   │ │
│  stripe_raw   │  └──────────────────────────────────────────────┘ │
│  + drop files │                                                   │
│               │  ● Runs here · scans 2.1 GB · ~4 s                │
│ Recent        │                                                   │
│  churn by …   │  select date_trunc('month', order_date) …   [edit]│
│  top custom…  │                                                   │
│               │  ┌── result ─────────────────────┬── chart ─────┐ │
│               │  │ month     customer   revenue  │   ▂▃▅▆▇▇█    │ │
│               │  │ 2026-01   Acme       84,210   │              │ │
│               │  └───────────────────────────────┴──────────────┘ │
│               │  [Save as question]  [Export]  [Schedule]          │
└───────────────┴──────────────────────────────────────────────────┘
```

What's in v0:

| Feature | Dev | Non-dev | Notes |
|---|---|---|---|
| Drag a CSV / Parquet / Excel onto the window → Iceberg table | ✓ | ✓ | This is the non-developer's `querysolo init`. Zero setup. |
| Ask box: English → SQL (shown, editable) or raw SQL | ✓ | ✓ | LLM sees the catalog schema, sample rows, and the gauge's verdict; user's own API key or a local model. |
| The gauge, inline, on every run | ✓ | ✓ | One line: verdict, bytes, time, burst cost if Red. |
| Results grid + auto chart | ✓ | ✓ | DuckDB → Arrow → grid; chart picked by column types. |
| Saved questions | ✓ | ✓ | A saved question is a SQL file with a title. That is the whole "dashboard" story in v0. |
| dbt project view with DAG coloured by verdict | ✓ | – | Uses the project's existing dbt files; QuerySolo does not invent a new modelling layer. |
| CLI: `init / sql / estimate / run / publish` | ✓ | – | Same core, no GUI. |
| Burst (Red → one click → cloud worker → result back) | ✓ | ✓ | Cost cap shown before the click, enforced by the worker. |

What's deliberately **not** in v0: connectors (Postgres, Stripe, etc.), scheduling, sharing, team catalog, permissions, a chart builder. Each is a phase-3 item in the financial plan.

## 3. Stack, chosen for speed to build

| Layer | v0 choice | Why | What replaces it later |
|---|---|---|---|
| Engine | **DuckDB 1.5.x** embedded, `iceberg` + `httpfs` extensions | Non-negotiable. It is the speed. | Nothing. Track 2.0 (server mode, Quack) for burst workers. |
| Core / data layer | **Python** (duckdb, pyiceberg, boto3, FastAPI) packaged as a sidecar binary | Fastest to write. pyiceberg reads manifests for the estimator; dbt-duckdb adapter exists today. Three weeks in Python is three months in Rust. | Rust port of hot paths (estimator, catalog) once the shape is stable. DuckDB does the heavy lifting in C++ either way, so Python is not the bottleneck. |
| Local catalog | **Own Iceberg REST catalog**, FastAPI + SQLite, ~1,500 lines | DuckDB-Iceberg writes need a REST catalog; the spec surface needed (namespaces, tables, load, commit, credential vending) is small. Owning it is the point (see §6). | Same code on Postgres becomes the hosted team catalog. |
| Desktop shell | **Tauri 2** (Rust shell, web frontend) with the Python core as a sidecar | A small shell, but the Python sidecar ships pyarrow, so the installer lands under 200 MB rather than 10–20; measured in session 10. Native feel; sidecar support is first-class. | Nothing; add auto-update. |
| Frontend | **React + TypeScript**, TanStack Table for the grid, Vega-Lite for charts, Monaco for the SQL editor | All three are proven, all free, none need design work to look good. | Nothing. |
| Frontend ↔ core | HTTP + Arrow IPC on localhost | Same API the future web app and team catalog will use; one frontend codebase for desktop and browser. | Nothing. |
| dbt | **dbt-core + dbt-duckdb (Python)** | Works today; QuerySolo wraps `compile` and `run`, injects the gauge per model. | dbt Core v2 Rust runtime when its Python interop settles. |
| English → SQL | **BYO API key** (Anthropic / OpenAI) or **Ollama** local; prompts and schema-context assembly are QuerySolo's | Nobody wants another AI subscription; privacy-sensitive users want local. QuerySolo's value is the context it assembles, not the model. | Hosted option in the Team tier. |
| Burst backend | **AWS Fargate**, us-east-1, one container image (DuckDB + extensions + 200-line agent) | Simplest thing that works; matches the architecture doc's economics. | Lambda for sub-10 GB jobs (sub-second start), warm pool for Team tier, Cloud Run / Fly for GCP and R2. |
| Control plane | **One FastAPI service + Postgres** on Fly.io or Railway | Jobs, auth, metering, cap → budget conversion. Tiny at v0. | Stays; grows a queue and a billing integration. |
| Auth / billing | Clerk or WorkOS + Stripe | Don't build these. | Nothing. |
| Distribution | `brew install querysolo`, `pipx install querysolo`, signed DMG / MSI | Three install paths, one core. | Nothing. |

**The "one binary" claim in the deck** survives: the user gets one installer and one `querysolo` command. Internally it is a Tauri shell plus a Python sidecar until the Rust port. Nobody buying the product cares about that; the deck does not need to change.

## 4. Speed of the product: what "instant" requires

The pitch collapses if the app ever feels like a warehouse UI. Concrete budgets:

| Interaction | Budget | How |
|---|---|---|
| App launch to usable | < 1.5 s | Tauri shell paints immediately; sidecar starts in the background; catalog loads from SQLite. |
| Gauge after a keystroke pause | < 150 ms | `EXPLAIN (FORMAT JSON)` on a local DuckDB is milliseconds; manifest stats are cached per table snapshot; bandwidth probe cached for an hour. |
| Green query on local data | as fast as DuckDB | Results stream to the grid as Arrow batches; first 1,000 rows render before the query finishes. |
| English → SQL | < 3 s to first token | Stream the model's output straight into the editor so the user watches SQL appear. Schema context is precomputed and cached, never rebuilt per request. |
| Drop a 2 GB CSV | table appears in < 10 s, queryable immediately | DuckDB `read_csv_auto` → Parquet → Iceberg commit. Show the gauge on the import itself. |
| Burst, Fargate | 30–60 s cold start + run | Show a live timer and the running cost; the honest version of "not instant." Lambda backend is the fix and is the first post-v0 item. |

The rule: **nothing blocks the UI and nothing hides behind a spinner without a number on it.** The gauge is a promise about time; the app has to keep it everywhere.

## 5. Eight-week plan, three people

Founder (product, catalog, burst), one data/backend engineer (Python core, estimator, dbt), one frontend engineer (Tauri, React, the ask box).

| Weeks | Ship | Gate |
|---|---|---|
| 1–2 | Spikes from the architecture doc: local Iceberg writes through a minimal REST catalog to `file://` and `s3://`; estimator vs actual on TPC-H SF10/100; one Fargate job with real numbers. Frontend engineer scaffolds Tauri + sidecar + grid in parallel. | Spikes pass or the plan changes now. |
| 3–4 | Desktop app: drop files, tables panel, SQL editor, gauge, results + chart. CLI `init / sql / estimate`. | Founder uses it daily on a real dataset. |
| 5 | Ask box: English → SQL with BYO key, streaming into the editor. dbt DAG view. | Five non-developers can answer a question from a CSV unassisted. |
| 6–7 | Burst: control plane, Fargate worker, cap enforcement, result streaming back, `publish` to S3. | Red → click → result, with the bill under the cap, ten times in a row. |
| 8 | Signed installers, `brew` tap, landing page wired to the real gauge, private beta to the waitlist. | Phase 1 gate in the financial plan (2,000 MAU) is now the goal. |

Deferred on purpose: team catalog on Postgres (needs paying users to design against), Lambda backend, connectors, scheduling, sharing.

## 6. Defensibility: what is actually ours

Be blunt about it: DuckDB, Iceberg and dbt are open, and any competent team can assemble them. If QuerySolo's value were the assembly, it would have none. The defensible parts are the things that accumulate or that others cannot easily copy:

1. **The calibration data.** Every run records `(query fingerprint, machine profile, estimate, actual)`. After a few thousand users that dataset makes QuerySolo's gauge more accurate than anything a newcomer can ship, and it improves with every run. This is the compounding asset; it is also the reason to keep the gauge free, because free is how the data arrives. Keep the raw dataset and the trained correction models closed; keep the estimator code open.
2. **The catalog.** The Iceberg REST spec is open and QuerySolo's implementation of it should be too (see §7), but the *hosted* catalog is where teams' tables, permissions, lineage and credential vending live. Once a team's tables are registered there, moving is possible (that is the pitch) but tedious. Standard switching cost, honestly earned.
3. **The burst protocol.** The catalog lease, the cap → wall-clock budget conversion, worker sizing from the estimate, partial-progress errors. Not patent-worthy individually; hard to copy as a working whole because it depends on (1).
4. **The ask-box context.** The prompt assembly (schema, sample rows, gauge verdict, saved questions, prior SQL) is the difference between an LLM that writes plausible SQL and one that writes SQL that runs on your tables in your budget. Model-agnostic on purpose; the context is the IP, not the model.
5. **Brand and community.** "The tool the article told me to learn on" is a position nobody else holds yet. It is also the one that decays fastest if v0 is late.

What is **not** defensible and should not be pretended to be: the UI pattern (chat + editor is now standard), the stack, "local-first" as an idea (MotherDuck says the same words).

**Against AWS specifically:** they employ the DuckDB roadmap and will ship a server-mode DuckDB on S3 Tables. QuerySolo's answer is (1) above plus multi-cloud plus a catalog that speaks to GCS and R2, which AWS will not build. If they ship, QuerySolo makes them a burst backend and competes on the experience.

## 7. IP and licensing decisions for v0

| Asset | Decision | Reasoning |
|---|---|---|
| CLI, desktop app, local catalog, estimator code | **Apache 2.0** | Patent grant protects users and contributors; signals seriousness to enterprises; matches dbt Core. MIT would be fine too, but Apache's explicit patent clause is worth the extra paragraph. |
| Hosted control plane, multi-tenant catalog service, billing, credential vending, calibration models | **Proprietary** (not published) | The Supabase pattern: every component open, the platform closed. Avoids the BSL/SSPL backlash HashiCorp and Elastic took, because nothing that was open ever becomes closed. |
| Calibration dataset | **Proprietary; opt-in telemetry with a visible toggle**, anonymised fingerprints only, never SQL text | Trust is the product. Default on for the desktop app with a one-line explanation; default off in CI. |
| Prompts and context assembly for the ask box | **Proprietary**, shipped obfuscated in the binary | It will leak; the point is that it keeps improving faster than a copy. |
| Name and mark | **Register "QuerySolo" as a trademark in software/SaaS classes now** (US + EU, ~$2–4K) and buy the domain before the launch post | "QuerySolo" is a common word with existing marks in other classes (furniture, games). A conflict search before the landing page goes live is cheap; a rename after is not. |
| Patents | **One US provisional** on the pre-flight verdict + hard-capped burst dispatch method, filed before public launch (~$3–5K) | Twelve months of optionality for a few thousand dollars. Defensive value only; do not let it slow anything down. |
| Contributor agreements | **DCO (sign-off), not a CLA** | CLAs deter contributors; DCO is enough under Apache 2.0 and is what the Linux kernel uses. |
| Third-party licences | DuckDB MIT, Iceberg Apache, dbt Apache, Tauri MIT/Apache, pyiceberg Apache | Clean. No copyleft anywhere in the shipped binary. |

## 8. Decisions this doc closes and opens

Closes: language for v0 (Python core + TS frontend), shell (Tauri), catalog (own Iceberg REST, SQLite), licence (Apache 2.0 for everything local), burst backend (Fargate first).

Opens for the founder:
1. Which LLM provider is the default in the ask box when the user has no key (none, or a QuerySolo-hosted trial with a daily cap)?
2. Trademark search result for "QuerySolo" — go/no-go on the name before the landing page ships.
3. Whether opt-in calibration telemetry is default-on in the desktop app (this doc says yes, with the toggle visible on first run).
