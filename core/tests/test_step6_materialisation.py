# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 6 amendment (brief §7, September 9; decisions-for-review_090926.md, all three
accepted): dbt builds a table model through the Iceberg catalog with the materialisation
``init`` writes into ``macros/querysolo.sql``, which overrides dbt's built-in ``table`` for
the project. dbt-duckdb's own ``table`` swaps a temp table into place by renames inside one
transaction, which DuckDB-Iceberg refuses, as it refuses ``CREATE OR REPLACE`` and a
drop-then-create in one transaction (confirmed in the extension's source and on the official
build). What works: ``DELETE`` then ``INSERT`` in one transaction, keeping the table; and
drop-then-create as separate transactions."""

from pathlib import Path

import yaml

from querysolo import Project
from querysolo.project import QUERYSOLO_MACROS
from tests.test_step2_dbt_spike import dbt_main, profiles_yml


def _dbt(root: Path, verb: str) -> dict[str, str]:
    result = dbt_main.dbtRunner().invoke(
        [verb, "--project-dir", str(root), "--profiles-dir", str(root), "--no-use-colors"]
    )
    assert result.success, result.exception
    return {r.node.name: str(r.status) for r in result.result.results}


def test_init_writes_the_materialisation_and_leaves_an_existing_one_alone(tmp_path) -> None:
    root = tmp_path / "proj"
    report = Project.init(root, probe_mb=0)
    assert "macros/querysolo.sql" in report.created
    assert (root / "macros" / "querysolo.sql").read_text() == QUERYSOLO_MACROS
    assert 'materialization table, adapter="duckdb"' in QUERYSOLO_MACROS
    assert "macros/querysolo.sql" in (root / "AGENTS.md").read_text()

    other = tmp_path / "other"
    (other / "macros").mkdir(parents=True)
    (other / "macros" / "querysolo.sql").write_text("-- mine\n")
    report = Project.init(other, probe_mb=0)
    assert "macros/querysolo.sql" not in report.created
    assert (other / "macros" / "querysolo.sql").read_text() == "-- mine\n"


def test_dbt_builds_a_saved_question_and_rebuilds_it_in_place(tmp_path) -> None:
    """A saved question is ``materialized: table`` in its ``schema.yml`` (step 6); with the
    override in place, ``dbt run`` builds it through the catalog, ``dbt test`` passes its two
    checks, a second run with the same columns keeps the table's identity and history, and a
    run with a changed column list drops and recreates it."""
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    with Project.open(root) as p:
        (root / "profiles.yml").write_text(profiles_yml(p.catalog_url))
        p.engine.execute(
            "CREATE TABLE querysolo.main.src AS "
            "SELECT range AS id, 'c' || (range % 3) AS c FROM range(90)"
        )
        q = p.questions.save("Count by c", "select c, count(*) as n from src group by 1")
        entry = yaml.safe_load((root / "models/questions/schema.yml").read_text())["models"][0]
        assert entry["config"] == {"materialized": "table"}  # nothing QuerySolo-specific

        assert _dbt(root, "run") == {q.slug: "success"}  # first build: create table as
        assert p.engine.execute(f"select sum(n) from {q.slug}").fetchone()[0] == 90
        first = p.tables.describe(q.slug)
        assert first.snapshots == 1
        assert set(_dbt(root, "test").values()) == {"pass"}  # returns_rows and not_null

        p.questions.save("Count by c", "select c, count(*) * 2 as n from src group by 1")
        assert _dbt(root, "run") == {q.slug: "success"}  # same columns: rows replaced
        assert p.engine.execute(f"select sum(n) from {q.slug}").fetchone()[0] == 180
        second = p.tables.describe(q.slug)
        assert second.location == first.location  # same table, its history kept
        assert second.snapshots == 3  # a delete snapshot and an append snapshot

        p.questions.save(
            "Count by c", "select c, count(*) as n, sum(id) as total from src group by 1"
        )
        assert _dbt(root, "run") == {q.slug: "success"}  # a new column: drop and create
        assert p.engine.execute(f"select sum(total) from {q.slug}").fetchone()[0] == sum(range(90))
        third = p.tables.describe(q.slug)
        assert [c[0] for c in third.columns] == ["c", "n", "total"]
        assert third.snapshots == 1

        assert [t.name for t in p.tables.list()] == [q.slug, "src"]
