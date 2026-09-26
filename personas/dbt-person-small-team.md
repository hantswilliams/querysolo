# The dbt person in a small team

*Persona · written 2026-09-24 · Status: **assumed, not observed** — this is the second outsider session in `decisions-for-review_092426.md` N3 (step 2): a dbt person with an existing project · Product name: Lakelet (working name; TBD\*).*

This is N1's second reader and the PRD's P1: the person Technical mode and the CLI are written for. They already have an editor, a warehouse, a project and a way of working, and they will find the team seam in an hour. What they are promised today is a local runtime for the workflow they already have, with a verdict on every model. What they are not promised, and the site must not say, is "team".

## Who

An analytics engineer, or a data engineer of one, at a company of ten to a hundred people; or one of a data team of two to five. Owns a dbt project of forty to four hundred models. Pays for a warehouse, or their company does: Snowflake, BigQuery or Redshift, sometimes Postgres, sometimes DuckDB with MotherDuck. The data fits: under a terabyte in total, most tables under ten gigabytes, the warehouse sized for the one nightly run that is not. Writes SQL in VS Code with the dbt extension, reviews in pull requests, runs tests in CI. Knows Iceberg is coming and has not had a reason to touch it.

## Tools, and where the day goes

| Task | What they use | What they see |
|---|---|---|
| Edit a model | VS Code with dbt Power User, or Cursor | the SQL; a compile preview if the extension is set up |
| Run it | `dbt run -s model+` against a dev schema on the warehouse | twenty to sixty seconds per round trip; credits; a collision with a colleague's dev schema |
| Look at the result | a database client, or the warehouse console | a second window, a second login |
| Decide what to rebuild | `state:modified+` against a production manifest, or a full refresh | slim CI that works when the artifact is there and not otherwise |
| Schedule | dbt Cloud, Airflow, Dagster, or a GitHub Actions cron | the run logs in the scheduler |
| Load | Fivetran, Airbyte or dlt into the warehouse | tables appearing in `raw` |
| Test and document | dbt tests, `dbt docs`, maybe elementary | a docs site nobody opens; a failed test in Slack at 3am |
| The bill | the warehouse's invoice | five hundred to five thousand a month, most of it idle |
| What happened last night | the scheduler, the warehouse's history, and git, in that order | three places for one question |

## What hurts

- The dev loop is a warehouse round trip: edit, run, wait, look in another window, repeat.
- Deciding what to rebuild after a change is a manifest artifact away from working, so they rebuild everything out of caution.
- What changed last night is three places: the run in the scheduler, the data in the warehouse, the code in git.
- The warehouse is paid for the biggest run and idle the rest of the time, for data that fits on the laptop they are typing on.
- A second person means a laptop, a dev schema, credentials and a day.
- The 3am page: a load failed, a test failed, the dashboard is wrong, and the fix is a rerun that costs credits.
- Dev and prod drift: the local runtime does not speak the warehouse's dialect, or the other way round.

## Scenarios

Each: the situation, what happens today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. Opening the project they already have

A dbt project with a profile for Snowflake and a `sources.yml` naming forty raw tables. Today the product does nothing for it. With the product, `lakelet init` in the project folder reads `dbt_project.yml` and `sources.yml`, says which sources are found in the project, attachable from a bucket, importable from a file, or missing, and a compile pass lists what will not compile on DuckDB before anything runs. The profile the core writes takes the name their project declares.

*Planned.* N3 step 4, two to three days, a decision to tick when it comes up. *Today:* the profile name is a bug, `sources.yml` is unread, and a model in the warehouse's dialect fails at run time rather than before.

### 2. The dev loop, on the laptop

Edit a model in VS Code, run it, look at rows. Today that is a warehouse round trip and a second window. With the product it is `lakelet run stg_orders+` in the terminal, or Refresh in the app, a verdict for every model in the selection before it builds, the DAG by verdict, and the rows in the results pane. Sub-second on their laptop, no credits, no dev-schema collision, and every button in the app shows the `lakelet` line it is, so the terminal is enough.

*Built today.* `lakelet run` with selectors and `--plan`, the DAG by verdict, the Models screen, Technical mode. *Planned:* the watcher, so the app notices the file they just saved in the editor (N3 step 4); a thin VS Code client with the verdict inline, after the event stream.

### 3. What to rebuild after a change

They changed one staging model. Today the honest answer needs a production manifest and `state:modified+`; the usual answer is a full refresh. With the product every model carries a state, fresh, edited, upstream changed or never built, from its content fingerprint and its inputs' snapshots. `lakelet run --stale` builds exactly what an edit invalidated, Run what changed does the same from the app, and the Review section shows the SQL diff since the last run before they press it. In CI the same command with exit codes is the slim build without the artifact.

*Built today.* The per-model state, `--stale`, the Review section, the exit codes. Renart's "Build stale" is the same idea; the difference is that here the snapshots of the tables count as changes too.

### 4. What happened last night

A number is wrong in the morning. Today it is the scheduler's log, then the warehouse's query history, then git. With the product `lakelet changes` is one list, newest first: every table's snapshots, every run of every model, every commit, and each snapshot names the models it made out of date. Lineage says what feeds the wrong number, and the model's versions show whether the SQL changed.

*Built today.* The Changes feed, `affects` on every snapshot, lineage, versions. *Planned:* the schedule itself and the alert (Team tier); until then cron or CI runs `lakelet run` and the feed records it.

### 5. The two models that do not fit

Thirty-eight of forty models are green on the laptop. Two are not: the gauge says needs more machine. Today everything runs on the warehouse because two things do. With the product the tables are Iceberg in the team's bucket, so the warehouse they already pay for reads them as they are, and the two models can run there while the thirty-eight run here. The split is chosen per model by verdict, and a burst to a worker in their own account under a cap is the third option.

*Built today.* The bucket warehouse at `init`, `publish` for a table that started local, views recorded in the catalog as Iceberg views, the catalog served so Spark or Trino read and write through it. *Planned:* split execution by verdict (the spec's F1.4 and F2.4), burst (session 8), route-and-cap with the cost per engine.

### 6. The second person

A colleague joins. Today it is a laptop, a dev schema and credentials. With the product, eventually, both laptops point at one catalog over one bucket, with one history and one Changes feed. Today the catalog is per laptop and the bucket warehouse is single-writer, so two people are two truths. What works now: the colleague clones the repository, which is the models and the questions, attaches the same read-only prefixes, and re-imports the files.

*Not built, and the site must not say team.* The cheapest path to two people over one bucket is bring-your-own REST catalog, `remote-catalog-plan.md` R1 (R2 Data Catalog, Polaris, Lakekeeper), before a hosted one; then the Team tier.

## Where this persona hits walls today

- **Opening an existing project.** The profile-name bug, `sources.yml` unread, no compile pass. Scenario 1 is the door, and it is not open.
- **Dialect.** Their models are Snowflake or BigQuery SQL. `QUALIFY`, `DATEADD`, `FLATTEN`, JSON path syntax, and warehouse-specific macros do not compile on DuckDB; the cross-database macros cover some of it. A greenfield project has no wall; a migration hits this first.
- **Materialisations to check before the session.** `table` is a delete and an insert on a V2 table, and `view` is an Iceberg view. Whether `incremental` and dbt snapshots work through the catalog, and what they cost in delete files, is not established. A daily-rebuilt table accumulates delete files until `expire`, and `compact` is decided, not built.
- **Two people, one truth.** The per-laptop catalog and the single writer. The site says "solo today"; it must keep saying it.
- **The editor.** No watcher, no VS Code client. The rule is that the app is not an editor; whether this person accepts edit-there-look-here is the session's central question.
- **Loads.** Their loaders write to the warehouse. A loader that writes Parquet to a bucket works with attach and refresh; one that writes only to the warehouse leaves the third door (a pulled slice) as the way in.
- **Scheduling and alerts.** Theirs to run from cron or CI until the Team tier.

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- N3 step 4's two fixes, open-an-existing-project and the watcher, are this persona's and should stay just after the outsider sessions; the compile pass is the half of scenario 1 that saves the most face in a session.
- Check `incremental` and snapshots before the session, so the answer is known rather than discovered.
- The remote-catalog round's R1, bring your own catalog, is the "second person" for this persona and should come before a hosted catalog; the persona file agrees with the brief's order.
- Never say "team" on the site until scenario 6 is true.

## Questions for the outsider session

- Which warehouse and which dialect, and how many models fail to compile when the project is opened as it is.
- Do they accept editing in VS Code and looking in the app, or do they want the editor inside. Does the terminal alone hold them.
- Does `lakelet run --stale` replace their slim CI in their head, and do they trust the state a model shows.
- Is the Changes feed the morning-after answer, or do they still open the warehouse console.
- Do they already have a bucket, and would they put the tables there.
- How do they schedule today, and what would they need to stop.
- Would they pay for a shared catalog, and at what price. The PRD wants five of these statements in writing.
