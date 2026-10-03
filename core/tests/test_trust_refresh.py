# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T2: an attached file that changes under the same path is detected. Refresh
compares every registered file's size with its manifest entry and its modification time
with the last verification; a mismatch names the file and refuses until the prefix is
registered again with ``attach --replace``. ``describe`` carries the same check as a line."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.register import VERIFIED_PROPERTY, ChangedFiles
from tests.s3_helpers import open_store
from tests.test_step8_remote import write_part


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
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    yield p
    p.close()


@pytest.fixture
def events(env, tmp_path):
    prefix = env.key(f"raw-{tmp_path.name}/events")
    for i in range(3):
        write_part(env, f"{prefix}/part-{i}.parquet", i * 1000, 1000)
    return SimpleNamespace(prefix=env.uri(prefix) + "/", key=prefix, s3=env)


def _verified_at(project, name: str) -> str:
    return project.metadata_io.read(project.store.get_table("main", name)).properties[
        VERIFIED_PROPERTY
    ]


def test_a_file_rewritten_with_different_content_is_refused_by_name_and_replace_recovers(
    project, events, env
) -> None:
    project.tables.attach("events", events.prefix)
    stamp = _verified_at(project, "events")
    assert project.tables.describe("events").changed_files == []

    write_part(env, f"{events.key}/part-1.parquet", 1000, 2500)  # same key, more rows
    with pytest.raises(ChangedFiles, match=r"part-1\.parquet \(size") as e:
        project.tables.refresh("events")
    assert "attach --replace events" in str(e.value)
    assert _verified_at(project, "events") == stamp  # a refused refresh moves nothing

    desc = project.tables.describe("events")
    assert [uri.rsplit("/", 1)[1] for uri, _ in desc.changed_files] == ["part-1.parquet"]
    assert desc.changed_files[0][1].startswith("size ")
    assert desc.verified_at == stamp

    info = project.tables.attach("events", events.prefix, replace=True)
    assert info.rows == 4500 and info.name == "events"
    assert [t.name for t in project.tables.list()] == ["events"]
    assert project.tables.describe("events").changed_files == []
    assert project.engine.execute("select count(*) from events").fetchone()[0] == 4500


def test_a_file_rewritten_after_the_attach_is_refused_even_at_the_same_size(
    project, events, env
) -> None:
    """pyarrow's listing carries no ETag, so a same-size rewrite is caught by its time: a
    byte-identical re-upload after the attach reads as changed too, which is the safe side."""
    project.tables.attach("events", events.prefix)
    time.sleep(3.5)  # past the rewrite grace plus S3's second-resolution LastModified
    write_part(env, f"{events.key}/part-2.parquet", 2000, 1000)  # the same rows again
    with pytest.raises(ChangedFiles, match=r"part-2\.parquet \(rewritten"):
        project.tables.refresh("events")


def test_a_new_file_is_still_added_and_the_stamp_moves_forward(project, events, env) -> None:
    project.tables.attach("events", events.prefix)
    stamp = _verified_at(project, "events")
    time.sleep(3.5)
    write_part(env, f"{events.key}/part-3.parquet", 3000, 500)
    report = project.tables.refresh("events")
    assert (report.added, report.files, report.rows) == (1, 4, 3500)
    assert _verified_at(project, "events") > stamp
    assert project.tables.describe("events").changed_files == []


def test_a_local_prefix_is_verified_the_same_way(project, tmp_path) -> None:
    folder = tmp_path / "local-events"
    folder.mkdir()
    for i in range(2):
        project.engine.execute(
            f"COPY (SELECT range AS id, range * 2 AS v FROM range({i * 10}, {i * 10 + 10})) "
            f"TO '{folder}/part-{i}.parquet' (FORMAT parquet)"
        )
    project.tables.attach("local_events", f"file://{folder}/")
    assert project.tables.refresh("local_events").added == 0
    project.engine.execute(
        f"COPY (SELECT range AS id, range * 2 AS v FROM range(0, 100)) "
        f"TO '{folder}/part-0.parquet' (FORMAT parquet)"
    )
    with pytest.raises(ChangedFiles, match="part-0.parquet"):
        project.tables.refresh("local_events")
    assert len(project.tables.describe("local_events").changed_files) == 1


def test_the_cli_refuses_and_replaces(project, events, env) -> None:
    project.tables.attach("events", events.prefix)
    write_part(env, f"{events.key}/part-0.parquet", 0, 10)
    runner = CliRunner()
    r = runner.invoke(app, ["-C", str(project.root), "tables", "refresh", "events"])
    assert r.exit_code != 0 and "changed under the same path" in " ".join(r.output.split())
    r = runner.invoke(app, ["-C", str(project.root), "tables", "describe", "events"])
    assert "1 changed under the same path" in " ".join(r.output.split())
    r = runner.invoke(app, ["-C", str(project.root), "tables", "attach", "events", events.prefix])
    assert r.exit_code != 0 and "--replace" in r.output
    r = runner.invoke(
        app, ["-C", str(project.root), "tables", "attach", "--replace", "events", events.prefix]
    )
    assert r.exit_code == 0, r.output
    assert "2,010 rows" in r.output
    r = runner.invoke(app, ["-C", str(project.root), "tables", "describe", "events"])
    assert "files: verified against" in r.output
