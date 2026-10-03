# A warehouse for one.
> QuerySolo is an open-source warehouse for one machine, for SQL and dbt: it says whether a query fits before it runs, records what every run actually did, and keeps every table in Iceberg so any engine can read it.
Developer preview · Apache 2.0 · macOS and Linux · QuerySolo · the guidebook to marketing/
---
# What "a warehouse for one" says
- **It is a warehouse.** Tables in a catalog you can list and describe. SQL over them. Transformations as managed tables and views. Snapshots and history. Statistics, lineage, a record of every run. Backups that are a copy of a folder. Not a database, not a notebook, not an editor, not a lakehouse tutorial.
- **It is for one.** One person, one machine, one folder, one writer. The boundary stated as a fact: no users, no permissions, no service other tools connect to, nothing that runs while nobody is looking.
- **"One" is a boundary that moves.** For one now. For a team when two laptops share one catalog over one bucket. For a company when the catalog and the control plane run in their own account. The word changes when the product does.
- Why not "open-source warehouse" bare: that shelf is ClickHouse, Doris, StarRocks and Trino over Iceberg, all servers, and we lose every row from "many writers" down.
---
# The half a person needs is built. The half a team needs is not.
| Built today | Not built |
|---|---|
| Tables in a catalog you can list and describe | Many writers |
| SQL over them, through the catalog | Users, roles, permissions |
| Transformations as managed tables and views, through dbt | A service other tools connect to |
| Atomic commits, snapshots, history | Runs when nobody is looking |
| Statistics, query history, lineage | Compute beyond the machine |
| Backups: a copy of the folder | |
| Many readers: DuckDB, pyiceberg, Spark, Trino | |
Two of the missing rows would bother a solo user and are not team features: nothing runs unattended, and no BI tool can connect. They are cheaper than the team rows.
---
# Three beats, always in this order
- **Know what fits.** Before a row comes back: the bytes it will read, the memory, the seconds, and a sentence that says why. Red refuses until you say run anyway.
- **Know what changed.** After the run: which model is out of date, from the data as well as the code; run only what is stale; every run recorded against its estimate; one feed for snapshots, runs and commits.
- **Nothing leaves. Any engine reads.** Zero outbound attempts on the quickstart, measured. Parquet and Iceberg in your folder or your bucket; Spark, Trino, pyiceberg, BigQuery and Databricks read them as they are.
The order is the argument: the verdict is the one thing nobody has; the record is what makes the verdict trustworthy; trust is what lets the reader install.
---
# Know what fits
> Before you run it, know.
| Verdict | What it means |
|---|---|
| Runs here | Fits this machine. The bytes and the seconds, before the first row. |
| Runs here, slowly | Fits, and the sentence says how long. |
| Needs more machine | Refused until you say run anyway. |
| Not estimated | It cannot attribute the scan, and says so instead of guessing. |
- BigQuery shows the bytes. This shows the minutes, and refuses.
- Every run is recorded against its estimate. The gauge's own name is Lookahead, never compounded with the product name.
![The verdict and its sentence before the rows](docs/screenshots/query-verdict.png)
---
# Know what changed
> After it runs, know what changed.
- Every model knows whether it is fresh, edited, out of date or never built.
- **A change to the data counts.** A table's new snapshot marks everything that reads it stale, because the tables and the models share one catalog.
- Run only what is stale does exactly that. Every run is recorded against its estimate.
- The Changes feed: the data's snapshots, the models' runs, the code's commits, in one list, newest first.
- dbt sees a changed model. Renart sees a changed file. This also sees changed data.
- The on-ramp, so there is something to keep track of: a question you keep becomes a model with two checks and a version. If you have never used dbt, you just did. If you have, the model you wrote gets a verdict, its checks, a version and a state without leaving your editor.
Saving is not the headline, because saving is not unique.
---
# Nothing leaves. Any engine reads.
> Your machine. Your bucket. Your tables.
- Zero outbound attempts on the whole quickstart, measured by querysolo audit network. The scope, always in the same paragraph: one extension download at init, and the buckets and bursts you ask for.
- The project is a folder: warehouse/ holds Parquet and Iceberg metadata, models/ the SQL, .querysolo/ the catalog and history, .git/ the versions, querysolo.toml the settings. A copy of the folder is the backup.
- Spark, Trino, pyiceberg, BigQuery and Databricks read the tables as they are. Leaving is pointing another engine at the folder.
- A failed replace keeps the old table, a moved folder is relocated, a newer schema is refused: every sentence in /docs/recovery has a test.
---
# Not an editor. Not a cloud warehouse.
> Beside your editor. Under your SQL.
- Your editor writes it. The product runs it, keeps the tables, tests them, draws the lineage, keeps the history.
- Every button in the app shows the command it is. The terminal can do everything the window can. The app is never a gate.
- The IDE owns typing, completion, formatting, the git panel and the pull request. The product owns the verdict, the run, the tests executed, the state, the versions read back from git, and the feed.
- The one deliberate crossing of that line is Save as question, for the person who has no editor. It stays the only one.
---
# Start with what you have
| Door | What happens | Status |
|---|---|---|
| A file | Drop it. A table in seconds, every column's type written down, the lossy casts named. | built |
| A bucket | Point at the Parquet. Nothing copied; public data needs no credentials; the bandwidth is in the verdict. | built, S3 |
| A warehouse you do not own | Pull a slice onto the laptop, refreshable, and let the verdict say what fits here and what goes back. | planned |
The page routes by door, never by job title. The third card is planned and visibly marked, because three of six personas want it most.
---
# Six personas, internal only
| Persona | Is "for one" true | The sentence they hear | Their door |
|---|---|---|---|
| The solo analyst with files | wholly | mine, on my laptop, nothing uploaded | a file |
| The data scientist in a notebook | wholly | one machine, pull once | a file, then a bucket |
| The learner | wholly | free, mine, no card, the real stack | a file |
| The dbt person in a small team | with the disclosure | solo today, and they said so | a bucket, or a file |
| The analyst on BigQuery or Databricks | partly, today | the minutes and a refusal, and nothing uploaded | a file; the third door when it exists |
| The coding agent | for one person's agent | cost before the run, a refusal it cannot argue with | the CLI and the API |
All six are assumed, none observed. The two outsider sessions turn the first two into observed. The page never names them.
---
# Words we use, words we do not
| Use | Not |
|---|---|
| the verdict; Lookahead | the score, the gauge reading, the AI estimate |
| fits; runs here; before it runs | fast, performant, pre-flight, predictive |
| a question (Simple); a model (Technical) | a saved query, an asset, a job |
| the record; the Changes feed; versions | audit trail, observability, monitoring |
| your machine, your bucket, your engine | the edge, on-prem, hybrid |
| open tables; Parquet and Iceberg; any engine | vendor-neutral, interoperable, open standards |
| a warehouse for one | a local lakehouse, a personal data platform, a desktop warehouse |
| planned; next; developer preview | coming soon, roadmap, beta, production-ready |
Never on the page: lakehouse as the category, local-first as the lede, team, shared, collaborate, burst as a feature, Windows, AI-powered, seamless, blazing, unlock, modern data stack.
---
# What we can cite, and what we do not claim
| We can cite, dated | We do not claim |
|---|---|
| Zero outbound attempts on the quickstart, measured (PRIVACY.md) | Team, shared, collaborate, or a second laptop seeing the first one's tables |
| A public dataset of 21.9 GB in 32 files, attached with no credentials, nothing copied (/docs/remote, 2026-09-11) | Burst as a feature, or any burst number |
| The verdict before the first row; 56 ms on the reference Mac, in the docs (2026-09-10) | A dollar saving or a market size |
| Every sentence in /docs/recovery has a test | Windows |
| Spark and Trino read and write the same tables through the catalog (2026-09-08) | Production-ready |
| Apache 2.0, a public repository, the DCO | The gauge's accuracy as a percentage, until the chart exists on someone else's workload |
---
# For one, then for a team
> Next: a slice of your warehouse on your laptop, a budget for your agent, and one job sent to your own cloud under a cap.
- The order from here: ship, then two outsider sessions, then the warehouse slice, then the watcher and open-a-dbt-project, then the catalog round. No new brief before the outsiders have been watched.
- For one, today. For a team when two laptops share one catalog over one bucket, bring-your-own catalog first, then ours. For a company when the catalog and the control plane run in their own account.
- What is sold moves from compute to decisions: seats for the record across a team, an identity with a budget for each agent, routing under a cap, burst metered under it. Estimates stay free and open.
The word changes when the product does.
---
# The landing page in one breath
- 1  Hero: A warehouse for one. The one-liner. The next line, quieter. Get it from source.
- 2  Know what fits: the four verdicts by name, the interactive Lookahead demo, the BigQuery line.
- 3  Know what changed: the state, a changed table counts, the feed, the on-ramp in two sentences.
- 4  Nothing leaves, any engine reads: the measured zero, the folder tree, the engines that read it.
- 5  Not an editor, not a cloud warehouse: your editor writes it, the product runs it.
- 6  Three doors: a file, a bucket, a warehouse you do not own (planned, marked).
- 7  For one, then for a team: the honest paragraph, in those words.
- 8  Built and planned: the generated status block.
- 9  Get it: from source; the installer when signed; the waitlist.
Applied on top of PR #1 once reviewed. Every feature sentence traced to web/src/data/status.ts.
