# The solo analyst with files, a bucket, or a warehouse they do not own

*Persona · written 2026-09-24 · Status: **assumed, not observed** — this is the first outsider session in `decisions-for-review_092426.md` N3 (step 2); the questions at the end are what it must answer · Product name: QuerySolo.*

This is N1's first user. They write SQL, or are willing to, which is what separates them from the PRD's P3, the non-developer with a question; that variant is noted at the end and is not served until the ask box exists. What separates them from the BigQuery or Databricks analyst (`analyst-bigquery-databricks.md`) is that nobody sends them the email about the expensive query. There is no platform team, no bill and no governance. The enemies are Excel's limits, pandas' memory, a folder of exports, and their own memory of what they did last month.

## Who

The only data person where they are, or a person of one. Four composites, one persona:

- **The analyst at a small company.** Ten to fifty people, no data team. Data arrives as exports: Stripe, the CRM, the shop platform, a Google Sheet somebody maintains, and a read-only login to the application's Postgres replica that an engineer set up once. They own the monthly numbers.
- **The consultant or freelancer.** A client's export under an NDA. Cannot upload it anywhere. Works on their own laptop and hands back a deck and a spreadsheet.
- **The researcher.** A public dataset in a bucket, or a departmental extract too big for Excel and too sensitive for a free cloud tier. No budget for a warehouse; a university laptop.
- **The data scientist doing an analysis.** pandas in a notebook, a six-gigabyte CSV, and no way to know before loading whether it will fit. (Their notebook life is its own persona, `data-scientist-notebook.md`; here they are the person with the file.)

Common to all: a laptop, usually 16 GB, Mac or Windows; no terminal habit to speak of, or a light one; nobody to ask when something breaks; and a strong preference that data does not leave the machine, either by policy or by instinct.

## Tools, and where the day goes

| Task | What they use | What they see |
|---|---|---|
| Open a file and look | Excel or Google Sheets | a million-row ceiling; dates and zip codes silently retyped; a crash at a few hundred megabytes |
| Anything bigger | pandas in Jupyter, or the DuckDB shell, or DBeaver | memory errors discovered after the load; no sense of what will fit before trying |
| The company's database | DBeaver or pgAdmin against a read replica, one query at a time | slow, and the engineer notices |
| A public dataset in a bucket | download the whole thing, or learn Athena, or give up | an hour and a full disk before the first question |
| Keep the analysis | a notebook that ran once; a folder of `final_v3_REAL.csv` | no history of which file made which number |
| Re-run it next month | copy the notebook, change the filename, hope | the numbers change and nothing says why |
| Share | a screenshot in Slack, a CSV by email, a chart pasted into a deck | the recipient cannot rerun it |
| A free warehouse | the BigQuery sandbox, a MotherDuck free tier, a Snowflake trial | an upload of data that should not be uploaded; a quota; a tier that ends |
| A coding assistant | ChatGPT or Claude in a browser, pasting column names | SQL that may or may not run against the file |

## What hurts

- Excel stops at a million rows and lies about types. pandas stops at a few gigabytes and says so only afterwards.
- Nothing tells them before they start whether the file, the query or the download fits on this machine.
- The public dataset is twenty gigabytes and the question needs three files of it, and there is no way to know that without downloading all of it.
- Last month's analysis is a notebook and a filename. This month's is a copy. Which file made the number in the deck is a memory, not a record.
- The result goes out as a screenshot. Nobody, including them in six months, can rerun it.
- Every free tier that would help asks them to upload data they should not upload.
- When it breaks there is nobody to ask.

## Scenarios

Each: the situation, what happens today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. The export that is too big for Excel

A two-gigabyte CSV of a year's transactions. Excel refuses, Sheets refuses, pandas takes a minute and then takes the memory. With the product it is a drop onto the window, a preview that shows every column's inferred type and the casts that lose something, a table in the project, and a verdict on the first question before it runs. The types are written down, so the zip code stays text.

*Built today.* Import for CSV, TSV, Parquet, JSON, JSONL and Excel; the preview with types and notes; the verdict; the chart. *Unmeasured:* the two-gigabyte import on a 16 GB laptop (the PRD's ninety-second target; the reference-laptop timings are an open item). *Untested against real exports:* header rows not on line one, thousands separators, European decimals, a workbook with six sheets. The session will find these.

### 2. The monthly re-run

Last month's analysis with this month's export. Today it is a copied notebook and a changed filename. With the product the new file replaces or appends to the table, the saved question is a model, `querysolo run` rebuilds it with a verdict first, the Versions section shows what the SQL was each time, and the Changes feed shows the new snapshot and that it made the model stale. The number in this month's deck has a commit behind it.

*Built today.* Replace or append on a re-import, save as question, `querysolo run`, run only what is stale, versions and restore, the Changes feed. *Planned:* the watcher, so the app notices a file changed in the folder (N3 step 4); a schedule (Team tier).

### 3. The public dataset in a bucket they do not own

An open dataset in S3: twenty gigabytes in thirty-two files. Today they download it all or learn Athena. With the product they attach the prefix with no credentials and nothing is copied. The gauge says a bounding-box question reads three of the thirty-two files and runs here, and that a full scan over the whole prefix is Red at their bandwidth, with the minutes it would take. Most Red verdicts for this person are bandwidth verdicts, and the sentence says so.

*Built today.* Attach a public S3 prefix anonymously; `/docs/remote` has the commands and the numbers for the Overture Maps demo. *Not built:* public datasets in GCS, or served over HTTP as a zip, which is how many of them come.

### 4. The warehouse they do not own

Read-only credentials to the company's Postgres replica, or a dataset a colleague shared with them in BigQuery. Today it is DBeaver, one query at a time, and the engineer notices. With the product they pull a slice as an Iceberg table on the laptop, the last year of orders with a `--where`, refresh it monthly, and iterate locally at speed with the gauge treating it as their own. The source and the filter are kept in the table's properties, never a password.

*Planned.* The third door, `decisions-for-review_092426.md` N2, after the outsider sessions. For this persona the first connector being Postgres is right: the read replica is a Postgres far more often than not. The BigQuery or Databricks analyst's file says the opposite; the two disagree and a decisions file must choose, with the sessions as the tiebreak.

### 5. The client data that cannot leave the laptop

A consultant's client export under an NDA, or a researcher's extract adjacent to health records. Today every tool that would help is a tool that uploads, so they stay in Excel and pandas. With the product the project is a folder on their disk, the only download is the DuckDB extensions at `init`, and `querysolo audit network` measures zero outbound attempts on the whole quickstart. `PRIVACY.md` says what is stored where in plain sentences they can hand to whoever asks.

*Built today.* The audit, the privacy page, the local-only catalog. *Planned, and off by default:* the ask box, which would send the schema and sample rows to a model provider; for this person a local model is the only version they would turn on.

### 6. Handing the work to someone else, or to themselves in six months

The analysis has to be reproducible: a colleague takes it over, a reviewer asks how the number was made, or they come back after a leave. Today it is a notebook, a folder and a README nobody wrote. With the product the project folder is a git repository, every save and every run is a commit, the models are SQL files anyone can read, lineage says what feeds what, and `querysolo changes` is the story in order. The recipient copies the folder and runs it. If they do not have the product, the tables are Parquet and Iceberg metadata, so pandas with pyiceberg, or Spark, reads them as they are.

*Built today.* Git in the project, versions, lineage, the Changes feed, the folder as the backup, relocate after a move. *Planned:* a shared page for the result (Day 2), and the Team tier for the case where the colleague is a permanent colleague.

## Where this persona hits walls today

- **No installer.** A clone and `uv sync` is the first wall for someone without a terminal habit, and for this person the first ten minutes are the whole product. Ship is in progress today: the freeze and the bundle are built, the unsigned `.app` and `.dmg` are the next Mac run, and signing waits on the Apple enrolment.
- **Windows.** The Power BI Desktop half of this persona runs it. macOS and Linux only, Windows untried.
- **No SQL, no product.** Simple mode still needs SQL in the box. The variant who has a question and no SQL is the PRD's P3, waits on the parked ask box (session 7), and is Duckle's for now. The site should say so rather than imply otherwise.
- **Messy files.** Real exports are not the sniffer's test set. Multi-sheet workbooks, header rows on line three, merged cells, mixed date formats. The import's behaviour on these is untested until a session produces them.
- **The 16 GB laptop.** The gauge's constants were tuned on a machine with 64 GB, and the two-gigabyte import has not been timed on the reference laptop. This person is the reference laptop.
- **Getting the answer out.** Their deliverable is a chart in a deck or a CSV to a colleague. The CLI writes CSV; whether the app's export and a chart image are one click is to check, and it is the last step of every scenario above.
- **Public data that is not in S3.** GCS buckets and HTTP downloads are not attachable.

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- Ship's first-run story is this persona's whole product. The installer matters more for them than for anyone else, which supports the order already chosen.
- The first connector for the warehouse door: this persona says Postgres, the previous says BigQuery or Databricks. The two outsider sessions decide it; until then Postgres, as N2 says, costs nothing to keep.
- After the session, write the messy-file cases it produced as import tests before anything else, because scenario 1 is the door everything else is behind.
- Export out of the app, and the chart as an image, are worth checking before the session, because every scenario ends there.
- The watcher matters less for this person than N3 step 4 implies; they edit in the app, not in an editor. It matters for the dbt persona.

## Questions for the outsider session

- Which machine and operating system, and can they install an unsigned app on it. If Windows, the session cannot happen yet.
- Where does their data actually come from: which exports, which replica, which bucket. Whichever it is, that is scenario 1's file, and it should be theirs, not our sample.
- What is the first file they try, and does the import survive it as it is.
- Do they reach a saved question unaided in forty minutes. Do they notice it became a model, and do they care.
- Do they read the verdict's sentence or only its colour. When it refuses, do they trust it, argue, or run anyway.
- When they come back "next month" with a second file, do they find replace or append, and do they find versions.
- What do they do with the answer: a chart in a deck, a CSV to someone, a number in Slack. That is the export the product must make trivial.
- Does "nothing leaves the machine" matter to them. Would they ever turn on a model provider, and would a local one change that answer.
