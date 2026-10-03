# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T4: the recovery contract, one test per sentence of ``/docs/recovery``. If a
sentence on that page has no test here, it does not belong on the page. Plus the schema
version both stores now read back: newer refuses, older migrates, current opens silently."""

from __future__ import annotations

import errno
import shutil

import pytest
import sqlalchemy as sa
from typer.testing import CliRunner

from querysolo import Project, __version__
from querysolo.catalog import store as catalog_store
from querysolo.cli import app
from querysolo.schema import SchemaTooNew


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    csv = tmp_path / "orders.csv"
    csv.write_text("id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n")
    p.tables.import_file(csv)
    more = tmp_path / "more.csv"
    more.write_text("id,customer,amt\n4,c2,2.0\n")
    p.tables.import_file(more, name="orders", mode="append")
    p.questions.save("Revenue", "select customer, sum(amt) as revenue from orders group by 1")
    yield p
    p.close()


def _rows(p: Project) -> int:
    return p.engine.execute("select count(*) from orders").fetchone()[0]


# -- the sentences of /docs/recovery ----------------------------------------------------


def test_a_copy_of_the_project_folder_restored_to_the_same_path_is_a_complete_backup(
    project, tmp_path
) -> None:
    root = project.root
    project.close()
    backup = tmp_path / "backup"
    shutil.copytree(root, backup)
    shutil.rmtree(root)
    shutil.copytree(backup, root)
    p = Project.open(root)
    try:
        assert _rows(p) == 4
        assert p.tables.describe("orders").snapshots == 2
        assert p.questions.get("revenue").title == "Revenue"
        assert len(p.versions.list("revenue")) == 1
    finally:
        p.close()


def test_the_derived_folders_can_be_deleted_and_are_rebuilt(project) -> None:
    root = project.root
    project.close()
    shutil.rmtree(root / ".querysolo" / "cache", ignore_errors=True)
    shutil.rmtree(root / ".querysolo" / "dbt", ignore_errors=True)
    p = Project.open(root)
    try:
        assert _rows(p) == 4
        est = p.estimate("select sum(amt) from orders")
        assert est.verdict == "green"  # the manifest cache is rebuilt on first use
        assert (root / ".querysolo" / "cache").is_dir()
    finally:
        p.close()


def test_a_failure_mid_import_leaves_the_previous_snapshot_current(project, tmp_path) -> None:
    from querysolo import tables

    real = tables.run_with_retry

    def crash(engine, sql, attempts=3):
        if sql.startswith("INSERT INTO"):
            raise RuntimeError("crash (simulated)")
        return real(engine, sql, attempts)

    more = tmp_path / "even-more.csv"
    more.write_text("id,customer,amt\n5,c3,9.0\n")
    before = project.tables.describe("orders")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tables, "run_with_retry", crash)
        with pytest.raises(RuntimeError):
            project.tables.import_file(more, name="orders", mode="append")
    after = project.tables.describe("orders")
    assert _rows(project) == 4
    assert after.snapshot_id == before.snapshot_id and after.snapshots == before.snapshots


def test_both_databases_are_sqlite_in_wal_mode(project) -> None:
    for engine in (project.store.engine, project.history.engine):
        with engine.connect() as c:
            assert c.execute(sa.text("PRAGMA journal_mode")).scalar() == "wal"


def test_a_full_disk_fails_the_commit_names_the_disk_and_writes_nothing_half(
    project, tmp_path, monkeypatch
) -> None:
    csv = tmp_path / "new.csv"
    csv.write_text("a,b\n1,2\n")
    mio = project.metadata_io

    def no_space(*args, **kwargs):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(type(mio), "write", no_space)
    with pytest.raises(Exception, match="No space left on device"):
        project.tables.import_file(csv)
    assert [t.name for t in project.tables.list()] == ["orders"]
    assert _rows(project) == 4


def test_expire_never_removes_a_file_the_current_snapshot_references(project) -> None:
    report = project.tables.expire("orders", keep_days=0, orphan_grace_seconds=0)
    assert report.snapshots_removed == 1
    md = project.tables._metadata("orders")
    for path in project.tables._referenced_files(md):
        assert project.metadata_io.io.new_input(path).exists()
    assert _rows(project) == 4


# -- the schema version (T4) --------------------------------------------------------------


def _set_version(path, value: str) -> None:
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        c.execute(sa.text("UPDATE meta SET value = :v WHERE key = 'schema_version'"), {"v": value})
    engine.dispose()


def test_a_newer_schema_is_refused_with_the_sentence_and_the_file_untouched(project) -> None:
    root = project.root
    project.close()
    catalog = root / ".querysolo" / "catalog.db"
    _set_version(catalog, "2")
    with pytest.raises(SchemaTooNew, match="newer QuerySolo") as e:
        Project.open(root)
    assert f"this is {__version__}, which reads schema 1" in str(e.value)
    engine = sa.create_engine(f"sqlite:///{catalog}")
    with engine.connect() as c:
        version = c.execute(sa.text("SELECT value FROM meta WHERE key='schema_version'"))
        assert version.scalar() == "2"
        assert c.execute(sa.text("SELECT count(*) FROM tables")).scalar() == 1
    engine.dispose()
    r = CliRunner().invoke(app, ["-C", str(root), "tables", "list"])
    assert r.exit_code == 1 and "newer QuerySolo" in " ".join(r.output.split())


def test_an_older_schema_runs_the_migration_once_and_records_the_version(
    project, monkeypatch
) -> None:
    root = project.root
    project.close()
    history = root / ".querysolo" / "history.db"
    _set_version(history, "0")
    ran: list[int] = []

    def migrate(c) -> None:
        ran.append(1)
        c.execute(sa.text("CREATE TABLE IF NOT EXISTS migrated_marker (x INTEGER)"))

    from querysolo import history as history_module

    monkeypatch.setattr(history_module, "MIGRATIONS", [(1, migrate)])
    p = Project.open(root)
    p.history.recent()  # history opens lazily, on first use
    p.close()
    p = Project.open(root)
    p.history.recent()
    p.close()
    assert ran == [1]
    engine = sa.create_engine(f"sqlite:///{history}")
    with engine.connect() as c:
        rows = dict(c.execute(sa.text("SELECT key, value FROM meta")).all())
    engine.dispose()
    assert rows["schema_version"] == "1" and rows["written_by"] == __version__


def test_the_current_schema_opens_silently_and_records_who_wrote_it(project) -> None:
    from querysolo import history as history_module

    for engine, current in (
        (project.store.engine, catalog_store.SCHEMA_VERSION),
        (project.history.engine, history_module.SCHEMA_VERSION),
    ):
        with engine.connect() as c:
            rows = dict(c.execute(sa.text("SELECT key, value FROM meta")).all())
        assert rows["schema_version"] == str(current)
        assert rows["written_by"] == __version__
