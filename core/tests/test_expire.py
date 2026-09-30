# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Snapshot expiry (decision 4, September 11, 2026): a rebuilt table stops growing once
expired; the current snapshot and the files it needs always survive; every remaining
snapshot still reads back; an attached table is refused; the CLI and the API do the same.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest
from pyiceberg.catalog.rest import RestCatalog
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.tables import NotExpirable

runner = CliRunner()


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    yield p
    p.close()


def _files_under(location: str) -> dict[str, int]:
    root = Path(location.removeprefix("file://"))
    return {str(f): f.stat().st_size for f in root.rglob("*") if f.is_file()}


def _rebuild(project: Project, csv: Path, n: int) -> None:
    """The dbt materialisation's path: delete then insert, in place, two snapshots."""
    project.engine.execute(
        f"COPY (SELECT range AS id, 'c' || (range % 7) AS c, range * {n}.5 AS amt "
        f"FROM range({1000 * n})) TO '{csv}' (HEADER)"
    )
    if project.tables._exists("orders"):
        project.engine.execute("DELETE FROM querysolo.main.orders")
        project.engine.execute(
            f"INSERT INTO querysolo.main.orders SELECT * FROM read_csv_auto('{csv}')"
        )
    else:
        project.tables.import_file(csv)


def test_expire_removes_old_snapshots_and_only_their_files(project, tmp_path) -> None:
    csv = tmp_path / "orders.csv"
    for n in (1, 2, 3, 4):
        _rebuild(project, csv, n)
    md = project.tables._metadata("orders")
    snapshots = len(md.snapshots)
    assert snapshots >= 4, "a create and three in-place rebuilds"
    before = _files_under(md.location)
    described = project.tables.describe("orders")
    assert described.snapshots == snapshots
    # nothing is a week old, so the project's retention would expire nothing
    assert described.expirable_snapshots == 0 and described.reclaimable_bytes == 0
    # the snapshot list the app's table detail shows: newest first, the current one marked
    listed = described.snapshot_list
    assert len(listed) == snapshots and listed[0]["current"] and not listed[1]["current"]
    assert listed[0]["timestamp"] >= listed[-1]["timestamp"]
    assert all(not s["expirable"] for s in listed)
    assert listed[-1]["operation"] == "append" and listed[-1]["added_rows"] == 1000
    assert project.tables.expire("orders").snapshots_removed == 0
    assert _files_under(md.location) == before, "nothing to expire means nothing deleted"

    report = project.tables.expire("orders", keep_days=0)
    assert report.snapshots_before == snapshots and report.snapshots_removed == snapshots - 1
    assert report.files_removed > 0 and report.bytes_reclaimed > 0
    md = project.tables._metadata("orders")
    assert len(md.snapshots) == 1 and md.current_snapshot() is not None
    after = _files_under(md.location)
    assert len(after) < len(before), "the files only old snapshots referenced are gone"
    kept = project.tables._referenced_files(md)
    for path in kept:
        assert Path(path.removeprefix("file://")).exists(), f"{path} is still needed"
    # the table reads back whole, through DuckDB and through pyiceberg
    rows = project.engine.execute("select count(*), max(amt) from orders").fetchone()
    assert rows == (4000, (4000 - 1) * 4.5)
    catalog = RestCatalog("querysolo", uri=project.catalog_url, **project.io_properties)
    table = catalog.load_table("main.orders")
    assert table.scan().to_arrow().num_rows == 4000
    assert len(table.metadata.snapshots) == 1
    # a fresh rebuild after expiry works, and expiry brings it back to one snapshot
    _rebuild(project, csv, 5)
    assert len(project.tables._metadata("orders").snapshots) == 3
    assert project.tables.expire("orders", keep_days=0).snapshots_removed == 2
    assert project.engine.execute("select count(*) from orders").fetchone()[0] == 5000


def test_a_replace_leaves_orphans_that_expire_sweeps_after_the_grace(project, tmp_path) -> None:
    csv = tmp_path / "orders.csv"
    _rebuild(project, csv, 1)
    location = project.tables._metadata("orders").location
    first_files = _files_under(location)
    project.tables.import_file(csv, mode="replace")  # drop and recreate: the old files stay
    assert len(project.tables._metadata("orders").snapshots) == 1
    assert set(first_files) <= set(_files_under(location)), "the previous table's files linger"
    # inside the grace period nothing is touched; with none, the orphans go
    untouched = project.tables.expire("orders", keep_days=0)
    assert untouched.files_removed == 0
    swept = project.tables.expire("orders", keep_days=0, orphan_grace_seconds=0)
    assert swept.files_removed > 0 and swept.snapshots_removed == 0
    kept = project.tables._referenced_files(project.tables._metadata("orders"))
    remaining = _files_under(location)
    for path in kept:
        assert path.removeprefix("file://") in remaining
    orphans = [
        f for f in remaining if f.endswith((".parquet", ".avro")) and f"file://{f}" not in kept
    ]
    assert orphans == [], orphans
    assert project.engine.execute("select count(*) from orders").fetchone()[0] == 1000


def test_expire_keeps_snapshots_inside_the_retention(project, tmp_path) -> None:
    csv = tmp_path / "orders.csv"
    _rebuild(project, csv, 1)
    _rebuild(project, csv, 2)
    n = len(project.tables._metadata("orders").snapshots)
    # keep_days=1: every snapshot is minutes old, so all stay
    report = project.tables.expire("orders", keep_days=1)
    assert report.snapshots_removed == 0 and report.files_removed == 0
    assert len(project.tables._metadata("orders").snapshots) == n


def test_an_attached_table_is_refused(project, tmp_path) -> None:
    prefix = tmp_path / "raw"
    prefix.mkdir()
    project.engine.execute(
        f"COPY (SELECT range AS id FROM range(10)) TO '{prefix}/part-0.parquet' (FORMAT parquet)"
    )
    project.tables.attach("raw", str(prefix))
    with pytest.raises(NotExpirable, match="registered from"):
        project.tables.expire("raw", keep_days=0)
    assert (prefix / "part-0.parquet").exists()


def test_the_verb_the_setting_and_the_route(project, tmp_path) -> None:
    csv = tmp_path / "orders.csv"
    _rebuild(project, csv, 1)
    _rebuild(project, csv, 2)
    root = str(project.root)
    toml = tomllib.loads((project.root / "querysolo.toml").read_text())
    assert toml["catalog"]["keep_snapshots_days"] == 7
    assert (
        runner.invoke(
            app, ["-C", root, "config", "set", "catalog.keep_snapshots_days", "0"]
        ).exit_code
        == 0
    )
    project.close()
    described = runner.invoke(app, ["-C", root, "tables", "describe", "orders"])
    assert described.exit_code == 0 and "snapshot(s) older than 0 days" in described.output
    assert "querysolo tables expire orders" in " ".join(described.output.split()), "the hint, however it wraps"
    expired = runner.invoke(app, ["-C", root, "tables", "expire", "orders"])
    assert expired.exit_code == 0, expired.output
    assert "of 3 snapshot(s) expired (keeping 0 days)" in expired.output
    assert runner.invoke(app, ["-C", root, "tables", "expire"]).exit_code == 1
    everything = runner.invoke(app, ["-C", root, "tables", "expire", "--all"])
    assert everything.exit_code == 0 and "0 of 1 snapshot(s) expired" in everything.output
