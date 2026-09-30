# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 3 gate (brief §4): the five file types and folders become Iceberg tables through the
catalog with explicit coercion (D24), replace and append (D16), preview, list, describe and
sample (M3), the AGENTS.md refresh (D16), and a fixture of every type DuckDB can put in a
Parquet file read back through pyiceberg with the types the preview promised."""

import re
from datetime import UTC, datetime, timedelta

import pytest
from pyiceberg.catalog.rest import RestCatalog

from querysolo import Project
from querysolo.project import TABLES_END, TABLES_START
from querysolo.tables import NoSuchTable, TableExists, UnsupportedFile

BASE = (
    "SELECT * FROM (VALUES (1, 'alpha', 1.5, DATE '2026-01-01'), "
    "(2, 'beta', 2.5, DATE '2026-01-02'), (3, 'gamma', 3.5, DATE '2026-01-03')) t(id, name, amt, d)"
)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root)
    p = Project.open(root)
    yield p
    p.close()


@pytest.fixture
def sources(project, tmp_path):
    d = tmp_path / "files"
    d.mkdir()
    e = project.engine
    e.execute(f"COPY ({BASE}) TO '{d}/orders.csv' (HEADER)")
    e.execute(f"COPY ({BASE}) TO '{d}/orders.tsv' (HEADER, DELIMITER '\\t')")
    e.execute(f"COPY ({BASE}) TO '{d}/orders.parquet' (FORMAT parquet)")
    e.execute(f"COPY ({BASE}) TO '{d}/orders.json' (FORMAT json, ARRAY true)")
    e.execute(f"COPY ({BASE}) TO '{d}/orders.jsonl' (FORMAT json)")
    e.execute(f"COPY ({BASE}) TO '{d}/orders.xlsx' (FORMAT xlsx, HEADER true)")
    return d


def test_preview_shows_the_name_the_types_and_a_sample_without_writing(project, sources) -> None:
    pv = project.tables.preview(sources / "orders.csv")
    assert pv.name == "orders"
    assert [c.name for c in pv.columns] == ["id", "name", "amt", "d"]
    assert [c.iceberg_type for c in pv.columns] == ["long", "string", "double", "date"]
    assert pv.sample[0][:2] == (1, "alpha") and len(pv.sample) == 3
    assert project.tables.list() == []
    assert project.tables.preview(sources / "orders.csv", name="o2").name == "o2"


@pytest.mark.parametrize("ext", ["csv", "tsv", "parquet", "json", "jsonl", "xlsx"])
def test_each_file_type_becomes_an_iceberg_table_pyiceberg_can_read(project, sources, ext) -> None:
    info = project.tables.import_file(sources / f"orders.{ext}", name=f"orders_{ext}")
    assert info.name == f"orders_{ext}" and info.rows == 3 and info.bytes > 0
    assert [c for c, _ in info.columns] == ["id", "name", "amt", "d"]
    table = RestCatalog("querysolo", uri=project.catalog_url).load_table(f"main.orders_{ext}")
    got = table.scan().to_arrow().sort_by("id").to_pydict()
    assert got["name"] == ["alpha", "beta", "gamma"]


def test_unsupported_and_missing_files(project, tmp_path) -> None:
    (tmp_path / "notes.txt").write_text("hello")
    with pytest.raises(UnsupportedFile):
        project.tables.import_file(tmp_path / "notes.txt")
    with pytest.raises(FileNotFoundError):
        project.tables.import_file(tmp_path / "missing.csv")


def test_create_replace_append(project, sources) -> None:
    first = project.tables.import_file(sources / "orders.csv")
    assert first.rows == 3
    with pytest.raises(TableExists):
        project.tables.import_file(sources / "orders.csv")
    appended = project.tables.import_file(sources / "orders.parquet", name="orders", mode="append")
    assert appended.rows == 6
    assert project.tables.describe("orders").snapshots == 2
    replaced = project.tables.import_file(sources / "orders.csv", mode="replace")
    assert replaced.rows == 3
    assert project.tables.describe("orders").snapshots == 1  # a new table, D16
    assert project.tables.import_file(sources / "orders.csv", name="fresh", mode="append").rows == 3


def test_import_dir_is_one_table_per_file(project, sources, tmp_path) -> None:
    folder = tmp_path / "folder"
    folder.mkdir()
    (folder / "orders.csv").write_bytes((sources / "orders.csv").read_bytes())
    project.engine.execute(f"COPY (SELECT 1 AS customer_id) TO '{folder}/customers.csv' (HEADER)")
    (folder / "notes.txt").write_text("skipped")
    previews = project.tables.preview_dir(folder)  # the folder can be looked at first
    assert [(p.name, len(p.columns)) for p in previews] == [("customers", 1), ("orders", 4)]
    assert project.tables.list() == [], "a preview writes nothing"
    infos = project.tables.import_dir(folder)
    assert {i.name for i in infos} == {"customers", "orders"}
    assert sorted(t.name for t in project.tables.list()) == ["customers", "orders"]


def test_import_dir_refuses_a_name_collision_before_writing(project, tmp_path) -> None:
    d = tmp_path / "clash"
    d.mkdir()
    for name in ("Orders 2026.csv", "orders_2026.csv"):
        (d / name).write_text("id\n1\n")
    with pytest.raises(TableExists, match="orders_2026"):
        project.tables.import_dir(d)
    assert project.tables.list() == []


def test_list_describe_sample(project, sources) -> None:
    project.tables.import_file(sources / "orders.csv")
    [info] = project.tables.list()
    assert (info.name, info.rows) == ("orders", 3) and info.bytes > 0
    assert info.columns == [("id", "long"), ("name", "string"), ("amt", "double"), ("d", "date")]
    assert info.freshness is not None and info.freshness.tzinfo is not None
    assert abs((datetime.now(UTC) - info.freshness).total_seconds()) < 60, (
        "the list carries freshness"
    )
    assert info.location.startswith(project.warehouse_url + "/main/orders")

    desc = project.tables.describe("orders")
    assert desc.partitioning == "unpartitioned"
    assert desc.freshness is not None and datetime.now(UTC) - desc.freshness < timedelta(minutes=1)
    assert desc.last_commit["snapshot_id"] == desc.snapshot_id
    assert desc.snapshots == 1 and desc.format_version == 2

    rows = project.tables.sample("orders", n=2, truncate=3)
    assert len(rows) == 2 and rows[0]["name"] == "alp"
    with pytest.raises(NoSuchTable):
        project.tables.sample("nope")
    with pytest.raises(NoSuchTable):
        project.tables.describe("nope")


def test_agents_md_block_is_refreshed_on_import(project, sources) -> None:
    project.tables.import_file(sources / "orders.csv")
    text = (project.root / "AGENTS.md").read_text()
    block = text[text.index(TABLES_START) : text.index(TABLES_END)]
    assert "- `orders` (" in block and "3 rows" in block
    project.tables.import_file(sources / "orders.csv", mode="replace")
    text = (project.root / "AGENTS.md").read_text()
    assert text.count("- `orders` (") == 1


def _normalise(iceberg_type: str) -> str:
    """pyiceberg prints struct fields with ids and optionality; the preview does not."""
    return re.sub(r"\d+: ", "", iceberg_type).replace(" optional", "").replace(" required", "")


def test_every_parquet_type_reads_back_with_the_type_the_preview_promised(
    project, tmp_path
) -> None:
    fixture = tmp_path / "types.parquet"
    project.engine.execute(
        f"""COPY (SELECT true AS b, 1::TINYINT AS i8, 1::SMALLINT AS i16, 1::INTEGER AS i32,
            1::UTINYINT AS u8, 1::USMALLINT AS u16, 1::BIGINT AS i64, 1::UINTEGER AS u32,
            1::UBIGINT AS u64, 1::HUGEINT AS i128, 1.5::FLOAT AS f32, 1.5::DOUBLE AS f64,
            1.234::DECIMAL(18,3) AS dec, 'x' AS s, '\\xAA'::BLOB AS bin, DATE '2026-01-01' AS d,
            TIME '12:00:00' AS t, TIMESTAMP '2026-01-01 00:00:00' AS ts,
            TIMESTAMP_NS '2026-01-01 00:00:00.123456789' AS ts_ns,
            TIMESTAMPTZ '2026-01-01 00:00:00+00' AS tstz, uuid() AS u, [1, 2]::INTEGER[] AS l,
            {{'a': 1::UTINYINT, 'b': 'x'}} AS st, MAP {{'k': 1::HUGEINT}} AS m,
            INTERVAL 1 DAY AS iv) TO '{fixture}' (FORMAT parquet)"""
    )
    pv = project.tables.preview(fixture)
    promised = {c.name: c.iceberg_type for c in pv.columns}
    print("\npreview:", [(c.name, c.duckdb_type, c.iceberg_type, c.note) for c in pv.columns])
    project.tables.import_file(fixture, name="types")
    table = RestCatalog("querysolo", uri=project.catalog_url).load_table("main.types")
    actual = {f.name: _normalise(str(f.field_type)) for f in table.schema().fields}
    assert actual == promised
    assert table.scan().to_arrow().num_rows == 1


def test_row_counts_subtract_position_deletes(project) -> None:
    """Real-data brief, step 3: the panel said 303 rows for a table DuckDB counted 200
    after a delete-then-insert rebuild, because a DuckDB delete is a position-delete file
    and the data files keep their record counts. The list, describe and the snapshot list
    all take the deletes off."""
    project.engine.execute("create table querysolo.main.t as select range as id from range(10)")
    project.engine.execute("delete from querysolo.main.t where id < 6")
    project.engine.execute("insert into querysolo.main.t select range from range(4)")
    assert project.engine.execute("select count(*) from t").fetchone()[0] == 8
    described = project.tables.describe("t")
    assert described.rows == 8
    assert [t.rows for t in project.tables.list() if t.name == "t"] == [8]
    ops = [(s["operation"], s["deleted_rows"], s["total_rows"]) for s in described.snapshot_list]
    assert ops == [("append", None, 8), ("delete", 6, 4), ("append", None, 10)]
