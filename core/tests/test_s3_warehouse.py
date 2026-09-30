# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Decisions W1 (2026-09-17): an `s3://` warehouse is a first-class way to run a project.
`init --warehouse s3://bucket/prefix` puts every table's data and metadata in the bucket;
the catalog stays in `.querysolo/`; and the whole product path — import, sql writes,
`querysolo run` with a table and a view model, describe, expire, versions, relocate — is run
here against the same store the S3 suite uses (Moto by default; a real bucket or RustFS
with the `tests/s3_helpers.py` variables)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from querysolo import Project, relocate
from querysolo.cli import app
from tests.s3_helpers import open_store

pytest.importorskip("dbt.cli.main")


@pytest.fixture(scope="module")
def s3():
    store = open_store()
    yield store
    store.stop()


@pytest.fixture
def env(s3, monkeypatch):
    for k, v in s3.environment().items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    return s3


@pytest.fixture
def project(env, tmp_path):
    """A project whose warehouse is a prefix in the bucket, with a CSV to import and two
    models: a table over the import and a view over the table."""
    root = tmp_path / "proj"
    prefix = env.uri(env.key(f"wh-{tmp_path.name}"))
    Project.init(root, probe_mb=0, warehouse=prefix)
    (tmp_path / "orders.csv").write_text(
        "id,customer,amt\n" + "".join(f"{i},c{i % 3},{i * 1.5}\n" for i in range(300))
    )
    (root / "models" / "by_customer.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select customer, sum(amt) as total from orders group by 1\n"
    )
    (root / "models" / "top.sql").write_text(
        "select customer from {{ ref('by_customer') }} order by total desc limit 1\n"
    )
    p = Project.open(root, serve=True)
    p.prefix = prefix
    yield p
    p.close()


def test_init_writes_the_warehouse_and_makes_no_local_folder(env, tmp_path) -> None:
    root = tmp_path / "acme"
    prefix = env.uri(env.key("wh-init"))
    r = CliRunner().invoke(app, ["init", str(root), "--probe-mb", "0", "--warehouse", prefix])
    assert r.exit_code == 0, r.output
    # rich wraps at the terminal width, so compare with all whitespace removed
    assert f"everytable'sfilesgoto{prefix}" in "".join(r.output.split())
    assert f'warehouse = "{prefix}"' in (root / "querysolo.toml").read_text()
    assert not (root / "warehouse").exists()
    p = Project.open(root)
    try:
        assert p.warehouse_url == prefix
    finally:
        p.close()
    # only s3:// is a bucket warehouse; anything else is refused before a file is written
    r = CliRunner().invoke(
        app, ["init", str(tmp_path / "nope"), "--probe-mb", "0", "--warehouse", "gs://b/p"]
    )
    assert r.exit_code == 1 and "s3://bucket/prefix" in r.output
    assert not (tmp_path / "nope" / "querysolo.toml").exists()
    # the warehouse is not a setting: it is fixed at init
    r = CliRunner().invoke(app, ["-C", str(root), "config", "set", "project.warehouse", "./w"])
    assert r.exit_code != 0 and "not a setting" in r.output


def test_the_product_path_on_a_bucket_warehouse(project, tmp_path) -> None:
    from pyiceberg.catalog.rest import RestCatalog

    from querysolo.dbt import runner

    p = project
    # import: the table's data and metadata are in the bucket, nothing under the project
    orders = p.tables.import_file(tmp_path / "orders.csv")
    assert orders.location.startswith(p.prefix) and orders.rows == 300
    assert not (p.root / "warehouse").exists()
    keys = p.tables.describe("orders")
    assert keys.location.startswith("s3://") and keys.snapshots == 1
    # the gauge calls it remote and estimates by bandwidth, as it does an attached table
    est = p.estimate("select customer, sum(amt) from orders group by 1")
    assert est.tables[0]["locality"] == "remote"
    # a write through SQL is a second snapshot in the bucket
    p.engine.execute("insert into querysolo.main.orders values (1000, 'c9', 9.0)")
    assert p.tables.describe("orders").snapshots == 2
    assert p.engine.execute("select count(*) from orders").fetchone()[0] == 301
    # querysolo run: a table model lands in the bucket, a view model in the catalog
    report = runner.run(p)
    assert report.ok and report.views_recorded == ["top"]
    by_customer = p.tables.describe("by_customer")
    assert by_customer.location.startswith(p.prefix) and by_customer.rows == 4
    assert p.engine.execute("select customer from top").fetchone()[0] in {"c0", "c1", "c2"}
    # another process reads every table from the bucket through the catalog
    catalog = RestCatalog("querysolo", uri=p.catalog_url, **p.io_properties)
    assert catalog.load_table("main.orders").scan().to_arrow().num_rows == 301
    assert catalog.load_table("main.by_customer").metadata_location.startswith("s3://")
    # every model is fresh after its run; the state rules do not care where the bytes are
    assert all(m.state == "fresh" for m in runner.plan(p))
    # a rebuild in place then expire: the old snapshot's files are deleted in the bucket
    p.engine.execute("delete from querysolo.main.orders")
    p.engine.execute("insert into querysolo.main.orders select range, 'c', 1.0 from range(10)")
    before = p.tables.describe("orders")
    assert before.snapshots == 4
    swept = p.tables.expire("orders", keep_days=0)
    assert swept.snapshots_removed == 3 and swept.files_removed >= 1
    assert p.engine.execute("select count(*) from orders").fetchone()[0] == 10
    # nothing to relocate: a bucket table has no folder to have moved
    assert relocate.moved_from(p) is None
    assert relocate.relocate(p).relocated == []
    # the list says where the tables are, for the app's Where line
    where = {t.name: t.location for t in p.tables.list(views=False)}
    assert all(loc.startswith(p.prefix) for loc in where.values())
    # versions are files, not data: a save is a version as anywhere
    q = p.questions.save("Total", "select sum(amt) as total from orders")
    assert q.commit


@pytest.fixture
def local_project(env, tmp_path):
    """A local-warehouse project with a table of three snapshots (create, append, delete)
    and a question over it, to publish (decisions W2)."""
    root = tmp_path / "local"
    Project.init(root, probe_mb=0)
    p = Project.open(root, serve=True)
    p.engine.execute(
        "create table querysolo.main.orders as select range as id, 'c' || (range % 5) as c, "
        "range * 1.5 as amt from range(1000)"
    )
    p.engine.execute(
        "insert into querysolo.main.orders select range, 'x', 1.0 from range(1000, 1500)"
    )
    p.engine.execute("delete from querysolo.main.orders where id < 10")
    p.questions.save("Total", "select sum(amt) as total from orders")
    yield p
    p.close()


def test_publish_moves_a_table_into_a_bucket_with_every_snapshot(local_project, env) -> None:
    from pyiceberg.catalog.rest import RestCatalog

    from querysolo.relocate import NotPublishable, publish

    p = local_project
    prefix = env.uri(env.key("published"))
    first_snapshot = p.tables.describe("orders").snapshot_list[-1]["id"]
    local_files = list((p.root / "warehouse" / "main" / "orders").rglob("*"))
    local_count = sum(1 for f in local_files if f.is_file())

    # a dry run counts and weighs and moves nothing
    dry = publish(p, "orders", prefix, dry_run=True)
    assert dry.dry_run and dry.files == local_count and dry.bytes > 0 and dry.copied == 0
    assert p.tables.describe("orders").location.startswith("file://")

    report = publish(p, "orders", prefix)
    assert report.target == f"{prefix}/main/orders"
    assert report.copied == local_count and report.skipped == 0
    assert report.data_files == 1  # the position-delete file, written again with bucket paths
    # the catalog points at the bucket; every snapshot resolves for DuckDB and pyiceberg
    desc = p.tables.describe("orders")
    assert desc.location == report.target and desc.snapshots == 3 and desc.rows == 1490
    assert p.engine.execute("select count(*) from orders").fetchone()[0] == 1490
    old = p.engine.execute(
        f"select count(*) from orders AT (VERSION => {first_snapshot})"
    ).fetchone()[0]
    assert old == 1000
    table = RestCatalog("querysolo", uri=p.catalog_url, **p.io_properties).load_table("main.orders")
    assert table.scan().to_arrow().num_rows == 1490
    assert all(t.file.file_path.startswith("s3://") for t in table.scan().plan_files())
    # the list says where it is
    assert {t.name: t.location for t in p.tables.list(views=False)}["orders"] == report.target
    # the local files are still there, counted, until expire sweeps them after its grace
    assert desc.local_copy_files == local_count
    r = CliRunner().invoke(app, ["-C", str(p.root), "tables", "describe", "orders"])
    assert r.exit_code == 0, r.output
    assert f"localcopy:{local_count}file(s)stillunderthewarehouse" in "".join(r.output.split())
    swept = p.tables.expire("orders", keep_days=0, orphan_grace_seconds=0)
    assert swept.files_removed >= local_count
    assert not any(f.is_file() for f in (p.root / "warehouse" / "main" / "orders").rglob("*"))
    assert p.tables.describe("orders").local_copy_files == 0
    assert p.engine.execute("select count(*) from orders").fetchone()[0] == 1490
    # a second publish is refused: the table is in a bucket now
    with pytest.raises(NotPublishable, match="already in a bucket"):
        publish(p, "orders", prefix)


def test_publish_resumes_refuses_and_the_verb_and_route(local_project, env, monkeypatch) -> None:
    import httpx

    from querysolo.relocate import NotPublishable, publish

    p = local_project
    prefix = env.uri(env.key("resumed"))
    # an interrupted copy: half the files are in the bucket already; the rest are copied,
    # the ones there at the same size are not copied twice
    files = sorted(f for f in (p.root / "warehouse" / "main" / "orders").rglob("*") if f.is_file())
    io = p.metadata_io.io
    half = files[: len(files) // 2]
    for f in half:
        target = f"{prefix}/main/orders/{f.relative_to(p.root / 'warehouse' / 'main' / 'orders')}"
        with io.new_output(target).create(overwrite=True) as out:
            out.write(f.read_bytes())
    report = publish(p, "orders", prefix)
    assert report.skipped == len(half) and report.copied == len(files) - len(half)
    assert p.engine.execute("select count(*) from orders").fetchone()[0] == 1490

    # refused: an attached table, a target that is not a bucket, a cap the copy would blow
    folder = p.root.parent / "outside"
    folder.mkdir()
    p.engine.execute(
        f"COPY (SELECT range AS id FROM range(5)) TO '{folder}/a.parquet' (FORMAT parquet)"
    )
    p.tables.attach("outside", f"file://{folder}/")
    with pytest.raises(NotPublishable, match="not QuerySolo's to move"):
        publish(p, "outside", prefix)
    p.engine.execute("create table querysolo.main.small as select 1 as id")
    with pytest.raises(NotPublishable, match="s3://bucket/prefix"):
        publish(p, "small", "gs://nope")
    from querysolo.gauge import inputs

    cache = inputs.load_machine_cache(p.cache_dir)
    cache["bandwidth_mbps"] = 0.000001  # a link so slow the copy would take days
    inputs.save_machine_cache(p.cache_dir, cache)
    with pytest.raises(NotPublishable, match="over the cap"):
        publish(p, "small", prefix, cap_seconds=600)
    assert publish(p, "small", prefix, dry_run=True).seconds > 600

    # the verb: dry run, the refusal without --yes, then --yes
    r = CliRunner().invoke(
        app, ["-C", str(p.root), "tables", "publish", "small", prefix, "--dry-run"]
    )
    assert r.exit_code == 0, r.output
    assert "nothingmoved(--dry-run)" in "".join(r.output.split())
    r = CliRunner().invoke(app, ["-C", str(p.root), "tables", "publish", "small", prefix])
    assert r.exit_code == 1 and "over the cap" in r.output
    r = CliRunner().invoke(app, ["-C", str(p.root), "tables", "publish", "small", prefix, "--yes"])
    assert r.exit_code == 0, r.output
    assert "publishedsmallto" in "".join(r.output.split())
    r = CliRunner().invoke(app, ["-C", str(p.root), "tables", "publish", "nowhere", prefix])
    assert r.exit_code == 1 and "no table named nowhere" in r.output

    # the route
    p.engine.execute("create table querysolo.main.tiny as select 2 as id")
    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=120
    )
    body = client.post("/api/tables/tiny/publish", json={"prefix": prefix, "dry_run": True}).json()
    assert body["dry_run"] and body["files"] >= 2 and body["copied"] == 0
    r = client.post("/api/tables/tiny/publish", json={"prefix": prefix})
    assert r.status_code == 409 and r.json()["error"] == "not_publishable"
    body = client.post("/api/tables/tiny/publish", json={"prefix": prefix, "yes": True}).json()
    assert body["target"] == f"{prefix}/main/tiny" and body["copied"] >= 2
    assert client.get("/api/tables/tiny").json()["location"] == body["target"]
    r = client.post("/api/tables/outside/publish", json={"prefix": prefix, "yes": True})
    assert r.status_code == 409
    assert client.post("/api/tables/nowhere/publish", json={"prefix": prefix}).status_code == 404
    client.close()
