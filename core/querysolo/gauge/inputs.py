# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Gauge inputs (brief §4.1 of the architecture, D20, D21, D36): the optimised plan, the
tables a statement reads, and the machine profile."""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import psutil

if TYPE_CHECKING:
    from querysolo.engine import Engine

#: The plan nodes that read something. Only ICEBERG_SCAN reads a catalog table; the rest
#: — a file read by function, a DuckDB native or temp table — are outside the catalog and
#: cannot be attributed to a table the gauge has statistics for (trust round T3).
SCAN_NODES = ("ICEBERG_SCAN", "TABLE_SCAN", "PARQUET_SCAN", "READ_PARQUET", "SEQ_SCAN")
CATALOG_SCAN_NODES = ("ICEBERG_SCAN",)
_UNITS = {"B": 1, "KB": 10**3, "MB": 10**6, "GB": 10**9, "TB": 10**12}
_UNITS |= {"KIB": 2**10, "MIB": 2**20, "GIB": 2**30, "TIB": 2**40}


def parse_memory(text: str) -> int | None:
    """DuckDB prints ``51.2 GiB``; config says ``8GB``. Bytes, or None for anything else."""
    match = re.fullmatch(r"\s*([\d.]+)\s*([A-Za-z]+)\s*", text or "")
    if not match:
        return None
    unit = _UNITS.get(match.group(2).upper())
    return int(float(match.group(1)) * unit) if unit else None


def plan_json(engine: Engine, sql: str) -> list[dict[str, Any]]:
    """``EXPLAIN (FORMAT JSON)``: the optimised plan, with filters and projections already
    pushed down to the scan nodes (brief D20)."""
    return json.loads(engine.execute(f"EXPLAIN (FORMAT JSON) {sql}").fetchone()[1])


def walk(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """All plan nodes in tree order."""
    out: list[dict[str, Any]] = []

    def visit(node: dict[str, Any]) -> None:
        out.append(node)
        for child in node.get("children", []):
            visit(child)

    for node in nodes:
        visit(node)
    return out


def scan_nodes(plan: list[dict[str, Any]]) -> list[dict[str, Any]]:
    scans = []
    for node in walk(plan):
        if node.get("name") in SCAN_NODES:
            extra = node.get("extra_info", {})
            projections = extra.get("Projections", [])
            if isinstance(projections, str):
                projections = [projections]
            scans.append(
                {
                    "name": node["name"],
                    "projections": list(projections),
                    "filters": extra.get("Filters"),
                    "estimated_cardinality": int(extra.get("Estimated Cardinality", 0) or 0),
                    # what the node reads, for the sentence when it is outside the catalog
                    "label": extra.get("Table") or extra.get("Function") or node["name"],
                }
            )
    return scans


def operator_counts(plan: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for node in walk(plan):
        name = node.get("name", "?")
        counts[name] = counts.get(name, 0) + 1
    return counts


_TABLE_REF = re.compile(
    r"\b(?:from|join|into|update|table)\s+((?:\"[^\"]+\"|[\w]+)(?:\.(?:\"[^\"]+\"|[\w]+))*)",
    re.IGNORECASE,
)


def base_tables(engine: Engine, sql: str) -> list[str]:
    """Table names the statement refers to, in order of appearance. DuckDB's own parse of
    the SQL for a SELECT (``json_serialize_sql`` serialises nothing else); a keyword scan
    for writes. CTE names come out too; the caller keeps the ones the catalog knows."""
    data = json.loads(engine.execute("select json_serialize_sql(?)", [sql]).fetchone()[0])
    names: list[str] = []

    def add(name: str) -> None:
        bare = name.split(".")[-1].strip('"')
        if bare and bare not in names:
            names.append(bare)

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "BASE_TABLE" and node.get("table_name"):
                add(node["table_name"])
            for value in node.values():
                visit(value)
        elif isinstance(node, list):
            for value in node:
                visit(value)

    if "statements" in data:
        visit(data)
    else:
        for match in _TABLE_REF.finditer(sql):
            add(match.group(1))
    return names


def machine_profile(engine: Engine, root: str) -> dict[str, Any]:
    limit_text = engine.execute("select current_setting('memory_limit')").fetchone()[0]
    threads = engine.execute("select current_setting('threads')").fetchone()[0]
    battery = psutil.sensors_battery()
    return {
        "platform": platform.system(),
        "machine": platform.machine(),
        "ram": psutil.virtual_memory().total,
        "memory_limit": parse_memory(limit_text),
        "memory_limit_text": limit_text,
        "cores": os.cpu_count(),
        "threads": int(threads),
        "free_disk": shutil.disk_usage(root).free,
        "on_battery": (not battery.power_plugged) if battery is not None else None,
    }


def machine_hash(profile: dict[str, Any]) -> str:
    key = f"{profile['platform']}|{profile['machine']}|{profile['ram']}|{profile['cores']}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


#: What a cached read is capped at when the cache cannot be bypassed (decision 2 of
#: September 11, 2026): a PCIe 4 NVMe's ceiling, so the gauge errs fast by a known bound.
CACHED_PROBE_CEILING_MBPS = 7000.0
#: Faster than this is not a disk; a bypass that reports it did not bypass, and the
#: figure is treated as cached (macOS serves pages already in memory even under F_NOCACHE).
IMPLAUSIBLE_MBPS = 20_000.0
PROBE_CHUNK = 4 * 1024 * 1024


@dataclass
class ProbeResult:
    """MB per second, and how it was measured: ``nocache`` (macOS ``F_NOCACHE``), ``direct``
    (Linux ``O_DIRECT``), or ``cached`` (through the page cache, capped)."""

    mbps: float
    method: str
    size_bytes: int


def _bypass_flags() -> tuple[int, str] | None:
    """The open flag and the method name for a cache-bypassed file on this platform, or
    None where there is neither (Windows; a filesystem that refuses)."""
    if hasattr(os, "O_DIRECT"):
        return os.O_DIRECT, "direct"
    try:
        import fcntl

        if getattr(fcntl, "F_NOCACHE", None) is not None:
            return 0, "nocache"
    except ImportError:
        pass
    return None


def _set_nocache(fd: int) -> None:
    import fcntl

    fcntl.fcntl(fd, fcntl.F_NOCACHE, 1)


def _write_uncached(path: Path, size_bytes: int) -> str | None:
    """Write ``size_bytes`` of random data with the cache bypassed, so no page of the file
    is in memory when it is read back (on macOS, F_NOCACHE on the read alone leaves the
    pages the write put there, and the read is served from them). The method, or None."""
    import mmap

    flags = _bypass_flags()
    if flags is None:
        return None
    flag, method = flags
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | flag, 0o600)
    except OSError:
        return None
    try:
        if method == "nocache":
            _set_nocache(fd)
        buffer = mmap.mmap(-1, PROBE_CHUNK)
        try:
            buffer.write(os.urandom(PROBE_CHUNK))  # incompressible, so no controller shortcut
            written = 0
            while written < size_bytes:
                written += os.writev(fd, [buffer])
            os.fsync(fd)
        finally:
            buffer.close()
    except OSError:
        return None
    finally:
        os.close(fd)
    return method


def _read_uncached(path: Path) -> tuple[float, str] | None:
    """Sequential read of the whole file with the page cache bypassed; seconds and the
    method, or None when the platform or filesystem refuses."""
    import mmap

    flags = _bypass_flags()
    if flags is None:
        return None
    flag, method = flags
    try:
        fd = os.open(path, os.O_RDONLY | flag)
    except OSError:
        return None
    try:
        if method == "nocache":
            _set_nocache(fd)
        # O_DIRECT needs a page-aligned buffer; an anonymous mmap is one on every platform
        buffer = mmap.mmap(-1, PROBE_CHUNK)
        try:
            started = time.perf_counter()
            while True:
                n = os.readv(fd, [buffer])
                if n <= 0:
                    break
            return max(time.perf_counter() - started, 1e-4), method
        except OSError:
            return None
        finally:
            buffer.close()
    finally:
        os.close(fd)


def _write_cached(path: Path, size_bytes: int) -> None:
    block = os.urandom(PROBE_CHUNK)
    with path.open("wb") as f:
        written = 0
        while written < size_bytes:
            f.write(block)
            written += len(block)
        f.flush()
        os.fsync(f.fileno())


def probe_throughput(warehouse: Path, size_mb: int = 512) -> ProbeResult:
    """Brief D36 as amended September 11, 2026: write a file of ``size_mb`` of random bytes
    in the warehouse and read it back once, both with the page cache bypassed
    (``O_DIRECT`` on Linux, ``F_NOCACHE`` on macOS), then delete it. Where the cache
    cannot be bypassed, or the figure is faster than any disk, read through the cache and
    cap the figure, saying so. MB per second and the method; the gauge divides bytes
    scanned by the number."""
    warehouse.mkdir(parents=True, exist_ok=True)
    path = warehouse / ".querysolo-probe.bin"
    size_bytes = max(1, size_mb) * PROBE_CHUNK // 4  # size_mb MiB, a multiple of the chunk
    try:
        bypassed = _write_uncached(path, size_bytes)
        uncached = _read_uncached(path) if bypassed else None
        if uncached is not None:
            elapsed, method = uncached
            mbps = size_bytes / 1e6 / elapsed
            if mbps <= IMPLAUSIBLE_MBPS:
                return ProbeResult(mbps, method, size_bytes)
            # the bypass did not bypass: treat it as a cached read
        if not path.exists() or path.stat().st_size < size_bytes:
            _write_cached(path, size_bytes)
        # the cache cannot be bypassed here: read through it, twice, keep the second, cap
        for _ in range(2):
            started = time.perf_counter()
            with path.open("rb") as f:
                while f.read(PROBE_CHUNK):
                    pass
            elapsed = max(time.perf_counter() - started, 1e-4)
        return ProbeResult(
            min(size_bytes / 1e6 / elapsed, CACHED_PROBE_CEILING_MBPS), "cached", size_bytes
        )
    finally:
        path.unlink(missing_ok=True)


def probe_method(cache: dict[str, Any]) -> str:
    """How the cached figure was measured; a figure from before September 11, 2026 has no
    method recorded and was read through the cache."""
    return str(cache.get("probe") or ("cached" if cache.get("throughput_local_mbps") else "none"))


def load_machine_cache(cache_dir: Path) -> dict[str, Any]:
    path = cache_dir / "machine.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_machine_cache(cache_dir: Path, data: dict[str, Any]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tmp = cache_dir / "machine.json.tmp"
    tmp.write_text(json.dumps(data), encoding="utf-8")
    tmp.replace(cache_dir / "machine.json")
