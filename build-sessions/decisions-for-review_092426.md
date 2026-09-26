# Lakelet — decisions for review, September 24, 2026

*From two days of Hants' questions about who the product is for and what to build next: how it fits beside an IDE, whether the real dbt work happens outside it, whether the first version is over-engineered, and whether the data should be assumed to live in a bucket or a warehouse. The answers are here as decisions so they are not had again. Tick Agree or write the change. Nothing is built until it is decided; the order in N3 is what these change.*

---

## What the conversation settled, in one paragraph each

**Where the work happens.** Lakelet is not an editor. A project is a folder of dbt models in a git repository; the typing happens in whatever editor the person uses (VS Code, Cursor, vim, or the app's SQL box for a first question), and Lakelet runs the models, keeps the tables, tests them, draws the lineage, and keeps the history. Every button in the app shows the `lakelet` line it is, so the terminal can do everything the window can; the window is for the things an editor is bad at — rows, charts, the verdict, the DAG, history — which are the things a dbt person already leaves the editor for (a database client, `dbt docs`, the warehouse console). The rule that keeps this honest: the CLI stays complete, and the app is never a gate.

**Two personas, one gradient.** The first is a solo analyst or data scientist with files, a bucket, or a warehouse they do not own, and no dbt project: Simple mode is written for them, and Save as question is how they end up with a dbt project without asking for one. The second is the dbt person, solo or in a small team, whose data fits on a machine: Technical mode and the CLI are written for them. What the second does not get yet is the *team* part — a shared catalog, one history, permissions, burst — and the site must not say "team" until it exists. The two are one product because the analyst's saved question is a model file and the dbt person's model is a question card.

**Over-engineered?** For the first persona, in the sense that they see a third of what is built — the REST catalog, Postgres, relocate, publish, the replace semantics, the view macro, versions — yes. Those exist for the thesis (open format, open catalog, no lock-in, a team later), not for the analyst, and they are fine as long as they stay invisible and did not cost the thing that matters: strangers using the product. The risk is not in the code; it is in writing another brief before an outsider has been watched using it.

**Bucket or warehouse as the home?** The bucket half is the thesis and is built (attach, the bucket warehouse, W1). Making Snowflake or BigQuery *the* home would turn Lakelet into a local query client with connectors, a crowded and mostly solved category where the format and catalog stop mattering; declined. The right form of the instinct is a third door: pull a slice of the warehouse onto the laptop as an Iceberg table, refreshable, read-only, with the gauge saying which of the next questions fit here and which go back to the warehouse.

---

**N1. The first user is the solo analyst or data scientist with a file, a bucket, or a warehouse they do not own, and no dbt project. The site, the README's first screen, and the installer's first run are written for that person; the dbt person is the second reader and is served by the CLI being complete.**

*Recommend:* no new code. The landing page's "How it fits" section and the README's "How it fits" already say the two things; the persona page, if one is written, says "solo today, team next" in those words. Simple mode stays the default for a new project (it is today).

*Not chosen:* leading with the dbt persona (they have an editor and a warehouse and will find the team seam in an hour); leading with "team".

- [x] Agree
- [ ] Change:

---

**N2. Three doors into a project, named the same everywhere: drop a file, point at a prefix, pull a slice of a warehouse. The third is a new verb, read-only, and comes before the remote-catalog round.**

*Recommend:* `lakelet import <url> [--where …] [--name n]` where the URL names a warehouse the person already has credentials for — `snowflake://account/db/schema/table`, `bigquery://project/dataset/table`, `postgres://…` (DuckDB's own scanner), with the vendor's Python client returning Arrow and Lakelet writing an Iceberg table, the source URL kept in the table's properties so `tables refresh` re-pulls it the way an attached prefix is refreshed. Credentials follow C1: the vendor's own config and environment (`SNOWFLAKE_*`, the BigQuery ADC file, `PGPASSWORD`), never a key in the project; the app's dialog offers the door beside "Drop a file" and "s3://…" and says what to set. One connector first — Postgres, because DuckDB does it with no new dependency and the tests can run against `compose.yaml`'s Postgres — then Snowflake and BigQuery as optional extras (`lakelet[snowflake]`, `lakelet[bigquery]`) with their tests skipped without credentials, like the real-bucket tests. The gauge treats the pulled table as local from then on, which is the point.

*Not chosen:* live pass-through queries to the warehouse (that is the query client, declined above; the gauge cannot estimate what it does not hold); writing back to the warehouse (a different trust story); making the pull a dbt source (it is a table; a model can ref it).

*Gates:* pytest for the Postgres door against the compose service (a pull, a `--where`, a refresh that picks up new rows, the URL in the properties and never a password); the CLI reference; `/docs/tables` gains "From a warehouse"; the app's drop zone offers it with the C1-style sentence.

- [x] Agree
- [ ] Change:

---

**N3. The order from here: ship, then two outsider sessions, then N2's first door, then the watcher and the open-a-dbt-project fixes, then the remote-catalog round. No new brief is written before the outsider sessions have happened.**

*Recommend:* in this order, each a gate for the next.

1. **Ship** (`ship-v0-plan.md`, held since 2026-09-17): the freeze, the macOS DMG and the Ubuntu `.deb`, PyPI, the brew tap, the first-run story. Hants lifts the hold; the brief is already decided.
2. **Two outsider sessions**, recorded, forty minutes each: one analyst with a folder of CSVs and no dbt (do they reach a saved question unaided, and do they care that it became a model?), one dbt person with an existing project (does the CLI plus the results pane hold them, or do they want the editor inside?). What they ask becomes the README's next paragraph and the order of everything below.
3. **N2's first door**, Postgres, then the vendor connectors as demand says.
4. **Small things the sessions will surface, already known**: the project watcher (the app updates when a file is saved in the editor: `watchfiles` in the core, an event stream on `/api`, the screens refetch; about a day), and *open an existing dbt project* (the profile the core writes takes the name their `dbt_project.yml` declares — a bug today; `init` reads `sources.yml` and says which sources are found, attachable, importable or missing; a compile pass that lists what will not compile on DuckDB before anything runs; two to three days). Both are decisions to tick when they come up, not now.
5. **The remote-catalog round** (`remote-catalog-plan.md`, R0 first), which serves the second persona's team; then P2's hosted brief.

*Not chosen:* the catalog round before ship (it serves the persona that is second); an editor in the app (N1's rule); a VS Code extension now (a thin client on `/api` — "Run in Lakelet", results inline — is right eventually and cheap once the event stream exists, but the MCP server for the editor's agent is the more important editor integration and is already in the plan).

- [x] Agree
- [ ] Change:

---

*If agreed: nothing to build today. Ship is the next session; `TASKS.md`'s "Now" moves to `ship-v0-plan.md` step 0 when Hants lifts the hold. N2 becomes a brief item after the outsider sessions, not before.*
