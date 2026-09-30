# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T1: a replace that fails leaves the old table exactly as it was. The new
table is built under a temporary name before anything is dropped; the swap is a drop and a
rename; an interrupted swap is listed with the sentence that finishes it."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.catalog.store import REPLACE_SUFFIX
from querysolo.cli import app
from querysolo.tables import NotExpirable, ReservedName, TableExists, replace_name


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    yield p
    p.close()


@pytest.fixture
def orders(project, tmp_path):
    """An imported table with two snapshots, and a second file to replace it with."""
    first = tmp_path / "orders.csv"
    first.write_text("id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n")
    project.tables.import_file(first)
    more = tmp_path / "more.csv"
    more.write_text("id,customer,amt\n4,c2,2.0\n")
    project.tables.import_file(more, name="orders", mode="append")
    second = tmp_path / "orders2.csv"
    second.write_text("id,customer,amt,region\n10,c9,9.0,north\n11,c9,1.0,south\n")
    return {"first": first, "second": second}


def _rows(project, name="orders") -> int:
    return project.engine.execute(f"select count(*) from querysolo.main.{name}").fetchone()[0]


def _snapshots(project, name="orders") -> int:
    return project.tables.describe(name).snapshots


def test_a_file_that_does_not_parse_leaves_the_old_table_with_its_rows_and_history(
    project, orders, tmp_path
) -> None:
    assert _rows(project) == 4 and _snapshots(project) == 2
    bad = tmp_path / "bad.json"
    bad.write_text("{not json at all")
    import duckdb

    with pytest.raises(duckdb.Error):
        project.tables.import_file(bad, name="orders", mode="replace")
    assert _rows(project) == 4 and _snapshots(project) == 2
    assert [t.name for t in project.tables.list()] == ["orders"]


def test_a_failure_inside_the_create_leaves_the_old_table_and_no_temporary(
    project, orders, monkeypatch
) -> None:
    from querysolo import tables

    real = tables.run_with_retry

    def failing(engine, sql, attempts=3):
        if sql.startswith("CREATE TABLE"):
            raise RuntimeError("disk full (simulated)")
        return real(engine, sql, attempts)

    monkeypatch.setattr(tables, "run_with_retry", failing)
    with pytest.raises(RuntimeError, match="disk full"):
        project.tables.import_file(orders["second"], name="orders", mode="replace")
    assert _rows(project) == 4 and _snapshots(project) == 2
    assert [t.name for t in project.tables.list()] == ["orders"]


def test_a_replace_that_succeeds_keeps_the_name_and_folder_and_leaves_no_temporary(
    project, orders
) -> None:
    before = project.tables.describe("orders")
    info = project.tables.import_file(orders["second"], name="orders", mode="replace")
    assert info.name == "orders" and info.rows == 2
    assert [c for c, _ in info.columns] == ["id", "customer", "amt", "region"]
    assert info.location == before.location  # the swap moved no data
    assert [t.name for t in project.tables.list()] == ["orders"]
    assert _rows(project) == 2
    # the old files are orphans in the shared folder, swept by expire after its grace
    report = project.tables.expire("orders", orphan_grace_seconds=0)
    assert report.files_removed >= 1


def test_the_temporary_name_is_refused_for_a_users_table(project, orders) -> None:
    with pytest.raises(ReservedName):
        project.tables.import_file(orders["second"], name=f"mine{REPLACE_SUFFIX}")
    runner = CliRunner()
    args = [
        "-C",
        str(project.root),
        "import",
        str(orders["second"]),
        "--name",
        "x" + REPLACE_SUFFIX,
    ]
    r = runner.invoke(app, args)
    assert r.exit_code != 0 and "QuerySolo's own" in r.output


def test_an_interrupted_swap_is_listed_with_the_sentence_and_rename_finishes_it(
    project, orders, monkeypatch
) -> None:
    from querysolo import tables

    real = tables.run_with_retry

    def crash_before_rename(engine, sql, attempts=3):
        if sql.startswith("ALTER TABLE"):
            raise RuntimeError("crash (simulated)")
        return real(engine, sql, attempts)

    monkeypatch.setattr(tables, "run_with_retry", crash_before_rename)
    with pytest.raises(RuntimeError, match="crash"):
        project.tables.import_file(orders["second"], name="orders", mode="replace")
    monkeypatch.setattr(tables, "run_with_retry", real)

    temp = replace_name("orders")
    listed = project.tables.list()
    assert [t.name for t in listed] == [temp]
    assert listed[0].interrupted_replace_of == "orders"
    assert _rows(project, temp) == 2  # the data is never invisible

    runner = CliRunner()
    r = runner.invoke(app, ["-C", str(project.root), "tables", "list"])
    assert f"querysolo tables rename {temp} orders" in " ".join(r.output.split())  # rich wraps

    r = runner.invoke(app, ["-C", str(project.root), "tables", "rename", temp, "orders"])
    assert r.exit_code == 0, r.output
    assert [t.name for t in project.tables.list()] == ["orders"]
    assert _rows(project) == 2
    assert [c for c, _ in project.tables.describe("orders").columns][-1] == "region"


def test_expire_refuses_while_a_replace_is_interrupted_and_rename_checks_both_names(
    project, orders, monkeypatch
) -> None:
    from querysolo import tables

    real = tables.run_with_retry
    monkeypatch.setattr(
        tables,
        "run_with_retry",
        lambda e, sql, attempts=3: (
            (_ for _ in ()).throw(RuntimeError("crash"))
            if sql.startswith('DROP TABLE querysolo.main."orders"')
            else real(e, sql, attempts)
        ),
    )
    with pytest.raises(RuntimeError):
        project.tables.import_file(orders["second"], name="orders", mode="replace")
    monkeypatch.setattr(tables, "run_with_retry", real)
    # both exist: the old table and the finished temporary
    assert sorted(t.name for t in project.tables.list()) == ["orders", replace_name("orders")]
    with pytest.raises(NotExpirable, match="interrupted"):
        project.tables.expire("orders")
    with pytest.raises(TableExists):
        project.tables.rename(replace_name("orders"), "orders")
    # a second replace supersedes the stale temporary and completes
    info = project.tables.import_file(orders["second"], name="orders", mode="replace")
    assert info.rows == 2 and [t.name for t in project.tables.list()] == ["orders"]
