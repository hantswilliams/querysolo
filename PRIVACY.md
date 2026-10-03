# Privacy

QuerySolo runs on your machine and keeps everything there. This file says exactly what that means, in the same words the tests use, so the claim on the website ("nothing leaves your machine") stays precisely as true as the code.

## What is stored, and where

Everything about a project lives in its folder:

| What | Where | Contains |
|---|---|---|
| The catalog | `.querysolo/catalog.db` (SQLite) | table names and the location of each table's Iceberg metadata; the schema version and which QuerySolo wrote it |
| The tables | `warehouse/` | Parquet data files and Iceberg metadata, both open formats any engine can read |
| The query record ("history") | `.querysolo/history.db` (SQLite) | every statement run through QuerySolo: its **SQL text**, the gauge's estimate, what actually happened, the machine profile it ran on |
| Saved questions and models | `models/`, `schema.yml`, `macros/` | SQL files and their checks; committed to the project's own git repository, never pushed anywhere by QuerySolo |
| Caches | `.querysolo/cache/` | manifest statistics, and for attached buckets a copy of their Iceberg metadata |
| The app's session | `.querysolo/serve.json` (mode 0600) | the loopback port and the per-launch token, removed on close |

The query record keeps your SQL. It is the record the gauge learns from, it never leaves the folder, and `querysolo gauge reset` deletes it. `querysolo gauge export` writes a calibration file into the project — one line per run with the machine profile in coarse buckets, the operator counts, the estimate and the actual — and **never** the SQL, the table names, the sentence or the error text (the fields are listed in `core/querysolo/gauge/export.py`). Sharing that file is a choice you make by sending it; QuerySolo does not.

`querysolo audit network` runs the quickstart — init, import, estimate, a query, a saved question, a `querysolo run` — with every outbound connection counted, and reports the number. It is zero, and the count is the test. One known blind spot: the audit counts connections, not name resolutions, so on a machine without DNS an attempt to reach a host by name would not be counted; the zero is measured on machines with DNS.

## What leaves the machine

Nothing, except what you ask for:

- `querysolo init` downloads DuckDB's Iceberg, httpfs, excel and aws extensions from `extensions.duckdb.org` once, and says so. Installers (session 10) bundle them, after which not even that.
- `querysolo tables attach`, `discover` and `refresh` read the bucket you name, with the credentials in your environment or none for a public bucket. Nothing is written to a bucket unless you asked for `--metadata-in-bucket`.
- QuerySolo holds no AWS key. A project names an AWS profile; the app reads the profile *names* from `~/.aws/config` and `~/.aws/credentials` to list them, never the keys, and never writes to those files. The name is kept on this machine (`projects.json` next to the app's recent list), not in the project.
- `--burst` (not built yet) will send a job to a worker in **your** cloud account, under a cost cap you set, and will say so before it does.
- `querysolo run` invokes dbt with its usage statistics turned off (`DO_NOT_TRACK=1`), and the profile QuerySolo writes for a `dbt` run by hand does the same.

There is no telemetry, no crash reporting, no update check, no account.

## The local server

`querysolo serve` (what the desktop app runs) and `querysolo catalog serve` bind **127.0.0.1 only**; a non-loopback host is refused. Two prefixes share the server:

- `/api/*` needs `Authorization: Bearer <token>` with the per-launch token from `serve.json`; without it, 401. CORS is granted to the app's own origins only.
- `/v1/*`, the Iceberg REST catalog, carries no token in local mode so that DuckDB, pyiceberg, Spark and Trino attach with zero configuration. Because loopback alone is not a boundary a browser respects, the server refuses, before any route runs: a request whose `Host` is not `127.0.0.1`, `localhost` or `::1` (DNS rebinding); any request with an `Origin` header on `/v1`, or one on `/api` that CORS does not allow (every browser sends one, no engine does); and any body that is not `application/json` (the `text/plain` and form posts a page can send without a preflight). `core/tests/test_trust_catalog.py` sends each and gets 403.

The same user who runs the server already has read-write access to `catalog.db`; the refusals are about pages in a browser, not about that user.

## SQL is code

`querysolo sql` runs whatever you type, and DuckDB can read local files and reach the network from SQL. That is a feature when the SQL is yours. When the SQL comes from somewhere else — a model in a project you cloned, an agent — treat it as you would code from that source. `querysolo mcp` (session 5) will run agent SQL with DuckDB's external access disabled and its configuration locked; until then, there is no agent path.

## Reporting a privacy problem

If QuerySolo sends something you did not ask it to, that is a bug of the most serious kind. `SECURITY.md` says how to report it privately.
