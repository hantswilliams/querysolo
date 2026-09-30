---
title: Backups, crashes, upgrades and moves
description: What a backup of a QuerySolo project is, what an interrupted write leaves behind, what happens when QuerySolo is upgraded or the folder is moved. Every sentence here has a test.
section: Guide
order: 6
---

Every sentence on this page is asserted by a test in `core/tests/test_recovery.py` (and, for the moved folder, `test_trust_relocate.py`). If a sentence has no test, it does not belong here. Written for the trust round of September 2026, T4 and T5.

## The project folder is the backup unit

A copy of the project folder at rest, restored to the same path, is a complete backup: the tables, their history, the saved questions and their versions all come back. Nothing about a project lives outside its folder — the catalog is `.querysolo/catalog.db`, the query record is `.querysolo/history.db`, the data is `warehouse/`, the questions are `models/questions/`, the versions are `.git/`. Time Machine, a `cp -r`, a `zip`: any of them is the backup.

Two folders inside `.querysolo/` are derived and can be deleted at any time: `cache/` (the manifest statistics the gauge reads, and remote metadata it fetched) and `dbt/` (dbt's compiled target). Both are rebuilt on first use. `history.db` is not derived — it is the record the gauge learns from — but losing it loses only that record, never a table.

A copy restored to a *different* path is a moved project: see the last section.

## What a crash leaves behind

**A table commit is one atomic write to the catalog.** An import, an append, a `querysolo run` or a statement of your own writes its data files first and then commits a new snapshot through the catalog; the catalog entry is updated last, in one SQLite transaction. A crash before that update leaves the previous snapshot current and the new files as orphans, which `querysolo tables expire` sweeps once they are older than an hour. A crash after it is a finished commit.

**A replace never drops the old table until the new one is complete.** `querysolo import --replace` builds the new table under a temporary name, then drops the old and renames the new — so a file that does not parse, a cast that fails or a disk that fills leaves the old table exactly as it was. A crash in the instant between the drop and the rename leaves the new table listed under its temporary name, with the sentence that finishes the swap (`querysolo tables rename`). The data is never invisible.

**Both databases are SQLite in WAL mode.** A commit to the catalog or to history is durable once it returns; a process killed mid-transaction rolls that transaction back on the next open. There is no separate database server, and no database file to lose: the warehouse is the Parquet and the catalog, and both survive a crash mid-query.

**A full disk fails the commit and names the disk.** The catalog answers with the operating system's own sentence (`No space left on device`) and *the catalog was not changed*; the engine reports it, and nothing is half-written into the catalog. The data files written before the failure are orphans for `expire`.

**`expire` never removes a file the current snapshot references.** It drops snapshots older than the retention and deletes only the files no remaining snapshot references, plus orphans past their grace. A scan that started before an expiry and still needs an expired file will fail naming that file; that is the one race a long query and an expiry can have, and it is why `expire` is a verb a person runs rather than something QuerySolo does on its own.

## Upgrades and downgrades

Both databases record the schema version that wrote them and which QuerySolo did. On open, **a newer schema is refused** with the sentence that says so — *this project's catalog was written by a newer QuerySolo (0.2.0, schema 2); this is 0.1.0, which reads schema 1 — upgrade QuerySolo, or open the project with the version that wrote it* — and the file is left untouched. **An older schema is migrated forward**, each numbered migration once, in order, and the version recorded. The first one is history's schema 2 (September 20, 2026): the tables that say which model or question a run belongs to are keyed by the run, so every run is kept for [the changes feed](/docs/tables#what-happened-the-changes-feed); a schema-1 `history.db` is rewritten on open with its rows carried over. The catalog has none yet.

## A moved or copied folder

Iceberg metadata records absolute locations: the table, every metadata file, every manifest list, every manifest, every data file — and a position-delete file names, in every row, the data file it deletes from by absolute path. Move `~/acme` to `~/Documents/acme`, or copy it to another machine, and every table's metadata points at where it used to be. QuerySolo notices on open — a local table's metadata is missing at its recorded location and present at the same relative path under this folder — lists every such table marked *needs relocate* (never invisible), and says: *this project was moved from `<old path>`; `querysolo relocate` updates its tables*. The app says the same on the Tables screen with a **Relocate** button.

`querysolo relocate` rewrites, for every table under the project's own warehouse: each manifest, written again beside itself with its data-file paths under the new root (pyiceberg's own writers; sequence numbers and the manifest's kind preserved); each manifest list; each position-delete file, written again with the new paths in its rows; and the metadata file as a new version, moved to in the catalog in one commit. **Every snapshot is kept**: time travel to a snapshot from before the move still answers. Tables attached from a bucket need nothing and are skipped. The old metadata and delete files become orphans, and `querysolo tables expire` sweeps them after its grace. A second `relocate` has nothing to do and says so.
