---
title: CLI reference
description: Every querysolo verb with its arguments and options, generated from the CLI's own help text.
section: Reference
order: 1
---

Generated from `querysolo --help` and every subcommand's help at version `0.1.0.dev0`
by `web/scripts/gen-cli-reference.py`. Do not edit by hand; re-run the script after a
CLI change.

Every verb runs against the project in the current folder; `-C <path>` points at another
one, and `--profile <name>` names the AWS profile for a private bucket, as `AWS_PROFILE`
would ([credentials](/docs/remote#credentials)). The gauge line goes to stderr and rows to stdout, so `querysolo sql … > out.csv` keeps
the two apart. Exit codes: `0` ran; `1` an error, named on stderr; `2` a Red verdict that
was refused (add `--run-anyway`); `4` a catalog conflict after retries.

## `querysolo`

```text
Usage: querysolo [OPTIONS] COMMAND [ARGS]...

  Your laptop is the warehouse until it can't be.

Options:
  --version             Print the version and exit.
  -C, --project <path>  The project folder; the current folder by default.
  --profile <name>      The AWS profile for a private bucket, as AWS_PROFILE names it.
  --help                Show this message and exit.

Commands:
  init      Turn a folder into a lakehouse: catalog, warehouse, querysolo.toml,...
  import    Import a file or a folder of files into Iceberg tables.
  sql       Run SQL: the gauge line first (stderr), then the rows (stdout).
  estimate  The gauge only: verdict, bytes, memory, time, the burst half.
  run       Build the project's dbt models through the catalog, each with its...
  versions  The versions of one question or model: every commit that changed its...
  restore   Put an earlier version of a question or model back.
  lineage   What a table, view or model reads and what reads it, and how each edge...
  changes   Everything that happened to the project, newest first: every table's...
  relocate  After the project folder was moved or copied: rewrite every local...
  serve     Run the core as the app's sidecar: catalog and API on one loopback...
  tables    List, describe and sample tables.
  catalog   The Iceberg REST catalog.
  question  Saved questions: dbt models with checks.
  gauge     The gauge's record.
  audit     Prove what leaves the machine.
  config    The settings in querysolo.toml.
  bucket    A bucket you own, before a project uses it.
```

### `querysolo init`

```text
Usage: querysolo init [OPTIONS] [directory]

  Turn a folder into a lakehouse: catalog, warehouse, querysolo.toml, AGENTS.md, dbt
  project.

Arguments:
  directory  The folder to turn into a lakehouse.  [default: .]

Options:
  --name <str>       Project name; the folder's name by default.
  --probe-mb <int>   Size of the disk-throughput probe; 0 skips it.  [default: 512]
  --warehouse <str>  An s3://bucket/prefix for the tables' files; warehouse/ by default.
  --help             Show this message and exit.
```

### `querysolo import`

```text
Usage: querysolo import [OPTIONS] {path}

  Import a file or a folder of files into Iceberg tables.

Arguments:
  path  A .csv .tsv .parquet .json .jsonl .xlsx file, or a folder.  [required]

Options:
  --name <str>  Table name; from the file name by default.
  --replace     Drop and recreate an existing table.
  --append      Append to an existing table.
  --preview     Show the inferred schema and stop.
  --help        Show this message and exit.
```

### `querysolo sql`

```text
Usage: querysolo sql [OPTIONS] [query]

  Run SQL: the gauge line first (stderr), then the rows (stdout).

Arguments:
  query  The SQL; or use -f.

Options:
  -f, --file <path>    Read the SQL from a file.
  --format <str>       table, csv, json or parquet; table on a terminal, csv when piped.
  -o, --output <path>  Write the result to a file.
  --run-anyway         Run a Red verdict here regardless.
  --limit <int>        Rows shown as a table.  [default: 1000]
  --help               Show this message and exit.
```

### `querysolo estimate`

```text
Usage: querysolo estimate [OPTIONS] [query]

  The gauge only: verdict, bytes, memory, time, the burst half. Nothing runs.

Arguments:
  query  The SQL; or use -f.

Options:
  -f, --file <path>  Read the SQL from a file.
  --json             The numbers as JSON instead of the line.
  --help             Show this message and exit.
```

### `querysolo run`

```text
Usage: querysolo run [OPTIONS] [select]...

  Build the project's dbt models through the catalog, each with its verdict first. A
  `view` model becomes a view in the catalog; a `table` model an Iceberg table. The DAG
  says each model's state: fresh, edited, upstream (an input changed) or never.

Arguments:
  select...  dbt selectors; none means every model.

Options:
  --burst <str>  never (here) or auto (session 8; refuses today).  [default: never]
  --run-anyway   Run the DAG here even if a model is Red.
  --plan         Print the DAG with its verdicts and stop.
  --stale        Build only what is not fresh: edited, an input changed, or never built.
  --help         Show this message and exit.
```

### `querysolo versions`

```text
Usage: querysolo versions [OPTIONS] {name}

  The versions of one question or model: every commit that changed its SQL or its
  checks, newest first.

Arguments:
  name  A saved question's slug, or a model's name.  [required]

Options:
  --limit <int>  How many versions to list; newest first.  [default: 20]
  --help         Show this message and exit.
```

### `querysolo restore`

```text
Usage: querysolo restore [OPTIONS] {name} {version}

  Put an earlier version of a question or model back. The restore is itself a version;
  nothing in the history is rewritten.

Arguments:
  name     A saved question's slug, or a model's name.  [required]
  version  A version id, or any unambiguous prefix.  [required]

Options:
  --help  Show this message and exit.
```

### `querysolo lineage`

```text
Usage: querysolo lineage [OPTIONS] [name]

  What a table, view or model reads and what reads it, and how each edge is known: a dbt
  ref() or source(), a table named in the SQL, or a catalog view's SQL. From the last
  compile's manifest and the catalog; compiles first when the models are newer. --all
  prints the whole graph, as the app's Lineage screen draws it.

Arguments:
  name  A table, a view or a model; none with --all.

Options:
  --depth <int range>  How many levels each way; 1 is direct.  [default: 1; x>=1]
  --all                The whole project: every node and its state, every edge.
  --json               The same as the API returns.
  --help               Show this message and exit.
```

### `querysolo changes`

```text
Usage: querysolo changes [OPTIONS] [name]

  Everything that happened to the project, newest first: every table's snapshots (and
  the models each made out of date), each model's and question's last run, and the
  versions git holds for the models. Read from what is there; nothing is recorded.

Arguments:
  name  Only what happened to this table, model or question.

Options:
  --since <str>       2d, 12h, 30m, 1w, or an ISO date.
  --last <int range>  At most this many entries.  [default: 50; x>=1]
  --json              The same as the API returns.
  --help              Show this message and exit.
```

### `querysolo relocate`

```text
Usage: querysolo relocate [OPTIONS]

  After the project folder was moved or copied: rewrite every local table's locations
  under this folder so the tables resolve again. Every snapshot is kept; the old
  metadata files become orphans for `tables expire`. Tables attached from a bucket are
  skipped.

Options:
  --help  Show this message and exit.
```

### `querysolo serve`

```text
Usage: querysolo serve [OPTIONS]

  Run the core as the app's sidecar: catalog and API on one loopback port, named in
  .querysolo/serve.json with a per-launch token.

Options:
  --port <int>          A fixed port; 0 picks a free one.  [default: 0]
  --host <str>          Loopback only in v0.  [default: 127.0.0.1]
  --memory-limit <str>  DuckDB memory limit for this process, e.g. 8GB; the app sets one
                        per window.
  --help                Show this message and exit.
```

### `querysolo tables`

```text
Usage: querysolo tables [OPTIONS] COMMAND [ARGS]...

  List, describe and sample tables.

Options:
  --help  Show this message and exit.

Commands:
  list      Tables in the catalog with rows, size, when they were last written, and...
  rename    Rename a table: one catalog commit, the data does not move.
  describe  Columns, types, partitioning, freshness and the last commit of a table.
  publish   Move a table built here into a bucket, every snapshot kept: its files...
  expire    Drop snapshots older than the retention and delete the files only they...
  sample    The first rows of a table.
  attach    Register remote data as a read-only Iceberg table without copying it.
  refresh   Add the files new under a registered prefix since it was attached.
  discover  Candidate prefixes under a bucket, with their size and kind.
```

#### `querysolo tables list`

```text
Usage: querysolo tables list [OPTIONS]

  Tables in the catalog with rows, size, when they were last written, and location.

Options:
  --help  Show this message and exit.
```

#### `querysolo tables rename`

```text
Usage: querysolo tables rename [OPTIONS] {old} {new}

  Rename a table: one catalog commit, the data does not move. Finishes a replace that
  was interrupted between its drop and its rename.

Arguments:
  old  [required]
  new  [required]

Options:
  --help  Show this message and exit.
```

#### `querysolo tables describe`

```text
Usage: querysolo tables describe [OPTIONS] {name}

  Columns, types, partitioning, freshness and the last commit of a table.

Arguments:
  name  [required]

Options:
  --help  Show this message and exit.
```

#### `querysolo tables publish`

```text
Usage: querysolo tables publish [OPTIONS] {name} {prefix}

  Move a table built here into a bucket, every snapshot kept: its files are copied under
  the prefix, its metadata written again there, and the catalog moved to it in one
  commit. The local files become orphans `tables expire` sweeps. An interrupted publish
  resumes: files already in the bucket at the same size are not copied twice.

Arguments:
  name    A table QuerySolo wrote, under the local warehouse.  [required]
  prefix  s3://bucket/prefix; the table goes under main/.  [required]

Options:
  --dry-run  Count and weigh the files; move nothing.
  --yes      Publish even if the copy would take longer than the cap.
  --help     Show this message and exit.
```

#### `querysolo tables expire`

```text
Usage: querysolo tables expire [OPTIONS] [name]

  Drop snapshots older than the retention and delete the files only they referenced,
  plus any file under the table that no snapshot references and that is over an hour old
  (what a previous --replace left). The current snapshot always stays; a table
  registered with `tables attach` is never touched. The one verb that deletes data
  files.

Arguments:
  name  A table; or --all.

Options:
  --all              Every table QuerySolo wrote.
  --keep-days <int>  Days of snapshots to keep; querysolo.toml's by default.
  --help             Show this message and exit.
```

#### `querysolo tables sample`

```text
Usage: querysolo tables sample [OPTIONS] {name}

  The first rows of a table.

Arguments:
  name  [required]

Options:
  -n <int>  Rows to show.  [default: 5]
  --help    Show this message and exit.
```

#### `querysolo tables attach`

```text
Usage: querysolo tables attach [OPTIONS] {name} {source}

  Register remote data as a read-only Iceberg table without copying it.

Arguments:
  name    [required]
  source  s3://bucket/prefix/ of Parquet, or a …metadata.json  [required]

Options:
  --metadata-in-bucket  Keep the Iceberg metadata under s3://bucket/_querysolo/.
  --anonymous           A public bucket: read it without credentials (metadata stays
                        local).
  --replace             Register the prefix again over an existing table (after files
                        changed).
  --help                Show this message and exit.
```

#### `querysolo tables refresh`

```text
Usage: querysolo tables refresh [OPTIONS] {name}

  Add the files new under a registered prefix since it was attached. Refuses if a
  registered file is gone or was rewritten under the same path since the attach.

Arguments:
  name  [required]

Options:
  --help  Show this message and exit.
```

#### `querysolo tables discover`

```text
Usage: querysolo tables discover [OPTIONS] {prefix}

  Candidate prefixes under a bucket, with their size and kind.

Arguments:
  prefix  s3://bucket/ or s3://bucket/prefix/  [required]

Options:
  --anonymous  A public bucket: list it without credentials.
  --help       Show this message and exit.
```

### `querysolo catalog`

```text
Usage: querysolo catalog [OPTIONS] COMMAND [ARGS]...

  The Iceberg REST catalog.

Options:
  --help  Show this message and exit.

Commands:
  serve  Expose the project's Iceberg REST catalog on a fixed loopback port.
```

#### `querysolo catalog serve`

```text
Usage: querysolo catalog serve [OPTIONS]

  Expose the project's Iceberg REST catalog on a fixed loopback port.

Options:
  --port <int>  A fixed port for Spark, Trino, pyiceberg and other DuckDBs.  [default:
                8181]
  --host <str>  Loopback only in v0.  [default: 127.0.0.1]
  --help        Show this message and exit.
```

### `querysolo question`

```text
Usage: querysolo question [OPTIONS] COMMAND [ARGS]...

  Saved questions: dbt models with checks.

Options:
  --help  Show this message and exit.

Commands:
  save  Save a question as a dbt model with two default checks.
  list  Saved questions with their last run.
  run   Run a saved question: the gauge first.
```

#### `querysolo question save`

```text
Usage: querysolo question save [OPTIONS] {title}

  Save a question as a dbt model with two default checks.

Arguments:
  title  [required]

Options:
  -f, --file <path>  Read the SQL from a file.
  --sql <str>        The SQL inline.
  --help             Show this message and exit.
```

#### `querysolo question list`

```text
Usage: querysolo question list [OPTIONS]

  Saved questions with their last run.

Options:
  --help  Show this message and exit.
```

#### `querysolo question run`

```text
Usage: querysolo question run [OPTIONS] {slug}

  Run a saved question: the gauge first.

Arguments:
  slug  [required]

Options:
  --format <str>       table, csv, json or parquet.
  -o, --output <path>
  --run-anyway
  --limit <int>        [default: 1000]
  --help               Show this message and exit.
```

### `querysolo gauge`

```text
Usage: querysolo gauge [OPTIONS] COMMAND [ARGS]...

  The gauge's record.

Options:
  --help  Show this message and exit.

Commands:
  probe    Measure local disk throughput again and record it for the gauge (a...
  export   Write the calibration record as JSON lines: fingerprint, machine class,...
  reset    Forget every recorded run and what the gauge learned from them.
  history  Recent runs: verdict, estimate, actual.
```

#### `querysolo gauge probe`

```text
Usage: querysolo gauge probe [OPTIONS]

  Measure local disk throughput again and record it for the gauge (a project set up
  before September 11, 2026 measured the page cache, not the disk).

Options:
  --mb <int>  Size of the probe file.  [default: 512]
  --help      Show this message and exit.
```

#### `querysolo gauge export`

```text
Usage: querysolo gauge export [OPTIONS]

  Write the calibration record as JSON lines: fingerprint, machine class, operator
  counts, estimate, actual. Never SQL, table or column names, or values (PRD F0.3.9).

Options:
  --out <str>  Where to write; '-' for stdout. Default:
               .querysolo/exports/gauge-<time>.jsonl
  --help       Show this message and exit.
```

#### `querysolo gauge reset`

```text
Usage: querysolo gauge reset [OPTIONS]

  Forget every recorded run and what the gauge learned from them.

Options:
  --yes   Do not ask.
  --help  Show this message and exit.
```

#### `querysolo gauge history`

```text
Usage: querysolo gauge history [OPTIONS]

  Recent runs: verdict, estimate, actual.

Options:
  --last <int>  Runs to show.  [default: 20]
  --help        Show this message and exit.
```

### `querysolo audit`

```text
Usage: querysolo audit [OPTIONS] COMMAND [ARGS]...

  Prove what leaves the machine.

Options:
  --help  Show this message and exit.

Commands:
  network  Run the quickstart with outbound connections blocked and report every...
```

#### `querysolo audit network`

```text
Usage: querysolo audit network [OPTIONS]

  Run the quickstart with outbound connections blocked and report every attempt.

Options:
  --help  Show this message and exit.
```

#### `querysolo audit _run`

```text
Usage: querysolo audit _run [OPTIONS]

  The audit itself, in this process (what `audit network` spawns when frozen).

Options:
  --help  Show this message and exit.
```

### `querysolo config`

```text
Usage: querysolo config [OPTIONS] COMMAND [ARGS]...

  The settings in querysolo.toml.

Options:
  --help  Show this message and exit.

Commands:
  show  The settings a hand or the app may change, with their current values.
  set   Set one setting in querysolo.toml, leaving the rest of the file as it was.
```

#### `querysolo config show`

```text
Usage: querysolo config show [OPTIONS]

  The settings a hand or the app may change, with their current values.

Options:
  --help  Show this message and exit.
```

#### `querysolo config set`

```text
Usage: querysolo config set [OPTIONS] {key} {value}

  Set one setting in querysolo.toml, leaving the rest of the file as it was. The engine
  reads its settings at start, so a running `querysolo serve` keeps the old ones.

Arguments:
  key    engine.memory_limit, engine.threads or gauge.share_calibration.  [required]
  value  auto or a size; auto or a count; true or false.  [required]

Options:
  --help  Show this message and exit.
```

### `querysolo bucket`

```text
Usage: querysolo bucket [OPTIONS] COMMAND [ARGS]...

  A bucket you own, before a project uses it.

Options:
  --help  Show this message and exit.

Commands:
  check  Try a bucket the way a project would (decisions P1): the credentials in...
```

#### `querysolo bucket check`

```text
Usage: querysolo bucket check [OPTIONS] {prefix}

  Try a bucket the way a project would (decisions P1): the credentials in the
  environment, a list of the prefix, one object written under it and removed. Nothing is
  created; no project is needed. Exit 1 when the prefix cannot be written.

Arguments:
  prefix  s3://bucket/prefix the project's tables would use.  [required]

Options:
  --json  The result as JSON.
  --help  Show this message and exit.
```

