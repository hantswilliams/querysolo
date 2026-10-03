# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The Iceberg half of a commit, done with pyiceberg (brief D19): validate the client's
requirements against the current metadata, apply its updates, and write the next numbered
metadata file. Mirrors ``pyiceberg.catalog.MetastoreCatalog.commit_table`` so the files
QuerySolo writes are the files pyiceberg would write.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from pyiceberg.catalog import TABLE_METADATA_FILE_NAME_REGEX, MetastoreCatalog
from pyiceberg.io import FileIO, InputFile, InputStream, OutputFile, load_file_io
from pyiceberg.manifest import DataFileContent, ManifestContent
from pyiceberg.partitioning import UNPARTITIONED_PARTITION_SPEC, PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.serializers import FromInputFile, ToOutputFile
from pyiceberg.table.metadata import TableMetadata, new_table_metadata
from pyiceberg.table.sorting import UNSORTED_SORT_ORDER, SortOrder
from pyiceberg.table.update import TableRequirement, TableUpdate, update_table_metadata


def metadata_location(table_location: str, version: int) -> str:
    """pyiceberg's file naming (brief D36): ``<version>-<uuid>.metadata.json``."""
    return f"{table_location}/metadata/{version:05d}-{uuid.uuid4()}.metadata.json"


def parse_version(location: str) -> int:
    match = TABLE_METADATA_FILE_NAME_REGEX.search(location)
    return int(match.group(1)) if match else -1


class _CachedInputFile(InputFile):
    """An immutable remote object (a manifest, a manifest list, a metadata file) served from
    a local copy after the first read, so the second estimate needs no network."""

    def __init__(self, inner: InputFile, cache_path: Path) -> None:
        super().__init__(inner.location)
        self._inner = inner
        self._cache_path = cache_path

    def __len__(self) -> int:
        return self._cache_path.stat().st_size if self._cache_path.exists() else len(self._inner)

    def exists(self) -> bool:
        return self._cache_path.exists() or self._inner.exists()

    def open(self, seekable: bool = True) -> InputStream:
        if not self._cache_path.exists():
            self._cache_path.parent.mkdir(parents=True, exist_ok=True)
            with self._inner.open() as stream:
                data = stream.read()
            tmp = self._cache_path.with_suffix(".tmp")
            tmp.write_bytes(data)
            tmp.replace(self._cache_path)
        return self._cache_path.open("rb")


class CachingFileIO(FileIO):
    """Wraps a FileIO; reads of ``.avro`` and ``.metadata.json`` objects that are not local
    are cached under ``.querysolo/cache/objects/`` (brief §4 step 8)."""

    def __init__(self, inner: FileIO, cache_dir: Path) -> None:
        super().__init__(inner.properties)
        self._inner = inner
        self._dir = cache_dir

    def new_input(self, location: str) -> InputFile:
        inner = self._inner.new_input(location)
        if "://" not in location or location.startswith("file://"):
            return inner
        if not location.endswith((".avro", ".metadata.json")):
            return inner
        return _CachedInputFile(inner, self._dir / location.replace("://", "/"))

    def new_output(self, location: str) -> OutputFile:
        return self._inner.new_output(location)

    def delete(self, location: str | InputFile | OutputFile) -> None:
        self._inner.delete(location)


class MetadataIO:
    """Reads and writes metadata files through pyiceberg's FileIO, so ``file://`` and
    ``s3://`` warehouses are the same code path. With ``cache_dir`` set, remote metadata
    files and manifests are kept locally after the first read: Iceberg never rewrites a
    file under the same name, so the copy is good for as long as the name is (brief §4
    step 8; the second estimate on a bucket table needs no network)."""

    def __init__(self, properties: dict[str, str], cache_dir: Path | None = None) -> None:
        inner: FileIO = load_file_io(properties)
        self.io: FileIO = CachingFileIO(inner, cache_dir) if cache_dir else inner

    def read(self, location: str) -> TableMetadata:
        return FromInputFile.table_metadata(self.io.new_input(location))

    def write(self, table_metadata: TableMetadata, location: str) -> None:
        ToOutputFile.table_metadata(table_metadata, self.io.new_output(location), overwrite=False)

    def table_stats(self, table_metadata: TableMetadata) -> tuple[int, int]:
        """Rows and bytes of the current snapshot, from its manifests. DuckDB's snapshot
        summaries do not carry the totals Java writers add, and its `total-records` does
        not subtract deletes. Rows are the data files' record counts less the position
        deletes on file (DuckDB deletes by position, one entry per row, so the difference
        is exact; an equality delete from another writer would make it an upper bound);
        bytes are every data and delete file the snapshot holds."""
        snapshot = table_metadata.current_snapshot()
        if snapshot is None:
            return 0, 0
        rows = size = 0
        for manifest in snapshot.manifests(self.io):
            for entry in manifest.fetch_manifest_entry(self.io, discard_deleted=True):
                size += entry.data_file.file_size_in_bytes
                if manifest.content == ManifestContent.DATA:
                    rows += entry.data_file.record_count
                elif entry.data_file.content == DataFileContent.POSITION_DELETES:
                    rows -= entry.data_file.record_count
        return max(rows, 0), size


def create_metadata(
    schema: Schema,
    location: str,
    partition_spec: PartitionSpec | None,
    sort_order: SortOrder | None,
    properties: dict[str, str],
) -> TableMetadata:
    return new_table_metadata(
        schema=schema,
        partition_spec=partition_spec or UNPARTITIONED_PARTITION_SPEC,
        sort_order=sort_order or UNSORTED_SORT_ORDER,
        location=location,
        properties=properties,
    )


def apply_commit(
    base: TableMetadata | None,
    base_location: str | None,
    requirements: tuple[TableRequirement, ...],
    updates: tuple[TableUpdate, ...],
) -> TableMetadata:
    """Validate then apply. ``base`` is None for a staged create being committed; the
    requirements raise ``CommitFailedException`` when they do not hold."""
    for requirement in requirements:
        requirement.validate(base)
    return update_table_metadata(
        base_metadata=base if base is not None else MetastoreCatalog._empty_table_metadata(),
        updates=updates,
        enforce_validation=base is None,
        metadata_location=base_location,
    )
