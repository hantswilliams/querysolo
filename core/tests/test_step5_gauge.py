# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 5 gate, the local half (brief §4): predicates from EXPLAIN into pyiceberg
expressions (D20), pruning through the manifest cache, the model, the verdict in the site's
words (D28), the burst half by arithmetic (D29), Red refused unless allowed, the 150 ms budget
with cached manifests, and the throughput probe at init (D36). TPC-H accuracy is its own file."""

import os
import time

import pytest
from pyiceberg.expressions import (
    And,
    EqualTo,
    GreaterThan,
    GreaterThanOrEqual,
    In,
    LessThan,
    NotEqualTo,
    NotNull,
    Or,
    StartsWith,
)

from querysolo import Project
from querysolo.gauge import predicates
from querysolo.gauge.model import LADDER, round_cap
from querysolo.gauge.verdict import human_bytes, human_seconds
from querysolo.query import RedRefused


@pytest.mark.parametrize(
    ("filters", "expected", "pruning"),
    [
        ("id>500 AND id<900", And(GreaterThan("id", 500), LessThan("id", 900)), "full"),
        ("customer='c1'", EqualTo("customer", "c1"), "full"),
        ("d>='2026-03-01'::DATE", GreaterThanOrEqual("d", "2026-03-01"), "full"),
        ("optional: customer IN ('c1', 'c2')", In("customer", ["c1", "c2"]), "full"),
        ("optional: id=5 OR id=7", Or(EqualTo("id", 5), EqualTo("id", 7)), "full"),
        ("(customer IS NOT NULL)", NotNull("customer"), "full"),
        ("flag", EqualTo("flag", True), "full"),
        (
            ["amt>1.5", "customer!='c3'"],
            And(GreaterThan("amt", 1.5), NotEqualTo("customer", "c3")),
            "full",
        ),
        ("prefix(customer, 'c')", StartsWith("customer", "c"), "full"),
        ("suffix(customer, '1')", None, "full"),  # understood, prunes nothing
        ("(o_comment !~~ '%special%requests%')", None, "full"),
        ("(NOT prefix(p_type, 'MEDIUM POLISHED'))", "not-starts-with", "full"),
        ("(\"substring\"(c_phone, 1, 2) IN ('13', '31'))", None, "full"),
        ("NOT id>5", None, "full"),
        ("id + 1 > 3", None, "none"),
        (["id>5", "id + 1 > 3"], GreaterThan("id", 5), "partial"),
        (None, None, "full"),
    ],
)
def test_filters_become_pyiceberg_expressions(filters, expected, pruning) -> None:
    t = predicates.translate(filters)
    assert t.pruning == pruning
    text = str(t.expression)
    if filters == "NOT id>5":
        assert text.startswith("Not") and "GreaterThan" in text
    elif expected == "not-starts-with":
        assert text.startswith("Not") and "StartsWith" in text
    elif expected is None:
        assert text == "AlwaysTrue()"
    else:
        assert text == str(expected)


def test_cap_rounding_and_formatting() -> None:
    assert round_cap(0.19) == 0.4
    assert round_cap(0.5) == 1.0
    assert round_cap(0.6) == 2.0
    assert [r[0] for r in LADDER] == ["S", "M", "L", "XL"]
    assert human_bytes(2.1e9) == "2.1 GB" and human_bytes(210e6) == "210.0 MB"
    assert human_seconds(4) == "~4 s" and human_seconds(150) == "~2 min"


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    report = Project.init(root, probe_mb=8)
    assert report.throughput_local_mbps and report.throughput_local_mbps > 0
    assert report.throughput_probe in ("nocache", "direct", "cached")
    p = Project.open(root)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, "
        "'c' || (range % 10) AS customer, "
        "(range * 1.5)::DOUBLE AS amt, DATE '2026-01-01' + (range % 365)::INTEGER AS d "
        "FROM range(1000000)"
    )
    yield p
    p.close()


def test_estimate_on_a_local_table(project) -> None:
    est = project.estimate("select customer, sum(amt) from orders where id > 500000 group by 1")
    assert est.verdict == "green" and est.words == "Runs here"
    assert est.line.startswith("● Runs here · scans ") and "fits in memory" in est.reason
    table_bytes = project.tables.describe("orders").bytes
    assert 0 < est.bytes_scanned <= table_bytes
    assert 0 < est.rows_scanned <= 1_000_000
    assert est.pruning == "full" and est.peak_memory > 0 and est.wall_local > 0
    assert est.worker in {r[0] for r in LADDER} and est.cap > 0 and est.wall_burst > 45
    assert len(est.fingerprint) == 64
    assert est.tables[0]["name"] == "orders" and est.tables[0]["bytes_after_pruning"] > 0
    assert est.throughput_mbps > 0 and not est.remote


def test_pruning_removes_files_the_predicate_excludes(project) -> None:
    whole = project.estimate("select id from orders")
    assert whole.files_scanned >= 2, "the fixture should have several data files"
    pruned = project.estimate("select id from orders where id > 999000")
    assert pruned.files_scanned < whole.files_scanned
    assert pruned.bytes_scanned < whole.bytes_scanned / 1.5
    assert pruned.pruning == "full"


def test_projection_shrinks_the_bytes(project) -> None:
    one = project.estimate("select id from orders")
    all_columns = project.estimate("select * from orders")
    assert one.bytes_scanned < all_columns.bytes_scanned


def test_second_estimate_is_within_the_budget(project) -> None:
    sql = "select customer, count(*) from orders where d >= '2026-06-01' group by 1"
    started = time.perf_counter()
    project.estimate(sql)
    first = time.perf_counter() - started
    started = time.perf_counter()
    project.estimate(sql)
    second = time.perf_counter() - started
    print(f"\nestimate: first {first * 1000:.0f} ms, second {second * 1000:.0f} ms")
    load, cores = os.getloadavg()[0], os.cpu_count() or 1
    if load > cores:
        pytest.skip(
            f"machine under load ({load:.0f} on {cores} cores); the budget cannot be measured"
        )
    assert second < 0.150


def test_query_overhead_beyond_duckdb_is_within_the_budget(project) -> None:
    """Brief §6: what QuerySolo adds around a statement (the estimate, the profile read, the
    history row) is under 50 ms. Measured as the difference between a full ``query()``
    consumed to exhaustion and DuckDB alone on the same statement, warm, best of three."""
    sql = "select customer, count(*) from orders where d >= '2026-06-01' group by 1"
    project.query(sql).to_arrow()  # warm: caches, history schema, the profile file

    def raw() -> float:
        started = time.perf_counter()
        project.engine.execute(sql).arrow()
        return time.perf_counter() - started

    def full() -> float:
        started = time.perf_counter()
        project.query(sql).to_arrow()
        return time.perf_counter() - started

    duckdb_alone = min(raw() for _ in range(3))
    querysolo = min(full() for _ in range(3))
    overhead = querysolo - duckdb_alone
    print(
        f"\nquery: duckdb {duckdb_alone * 1000:.0f} ms, querysolo {querysolo * 1000:.0f} ms, "
        f"overhead {overhead * 1000:.0f} ms"
    )
    load, cores = os.getloadavg()[0], os.cpu_count() or 1
    if load > cores:
        pytest.skip(
            f"machine under load ({load:.0f} on {cores} cores); the budget cannot be measured"
        )
    assert overhead < 0.050


def _lower_thresholds(project: Project, green: float, yellow: float) -> Project:
    toml = project.root / "querysolo.toml"
    text = toml.read_text().replace("green_max_seconds = 60", f"green_max_seconds = {green}")
    text = text.replace("yellow_max_seconds = 600", f"yellow_max_seconds = {yellow}")
    toml.write_text(text)
    root = project.root
    project.close()
    return Project.open(root)


def test_yellow_and_red_carry_the_burst_half(project) -> None:
    sql = "select customer, sum(amt) from orders group by 1"
    p = _lower_thresholds(project, green=0.0000001, yellow=1000)
    try:
        est = p.estimate(sql)
        assert est.verdict == "yellow" and est.words == "Runs here, slowly"
        assert "burst ~" in est.reason and "cap $" in est.reason
        list(p.query(sql))  # Yellow runs
        assert p.history.recent(1)[0].verdict == "yellow"
    finally:
        p.close()


def test_red_is_refused_unless_allowed_and_recorded_either_way(project) -> None:
    sql = "select customer, sum(amt) from orders group by 1"
    p = _lower_thresholds(project, green=0.0000001, yellow=0.0000002)
    try:
        est = p.estimate(sql)
        assert est.verdict == "red" and est.line.startswith("● Needs more machine · scans ")
        assert "burst ~" in est.reason and "cap $" in est.reason
        with pytest.raises(RedRefused) as excinfo:
            p.query(sql)
        assert excinfo.value.estimate.verdict == "red"
        refused = p.history.recent(1)[0]
        assert refused.ran is False and refused.ran_where == "refused" and refused.verdict == "red"
        assert refused.est_bytes == est.bytes_scanned and refused.reason == est.reason

        result = p.query(sql, allow_red=True)
        rows = result.to_arrow().num_rows
        assert rows == 10 and result.estimate is not None and result.estimate.verdict == "red"
        ran = p.history.recent(1)[0]
        assert ran.ran and ran.ran_where == "local" and ran.verdict == "red"
        assert ran.est_wall_burst and ran.est_cost_burst and ran.pruning == "full"
    finally:
        p.close()


def test_the_run_records_the_estimate_next_to_the_actual(project) -> None:
    sql = "select sum(amt) from orders"
    est = project.estimate(sql)
    list(project.query(sql))
    run = project.history.recent(1)[0]
    assert run.verdict == "green" and run.est_bytes == est.bytes_scanned
    assert run.est_peak_mem == est.peak_memory and run.throughput_local_mbps == est.throughput_mbps
    assert run.actual_bytes and 0.8 <= run.actual_bytes / run.est_bytes <= 1.25, (
        run.actual_bytes,
        run.est_bytes,
    )
    assert run.actual_rows_scanned == 1_000_000


def test_the_probe_bypasses_the_page_cache_and_says_how(tmp_path) -> None:
    """Decisions 1 to 3 of September 11, 2026: the figure is the disk's, not the cache's, on
    macOS and Linux; where it cannot be, it is capped and labelled; the method is recorded
    and a figure from before the change reads as cached."""
    import sys

    from querysolo.gauge import inputs
    from querysolo.project import run_probe

    probe = inputs.probe_throughput(tmp_path / "wh", 64)
    assert probe.size_bytes == 64 * 1024 * 1024 and probe.mbps > 0
    if sys.platform == "darwin":
        assert probe.method == "nocache"
    elif sys.platform.startswith("linux"):
        assert probe.method == "direct"
    else:
        assert probe.method == "cached" and probe.mbps <= inputs.CACHED_PROBE_CEILING_MBPS
    if probe.method != "cached":
        # a 64 MB read through the page cache would report tens of thousands
        assert probe.mbps < 20_000, probe
    assert not (tmp_path / "wh" / ".querysolo-probe.bin").exists(), "the file is removed"

    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    cache = inputs.load_machine_cache(root / ".querysolo" / "cache")
    assert cache["probe"] == probe.method and cache["probe_mb"] == 8
    again = run_probe(root, 16)
    cache = inputs.load_machine_cache(root / ".querysolo" / "cache")
    assert cache["throughput_local_mbps"] == again.mbps and cache["probe_mb"] == 16
    assert inputs.probe_method({}) == "none"
    assert inputs.probe_method({"throughput_local_mbps": 84914.0}) == "cached", "before the change"
