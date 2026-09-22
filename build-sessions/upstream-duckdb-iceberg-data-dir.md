# Draft issue for duckdb/duckdb-iceberg (decisions F1, 2026-09-22)

*For Hants to file. Lakelet's workaround is `remove_stray_data_dir()` in `core/lakelet/engine.py`, called after every statement and after a dbt run; it goes when this is fixed upstream. The versions below are the ones the repro ran on; check `select extension_version from duckdb_extensions() where extension_name = 'iceberg'` before filing.*

---

**Title:** CREATE TABLE against a REST catalog creates an empty `data/` directory in the process's working directory

**What happens**

With an Iceberg REST catalog attached, the first `CREATE TABLE ... AS SELECT` in a process creates an empty directory named `data` in the current working directory of the process, in addition to the table's real `<location>/data/` under the location the catalog returned. The stray directory is always empty and always relative to the cwd, so it lands wherever the client happened to be started from (a project folder, a home directory, `/` for a desktop app launched from a Dock).

**Versions**

DuckDB 1.5.5 (Python, `duckdb` wheel from PyPI); iceberg extension from `extensions.duckdb.org` for that build; Linux x86_64 and macOS arm64 both show it.

**Reproduce**

Any REST catalog that assigns the table location itself (the request carries no `location`). With Lakelet's SQLite-backed REST catalog:

```python
import os, tempfile, duckdb
os.chdir(tempfile.mkdtemp())            # an empty cwd
con = duckdb.connect()
con.execute("LOAD iceberg; LOAD httpfs;")
con.execute("CREATE SECRET (TYPE ICEBERG, TOKEN 'x')")
con.execute("ATTACH 'main' AS cat (TYPE ICEBERG, ENDPOINT 'http://127.0.0.1:PORT/v1')")
con.execute("CREATE TABLE cat.main.t AS SELECT 1 AS id")
print(os.listdir("."))                  # ['data']  <- empty, unexpected
```

The table's own files are written correctly under the location the catalog returned (`.../main/t/data/*.parquet`, `.../main/t/metadata/...`).

**Expected**

No directory outside the table's location. If the directory is a staging step before the create response arrives, it should be created only once the location is known, or under the catalog's default warehouse, not relative to the cwd.

**Why it matters**

A desktop application that embeds DuckDB has no meaningful cwd; an installed macOS app starts in `/`, where the `mkdir` fails or, if it does not, litters. A CLI leaves an empty `data/` in every folder it was ever run from.
