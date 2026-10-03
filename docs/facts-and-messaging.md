# QuerySolo — Verified facts & messaging brief (Sep 7, 2026)

*Amended September 8, 2026 by `build-sessions/core-v0.5-plan.md` §8; where the two differ, the brief wins.*

Use ONLY these facts. Do not invent numbers. Anything marked ESTIMATE must be labeled as such.

## Positioning
- Name: QuerySolo (Lakelet until 2026-09-30; `build-sessions/rename-querysolo-plan.md`). Tagline options: "Supabase for the warehouse." / "Your laptop is the warehouse — until it can't be."
- One-liner: Open-source, one binary, local by default. Your laptop is the warehouse until it can't be — then one job bursts to the cloud and comes back. *(The burst half is planned, not built: since September 15, 2026 the site's lede says only what exists — "an open-source, local-first lakehouse in one binary: Iceberg tables on your laptop, DuckDB as the engine, dbt built in, and a gauge that says whether a query fits before it runs" — with burst, MCP and English on a quieter "next" line. "Nothing leaves your machine" is scoped exactly as `PRIVACY.md` scopes it: the one extension download at `init`, and the buckets and bursts you ask for.)*
- Wedge feature: the "Can I run this here?" gauge. Every query/dbt run gets a pre-flight estimate (bytes scanned, memory, time) vs. your actual machine. Green = runs local. Yellow = runs local but slow. Red = one click sends just that job to an ephemeral cloud worker, with a HARD COST CAP shown before you click. "The bill for a burst can never exceed the number you clicked."
- Differentiation vs MotherDuck: bring-your-own S3/GCS/R2, open Iceberg format, open (Iceberg REST) catalog, visible & user-controlled local/cloud boundary, no lock-in. (Supabase-vs-Firebase argument.)
- Own the UX + catalog + burst orchestration, not the engine.

## Verified facts (with dates)
- DuckDB v1.5.3 released May 29, 2026: full Iceberg writes — MERGE INTO, ALTER TABLE, bucket()/truncate() partition transforms, Iceberg V3 (deletion vectors, row lineage). Works against Polaris, Lakekeeper, Amazon S3 Tables REST catalogs. Spark is no longer required to write Iceberg.
- AWS announced acquisition of DuckLabs (the company behind DuckDB) on Aug 26, 2026. AWS explicitly is NOT acquiring the DuckDB open-source project; it stays MIT-licensed under the independent DuckDB Foundation. Founders Hannes Mühleisen & Mark Raasveldt keep technical leadership.
- Apache Polaris graduated to Apache Top-Level Project on Feb 19, 2026 (vendor-neutral Iceberg REST catalog).
- DuckLake v1.0 released Apr 13, 2026 (production-ready; SQLite/Postgres/DuckDB catalog backends; multi-writer via Postgres catalog).
- dbt Core v2 (June 2026): Apache 2.0, no usage limits, Rust runtime shared with Fusion. Fivetran + dbt Labs merger completed June 2026.
- MotherDuck: $133M total raised; $52.5M Series B (Sep 2023) at $400M post-money; $33M Series B+ (May 2025) led by Felicis with a16z, Redpoint, Madrona, Amplify, Altimeter. Consumption-based; targets teams under 10–20 TB. In Jan/Feb 2026 the $25/mo tier was removed: Free "Lite" = 3 users, 10 GB, 10 compute-hours; Business = $250/month per org + usage; compute $0.60/hr (Pulse) to $24/hr (Giga); storage $0.04/GB-mo.
- Snowflake small-team cost (Definite pricing guide model): Series-A team, one analyst, dbt 1–2×/day, ~500 GB → ~$490/month; teams with always-on dashboards and several analysts land in the low thousands. ESTIMATE range to use: "$500–5,000/month on data that fits on a laptop." Mid-market (10–50 TB) typically $200K–800K/yr.
- AWS Fargate list price ~ $0.04/vCPU-hr and ~$0.0044/GB-hr → a 16 vCPU / 64 GB worker ≈ $0.93/hr before margin. Typical burst job = cents to low dollars. (ESTIMATE, from list prices.)
- Bandwidth reality: scanning 50 GB from S3 over a 200 Mbps home connection ≈ 35 min; a worker in the bucket's region ≈ ~1 min. Most Red verdicts are bandwidth verdicts.

## Product layers (Supabase parallel)
1. Local CLI + desktop app — free, open source (MIT/Apache).
2. Team catalog — hosted Iceberg REST catalog (Postgres) so tables are shared across laptops. Collaboration hook.
3. Burst compute — metered. The revenue line.
4. Ops-in-a-box — compaction, snapshot expiry, freshness checks, scheduled dbt runs. "We do the 3am pager work."

## Pricing (proposed)
- Free local forever.
- Team: ~$20–30/seat/month for team catalog + scheduling.
- Burst: at cost plus margin, hard per-run cap shown before you click.

## Who buys
- First: solo data engineers and 2–10 person data teams under ~1 TB paying Snowflake/BigQuery for data that fits on a MacBook.
- Second: learners building portfolio projects on the free tier who bring the tool to their next job.

## Roadmap (12 weeks)
- Wk 1–2: spikes (local Iceberg writes via own REST catalog; estimator accuracy on TPC-H; Fargate worker economics).
- Wk 3–6: CLI v0 to design partners (init/sql/estimate + gauge); public repo in Day 1. Landing page + waitlist.
- Wk 7–10: Burst v0 (control plane, Fargate, hard cap, metering). 10 design partners.
- Wk 11–12: dbt integration + team catalog alpha; billing on.

## The ask (pre-seed) — PLACEHOLDER, founder to confirm
- Raising: $[X]M pre-seed. Use: 2 engineers + founder for 12 months, cloud costs, design-partner program. Milestones: OSS CLI launched, 10 design partners on burst, team catalog GA, first $ revenue.

## Risks (be honest on the slide)
- MotherDuck incumbent; AWS could ship "DuckDB serverless" (mitigate: multi-cloud, own catalog/UX, make it a backend); DuckDB-Iceberg writes are 3 months old; estimator trust.
