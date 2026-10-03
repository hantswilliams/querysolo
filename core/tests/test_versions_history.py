# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Versions step 1 gate (versions brief §4, G4, G5): a question's history is the commits that
changed its SQL or its checks, each with the diff against the version before; restore writes
an old version back and is itself a new version, never a rewrite; ``querysolo run`` records a
version of what it is about to build, and ``git.auto_commit = false`` stops that while a save
still commits. The CLI verbs and the three routes over the same functions."""

import httpx
import pytest
from typer.testing import CliRunner

from querysolo import Project, versions
from querysolo.cli import app
from querysolo.dbt import runner
from querysolo.versions import NoHistory, NoSuchModel
from tests.test_versions import log, use_gitconfig

cli = CliRunner()
SQL = "select customer, sum(amt) as revenue from orders group by 1"
WIDER = SQL + " order by 2 desc"


@pytest.fixture
def gitconfig(tmp_path, monkeypatch):
    use_gitconfig(
        monkeypatch,
        tmp_path / "gitconfig",
        "[user]\n\tname = Ada Lovelace\n\temail = ada@example.com\n",
    )


@pytest.fixture
def project(tmp_path, gitconfig):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root, serve=True)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 5) AS customer, "
        "(range * 1.5)::DOUBLE AS amt FROM range(1000)"
    )
    yield p
    p.close()


@pytest.fixture
def saved_twice(project):
    """A question saved, then changed: two versions and the init commit behind them."""
    project.questions.save("Revenue by customer", SQL)
    project.questions.save("Revenue by customer", WIDER)
    return project


# -- the list and the diff (G5) ------------------------------------------------------------


def test_two_saves_are_two_versions_with_the_diff_against_the_one_before(saved_twice) -> None:
    entries = saved_twice.versions.list("revenue_by_customer")

    assert [v.message for v in entries] == [
        "update question: Revenue by customer",
        "save question: Revenue by customer",
    ]
    assert all(v.author == "Ada Lovelace <ada@example.com>" for v in entries)
    assert all(v.sql_changed for v in entries)
    assert len(entries[0].short) == 7 and entries[0].id.startswith(entries[0].short)
    assert entries[0].when.startswith("20")

    newest = entries[0].diff
    assert "+++ after" in newest and "--- before" in newest
    assert any(line.startswith("+") and "order by 2 desc" in line for line in newest.splitlines())
    # the first save has no version before it, so its diff is the whole file arriving
    assert entries[1].diff.count("\n+") >= 3 and "-select" not in entries[1].diff


def test_the_first_version_says_the_checks_changed_and_a_sql_only_change_does_not(
    saved_twice,
) -> None:
    """G5: the app shows "checks changed" / "checks unchanged" per version."""
    first, second = saved_twice.versions.list("revenue_by_customer")[::-1]
    assert first.checks_changed, "the first save wrote the schema.yml entry"
    assert not second.checks_changed, "the second changed only the SQL"


def test_a_commit_that_touched_only_the_checks_is_in_the_list_and_marked(saved_twice) -> None:
    """G5: a change to the checks is a version of the question too, marked as such."""
    import yaml

    schema = saved_twice.root / "models" / "questions" / "schema.yml"
    data = yaml.safe_load(schema.read_text())
    data["models"][0]["columns"][0]["data_tests"].append("unique")
    schema.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    versions.commit(saved_twice.root, [schema], "update question: checks by hand")

    newest = saved_twice.versions.list("revenue_by_customer")[0]
    assert newest.message == "update question: checks by hand"
    assert newest.checks_changed and not newest.sql_changed
    assert newest.diff == "", "the model's own file did not change"


def test_a_comment_added_to_schema_yml_is_not_a_version_of_the_question(saved_twice) -> None:
    """The entry is what is compared, so reformatting the file or adding a comment beside it
    is not a version of any question in it."""
    schema = saved_twice.root / "models" / "questions" / "schema.yml"
    schema.write_text(schema.read_text() + "\n# reviewed by hand\n", encoding="utf-8")
    versions.commit(saved_twice.root, [schema], "a comment, nothing more")

    assert [v.message for v in saved_twice.versions.list("revenue_by_customer")] == [
        "update question: Revenue by customer",
        "save question: Revenue by customer",
    ]


def test_another_questions_save_is_not_a_version_of_this_one(project) -> None:
    """G5's mark is this model's `schema.yml` entry, not the file. Every question in a project
    shares `models/questions/schema.yml`, so comparing the file would put every other
    question's save into this one's history."""
    project.questions.save("Revenue by customer", SQL)
    project.questions.save("Orders by day", "select id, count(*) as n from orders group by 1")
    project.questions.save(
        "Orders by day", "select id, count(*) as n from orders group by 1 limit 5"
    )

    [only] = project.versions.list("revenue_by_customer")
    assert only.message == "save question: Revenue by customer"
    assert len(project.versions.list("orders_by_day")) == 2


def test_a_model_that_is_not_a_question_has_versions_too(project) -> None:
    """A model someone writes in an editor is the same thing here: a file with commits."""
    model = project.root / "models" / "stg.sql"
    model.write_text("select 1 as id\n", encoding="utf-8")
    versions.commit(project.root, [model], "run: stg changed")

    [entry] = project.versions.list("stg")
    assert entry.message == "run: stg changed" and entry.sql_changed and not entry.checks_changed


def test_a_file_with_no_commits_says_why_rather_than_showing_nothing(project) -> None:
    (project.root / "models" / "draft.sql").write_text("select 1\n", encoding="utf-8")
    with pytest.raises(NoHistory, match="no versions yet"):
        project.versions.list("draft")
    with pytest.raises(NoSuchModel):
        project.versions.list("nothing_of_the_sort")


# -- restore (G5) --------------------------------------------------------------------------


def test_restore_writes_the_old_sql_back_and_is_a_third_version(saved_twice) -> None:
    first = saved_twice.versions.list("revenue_by_customer")[-1]
    result = saved_twice.versions.restore("revenue_by_customer", first.id)

    assert result.id and result.id != first.id
    assert saved_twice.questions.get("revenue_by_customer").sql == SQL
    messages = [m for m, _ in log(saved_twice.root)]
    assert messages[0] == f"restore question: Revenue by customer to {versions.short(first.id)}"
    assert len(saved_twice.versions.list("revenue_by_customer")) == 3, "nothing was rewritten"


def test_restore_takes_a_prefix_and_re_derives_the_checks(saved_twice) -> None:
    first = saved_twice.versions.list("revenue_by_customer")[-1]
    saved_twice.versions.restore("revenue_by_customer", first.short)

    import yaml

    schema = yaml.safe_load((saved_twice.root / "models" / "questions" / "schema.yml").read_text())
    [entry] = schema["models"]
    assert entry["description"] == "Revenue by customer"
    assert entry["columns"] == [{"name": "customer", "data_tests": ["not_null"]}]
    assert entry["data_tests"] == ["returns_rows"]


def test_an_ambiguous_or_unknown_version_says_so(saved_twice) -> None:
    with pytest.raises(NoHistory, match="no version"):
        saved_twice.versions.restore("revenue_by_customer", "0000000")


def test_show_returns_that_versions_sql(saved_twice) -> None:
    entries = saved_twice.versions.list("revenue_by_customer")
    assert SQL in saved_twice.versions.sql("revenue_by_customer", entries[-1].id)
    assert WIDER in saved_twice.versions.sql("revenue_by_customer", entries[0].id)


# -- querysolo run records a version (G4) ----------------------------------------------------


def _model(project, sql: str) -> None:
    (project.root / "models" / "stg.sql").write_text(sql, encoding="utf-8")
    (project.root / "models" / "schema.yml").write_text(
        "version: 2\nsources:\n  - name: querysolo\n    database: querysolo\n    schema: main\n"
        "    tables: [{ name: orders }]\n",
        encoding="utf-8",
    )


def test_run_commits_the_models_it_is_about_to_build(project) -> None:
    _model(project, "select id, customer, amt from {{ source('querysolo','orders') }}\n")
    report = runner.run(project)

    assert report.commit and report.git is None
    assert [m for m, _ in log(project.root)][0] == "run: stg changed"
    assert project.versions.list("stg")[0].message == "run: stg changed"


def test_a_second_run_with_nothing_changed_records_no_version(project) -> None:
    _model(project, "select id, customer, amt from {{ source('querysolo','orders') }}\n")
    runner.run(project)
    again = runner.run(project)
    assert again.commit is None and again.git is None
    assert [m for m, _ in log(project.root)].count("run: stg changed") == 1


def test_a_run_refused_as_red_records_no_version(project) -> None:
    """G4's commit is of what dbt is about to build, so a run that dbt never gets to must
    leave no version behind: plan, then the refusal, then the commit."""
    from querysolo.config import Config, set_value

    toml = project.root / "querysolo.toml"
    for key, value in (("gauge.green_max_seconds", "0"), ("gauge.yellow_max_seconds", "0")):
        toml.write_text(set_value(toml.read_text(), key, value), encoding="utf-8")
    project.config = Config.load(toml)
    _model(project, "select id, customer, amt from {{ source('querysolo','orders') }}\n")

    with pytest.raises(runner.RedRefusedRun):
        runner.run(project)
    assert "run: stg changed" not in [m for m, _ in log(project.root)]

    ran = runner.run(project, run_anyway=True)
    assert ran.commit, "run anyway builds, so it records the version it built"


def test_auto_commit_false_stops_the_run_time_commit_and_a_save_still_commits(project) -> None:
    """G4: a developer who keeps their own git turns the run-time commit off; a save with no
    version is the one thing the product promises not to do, so saves are unaffected."""
    from querysolo.config import Config, set_value

    toml = project.root / "querysolo.toml"
    toml.write_text(set_value(toml.read_text(), "git.auto_commit", False), encoding="utf-8")
    project.config = Config.load(toml)
    _model(project, "select id, customer, amt from {{ source('querysolo','orders') }}\n")

    report = runner.run(project)
    assert report.commit is None
    assert "run: stg changed" not in [m for m, _ in log(project.root)]

    saved = project.questions.save("Revenue by customer", SQL)
    assert saved.commit, "a save is a version whatever the setting says"


def test_the_setting_is_settable_and_defaults_to_true(project) -> None:
    from querysolo.config import current_settings, parse_setting

    assert current_settings(project.config)["git.auto_commit"] is True
    assert parse_setting("git.auto_commit", "false") is False
    result = cli.invoke(app, ["-C", str(project.root), "config", "set", "git.auto_commit", "false"])
    assert result.exit_code == 0, result.output
    assert "git.auto_commit" in cli.invoke(app, ["-C", str(project.root), "config", "show"]).output


# -- the CLI and the routes ----------------------------------------------------------------


def test_the_cli_lists_and_restores(saved_twice) -> None:
    root = str(saved_twice.root)
    saved_twice.close()

    # rich fits its table to the terminal, so give the test one wide enough to read
    listed = cli.invoke(
        app, ["-C", root, "versions", "revenue_by_customer"], env={"COLUMNS": "200"}
    )
    assert listed.exit_code == 0, listed.output
    assert "update question: Revenue by customer" in listed.output
    assert "Ada Lovelace" in listed.output and "the SQL" in listed.output

    with Project.open(root) as p:
        first = p.versions.list("revenue_by_customer")[-1]
    done = cli.invoke(app, ["-C", root, "restore", "revenue_by_customer", first.short])
    assert done.exit_code == 0, done.output
    assert "restored revenue_by_customer" in done.output and "version " in done.output

    with Project.open(root) as p:
        assert p.questions.get("revenue_by_customer").sql == SQL
    missing = cli.invoke(app, ["-C", root, "versions", "nothing_of_the_sort"])
    assert missing.exit_code == 1 and "no model or question" in missing.output


def test_the_three_routes(saved_twice) -> None:
    p = saved_twice
    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    listed = client.get("/api/versions/revenue_by_customer").json()
    assert [v["message"] for v in listed] == [
        "update question: Revenue by customer",
        "save question: Revenue by customer",
    ]
    assert listed[0]["checks_changed"] is False and listed[0]["sql_changed"] is True
    assert "--- before" in listed[0]["diff"]

    first = listed[-1]
    sql = client.get(f"/api/versions/revenue_by_customer/{first['id'][:7]}").json()
    assert SQL in sql["sql"]

    restored = client.post(
        "/api/versions/revenue_by_customer/restore", json={"id": first["id"]}
    ).json()
    assert restored["commit"] and restored["git"] is None
    assert p.questions.get("revenue_by_customer").sql == SQL
    assert len(client.get("/api/versions/revenue_by_customer").json()) == 3

    gone = client.get("/api/versions/nothing_of_the_sort")
    assert gone.status_code == 404 and gone.json()["error"] == "no_such_model"
    client.close()


# -- the panel's git line (G6, step 3) -----------------------------------------------------


def test_the_git_line_names_the_branch_and_when_origin_is_not_set(saved_twice, tmp_path) -> None:
    p = saved_twice
    assert p.versions.status() == {"repository": True, "branch": "main", "origin": None}

    from dulwich.repo import Repo

    with Repo(str(p.root)) as repo:
        config = repo.get_config()
        config.set((b"remote", b"origin"), b"url", b"git@example.com:ada/proj.git")
        config.write_to_path()
    assert p.versions.status()["origin"] == "git@example.com:ada/proj.git"

    nowhere = versions.status(tmp_path / "nowhere")
    assert nowhere == {"repository": False, "branch": None, "origin": None}

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    assert client.get("/api/git").json()["branch"] == "main"
    client.close()
