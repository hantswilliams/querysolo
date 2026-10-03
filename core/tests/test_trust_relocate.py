# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T5: a moved or copied project folder says so on open, and ``querysolo relocate``
makes its tables resolve again with every snapshot kept — including a position-delete
file, whose rows name the data file by absolute path and are written again."""

from __future__ import annotations

import shutil

import pytest
from typer.testing import CliRunner

from querysolo import Project, relocate
from querysolo.cli import app


@pytest.fixture
def moved(tmp_path):
    """A project with a table of three snapshots (create, append, delete) and a saved
    question, moved to another folder after it was closed."""
    root = tmp_path / "acme"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 5) AS c, "
        "range * 1.5 AS amt FROM range(1000)"
    )
    p.engine.execute(
        "INSERT INTO querysolo.main.orders SELECT range, 'x', 1.0 FROM range(1000, 1500)"
    )
    p.engine.execute("DELETE FROM querysolo.main.orders WHERE id < 10")
    p.questions.save("Total", "select sum(amt) as total from orders")
    first_snapshot = p.tables.describe("orders").snapshot_list[-1]["id"]
    p.close()
    new_root = tmp_path / "elsewhere" / "acme"
    new_root.parent.mkdir()
    shutil.move(str(root), str(new_root))
    return {"old": root, "new": new_root, "first_snapshot": first_snapshot}


def test_a_moved_project_opens_says_where_it_was_and_marks_its_tables(moved) -> None:
    p = Project.open(moved["new"])
    try:
        assert relocate.moved_from(p) == str(moved["old"])
        [orders] = p.tables.list(views=False)
        assert orders.needs_relocate and orders.name == "orders" and orders.rows == 0
        r = CliRunner().invoke(app, ["-C", str(moved["new"]), "tables", "list"])
        assert r.exit_code == 0, r.output
        # rich wraps at the terminal width, so compare with all whitespace removed
        text = "".join(r.output.split())
        assert f"movedfrom{moved['old']}" in text and "querysolorelocate" in text
    finally:
        p.close()


def test_relocate_makes_every_snapshot_resolve_for_duckdb_and_pyiceberg(moved) -> None:
    from pyiceberg.catalog.rest import RestCatalog

    p = Project.open(moved["new"])
    try:
        report = relocate.relocate(p)
        assert report.relocated == ["orders"] and report.skipped == []
        assert report.data_files == 1  # the position-delete file, written again
        assert relocate.moved_from(p) is None
        assert p.engine.execute("select count(*) from orders").fetchone()[0] == 1490
        desc = p.tables.describe("orders")
        assert desc.snapshots == 3 and desc.rows == 1490 and not desc.needs_relocate
        assert desc.location.startswith(f"file://{moved['new']}")
        table = RestCatalog("querysolo", uri=p.catalog_url, **p.io_properties).load_table(
            "main.orders"
        )
        assert table.scan().to_arrow().num_rows == 1490
        assert all(
            t.file.file_path.startswith(f"file://{moved['new']}") for t in table.scan().plan_files()
        )
        old_count = p.engine.execute(
            f"select count(*) from orders AT (VERSION => {moved['first_snapshot']})"
        ).fetchone()[0]
        assert old_count == 1000  # history survives the move
        assert p.questions.get("total").sql.startswith("select sum(amt)")
        # a second relocate has nothing to do
        again = relocate.relocate(p)
        assert again.relocated == [] and again.old_root is None
    finally:
        p.close()


def test_the_verb_and_the_route(moved) -> None:
    import httpx

    r = CliRunner().invoke(app, ["-C", str(moved["new"]), "relocate"])
    assert r.exit_code == 0, r.output
    assert "relocated 1 table(s)" in r.output and "orders" in r.output
    r = CliRunner().invoke(app, ["-C", str(moved["new"]), "relocate"])
    assert "nothing to relocate" in r.output
    p = Project.open(moved["new"], serve=True)
    try:
        client = httpx.Client(
            base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
        )
        assert client.get("/api/health").json()["moved_from"] is None
        assert client.post("/api/relocate").json()["relocated"] == []
        client.close()
    finally:
        p.close()


def test_an_attached_table_is_skipped_and_the_old_files_are_orphans_expire_sweeps(
    moved, tmp_path
) -> None:
    p = Project.open(moved["new"])
    try:
        folder = tmp_path / "outside"
        folder.mkdir()
        p.engine.execute(
            f"COPY (SELECT range AS id FROM range(5)) TO '{folder}/a.parquet' (FORMAT parquet)"
        )
        p.tables.attach("outside", f"file://{folder}/")
        report = relocate.relocate(p)
        assert report.relocated == ["orders"] and report.skipped == ["outside"]
        assert p.engine.execute("select count(*) from outside").fetchone()[0] == 5
        swept = p.tables.expire("orders", keep_days=0, orphan_grace_seconds=0)
        assert swept.files_removed >= 1  # the old manifests and the old delete file
        assert p.engine.execute("select count(*) from orders").fetchone()[0] == 1490
    finally:
        p.close()
