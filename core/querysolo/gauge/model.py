# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The gauge's model (architecture §4.2, brief D8, D29): bytes scanned after pruning, peak
memory from a plan heuristic, wall time from measured throughput, and the burst half by
arithmetic over the worker ladder. Constants are v0 and calibrated on TPC-H SF1; the
correction factors of session 10 refine them per machine."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from querysolo.gauge import inputs

# Worker ladder from the pricing page: name, vCPU, memory in GB, list price per hour.
LADDER = [("S", 4, 16, 0.23), ("M", 8, 32, 0.46), ("L", 16, 64, 0.92), ("XL", 16, 120, 1.17)]
COLD_START_SECONDS = 45.0
WORKER_READ_BYTES_PER_SECOND = 200e6
MARGIN = 1.15
MEMORY_HEADROOM = 1.5

DEFAULT_THROUGHPUT_MBPS = 1500.0  # an NVMe laptop, until the probe has run
FIXED_OVERHEAD_SECONDS = 0.01
ROW_ESTIMATE_CAP = 4.0  # a node's rows are capped at this multiple of the largest scan
BUFFER_ALLOWANCE_BYTES = 128 * 2**20
IN_MEMORY_EXPANSION = 2.5  # Parquet compressed bytes to in-memory row width
MIN_ROW_WIDTH = 8

# CPU nanoseconds per input row per operator class, single core.
COST_NS = {
    "SCAN": 8.0,
    "FILTER": 2.0,
    "PROJECTION": 1.0,
    "HASH_JOIN_PROBE": 15.0,
    "HASH_JOIN_BUILD": 25.0,
    "HASH_GROUP_BY": 20.0,
    "PERFECT_HASH_GROUP_BY": 8.0,
    "UNGROUPED_AGGREGATE": 4.0,
    "ORDER_BY": 30.0,
    "TOP_N": 8.0,
    "WINDOW": 30.0,
    "OTHER": 3.0,
}
THREAD_EFFICIENCY = 0.7


@dataclass
class Thresholds:
    green_max_seconds: float = 60
    yellow_max_seconds: float = 600
    green_max_memory_fraction: float = 0.6


@dataclass
class Estimate:
    verdict: str
    words: str
    bytes_scanned: int
    rows_scanned: int
    files_scanned: int
    peak_memory: int
    wall_local: float
    io_seconds: float
    cpu_seconds: float
    spill_bytes: int
    reason: str
    fingerprint: str
    pruning: str
    tables: list[dict[str, Any]]
    remote: bool
    bandwidth_mbps: float | None
    throughput_mbps: float
    worker: str
    wall_burst: float
    cost_burst: float
    cap: float
    plan: list[dict[str, Any]] = field(default_factory=list)

    @property
    def line(self) -> str:
        """The gauge line: the dot, the site's words, the sentence (brief D28)."""
        from querysolo.gauge import verdict

        return verdict.line(self.verdict, self.reason)


def round_cap(cost: float) -> float:
    """PRD F0.5.3: estimated cost times two, to the next $0.10 below $1 and the next $1 above."""
    doubled = cost * 2
    if doubled < 1:
        return math.ceil(doubled * 10 - 1e-9) / 10
    return float(math.ceil(doubled - 1e-9))


def burst(peak_memory: int, bytes_scanned: int, cpu_seconds: float, local_threads: int) -> tuple:
    rung = next((r for r in LADDER if r[2] * 1e9 >= peak_memory * MEMORY_HEADROOM), LADDER[-1])
    name, vcpu, _, price = rung
    cpu = cpu_seconds * max(local_threads, 1) / vcpu
    wall = COLD_START_SECONDS + bytes_scanned / WORKER_READ_BYTES_PER_SECOND + cpu
    cost = price * MARGIN * wall / 3600
    return name, wall, cost, round_cap(cost)


def _width(
    node: dict[str, Any], scans: dict[int, dict[str, Any]], widths: dict[int, float]
) -> float:
    """In-memory row width of a node's output, from its scans upward."""
    node_id = id(node)
    if node_id in widths:
        return widths[node_id]
    if node_id in scans:
        width = max(scans[node_id]["bytes_per_row"] * IN_MEMORY_EXPANSION, MIN_ROW_WIDTH)
    else:
        children = [_width(c, scans, widths) for c in node.get("children", [])]
        width = (
            sum(children)
            if node.get("name") in ("HASH_JOIN", "NESTED_LOOP_JOIN", "CROSS_PRODUCT")
            else (children[0] if children else MIN_ROW_WIDTH)
        )
    widths[node_id] = width
    return width


def _rows(
    node: dict[str, Any], scans: dict[int, dict[str, Any]], cap: float = float("inf")
) -> float:
    """A node's rows: the pruned count for a scan, DuckDB's estimate otherwise, capped
    because DuckDB's join estimates can run away by orders of magnitude."""
    if id(node) in scans:
        return scans[id(node)]["rows"]
    return min(float(node.get("extra_info", {}).get("Estimated Cardinality", 0) or 0), cap)


def estimate_plan(
    plan: list[dict[str, Any]],
    scan_info: list[dict[str, Any]],
    machine: dict[str, Any],
    throughput_mbps: float | None,
    bandwidth_mbps: float | None,
    thresholds: Thresholds,
) -> dict[str, Any]:
    """The three numbers, the spill, and the verdict, from the plan and the pruned scans."""
    scans: dict[int, dict[str, Any]] = {}
    scan_nodes = [n for n in inputs.walk(plan) if n.get("name") in inputs.SCAN_NODES]
    for node, info in zip(scan_nodes, scan_info, strict=False):
        scans[id(node)] = info

    widths: dict[int, float] = {}
    cap = ROW_ESTIMATE_CAP * max((float(s["rows"]) for s in scan_info), default=float("inf"))
    peak = 0.0
    cpu_ns = 0.0
    for node in inputs.walk(plan):
        name = node.get("name", "OTHER")
        children = node.get("children", [])
        rows_out = _rows(node, scans, cap)
        rows_in = sum(_rows(c, scans, cap) for c in children) if children else rows_out
        if name in inputs.SCAN_NODES:
            cpu_ns += COST_NS["SCAN"] * rows_out
        elif name == "HASH_JOIN" and len(children) == 2:
            probe, build = children
            cpu_ns += COST_NS["HASH_JOIN_PROBE"] * _rows(probe, scans, cap)
            cpu_ns += COST_NS["HASH_JOIN_BUILD"] * _rows(build, scans, cap)
            peak = max(peak, _rows(build, scans, cap) * _width(build, scans, widths) * 1.5)
        elif name in ("HASH_GROUP_BY", "PERFECT_HASH_GROUP_BY"):
            cpu_ns += COST_NS[name] * rows_in
            peak = max(peak, rows_out * _width(node, scans, widths) * 1.5)
        elif name in ("ORDER_BY", "WINDOW"):
            cpu_ns += COST_NS[name] * rows_in
            peak = max(peak, rows_in * _width(node, scans, widths))
        else:
            cpu_ns += COST_NS.get(name, COST_NS["OTHER"]) * rows_in
    peak = int(peak + BUFFER_ALLOWANCE_BYTES)

    bytes_scanned = sum(int(s["bytes"]) for s in scan_info)
    rows_scanned = sum(int(s["rows"]) for s in scan_info)
    files_scanned = sum(int(s["files"]) for s in scan_info)
    remote = any(s.get("locality") == "remote" for s in scan_info)
    local_throughput = throughput_mbps or DEFAULT_THROUGHPUT_MBPS
    effective_mbps = (bandwidth_mbps / 8) if (remote and bandwidth_mbps) else local_throughput
    io_seconds = bytes_scanned / (effective_mbps * 1e6)
    threads = max(1, int(machine.get("threads") or machine.get("cores") or 1))
    cpu_seconds = cpu_ns / 1e9 / (threads * THREAD_EFFICIENCY)
    limit = machine.get("memory_limit") or machine.get("ram") or peak
    spill = max(0, peak - limit)
    spill_seconds = 2 * spill / (local_throughput * 1e6)
    wall = FIXED_OVERHEAD_SECONDS + max(io_seconds, cpu_seconds) + spill_seconds

    free_room = (machine.get("ram") or 0) + (machine.get("free_disk") or 0)
    unattributed = [s["unattributed"] for s in scan_info if s.get("unattributed")]
    if unattributed:
        verdict = "none"  # a scan the gauge knows nothing about: never Green (T3)
    elif wall >= thresholds.yellow_max_seconds or peak > free_room:
        verdict = "red"
    elif (
        remote
        and bandwidth_mbps
        and bytes_scanned > bandwidth_mbps / 8 * 1e6 * thresholds.yellow_max_seconds
    ):
        verdict = "red"
    elif spill or wall >= thresholds.green_max_seconds:
        verdict = "yellow"
    elif peak < thresholds.green_max_memory_fraction * limit:
        verdict = "green"
    else:
        verdict = "yellow"
    worker, wall_burst, cost_burst, cap = burst(peak, bytes_scanned, cpu_seconds, threads)
    return {
        "verdict": verdict,
        "bytes_scanned": bytes_scanned,
        "rows_scanned": rows_scanned,
        "files_scanned": files_scanned,
        "peak_memory": peak,
        "wall_local": wall,
        "io_seconds": io_seconds,
        "cpu_seconds": cpu_seconds,
        "spill_bytes": spill,
        "remote": remote,
        "throughput_mbps": local_throughput,
        "worker": worker,
        "wall_burst": wall_burst,
        "cost_burst": cost_burst,
        "cap": cap,
        "memory_limit": limit,
        "unattributed": unattributed,
    }
