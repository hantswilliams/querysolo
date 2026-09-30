---
title: querysolo.toml and the project folder
description: Every setting the core reads, what init writes, and what lives where on disk.
section: Reference
order: 2
---

A QuerySolo project is a folder with a `querysolo.toml` in it. `querysolo init` writes the file below; the core reads four sections and carries every other section and unknown key through untouched, so a file written by a later version still opens in this one.

## The file `init` writes

```toml
[project]
name = "acme"
warehouse = "./warehouse"        # or s3://bucket/prefix, later

[catalog]
mode = "local"                    # local | team | external

[engine]
memory_limit = "auto"             # DuckDB default, 80% of RAM
threads = "auto"

[git]
auto_commit = true                # record a version on every save and run; false stops the
                                  # run-time commit, a save is a version either way

[gauge]
green_max_seconds = 60
yellow_max_seconds = 600
green_max_memory_fraction = 0.6
share_calibration = false         # CLI default off; the app asks on first run

[burst]                           # read from session 8 on
default = "prompt"
max_cost_per_run_usd = 5.00

[agents]                          # read from session 5 on
allow = []
```

## Sections the core reads

### `[project]`

| Key | Default | Meaning |
|---|---|---|
| `name` | the folder's name | The project's name; shows in `/api/health` and `dbt_project.yml`. Required. |
| `warehouse` | `./warehouse` | Where the catalog puts table data and metadata. A relative path is resolved against the project folder and becomes a `file://` URL. |

### `[catalog]`

| Key | Default | Meaning |
|---|---|---|
| `mode` | `local` | `local` is the only mode implemented: an embedded Iceberg REST server on a loopback port over `.querysolo/catalog.db`. `team` and `external` are accepted by the schema and not yet acted on. |
| `url` | none | Reserved for `team` and `external`. |
| `keep_snapshots_days` | `7` | How many days of table history `querysolo tables expire` keeps. The current snapshot always stays. Settable with `querysolo config set catalog.keep_snapshots_days N`. |

### `[engine]`

| Key | Default | Meaning |
|---|---|---|
| `memory_limit` | `auto` | Passed to DuckDB's `memory_limit`; `auto` leaves DuckDB's default of 80% of RAM. A string such as `"8GB"` sets it. The gauge reads the effective limit back from DuckDB, so a lower limit makes Yellow and Red more likely. |
| `threads` | `auto` | Passed to DuckDB's `threads`. |

### `[gauge]`

| Key | Default | Meaning |
|---|---|---|
| `green_max_seconds` | `60` | Above this estimated wall time the verdict is at least Yellow. |
| `yellow_max_seconds` | `600` | Above this it is Red. Also the window used to decide whether a remote table is Red for bandwidth. |
| `green_max_memory_fraction` | `0.6` | Green needs the estimated peak under this fraction of the memory limit; otherwise Yellow. |
| `share_calibration` | `false` | Reserved: whether anonymised estimate/actual pairs may leave the machine. Nothing reads it yet and nothing is sent. |

The verdict rule that uses these is on [the gauge](/docs/gauge) page.

### `[git]`

| Key | Default | Meaning |
|---|---|---|
| `auto_commit` | `true` | Whether `querysolo run` commits the model files it is about to build. `false` stops that; saving a question is a version either way. Settable with `querysolo config set git.auto_commit false`, or the switch in the app's settings. See [dbt and views](/docs/dbt). |

### `[burst]` and `[agents]`

Written so the file is already valid for the sessions that will read them; the core ignores them today. Keys you add anywhere in the file survive a round trip.

## The folder

| Path | Written by | What |
|---|---|---|
| `querysolo.toml` | `init` | The file above. |
| `AGENTS.md` | `init`, refreshed by `import` and `tables attach` | A short guide for coding agents working in the folder, with one block per table between markers that QuerySolo rewrites. Edit anything outside the markers. |
| `dbt_project.yml` | `init` (only if absent) | A minimal dbt project with `+database: querysolo`, so dbt-duckdb builds models into the catalog. |
| `models/` | `init` | dbt models. Saved questions land in `models/questions/`. |
| `macros/querysolo.sql` | `init` (only if absent) | QuerySolo's `table` materialisation for the Iceberg catalog, overriding dbt's built-in one for the project. See [Transactions and the catalog](/docs/transactions). |
| `tests/generic/returns_rows.sql` | first `question save` | The generic test every saved question carries. |
| `.gitignore` | `init` (lines appended, never overwritten) | `warehouse/`, `.querysolo/` and `.DS_Store`. |
| `.git/` | `init`, when the folder is not already in a repository | A git repository on branch `main`, whose first commit is what `init` wrote. Every save is a version in it; see [Questions](/docs/questions). A folder already inside a repository is used as it is. |
| `warehouse/main/<table>/` | the catalog, on every write | The Iceberg tables: `data/*.parquet` and `metadata/*.metadata.json`, manifests and manifest lists. Format version 2. |
| `.querysolo/catalog.db` | `init` | The catalog: namespaces, tables with their current metadata location, a `leased_until` column for later. SQLite in WAL mode. |
| `.querysolo/history.db` | first run | Every `sql`, `estimate`, and question run, with estimates and actuals. |
| `.querysolo/cache/machine.json` | `init`'s probe, the first remote attach | Local disk throughput, and bandwidth to the bucket once measured. |
| `.querysolo/cache/` | the gauge | Manifest statistics per table and snapshot, and immutable objects fetched from S3. Safe to delete; rebuilt on the next estimate. |
| `.querysolo/last-profile.json` | every statement | DuckDB's JSON profile of the last statement. |
| `.querysolo/serve.json` | `querysolo serve`, while it runs | `{port, pid, token, started}`, mode 0600; removed on exit. |

## Names

Table names and question slugs follow one rule: lower case; any run of other characters becomes one underscore; a leading digit gets a `t_` prefix. `import` derives a name from the file name (`Orders 2026.csv` becomes `orders_2026`), `--name` overrides it, and `question save "Orders by country"` makes `orders_by_country`. Namespaces are single level; every table is in `main` in v0, and a bare name in SQL resolves there.

## Environment

The core reads no settings from the environment except for remote data. `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` (or `AWS_DEFAULT_REGION`) and `AWS_ENDPOINT_URL` configure both DuckDB and pyiceberg for `tables attach`; with no keys set, both fall back to the AWS default credential chain. Credentials are never written to `querysolo.toml`.
