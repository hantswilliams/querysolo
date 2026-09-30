# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 5 gate, the accuracy half (brief §4, architecture §4.5): TPC-H at SF1 from DuckDB's
``tpch`` extension, imported into Iceberg tables, all 22 queries estimated then run. 80%
within 2x on time and 1.5x on bytes; no Green over 3 minutes; pruning full on every query.
Runs in the default suite (about five seconds here). The time-accuracy assertion depends on
the machine the constants were tuned on, so it is strict only with QUERYSOLO_TPCH=1, the
reference run; everywhere else the table is printed and the structural gates are asserted."""

import os

import duckdb

from querysolo import Project

STRICT_TIMING = os.environ.get("QUERYSOLO_TPCH") == "1"

TABLES = ["customer", "lineitem", "nation", "orders", "part", "partsupp", "region", "supplier"]


def test_tpch_sf1_accuracy(tmp_path) -> None:
    gen = duckdb.connect()
    gen.execute("INSTALL tpch; LOAD tpch; CALL dbgen(sf=1)")
    for table in TABLES:
        gen.execute(f"COPY {table} TO '{tmp_path}/{table}.parquet' (FORMAT parquet)")
    queries = gen.execute("SELECT query_nr, query FROM tpch_queries() ORDER BY query_nr").fetchall()
    gen.close()

    root = tmp_path / "proj"
    Project.init(root, probe_mb=64)
    rows = []
    with Project.open(root) as p:
        for table in TABLES:
            p.tables.import_file(tmp_path / f"{table}.parquet")
        for nr, sql in queries:
            result = p.query(sql, allow_red=True)
            list(result)
            run = p.history.recent(1)[0]
            rows.append(
                (
                    nr,
                    run.verdict,
                    run.pruning,
                    run.est_wall_local,
                    run.actual_wall,
                    run.est_bytes,
                    run.actual_bytes,
                )
            )

    def ratio(est, actual):
        return (est / actual) if est and actual else float("nan")

    print("\n q  verdict pruning   est_s  actual_s  ratio    est_MB  actual_MB  ratio")
    within_time = within_bytes = 0
    for nr, verdict, pruning, est_s, act_s, est_b, act_b in rows:
        rt, rb = ratio(est_s, act_s), ratio(est_b, act_b)
        within_time += 0.5 <= rt <= 2.0
        within_bytes += 1 / 1.5 <= rb <= 1.5
        print(
            f"{nr:2}  {verdict:7} {pruning:8} {est_s:7.3f} {act_s:9.3f} {rt:6.2f}  "
            f"{est_b / 1e6:8.1f} {act_b / 1e6:10.1f} {rb:6.2f}"
        )
    n = len(rows)
    print(f"within 2x on time: {within_time}/{n}; within 1.5x on bytes: {within_bytes}/{n}")
    assert all(r[2] == "full" for r in rows), [r[:3] for r in rows if r[2] != "full"]
    assert not any(r[1] == "green" and r[4] > 180 for r in rows)
    assert within_bytes / n >= 0.8
    if STRICT_TIMING:
        assert within_time / n >= 0.8
