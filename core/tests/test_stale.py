# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Decisions-for-review V3 (2026-09-16), built in versions step 4: every planned model
carries a state — `never`, `fresh`, `edited`, `upstream` — computed from lineage's graph
and history at plan time, each provoked here; `querysolo run --stale` builds only the models
that are not fresh, in dependency order, and nothing when every model is fresh; the CLI's
DAG and the routes carry it. Decisions L3 (2026-09-17): a table's snapshots say which
models each one made out of date."""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.dbt import runner

pytest.importorskip("dbt.cli.main")


def _models(root: Path) -> None:
    (root / "models" / "stg_orders.sql").write_text("select id, c, amt from src where amt > 0\n")
    (root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select c, sum(amt) as total from {{ ref('stg_orders') }} group by 1\n"
    )
    (root / "models" / "top.sql").write_text(
        "select c from {{ ref('by_c') }} order by total desc limit 1\n"
    )
    (root / "models" / "sources.yml").write_text(
        "version: 2\nsources:\n  - name: raw\n    database: querysolo\n    schema: main\n"
        "    tables:\n      - name: src\n      - name: other\n"
    )
    (root / "models" / "from_other.sql").write_text(
        "select count(*) as n from {{ source('raw', 'other') }}\n"
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=0)
    _models(root)
    p = Project.open(root, serve=True)
    p.engine.execute(
        "create table querysolo.main.src as "
        "select range as id, 'c' || (range % 3) as c, range * 1.5 as amt from range(300)"
    )
    p.engine.execute("create table querysolo.main.other as select range as id from range(10)")
    p.questions.save("Total", "select sum(amt) as total from src")
    yield p
    p.close()


def _states(models) -> dict[str, tuple[str | None, str | None]]:
    return {m.name: (m.state, m.state_reason) for m in models}


def test_never_then_fresh_and_stale_runs_only_what_is_not_fresh(project) -> None:
    p = project
    planned = runner.plan(p)
    assert all(m.state == "never" and m.state_reason == "never built" for m in planned)
    assert all(m.state_since is None for m in planned)

    report = runner.run(p, stale=True)
    assert report.selected == [m.name for m in planned]  # everything, in dependency order
    assert report.ok and len(report.results) == 5
    after = runner.plan(p)
    assert _states(after) == {m.name: ("fresh", None) for m in planned}

    # nothing is stale: nothing runs, nothing is recorded
    before = {m.name: m.last_run.ts for m in after}
    again = runner.run(p, stale=True)
    assert again.selected == [] and again.results == [] and again.commit is None
    assert {m.name: m.last_run.ts for m in runner.plan(p)} == before


def test_edited_and_upstream_each_provoked_and_repaired(project) -> None:
    p = project
    runner.run(p)
    assert all(m.state == "fresh" for m in runner.plan(p))

    # an edit to one model: that model is edited, what reads it is upstream
    time.sleep(0.01)
    (p.root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select c, sum(amt) as total, count(*) as n from {{ ref('stg_orders') }} group by 1\n"
    )
    planned = runner.plan(p)
    states = _states(planned)
    assert states["by_c"] == ("edited", "the SQL changed since the last run")
    assert states["top"] == ("upstream", "by_c is out of date")
    # what changed is shown, not only said: the diff of the compiled SQL since the run
    diff = {m.name: m.state_diff for m in planned}["by_c"]
    assert diff.startswith("--- last run\n+++ now\n")
    assert "-select c, sum(amt) as total from" in diff
    assert "+select c, sum(amt) as total, count(*) as n from" in diff
    assert all(m.state_diff is None for m in planned if m.name != "by_c")
    assert states["stg_orders"] == ("fresh", None)
    assert states["from_other"] == ("fresh", None) and states["total"] == ("fresh", None)
    report = runner.run(p, stale=True)
    assert report.selected == ["by_c", "top"]
    assert all(m.state == "fresh" for m in runner.plan(p))

    # a table an input reads gets a new snapshot: everything downstream of it is upstream,
    # each naming the thing nearest to it that changed; the rest stays fresh
    time.sleep(0.01)
    p.engine.execute("insert into querysolo.main.src select 1000, 'c9', 9.0")
    planned = runner.plan(p)
    states = _states(planned)
    src_when = p.tables.describe("src").freshness.isoformat()
    assert states["stg_orders"] == ("upstream", "src changed")
    assert states["total"] == ("upstream", "src changed")
    assert states["by_c"] == ("upstream", "stg_orders is out of date")
    assert states["top"] == ("upstream", "by_c is out of date")
    assert states["from_other"] == ("fresh", None)
    by_name = {m.name: m for m in planned}
    assert by_name["stg_orders"].state_since == src_when
    assert by_name["top"].state_since == src_when  # carried down the chain
    # and the commits to the table since the run, for the models that read it directly
    assert by_name["stg_orders"].state_changes == [
        {
            "name": "src",
            "operation": "append",
            "added_rows": 1,
            "deleted_rows": None,
            "timestamp": src_when,
        }
    ]
    assert by_name["total"].state_changes == by_name["stg_orders"].state_changes
    assert by_name["by_c"].state_changes == [] and by_name["by_c"].state_diff is None
    report = runner.run(p, stale=True)
    assert set(report.selected) == {"stg_orders", "total", "by_c", "top"}
    order = report.selected
    assert order.index("stg_orders") < order.index("by_c") < order.index("top")
    assert all(m.state == "fresh" for m in runner.plan(p))

    # a source table the model reads through source(): the same
    time.sleep(0.01)
    p.engine.execute("insert into querysolo.main.other select 99")
    states = _states(runner.plan(p))
    assert states["from_other"] == ("upstream", "other changed")
    assert sum(1 for s in states.values() if s[0] != "fresh") == 1


def test_the_cli_and_the_routes(project) -> None:
    p = project
    r = CliRunner().invoke(app, ["-C", str(p.root), "run", "--plan"])
    assert r.exit_code == 0, r.output
    assert "never: never built" in r.output
    r = CliRunner().invoke(app, ["-C", str(p.root), "run", "--stale"])
    assert r.exit_code == 0, r.output
    assert "5 model(s) in" in r.output
    r = CliRunner().invoke(app, ["-C", str(p.root), "run", "--stale"])
    assert r.exit_code == 0, r.output
    assert "every model is fresh; nothing to run" in r.output
    assert "fresh" in r.output and "never" not in r.output

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=120
    )
    plan = client.get("/api/run/plan").json()
    assert all(m["state"] == "fresh" and m["state_reason"] is None for m in plan)
    assert all(m["last_run"]["sql_hash"] for m in plan)
    (p.root / "models" / "top.sql").write_text(
        "select c from {{ ref('by_c') }} order by total asc limit 1\n"
    )
    body = client.post("/api/run", json={"stale": True}).json()
    assert body["selected"] == ["top"] and body["ok"] and len(body["results"]) == 1
    edited = [m for m in body["models"] if m["name"] == "top"][0]
    assert edited["state"] == "edited"  # the plan the run was made from
    assert "+select c from" in edited["state_diff"] and "asc" in edited["state_diff"]
    assert edited["state_changes"] == [] and "sql_text" not in edited["last_run"]
    body = client.post("/api/run", json={"stale": True}).json()
    assert body["selected"] == [] and body["results"] == []
    assert json.dumps(body)  # JSON-clean
    client.close()


def test_a_snapshot_names_the_models_it_made_out_of_date(project) -> None:
    p = project
    # before any run: nothing downstream has a run, so no snapshot affects anything
    assert p.tables.describe("src").snapshot_list[0]["affects"] == []
    runner.run(p)
    time.sleep(0.01)
    p.engine.execute("insert into querysolo.main.src select 1000, 'c9', 9.0")
    snapshots = p.tables.describe("src").snapshot_list
    # the new snapshot made every model downstream out of date, in dependency order; the
    # one before it (the create) predates every run and affects nothing
    assert snapshots[0]["affects"] == ["stg_orders", "total", "by_c", "top"]
    assert snapshots[1]["affects"] == []
    # a table nothing reads: its snapshot affects nothing
    p.engine.execute("insert into querysolo.main.other select 99")
    assert p.tables.describe("other").snapshot_list[0]["affects"] == ["from_other"]
    # after a stale run every snapshot's list is empty again
    runner.run(p, stale=True)
    assert all(s["affects"] == [] for s in p.tables.describe("src").snapshot_list)
    assert p.tables.describe("other").snapshot_list[0]["affects"] == []
    # the route carries it
    import httpx

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    time.sleep(0.01)
    p.engine.execute("delete from querysolo.main.src where id = 1000")
    body = client.get("/api/tables/src").json()
    assert body["snapshot_list"][0]["affects"] == ["stg_orders", "total", "by_c", "top"]
    client.close()
