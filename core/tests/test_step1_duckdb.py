# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 1 gate, first client: DuckDB writes through QuerySolo's catalog to a file://
warehouse and pyiceberg reads the result. The load-bearing test of the brief (§4 step 1,
§7). Observations the brief asks for (D31, attach visibility) are printed under
``pytest -s`` and transcribed into the session log."""

import duckdb
import pyarrow as pa
import pytest
from pyiceberg.catalog.rest import RestCatalog

from tests.catalog_helpers import attach, serve


@pytest.fixture
def served(tmp_path):
    s = serve(f"sqlite:///{tmp_path}/catalog.db", f"file://{tmp_path}/warehouse")
    s.root = tmp_path
    yield s
    s.stop()


def _requests(served) -> list[tuple[str, str, int]]:
    return [(m, p.replace("/v1/querysolo", ""), c) for m, p, c in served.log]


def test_duckdb_create_insert_select_and_pyiceberg_reads(served) -> None:
    RestCatalog("querysolo", uri=served.url).create_namespace("main")
    con = attach(served.url)
    con.execute("CREATE TABLE querysolo.main.orders (id BIGINT, amt DOUBLE)")
    con.execute("INSERT INTO querysolo.main.orders VALUES (1, 1.0), (2, 2.0), (3, 3.0)")
    assert con.execute("SELECT count(*) FROM querysolo.main.orders").fetchone()[0] == 3

    table = RestCatalog("querysolo", uri=served.url).load_table("main.orders")
    assert table.scan().to_arrow().num_rows == 3
    print("\nformat-version DuckDB created:", table.metadata.format_version)
    print("requests:", _requests(served))


def test_duckdb_write_matrix(served) -> None:
    """CTAS, MERGE INTO, rename, drop, create schema. Each is tried on its own so one failure
    does not hide the others; the observations are printed and the gate asserts at the end."""
    RestCatalog("querysolo", uri=served.url).create_namespace("main")
    con = attach(served.url)
    con.execute("CREATE TABLE querysolo.main.orders (id BIGINT, amt DOUBLE)")
    con.execute("INSERT INTO querysolo.main.orders VALUES (1, 1.0), (2, 2.0), (3, 3.0)")
    results: dict[str, str] = {}
    statements = {
        "ctas": "CREATE TABLE querysolo.main.copy AS SELECT * FROM querysolo.main.orders",
        "merge": (
            "MERGE INTO querysolo.main.orders t USING (SELECT 2 AS id, 20.0 AS amt UNION ALL "
            "SELECT 4, 4.0) s ON t.id = s.id WHEN MATCHED THEN UPDATE SET amt = s.amt "
            "WHEN NOT MATCHED THEN INSERT VALUES (s.id, s.amt)"
        ),
        "rename": "ALTER TABLE querysolo.main.copy RENAME TO copy2",
        "drop": "DROP TABLE querysolo.main.copy2",
        "create_schema": "CREATE SCHEMA querysolo.staging",
        "use": "USE querysolo.main",
    }
    for name, sql in statements.items():
        try:
            con.execute(sql)
            results[name] = "ok"
        except Exception as e:  # noqa: BLE001  recorded, then asserted below
            results[name] = f"{type(e).__name__}: {str(e).splitlines()[0][:160]}"
    print("\nwrite matrix:", results)

    table = RestCatalog("querysolo", uri=served.url).load_table("main.orders")
    rows = table.scan().to_arrow().sort_by("id").to_pydict()
    print("after merge:", rows)
    snapshot = table.current_snapshot()
    if snapshot is not None:
        kinds = {
            (entry.data_file.content.name, entry.data_file.file_format.name)
            for manifest in snapshot.manifests(table.io)
            for entry in manifest.fetch_manifest_entry(table.io)
        }
        print("data-file kinds in the current snapshot:", kinds)
    print("format-version after merge:", table.metadata.format_version)
    print("requests:", _requests(served))
    assert results["ctas"] == "ok" and results["merge"] == "ok"
    assert results["rename"] == "ok" and results["drop"] == "ok"
    assert rows["amt"] == [1.0, 20.0, 3.0, 4.0]


def test_a_long_lived_attach_sees_another_writers_table(served) -> None:
    RestCatalog("querysolo", uri=served.url).create_namespace("main")
    con = attach(served.url)
    cat = RestCatalog("querysolo", uri=served.url)
    cat.create_table("main.late", schema=pa.schema([("id", pa.int64())]))
    cat.load_table("main.late").append(pa.table({"id": [1, 2]}))
    try:
        n = con.execute("SELECT count(*) FROM querysolo.main.late").fetchone()[0]
        print("\nlong-lived attach sees a table committed by another process without re-attach")
    except duckdb.Error as e:
        print("\nlong-lived attach needs a re-attach to see a new table:", str(e)[:100])
        con.execute("DETACH querysolo")
        con = attach(served.url)
        n = con.execute("SELECT count(*) FROM querysolo.main.late").fetchone()[0]
    assert n == 2


def test_duckdb_conflict_behaviour_is_recorded(served) -> None:
    """Force a 409 against DuckDB: open a DuckDB transaction with an INSERT buffered, let
    pyiceberg commit to the same table underneath it, then commit. The brief asks whether
    DuckDB retries on its own (D23); the answer is printed and the data is checked either
    way."""
    cat = RestCatalog("querysolo", uri=served.url)
    cat.create_namespace("main")
    con = attach(served.url)
    con.execute("CREATE TABLE querysolo.main.t (id BIGINT)")
    con.execute("INSERT INTO querysolo.main.t VALUES (1)")

    con.execute("BEGIN")
    con.execute("INSERT INTO querysolo.main.t VALUES (2)")
    cat.load_table("main.t").append(pa.table({"id": [3]}))  # lands first
    served.log.clear()
    try:
        con.execute("COMMIT")
        outcome = "committed"
    except duckdb.Error as e:
        outcome = f"raised {type(e).__name__}: {str(e).splitlines()[0][:140]}"
    commits = [(m, p, c) for m, p, c in _requests(served) if m == "POST" and "commit" in p]
    print("\nDuckDB on a 409:", outcome)
    print("commit attempts after the conflict:", commits)

    ids = sorted(cat.load_table("main.t").scan().to_arrow().to_pydict()["id"])
    if outcome == "committed":
        assert ids == [1, 2, 3], ids
    else:
        assert ids == [1, 3], ids
