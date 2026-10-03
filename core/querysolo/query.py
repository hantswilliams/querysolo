# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""A query (brief §3.6, D10, D21, D23): gauge (step 5), then execute through the attached
catalog, stream Arrow record batches, retry a catalog conflict, and record the run with
the profiler's actuals in history."""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import duckdb
import psutil
import pyarrow as pa

from querysolo import __version__
from querysolo.catalog.store import NotFound
from querysolo.engine import CatalogConflict, is_conflict
from querysolo.gauge import inputs, predicates, verdict
from querysolo.gauge.model import Estimate, Thresholds, estimate_plan
from querysolo.history import Run
from querysolo.project import NAMESPACE

if TYPE_CHECKING:
    from querysolo.project import Project

CONFLICT_ATTEMPTS = 3


class Interrupted(Exception):
    """The statement was stopped before it produced its first batch (``Engine.interrupt``);
    the run is in history as stopped early, with no error."""


class RedRefused(Exception):
    """The gauge said Needs more machine and the caller did not allow it (exit 2)."""

    def __init__(self, estimate: Estimate) -> None:
        super().__init__(estimate.reason)
        self.estimate = estimate


# -- identity (brief D10) --------------------------------------------------------------


def normalise(sql: str) -> str:
    """Comments stripped, whitespace collapsed, everything outside string literals
    lower-cased, literals kept."""
    out, i, n = [], 0, len(sql)
    while i < n:
        ch = sql[i]
        if ch == "'":
            end = i + 1
            while end < n:
                if sql[end] == "'" and not (end + 1 < n and sql[end + 1] == "'"):
                    break
                end += 2 if sql[end] == "'" else 1
            out.append(sql[i : end + 1])
            i = end + 1
        elif sql.startswith("--", i):
            i = sql.find("\n", i)
            i = n if i == -1 else i
        elif sql.startswith("/*", i):
            end = sql.find("*/", i + 2)
            i = n if end == -1 else end + 2
        else:
            out.append(ch.lower())
            i += 1
    return re.sub(r"\s+", " ", "".join(out)).strip()


def sql_hash(sql: str) -> str:
    return hashlib.sha256(normalise(sql).encode()).hexdigest()


def fingerprint(sql: str, tables: list[tuple[str, int | None]]) -> str:
    snapshots = ";".join(f"{name}={snapshot}" for name, snapshot in sorted(tables))
    return hashlib.sha256(f"{normalise(sql)}|{snapshots}".encode()).hexdigest()


# -- the run ------------------------------------------------------------------------


@dataclass
class Actual:
    wall: float
    rows_returned: int
    rows_scanned: int | None = None
    bytes: int | None = None
    peak_mem: int | None = None
    peak_rss: int | None = None
    spill: int | None = None


class _RssSampler(threading.Thread):
    """Peak process RSS during execution, the cross-check of D21."""

    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.peak = 0
        self._stop = threading.Event()

    def run(self) -> None:
        process = psutil.Process()
        while not self._stop.is_set():
            self.peak = max(self.peak, process.memory_info().rss)
            self._stop.wait(0.05)

    def stop(self) -> int:
        self._stop.set()
        self.join(timeout=1)
        return self.peak


class Result:
    """Iterates ``pyarrow.RecordBatch``; ``actual`` is set once the batches are exhausted or
    the result is closed; ``run_id`` is the history row."""

    def __init__(self, project: Project, sql: str, run: Run, scans: list[dict[str, Any]]) -> None:
        self.project = project
        self.sql = sql
        self.run = run
        self.scans = scans
        self.estimate: Estimate | None = None
        self.actual: Actual | None = None
        self.run_id: int | None = None
        self.question_slug: str | None = None
        self._reader: pa.RecordBatchReader | None = None
        self._rows = 0
        self._started = 0.0
        self._sampler = _RssSampler()

    def _execute(self, batch_rows: int) -> None:
        self._sampler.start()
        self._started = time.perf_counter()
        for attempt in range(CONFLICT_ATTEMPTS):
            try:
                cursor = self.project.engine.execute(self.sql)
                break
            except duckdb.InterruptException as e:
                self._finish(complete=False)
                raise Interrupted() from e
            except duckdb.Error as e:
                if not is_conflict(e):
                    self._finish(error=str(e))
                    raise
                self.run.retries = attempt + 1
                if attempt == CONFLICT_ATTEMPTS - 1:
                    self.run.retries = attempt
                    self._finish(error=str(e))
                    raise CatalogConflict(str(e)) from e
                time.sleep(0.1 * (attempt + 1))
        self._reader = cursor.to_arrow_reader(batch_rows)

    def __iter__(self) -> Iterator[pa.RecordBatch]:
        assert self._reader is not None
        try:
            for batch in self._reader:
                self._rows += batch.num_rows
                yield batch
        except duckdb.InterruptException:
            # stopped mid-stream (the app's Esc): what is known is recorded, as close() does
            self._finish(complete=False)
            return
        except duckdb.Error as e:
            self._finish(error=str(e))
            raise
        self._finish()

    def to_arrow(self) -> pa.Table:
        assert self._reader is not None
        schema = self._reader.schema
        return pa.Table.from_batches(list(self), schema=schema)

    def close(self) -> None:
        """Record what is known if the consumer stopped early."""
        if self.actual is None:
            self._finish(complete=False)

    def _finish(self, error: str | None = None, complete: bool = True) -> None:
        if self.actual is not None:
            return
        wall = time.perf_counter() - self._started
        peak_rss = self._sampler.stop()
        self.actual = Actual(wall=wall, rows_returned=self._rows, peak_rss=peak_rss)
        if complete and error is None:
            self._read_profile()
        run = self.run
        run.ran = True
        run.error = error
        run.actual_wall = wall
        run.actual_peak_rss = peak_rss
        run.actual_rows_scanned = self.actual.rows_scanned
        run.actual_bytes = self.actual.bytes
        run.actual_peak_mem = self.actual.peak_mem
        run.actual_spill = self.actual.spill
        self.run_id = self.project.history.record(run)
        if self.question_slug and error is None and complete:
            self.project.history.record_question_run(self.question_slug, self.run_id)

    def _read_profile(self) -> None:
        profile = self.project.engine.last_profile()
        if not profile:
            return
        self.actual.peak_mem = profile.get("system_peak_buffer_memory")
        self.actual.spill = profile.get("system_peak_temp_dir_size")
        profile_scans = [
            node
            for node in inputs.walk([profile])
            if node.get("operator_type") in inputs.SCAN_NODES
        ]
        if not profile_scans:
            return
        # Derived (D21): rows each scan read from its files, as a share of the table, times
        # the table's bytes and the projected columns' share of them. The profiler's
        # rows-scanned counter over-reports on tiny single-file tables, so it is capped.
        rows_total, bytes_total = 0, 0.0
        for scan, node in zip(self.scans, profile_scans, strict=False):
            table_rows = scan.get("table_rows") or 0
            read = node.get("operator_rows_scanned") or node.get("operator_cardinality") or 0
            read = min(read, table_rows) if table_rows else read
            rows_total += read
            if table_rows:
                share = read / table_rows
                bytes_total += share * scan.get("table_bytes", 0) * scan.get("fraction", 1.0)
        self.actual.rows_scanned = rows_total
        self.actual.bytes = int(bytes_total)


def _through_views(project: Project, names: list[str]) -> list[str]:
    """A name that is a catalog view (real-data brief R6) stands for the tables its SQL
    reads, recursively; the plan's scans are of those tables, never of the view."""
    views = project.engine.views
    out: list[str] = []
    seen: set[str] = set()

    def visit(name: str) -> None:
        if name in seen:
            return
        seen.add(name)
        if name in views:
            for inner in inputs.base_tables(project.engine, views[name]):
                visit(inner)
        elif name not in out:
            out.append(name)

    for name in names:
        visit(name)
    return out


def _table_scans(project: Project, sql: str, plan: list[dict[str, Any]]) -> tuple[list, list]:
    """The catalog tables the statement reads with their current snapshot ids, and the
    plan's scan nodes each attributed to one of them (by projected columns, then by order),
    pruned with the filters DuckDB pushed down (brief D20)."""
    known = []
    for name in _through_views(project, inputs.base_tables(project.engine, sql)):
        try:
            location = project.store.get_table(NAMESPACE, name)
        except NotFound:
            continue  # a CTE, a temp table, or something outside the catalog
        _, stats = project.manifests.get(name, location)
        known.append(
            {
                "name": name,
                "location": location,
                "snapshot_id": stats.snapshot_id,
                "locality": stats.locality,
                "source": stats.source,
                "columns": set(project.metadata_io.read(location).schema().column_names),
                "stats": stats,
                "bytes_after_pruning": 0,
                "files_after_pruning": 0,
            }
        )
    scans = inputs.scan_nodes(plan)
    unassigned = list(known)
    for scan in scans:
        projected = set(scan["projections"])
        candidates = [t for t in known if projected and projected <= t["columns"]]
        table = candidates[0] if len(candidates) == 1 else (unassigned[0] if unassigned else None)
        if scan["name"] not in inputs.CATALOG_SCAN_NODES or table is None:
            # Outside the catalog — a file read by function, a native or temp table, or an
            # Iceberg scan no known table accounts for: nothing is known about what it
            # reads, so the estimate says so rather than counting it as nothing (T3).
            scan.update(
                bytes=0,
                rows=0,
                files=0,
                pruning="full",
                bytes_per_row=8.0,
                fraction=1.0,
                unattributed=str(scan["label"]).lower(),
            )
            continue
        if table in unassigned:
            unassigned.remove(table)
        translation = predicates.translate(scan["filters"])
        pruned, accepted = project.manifests.prune(
            table["name"], table["location"], translation.expression, scan["projections"]
        )
        stats = table["stats"]
        scan.update(
            table=table["name"],
            locality=table["locality"],
            bytes=pruned.bytes,
            rows=pruned.rows,
            files=pruned.files,
            of_files=pruned.of_files,
            pruning=translation.pruning if accepted else "none",
            dropped=translation.dropped,
            bytes_per_row=stats.bytes_per_row(scan["projections"]),
            fraction=stats.fraction(scan["projections"]),
            table_rows=stats.rows,
            table_bytes=stats.bytes,
        )
        table["bytes_after_pruning"] += pruned.bytes
        table["files_after_pruning"] += pruned.files
    tables = [
        {
            k: t[k]
            for k in (
                "name",
                "snapshot_id",
                "locality",
                "source",
                "bytes_after_pruning",
                "files_after_pruning",
            )
        }
        for t in known
    ]
    return tables, scans


def _overall_pruning(scans: list[dict[str, Any]]) -> str:
    states = {s.get("pruning", "full") for s in scans}
    if "none" in states:
        return "none"
    return "partial" if "partial" in states else "full"


def _thresholds(project: Project) -> Thresholds:
    g = project.config.gauge
    return Thresholds(g.green_max_seconds, g.yellow_max_seconds, g.green_max_memory_fraction)


def _estimate(project: Project, sql: str) -> tuple[Estimate, list[dict[str, Any]]]:
    engine = project.engine
    plan = inputs.plan_json(engine, sql)
    tables, scans = _table_scans(project, sql, plan)
    machine = inputs.machine_profile(engine, str(project.root))
    cache = inputs.load_machine_cache(project.cache_dir)
    throughput = cache.get("throughput_local_mbps")
    bandwidth = cache.get("bandwidth_mbps")
    numbers = estimate_plan(plan, scans, machine, throughput, bandwidth, _thresholds(project))
    remote_source = next((t["source"] for t in tables if t["locality"] == "remote"), None)
    text = verdict.reason(numbers, remote_source, bandwidth)
    est = Estimate(
        verdict=numbers["verdict"],
        words=verdict.WORDS[numbers["verdict"]],
        bytes_scanned=numbers["bytes_scanned"],
        rows_scanned=numbers["rows_scanned"],
        files_scanned=numbers["files_scanned"],
        peak_memory=numbers["peak_memory"],
        wall_local=numbers["wall_local"],
        io_seconds=numbers["io_seconds"],
        cpu_seconds=numbers["cpu_seconds"],
        spill_bytes=numbers["spill_bytes"],
        reason=text,
        fingerprint=fingerprint(sql, [(t["name"], t["snapshot_id"]) for t in tables]),
        pruning=_overall_pruning(scans),
        tables=tables,
        remote=numbers["remote"],
        bandwidth_mbps=bandwidth,
        throughput_mbps=numbers["throughput_mbps"],
        worker=numbers["worker"],
        wall_burst=numbers["wall_burst"],
        cost_burst=numbers["cost_burst"],
        cap=numbers["cap"],
        plan=plan,
    )
    return est, scans


def estimate(project: Project, sql: str) -> Estimate:
    """The gauge: three numbers, a verdict, one sentence (brief D8, D28, D29)."""
    return _estimate(project, sql)[0]


def query(project: Project, sql: str, allow_red: bool = False, batch_rows: int = 1000) -> Result:
    engine = project.engine
    est: Estimate | None = None
    scans: list[dict[str, Any]] = []
    tables: list[dict[str, Any]] = []
    plan: list[dict[str, Any]] = []
    try:
        est, scans = _estimate(project, sql)
        tables, plan = est.tables, est.plan
    except Exception:  # noqa: BLE001
        # The gauge never blocks execution (PRD F0.3): run anyway, record without an
        # estimate, and let DuckDB say why if the statement itself is wrong.
        try:
            plan = inputs.plan_json(engine, sql)
            tables, scans = _table_scans(project, sql, plan)
        except Exception:  # noqa: BLE001
            plan, tables, scans = [], [], []
    profile = inputs.machine_profile(engine, str(project.root))
    cache = inputs.load_machine_cache(project.cache_dir)
    run = Run(
        fingerprint=est.fingerprint
        if est
        else fingerprint(sql, [(t["name"], t["snapshot_id"]) for t in tables]),
        sql_hash=sql_hash(sql),
        sql_text=sql,
        querysolo_version=__version__,
        duckdb_version=duckdb.__version__,
        machine_hash=inputs.machine_hash(profile),
        machine=profile,
        tables=[{k: v for k, v in t.items() if k != "source"} for t in tables],
        operator_counts=inputs.operator_counts(plan),
        throughput_local_mbps=cache.get("throughput_local_mbps"),
        bandwidth_mbps=cache.get("bandwidth_mbps"),
    )
    if est is not None:
        run.pruning = est.pruning
        run.est_bytes = est.bytes_scanned
        run.est_peak_mem = est.peak_memory
        run.est_wall_local = est.wall_local
        run.est_wall_burst = est.wall_burst
        run.est_cost_burst = est.cost_burst
        run.verdict = est.verdict
        run.reason = est.reason
        if est.verdict == "red" and not allow_red:
            run.ran = False
            run.ran_where = "refused"
            project.history.record(run)
            raise RedRefused(est)
    result = Result(project, sql, run, scans)
    result.estimate = est
    result._execute(batch_rows)
    return result
