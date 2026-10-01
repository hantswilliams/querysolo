# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The rename (build-sessions/rename-querysolo-plan.md, R3 to R5): a project made while the
product was called Lakelet opens under QuerySolo with nothing lost. Its folder and settings
file are renamed in place, once, with its dbt macros, `.gitignore` line and `AGENTS.md`; a
folder holding both layouts is refused; old tables' `lakelet.*` properties and an
interrupted `__lakelet_replace` are still read; `history.db` moves its version column."""

from __future__ import annotations

import pytest
import sqlalchemy as sa

from querysolo import Project, layout
from querysolo.history import History
from querysolo.register import SOURCE_PROPERTY, VERIFIED_PROPERTY, table_property
from querysolo.tables import interrupted_replace_of

OLD = "lake" + "let"  # the old name, spelled so the allowlist test finds it only on purpose


def _to_old_layout(root) -> None:
    """Turn a project made today back into what the old release wrote."""
    (root / ".querysolo").rename(root / f".{OLD}")
    (root / "querysolo.toml").rename(root / f"{OLD}.toml")
    for new, old in (("querysolo.sql", f"{OLD}.sql"), ("querysolo_views.sql", f"{OLD}_views.sql")):
        text = (root / "macros" / new).read_text()
        (root / "macros" / new).unlink()
        (root / "macros" / old).write_text(
            text.replace("querysolo", OLD).replace("QuerySolo", "Lakelet")
        )
    for name in (".gitignore", "AGENTS.md"):
        path = root / name
        path.write_text(path.read_text().replace("querysolo", OLD).replace("QuerySolo", "Lakelet"))


@pytest.fixture
def old_project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=0)
    with Project.open(root) as p:
        p.engine.execute("create table querysolo.main.orders as select range as id from range(40)")
        p.query("select count(*) from orders").to_arrow()  # read to the end, so it is recorded
    _to_old_layout(root)
    return root


def test_an_old_project_opens_renamed_in_place_with_nothing_lost(old_project) -> None:
    root = old_project
    with Project.open(root) as p:
        assert p.engine.execute("select count(*) from orders").fetchone()[0] == 40
        assert p.history.recent(), "the query record came across"
    assert (root / "querysolo.toml").is_file() and not (root / f"{OLD}.toml").exists()
    assert (root / ".querysolo" / "catalog.db").is_file() and not (root / f".{OLD}").exists()
    assert sorted(f.name for f in (root / "macros").iterdir()) == [
        "querysolo.sql",
        "querysolo_views.sql",
    ]
    assert "querysolo__columns_of_relation" in (root / "macros" / "querysolo.sql").read_text()
    assert ".querysolo/" in (root / ".gitignore").read_text().splitlines()
    for name in ("AGENTS.md", ".gitignore", "macros/querysolo.sql", "macros/querysolo_views.sql"):
        assert OLD not in (root / name).read_text().lower(), name


def test_the_migration_runs_once_and_a_second_open_changes_nothing(old_project) -> None:
    assert layout.migrate(old_project) is True
    before = sorted(p.name for p in old_project.iterdir())
    assert layout.migrate(old_project) is False
    assert sorted(p.name for p in old_project.iterdir()) == before


def test_a_folder_with_both_layouts_is_refused_and_nothing_moves(old_project) -> None:
    (old_project / "querysolo.toml").write_text("")
    with pytest.raises(layout.LayoutConflict, match=f"both {OLD}.toml and querysolo.toml"):
        Project.open(old_project)
    assert (old_project / f".{OLD}").is_dir() and (old_project / f"{OLD}.toml").is_file()


def test_old_table_properties_are_still_read_and_the_new_name_wins() -> None:
    old = {f"{OLD}.source-prefix": "s3://old/", f"{OLD}.verified-at": "2026-09-01T00:00:00Z"}
    assert table_property(old, SOURCE_PROPERTY) == "s3://old/"
    assert table_property(old, VERIFIED_PROPERTY) == "2026-09-01T00:00:00Z"
    assert table_property({**old, SOURCE_PROPERTY: "s3://new/"}, SOURCE_PROPERTY) == "s3://new/"
    assert table_property({}, SOURCE_PROPERTY) is None


def test_an_interrupted_replace_under_the_old_suffix_is_still_recognised() -> None:
    assert interrupted_replace_of(f"orders__{OLD}_replace") == "orders"
    assert interrupted_replace_of("orders__querysolo_replace") == "orders"
    assert interrupted_replace_of("orders") is None


def test_the_history_version_column_is_renamed_by_migration_three(tmp_path) -> None:
    db = tmp_path / "history.db"
    History(db).close()
    engine = sa.create_engine(f"sqlite:///{db}")
    with engine.begin() as c:
        c.exec_driver_sql(f"alter table runs rename column querysolo_version to {OLD}_version")
        c.exec_driver_sql(
            f"insert into runs (ts, {OLD}_version, duckdb_version, fingerprint, sql_hash, "
            "sql_text, "
            "tables, operator_counts, machine_hash, machine, ran, ran_where, retries) values "
            "('2026-09-01 00:00:00', '0.1.0', '1.5.5', 'f', 'h', 'select 1', '[]', '{}', "
            "'m', '{}', 1, 'local', 0)"
        )
        c.exec_driver_sql("update meta set value = '2' where key = 'schema_version'")
    engine.dispose()
    h = History(db)
    try:
        cols = [
            r[1]
            for r in sa.create_engine(f"sqlite:///{db}")
            .connect()
            .exec_driver_sql("pragma table_info(runs)")
        ]
        assert "querysolo_version" in cols and f"{OLD}_version" not in cols
        assert h.recent()[0].querysolo_version == "0.1.0"
    finally:
        h.close()
