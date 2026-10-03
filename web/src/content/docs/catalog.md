---
title: The Iceberg REST catalog
description: The catalog every engine talks to, how to serve it on a port, and how DuckDB, pyiceberg, Spark and Trino connect.
section: Guide
order: 3
---

QuerySolo's catalog is an Iceberg REST catalog server, embedded in the process. The CLI starts it on a free loopback port for the length of a command; `querysolo catalog serve` keeps it on a fixed port so other engines can use it. The store behind it is `.querysolo/catalog.db`, SQLite in WAL mode; the same code runs on Postgres for a shared catalog later, and the Postgres variant is in the test suite.

It is a real Iceberg REST implementation, not a shim: pyiceberg does the Iceberg half (validating commit requirements, applying metadata updates, writing the new `metadata.json`), and the server does the catalog half (namespaces, table pointers, a compare-and-swap on the current metadata location). Two writers committing to the same table at once get one success and one 409; a hundred commits from ten concurrent processes lose nothing.

## Serving it

```bash
querysolo catalog serve --port 8181
# catalog at http://127.0.0.1:8181 (Iceberg REST, warehouse file:///Users/you/acme/warehouse)
```

The server binds loopback only and refuses any other `--host` in v0. There is no token on `/v1` in local mode: anything on the machine can read and write the catalog, which is the same trust boundary as the folder itself. Stop it with Ctrl-C. `querysolo serve` runs the same catalog on the same port as the [HTTP API](/docs/api).

## Clients

### DuckDB

Any DuckDB 1.5 with the `iceberg` extension, in another process, attaches the catalog and reads and writes through it. This is the attach the CLI itself uses:

```sql
INSTALL iceberg; LOAD iceberg;
ATTACH 'querysolo' AS querysolo (TYPE ICEBERG, ENDPOINT 'http://127.0.0.1:8181', AUTHORIZATION_TYPE 'none', DEFAULT_SCHEMA 'main');
USE querysolo.main;
SELECT count(*) FROM orders;
CREATE TABLE big AS SELECT * FROM orders WHERE amount > 100;
INSERT INTO orders SELECT * FROM read_csv('more.csv');
```

`CREATE TABLE`, `CREATE TABLE AS`, `INSERT`, `MERGE INTO`, `ALTER TABLE … RENAME`, `DROP TABLE`, `CREATE SCHEMA` and `USE` all work through it; `CREATE OR REPLACE`, and a drop-then-create or a create-then-rename inside one transaction, do not, and [Transactions and the catalog](/docs/transactions) says why. `DEFAULT_SCHEMA 'main'` is needed before DuckDB will create tables at all. DuckDB does not retry a commit conflict on its own; QuerySolo's own engine retries three times, a bare DuckDB gets a `TransactionException` and a consistent table. A long-lived attach sees tables committed by other processes without re-attaching.

### pyiceberg

```python
from pyiceberg.catalog.rest import RestCatalog
catalog = RestCatalog("querysolo", uri="http://127.0.0.1:8181")
table = catalog.load_table("main.orders")
table.scan(row_filter="country = 'DE'").to_arrow()
table.append(arrow_table)          # writes a snapshot DuckDB then sees
```

pyiceberg retries a conflicting commit four times with backoff.

### Spark 3.5

With the Iceberg 1.9 Spark runtime on the classpath. Spark needs the warehouse to be somewhere it can reach, so this is for tables whose data is in a bucket; a `file://` warehouse on your laptop is not visible to a Spark in a container.

```properties
spark.sql.extensions                    org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions
spark.sql.catalog.querysolo               org.apache.iceberg.spark.SparkCatalog
spark.sql.catalog.querysolo.type          rest
spark.sql.catalog.querysolo.uri           http://127.0.0.1:8181
spark.sql.catalog.querysolo.io-impl       org.apache.iceberg.aws.s3.S3FileIO
spark.sql.defaultCatalog                querysolo
```

### Trino

```properties
connector.name=iceberg
iceberg.catalog.type=rest
iceberg.rest-catalog.uri=http://127.0.0.1:8181
iceberg.rest-catalog.warehouse=s3://your-bucket/warehouse
iceberg.rest-catalog.security=NONE
```

The repo's `compose.yaml` has a working Spark and Trino setup against the catalog and a self-hosted S3 store, and `core/tests/smoke/` is the test that walks a table through pyiceberg, Spark, Trino and DuckDB in turn, each seeing the others' writes. See [Develop](/docs/develop) for how to run it.

## The surface

Paths follow the Iceberg REST spec. `GET /v1/config` answers with `overrides.prefix = "querysolo"`, so clients address everything under `/v1/querysolo/…`.

| Method and path | What |
|---|---|
| `GET /v1/config` | The prefix. |
| `GET`, `POST /v1/{prefix}/namespaces` | List, create. Namespaces are single level in v0; a multi-level name is a 400. |
| `GET`, `HEAD`, `DELETE /v1/{prefix}/namespaces/{ns}` | Read, exists, drop. |
| `GET`, `POST /v1/{prefix}/namespaces/{ns}/tables` | List, create (including a staged create, which DuckDB uses). |
| `POST /v1/{prefix}/namespaces/{ns}/register` | Register a table by an existing metadata location. |
| `GET`, `HEAD /v1/{prefix}/namespaces/{ns}/tables/{table}` | Load, exists. |
| `POST /v1/{prefix}/namespaces/{ns}/tables/{table}` | Commit: requirements validated, updates applied, a new metadata file written, the pointer swapped. 409 on a stale base. |
| `POST /v1/{prefix}/transactions/commit` | Multi-table commit, applied one table at a time; DuckDB sends its inserts and merges here. |
| `DELETE /v1/{prefix}/namespaces/{ns}/tables/{table}` | Drop. |
| `POST /v1/{prefix}/tables/rename` | Rename. |
| `POST …/tables/{table}/metrics` | Accepted and ignored. |
| `GET`, `POST /v1/{prefix}/namespaces/{ns}/views` | List, create a view (the view spec's JSON: a schema and a first version with its SQL representations). |
| `GET`, `HEAD`, `DELETE /v1/{prefix}/namespaces/{ns}/views/{view}` | Load, exists, drop. |
| `POST /v1/{prefix}/namespaces/{ns}/views/{view}` | Replace: `add-schema`, `add-view-version`, `set-current-view-version` and the property updates, a new metadata file, the pointer moved. |

Two things learned from the clients and built in: DuckDB expects a table's `data/` directory to exist on a local warehouse, so the server creates `data/` and `metadata/` when a create is staged; and the Java clients omit `identifier` on a per-table commit, which the server accepts.

## Where the files go

`[project] warehouse` in `querysolo.toml` is the base: `./warehouse` by default, resolved to `file://`, or an `s3://` prefix given to `querysolo init --warehouse` ([A real bucket](/docs/remote) has the page); it is fixed at `init`, because tables carry absolute locations. A table's data and metadata sit under `<warehouse>/main/<table>/`. Every commit writes a new `<version>-<uuid>.metadata.json`; the catalog holds the pointer to the current one. Leaving QuerySolo means keeping `warehouse/` and pointing any Iceberg reader at the latest `metadata.json` of each table.
