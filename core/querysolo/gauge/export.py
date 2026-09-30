# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""`querysolo gauge export` (real-data brief R8; ship brief S11): the calibration record as
JSON lines, exactly the fields PRD F0.3.9 allows to leave the machine and nothing else.

One line per run: the fingerprint hash, the machine profile in buckets, the operator-class
counts, the estimate, the actual, the verdict and where it ran. Never the SQL, a table
name, a column name, a value, or the gauge's sentence (which names the source prefix).
This file is the contract the Day 1 sharing path will send; until then a partner sends
it by hand."""

from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Any

from querysolo.history import Run

FIELDS = (
    "fingerprint",
    "ts",
    "querysolo_version",
    "duckdb_version",
    "machine_hash",
    "machine",
    "operator_counts",
    "pruning",
    "throughput_local_mbps",
    "bandwidth_mbps",
    "est_bytes",
    "est_peak_mem",
    "est_wall_local",
    "est_wall_burst",
    "est_cost_burst",
    "verdict",
    "ran",
    "ran_where",
    "actual_rows_scanned",
    "actual_bytes",
    "actual_peak_mem",
    "actual_peak_rss",
    "actual_spill",
    "actual_wall",
    "actual_cost",
    "retries",
    "failed",
)

#: Fields of a run that never leave the machine: the statement, its hash, the tables it
#: read (names), the sentence (the source prefix), the error text (could quote a name).
NEVER = ("sql_text", "sql_hash", "tables", "reason", "error")


def _bucket(value: float | None, step: float) -> float | None:
    return None if value is None else round(value / step) * step


def machine_buckets(profile: dict[str, Any]) -> dict[str, Any]:
    """The machine as a class, not a fingerprint: RAM to the nearest 8 GB, cores and
    threads, the disk figure to the nearest 500 MB/s, the platform and architecture."""
    ram = profile.get("ram")
    limit = profile.get("memory_limit")
    return {
        "platform": profile.get("platform"),
        "arch": profile.get("machine"),
        "ram_gb": _bucket(ram / 2**30, 8) if ram else None,
        "memory_limit_gb": _bucket(limit / 2**30, 4) if limit else None,
        "cores": profile.get("cores"),
        "threads": profile.get("threads"),
        "on_battery": profile.get("on_battery"),
    }


def export_record(run: Run) -> dict[str, Any]:
    record: dict[str, Any] = {}
    for name in FIELDS:
        if name == "ts":
            record[name] = run.ts.isoformat() if run.ts else None
        elif name == "machine":
            record[name] = machine_buckets(run.machine)
        elif name == "throughput_local_mbps":
            record[name] = _bucket(run.throughput_local_mbps, 500)
        elif name == "bandwidth_mbps":
            record[name] = _bucket(run.bandwidth_mbps, 50)
        elif name == "failed":
            record[name] = run.error is not None
        else:
            record[name] = getattr(run, name)
    for name in NEVER:
        assert name not in record
    return record


def export_lines(runs: Iterable[Run]) -> Iterator[str]:
    for run in runs:
        if run.verdict == "none":
            continue  # nothing was measured: never a calibration point (T3)
        yield json.dumps(export_record(run), sort_keys=True)
