# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T3: the gauge never says Green about a scan it could not attribute. A file
read by function, a native or temp table, or anything else outside the catalog makes the
estimate "not estimated" — the fourth verdict, ``none`` — with the scan named; the statement
still runs; history records it; the calibration export leaves it out; ``querysolo run`` builds
such a model and says so."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.gauge import export


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root, serve=True)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 5) AS customer, "
        "(range * 1.5)::DOUBLE AS amt FROM range(1000)"
    )
    p.engine.execute(
        f"COPY (SELECT range AS id, range * 2 AS v FROM range(50)) "
        f"TO '{tmp_path}/outside.parquet' (FORMAT parquet)"
    )
    yield p
    p.close()


def test_a_file_read_outside_the_catalog_is_not_estimated_and_never_green(
    project, tmp_path
) -> None:
    est = project.estimate(f"select * from read_parquet('{tmp_path}/outside.parquet')")
    assert est.verdict == "none"
    assert est.words == "Not estimated"
    assert est.reason == "1 scan outside the catalog: read_parquet"
    assert est.line.startswith("○ Not estimated · ")
    assert est.tables == []


def test_a_catalog_table_joined_to_an_outside_file_is_not_estimated_either(
    project, tmp_path
) -> None:
    est = project.estimate(
        f"select o.id from orders o join read_parquet('{tmp_path}/outside.parquet') y "
        "on o.id = y.id"
    )
    assert est.verdict == "none" and "read_parquet" in est.reason
    assert [t["name"] for t in est.tables] == ["orders"]  # what was attributed is still named


def test_a_temp_table_is_outside_the_catalog_too(project) -> None:
    project.engine.execute("create temp table scratch as select 1 as a")
    est = project.estimate("select * from scratch")
    assert est.verdict == "none" and "scratch" in est.reason


def test_a_plain_catalog_query_is_unchanged(project) -> None:
    est = project.estimate("select customer, sum(amt) from orders group by 1")
    assert est.verdict == "green" and est.reason.startswith("scans ")


def test_the_statement_still_runs_history_records_none_and_the_export_leaves_it_out(
    project, tmp_path
) -> None:
    # (count(*) alone is answered from the footer — a COLUMN_DATA_SCAN, honestly Green — so
    # the statement reads a column.)
    result = project.query(f"select sum(v) as s from read_parquet('{tmp_path}/outside.parquet')")
    rows = list(result)
    assert rows and rows[0].num_rows == 1
    run = project.history.recent()[0]
    assert run.verdict == "none" and run.ran
    list(project.query("select sum(amt) from orders"))
    lines = list(export.export_lines(project.history.all_runs()))
    assert len(lines) == 1 and json.loads(lines[0])["verdict"] == "green"


def test_the_cli_prints_the_hollow_dot_and_the_headers_carry_the_verdict(project, tmp_path) -> None:
    import httpx

    r = CliRunner().invoke(
        app,
        [
            "-C",
            str(project.root),
            "estimate",
            f"select * from read_parquet('{tmp_path}/outside.parquet')",
        ],
    )
    assert r.exit_code == 0, r.output
    assert "○ Not estimated · 1 scan outside the catalog: read_parquet" in r.output
    client = httpx.Client(
        base_url=project.catalog_url, headers={"Authorization": f"Bearer {project.token}"}
    )
    est = client.post(
        "/api/estimate", json={"sql": f"select * from read_parquet('{tmp_path}/outside.parquet')"}
    ).json()
    assert est["verdict"] == "none" and est["words"] == "Not estimated"
    client.close()


def test_querysolo_run_builds_a_model_it_could_not_estimate_and_says_so(project, tmp_path) -> None:
    pytest.importorskip("dbt")
    from querysolo.dbt import runner

    (project.root / "models" / "outside.sql").write_text(
        f"select id, v from read_parquet('{tmp_path}/outside.parquet')\n"
    )
    planned = runner.plan(project)
    m = next(m for m in planned if m.name == "outside")
    assert m.verdict == "none" and m.error is None
    assert "read_parquet" in (m.reason or "")
    report = runner.run(project)
    assert report.ok and {r.name for r in report.results} == {"outside"}
    r = CliRunner().invoke(app, ["-C", str(project.root), "run", "--plan"])
    assert r.exit_code == 0, r.output
    assert "none" in r.output
