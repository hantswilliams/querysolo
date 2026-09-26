# The data scientist in a notebook

*Persona · written 2026-09-24 · Status: **assumed, not observed** — no session planned yet; named in the app conversation of this day as the cheapest unserved surface · Product name: Lakelet (working name; TBD\*).*

The solo analyst's fourth composite, seen from the notebook. Python first, SQL when it is shorter, pandas by habit and polars or DuckDB when pandas runs out. Their day is a kernel, and the product enters it only if it can be called from a cell. Today it cannot, except through the shell or the HTTP API.

## Who

A data scientist or quantitative researcher, alone or in a small team, at a company or a lab. Trains models, runs analyses, writes up. Data comes as a pull from a warehouse into a DataFrame, as Parquet in a bucket, or as a file somebody sent. Works in Jupyter or VS Code notebooks on a laptop, and sometimes on a cloud notebook that forgets everything when the session ends. Cares about which data a model was trained on and can rarely say. Hands work on as a notebook and a folder.

## Tools, and where the day goes

| Task | What they use | What they see |
|---|---|---|
| Get the data | `pd.read_sql` from the warehouse; `pd.read_csv`; `s3fs` and `pyarrow` for a bucket | ten minutes, then a memory error, discovered after the pull |
| Hold it | pandas; polars or DuckDB when it does not fit | no way to know before which one it will be |
| Transform | pandas chains, or `duckdb.sql("... from df")` | intermediate frames nobody else can use |
| Model | scikit-learn, statsmodels, torch; MLflow if the team has it | the model versioned, the data not |
| Version | git, badly, with notebooks; DVC or lakeFS if someone set it up | a notebook that ran once, in some order |
| Cloud | Colab, SageMaker, a Databricks notebook | the pull again every session |
| Share | the notebook, a PDF, a chart | the reviewer cannot rerun it |

## What hurts

- The pull that dies: eight million rows into pandas, and no way to know the size before asking.
- "Which data did this model train on" is a memory. The table has changed since.
- The feature table they built lives in a DataFrame, and the engineer who wants it in the warehouse cannot get it there.
- The notebook is the record, and the notebook is not reproducible.
- The cloud notebook re-pulls every session and cannot see the laptop's tables.
- Memory is discovered by running out of it.

## Scenarios

Each: the situation, what happens today, what happens with the product, and which parts are built. "Built" means on `main` today, macOS and Linux, per the README's status block.

### 1. The file that kills pandas

A six-gigabyte CSV. `read_csv` takes the memory and then the kernel. With the product the file is imported once into an Iceberg table, streaming, and every question after that is a query whose verdict says bytes, memory and seconds before it runs. The result comes back as Arrow, which pandas or polars take directly, and the memory number is a warning before the pull rather than a crash after.

*Built today.* Import, the verdict, the HTTP API returning an Arrow stream with the verdict in its headers. *To check:* the gauge's memory figure is DuckDB's for the query, not pandas' for the result; converting Arrow to pandas can double it, and the sentence should say which number it is. *Planned:* a Python entry point so the cell calls the core instead of the shell.

### 2. The pull from the warehouse

A year of events for a model. Today it is `pd.read_sql` and a coffee. With the product the slice is pulled once as an Iceberg table on the laptop with a `--where`, refreshed when they ask, and every query after that runs locally with a verdict. The cloud pull happens once, not every session.

*Planned.* The third door, `decisions-for-review_092426.md` N2. *Today:* if the slice already exists as Parquet in an S3 bucket, attach reads it in place.

### 3. Which data trained the model

Six weeks later a reviewer asks. Today the answer is a date and a guess. With the product every table is Iceberg, so every load and every replace is a snapshot with a timestamp, `describe` lists them, and the Changes feed puts them beside the commits of the SQL that built the features. The training run can record the snapshot id it read.

*Built today.* Snapshots kept and listed, `expire` with a retention, the Changes feed. *To check:* querying a table as of a past snapshot from the product. DuckDB's Iceberg reader can; whether the product exposes it is not established, and for this persona it is the feature.

### 4. The feature table the engineer wants

They built it in pandas. With the product the query that built it is a saved question, which is a model with two checks and a version, and the table is Iceberg that the engineer's Spark or warehouse reads without asking. `publish` moves it to the bucket when it is ready. A frame that was built in pandas rather than SQL goes in by writing Parquet and importing it.

*Built today.* Save as question, `lakelet run`, `publish`, import from Parquet. *Planned:* a Python entry that writes a DataFrame into a table in one call.

### 5. The notebook a reviewer can rerun

Today it is the notebook, a folder, and hope about cell order. With the product the project folder is a git repository, the models are SQL files, every save and run is a commit, lineage says what fed the features, and the notebook shrinks to the exploration and the plots while the record lives beside it. The reviewer copies the folder and runs it, or reads the tables with pyiceberg and never installs the product.

*Built today.* Git in the project, versions, lineage, the folder as the backup. *Planned:* the Python entry, so the cells that query do so through the core and are recorded as questions.

### 6. The cloud notebook

Colab or SageMaker, and the tables on the laptop. Today the pull again. With the product, if the warehouse is a bucket, the cloud notebook reads the Iceberg tables straight from it with pyiceberg. What it cannot do is find them, because the catalog is the laptop's SQLite; it reads the table's metadata by path instead.

*Built today.* The bucket warehouse, readable by any Iceberg reader by path. *Planned:* bring-your-own REST catalog (`remote-catalog-plan.md` R1), which gives the cloud notebook the same catalog the laptop has.

## Where this persona hits walls today

- **No entry point from a cell.** The core is Python and the product is a shell command and an HTTP API. A documented `import` and a cell magic are suggested in the session log of 2026-09-24 and are not in any brief.
- **PyPI.** This person installs with `pip` or `conda`, not a DMG. The PyPI release is the ship brief's S7 and is not out.
- **DataFrames in and out.** In: write Parquet, import it. Out: the Arrow stream. Both work; neither is one call.
- **Time travel to check.** Reading a past snapshot from the product is not established.
- **The cloud notebook sees the bucket, not the catalog.**
- **The memory figure.** The gauge's number is the engine's; the persona's question is pandas'. The sentence should say which.
- **Windows.** As every persona.

## What this suggests for the order

Suggestions, not decisions; the box goes in a decisions file.

- The Python entry is the cheapest surface there is and unlocks this persona whole. It belongs in the same decision as the MCP server: the two surfaces where the verdict has to be, and neither is the window.
- For this persona PyPI matters more than the DMG; S7 should not slip behind the signing.
- Bring-your-own catalog before a hosted one, for the cloud-notebook case as much as for the dbt team.
- Check time travel before promising scenario 3.

## Questions for the session

- Jupyter or VS Code; pandas or polars; laptop or cloud.
- Where the data comes from, and how big the usual pull is.
- Would they call the core from a cell if they could, and what should the call return: a DataFrame, Arrow, a table name.
- Do they care which snapshot a model trained on, or is that the reviewer's question and not theirs.
- How do they hand work on today, and what would the folder need to contain for that to be the product's folder.
