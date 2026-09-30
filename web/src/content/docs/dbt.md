---
title: dbt and views
description: querysolo run builds the project's dbt models through the gauge and the catalog; a view model is an Iceberg view in QuerySolo's catalog that every session and engine sees.
section: Guide
order: 5
---

A QuerySolo project is a dbt project: `init` writes `dbt_project.yml` with `models: +database: querysolo`, and every saved question is a model under `models/questions/`. `querysolo run` is how the models get built.

> **If you already use dbt, the one thing to know: build with `querysolo run`, not `dbt run`.** Both build your `table` models the same way, through the catalog. The difference is `view` models. `querysolo run` records every view in QuerySolo's catalog when the run finishes, so the app, the next `querysolo serve`, the CLI and Spark all see it. A bare `dbt run` cannot do that recording (the reason is under *Views*), so a view it builds exists for that dbt session only and is gone afterwards; dbt prints a line saying so for each one. `dbt run` can still *read* the views QuerySolo has recorded, so it is fine for checking a model or running `dbt test`. `querysolo run` also shows each model's verdict before anything is built, which `dbt run` never will.

```bash
querysolo run                       # every model, each with its verdict first
querysolo run stg_orders+           # dbt selectors, as `dbt run --select` takes them
querysolo run --plan                # the DAG with verdicts and states, nothing built
querysolo run --stale               # only the models that are not fresh, in dependency order
querysolo run --run-anyway          # build even where a model is Red
```

Needs dbt: `pip install 'querysolo[dbt]'` (dbt-core and dbt-duckdb; a clone's `uv sync` has them). Without it `querysolo run` says so and nothing else changes.

## What a run does

`querysolo run` compiles the project with dbt (into `.querysolo/dbt/`, with a `profiles.yml` it writes on every run, because the catalog's address is per process), then takes the models in dependency order and asks [the gauge](/docs/gauge) about each one's compiled SQL, giving the engine a view for each model as it goes so the models after it bind: a `view` model as itself, a `table` model not built yet as a stand-in over its query. That is the DAG it prints:

```
  stg_orders  view   green  ~0.0 s    fresh
  by_c        table  green  ~2 s      edited: the SQL changed since the last run
  top         view   green  ~0.0 s    upstream: by_c is out of date
```

If any model is Red the run stops there, the way `querysolo sql` refuses a Red statement, until `--run-anyway`; `--burst auto` is session 8's and refuses today with that sentence. Then dbt runs the DAG through QuerySolo's plugin (`querysolo.dbt.plugin`, which attaches the catalog to every connection dbt opens and sets the search path the engine uses), each model's estimate and dbt's actual time go into [history](/docs/gauge) like a query's, and every `view` model that built is recorded in the catalog as described next. `table` models build through the materialisation `init` writes into `macros/querysolo.sql` ([Transactions and the catalog](/docs/transactions) says why dbt's own cannot).

The same run is the app's **Models** screen: the plan as a list with a verdict and a state per model, a model's compiled SQL, what it reads and what reads it, its tests from `schema.yml`, its last run from history, **Run all**, **Run what changed** and **Run this** with the `querysolo run` line beside them, and the same refusal on Red. History keeps which run was which model (a `model_runs` table beside the runs), which is how the screen says when a model last ran. See [the app](/docs/app).

## Is it out of date?

The last column of the DAG is the model's state, computed at plan time from what the run already recorded, so it costs nothing new:

| State | Meaning |
|---|---|
| `fresh` | Nothing it is made of has changed since its last successful run. |
| `edited` | Its own SQL differs from what that run built (the compiled SQL's hash, kept in history). `--plan` and the app show the diff. |
| `upstream` | A table it reads has a newer snapshot than the run, a view it reads a newer version, or a model it reads is not fresh; the reason names the nearest one (`orders changed`, `by_c is out of date`) and when. |
| `never` | No successful `querysolo run` in history — never built, or the last run failed. |

`querysolo run --stale` plans the whole project and builds only the models that are not fresh, in dependency order; when every model is fresh it says so and nothing runs, nothing is recorded. The app's **Run what changed** (Simple: **Refresh what changed**) is the same verb, and its **Review** section lists every out-of-date model with what changed — the SQL diff since the run, or the commits to the table since — before you run it. Both `GET /api/run/plan` and `querysolo run --plan --json` carry `state`, `state_reason`, `state_since`, `state_diff` and `state_changes`.

What "changed" compares against is the time the run was recorded, not a fingerprint of the inputs: a model downstream of a table model is estimated before that table is rebuilt, so the snapshot ids an estimate sees are always one run behind, and comparing times against the record is exact.

## Views

**Why `dbt run` cannot record a view.** A dbt materialisation is SQL and only SQL. DuckDB has no SQL that creates a view inside an Iceberg catalog (`CREATE VIEW querysolo.main.v` is refused as not implemented), and the only other way for a dbt plugin to reach the catalog from inside a run, a Python function registered on the connection, needs numpy, which QuerySolo does not carry. So the recording has to happen from outside the run, and `querysolo run` is that outside: it runs dbt, then writes every `view` model that built into the catalog. A bare `dbt run` has no such afterwards, and its view models stay in that session.

DuckDB's Iceberg catalog cannot hold a view, so a `materialized: view` model lives in the session's `memory` database while dbt runs (`macros/querysolo_views.sql`, written by `init`, sends it there and every `ref()` to it follows), and `querysolo run` then records it in QuerySolo's catalog as an **Iceberg view**: a metadata file under `warehouse/main/<name>/metadata/` in the shape of the Iceberg view spec (format version 1), with one SQL representation in DuckDB's dialect and the schema of its result, and a row in the catalog. Every replace is a new version in that file; the earlier versions stay.

From then on the view is there for everyone: the engine of every later session (the CLI, `querysolo serve`, the app) creates a DuckDB view of the same name at start and after every change, so `select … from top` and the gauge work on it as on a table (the gauge sees through it to the tables it reads); a bare `dbt run` gets the catalog's views from the plugin, so a model may read a view that is not a dbt model; `querysolo tables list` shows it as `view`; and Spark or Trino read it through the [REST catalog](/docs/catalog)'s view routes. A view model removed from the project is dropped from the catalog on the next full run (a run with selectors drops nothing).

The recorded SQL names tables as `"main"."by_c"`, which DuckDB resolves through the search path (`querysolo.main`, then `memory.main`) and Spark through the default namespace, so the same text reads in both; a view that uses a DuckDB-only function is Spark's to refuse.

A view that is not a dbt model can be recorded from Python (`project.views.put(name, sql)`) and is listed and dropped the same way; `querysolo tables list` and `/api/tables` show `kind: view` with its SQL. A CLI verb for that waits until someone asks for it.

## Running dbt yourself

`dbt test`, `dbt compile`, `dbt docs`, or a `dbt run` to check one model: all fine, with two things in place. dbt needs a live catalog to attach to, and the profile that names it. `querysolo run` starts and stops its own catalog, so the profile it leaves in `.querysolo/dbt/profiles.yml` points at a port that is gone once it exits (a bare `dbt run` against it says *Could not connect to server*). Start one that stays up, and its profile is written for you:

```bash
querysolo catalog serve            # terminal 1: a catalog on a fixed port; prints the dbt line
dbt test --profiles-dir .querysolo/dbt      # terminal 2, in the project
dbt run  --profiles-dir .querysolo/dbt --select stg_orders
```

The app's core (`querysolo serve`) writes the same profile when it starts, so with the project open in the app the profile is live too. Whichever wrote it, the profile is good for as long as that process runs. And `view` models built this way are that session's only, as the callout at the top says; `querysolo run` is what records them.

## What dbt sees

The plugin runs on every connection: `LOAD iceberg; LOAD httpfs`, `ATTACH 'querysolo' … TYPE ICEBERG`, `SET search_path = 'querysolo.main,memory.main'`, then the catalog's views as DuckDB views in `memory.main`; on every cursor, the search path again, because dbt-duckdb runs models on cursors that do not inherit it. The profile is `.querysolo/dbt/profiles.yml`, written by whichever QuerySolo process is serving the catalog (`querysolo run` for its own run, `querysolo serve`, `querysolo catalog serve`), naming the plugin module `querysolo.dbt.plugin` and that catalog's URL.

## A run records a version

Before dbt builds anything, `querysolo run` commits the model files the manifest names that have changed since the last version, plus `dbt_project.yml` and the macros, as `run: stg, by_customer changed`. Nothing changed means no commit and no noise. That is what gives a model you edit in your own editor a history in the app: each run's version holds the SQL that run built, so `querysolo versions stg` has entries and not only saved questions do.

```toml
[git]
auto_commit = true    # false stops the commit a run makes
```

`querysolo config set git.auto_commit false` (or the switch in the app's settings, "Record a version on every save and run") turns the run-time commit off, for people who keep their own git and would rather commit by hand. Saving a question still commits, whatever this says: a save with no version is the one thing QuerySolo promises not to do. A `dbt run` you invoke yourself is never committed for — QuerySolo only records versions for its own verbs.

Nothing of yours is swept in either way: the commit carries the files named above and no others, so work you have staged or left uncommitted stays exactly as it was.

## Nothing leaves the machine, dbt included

dbt-core sends anonymous usage statistics to its own collector unless it is told not to. QuerySolo turns them off on both of the paths it controls, because "nothing leaves the machine" has to hold for the code QuerySolo calls as well as the code it wrote:

- `querysolo run` sets dbt's own `DO_NOT_TRACK` switch before every invocation, so `send_anonymous_usage_stats` is false and the tracker is inert for anything QuerySolo builds.
- the profile QuerySolo writes, `.querysolo/dbt/profiles.yml`, carries `config: send_anonymous_usage_stats: false`, so a `dbt run` or `dbt test` you run by hand against it — the section above — does not send anything either.

A profile of your own is your own business and QuerySolo does not touch it; these are the two it is responsible for.

`querysolo audit network` builds a model as part of its quickstart for this reason, so the zero it reports covers `querysolo run` rather than stopping at the verbs that never call dbt. Where dbt is not installed the audit says so on that line instead of failing.
