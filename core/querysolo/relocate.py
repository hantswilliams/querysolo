# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""A moved or copied project folder (trust round T5). Iceberg metadata records absolute
locations — the table, every metadata file, every manifest list, every manifest, every data
file — so a folder moved from ``~/acme`` to ``~/Documents/acme`` has tables whose metadata
points at where it used to be. ``moved_from`` notices; ``relocate`` rewrites every location
under the project's own warehouse with pyiceberg's own writers and commits the result to
the catalog, so it is a normal metadata commit and the old metadata files become orphans
for ``expire``. Tables attached from a bucket need nothing and are skipped.

``publish`` (decisions W2) is the same rewriter with a copy first and a bucket as the
target: a table built locally is copied under ``s3://bucket/prefix/main/<name>/`` with the
same relative names, its metadata tree rewritten there, and the catalog moved to it in one
commit, every snapshot kept; the local files become orphans ``expire`` sweeps."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from querysolo.project import NAMESPACE

if TYPE_CHECKING:
    from querysolo.project import Project


@dataclass
class RelocateReport:
    old_root: str | None
    new_root: str
    relocated: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    metadata_files: int = 0
    #: Position-delete files rewritten: their rows name the data file they delete from by
    #: its absolute path, so a moved delete file must be written again with the new paths.
    data_files: int = 0


def _local_path(location: str) -> Path | None:
    return Path(location.removeprefix("file://")) if location.startswith("file://") else None


def _relative_to_warehouse(location: str) -> str | None:
    """``main/orders/metadata/00001-….metadata.json`` from a location under any warehouse
    whose layout is QuerySolo's, or None."""
    marker = f"/{NAMESPACE}/"
    return NAMESPACE + "/" + location.split(marker, 1)[1] if marker in location else None


FILE_PATH_FIELD_ID = 2147483546  # the Iceberg spec's reserved id for a delete file's `file_path`


def _rewrite_position_deletes(io, data_file, translate) -> None:
    """A position-delete Parquet file names, in every row, the data file it deletes from by
    absolute path; a delete file that moved still names the old path and would delete
    nothing. It is written again beside itself with the paths under the new root, and the
    entry's path, size and `file_path` bounds updated (fields 1, 5, 10 and 11)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    source = translate(data_file.file_path)
    with io.new_input(source).open() as f:
        table = pq.read_table(f)
    paths = table.column("file_path")
    new_paths = pa.array([translate(p) for p in paths.to_pylist()], type=paths.type)
    table = table.set_column(table.schema.get_field_index("file_path"), "file_path", new_paths)
    target = source.replace(".parquet", "-relocated.parquet")
    with io.new_output(target).create(overwrite=True) as out:
        pq.write_table(table, out)
    data_file[1] = target
    data_file[5] = len(io.new_input(target))  # the caller does not translate a delete file again
    if new_paths.null_count < len(new_paths) and len(new_paths):
        low = pc.min(new_paths).as_py().encode("utf-8")
        high = pc.max(new_paths).as_py().encode("utf-8")
        for index, value in ((10, low), (11, high)):
            bounds = dict(data_file[index] or {})
            if FILE_PATH_FIELD_ID in bounds:
                bounds[FILE_PATH_FIELD_ID] = value
                data_file[index] = bounds


def moved_from(project: Project) -> str | None:
    """The folder this project's tables were written in, when it is not the one it is open
    from: a local table's metadata is missing at its recorded location and present at the
    same relative path under this folder. None when nothing moved (or nothing is local)."""
    for name in project.store.list_tables(NAMESPACE):
        location = project.store.get_table(NAMESPACE, name)
        old = _local_path(location)
        if old is None or old.exists():
            continue
        relative = _relative_to_warehouse(location)
        if relative is None:
            continue
        here = _local_path(f"{project.warehouse_url}/{relative}")
        if here is not None and here.exists():
            old_warehouse = location[: -len(relative) - 1]
            return old_warehouse.removeprefix("file://").removesuffix(
                "/" + project.config.project.warehouse.removeprefix("./")
            )
    return None


def relocate(project: Project) -> RelocateReport:
    """Rewrite every local table's locations from the folder it was written in to this one.
    Every snapshot is kept: each manifest is read from where the file now is, written again
    beside it with its data-file paths under the new root, then the manifest list, then the
    metadata file as a new version, and the catalog entry is moved to it in one commit."""
    old_root = moved_from(project)
    report = RelocateReport(old_root=old_root, new_root=str(project.root))
    if old_root is None:
        return report
    old_prefix = f"file://{old_root}"
    new_prefix = f"file://{project.root}"

    def translate(location: str) -> str:
        return (
            new_prefix + location[len(old_prefix) :]
            if location.startswith(old_prefix)
            else location
        )

    for name in sorted(project.store.list_tables(NAMESPACE)):
        old_location = project.store.get_table(NAMESPACE, name)
        if not old_location.startswith(old_prefix):
            report.skipped.append(name)  # a bucket, or already under this folder
            continue
        counts = _rewrite(project, name, old_location, translate)
        report.relocated.append(name)
        report.metadata_files += counts[0]
        report.data_files += counts[1]
    return report


def _rewrite(project: Project, name: str, old_location: str, translate) -> tuple[int, int]:
    """Read the table's metadata from ``translate(old_location)`` (where the files now are),
    write every manifest, manifest list and the metadata file again with every location
    translated, and move the catalog to the new metadata file in one commit. Returns the
    metadata files written and the position-delete files rewritten."""
    from pyiceberg.manifest import DataFileContent, write_manifest, write_manifest_list
    from pyiceberg.table.snapshots import MetadataLogEntry

    from querysolo.catalog.commit import metadata_location, parse_version

    io = project.metadata_io.io
    metadata_files = data_files = 0
    md = project.metadata_io.read(translate(old_location))
    metadata_dir = f"{translate(md.location)}/metadata"
    snapshots = []
    for snapshot in md.snapshots:
        moved = snapshot.model_copy(update={"manifest_list": translate(snapshot.manifest_list)})
        new_manifests = []
        for manifest in moved.manifests(io):
            # pyiceberg's Records are positional: the manifest's path is field 0 and a
            # data file's is field 1 (`ManifestFile.manifest_path`, `DataFile.file_path`).
            readable = copy.copy(manifest)
            readable[0] = translate(manifest.manifest_path)
            entries = list(readable.fetch_manifest_entry(io, discard_deleted=False))
            spec = md.specs()[manifest.partition_spec_id]
            target = f"{metadata_dir}/{Path(manifest.manifest_path).name}"
            if target == readable.manifest_path:
                target = target.replace(".avro", "-relocated.avro")
            for entry in entries:
                if entry.data_file.content == DataFileContent.POSITION_DELETES:
                    _rewrite_position_deletes(io, entry.data_file, translate)
                    data_files += 1
                else:
                    entry.data_file[1] = translate(entry.data_file.file_path)
            with write_manifest(
                md.format_version,
                spec,
                md.schema(),
                io.new_output(target),
                manifest.added_snapshot_id,
                "gzip",
            ) as writer:
                for entry in entries:
                    writer.add_entry(entry)
            rewritten = writer.to_manifest_file()
            # the writer leaves the sequence numbers unassigned, as for a manifest of a
            # new commit; these are the old manifests, so theirs are kept (fields 4, 5)
            rewritten[3] = manifest.content  # a delete manifest stays a delete manifest
            rewritten[4] = manifest.sequence_number
            rewritten[5] = manifest.min_sequence_number
            new_manifests.append(rewritten)
            metadata_files += 1
        list_target = f"{metadata_dir}/{Path(snapshot.manifest_list).name}"
        if list_target == moved.manifest_list:
            list_target = list_target.replace(".avro", "-relocated.avro")
        with write_manifest_list(
            md.format_version,
            io.new_output(list_target),
            snapshot.snapshot_id,
            snapshot.parent_snapshot_id,
            snapshot.sequence_number,
            "gzip",
        ) as list_writer:
            list_writer.add_manifests(new_manifests)
        metadata_files += 1
        snapshots.append(snapshot.model_copy(update={"manifest_list": list_target}))
    updates: dict[str, Any] = {
        "location": translate(md.location),
        "snapshots": snapshots,
        "metadata_log": [
            MetadataLogEntry(metadata_file=translate(e.metadata_file), timestamp_ms=e.timestamp_ms)
            for e in md.metadata_log
        ],
    }
    new_md = md.model_copy(update=updates)
    new_location = metadata_location(updates["location"], parse_version(old_location) + 1)
    project.metadata_io.write(new_md, new_location)
    project.store.update_table(NAMESPACE, name, old_location, new_location)
    return metadata_files + 1, data_files


class NotPublishable(Exception):
    """An attached table (its files are not QuerySolo's), a table already in a bucket, or a
    target that is not an `s3://` prefix."""


@dataclass
class PublishReport:
    name: str
    source: str
    target: str
    #: Every data, delete and metadata file under the table: how many, how heavy.
    files: int = 0
    bytes: int = 0
    #: Copied this time, and already in the bucket at the same size (a publish resumed).
    copied: int = 0
    skipped: int = 0
    metadata_files: int = 0
    data_files: int = 0
    #: The bandwidth figure's estimate for the copy, when the cache has one.
    seconds: float | None = None
    dry_run: bool = False


def _table_files(location: str) -> list[tuple[Path, int]]:
    root = _local_path(location)
    if root is None:
        return []
    out = []
    for sub in ("data", "metadata"):
        folder = root / sub
        if folder.is_dir():
            out += [(f, f.stat().st_size) for f in sorted(folder.rglob("*")) if f.is_file()]
    return out


def publish(
    project: Project,
    name: str,
    prefix: str,
    dry_run: bool = False,
    cap_seconds: float | None = None,
) -> PublishReport:
    """`querysolo tables publish <name> <s3://bucket/prefix>`: the table's files copied under
    ``<prefix>/main/<name>/`` with the same relative names (a file already there at the same
    size is not copied again, so an interrupted publish resumes), the metadata tree written
    again with every location in the bucket, and the catalog moved to it in one commit —
    the last step, so a crash before it leaves the local table in place. ``dry_run``
    counts and weighs; ``cap_seconds`` refuses a copy the bandwidth figure says would take
    longer, the way Red refuses (`--yes` lifts it)."""
    from querysolo.catalog.store import NotFound
    from querysolo.gauge import inputs
    from querysolo.register import SOURCE_PROPERTY, table_property
    from querysolo.tables import NoSuchTable

    if not prefix.startswith("s3://"):
        raise NotPublishable(f"the target is an s3://bucket/prefix, not {prefix}")
    try:
        old_location = project.store.get_table(NAMESPACE, name)
    except NotFound:
        raise NoSuchTable(name) from None
    md = project.metadata_io.read(old_location)
    if table_property(md.properties, SOURCE_PROPERTY) is not None:
        raise NotPublishable(
            f"{name} is registered from {table_property(md.properties, SOURCE_PROPERTY)}; its files are not "
            "QuerySolo's to move"
        )
    if _local_path(md.location) is None:
        raise NotPublishable(f"{name} is already in a bucket: {md.location}")
    source_root = md.location.rstrip("/")
    target_root = f"{prefix.rstrip('/')}/{NAMESPACE}/{name}"
    report = PublishReport(name=name, source=source_root, target=target_root, dry_run=dry_run)
    files = _table_files(source_root)
    report.files, report.bytes = len(files), sum(size for _, size in files)
    bandwidth = inputs.load_machine_cache(project.cache_dir).get("bandwidth_mbps")
    if bandwidth:
        report.seconds = report.bytes * 8 / (bandwidth * 1_000_000)
    if dry_run:
        return report
    if cap_seconds is not None and report.seconds is not None and report.seconds > cap_seconds:
        raise NotPublishable(
            f"{name} weighs {report.bytes:,} bytes and would take about {report.seconds:,.0f} s "
            f"at {bandwidth:,.0f} Mbps, over the cap of {cap_seconds:,.0f} s; `--yes` publishes "
            "anyway"
        )

    def translate(location: str) -> str:
        return (
            target_root + location[len(source_root) :]
            if location.startswith(source_root)
            else location
        )

    io = project.metadata_io.io
    for path, size in files:
        target = translate(f"file://{path}")
        try:
            if len(io.new_input(target)) == size:
                report.skipped += 1
                continue
        except (FileNotFoundError, OSError):
            pass
        with path.open("rb") as src, io.new_output(target).create(overwrite=True) as out:
            for chunk in iter(lambda: src.read(8 * 1024 * 1024), b""):
                out.write(chunk)
        report.copied += 1
    report.metadata_files, report.data_files = _rewrite(project, name, old_location, translate)
    return report
