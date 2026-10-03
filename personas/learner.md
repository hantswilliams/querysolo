# The learner

*Persona · written 2026-09-24 · Status: **assumed, not observed** · The PRD's P2 and the Day 1 launch audience; not a Day 0 design partner · Product name: QuerySolo.*

The person the DataExpert article was written for: "DuckDB just put a $400K/year skill on your laptop." They want the real stack, Iceberg and dbt and a catalog, because the job postings say so, and they cannot pay for it. The honest competition is not a warehouse. It is a Medium post and `pip install duckdb`, and a BigQuery sandbox that is free and real. The product's answer to that is not the tables; it is the verdict and the record, and the one lesson nobody else's tutorial can teach.

## Who

A career-changer or a junior, self-taught, in a bootcamp, or in a course. Builds portfolio projects on GitHub. Follows tutorials, watches videos, reads the "laptop lakehouse" posts. Has an old or small laptop, often Windows. Has been burned by a Docker Compose of nine services that broke on step four, and by a free tier that asked for a card. Nobody reviews their SQL. A recruiter looks at the README and cannot run the project.

The instructor is the same persona from the other side: needs thirty laptops to behave the same, offline in a classroom, and a dataset that fits.

## Tools, and where the day goes

| Task | What they use | What they see |
|---|---|---|
| The stack | a Docker Compose from a tutorial: Postgres, Airbyte, dbt, Metabase | hours on setup, none on the ideas |
| A warehouse | the BigQuery sandbox, a Snowflake trial, Databricks Community Edition, MotherDuck free | real, until the quota or the trial ends; an upload every time |
| A lakehouse | a Medium post with DuckDB, pyiceberg and a SQLite catalog | it works once, in a notebook, and they cannot say what a catalog is |
| dbt | jaffle_shop against DuckDB | the models run; nothing says whether they should |
| The project | a GitHub repository with a README and screenshots | a recruiter cannot run it |
| Help | ChatGPT, a Discord, the tutorial's comments | an answer for a different version |

## What hurts

- Setup is the whole course. The concepts never arrive.
- Free tiers end, bill, or want a card.
- They cannot tell the real thing from a toy, and they fear learning a toy.
- Nobody tells them a query was bad or a model unnecessary; nothing pushes back.
- The portfolio project is a README because nobody can run it.
- The laptop is small and the dataset that would be impressive is not.

## Scenarios

Each: the situation, what happens today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. The first lakehouse, in ten minutes

Today it is a Compose file or a notebook. With the product it is the README's ten minutes: `init`, four CSVs into Iceberg tables, a query with a verdict, a saved question that is a dbt model, a run, a version. A real catalog, real Iceberg metadata Spark would read, dbt, git. Nothing to configure and nothing uploaded. The point to teach is not that a table exists; it is that the verdict said why the query fit.

*Built today,* from source; the installer and the brew tap are the ship brief. *Missing:* the tutorial itself. The Day 1 exit criterion is one course, tutorial or chapter that uses the product as its lakehouse, and none exists.

### 2. The lesson only this stack can teach: what a table format costs

Hasan's experiment as a lab. Append two hundred times and watch `describe`'s file count climb and the verdict's seconds with it; then expire, then compact, and watch it recover. The learner sees with their own eyes that a lakehouse is a maintenance job, which is the thing the job will actually ask of them and the thing no tutorial shows.

*Built today.* `describe` with what is reclaimable, `expire` with a retention. *Planned:* `compact` (V2) and the needs-maintenance verdict. Until compact exists the lab ends at the problem.

### 3. The portfolio project a recruiter can run

Today a README with screenshots. With the product the repository is the project: the models as SQL, the sample generator or a small CSV, `querysolo run` to rebuild it, lineage and the Changes feed as the documentation that writes itself. The recruiter installs the product, copies the folder, runs one command.

*Built today* except the recruiter's install, which is the ship brief; data files stay out of git by rule, so the project commits its generator.

### 4. Outgrowing the laptop, on purpose

The impressive dataset is fifty gigabytes in a public bucket. Today they download it or give up. With the product they attach the prefix with no credentials, ask a question that touches three files, and see green; ask for the whole thing and see Red with the minutes at their bandwidth. The three moves on Red are the lesson: wait, read less, or point a bigger engine at the same tables. The burst is the fourth, later.

*Built today.* Anonymous attach, the verdict, the bandwidth sentence. *Planned:* burst.

### 5. Learning with an agent beside them

They use Claude Code or Cursor to learn. The project's `AGENTS.md` tells the agent what the tables are, what the gauge means and how to behave; the agent runs the commands and explains the verdict. The site's `llms.txt` gives the agent the docs.

*Built today.* `AGENTS.md` written by `init`, the CLI, `llms.txt`. *Planned:* the MCP server, so the agent's tools carry the verdict rather than parsing it.

### 6. The classroom

Thirty laptops, no reliable network, a two-hour session. Today: half the room stuck on Docker. With the product the instructor needs an installer that works on every machine in the room, offline after the one download at `init`, with a dataset that fits a small laptop and a gauge that behaves the same on each.

*Built today.* Offline after `init`, proven by `audit network`; the sample generator. *Blocked:* Windows, which is half the room; the installer; and the gauge's constants tuned on one 64 GB machine, so the verdicts differ by laptop until the reference calibration file exists (E4 in the session log).

## Where this persona hits walls today

- **Install from source.** A clone and `uv` is the same wall as the Compose file. The installer, the brew tap and PyPI are the ship brief.
- **Windows.** Students run it. Untried.
- **No tutorial.** The product without a lesson is another Medium post's stack.
- **The sandbox comparison.** The BigQuery sandbox is free, real and needs no install. The honest answer is the open format, nothing uploaded, and the verdict; the site should make that comparison rather than avoid it.
- **No compact,** so the best lesson stops halfway.
- **The name collision.** A search for the working name finds another lakehouse engine on GitHub first. *(Resolved 2026-09-30: that was the old name, Lakelet; QuerySolo is clear on GitHub and the registries.)*

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- Nothing in the build order changes for this persona: they are the Day 1 audience and the installer and Windows are their gates, both already on the list.
- The tutorial is content, not code, and the maintenance lab is the chapter that is uniquely ours; write it when compact lands.
- The reference calibration file matters here more than anywhere, because a classroom is thirty different machines seeing the same query.

## Questions for a session

- Which laptop and operating system, and could they install the unsigned build.
- Which tutorial they last followed and where it broke.
- After the ten minutes, can they say what the catalog is for, and what the verdict said.
- Would they put the project on GitHub, and could a friend run it.
- For the instructor: what dataset, what machine floor, and whether offline is a requirement or a preference.
