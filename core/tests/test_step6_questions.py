# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 6 gate (brief §4, D30, D16): a saved question is a dbt model with two default checks;
``dbt parse`` accepts the generated project with a stub profile; a run goes through the
gauge, records ``last_run`` in history, and touches no file. The generated checks are also
run through dbt against the catalog to prove they are real."""

import pytest
import yaml

from querysolo import Project
from querysolo.query import RedRefused
from querysolo.questions import NoSuchQuestion
from tests.test_step2_dbt_spike import dbt_main, profiles_yml

SQL = "select customer, sum(amt) as revenue from orders group by 1 order by 2 desc"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 5) AS customer, "
        "(range * 1.5)::DOUBLE AS amt FROM range(1000)"
    )
    yield p
    p.close()


def test_save_writes_a_dbt_model_and_two_checks(project) -> None:
    q = project.questions.save("Revenue by customer", SQL)
    assert q.slug == "revenue_by_customer" and q.title == "Revenue by customer"
    assert q.path == project.root / "models/questions/revenue_by_customer.sql"
    assert q.sql == SQL and q.created is not None and q.last_run is None
    assert q.path.read_text().splitlines()[0] == "-- Revenue by customer"

    schema = yaml.safe_load((project.root / "models/questions/schema.yml").read_text())
    [entry] = schema["models"]
    assert schema["version"] == 2
    assert entry["name"] == "revenue_by_customer" and entry["description"] == "Revenue by customer"
    assert entry["config"] == {"materialized": "table"}
    assert entry["data_tests"] == ["returns_rows"]
    assert entry["columns"] == [{"name": "customer", "data_tests": ["not_null"]}]
    assert (project.root / "tests/generic/returns_rows.sql").exists()


def test_save_again_updates_in_place(project) -> None:
    first = project.questions.save("Revenue by customer", SQL)
    again = project.questions.save("Revenue by customer", SQL + " limit 3")
    assert again.created == first.created and again.sql.endswith("limit 3")
    assert len(project.questions.list()) == 1
    assert (
        len(yaml.safe_load((project.root / "models/questions/schema.yml").read_text())["models"])
        == 1
    )


def test_run_goes_through_the_gauge_records_last_run_and_touches_no_file(project) -> None:
    project.questions.save("Revenue by customer", SQL)
    sql_path = project.root / "models/questions/revenue_by_customer.sql"
    schema_path = project.root / "models/questions/schema.yml"
    before = (sql_path.stat().st_mtime_ns, schema_path.stat().st_mtime_ns)

    result = project.questions.run("revenue_by_customer")
    assert result.estimate is not None and result.estimate.verdict == "green"
    assert result.to_arrow().num_rows == 5

    after = (sql_path.stat().st_mtime_ns, schema_path.stat().st_mtime_ns)
    assert after == before, "a run must not touch the question's files"
    [q] = project.questions.list()
    assert q.last_run is not None
    run = project.history.recent(1)[0]
    assert run.sql_text == SQL and run.id == result.run_id
    with pytest.raises(NoSuchQuestion):
        project.questions.run("nope")


def test_a_red_question_is_refused_and_leaves_last_run_alone(project) -> None:
    project.questions.save("Revenue by customer", SQL)
    toml = project.root / "querysolo.toml"
    toml.write_text(
        toml.read_text()
        .replace("green_max_seconds = 60", "green_max_seconds = 0.0000001")
        .replace("yellow_max_seconds = 600", "yellow_max_seconds = 0.0000002")
    )
    root = project.root
    project.close()
    p = Project.open(root)
    try:
        with pytest.raises(RedRefused):
            p.questions.run("revenue_by_customer")
        assert p.questions.get("revenue_by_customer").last_run is None
        assert p.questions.run("revenue_by_customer", allow_red=True).to_arrow().num_rows == 5
        assert p.questions.get("revenue_by_customer").last_run is not None
    finally:
        p.close()


def test_dbt_parse_accepts_the_generated_project(project) -> None:
    project.questions.save("Revenue by customer", SQL)
    (project.root / "profiles.yml").write_text(
        "querysolo:\n  target: dev\n  outputs:\n    dev:\n"
        "      type: duckdb\n      path: ':memory:'\n"
    )
    result = dbt_main.dbtRunner().invoke(
        ["parse", "--project-dir", str(project.root), "--profiles-dir", str(project.root)]
    )
    assert result.success, result.exception
    manifest = result.result
    nodes = {n.name: n for n in manifest.nodes.values()}
    assert (
        "revenue_by_customer" in nodes
        and nodes["revenue_by_customer"].description == "Revenue by customer"
    )
    tests = sorted(n.name for n in manifest.nodes.values() if n.resource_type == "test")
    assert len(tests) == 2
    assert tests[0] == "not_null_revenue_by_customer_customer"
    assert tests[1].startswith("returns_rows_revenue_by_customer")


def test_the_generated_checks_are_real_dbt_tests_that_pass(project) -> None:
    """The two default checks run through dbt against the question's table, which ``dbt run``
    builds through the catalog with the materialisation ``init`` wrote (step 6 amendment,
    September 9; ``test_step6_materialisation.py`` covers the rebuild paths)."""
    project.questions.save("Revenue by customer", SQL)
    (project.root / "profiles.yml").write_text(profiles_yml(project.catalog_url))
    built = dbt_main.dbtRunner().invoke(
        ["run", "--project-dir", str(project.root), "--profiles-dir", str(project.root)]
    )
    assert built.success, built.exception
    result = dbt_main.dbtRunner().invoke(
        [
            "test",
            "--project-dir",
            str(project.root),
            "--profiles-dir",
            str(project.root),
            "--no-use-colors",
        ]
    )
    outcomes = {r.node.name: str(r.status) for r in result.result.results}
    assert result.success, outcomes
    assert len(outcomes) == 2 and set(outcomes.values()) == {"pass"}, outcomes
