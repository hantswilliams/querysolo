# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 8 gate (brief §4, D25, D26, D27, D36, M3): a Parquet prefix attaches in place without
copying, DuckDB and pyiceberg both read it, refresh adds a new file and refuses a missing
one, metadata local or in the bucket, register by metadata location, discover, the
bandwidth probe, the Red bandwidth sentence, and the second estimate under 150 ms with the
manifests cached. Runs against Moto in the default suite; QUERYSOLO_TEST_S3_BUCKET (a real
bucket) or QUERYSOLO_TEST_S3_ENDPOINT (a self-hosted store) points it at a real one, see
tests/s3_helpers.py. The schema-drift and hive fixtures are here; ten thousand files is gated."""

import os
import time
from types import SimpleNamespace

import duckdb
import httpx
import pytest
from pyiceberg.catalog.rest import RestCatalog

from querysolo import Project
from querysolo.gauge import inputs
from querysolo.register import MissingFiles, NotRegistrable, SchemaDrift
from querysolo.tables import TableExists
from tests.s3_helpers import open_store


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


def writer(s3) -> duckdb.DuckDBPyConnection:
    """A non-Iceberg writer: plain DuckDB with its own secret, the way a partner's pipeline
    would have written the prefix."""
    if s3.writer_con is None:
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs")
        con.execute(s3.duckdb_secret_sql())
        s3.writer_con = con
    return s3.writer_con


def write_part(s3, key: str, start: int, rows: int, extra: str = "") -> None:
    """``key`` is a full key in the store's bucket (``s3.key(...)`` puts it under the run)."""
    writer(s3).execute(
        f"COPY (SELECT range AS id, 'c' || (range % 10) AS customer, range * 1.5 AS amt{extra} "
        f"FROM range({start}, {start + rows})) TO '{s3.uri(key)}' (FORMAT parquet)"
    )


@pytest.fixture
def project(env, tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    yield p
    p.close()


@pytest.fixture
def events(env, tmp_path):
    """Three plain Parquet files under a unique prefix, written by a non-Iceberg writer."""
    prefix = env.key(f"raw-{tmp_path.name}/events")
    for i in range(3):
        write_part(env, f"{prefix}/part-{i}.parquet", i * 1000, 1000)
    return SimpleNamespace(prefix=env.uri(prefix) + "/", key=prefix, s3=env)


def object_keys(s3, prefix: str) -> set[str]:
    return s3.keys(prefix)


def test_attach_registers_in_place_and_both_engines_read_it(project, events, env) -> None:
    before = object_keys(env, events.key)
    info = project.tables.attach("events", events.prefix)
    assert info.rows == 3000 and info.location.startswith(project.warehouse_url + "/main/events")
    assert object_keys(env, events.key) == before, "registration must not copy or write data"
    assert list((project.root / "warehouse/main/events/metadata").glob("*.metadata.json"))

    assert project.engine.execute("select count(*) from events").fetchone()[0] == 3000
    assert project.engine.execute("select max(id) from events where id < 1000").fetchone()[0] == 999
    table = RestCatalog("querysolo", uri=project.catalog_url, **project.io_properties).load_table(
        "main.events"
    )
    assert table.scan().to_arrow().num_rows == 3000
    files = [t.file.file_path for t in table.scan().plan_files()]
    assert all(f.startswith(f"s3://{env.bucket}/") for f in files)

    desc = project.tables.describe("events")
    assert desc.rows == 3000 and desc.snapshots == 1
    assert "s3://" in (project.root / "AGENTS.md").read_text()
    with pytest.raises(TableExists):
        project.tables.attach("events", events.prefix)


def test_metadata_in_the_bucket_and_register_by_metadata_location(project, events, env) -> None:
    info = project.tables.attach("events_b", events.prefix, metadata_in_bucket=True)
    assert info.location == env.uri("_querysolo/events_b")
    assert any(k.endswith(".metadata.json") for k in object_keys(env, "_querysolo/events_b/"))
    assert project.engine.execute("select count(*) from events_b").fetchone()[0] == 3000

    location = project.store.get_table("main", "events_b")
    again = project.tables.attach("events_c", location)
    assert (
        again.rows == 3000
        and project.engine.execute("select count(*) from events_c").fetchone()[0] == 3000
    )


def test_refresh_adds_new_files_and_refuses_missing_ones(project, events, env) -> None:
    project.tables.attach("events", events.prefix)
    assert project.tables.refresh("events").added == 0
    write_part(events.s3, f"{events.key}/part-3.parquet", 3000, 500)
    report = project.tables.refresh("events")
    assert (report.added, report.files, report.rows) == (1, 4, 3500)
    assert project.engine.execute("select count(*) from events").fetchone()[0] == 3500
    assert project.tables.describe("events").snapshots == 2

    env.client.delete_object(Bucket=env.bucket, Key=f"{events.key}/part-1.parquet")
    with pytest.raises(MissingFiles, match="part-1.parquet"):
        project.tables.refresh("events")


def test_schema_drift_is_refused_with_the_file_and_column_named(project, env, tmp_path) -> None:
    key = env.key(f"drift-{tmp_path.name}/t")
    write_part(env, f"{key}/part-0.parquet", 0, 10)
    write_part(env, f"{key}/part-1.parquet", 10, 10)
    write_part(env, f"{key}/part-2.parquet", 20, 10, extra=", 'x' AS region")
    with pytest.raises(SchemaDrift, match=r"part-2\.parquet.*adds \['region'\]"):
        project.tables.attach("drift", env.uri(key) + "/")
    assert project.tables.list() == []


def test_hive_partition_only_in_the_path_is_refused_by_name(project, env, tmp_path) -> None:
    key = env.key(f"hive-{tmp_path.name}/t")
    write_part(env, f"{key}/country=US/part-0.parquet", 0, 10)
    write_part(env, f"{key}/country=DE/part-0.parquet", 10, 10)
    with pytest.raises(NotRegistrable, match="country"):
        project.tables.attach("hive", env.uri(key) + "/")


def test_a_geoparquet_column_reads_as_the_binary_the_catalog_says(project, env, tmp_path) -> None:
    """A prefix of GeoParquet (a `geo` footer entry, as Overture's files carry) is attached
    with its geometry as `binary`. DuckDB's reader would turn that column into GEOMETRY on
    a machine that has the spatial extension (`enable_geoparquet_conversion`, on by
    default), and the Iceberg scan then failed to cast it back — `select * from place`
    refused on Hants' Mac, 2026-09-21. The engine and dbt's connection turn the conversion
    off, so the WKB bytes come through; the geometry is one core function away."""
    key = env.key(f"geo-{tmp_path.name}/places")
    writer(env).execute(
        f"COPY (SELECT range AS id, ('POINT(' || range || ' 2)')::GEOMETRY AS geometry "
        f"FROM range(5)) TO '{env.uri(key)}/part-0.parquet' (FORMAT parquet)"
    )
    info = project.tables.attach("places", env.uri(key) + "/")
    assert dict(info.columns)["geometry"] == "binary"
    con = project.engine
    assert (
        con.execute("SELECT current_setting('enable_geoparquet_conversion')").fetchone()[0] is False
    )
    rows = con.execute(
        "SELECT id, typeof(geometry), st_astext(st_geomfromwkb(geometry)) FROM places ORDER BY id"
    ).fetchall()
    assert rows[0] == (0, "BLOB", "POINT (0 2)") and len(rows) == 5


def test_discover_lists_candidate_prefixes(project, events, env) -> None:
    bucket_prefix = events.prefix.rsplit("/", 2)[0] + "/"
    found = {d.prefix: d for d in project.tables.discover(bucket_prefix)}
    assert events.prefix in found
    assert found[events.prefix].kind == "parquet" and found[events.prefix].files == 3
    assert found[events.prefix].bytes > 0


def test_discover_skips_both_metadata_folders_the_old_name_included(project, events, env) -> None:
    """Buckets written before the rename hold `_lakelet/` (rename plan R4); neither it nor
    `_querysolo/` is a dataset to offer."""
    root = events.key.rsplit("/", 1)[0]
    for folder in ("_" + "lake" + "let", "_querysolo"):
        write_part(env, f"{root}/{folder}/orders/part-0.parquet", 0, 10)
    found = {d.prefix for d in project.tables.discover(env.uri(root) + "/")}
    assert events.prefix in found
    assert not any("/_querysolo" in f or "/_lake" + "let" in f for f in found), found


def test_bandwidth_probe_red_sentence_and_the_cached_second_estimate(project, events) -> None:
    project.tables.attach("events", events.prefix, metadata_in_bucket=True)
    cache = inputs.load_machine_cache(project.cache_dir)
    assert cache.get("bandwidth_mbps", 0) > 0, "the probe should have run on first attach"

    est = project.estimate("select sum(amt) from events")
    assert est.remote and events.prefix.rstrip("/") in est.reason and "from s3://" in est.reason

    # A slow link and the thresholds of a tiny fixture: 60 KB at 0.5 Mbps must read as Red.
    cache["bandwidth_mbps"] = 0.5
    inputs.save_machine_cache(project.cache_dir, cache)
    toml = project.root / "querysolo.toml"
    toml.write_text(
        toml.read_text()
        .replace("green_max_seconds = 60", "green_max_seconds = 0.01")
        .replace("yellow_max_seconds = 600", "yellow_max_seconds = 0.1")
    )
    root = project.root
    project.close()
    p = Project.open(root)
    try:
        red = p.estimate("select sum(amt) from events")
        assert red.verdict == "red" and red.words == "Needs more machine", red.reason
        assert (
            "at your 0.5 Mbps" in red.reason and "burst ~" in red.reason and "cap $" in red.reason
        )
        assert red.line.startswith("● Needs more machine · scans ")

        # The second estimate must not fetch metadata or manifests again: every remote read
        # the Python side makes goes through the caching FileIO, counted here at its inner.
        inner = p.metadata_io.io._inner
        fetched: list[str] = []
        original = inner.new_input

        def spy(location: str):
            f = original(location)
            opened = f.open
            f.open = lambda *a, **k: fetched.append(location) or opened(*a, **k)
            return f

        inner.new_input = spy
        started = time.perf_counter()
        p.estimate("select sum(amt) from events where id > 2500")
        second = time.perf_counter() - started
        inner.new_input = original
        print(f"\nsecond estimate on a bucket-metadata table: {second * 1000:.0f} ms")
        assert list((p.cache_dir / "objects").rglob("*.avro")), "manifests should be cached on disk"
        assert list((p.cache_dir / "objects").rglob("*.metadata.json")), "metadata cached too"
        assert fetched == [], f"the second estimate read from the store: {fetched}"
        load, cores = os.getloadavg()[0], os.cpu_count() or 1
        if load > cores:
            pytest.skip(
                f"machine under load ({load:.0f} on {cores} cores); the budget cannot be measured"
            )
        assert second < 0.150
    finally:
        p.close()


def test_cli_attach_refresh_discover(project, events, env) -> None:
    from typer.testing import CliRunner

    from querysolo.cli import app

    project.close()
    runner = CliRunner()
    root = str(project.root)
    attached = runner.invoke(app, ["-C", root, "tables", "attach", "events", events.prefix])
    assert attached.exit_code == 0, attached.output
    assert "3,000 rows" in attached.output and "in place" in attached.output
    write_part(events.s3, f"{events.key}/part-9.parquet", 9000, 100)
    refreshed = runner.invoke(app, ["-C", root, "tables", "refresh", "events"])
    assert refreshed.exit_code == 0 and "1 file(s) added" in refreshed.output
    discovered = runner.invoke(
        app, ["-C", root, "tables", "discover", events.prefix.rsplit("/", 2)[0] + "/"]
    )
    assert discovered.exit_code == 0 and "parquet" in discovered.output
    twice = runner.invoke(app, ["-C", root, "tables", "attach", "events", events.prefix])
    assert twice.exit_code == 1


def test_a_public_bucket_is_read_without_credentials(events, env, monkeypatch, tmp_path) -> None:
    """Real-data brief R3: `--anonymous` lists, registers, reads and refreshes a prefix with
    no AWS keys anywhere, the engine reading through a secret scoped to the bucket, and the
    bucket remembered so a re-opened project reads the table too."""
    from querysolo.remote import load_public_buckets

    if env.real:
        pytest.skip("a private bucket is not made public by a test; the Open Data run is by hand")
    # Moto honours ACLs the way S3 does: an anonymous request needs a public-read grant.
    env.client.put_bucket_acl(Bucket=env.bucket, ACL="public-read")
    for key in env.keys(events.key):
        env.client.put_object_acl(Bucket=env.bucket, Key=key, ACL="public-read")
    # "No credentials anywhere" has to mean the whole default chain, not three variables:
    # a machine with ~/.aws, an SSO cache, a role or the instance metadata service would
    # otherwise still resolve credentials and the test would not be testing anything.
    for key in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_ROLE_ARN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(tmp_path / "no-credentials"))
    monkeypatch.setenv("AWS_CONFIG_FILE", str(tmp_path / "no-config"))
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    root = tmp_path / "public"
    Project.init(root, probe_mb=8)
    p = Project.open(root, serve=True)
    try:
        with pytest.raises(NotRegistrable, match="no AWS credentials"):
            p.tables.discover(events.prefix.rsplit("/", 2)[0] + "/")
        found = p.tables.discover(events.prefix.rsplit("/", 2)[0] + "/", anonymous=True)
        assert any(d.prefix == events.prefix for d in found)
        # The app's preview before an attach: one footer's columns, the files and bytes,
        # through the API as the drop zone calls it.
        client = httpx.Client(
            base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}
        )
        refused = client.post("/api/preview", json={"path": events.prefix})
        assert refused.status_code == 400 and refused.json()["error"] == "not_registrable"
        shown = client.post("/api/preview", json={"path": events.prefix, "anonymous": True})
        assert shown.status_code == 200, shown.text
        body = shown.json()
        assert body["remote"] and body["files"] == 3 and body["bytes"] > 0 and body["anonymous"]
        assert body["name"] == "events" and body["sample"] == []
        assert [c["name"] for c in body["columns"]] == ["id", "customer", "amt"]
        assert [c["iceberg_type"] for c in body["columns"]] == ["long", "string", "decimal(21, 1)"]
        client.close()
        with pytest.raises(NotRegistrable, match="read-only"):
            p.tables.attach("events", events.prefix, metadata_in_bucket=True, anonymous=True)
        info = p.tables.attach("events", events.prefix, anonymous=True)
        assert info.rows == 3000 and info.public and info.source == events.prefix
        assert info.location.startswith(p.warehouse_url), "metadata stays local"
        assert p.engine.execute("select count(*) from events").fetchone()[0] == 3000
        assert list(load_public_buckets(p.querysolo_dir)) == [env.bucket]
        write_part(events.s3, f"{events.key}/part-3.parquet", 3000, 500)
        env.client.put_object_acl(
            Bucket=env.bucket, Key=f"{events.key}/part-3.parquet", ACL="public-read"
        )
        assert p.tables.refresh("events").rows == 3500
        assert p.estimate("select sum(amt) from events").remote
    finally:
        p.close()
    again = Project.open(root)
    try:
        assert again.engine.execute("select count(*) from events").fetchone()[0] == 3500
        assert [t.public for t in again.tables.list()] == [True]
    finally:
        again.close()


@pytest.mark.skipif(os.environ.get("QUERYSOLO_PERF") != "1", reason="set QUERYSOLO_PERF=1")
def test_ten_thousand_small_files(project, env, tmp_path) -> None:
    key = env.key(f"many-{tmp_path.name}/t")
    started = time.perf_counter()
    for i in range(10_000):
        write_part(env, f"{key}/part-{i:05}.parquet", i * 10, 10)
    written = time.perf_counter() - started
    started = time.perf_counter()
    info = project.tables.attach("many", env.uri(key) + "/")
    registered = time.perf_counter() - started
    print(f"\n10,000 files: written in {written:.0f}s, registered in {registered:.0f}s")
    assert info.rows == 100_000


def test_a_table_name_from_a_prefix() -> None:
    from querysolo.register import remote_name

    assert remote_name("s3://b/release/2026-08-19.0/theme=places/type=place/") == "place"
    assert remote_name("s3://b/exports/events/") == "events"
    assert remote_name("s3://b/exports/2024-events") == "t_2024_events"


def test_nested_iceberg_types_read_without_field_ids() -> None:
    import pyarrow as pa
    from pyiceberg.catalog import Catalog

    from querysolo.register import iceberg_type_text

    arrow = pa.schema(
        [
            pa.field("bbox", pa.struct([("xmin", pa.float64()), ("xmax", pa.float64())])),
            pa.field("websites", pa.list_(pa.string())),
            pa.field("names", pa.map_(pa.string(), pa.int64())),
            pa.field("id", pa.string()),
        ]
    )
    fields = Catalog._convert_schema_if_needed(arrow).fields
    assert [iceberg_type_text(f.field_type) for f in fields] == [
        "struct<xmin: double, xmax: double>",
        "list<string>",
        "map<string, long>",
        "string",
    ]
