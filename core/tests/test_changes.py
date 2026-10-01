# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Decisions L2: `querysolo changes` — an import, a run, a save and a restore appear in
order with the right shapes, merged from the catalog's snapshots, history's runs and git's
commits; `--since` and a name filter; the route. Against a real dbt project."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.changes import changes, parse_since
from querysolo.cli import app
from querysolo.dbt import runner

pytest.importorskip("dbt.cli.main")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=0)
    (root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\nselect c, sum(amt) as total from src group by 1\n"
    )
    p = Project.open(root, serve=True)
    p.engine.execute(
        "create table querysolo.main.src as "
        "select range as id, 'c' || (range % 3) as c, range * 1.5 as amt from range(300)"
    )
    yield p
    p.close()


def _kinds(feed) -> list[tuple[str, str | None]]:
    return [(c.kind, c.name) for c in feed]


def test_an_import_a_run_a_save_and_a_restore_in_order(project) -> None:
    p = project
    # before anything but the create: one snapshot, and init's own version (its dbt files
    # under models/), about the project rather than a model
    feed = changes(p)
    assert _kinds(feed) == [("snapshot", "src"), ("version", None)]
    assert feed[1].target == "project" and feed[1].message == "querysolo init"
    assert feed[1].names == [] and feed[1].sentence().startswith("querysolo init · by ")
    src = feed[0]
    assert src.target == "table" and src.operation == "append" and src.added_rows == 300
    assert src.affects == [] and src.sentence() == "src: 300 rows added"

    # a run: the model's run and, with auto_commit, the run-time version of its file. A
    # commit's time is whole seconds, so each step waits a second to keep the order plain.
    report = runner.run(p)
    assert report.ok
    time.sleep(1.1)
    # a save, twice (the second is an update), then a restore of the first
    first = p.questions.save("Total", "select sum(amt) as total from src")
    time.sleep(1.1)
    p.questions.save("Total", "select sum(amt) as total from src where amt > 1")
    time.sleep(1.1)
    p.versions.restore("total", first.commit)
    time.sleep(1.1)
    # an append to src: the newest snapshot names the model it made out of date (L3)
    p.engine.execute("insert into querysolo.main.src values (999, 'c9', 9.0)")

    feed = changes(p)
    kinds = _kinds(feed)
    assert kinds[0] == ("snapshot", "src")
    assert feed[0].affects == ["by_c"] and "made out of date: by_c" in feed[0].sentence()
    assert kinds[1] == ("version", "total") and feed[1].message.startswith("restore question:")
    assert feed[1].target == "question" and feed[1].names == ["total"] and len(feed[1].id) == 7
    assert kinds[2] == ("version", "total") and feed[2].message == "update question: Total"
    assert kinds[3] == ("version", "total") and feed[3].message == "save question: Total"
    # the run's entries: by_c's snapshot (dbt built a table), its run, the run-time version
    run_entries = [c for c in feed if c.kind == "run"]
    assert [(c.name, c.target, c.ok) for c in run_entries] == [("by_c", "model", True)]
    assert run_entries[0].seconds is not None and run_entries[0].verdict in ("green", "yellow")
    assert run_entries[0].sentence().startswith("by_c built in ")
    assert ("snapshot", "by_c") in kinds
    run_version = [c for c in feed if c.kind == "version" and c.message.startswith("run:")]
    assert len(run_version) == 1 and run_version[0].names == ["by_c"]
    assert run_version[0].target == "model" and run_version[0].name == "by_c"
    assert kinds[-2:] == [("snapshot", "src"), ("version", None)]  # the create, then init
    assert all(feed[i].when >= feed[i + 1].when for i in range(len(feed) - 1))
    for c in feed:
        assert c.sentence()

    # the name filter: only what happened to total (its versions), then to src
    total = changes(p, name="total")
    assert {c.kind for c in total} == {"version"} and len(total) == 3
    assert [c.kind for c in changes(p, name="src")] == ["snapshot", "snapshot"]
    assert [c.name for c in changes(p, name="by_c")] == ["by_c"] * 3  # snapshot, run, version
    assert changes(p, name="nowhere") == []
    # since: a cutoff after the restore leaves the insert alone; last caps
    cutoff = feed[1].when
    assert _kinds(changes(p, since=cutoff)) == kinds[:2]
    assert len(changes(p, last=2)) == 2 and _kinds(changes(p, last=2)) == kinds[:2]

    # a second run is a second entry: history keeps every run (schema 2); this run also
    # builds the question saved above, so total has its first
    runner.run(p)
    assert sorted(c.name for c in changes(p) if c.kind == "run") == ["by_c", "by_c", "total"]
    assert [c.name for c in changes(p, name="by_c") if c.kind == "run"] == ["by_c", "by_c"]
    assert len([c for c in changes(p, name="total") if c.kind == "run"]) == 1


def test_since_parsing() -> None:
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    assert abs((now - parse_since("2d")) - timedelta(days=2)) < timedelta(seconds=5)
    assert abs((now - parse_since("12h")) - timedelta(hours=12)) < timedelta(seconds=5)
    assert parse_since("2026-09-01") == datetime(2026, 9, 1, tzinfo=UTC)
    assert parse_since("2026-09-01T10:00:00+02:00").isoformat() == "2026-09-01T10:00:00+02:00"
    with pytest.raises(ValueError, match="--since takes"):
        parse_since("yesterday")


def test_json_survives_a_narrow_terminal(project) -> None:
    """`--json` is for programs: a line longer than the terminal (CI's 80 columns and its long
    temporary paths) must not be wrapped into the middle of a string."""
    p = project
    runner.run(p)
    p.questions.save("A question with a long enough title to pass forty columns", "select sum(amt) as total from src")
    for argv in (["changes", "--json"], ["lineage", "--all", "--json"]):
        r = CliRunner().invoke(app, ["-C", str(p.root), *argv], env={"COLUMNS": "40"})
        assert r.exit_code == 0, r.output
        json.loads(r.output)


def test_the_cli_and_the_route(project) -> None:
    p = project
    runner.run(p)
    p.questions.save("Total", "select sum(amt) as total from src")
    r = CliRunner().invoke(app, ["-C", str(p.root), "changes"])
    assert r.exit_code == 0, r.output
    text = "".join(r.output.split())
    assert "versionsavequestion:Total" in text and "runby_cbuiltin" in text
    assert "snapshotsrc:300rowsadded" in text
    r = CliRunner().invoke(app, ["-C", str(p.root), "changes", "total", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert [d["kind"] for d in data] == ["version"] and data[0]["when"].endswith("+00:00")
    r = CliRunner().invoke(app, ["-C", str(p.root), "changes", "nowhere"])
    assert r.exit_code == 0 and "nothing about nowhere" in r.output
    r = CliRunner().invoke(app, ["-C", str(p.root), "changes", "--since", "yesterday"])
    assert r.exit_code == 1 and "--since takes" in r.output

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    body = client.get("/api/changes").json()
    assert body == json.loads(
        CliRunner().invoke(app, ["-C", str(p.root), "changes", "--json"]).output
    )
    assert {c["kind"] for c in body} == {"snapshot", "run", "version"}
    two = client.get("/api/changes", params={"last": 2, "since": "1d"}).json()
    assert len(two) == 2
    assert client.get("/api/changes", params={"name": "by_c"}).json()[0]["name"] == "by_c"
    assert client.get("/api/changes", params={"since": "soon"}).status_code == 400
    client.close()


def test_a_project_without_git_or_models_still_answers(tmp_path) -> None:
    """A folder that is no repository and has never compiled: the snapshots alone."""
    root = tmp_path / "bare"
    Project.init(root, probe_mb=0)
    import shutil

    shutil.rmtree(root / ".git", ignore_errors=True)
    p = Project.open(root, serve=False)
    try:
        p.engine.execute("create table querysolo.main.t as select 1 as x")
        feed = changes(p)
        assert _kinds(feed) == [("snapshot", "t")] and feed[0].affects == []
        assert Path(root / ".git").exists() is False
    finally:
        p.close()


def test_a_schema_one_history_migrates_and_keeps_its_last_runs(tmp_path) -> None:
    """Schema 2 (2026-09-20): `model_runs` and `question_runs` keyed by the run. A file
    from before it — one row per model and per question, the latest run — is rewritten in
    place on open, its rows kept, and runs accumulate from then on."""
    import sqlalchemy as sa

    from querysolo import history as history_module
    from querysolo.history import History

    path = tmp_path / "history.db"
    h = History(path)
    run_a = h.record(_run())
    run_b = h.record(_run())
    h.close()
    # back to the schema-1 shape by hand: the old tables and the old version
    engine = sa.create_engine(f"sqlite:///{path}")
    with engine.begin() as c:
        for table, key in (("model_runs", "unique_id"), ("question_runs", "slug")):
            c.execute(sa.text(f"DROP TABLE {table}"))
            c.execute(
                sa.text(
                    f"CREATE TABLE {table} ({key} VARCHAR(255) PRIMARY KEY, ts DATETIME NOT NULL, "
                    "run_id INTEGER NOT NULL REFERENCES runs (id))"
                )
            )
        c.execute(
            sa.text("INSERT INTO model_runs VALUES ('model.proj.by_c', '2026-09-19 10:00:00', :r)"),
            {"r": run_a},
        )
        c.execute(
            sa.text("INSERT INTO question_runs VALUES ('total', '2026-09-19 10:00:01', :r)"),
            {"r": run_b},
        )
        c.execute(sa.text("UPDATE meta SET value = '1' WHERE key = 'schema_version'"))
    engine.dispose()

    h = History(path)
    with h.engine.connect() as c:
        version = c.execute(sa.text("SELECT value FROM meta WHERE key = 'schema_version'")).scalar()
    assert version == str(history_module.SCHEMA_VERSION) == "3"  # 3: the rename (plan R5)
    assert h.model_last_run("model.proj.by_c").id == run_a
    assert h.question_last_run("total") is not None
    assert sorted(k for _, k, _ in h.model_and_question_runs()) == ["model.proj.by_c", "total"]
    # runs accumulate now, and the last is the newest
    run_c = h.record(_run())
    h.record_model_run("model.proj.by_c", run_c)
    assert h.model_last_run("model.proj.by_c").id == run_c
    assert [k for t, k, _ in h.model_and_question_runs() if t == "model"] == ["model.proj.by_c"] * 2
    h.close()


def _run():
    from querysolo.history import Run

    return Run(
        fingerprint="f",
        sql_hash="h",
        sql_text="select 1",
        querysolo_version="0",
        duckdb_version="0",
        machine_hash="m",
        machine={},
        ran=True,
        actual_wall=0.1,
        verdict="green",
    )
