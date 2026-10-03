---
title: Transactions and the catalog
description: What DuckDB-Iceberg refuses inside one transaction, why, and what it means for dbt and for your own SQL.
section: Guide
order: 5
---

Everything DuckDB's Iceberg documentation lists as supported works through QuerySolo's catalog: `CREATE` and `DROP` for schemas and tables, `INSERT`, `UPDATE`, `DELETE`, `MERGE INTO`, `ALTER TABLE` including `RENAME`, and `SELECT`. What the documentation does not describe is what happens *inside one transaction*, and that is where a pattern that is routine on DuckDB's own tables gets refused. This page is the list, with the exact error text, so that a search for the message lands here.

## Why there is a list at all

A DuckDB transaction against a native table is a private workspace: you can create a table, rename it, drop it and create it again, and only the end state matters at `COMMIT`. A DuckDB transaction against the Iceberg catalog is different: at `COMMIT` the extension turns what you did into Iceberg commits, one per table, each a new snapshot on a table whose identity is a UUID in the catalog. Three things have no clean meaning in that model, and rather than guess, the extension refuses them.

## What is refused

| Statement, inside one transaction | The error |
|---|---|
| `CREATE OR REPLACE TABLE t AS …` | `Not implemented Error: CREATE OR REPLACE not supported in DuckDB-Iceberg. Please use separate Drop and Create Statements` |
| `DROP TABLE t` then `CREATE TABLE t …` | `Not implemented Error: Cannot create table deleted within a transaction: querysolo.main.t` |
| `CREATE TABLE t …` then `ALTER TABLE t RENAME TO u` | refused at commit; the table created in the transaction cannot be renamed in it |

These are choices in the extension's source (`duckdb/duckdb-iceberg`, `iceberg_schema_entry.cpp`, `HandleCreateConflict`), not bugs in QuerySolo's catalog server, and QuerySolo does not try to work around them in the server: pyiceberg, Spark and Trino would then see a catalog that behaves differently from every other Iceberg REST catalog.

Each of these works when the statements are separate transactions. Outside an explicit `BEGIN`, every statement in DuckDB is its own transaction, so `DROP TABLE t; CREATE TABLE t AS …` typed at a prompt is fine; it is two commits, and a reader in another process can see the table absent between them.

## What works, and what it costs

| Pattern | Result |
|---|---|
| `CREATE TABLE t AS …` | One snapshot. This is what `querysolo import` does. |
| `BEGIN; DELETE FROM t; INSERT INTO t …; COMMIT` | Works, and keeps the table: same identity, same history, two new snapshots (a delete, then an append). A reader in another process can see the table empty for the instant between the two commits. |
| `DROP TABLE t` and `CREATE TABLE t AS …` as separate transactions | Works. A new table with a new identity and no history; absent between the two commits. |
| The swap: `CREATE TABLE t_tmp AS …`, `ALTER TABLE t RENAME TO t_old`, `ALTER TABLE t_tmp RENAME TO t`, `DROP TABLE t_old`, each its own transaction | Works, at the cost of four commits and a new identity every time. |

Neither rebuild pattern removes old data files. Iceberg keeps every snapshot's files until snapshots are expired, and QuerySolo has no snapshot expiry yet, so a table rebuilt every night grows every night. That is a known gap, listed in the task list, not a surprise you should discover from your disk.

## What it means for dbt

dbt-duckdb's built-in `table` materialisation was written for DuckDB's own storage. It builds `<model>__dbt_tmp`, renames the existing table aside, renames the temp table into place, and drops the old one, all inside one `BEGIN … COMMIT`. On native tables that is the right way to swap a table atomically. Against the Iceberg catalog it is the third row of the refused list, so a `materialized: table` model fails at commit with a message about the rename. The `incremental` materialisation with a `merge` strategy does not rename and works through the catalog today (that was step 2's spike).

QuerySolo's answer is a materialisation that only asks the catalog for what it does. `init` writes it into the project as `macros/querysolo.sql`, and it overrides dbt's built-in `table` for that project, so ordinary `materialized: table` models need no QuerySolo-specific config. When a model's columns are unchanged it runs `DELETE` then `INSERT` in one transaction, keeping the table; when they changed it runs `DROP` then `CREATE` as separate transactions. `core/tests/test_step6_materialisation.py` exercises it on three consecutive `dbt run`s plus `dbt test`. If you already have a `macros/querysolo.sql`, `init` leaves yours alone.

## If you write your own SQL against the catalog

Use `CREATE TABLE AS` for a new table and `INSERT`, `UPDATE`, `DELETE` or `MERGE INTO` to change one. To replace a table's contents, prefer `DELETE` then `INSERT` in one transaction over drop-and-create; it keeps the history and the identity that `describe`, the gauge's caches and any later lease depend on. Reserve drop-and-create for a changed schema, and do it as two statements outside a `BEGIN`.
