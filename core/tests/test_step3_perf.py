# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""PRD F0.1 AC: 200 MB CSV in 10 s, 2 GB CSV in 90 s with no swap. Generated fixtures, never
in git (brief D12). Opt-in with QUERYSOLO_PERF=1; run on the reference machine and recorded in
the session log."""

import os
import time

import pytest

from querysolo import Project

pytestmark = pytest.mark.skipif(os.environ.get("QUERYSOLO_PERF") != "1", reason="set QUERYSOLO_PERF=1")


@pytest.mark.parametrize(
    ("rows", "label", "budget"), [(4_500_000, "200 MB", 10.0), (45_000_000, "2 GB", 90.0)]
)
def test_csv_import_within_budget(tmp_path, rows, label, budget) -> None:
    root = tmp_path / "proj"
    Project.init(root)
    toml = root / "querysolo.toml"
    toml.write_text(toml.read_text().replace('memory_limit = "auto"', 'memory_limit = "8GB"'))
    csv = tmp_path / "big.csv"
    with Project.open(root) as p:
        started = time.perf_counter()
        p.engine.execute(
            f"COPY (SELECT range AS id, (random() * 1000)::DECIMAL(10,2) AS amt, "
            f"'customer_' || (range % 1000) AS customer, "
            f"DATE '2026-01-01' + (range % 365)::INTEGER AS d FROM range({rows})) "
            f"TO '{csv}' (HEADER)"
        )
        generated = time.perf_counter() - started
        size_mb = csv.stat().st_size / 1e6
        started = time.perf_counter()
        info = p.tables.import_file(csv, name="big")
        elapsed = time.perf_counter() - started
        profile = p.engine.last_profile() or {}
        peak = profile.get("system_peak_buffer_memory")
    print(
        f"\n{label}: {size_mb:.0f} MB, {rows:,} rows; generated in {generated:.1f}s; "
        f"imported in {elapsed:.1f}s (budget {budget:.0f}s); peak buffer memory {peak}"
    )
    assert info.rows == rows
    assert elapsed <= budget
