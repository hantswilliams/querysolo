# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 2's half-day spike (brief M6): dbt-duckdb against the attached catalog, one
incremental merge model, run twice. The answer goes into the brief's §7 either way."""

import pytest

from querysolo import Project

dbt_main = pytest.importorskip("dbt.cli.main")

MODEL = """{{ config(materialized='incremental', incremental_strategy='merge', unique_key='id',
              database='querysolo') }}
select id, amt, updated_at from querysolo.main.src_orders
{% if is_incremental() %}
where updated_at > (select coalesce(max(updated_at), timestamp '1970-01-01') from {{ this }})
{% endif %}
"""


def profiles_yml(catalog_url: str) -> str:
    return f"""querysolo:
  target: dev
  outputs:
    dev:
      type: duckdb
      path: ":memory:"
      schema: main
      threads: 1
      plugins:
        - module: tests.dbt_plugin
          config:
            catalog_url: "{catalog_url}"
"""


def run_dbt(root) -> None:
    result = dbt_main.dbtRunner().invoke(
        ["run", "--project-dir", str(root), "--profiles-dir", str(root), "--no-use-colors"]
    )
    assert result.success, result.exception


def test_dbt_incremental_merge_through_the_catalog(tmp_path) -> None:
    root = tmp_path / "proj"
    Project.init(root)
    (root / "models" / "orders_inc.sql").write_text(MODEL)
    with Project.open(root) as p:
        (root / "profiles.yml").write_text(profiles_yml(p.catalog_url))
        p.engine.execute(
            "CREATE TABLE querysolo.main.src_orders (id BIGINT, amt DOUBLE, updated_at TIMESTAMP)"
        )
        p.engine.execute(
            "INSERT INTO src_orders VALUES (1, 1.0, '2026-01-01'), (2, 2.0, '2026-01-01')"
        )

        run_dbt(root)
        assert p.engine.execute("select count(*) from orders_inc").fetchone()[0] == 2

        p.engine.execute("INSERT INTO src_orders VALUES (3, 3.0, '2026-02-01')")
        p.engine.execute(
            "MERGE INTO src_orders t USING (SELECT 2 AS id, 20.0 AS amt, "
            "TIMESTAMP '2026-02-01' AS updated_at) s ON t.id = s.id "
            "WHEN MATCHED THEN UPDATE SET amt = s.amt, updated_at = s.updated_at"
        )
        run_dbt(root)
        rows = p.engine.execute("select id, amt from orders_inc order by id").fetchall()
    assert rows == [(1, 1.0), (2, 20.0), (3, 3.0)], rows
    print("\ndbt-duckdb incremental merge through the attached catalog: works")
