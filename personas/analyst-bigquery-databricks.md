# The mid-tier analyst on BigQuery or Databricks

*Persona · written 2026-09-24 from the positioning conversation of that day (the articles in `research/`; the conclusions in `build-sessions/lakelet-build-sessions_092426b.md`) · Status: **assumed, not observed** — no recorded session with this person has happened; the questions at the end are what one must answer · Product name: Lakelet (working name; TBD\*).*

## Who

Writes SQL well and does not manage infrastructure. Two to eight years in. Owns a handful of reports and answers questions from a manager or a product team. Works under a platform or data-engineering team that sets the cost rules, approves datasets, and sends the email when a query was expensive. Uses dbt lightly or not at all. Has a corporate laptop, usually 16 GB, often Windows, with a policy about what can be installed. Keeps a folder of CSVs that never made it into the platform.

On BigQuery they already see a bytes number before a query runs. On Databricks they see nothing until the warehouse has spun up and billed. Both export to Sheets or Power BI, both get the "who ran this" email, and both use a coding agent that runs queries with their credentials.

## Tools, and where the day goes

| Task | On BigQuery | On Databricks |
|---|---|---|
| Write and run SQL | the console; a bytes estimate before the run | the SQL editor or a notebook against a SQL warehouse; nothing before the run; a cold start when the warehouse has stopped |
| The cost they can see | on-demand per TB scanned; the dry-run bytes; custom quotas if the platform team set them | DBUs per warehouse-hour; the bill arrives per warehouse, not per query |
| Bring a file in | upload to GCS, create a dataset, a load job | upload to a volume, a create-table cell |
| Keep a result | a saved query, a scheduled query, a destination table | a notebook, a job, a table in Unity Catalog |
| Share | Sheets, Looker Studio, a link to the query | a dashboard, a notebook link, Power BI |
| Where the tables are | BigQuery-native; BigLake for Parquet and Iceberg in GCS | Delta in Unity Catalog; UniForm exposes Delta as Iceberg through Unity's REST endpoint |
| The coding agent | Cursor or Claude Code, running queries as them, no budget | the same |

## What hurts

- Exploration is a warehouse round trip forty times over: seconds of latency on BigQuery, a meter and a cold start on Databricks.
- The cost is discovered after the run, or, on BigQuery, shown but not enforced, and the email comes from someone else.
- A file from finance needs a governance step before a question can be asked of it.
- A scheduled report rebuilds whether or not anything changed, and when a number is wrong nothing says which load did it.
- The coding agent runs as them with no ceiling.
- The platform's bill is argued with anecdotes, because nobody keeps a record of what actually fit where.

## Scenarios

Each: the situation, what happens on their platform today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. The export somebody sent

A 900 MB CSV arrives from finance. On BigQuery that is a bucket upload, a dataset, a load job, and a question from the platform team about who created the dataset. On Databricks it is a volume upload and a create-table cell. With the product it is a drop onto the window, a table in a few seconds, a verdict that says runs here, the question typed, the chart. Nothing was uploaded to the company platform, so nothing needs governing. The question they keep becomes a model with two checks and a version.

*Built today.* Import, the verdict, the chart, save as question, versions.

### 2. Forty drafts before the right query

The real cost of exploration is not the final query but the forty attempts before it, each a warehouse round trip. With the product the analyst pulls a slice of the table onto the laptop, the last ninety days of one fact table, as a refreshable Iceberg table, and iterates against it at sub-second speed. The gauge says which of the follow-up questions still fit here. When the final version needs two years instead of ninety days, the verdict says needs more machine, and the same SQL goes back to the warehouse with the cost shown first.

*Planned.* The pull is the third door (`decisions-for-review_092426.md` N2), after the outsider sessions, Postgres first and the warehouse connectors as extras. The routing back with a cost is the Day 2 route-and-cap brief. *Built today:* the slice works only where the data already sits as Parquet in an S3 bucket, which attach reads in place.

### 3. The email about the expensive query

A join goes wrong and the query reads the whole events table, five terabytes deep. BigQuery on-demand bills it and runs it the moment they click. A Databricks warehouse grinds for forty minutes and the team's other queries queue behind it. With the product the verdict comes in two halves before anything runs. The fact half says what will be read, the bytes and the file count out of the manifests, which anyone can check. The forecast half says about forty minutes on this machine, and, with the per-engine cost models, about thirty dollars on BigQuery or twenty-five minutes on their warehouse. Red refuses. If they route it anyway, the dispatcher sets the engine's own ceiling on the job so the bill cannot exceed what they saw.

BigQuery deserves the fair comparison: it already shows the bytes. What it does not do is forecast time, refuse, cap the job, or keep the analyst's own record of estimate against actual.

*Built today.* The refusal and the local record, for tables in the project. *Planned:* the fact-and-forecast split (E1 in the session log), the per-engine cost and the cap on a foreign engine (Day 2).

### 4. The weekly report they own

Every Monday a scheduled query rebuilds a summary table whether or not anything changed underneath, and when a number looks wrong the analyst cannot say which upstream load did it. With the product the report is a model in the project. Run only what is stale builds it when an upstream table has a new snapshot and skips it otherwise. The Changes feed shows the snapshot that made it stale, lineage shows what feeds it, and every run is a version with the SQL diff. A table rebuilt every week accumulates delete files, and the gauge will say needs maintenance once compaction lands.

*Built today.* `lakelet run --stale`, the Changes feed, lineage, versions. *Planned:* the schedule itself (Team tier; cron or CI until then), compaction (V2) and the needs-maintenance verdict.

### 5. The coding agent with their credentials

They write SQL with Cursor or Claude Code, and the agent runs queries as them, with no budget. On either platform an agent looping over the events table thirty times is a real bill and a real email. With the product the agent gets the estimate tool before the query tool, read-only by default, a daily budget in bytes and seconds that the core refuses past, and a log of every call. Anything the agent saves is a model and a commit that names the agent, so the review is a pull request.

*Built today.* The local API and the project's `AGENTS.md`. *Planned:* the MCP server and the budget (session 5), which the gauge-first business model moves up.

### 6. Being asked to prove the platform is oversized

The contract is up for renewal, or a small team pays two thousand a month for four hundred gigabytes. With the product the argument is a chart, not a claim: three months of the gauge's record showing what share of their real queries were green on a laptop, and what the rest would cost routed to a pay-per-query engine over the same tables. The tables are already Iceberg in their own bucket, which Databricks reads through Unity's Iceberg endpoint and BigQuery reads through BigLake, so nothing moves back if the answer is to stay.

*Built today.* The record, per machine, on the Gauge screen and in `gauge export`. *Planned:* the chart across a team (Team tier); the bucket half for this persona needs GCS (below).

## Where this persona hits walls today

- **Windows.** Most corporate analyst laptops run it. The product is macOS and Linux, Windows untried. This is the first wall either persona hits.
- **GCS.** The BigQuery analyst's exports live in Google Cloud Storage. Bucket support is S3 today; GCS and R2 are Day 2 in `docs/lakelet-product-spec.md`.
- **Delta and Unity.** The Databricks analyst's tables are Delta. Attach reads Parquet prefixes and Iceberg, not a Delta log, and reading UniForm tables through Unity's Iceberg REST endpoint waits on the bring-your-own-catalog round (`remote-catalog-plan.md` R1).
- **The 16 GB laptop.** The gauge's constants were tuned on one machine with 64 GB. The reference-laptop timings are an open item in `TASKS.md`, and this persona is the reference laptop.
- **The warehouse door.** Scenario 2 is the strongest story for both, and its first connector is Postgres. Snowflake and BigQuery are the extras to write next; a Databricks SQL connector would be a third.

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- After the outsider sessions, open the warehouse door on BigQuery or Databricks before Postgres. The analyst in these scenarios has one of those and not a Postgres; Postgres was chosen for test convenience, not for a user.
- Windows moves from "untried" to a named item once this persona is observed, because scenarios 1 and 2 do not happen on a machine the product does not run on.
- The fact-and-forecast split (E1) and the local budget (E2) are what scenario 3 and scenario 5 need first; both are small and both are visible in a session.

## Questions for the outsider session

- Which machine, and which operating system, do they actually have, and can they install an unsigned app on it.
- Do they have any bucket access at all, or only the warehouse. If only the warehouse, scenario 2 is the whole product for them.
- Do they use dbt, or is the model file something they would rather not see. Does Simple mode hold them.
- When the verdict refuses, do they trust it, argue with it, or click run anyway. What would make them trust it: the fact half, a track record, or someone else's.
- Do they run a coding agent against the warehouse today, and does anyone cap it.
- What do they do with the answer: Sheets, Power BI, a link. Whichever it is, that is the export the product must make trivial.
