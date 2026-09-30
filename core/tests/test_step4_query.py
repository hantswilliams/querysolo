# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 4 gate (brief §4): Arrow streaming with the first batch before completion, every run
recorded with the §3.4 schema including the profiler's actuals, derived bytes and the SQL
text (D7, D21), the fingerprint (D10), and the conflict retry (D23)."""

import time

import duckdb
import pyarrow as pa
import pytest

from querysolo import Project
from querysolo.engine import CatalogConflict
from querysolo.query import fingerprint, normalise, sql_hash


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root)
    p = Project.open(root)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 10) AS customer, "
        "(range * 1.5)::DOUBLE AS amt FROM range(10000)"
    )
    yield p
    p.close()


def test_query_streams_arrow_and_records_the_run(project) -> None:
    sql = "select id, amt from orders where id >= 9000 order by id"
    result = project.query(sql)
    batches = list(result)
    assert batches and all(isinstance(b, pa.RecordBatch) for b in batches)
    assert sum(b.num_rows for b in batches) == 1000
    assert batches[0].column("id")[0].as_py() == 9000

    actual = result.actual
    assert actual is not None and actual.wall > 0 and actual.rows_returned == 1000
    assert actual.peak_mem is not None and actual.peak_mem > 0
    assert actual.peak_rss is not None and actual.peak_rss > 0
    assert actual.rows_scanned is not None and actual.rows_scanned > 0
    assert actual.bytes is not None and actual.bytes > 0

    [run] = project.history.recent()
    assert run.id == result.run_id and run.sql_text == sql
    assert (
        len(run.fingerprint) == 64 and len(run.sql_hash) == 64 and run.fingerprint != run.sql_hash
    )
    assert run.tables[0]["name"] == "orders" and run.tables[0]["locality"] == "local"
    assert run.tables[0]["snapshot_id"] == project.tables.describe("orders").snapshot_id
    assert run.operator_counts.get("ICEBERG_SCAN") == 1
    assert {"ram", "cores", "memory_limit", "free_disk", "on_battery"} <= set(run.machine)
    assert run.machine_hash and run.querysolo_version and run.duckdb_version == duckdb.__version__
    assert run.ran and run.ran_where == "local" and run.retries == 0 and run.error is None
    assert run.actual_wall == actual.wall and run.actual_bytes == actual.bytes
    assert run.est_bytes and run.verdict == "green" and run.pruning == "full"  # step 5 fills these


def test_first_batch_arrives_before_completion(project) -> None:
    sql = "select i, md5(i::varchar) as h from range(20000000) t(i)"
    started = time.perf_counter()
    result = project.query(sql, batch_rows=1000)
    it = iter(result)
    first = next(it)
    first_at = time.perf_counter() - started
    rows = first.num_rows + sum(b.num_rows for b in it)
    total = time.perf_counter() - started
    assert rows == 20_000_000 and first.num_rows >= 1
    print(f"\nfirst batch after {first_at:.3f}s, all batches after {total:.2f}s")
    if total > 0.5:
        assert first_at < total * 0.3, "the first batch waited for the whole result"


def test_fingerprint_follows_data_and_ignores_text_noise(project) -> None:
    a = "SELECT id FROM orders WHERE customer = 'C1'"
    b = "  select   id\nfrom orders -- a comment\n where customer = 'C1' /* same */"
    assert normalise(a) == normalise(b) == "select id from orders where customer = 'C1'"
    assert sql_hash(a) == sql_hash(b)
    list(project.query(a))
    list(project.query(b))
    project.engine.execute("INSERT INTO orders VALUES (10000, 'c1', 1.0)")
    list(project.query(a))
    newest, same_data_b, same_data_a = project.history.recent(3)
    assert same_data_a.fingerprint == same_data_b.fingerprint
    assert same_data_a.sql_hash == same_data_b.sql_hash == newest.sql_hash
    assert newest.fingerprint != same_data_a.fingerprint
    assert fingerprint(a, [("orders", 1)]) != fingerprint(a, [("orders", 2)])


def test_a_failed_statement_is_recorded_with_its_error(project) -> None:
    with pytest.raises(duckdb.Error):
        list(project.query("select * from no_such_table"))
    [run] = project.history.recent()
    assert run.ran and "no_such_table" in run.error and run.actual_wall is not None
    assert run.tables == []


def test_a_write_statement_goes_through_query_too(project) -> None:
    result = project.query("insert into orders values (10001, 'c2', 2.0)")
    assert result.to_arrow().num_rows == 1
    assert project.tables.describe("orders").rows == 10001
    [run] = project.history.recent()
    assert run.tables[0]["name"] == "orders" and run.ran


def test_closing_early_still_records(project) -> None:
    result = project.query("select * from orders", batch_rows=100)
    next(iter(result))
    result.close()
    assert result.actual is not None and result.actual.rows_returned == 100
    [run] = project.history.recent()
    assert run.ran and run.actual_wall is not None


def _conflict(url: str = "http://127.0.0.1:1/v1/querysolo/transactions/commit") -> duckdb.Error:
    return duckdb.TransactionException(
        "TransactionContext Error: Failed to commit: Failed to commit Iceberg transaction: "
        f"Request to '{url}' returned a non-200 status code (409 Conflict)"
    )


def test_a_conflict_is_retried_then_succeeds(project, monkeypatch) -> None:
    real = project.engine.execute
    sql = "insert into orders values (20000, 'c3', 3.0)"
    failures = {"left": 2}

    def flaky(statement, parameters=None):
        if statement == sql and failures["left"]:
            failures["left"] -= 1
            raise _conflict()
        return real(statement, parameters)

    monkeypatch.setattr(project.engine, "execute", flaky)
    list(project.query(sql))
    [run] = project.history.recent()
    assert run.retries == 2 and run.error is None
    assert project.tables.describe("orders").rows == 10001


def test_a_conflict_that_never_clears_raises_catalog_conflict(project, monkeypatch) -> None:
    real = project.engine.execute
    sql = "insert into orders values (20001, 'c3', 3.0)"

    def always(statement, parameters=None):
        if statement == sql:
            raise _conflict()
        return real(statement, parameters)

    monkeypatch.setattr(project.engine, "execute", always)
    with pytest.raises(CatalogConflict):
        project.query(sql)
    [run] = project.history.recent()
    assert run.retries == 2 and "409" in run.error and run.ran


def test_question_last_run_bookkeeping(project) -> None:
    result = project.query("select 1")
    list(result)
    assert project.history.question_last_run("revenue") is None
    project.history.record_question_run("revenue", result.run_id)
    assert project.history.question_last_run("revenue") is not None


def test_timestamps_read_back_from_history_carry_utc(project) -> None:
    """SQLite drops the offset; a naive timestamp reaches a browser as local time, an hour
    out on a machine in London. Every read path puts UTC back (found 2026-09-15 on the Mac)."""
    from datetime import UTC

    result = project.query("select 1")
    list(result)
    project.history.record_question_run("revenue", result.run_id)
    project.history.record_model_run("model.demo.revenue", result.run_id)
    for ts in (
        project.history.recent()[0].ts,
        next(project.history.all_runs()).ts,
        project.history.model_last_run("model.demo.revenue").ts,
        project.history.question_last_run("revenue"),
    ):
        assert ts is not None and ts.tzinfo is UTC
        assert ts.isoformat().endswith("+00:00")
