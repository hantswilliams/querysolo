# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Per-table file statistics and pruning (brief D20, D21). One ``StaticTable`` per (table,
snapshot) is kept in memory so pyiceberg's planning runs in milliseconds; the whole-table
stats and the per-column byte fractions are written to ``.querysolo/cache/manifests/``.

DuckDB-written manifests carry bounds but no column sizes, so the projected-column fraction
comes from one Parquet footer per snapshot, read with DuckDB's ``parquet_metadata``."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from pyiceberg.catalog.noop import NoopCatalog
from pyiceberg.expressions import AlwaysTrue, BooleanExpression
from pyiceberg.manifest import ManifestContent
from pyiceberg.table import StaticTable
from pyiceberg.table.metadata import TableMetadata

from querysolo.catalog.commit import MetadataIO
from querysolo.register import table_property

if TYPE_CHECKING:
    from querysolo.project import Project


@dataclass
class FileStat:
    path: str
    size: int
    records: int
    column_sizes: dict[int, int] = field(default_factory=dict)


@dataclass
class TableStats:
    name: str
    snapshot_id: int | None
    location: str
    rows: int
    bytes: int
    files: int
    column_bytes: dict[str, int]
    """Compressed bytes per column in one sampled data file, from its Parquet footer."""
    locality: str = "local"
    """``local`` or ``remote``, from where the data files live, not the metadata (D26)."""
    source: str = ""
    """What the sentence names: the registered prefix, or the data files' common prefix."""

    def fraction(self, columns: list[str]) -> float:
        total = sum(self.column_bytes.values())
        if not columns or not total:
            return 1.0
        return max(sum(self.column_bytes.get(c, 0) for c in columns) / total, 0.01)

    def bytes_per_row(self, columns: list[str] | None = None) -> float:
        if not self.rows:
            return 0.0
        return self.bytes / self.rows * (self.fraction(columns) if columns else 1.0)


@dataclass
class Pruned:
    bytes: int
    rows: int
    files: int
    of_files: int


def _common_prefix(paths: list[str]) -> str:
    if not paths:
        return ""
    parts = [p.rsplit("/", 1)[0] for p in paths]
    prefix = parts[0]
    for p in parts[1:]:
        while not p.startswith(prefix):
            prefix = prefix.rsplit("/", 1)[0]
    return prefix + "/"


def file_stats(metadata_io: MetadataIO, table_metadata: TableMetadata) -> list[FileStat]:
    snapshot = table_metadata.current_snapshot()
    if snapshot is None:
        return []
    stats = []
    for manifest in snapshot.manifests(metadata_io.io):
        if manifest.content != ManifestContent.DATA:
            continue
        for entry in manifest.fetch_manifest_entry(metadata_io.io, discard_deleted=True):
            f = entry.data_file
            stats.append(
                FileStat(
                    f.file_path, f.file_size_in_bytes, f.record_count, dict(f.column_sizes or {})
                )
            )
    return stats


def bytes_per_row(stats: list[FileStat], field_ids: set[int] | None = None) -> float:
    records = sum(s.records for s in stats)
    if not records:
        return 0.0
    if field_ids is None:
        return sum(s.size for s in stats) / records
    projected = sum(sum(v for k, v in s.column_sizes.items() if k in field_ids) for s in stats)
    if not projected:
        return sum(s.size for s in stats) / records
    return projected / records


class ManifestCache:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.dir = project.cache_dir / "manifests"
        self.io = project.metadata_io.io  # caches remote manifests and metadata by location
        self._tables: dict[tuple[str, int | None], tuple[StaticTable, TableStats]] = {}

    def get(self, name: str, metadata_location: str) -> tuple[StaticTable, TableStats]:
        md = self.project.metadata_io.read(metadata_location)
        snapshot = md.current_snapshot()
        key = (name, snapshot.snapshot_id if snapshot else None)
        if key in self._tables:
            return self._tables[key]
        table = StaticTable(
            identifier=("static-table", metadata_location),
            metadata_location=metadata_location,
            metadata=md,
            io=self.io,
            catalog=NoopCatalog("static-table"),
        )
        stats = self._load(key) or self._compute(name, md, metadata_location)
        self._tables[key] = (table, stats)
        return table, stats

    def _cache_path(self, key: tuple[str, int | None]) -> Path:
        return self.dir / f"{key[0]}-{key[1]}.json"

    def _load(self, key: tuple[str, int | None]) -> TableStats | None:
        path = self._cache_path(key)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return TableStats(**data)

    def _compute(self, name: str, md: TableMetadata, location: str) -> TableStats:
        files = file_stats(self.project.metadata_io, md)
        snapshot = md.current_snapshot()
        largest = max(files, key=lambda f: f.size, default=None)
        data_paths = [f.path for f in files]
        remote = any(not p.startswith("file://") for p in data_paths)
        source = (
            table_property(md.properties, "querysolo.source-prefix") or _common_prefix(data_paths) or md.location
        )
        stats = TableStats(
            name=name,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
            location=md.location,
            rows=sum(f.records for f in files),
            bytes=sum(f.size for f in files),
            files=len(files),
            column_bytes=self._column_bytes(largest.path) if largest else {},
            locality="remote" if remote else "local",
            source=source,
        )
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self._cache_path((name, stats.snapshot_id)).with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(stats)), encoding="utf-8")
        tmp.replace(self._cache_path((name, stats.snapshot_id)))  # atomic: processes share it
        return stats

    def _column_bytes(self, path: str) -> dict[str, int]:
        """Per-column compressed bytes from one Parquet footer; the engine reads local files
        directly and remote ones through its S3 secret."""
        target = path.removeprefix("file://")
        try:
            rows = self.project.engine.execute(
                "select path_in_schema, sum(total_compressed_size) from parquet_metadata(?) "
                "group by 1",
                [target],
            ).fetchall()
        except Exception:  # noqa: BLE001  a footer the engine cannot reach; whole rows then
            return {}
        return {name: int(size) for name, size in rows}

    def prune(
        self,
        name: str,
        metadata_location: str,
        expression: BooleanExpression,
        projections: list[str],
    ) -> tuple[Pruned, bool]:
        """Files surviving the expression, and whether pyiceberg accepted it; on a binding
        error the whole table counts, the safe direction."""
        table, stats = self.get(name, metadata_location)
        try:
            tasks = list(table.scan(row_filter=expression).plan_files())
            accepted = True
        except Exception:  # noqa: BLE001  an expression pyiceberg cannot bind
            tasks = list(table.scan(row_filter=AlwaysTrue()).plan_files())
            accepted = False
        fraction = stats.fraction(projections)
        return (
            Pruned(
                bytes=int(sum(t.file.file_size_in_bytes for t in tasks) * fraction),
                rows=sum(t.file.record_count for t in tasks),
                files=len(tasks),
                of_files=stats.files,
            ),
            accepted,
        )
