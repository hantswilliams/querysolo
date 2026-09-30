---
title: Saved questions
description: A question is a dbt model in the project with two checks; saving, listing and running one, and what dbt sees.
section: Guide
order: 4
---

A saved question is SQL with a title, kept as a dbt model in the project so it is a file in git, a node in a dbt DAG, and something `dbt test` can check. `querysolo init` writes a `dbt_project.yml` for this; you do not need dbt installed to save or run questions, only to run dbt itself.

## Saving

```bash
querysolo question save "Revenue by customer" --sql "select customer, sum(amount) as revenue from orders group by 1"
querysolo question save "Revenue by customer" -f revenue.sql
```

The slug is the title through the [naming rule](/docs/config): `revenue_by_customer`. Saving writes three things:

`models/questions/revenue_by_customer.sql`, the SQL under a two-line comment header:

```sql
-- Revenue by customer
-- saved by querysolo on 2026-09-09
select customer, sum(amount) as revenue from orders group by 1
```

An entry in `models/questions/schema.yml`, with the title as the description, `materialized: table`, and two default checks: a model-level `returns_rows` test, and `not_null` on the first column:

```yaml
models:
  - name: revenue_by_customer
    description: Revenue by customer
    config: {materialized: table}
    meta: {querysolo: {title: Revenue by customer, created: "2026-09-09T13:02:11+00:00"}}
    data_tests: [returns_rows]
    columns:
      - name: customer
        data_tests: [not_null]
```

And, the first time, `tests/generic/returns_rows.sql`, the generic test the first check names. The SQL is checked with `DESCRIBE` before anything is written, so a question that does not bind is refused. Saving the same title again updates the model in place and keeps its `created` date.

## Every save is a version

`querysolo init` makes the folder a git repository on branch `main` and commits the files it wrote as `querysolo init`. Every save after that is a commit of the files that save wrote:

```text
saved revenue_by_customer: models/questions/revenue_by_customer.sql (+ schema.yml entry with 2 checks)
version c1da45c
```

The message is `save question: <title>` the first time and `update question: <title>` after that; the author is git's own, read from the same configuration files git reads (`user.name` and `user.email` in the repository's config, yours, or the system's), and with none set it is the OS user at this host, which is what git itself falls back to. Saving a question that has not changed writes nothing and makes no commit: the line says `no change, so no new version`.

A commit carries the model file, the `schema.yml` entry and, on the first save of a project, the generic test — and nothing else. Your own work in the same repository is untouched: a file you have staged stays staged and out of QuerySolo's commit, and nothing is swept in with a `git add -A`. Anything `.gitignore` excludes can never be committed, so `warehouse/`, `.querysolo/` and the history database stay out by construction.

Git is a library in the package (dulwich), not the `git` binary, so none of this needs `git` installed; a `git` of your own on the same folder sees ordinary commits and can do everything else with them. Nothing here reaches the network — there is no fetch and no push — and `querysolo audit network` still reports zero.

Three things it does not do. It does not commit on a folder that is already inside a repository *at `init` time*: a dbt project you brought, or a subfolder of a monorepo, is used as it is and its first version is its first save. It does not sign: a `commit.gpgsign = true` in your configuration produces an unsigned commit rather than an error. And it never fails a save — if the repository cannot be written (a read-only folder, a broken `.git`), the files are still written and the response carries a `git:` line saying why there is no version.

## Saving one from the app

On the query screen, **Save as question** appears beside Run once the gauge has spoken — a statement that finished, one you stopped, or one it refused as Red. The title is the only thing it asks for; the slug comes from it by the same [naming rule](/docs/config) the CLI uses, and the box shows the file it will write and the two checks before you commit to it. What comes back names the checks and the version the save recorded, with the `querysolo question save` line beside it.

A title whose slug is already saved is refused rather than overwritten, and the box offers **Replace it** — the same shape as an import onto a table that exists. A Red statement can be saved: a question is allowed to be bigger than the machine you wrote it on.

The question is a model like any other, so it appears on the Models screen with its title as its description the next time that screen plans.

## The versions of one question

```bash
querysolo versions revenue_by_customer          # newest first; --limit 20 by default
querysolo restore revenue_by_customer 6c89b4f   # put an earlier version back
```

`versions` lists every commit that changed the question's `.sql` or its `schema.yml` entry: the version, when, who, the message, and what changed. A commit that touched only the checks is in the list, marked `checks changed`, because a change to the checks is a version of the question too.

`restore` writes that version's content over the current file, re-derives the `schema.yml` entry from it (the title is the file's first comment line, so the checks always match the SQL beside them), and commits the result as `restore question: <title> to <version>`. That is the whole of it: the restore is a new version, the history stays linear, and nothing is reset or rewritten. Any unambiguous prefix of a version works, which is why the list shows seven characters.

The same two verbs work on a model you wrote by hand — `querysolo versions stg` — because a model and a saved question are the same thing here: a file under `models/` with commits behind it. Neither verb compiles the project, so a version list costs no dbt run. A file with no commits says so rather than showing an empty list.

Over the [HTTP API](/docs/api) it is `GET /versions/{name}` (each version with the unified diff against the one before it), `GET /versions/{name}/{id}` for that version's SQL, and `POST /versions/{name}/restore`.

## Listing and running

```bash
querysolo question list                    # slug, title, created, last run
querysolo question run revenue_by_customer # the gauge line, then the rows; --format, --output, --run-anyway as for sql
```

`run` executes the question's SQL through the [gauge](/docs/gauge) exactly like `querysolo sql`, and when the result completes it records the run against the question, which is where `last_run` comes from. Nothing under `models/` is touched by a run. Over the [HTTP API](/docs/api) it is `GET /questions`, `POST /questions` and `POST /questions/{slug}/run`.

## What dbt sees

`init`'s `dbt_project.yml` is minimal: the project's name, `models/` as the model path, and `models: +database: querysolo`, so anything dbt builds lands in the catalog beside the tables it reads. With `dbt-core` and `dbt-duckdb` installed and a profile that attaches the catalog, `dbt parse` accepts the generated project and `dbt test` runs both checks against the question's table.

The attach happens through a dbt-duckdb plugin in the package, `querysolo.dbt.plugin`; [dbt and views](/docs/dbt) has what it does and how `querysolo run` builds the models with their verdicts first.

**Building it with dbt.** `querysolo run` builds the project's models with their verdicts first ([dbt and views](/docs/dbt); build with `querysolo run` rather than `dbt run`, because only `querysolo run` records `view` models in the catalog). `init` writes `macros/querysolo.sql`, a `table` materialisation for the Iceberg catalog that overrides dbt's built-in one for the project, so either verb builds every `materialized: table` model, saved questions included, through the catalog with nothing QuerySolo-specific in the model. A rebuild with unchanged columns keeps the table (a delete and an insert in one transaction: same identity, two new snapshots); a rebuild whose columns changed drops and recreates it. Why the built-in materialisation cannot do this, and what it costs, is on [Transactions and the catalog](/docs/transactions). `querysolo question run` still runs the question's SQL directly through the gauge; it does not build the table.
