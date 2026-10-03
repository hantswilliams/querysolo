---
title: QuerySolo developer docs
description: What is built, what is not, and how to run the core from source today.
section: Start
order: 0
---

QuerySolo is an open-source warehouse for one machine: Apache Iceberg tables on Parquet in a folder you own, a catalog that speaks the Iceberg REST spec, DuckDB as the engine, and a pre-flight gauge that says whether this machine can run a query before it runs. The Python package `querysolo` in `core/` is the core, driven by a CLI; the desktop app in `app/` is a window over it, running from source. Bursting to a cloud worker, the ask box and the MCP server are on the [marketing pages](/) as plans; they are not built yet.

## What exists

| Surface | State | Page |
|---|---|---|
| `querysolo init`, `import`, `sql`, `estimate`, `tables` | Built, tested on macOS; Ubuntu in CI | [Quickstart](/docs/install), [CLI](/docs/cli) |
| The gauge: Green, Yellow, Red, the sentence, exit codes, history | Built; constants are v0, tuned on one machine | [The gauge](/docs/gauge) |
| Importing files and folders into Iceberg, with the type coercion table | Built; six file types | [Tables](/docs/tables) |
| `tables attach`, `refresh`, `discover` for Parquet already in S3 | Built, tested against an in-process S3 mock and RustFS; the same suite runs against a real bucket by hand | [Tables](/docs/tables), [A real bucket](/docs/remote) |
| A warehouse in a bucket: `init --warehouse s3://…`, every table's files in the bucket, the whole product path against it | Built, September 18, 2026; the same store as the attach tests, a real bucket by hand | [A real bucket](/docs/remote) |
| `tables publish`: one local table moved into a bucket with every snapshot, weighed first, resumable | Built, September 18, 2026; tested on the S3 mock and in the app | [Tables](/docs/tables#publishing-a-table-into-a-bucket) |
| `querysolo changes`: everything that happened, newest first, across tables, models and versions; the Changes screen and the Recent strip on every detail | Built, September 18, 2026; nothing recorded, read from the catalog, history and git | [Tables](/docs/tables#what-happened-the-changes-feed) |
| The Iceberg REST catalog, `catalog serve`; DuckDB, pyiceberg, Spark 3.5 and Trino as clients | Built; Spark and Trino verified through Docker Compose | [Catalog](/docs/catalog) |
| Saved questions as dbt models with two checks; `dbt run` builds them through the catalog | Built; `dbt run` and `dbt test` pass on the generated project | [Questions](/docs/questions) |
| Every save is a version: `init` makes the project a git repository, a save is a commit, `querysolo versions` and `restore` | Built; git is a library in the package, so no `git` binary is needed and nothing reaches the network | [Questions](/docs/questions) |
| `querysolo run`: the dbt DAG with a verdict per model; `view` models as Iceberg views in the catalog (build with `querysolo run`, not `dbt run`; the page says why); each model's state (fresh, edited, upstream, never) with what changed, and `querysolo run --stale` | Built | [dbt and views](/docs/dbt) |
| `querysolo lineage`: what a table, view or model reads and what reads it, from the dbt manifest and the catalog, with how each edge is known | Built, September 16, 2026; table level (column level is a later day) | [Tables](/docs/tables#lineage), [HTTP API](/docs/api) |
| `querysolo serve`: the local HTTP API with a bearer token and Arrow results | Built; the app runs one per window | [HTTP API](/docs/api) |
| The desktop app: projects, drop-to-import with a preview, attaching a bucket, the SQL screen with the verdict before the rows, the streaming grid, the auto-chart, the table and view detail, the Models screen over `querysolo run` with each model's state, the Review of what changed and Run what changed, the Reads from / Feeds lines on every detail, the Lineage screen, the Changes screen and the Recent strip, the Versions section with Restore, Simple and Technical mode, Save as question, light and dark, the Gauge screen, crash recovery, settings | Built, from source; tested with Playwright against ten real sidecars on macOS and Ubuntu; no installer yet | [The desktop app](/docs/app) |
| `querysolo tables expire`, `querysolo gauge probe`, `querysolo config` | Built | [Tables](/docs/tables), [The gauge](/docs/gauge), [Config](/docs/config) |
| The trust round: a replace that keeps the old table until the new one is complete, attached files checked for rewrites, the gauge's fourth verdict (Not estimated), schema versions read back, `querysolo relocate` for a moved folder, the catalog refusing what a browser can send | Built, September 15, 2026; every sentence of the recovery page has a test | [Backups, crashes, upgrades and moves](/docs/recovery), [PRIVACY.md](https://github.com/hantswilliams/querysolo/blob/main/PRIVACY.md) |
| `querysolo audit network` | Built; measures zero outbound attempts on the quickstart, which builds a dbt model so `querysolo run` is covered too | [Quickstart](/docs/install) |
| Installers, brew tap, a PyPI release | Not yet | |
| Burst, `ask`, `mcp`, correction factors, `catalog attach` | Not yet | |
| A slice of a warehouse you do not own | Not yet; the third door, after the outsider sessions | |

## Versions

The package is `0.1.0.dev0` and is not on PyPI. It needs Python 3.12 or newer (3.13 is what the repo pins), DuckDB 1.5.x, pyiceberg 0.12, and the four DuckDB extensions `iceberg`, `httpfs`, `excel` and `aws`, which `querysolo init` downloads once. Every version ceiling is in `core/pyproject.toml`.

## How to read these pages

Start with the [quickstart](/docs/install), which is the same sequence the test suite runs end to end. The [CLI reference](/docs/cli) is generated from the CLI's own help text and cannot drift from the code. Everything else describes what a test asserts; where a page names a number (a budget, a timing), the number was measured on one machine and says so.

The source of truth for the design is the current brief in `build-sessions/` — `TASKS.md` names which one that is — and for the running state, `build-sessions/TASKS.md`. Where a doc page and the brief disagree, the brief wins and the page is wrong; [edit it](https://github.com/hantswilliams/querysolo/tree/main/web/src/content/docs).
