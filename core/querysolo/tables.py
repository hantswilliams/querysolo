# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Tables (brief §3.6, D16, D24, D36, M3): preview a file, import a file or a folder into an
Iceberg table through the catalog, list, describe, sample. Every write is a DuckDB
statement through the attached catalog; the catalog does the commit."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from querysolo import types
from querysolo.catalog.store import LEGACY_REPLACE_SUFFIX, REPLACE_SUFFIX, NotFound
from querysolo.engine import run_with_retry
from querysolo.project import NAMESPACE, TABLES_END, TABLES_START, identifier
from querysolo.register import table_property

if TYPE_CHECKING:
    from querysolo.project import Project

READERS = {
    ".csv": "read_csv_auto({path})",
    ".tsv": "read_csv_auto({path})",
    ".parquet": "read_parquet({path})",
    ".json": "read_json_auto({path})",
    ".jsonl": "read_json_auto({path})",
    ".xlsx": "read_xlsx({path})",
}
Mode = Literal["create", "replace", "append"]


class UnsupportedFile(Exception):
    pass


class TableExists(Exception):
    """The table is there already; the caller offers replace, append or another name."""


class NotExpirable(Exception):
    """A table `expire` will not touch: one registered with `tables attach` (its files are
    not QuerySolo's), or one whose location is outside the project's warehouse."""


class NoSuchTable(Exception):
    pass


class ReservedName(Exception):
    """A name ending in the replace suffix is QuerySolo's, not a user's (T1)."""


def replace_name(name: str) -> str:
    """The temporary table a replace builds before the swap."""
    return f"{name}{REPLACE_SUFFIX}"


def interrupted_replace_of(name: str) -> str | None:
    """The final name a temporary table was meant to become, or None for an ordinary name.
    A replace interrupted before the rename carries the old suffix (rename plan R4)."""
    for suffix in (REPLACE_SUFFIX, LEGACY_REPLACE_SUFFIX):
        if name.endswith(suffix):
            return name.removesuffix(suffix)
    return None


@dataclass
class Column:
    name: str
    duckdb_type: str
    iceberg_type: str
    note: str = ""


@dataclass
class Preview:
    name: str
    source: str
    columns: list[Column]
    sample: list[tuple]
    #: A remote prefix's preview (`tables attach`, not `import`): the file count and bytes
    #: of what would be registered in place, and whether it is read without credentials.
    remote: bool = False
    files: int | None = None
    bytes: int | None = None
    anonymous: bool = False


@dataclass
class TableInfo:
    name: str
    rows: int
    bytes: int
    columns: list[tuple[str, str]]
    location: str
    snapshot_id: int | None
    #: When the current snapshot was committed: the table's freshness, in the list too so
    #: the app's tables panel can show it without a describe per table.
    freshness: datetime | None
    #: For a table registered from a prefix (`tables attach`): the prefix; None for a table
    #: QuerySolo wrote. ``public`` is true when it is read without credentials.
    source: str | None = None
    public: bool = False
    #: "table", or "view" for a view in the catalog (real-data brief R6), whose rows and
    #: bytes are 0 and whose `view_sql` is its query.
    kind: str = "table"
    view_sql: str | None = None
    #: A replace interrupted between its drop and its rename (T1): the name this temporary
    #: table was meant to become, so the list can say how to finish it; None otherwise.
    interrupted_replace_of: str | None = None
    #: The project folder moved and this table's metadata still points at where it was (T5):
    #: rows, bytes and columns are unknown until `querysolo relocate`.
    needs_relocate: bool = False


@dataclass
class ExpireReport:
    name: str
    keep_days: int
    snapshots_before: int
    snapshots_removed: int
    files_removed: int
    bytes_reclaimed: int


@dataclass
class TableDescription(TableInfo):
    partitioning: str = "unpartitioned"
    #: Snapshots `querysolo tables expire` would remove at the project's retention, and the
    #: bytes of the files only they reference (decision 4, September 11, 2026).
    expirable_snapshots: int = 0
    reclaimable_bytes: int = 0
    keep_days: int = 7
    last_commit: dict[str, Any] = field(default_factory=dict)
    snapshots: int = 0
    format_version: int = 2
    #: Every snapshot, newest first (real-data brief R7, the app's table detail): id, when,
    #: operation, what it added, whether it is current and whether `expire` would take it.
    snapshot_list: list[dict[str, Any]] = field(default_factory=list)
    #: A view's properties (`querysolo.dbt-model` names the dbt model it came from); empty
    #: for a table.
    properties: dict[str, str] = field(default_factory=dict)
    #: For an attached table (trust round T2): when its files were last verified against
    #: the prefix, and the ones that changed under the same path since, ``(uri, why)``;
    #: ``verify_error`` when the prefix could not be listed (offline, no credentials).
    verified_at: str | None = None
    changed_files: list[tuple[str, str]] = field(default_factory=list)
    verify_error: str | None = None
    #: A table published to a bucket (decisions W2) whose files are still under the local
    #: warehouse too: how many, until `expire` sweeps them after its grace.
    local_copy_files: int = 0


def _rows_after(total: int | None, position_deletes: int | None) -> int | None:
    """A snapshot's live rows from its summary: DuckDB's `total-records` counts the data
    files' rows, deleted ones included; the position deletes on file come off."""
    if total is None:
        return None
    return max(total - (position_deletes or 0), 0)


def _sql_literal(text: str) -> str:
    return "'" + text.replace("'", "''") + "'"


def _quoted(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


class Tables:
    def __init__(self, project: Project) -> None:
        self.project = project

    # -- reading files -------------------------------------------------------------

    @staticmethod
    def _reader(path: Path) -> str:
        template = READERS.get(path.suffix.lower())
        if template is None:
            raise UnsupportedFile(f"{path.name}: QuerySolo imports {', '.join(READERS)}")
        if not path.exists():
            raise FileNotFoundError(path)
        return template.format(path=_sql_literal(str(path)))

    def _inferred(self, reader: str) -> list[Column]:
        rows = self.project.engine.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()
        columns = []
        for name, duckdb_type, *_ in rows:
            c = types.coerce(duckdb_type)
            columns.append(Column(name, duckdb_type, c.iceberg_type, c.note))
        return columns

    @staticmethod
    def _select(columns: list[Column]) -> str:
        parts = []
        for col in columns:
            cast_to = types.coerce(col.duckdb_type).cast_to
            q = _quoted(col.name)
            parts.append(f"CAST({q} AS {cast_to}) AS {q}" if cast_to else q)
        return ", ".join(parts)

    def preview(self, path: str | Path, name: str | None = None, sample: int = 5) -> Preview:
        path = Path(path)
        reader = self._reader(path)
        columns = self._inferred(reader)
        rows = self.project.engine.execute(
            f"SELECT {self._select(columns)} FROM {reader} LIMIT {int(sample)}"
        ).fetchall()
        return Preview(name or identifier(path.stem), str(path), columns, rows)

    def preview_dir(self, path: str | Path, sample: int = 5) -> list[Preview]:
        """One preview per file `import_dir` would import, in the same order, so a folder
        can be looked at before it is imported (CLI `--preview`, the app's drop zone)."""
        return [
            self.preview(file, name=name, sample=sample)
            for name, file in self._dir_files(path).items()
        ]

    # -- importing -----------------------------------------------------------------

    def import_file(
        self, path: str | Path, name: str | None = None, mode: Mode = "create"
    ) -> TableInfo:
        path = Path(path)
        reader = self._reader(path)
        name = name or identifier(path.stem)
        if interrupted_replace_of(name) is not None:
            raise ReservedName(f"{name}: names ending in {REPLACE_SUFFIX} are QuerySolo's own")
        target = f"querysolo.{NAMESPACE}.{_quoted(name)}"
        exists = self._exists(name)
        if mode == "create" and exists:
            raise TableExists(name)
        if mode == "append" and not exists:
            mode = "create"
        if mode == "append":
            columns = self._existing_columns(name)
            statement = f"INSERT INTO {target} SELECT {self._select(columns)} FROM {reader}"
            run_with_retry(self.project.engine, statement)
        elif exists:
            self._replace(name, reader)
        else:
            columns = self._inferred(reader)
            statement = f"CREATE TABLE {target} AS SELECT {self._select(columns)} FROM {reader}"
            run_with_retry(self.project.engine, statement)
        self.refresh_agents_md()
        return self._info(name)

    def _replace(self, name: str, reader: str) -> None:
        """Build the new table first, then swap (trust round T1). The columns are inferred
        and the whole new table written under a temporary name before anything is dropped,
        so a file that does not parse, a cast that fails or a disk that fills leaves the old
        table exactly as it was. Only then: drop the old, rename the new into place, each
        its own catalog commit (DuckDB-Iceberg refuses both inside one transaction; see
        /docs/transactions). The catalog gives the temporary table the final name's folder,
        so the rename moves no data and the old files are orphans `expire` sweeps. A crash
        between the drop and the rename leaves the temporary table listed with the sentence
        that says how to finish it, so the data is never invisible."""
        temp = replace_name(name)
        temp_target = f"querysolo.{NAMESPACE}.{_quoted(temp)}"
        target = f"querysolo.{NAMESPACE}.{_quoted(name)}"
        columns = self._inferred(reader)
        if self._exists(temp):  # an earlier replace was interrupted; this one supersedes it
            run_with_retry(self.project.engine, f"DROP TABLE {temp_target}")
        try:
            run_with_retry(
                self.project.engine,
                f"CREATE TABLE {temp_target} AS SELECT {self._select(columns)} FROM {reader}",
            )
        except Exception:
            if self._exists(temp):
                run_with_retry(self.project.engine, f"DROP TABLE {temp_target}")
            raise
        run_with_retry(self.project.engine, f"DROP TABLE {target}")
        self.rename(temp, name)

    def rename(self, old: str, new: str) -> TableInfo:
        """`querysolo tables rename`: one catalog commit; the data does not move. The verb
        that finishes an interrupted replace (T1)."""
        if not self._exists(old):
            raise NoSuchTable(old)
        if self._exists(new):
            raise TableExists(new)
        run_with_retry(
            self.project.engine,
            f"ALTER TABLE querysolo.{NAMESPACE}.{_quoted(old)} RENAME TO {_quoted(new)}",
        )
        return self._info(new)  # the manifest cache is keyed by name and snapshot: nothing stale

    def import_dir(self, path: str | Path, mode: Mode = "create") -> list[TableInfo]:
        """One table per file (brief D16). Files with an unsupported extension are skipped."""
        return [
            self.import_file(file, name=name, mode=mode)
            for name, file in self._dir_files(path).items()
        ]

    @staticmethod
    def _dir_files(path: str | Path) -> dict[str, Path]:
        root = Path(path)
        if not root.is_dir():
            raise FileNotFoundError(root)
        files = sorted(p for p in root.iterdir() if p.is_file() and p.suffix.lower() in READERS)
        names: dict[str, Path] = {}
        for file in files:
            name = identifier(file.stem)
            if name in names:
                raise TableExists(f"{names[name].name} and {file.name} would both be {name}")
            names[name] = file
        return names

    def _existing_columns(self, name: str) -> list[Column]:
        rows = self.project.engine.execute(
            f"DESCRIBE querysolo.{NAMESPACE}.{_quoted(name)}"
        ).fetchall()
        return [Column(n, t, types.coerce(t).iceberg_type) for n, t, *_ in rows]

    # -- reading the catalog -------------------------------------------------------

    def _exists(self, name: str) -> bool:
        try:
            self.project.store.get_table(NAMESPACE, name)
        except NotFound:
            return False
        return True

    def _metadata(self, name: str):
        try:
            location = self.project.store.get_table(NAMESPACE, name)
        except NotFound as e:
            raise NoSuchTable(name) from e
        return self.project.metadata_io.read(location)

    def _info(self, name: str) -> TableInfo:
        md = self._metadata(name)
        snapshot = md.current_snapshot()
        rows, size = self.project.metadata_io.table_stats(md)
        return TableInfo(
            name=name,
            rows=rows,
            bytes=size,
            columns=[(f.name, str(f.field_type)) for f in md.schema().fields],
            location=md.location,
            snapshot_id=snapshot.snapshot_id if snapshot else None,
            freshness=datetime.fromtimestamp(snapshot.timestamp_ms / 1000, tz=UTC)
            if snapshot
            else None,
            source=table_property(md.properties, "querysolo.source-prefix"),
            public=(table_property(md.properties, "querysolo.anonymous") or "").lower() == "true",
            interrupted_replace_of=interrupted_replace_of(name),
        )

    def list(self, views: bool = True) -> list[TableInfo]:
        infos = []
        for name in self.project.store.list_tables(NAMESPACE):
            try:
                infos.append(self._info(name))
            except FileNotFoundError:
                # the metadata is not where the catalog says (T5): listed, marked, so the
                # table is never invisible; `querysolo relocate` makes it resolve again
                infos.append(
                    TableInfo(
                        name=name,
                        rows=0,
                        bytes=0,
                        columns=[],
                        location=self.project.store.get_table(NAMESPACE, name),
                        snapshot_id=None,
                        freshness=None,
                        needs_relocate=True,
                    )
                )
        if views:
            infos += [self._view_info(v) for v in self.project.views.list()]
        return infos

    @staticmethod
    def _view_info(v) -> TableInfo:
        return TableInfo(
            name=v.name,
            rows=0,
            bytes=0,
            columns=[(f.name, str(f.field_type)) for f in v.schema.fields],
            location=v.location,
            snapshot_id=None,
            freshness=datetime.fromtimestamp(v.timestamp_ms / 1000, tz=UTC),
            kind="view",
            view_sql=v.sql,
        )

    def describe(self, name: str) -> TableDescription:
        if name not in self.project.store.list_tables(NAMESPACE):
            from querysolo.views import NoSuchView

            try:
                view = self.project.views.get(name)
            except NoSuchView:
                raise NoSuchTable(name) from None
            info = self._view_info(view)
            return TableDescription(
                **info.__dict__,
                partitioning="a view",
                keep_days=self.project.config.catalog.keep_snapshots_days,
                last_commit={
                    "operation": f"view version {view.version_id}",
                    "timestamp": info.freshness.isoformat() if info.freshness else None,
                },
                snapshots=view.versions,
                format_version=1,
                properties=dict(view.properties),
            )
        md = self._metadata(name)
        info = self._info(name)
        snapshot = md.current_snapshot()
        spec = md.spec()
        partitioning = (
            ", ".join(
                f"{f.name} = {f.transform}({md.schema().find_column_name(f.source_id)})"
                for f in spec.fields
            )
            if spec.fields
            else "unpartitioned"
        )
        expirable = self._expirable(md, self.project.config.catalog.keep_snapshots_days)
        reclaimable = 0
        if expirable:
            kept = self._referenced_files(md, exclude={s.snapshot_id for s in expirable})
            gone = self._referenced_files(md, only={s.snapshot_id for s in expirable})
            reclaimable = sum(size for path, size in gone.items() if path not in kept)
        expirable_ids = {s.snapshot_id for s in expirable}

        def summary_int(snap: Any, key: str) -> int | None:
            value = snap.summary.additional_properties.get(key) if snap.summary else None
            return int(value) if value is not None else None

        affects = self._affects(name)
        snapshot_list = [
            {
                "id": snap.snapshot_id,
                "timestamp": datetime.fromtimestamp(snap.timestamp_ms / 1000, tz=UTC).isoformat(),
                "operation": snap.summary.operation.value if snap.summary else None,
                "added_rows": summary_int(snap, "added-records"),
                "added_bytes": summary_int(snap, "added-files-size"),
                "added_files": summary_int(snap, "added-data-files"),
                "deleted_rows": summary_int(snap, "added-position-deletes"),
                "total_rows": _rows_after(
                    summary_int(snap, "total-records"), summary_int(snap, "total-position-deletes")
                ),
                "current": snapshot is not None and snap.snapshot_id == snapshot.snapshot_id,
                "expirable": snap.snapshot_id in expirable_ids,
                "affects": affects(datetime.fromtimestamp(snap.timestamp_ms / 1000, tz=UTC)),
            }
            for snap in sorted(md.snapshots, key=lambda s: s.timestamp_ms, reverse=True)
        ]
        verified_at: str | None = None
        changed: list[tuple[str, str]] = []
        verify_error: str | None = None
        if info.source:
            from querysolo import register

            try:
                v = register.verify(self.project, name)
                verified_at, changed = v.verified_at, v.changed
            except Exception as e:  # noqa: BLE001 - a listing that fails is a line, not a failure
                verify_error = str(e).splitlines()[0]
        return TableDescription(
            **info.__dict__,
            partitioning=partitioning,
            snapshot_list=snapshot_list,
            verified_at=verified_at,
            changed_files=changed,
            verify_error=verify_error,
            local_copy_files=len(self._local_copy(name, md.location, 0)),
            expirable_snapshots=len(expirable),
            reclaimable_bytes=reclaimable,
            keep_days=self.project.config.catalog.keep_snapshots_days,
            last_commit=(
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "operation": snapshot.summary.operation.value if snapshot.summary else None,
                    "timestamp": datetime.fromtimestamp(
                        snapshot.timestamp_ms / 1000, tz=UTC
                    ).isoformat(),
                }
                if snapshot
                else {}
            ),
            snapshots=len(md.snapshots),
            format_version=md.format_version,
        )

    def sample(self, name: str, n: int = 5, truncate: int | None = None) -> list[dict[str, Any]]:
        if self._exists(name):
            source = f"querysolo.{NAMESPACE}.{_quoted(name)}"
        elif name in self.project.engine.views:
            source = f"memory.{NAMESPACE}.{_quoted(name)}"  # a catalog view, in the session
        else:
            raise NoSuchTable(name)
        cursor = self.project.engine.execute(f"SELECT * FROM {source} LIMIT {int(n)}")
        names = [d[0] for d in cursor.description]
        rows = cursor.fetchall()

        def cut(value: Any) -> Any:
            if truncate and isinstance(value, str) and len(value) > truncate:
                return value[:truncate]
            return value

        return [{col: cut(v) for col, v in zip(names, row, strict=True)} for row in rows]

    # -- remote, read-only (brief D25, D26, D27, M3) ----------------------------------

    def discover(self, prefix: str, anonymous: bool = False):
        from querysolo import register

        return register.discover(self.project, prefix, anonymous=anonymous)

    def preview_remote(self, prefix: str, anonymous: bool = False) -> Preview:
        """The columns of a Parquet prefix before `attach`, in the shape of a file's preview
        so the app's panel shows both; `files`, `bytes` and `remote` say the rest."""
        from querysolo import register

        r = register.inspect(self.project, prefix, anonymous=anonymous)
        columns = [Column(n, arrow, iceberg) for n, arrow, iceberg in r.columns]
        return Preview(
            r.name,
            r.source,
            columns,
            [],
            remote=True,
            files=r.files,
            bytes=r.bytes,
            anonymous=r.anonymous,
        )

    def attach(
        self,
        name: str,
        source: str,
        metadata_in_bucket: bool = False,
        anonymous: bool = False,
        replace: bool = False,
    ) -> TableInfo:
        """A Parquet prefix registered in place, or an existing Iceberg table by its
        metadata location. Nothing is copied. ``anonymous``: a public bucket, no credentials.
        ``replace`` (T2): register again over an existing table in T1's order — the new
        registration is built under the temporary name first, then the old is dropped and
        the new renamed, so a prefix that fails to register leaves the old table as it was."""
        if interrupted_replace_of(name) is not None:
            raise ReservedName(f"{name}: names ending in {REPLACE_SUFFIX} are QuerySolo's own")
        if self._exists(name):
            if not replace:
                raise TableExists(name)
            temp = replace_name(name)
            if self._exists(temp):
                run_with_retry(
                    self.project.engine, f"DROP TABLE querysolo.{NAMESPACE}.{_quoted(temp)}"
                )
            self._attach(temp, source, metadata_in_bucket, anonymous)
            run_with_retry(self.project.engine, f"DROP TABLE querysolo.{NAMESPACE}.{_quoted(name)}")
            return self.rename(temp, name)
        self._attach(name, source, metadata_in_bucket, anonymous)
        self.refresh_agents_md()
        return self._info(name)

    def _attach(self, name: str, source: str, metadata_in_bucket: bool, anonymous: bool) -> None:
        from querysolo import register

        if source.endswith(".metadata.json"):
            if anonymous:
                raise register.NotRegistrable(
                    "--anonymous registers a Parquet prefix; an Iceberg table by its metadata "
                    "location needs credentials for its metadata"
                )
            register.attach_metadata(self.project, name, source)
        else:
            register.attach_prefix(
                self.project,
                name,
                source,
                metadata_in_bucket=metadata_in_bucket,
                anonymous=anonymous,
            )

    # -- expiry (decision 4, September 11, 2026) ---------------------------------------

    def _affects(self, name: str):
        """For the snapshot list (decisions L3): a function of a snapshot's time giving the
        models downstream of this table that the commit made out of date — their last
        successful run is older than it. One graph per describe, from the manifest as it
        is (nothing compiles here; the lineage lines compile when they open)."""
        from querysolo.lineage import Graph

        runs = Graph(self.project, compile_if_stale=False).downstream_runs(name)
        return lambda when: [n for _, n, ts in runs if ts < when]

    @staticmethod
    def _expirable(md, keep_days: int) -> list:
        """Snapshots older than the retention, other than the current one and any a branch
        or tag points at; what `expire` removes."""
        cutoff_ms = (time.time() - keep_days * 86400) * 1000
        protected = {md.current_snapshot_id} | {ref.snapshot_id for ref in md.refs.values()}
        return [
            s for s in md.snapshots if s.snapshot_id not in protected and s.timestamp_ms < cutoff_ms
        ]

    def _referenced_files(self, md, only=None, exclude=None) -> dict[str, int]:
        """Every file the given snapshots reference (manifest lists, manifests, data and
        delete files) with its size; the sweep deletes what the expired ones referenced and
        the kept ones do not."""
        io = self.project.metadata_io.io
        files: dict[str, int] = {}
        for snap in md.snapshots:
            if only is not None and snap.snapshot_id not in only:
                continue
            if exclude is not None and snap.snapshot_id in exclude:
                continue
            if snap.manifest_list:
                try:
                    files[snap.manifest_list] = len(io.new_input(snap.manifest_list))
                except Exception:  # noqa: BLE001 - a missing list is nothing to reclaim
                    files[snap.manifest_list] = 0
            for manifest in snap.manifests(io):
                files[manifest.manifest_path] = manifest.manifest_length
                for entry in manifest.fetch_manifest_entry(io, discard_deleted=False):
                    files[entry.data_file.file_path] = entry.data_file.file_size_in_bytes
        return files

    #: An unreferenced file younger than this is left alone: it may be a write in flight.
    ORPHAN_GRACE_SECONDS = 3600

    def expire(
        self, name: str, keep_days: int | None = None, orphan_grace_seconds: int | None = None
    ) -> ExpireReport:
        """`querysolo tables expire`: drop the snapshots older than the retention through the
        catalog (pyiceberg's `expire_snapshots`), then delete the files that only they
        referenced, and any data or manifest file under the table's own location that no
        remaining snapshot references (a previous `import --replace` leaves those) once it
        is older than the grace period. Only a table QuerySolo wrote into the project's
        warehouse; an attached table is refused."""
        from pyiceberg.catalog.rest import RestCatalog

        from querysolo.register import SOURCE_PROPERTY, table_property

        if keep_days is None:
            keep_days = self.project.config.catalog.keep_snapshots_days
        md = self._metadata(name)
        if table_property(md.properties, SOURCE_PROPERTY) is not None:
            source = table_property(md.properties, SOURCE_PROPERTY)
            raise NotExpirable(f"{name} is registered from {source}; its files are not QuerySolo's")
        # a table QuerySolo wrote is under the warehouse, or in the bucket `tables publish`
        # moved it to (W2); an attached table was refused above
        if not (
            md.location.startswith(self.project.warehouse_url) or md.location.startswith("s3://")
        ):
            raise NotExpirable(f"{name} lives outside the warehouse ({md.location})")
        if self._exists(replace_name(name)):
            raise NotExpirable(
                f"a replace of {name} was interrupted and its new table shares the folder; "
                f"`querysolo tables rename {replace_name(name)} {name}` finishes it first"
            )
        grace = self.ORPHAN_GRACE_SECONDS if orphan_grace_seconds is None else orphan_grace_seconds
        before = len(md.snapshots)
        expirable = self._expirable(md, keep_days)
        was = self._referenced_files(md)
        if expirable:
            catalog = RestCatalog(
                "querysolo", uri=self.project.catalog_url, **self.project.io_properties
            )
            table = catalog.load_table(f"{NAMESPACE}.{name}")
            newest_ms = max(s.timestamp_ms for s in expirable)
            table.maintenance.expire_snapshots().older_than(
                datetime.fromtimestamp((newest_ms + 1) / 1000, tz=UTC)
            ).commit()
        md_after = self._metadata(name)
        kept = self._referenced_files(md_after)
        doomed: dict[str, int] = {p: s for p, s in was.items() if p not in kept}
        doomed.update(self._orphans(md_after.location, kept, grace))
        doomed.update(self._local_copy(name, md_after.location, grace))
        io = self.project.metadata_io.io
        removed = 0
        reclaimed = 0
        for path, size in doomed.items():
            try:
                io.delete(path)
            except FileNotFoundError:
                continue
            removed += 1
            reclaimed += size
        # the manifest cache is keyed by the current snapshot, which expiry never touches
        return ExpireReport(
            name, keep_days, before, before - len(md_after.snapshots), removed, reclaimed
        )

    def _local_copy(self, name: str, location: str, grace_seconds: int) -> dict[str, int]:
        """The files a table published to a bucket (W2) left under the local warehouse,
        older than the grace: nothing in the bucket references them, so `expire` sweeps
        them all; `describe` counts them."""
        if location.startswith("file://") or "://" in self.project.config.project.warehouse:
            return {}
        folder = Path(self.project.warehouse_url.removeprefix("file://")) / NAMESPACE / name
        if not folder.is_dir():
            return {}
        cutoff = time.time() - grace_seconds
        return {
            f"file://{f}": f.stat().st_size
            for f in folder.rglob("*")
            if f.is_file() and f.stat().st_mtime <= cutoff
        }

    @staticmethod
    def _orphans(location: str, kept: dict[str, int], grace_seconds: int) -> dict[str, int]:
        """Data and manifest files under a local table's location that no snapshot
        references and that are older than the grace period; metadata JSON files stay."""
        if not location.startswith("file://"):
            return {}  # a remote warehouse has no listing here; expired files only
        root = Path(location.removeprefix("file://"))
        kept_paths = {Path(p.removeprefix("file://")) for p in kept}
        cutoff = time.time() - grace_seconds
        found: dict[str, int] = {}
        for sub in ("data", "metadata"):
            folder = root / sub
            if not folder.is_dir():
                continue
            for f in folder.rglob("*"):
                if not f.is_file() or f.suffix not in (".parquet", ".avro") or f in kept_paths:
                    continue
                if f.stat().st_mtime > cutoff:
                    continue
                found[f"file://{f}"] = f.stat().st_size
        return found

    def refresh(self, name: str):
        from querysolo import register

        if not self._exists(name):
            raise NoSuchTable(name)
        report = register.refresh(self.project, name)
        self.refresh_agents_md()
        return report

    # -- AGENTS.md -------------------------------------------------------------------

    def _where(self, name: str) -> str:
        """``local``, or the remote prefix the data lives under (D25)."""
        try:
            _, stats = self.project.manifests.get(
                name, self.project.store.get_table(NAMESPACE, name)
            )
        except Exception:  # noqa: BLE001  stats are a nicety here, never a reason to fail
            return "local"
        return "local" if stats.locality == "local" else stats.source

    def refresh_agents_md(self) -> None:
        """Regenerate the tables block between the markers (brief D16); leave the file alone
        if someone removed them."""
        path = self.project.root / "AGENTS.md"
        if not path.exists():
            return
        text = path.read_text(encoding="utf-8")
        if TABLES_START not in text or TABLES_END not in text:
            return
        lines = [
            f"- `{t.name}` (view: `{t.view_sql}`)"
            if t.kind == "view"
            else f"- `{t.name}` ({_human_bytes(t.bytes)}, {t.rows:,} rows, {self._where(t.name)})"
            for t in self.list()
        ] or [
            "No tables yet. `querysolo import <file>` adds one; "
            "this block is regenerated on every import."
        ]
        block = f"{TABLES_START}\n" + "\n".join(lines) + f"\n{TABLES_END}"
        text = re.sub(
            re.escape(TABLES_START) + ".*?" + re.escape(TABLES_END),
            block,
            text,
            count=1,
            flags=re.S,
        )
        path.write_text(text, encoding="utf-8")


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
