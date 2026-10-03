# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Real-data brief R5 and R6, step 5: `querysolo run` builds the dbt DAG through the gauge
and the catalog; a `view` model is an Iceberg view in QuerySolo's catalog that a second
process, the API and the engine all read; a replaced view gets a version, a removed model's
view goes; the plugin gives a bare `dbt run` the catalog's views; `--burst auto` refuses;
a Red model refuses the run until `--run-anyway`; every model is in history."""

import json
import os
from pathlib import Path

import httpx
import pytest
import yaml
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.dbt import runner
from querysolo.views import BadView, NoSuchView

pytest.importorskip("dbt.cli.main")

runner_cli = CliRunner()


def _models(root: Path) -> None:
    (root / "models" / "stg_orders.sql").write_text("select id, c, amt from src where amt > 0\n")
    (root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select c, sum(amt) as total from {{ ref('stg_orders') }} group by 1\n"
    )
    (root / "models" / "top.sql").write_text(
        "select c from {{ ref('by_c') }} order by total desc limit 1\n"
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
    yield p
    p.close()


def test_views_in_the_catalog(project) -> None:
    p = project
    v = p.views.put("by_c_view", "select c, count(*) as n from src group by 1")
    assert v.version_id == 1 and [f.name for f in v.schema.fields] == ["c", "n"]
    assert v.schema.fields[0].field_id == 1, "fresh field ids, not pyiceberg's -1"
    assert v.metadata_location.endswith(".view.metadata.json")
    assert p.engine.execute("select sum(n) from by_c_view").fetchone()[0] == 300
    over = p.views.put("over", "select n * 2 as m from by_c_view")
    assert over.version_id == 1
    assert p.engine.execute("select sum(m) from over").fetchone()[0] == 600
    # the same SQL again is not a new version; a change is
    assert p.views.put("by_c_view", "select c, count(*) as n from src group by 1").version_id == 1
    changed = p.views.put("by_c_view", "select c, count(*) * 10 as n from src group by 1")
    assert changed.version_id == 2 and changed.versions == 2
    assert p.engine.execute("select sum(m) from over").fetchone()[0] == 6000
    # the gauge sees through the view to the table it reads
    est = p.estimate("select * from over")
    assert [t["name"] for t in est.tables] == ["src"] and est.verdict == "green"
    # refusals
    with pytest.raises(BadView, match="nope"):
        p.views.put("bad", "select * from nope")
    with pytest.raises(BadView, match="is a table"):
        p.views.put("src", "select 1")
    # listed beside the tables, as a view
    listed = {t.name: t for t in p.tables.list()}
    assert (
        listed["over"].kind == "view"
        and listed["over"].view_sql == "select n * 2 as m from by_c_view"
    )
    assert listed["src"].kind == "table"
    assert "`over` (view:" in (p.root / "AGENTS.md").read_text()
    # a second process reads the views through the catalog
    root = p.root
    with Project.open(root) as q:
        assert q.engine.execute("select sum(m) from over").fetchone()[0] == 6000
        assert [v.name for v in q.views.list()] == ["by_c_view", "over"]
    # the REST routes, as Spark would use them
    c = httpx.Client(base_url=p.catalog_url)
    assert [
        i["name"] for i in c.get("/v1/querysolo/namespaces/main/views").json()["identifiers"]
    ] == [
        "by_c_view",
        "over",
    ]
    md = c.get("/v1/querysolo/namespaces/main/views/over").json()["metadata"]
    assert md["format-version"] == 1 and md["current-version-id"] == 1
    assert md["versions"][0]["representations"] == [
        {"type": "sql", "sql": "select n * 2 as m from by_c_view", "dialect": "duckdb"}
    ]
    created = c.post(
        "/v1/querysolo/namespaces/main/views",
        json={
            "name": "theirs",
            "schema": {
                "type": "struct",
                "schema-id": 0,
                "fields": [{"id": 1, "name": "d", "required": False, "type": "long"}],
            },
            "view-version": {
                "version-id": 1,
                "schema-id": 0,
                "summary": {"engine-name": "spark"},
                "representations": [{"type": "sql", "sql": "select 1 as d", "dialect": "spark"}],
                "default-namespace": ["main"],
            },
            "properties": {},
        },
    )
    assert created.status_code == 200
    replaced = c.post(
        "/v1/querysolo/namespaces/main/views/theirs",
        json={
            "updates": [
                {
                    "action": "add-view-version",
                    "view-version": {
                        "version-id": -1,
                        "schema-id": -1,
                        "summary": {},
                        "representations": [
                            {"type": "sql", "sql": "select 2 as d", "dialect": "spark"}
                        ],
                        "default-namespace": ["main"],
                    },
                },
                {"action": "set-current-view-version", "view-version-id": -1},
            ]
        },
    )
    assert replaced.json()["metadata"]["current-version-id"] == 2
    assert c.delete("/v1/querysolo/namespaces/main/views/theirs").status_code == 204
    assert c.get("/v1/querysolo/namespaces/main/views/theirs").status_code == 404
    p.views.drop("over")
    with pytest.raises(NoSuchView):
        p.views.get("over")
    assert "over" not in p.engine.views


def test_querysolo_run_builds_the_dag_and_records_views(project) -> None:
    p = project
    report = runner.run(p)
    assert [m.name for m in report.models] == ["stg_orders", "by_c", "top"], "dependency order"
    assert [m.verdict for m in report.models] == ["green", "green", "green"]
    assert [m.materialized for m in report.models] == ["view", "table", "view"]
    assert all(r.status == "success" for r in report.results) and report.ok
    assert report.views_recorded == ["stg_orders", "top"]
    assert p.tables.describe("by_c").rows == 3
    assert p.engine.execute("select * from top").fetchone() == ("c2",)
    # F1: dbt's own connection leaves the extension's empty data/ in the cwd; the runner removes it
    assert not (Path.cwd() / "data").exists() and not (p.root / "data").exists()
    top = p.views.get("top")
    assert top.sql == 'select c from "main"."by_c" order by total desc limit 1'
    assert top.properties == {"querysolo.dbt-model": "model.proj.top"}
    # history has a run per model with the estimate and dbt's actual
    runs = {r.sql_text: r for r in p.history.recent(10)}
    assert any("sum(amt)" in sql and r.actual_wall for sql, r in runs.items())
    # the DAG's lines
    lines = runner.dag_lines(report.models)
    assert lines[0].startswith("  stg_orders  view   green")
    # a second process, the API and the engine all read the view
    with Project.open(p.root) as q:
        assert q.engine.execute("select * from top").fetchone() == ("c2",)
    client = httpx.Client(base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"})
    response = client.post("/api/query", json={"sql": "select * from top"})
    assert response.status_code == 200 and response.headers["x-querysolo-verdict"] == "green"
    described = client.get("/api/tables/top").json()
    assert described["kind"] == "view" and described["snapshots"] == 1
    assert described["view_sql"] == top.sql and described["snapshot_list"] == []
    assert client.get("/api/tables/top/sample?n=5").json() == [{"c": "c2"}], "sample reads a view"
    kinds = {t["name"]: t["kind"] for t in client.get("/api/tables").json()}
    assert kinds == {"by_c": "table", "src": "table", "stg_orders": "view", "top": "view"}
    # a changed view model is a new version; a removed one goes; --select prunes nothing
    (p.root / "models" / "top.sql").write_text(
        "select c from {{ ref('by_c') }} order by total asc limit 1\n"
    )
    runner.run(p, select=["top"])
    assert p.views.get("top").version_id == 2
    assert p.engine.execute("select * from top").fetchone() == ("c0",)
    assert [v.name for v in p.views.list()] == ["stg_orders", "top"]
    (p.root / "models" / "top.sql").unlink()
    report = runner.run(p)
    assert report.views_dropped == ["top"] and [v.name for v in p.views.list()] == ["stg_orders"]
    assert "top" not in p.engine.views


def test_burst_auto_refuses_and_red_refuses_until_run_anyway(project) -> None:
    p = project
    with pytest.raises(runner.NoBurstYet, match="session 8"):
        runner.run(p, burst="auto")
    toml = p.root / "querysolo.toml"
    toml.write_text(
        toml.read_text()
        .replace("green_max_seconds = 60", "green_max_seconds = 0.0000001")
        .replace("yellow_max_seconds = 600", "yellow_max_seconds = 0.0000002")
    )
    root = p.root
    p.close()
    with Project.open(root) as q:
        with pytest.raises(runner.RedRefusedRun, match="need more machine"):
            runner.run(q)
        assert [v.name for v in q.views.list()] == []
        report = runner.run(q, run_anyway=True)
        assert report.ok and [m.verdict for m in report.models] == ["red", "red", "red"]


def test_a_bare_dbt_run_reads_catalog_views_and_warns_about_its_own(project) -> None:
    """The plugin gives every dbt connection the catalog's views, so a model may read a
    view that is not a dbt model. A bare `dbt run` builds a `view` model for its session
    only and says so, one line per view; under `querysolo run` the line is not printed,
    because the views are recorded afterwards (the docs' "build with querysolo run")."""
    import os

    from tests.test_step2_dbt_spike import dbt_main

    p = project
    p.views.put("orders_v", "select id, amt from src where id < 10")
    (p.root / "models" / "from_v.sql").write_text(
        "{{ config(materialized='table') }}\nselect count(*) as n from orders_v\n"
    )
    (p.root / "models" / "bare_v.sql").write_text("select id from src where id > 290\n")
    (p.root / "profiles.yml").write_text(runner.profiles_yml(p.catalog_url))
    os.environ.pop("QUERYSOLO_RUN", None)
    result = dbt_main.dbtRunner().invoke(
        [
            "run",
            "--select",
            "from_v",
            "bare_v",
            "--project-dir",
            str(p.root),
            "--profiles-dir",
            str(p.root),
            "--log-path",
            str(p.root / "bare-logs"),
            "--no-use-colors",
            "--quiet",
        ]
    )
    assert result.success, result.exception
    assert p.engine.execute("select n from from_v").fetchone()[0] == 10
    bare_log = (p.root / "bare-logs" / "dbt.log").read_text()
    assert "view bare_v is built for this dbt session only" in bare_log
    assert "run `querysolo run` to record it" in bare_log
    assert "bare_v" not in [v.name for v in p.views.list()], "a bare dbt run records nothing"

    runner.run(p, select=["bare_v"])
    assert "bare_v" in [v.name for v in p.views.list()]
    querysolo_log = (p.root / ".querysolo" / "dbt" / "logs" / "dbt.log").read_text()
    assert "built for this dbt session only" not in querysolo_log


def test_dbt_is_told_not_to_send_usage_statistics(project) -> None:
    """Versions brief G11. dbt sends anonymous usage statistics to its own collector by
    default, and `querysolo run` is the one verb that invokes dbt, so QuerySolo turns it off
    through dbt's own switch. Asserted on the effect rather than the environment variable:
    after a plan, dbt's flag is false and its tracker is inert."""
    import dbt.tracking
    from dbt.flags import get_flags

    runner.plan(project)
    assert get_flags().SEND_ANONYMOUS_USAGE_STATS is False
    assert dbt.tracking.active_user is not None and dbt.tracking.active_user.do_not_track


def test_the_profile_querysolo_writes_stops_a_dbt_run_by_hand_phoning_home(project) -> None:
    """G11, the other path: `querysolo run` sets `DO_NOT_TRACK` for its own invocations, but a
    user following /docs/dbt runs `dbt` themselves through the profile QuerySolo wrote. Asserted
    on the effect: dbt invoked with that profile, and without the environment variable, comes
    out with its flag false."""
    import dbt.tracking
    from dbt.cli.main import dbtRunner
    from dbt.flags import get_flags

    profiles_dir = runner.write_profile(project).parent
    (project.root / "models" / "m.sql").write_text("select 1 as id\n", encoding="utf-8")
    before = os.environ.pop("DO_NOT_TRACK", None)
    try:
        dbtRunner().invoke(
            [
                "parse",
                "--project-dir",
                str(project.root),
                "--profiles-dir",
                str(profiles_dir),
                "--target-path",
                str(profiles_dir / "target"),
                "--quiet",
            ]
        )
        assert get_flags().SEND_ANONYMOUS_USAGE_STATS is False
        assert dbt.tracking.active_user is not None and dbt.tracking.active_user.do_not_track
    finally:
        os.environ["DO_NOT_TRACK"] = before or "1"
        dbt.tracking.do_not_track()


def test_the_cli_and_the_routes(project) -> None:
    p = project
    root = str(p.root)
    p.close()
    plan = runner_cli.invoke(app, ["-C", root, "run", "--plan"])
    assert plan.exit_code == 0, plan.output
    assert "stg_orders" in plan.output and "green" in plan.output
    # a selection compiles only that model, and dbt would echo its compiled SQL first:
    # stdout is the DAG alone, so `querysolo run --plan | …` sees nothing else
    one = runner_cli.invoke(app, ["-C", root, "run", "by_c", "--plan"])
    assert one.exit_code == 0, one.output
    assert not one.output.lstrip().lower().startswith("select"), one.output
    assert "by_c" in one.output and "sum(" not in one.output
    ran = runner_cli.invoke(app, ["-C", root, "run"])
    assert ran.exit_code == 0, ran.output
    assert "views in the catalog: stg_orders, top" in ran.output
    assert "3 model(s) in" in ran.output
    burst = runner_cli.invoke(app, ["-C", root, "run", "--burst", "auto"])
    assert burst.exit_code == 1 and "session 8" in burst.output
    with Project.open(root, serve=True) as q:
        # A dbt compile is seconds, not milliseconds, and httpx defaults to a five-second
        # read timeout; the app's own fetch has no such cap and its button says `planning…`.
        client = httpx.Client(
            base_url=q.catalog_url, headers={"Authorization": f"Bearer {q.token}"}, timeout=60
        )
        planned = client.get("/api/run/plan").json()
        assert [m["name"] for m in planned] == ["stg_orders", "by_c", "top"]
        assert planned[0]["verdict"] == "green" and planned[0]["materialized"] == "view"
        done = client.post("/api/run", json={"select": ["by_c"]}).json()
        assert done["ok"] and [r["name"] for r in done["results"]] == ["by_c"]
        refused = client.post("/api/run", json={"burst": "auto"})
        assert refused.status_code == 400 and refused.json()["error"] == "no_burst_yet"
    # the profile querysolo run writes is a real one
    profile = (Path(root) / ".querysolo" / "dbt" / "profiles.yml").read_text()
    assert "module: querysolo.dbt.plugin" in profile
    # G11: a `dbt run` by hand through this profile does not phone home either.
    assert yaml.safe_load(profile)["config"] == {"send_anonymous_usage_stats": False}
    assert (Path(root) / ".querysolo" / "dbt" / "target" / "manifest.json").exists()
    assert json.loads((Path(root) / ".querysolo" / "dbt" / "target" / "manifest.json").read_text())[
        "nodes"
    ]


def test_the_plan_carries_tests_description_and_the_last_run(project) -> None:
    """Step 6 (the app's Models panel): a model's tests from `schema.yml`, its description,
    its file, and its last `querysolo run` from history come with the plan."""
    p = project
    (p.root / "models" / "schema.yml").write_text(
        "version: 2\n"
        "models:\n"
        "  - name: stg_orders\n"
        "    description: Orders with a positive amount.\n"
        "    columns:\n"
        "      - name: id\n"
        "        tests: [not_null, unique]\n"
        "      - name: c\n"
        "        tests:\n"
        "          - accepted_values:\n"
        "              values: ['c0', 'c1', 'c2']\n"
    )
    (p.root / "tests").mkdir(exist_ok=True)
    (p.root / "tests" / "no_negative_totals.sql").write_text(
        "select * from {{ ref('by_c') }} where total < 0\n"
    )
    planned = {m.name: m for m in runner.plan(p)}
    stg = planned["stg_orders"]
    assert stg.description == "Orders with a positive amount."
    assert stg.path == "models/stg_orders.sql"
    assert [(t.kind, t.column) for t in stg.tests] == [
        ("accepted_values", "c"),
        ("not_null", "id"),
        ("unique", "id"),
    ]
    assert [(t.kind, t.column) for t in planned["by_c"].tests] == [("singular", None)]
    assert planned["by_c"].tests[0].name == "no_negative_totals"
    assert planned["top"].tests == []
    assert all(m.last_run is None for m in planned.values()), "nothing has run yet"
    runner.run(p)
    planned = {m.name: m for m in runner.plan(p)}
    last = planned["by_c"].last_run
    assert last is not None and last.ok and last.verdict == "green" and last.seconds is not None
    assert last.ts.startswith("20") and last.error is None
    # the run is the same row the Gauge screen lists
    assert p.history.model_last_run("model.proj.by_c").sql_text == planned["by_c"].compiled_sql
    # over the API, and reset forgets it
    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    over = {m["name"]: m for m in client.get("/api/run/plan").json()}
    assert over["stg_orders"]["tests"][1] == {
        "name": "not_null_stg_orders_id",
        "kind": "not_null",
        "column": "id",
        "unique_id": over["stg_orders"]["tests"][1]["unique_id"],
    }
    assert over["by_c"]["last_run"]["ok"] is True
    assert client.get("/api/tables/top").json()["properties"] == {
        "querysolo.dbt-model": "model.proj.top"
    }
    assert client.post("/api/gauge/reset", json={}).json()["removed"] == 3
    assert all(m["last_run"] is None for m in client.get("/api/run/plan").json())
