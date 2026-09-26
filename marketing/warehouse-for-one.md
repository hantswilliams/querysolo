# A warehouse for one

*Concept and branding language · 2026-09-24 · Product name: Lakelet (working name; TBD\*) · The reasoning is in `build-sessions/lakelet-build-sessions_092426b.md` §2 and §7; the audit of what "warehouse" means against what is built is in that day's conversation and summarised in §1 below.*

## 1. What the phrase says

Three things, in this order.

**It is a warehouse.** Tables in a catalog you can list and describe. SQL over them. Transformations as managed tables and views. Atomic commits, snapshots, history. Statistics, lineage, a record of every run. Backups that are a copy of a folder. That is the half of a warehouse one person needs, and it is built, in an open format, on one machine. It is not a database (that is DuckDB, underneath), not a notebook, not an editor, and not a lakehouse tutorial.

**It is for one.** One person, one machine, one folder, one writer. The phrase states the boundary as a fact instead of hiding it: no users, no permissions, no service other tools connect to, nothing that runs while nobody is looking, one writer per table. The other half of a warehouse, the half a team needs, is not built, and the phrase says so before anyone asks.

**"One" is a boundary that moves.** For one now. For a team when two laptops share one catalog over one bucket (`build-sessions/remote-catalog-plan.md`). For a company when the catalog and the control plane run in their own account. The word changes at exactly the moment the product does, which is the right kind of expiry for a category word. "Local" and "for one machine" would expire earlier, at the bucket and the worker, without the product having changed.

Why not the bare "open-source warehouse": that shelf is ClickHouse, Doris, StarRocks and Trino over Iceberg, all servers, and against them we lose every row from "many writers" down. "For one" keeps us off that shelf and on our own.

## 2. The line

**The one-liner** (the README's first sentence, the hero's subtitle):

> TBD\* is an open-source warehouse for one machine, for SQL and dbt: it says whether a query fits before it runs, records what every run actually did, and keeps every table in Iceberg so any engine can read it.

**The tagline** (the hero headline, the tab title, the first line of the deck):

> A warehouse for one.

**The two-beat form** (a subhead, a tweet, the App Store line if there is ever one):

> Know what fits. Know what changed.

**The "next" line**, in the quieter style the trust round set, always under and never beside a feature:

> Next: a slice of your warehouse on your laptop, a budget for your agent, and one job sent to your own cloud under a cap.

Every clause of the one-liner is built. The "next" line is every planned thing the six personas pull hardest on, and nothing else.

## 3. The three beats

The page, the deck and the README follow the same three beats in the same order. Each is a headline, the sentence under it, and the feature it names.

1. **Know what fits.** Before a row comes back: the bytes it will read, the memory, the seconds, and a sentence that says why. Four verdicts by name: *Runs here*, *Runs here, slowly*, *Needs more machine*, *Not estimated*. Red refuses until you say run anyway. Every run is recorded against its estimate. The gauge's own name is **Lookahead**.
2. **Know what changed.** After the run, the record. Every model knows whether it is fresh, edited, out of date or never built, and a change to the *data* counts as a change, not only a change to the code: a table's new snapshot marks everything that reads it stale, because the tables and the models share one catalog. Run only what is stale does exactly that. Every run is recorded against its estimate. The Changes feed puts the data's snapshots, the models' runs and the code's commits in one list, newest first. The on-ramp, so there is something to keep track of: a question you want to keep becomes a model with two checks and a version, in one click, and every save and run is a commit.
3. **Nothing leaves. Any engine reads.** Zero outbound attempts on the whole quickstart, measured. The tables are Parquet and Iceberg metadata in a folder or in your bucket, and Spark, Trino, pyiceberg, BigQuery or Databricks read them as they are. Leaving is pointing another engine at the folder.

## 4. What "one" also means

Secondary meanings, usable in body copy, never as the lead.

- One folder is the project, the backup, and the thing you hand to someone else.
- One command behind every button: the app shows the `lakelet` line it is, so the terminal can do everything the window can.
- One download, at `init`, then nothing.
- One binary, once the installer ships. Not before.
- One writer. The honest one, and the one we say first.

## 5. Vocabulary

| Use | Not | Why |
|---|---|---|
| the verdict; Lookahead | the score, the gauge reading, the AI estimate | the verdict is a decision with a sentence; Lookahead is its own name, product-name-free |
| fits; runs here | is fast, is performant | the product's verb; the question every persona is asking |
| before it runs | pre-flight, predictive | plain words; the moment is the point |
| a question (Simple), a model (Technical) | a query you saved, an asset, a job | the same file, two readers; N1's gradient |
| the record; the Changes feed; versions | audit trail, observability, monitoring | what a person calls it |
| your machine, your bucket, your engine | the edge, on-prem, hybrid | the possessive is the trust story |
| open tables; Parquet and Iceberg; any engine | vendor-neutral, interoperable, open standards | the concrete noun beats the adjective |
| a warehouse for one | a local lakehouse, a personal data platform, a desktop warehouse | §1 |
| planned; next | coming soon, roadmap, beta | the trust round's word |
| developer preview | production-ready, enterprise-grade | one person uses it daily; strangers have not |

Words that do not appear: lakehouse (as the category; it may name the format lineage in docs), local-first (as the lede), modern data stack, AI-powered, seamless, blazing, unlock, effortless, democratise, single pane of glass, team, shared, collaborate, burst (as a feature), production-ready, Windows.

## 6. Voice

- Plain sentences, mostly short. One idea each.
- Second person for the reader. The product is "it". No "we" on the page except in the honest list.
- A number only when measured, and dated in the docs it links to. Otherwise the word: "seconds", "before the first row".
- Every feature sentence can be answered with a command or a screen. If it cannot, it is not a feature sentence.
- When something is not built, "planned" is in the same sentence, not a footnote.
- Concrete nouns over abstract ones: a CSV, a bucket, a Monday morning, a wrong number in a deck. Not data, insights, workflows, value.
- The comparison is stated, not implied. Name what the other thing does well first.
- No exclamation marks. No questions as headlines.

## 7. Comparisons we make, fairly

| They | What they do well | What we say we do that they do not |
|---|---|---|
| BigQuery | shows the bytes before a run, exactly | forecasts the minutes, refuses on Red, keeps your own record of estimate against actual, and nothing is uploaded |
| Databricks | the notebook and the cluster | anything before the run |
| The BigQuery sandbox | free, real, no install | free, real, on your machine, nothing uploaded, open tables you keep |
| MotherDuck | DuckDB in their cloud, shared | your machine and your bucket, open format, open catalog, the verdict |
| DuckDB alone | the engine, and it is ours too | the catalog, Iceberg, dbt, the record, the verdict |
| Renart | an IDE over a warehouse you already pay for; a fingerprint that sees a changed file | we are the warehouse and not an IDE; your editor writes it, the product runs it; a changed *table* counts as a change too |
| Duckle | a canvas for pipelines, no SQL needed | for people who write SQL; a table format, versions, a catalog |
| A "laptop lakehouse" post | the same stack, in an afternoon | the verdict and the record, which the post cannot give you |

## 8. Proof points we can cite today

Each with where it is measured, so the page can link and the deck can footnote.

- Zero outbound attempts on the whole quickstart, measured by `lakelet audit network`; what is stored where, in `PRIVACY.md`.
- A public dataset of 21.9 GB in 32 files, attached from a laptop with no credentials and nothing copied; a bounding-box query answered from another process with pyiceberg (`/docs/remote`, 2026-09-11).
- The verdict arrives before the first row. On the reference Mac the verdict line landed at 56 ms and the first rows at 62 ms over a 20-million-row table (app brief, 2026-09-10). The page says "before the first row"; the milliseconds stay in the docs.
- A failed replace keeps the old table, a moved folder is relocated, a newer schema is refused: every sentence in `/docs/recovery` has a test.
- Spark and Trino read and write the same tables through the catalog (the smoke test, 2026-09-08).
- Apache 2.0, a public repository, the DCO.

## 9. Claims we do not make

- "Team", "shared", "collaborate", or a second laptop seeing the first one's tables. Not until the catalog round.
- "Burst" as a feature, or any burst number. Arithmetic from a plan is not a measurement.
- A cost saving in dollars or a market size.
- Windows.
- "Production-ready." It is a developer preview used daily by one person and by a test suite.
- The gauge's accuracy as a percentage, until the estimate-against-actual chart exists on someone else's workload.
- "Nothing leaves your machine" without its scope in the same paragraph.
