# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Remote tables, read-only (brief D25, D26, D27, M3): discover the prefixes in a bucket,
register a Parquet prefix in place as an Iceberg table through the catalog with pyiceberg's
``add_files`` (nothing is copied), register an existing Iceberg table by its metadata
location, and refresh a registered prefix with the files added since.

What registration does not do, by design: files whose schema drifts from the first file are
refused with the file and the column named; hive layouts whose partition column exists only
in the path are refused with the column named; only Parquet is registered."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import pyarrow as pa
import pyarrow.fs as pafs
import pyarrow.parquet as pq
from pyiceberg.catalog.rest import RestCatalog

from querysolo.remote import LEGACY_PREFIX_FOLDER, QUERYSOLO_PREFIX, join_uri, split_uri

if TYPE_CHECKING:
    from querysolo.project import Project

SOURCE_PROPERTY = "querysolo.source-prefix"
PLACEMENT_PROPERTY = "querysolo.metadata-placement"
ANONYMOUS_PROPERTY = "querysolo.anonymous"  # "true": a public bucket read without credentials
#: When the registered files were last checked against the prefix (trust round T2): set by
#: attach, moved forward by every refresh that found nothing changed. A file modified after
#: it, or whose size no longer matches its manifest entry, is "changed under the same path".
VERIFIED_PROPERTY = "querysolo.verified-at"
_HIVE_SEGMENT = re.compile(r"^([A-Za-z_]\w*)=([^/]*)$")
#: Tables written before the rename carry these properties under the old prefix
#: (build-sessions/rename-querysolo-plan.md R4): read, never rewritten.
LEGACY_PREFIX = "lakelet."


def table_property(properties: dict[str, str], name: str) -> str | None:
    """One of QuerySolo's table properties: the current name, else the name a table written
    before the rename carries."""
    value = properties.get(name)
    if value is None and name.startswith("querysolo."):
        value = properties.get(LEGACY_PREFIX + name.removeprefix("querysolo."))
    return value


class NotRegistrable(Exception):
    pass


class SchemaDrift(NotRegistrable):
    pass


class ChangedFiles(Exception):
    """A registered file was rewritten under the same path since the attach (T2): its
    manifest entry — the row count and the column bounds the gauge prunes on — no longer
    describes it. Refresh refuses until the prefix is registered again."""


@dataclass
class Verification:
    """What `verify` found: every registered file compared with the prefix's listing."""

    name: str
    files: int
    #: ``(uri, why)`` for each file that changed: "size 1.2 MB → 3.4 MB" or "rewritten
    #: 2026-09-15T10:00:00+00:00, after the attach".
    changed: list[tuple[str, str]]
    verified_at: str | None

    @property
    def sentence(self) -> str | None:
        if not self.changed:
            return None
        head = ", ".join(f"{uri} ({why})" for uri, why in self.changed[:5])
        more = " …" if len(self.changed) > 5 else ""
        n = len(self.changed)
        return (
            f"{n} registered file(s) changed under the same path since the attach: {head}{more}; "
            f"the table's statistics no longer describe them. "
            f"`querysolo tables attach --replace {self.name} <prefix>` registers the prefix again"
        )


class MissingFiles(Exception):
    pass


@dataclass
class Discovered:
    prefix: str
    kind: str  # parquet | iceberg | other
    files: int
    bytes: int


@dataclass
class RefreshReport:
    name: str
    added: int
    files: int
    rows: int


@dataclass
class _Listing:
    scheme: str
    root: str
    fs: pafs.FileSystem
    files: list[pafs.FileInfo] = field(default_factory=list)

    def uri(self, info: pafs.FileInfo) -> str:
        return join_uri(self.scheme, info.path)


def _list(project: Project, prefix: str, anonymous: bool = False) -> _Listing:
    scheme, root = split_uri(prefix)
    if scheme == "s3" and not anonymous and (problem := project.engine.s3_problem()):
        raise NotRegistrable(problem)
    fs = project.s3.filesystem(scheme, anonymous=anonymous, bucket=root.split("/")[0])
    root = root.rstrip("/")
    selector = pafs.FileSelector(root, recursive=True)
    files = [f for f in fs.get_file_info(selector) if f.type == pafs.FileType.File]
    return _Listing(scheme, root, fs, sorted(files, key=lambda f: f.path))


def discover(project: Project, prefix: str, anonymous: bool = False) -> list[Discovered]:
    """Candidate prefixes directly under ``prefix``, one listing call (M3)."""
    listing = _list(project, prefix, anonymous)
    groups: dict[str, list[pafs.FileInfo]] = {}
    for info in listing.files:
        relative = info.path[len(listing.root) :].lstrip("/")
        head = relative.split("/")[0]
        if head in (QUERYSOLO_PREFIX, LEGACY_PREFIX_FOLDER):
            continue
        groups.setdefault(head, []).append(info)
    out = []
    for head, infos in sorted(groups.items()):
        parquet = [f for f in infos if f.path.endswith(".parquet")]
        iceberg = any("/metadata/" in f.path and f.path.endswith(".metadata.json") for f in infos)
        kind = "iceberg" if iceberg else "parquet" if parquet else "other"
        out.append(
            Discovered(
                prefix=join_uri(listing.scheme, f"{listing.root}/{head}/"),
                kind=kind,
                files=len(parquet) if kind == "parquet" else len(infos),
                bytes=sum(f.size or 0 for f in infos),
            )
        )
    return out


@dataclass
class RemotePreview:
    """What the app shows before `attach` (real-data brief R4): the prefix's files and
    bytes, and the columns of one footer with the Iceberg type each becomes. The drift
    check across every footer is `attach`'s; a preview reads one."""

    name: str
    source: str
    columns: list[tuple[str, str, str]]  # name, Arrow type, Iceberg type
    files: int
    bytes: int
    anonymous: bool


def remote_name(prefix: str) -> str:
    """A table name from a prefix's last segment: ``…/theme=places/type=place/`` gives
    ``place``, ``…/exports/events/`` gives ``events``."""
    from querysolo.project import identifier

    segment = prefix.rstrip("/").split("/")[-1]
    if "=" in segment:
        segment = segment.split("=", 1)[1]
    return identifier(segment)


def iceberg_type_text(t: Any) -> str:
    """An Iceberg type the way a person reads it: ``struct<xmin: double, xmax: double>``,
    ``list<string>``, ``map<string, long>``; pyiceberg's own ``str`` carries the field ids,
    which a schema built from a footer does not have yet (they print as ``-1``)."""
    from pyiceberg.types import ListType, MapType, StructType

    if isinstance(t, StructType):
        inner = ", ".join(f"{f.name}: {iceberg_type_text(f.field_type)}" for f in t.fields)
        return f"struct<{inner}>"
    if isinstance(t, ListType):
        return f"list<{iceberg_type_text(t.element_type)}>"
    if isinstance(t, MapType):
        return f"map<{iceberg_type_text(t.key_type)}, {iceberg_type_text(t.value_type)}>"
    return str(t)


def inspect(project: Project, prefix: str, anonymous: bool = False) -> RemotePreview:
    from pyiceberg.catalog import Catalog

    prefix = prefix if prefix.endswith("/") else prefix + "/"
    listing = _list(project, prefix, anonymous)
    files = _parquet_files(listing)
    if not files:
        raise NotRegistrable(f"no .parquet files under {prefix}")
    arrow = pq.read_schema(files[0].path, filesystem=listing.fs)
    iceberg = Catalog._convert_schema_if_needed(arrow)
    columns = [(f.name, str(arrow.field(f.name).type), str(f.field_type)) for f in iceberg.fields]
    return RemotePreview(
        name=remote_name(prefix),
        source=prefix,
        columns=columns,
        files=len(files),
        bytes=sum(f.size or 0 for f in files),
        anonymous=anonymous,
    )


def _parquet_files(listing: _Listing) -> list[pafs.FileInfo]:
    return [f for f in listing.files if f.path.endswith(".parquet")]


def _check_layout(listing: _Listing, files: list[pafs.FileInfo], schema: pa.Schema) -> None:
    for info in files:
        relative = info.path[len(listing.root) :].lstrip("/")
        for segment in relative.split("/")[:-1]:
            if match := _HIVE_SEGMENT.match(segment):
                column = match[1]
                if column not in schema.names:
                    raise NotRegistrable(
                        f"{relative}: hive partition column {column!r} exists only in the path; "
                        "QuerySolo v0 registers files whose columns are in the files"
                    )


def _check_schemas(listing: _Listing, files: list[pafs.FileInfo]) -> pa.Schema:
    first = pq.read_schema(files[0].path, filesystem=listing.fs)
    for info in files[1:]:
        schema = pq.read_schema(info.path, filesystem=listing.fs)
        if schema.equals(first, check_metadata=False):
            continue
        added = [n for n in schema.names if n not in first.names]
        missing = [n for n in first.names if n not in schema.names]
        changed = [
            n
            for n in first.names
            if n in schema.names and schema.field(n).type != first.field(n).type
        ]
        detail = ", ".join(
            part
            for part in (
                f"adds {added}" if added else "",
                f"lacks {missing}" if missing else "",
                f"changes the type of {changed}" if changed else "",
            )
            if part
        )
        raise SchemaDrift(
            f"{info.path[len(listing.root) :].lstrip('/')}: schema differs from "
            f"{files[0].path[len(listing.root) :].lstrip('/')} ({detail}); every file in a "
            "registered prefix must share one schema"
        )
    return first.remove_metadata()


def _client(project: Project, anonymous: bool = False, bucket: str | None = None) -> RestCatalog:
    props = dict(project.io_properties)
    if anonymous:
        # pyiceberg reads the Parquet footers and, later, the data files of this table
        # through its own S3 client; unsigned, like the listing (real-data brief R3).
        props = {k: v for k, v in props.items() if not k.startswith("s3.access")}
        props = {k: v for k, v in props.items() if not k.startswith("s3.secret")}
        props["s3.anonymous"] = "true"
        if bucket:
            props["s3.region"] = project.s3.bucket_region(bucket)
    return RestCatalog("querysolo", uri=project.catalog_url, **props)


def _metadata_root(project: Project, name: str, prefix: str, in_bucket: bool) -> str:
    from querysolo.catalog.store import LEGACY_REPLACE_SUFFIX, REPLACE_SUFFIX

    name = name.removesuffix(REPLACE_SUFFIX).removesuffix(
        LEGACY_REPLACE_SUFFIX
    )  # a replace's temporary shares the final folder
    if in_bucket:
        scheme, path = split_uri(prefix)
        bucket = path.split("/")[0]
        return join_uri(scheme, f"{bucket}/{QUERYSOLO_PREFIX}/{name}")
    return f"{project.warehouse_url}/main/{name}"


def attach_prefix(
    project: Project,
    name: str,
    prefix: str,
    metadata_in_bucket: bool = False,
    anonymous: bool = False,
) -> tuple[int, int]:
    """Register the Parquet files under ``prefix`` in place. Returns (files, rows).
    ``anonymous`` reads a public bucket without credentials; the metadata then stays local
    (there is nothing to write with) and the engine gets a scoped secret for the bucket."""
    prefix = prefix if prefix.endswith("/") else prefix + "/"
    if anonymous and metadata_in_bucket:
        raise NotRegistrable("a public bucket is read-only: the metadata cannot go in it")
    listing = _list(project, prefix, anonymous)
    files = _parquet_files(listing)
    if not files:
        raise NotRegistrable(f"no .parquet files under {prefix}")
    schema = _check_schemas(listing, files)
    _check_layout(listing, files, schema)
    bucket = split_uri(prefix)[1].split("/")[0]
    if anonymous:
        project.allow_public_bucket(bucket)
    catalog = _client(project, anonymous, bucket)
    properties = {
        SOURCE_PROPERTY: prefix,
        PLACEMENT_PROPERTY: "bucket" if metadata_in_bucket else "local",
        VERIFIED_PROPERTY: _now(),
    }
    if anonymous:
        properties[ANONYMOUS_PROPERTY] = "true"
    table = catalog.create_table(
        f"main.{name}",
        schema=schema,
        location=_metadata_root(project, name, prefix, metadata_in_bucket),
        properties=properties,
    )
    table.add_files([listing.uri(f) for f in files])
    rows = sum(t.file.record_count for t in catalog.load_table(f"main.{name}").scan().plan_files())
    _probe_bandwidth(project, listing, files)
    return len(files), rows


def attach_metadata(project: Project, name: str, metadata_location: str) -> None:
    """Register an existing Iceberg table by its metadata location (the primitive)."""
    if metadata_location.startswith("s3://") and (problem := project.engine.s3_problem()):
        raise NotRegistrable(problem)
    _client(project).register_table(f"main.{name}", metadata_location)


def is_anonymous(properties: dict[str, str]) -> bool:
    return (table_property(properties, ANONYMOUS_PROPERTY) or "").lower() == "true"


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


#: A file whose modification time is this much after the last verification counts as
#: rewritten: the two seconds absorb S3's second-resolution LastModified and a store clock a
#: little ahead of this machine's, so a file uploaded just before the attach is not flagged.
REWRITE_GRACE_SECONDS = 2


def _registered(project: Project, name: str):
    """The table, its catalog client, its prefix and the listing of that prefix."""
    catalog = _client(project)
    table = catalog.load_table(f"main.{name}")
    anonymous = is_anonymous(table.properties)
    prefix = table_property(table.properties, SOURCE_PROPERTY)
    if not prefix:
        raise NotRegistrable(f"{name} was not registered from a prefix; nothing to refresh")
    if anonymous:
        catalog = _client(project, anonymous=True, bucket=split_uri(prefix)[1].split("/")[0])
        table = catalog.load_table(f"main.{name}")
    return catalog, table, prefix, _list(project, prefix, anonymous)


def _compare(table, listing: _Listing, files: list[pafs.FileInfo]) -> Verification:
    """Every registered file against the listing (T2). A size that no longer matches the
    manifest's ``file_size_in_bytes`` is a rewrite for certain; a modification time after
    the last verification is a rewrite too, even at the same size — pyarrow's listing
    carries no ETag, so a byte-identical re-upload is reported as changed rather than let
    a same-size, different-content one through. The sentence names which."""
    from datetime import UTC, datetime, timedelta

    by_uri = {listing.uri(f): f for f in files}
    verified_at = table_property(table.properties, VERIFIED_PROPERTY)
    since = (
        datetime.fromisoformat(verified_at) + timedelta(seconds=REWRITE_GRACE_SECONDS)
        if verified_at
        else None
    )
    changed: list[tuple[str, str]] = []
    known = 0
    for task in table.scan().plan_files():
        known += 1
        info = by_uri.get(task.file.file_path)
        if info is None:
            continue  # gone: refresh raises MissingFiles for those (D27)
        if info.size is not None and info.size != task.file.file_size_in_bytes:
            changed.append(
                (
                    task.file.file_path,
                    f"size {_human(task.file.file_size_in_bytes)} → {_human(info.size)}",
                )
            )
        elif since is not None and info.mtime is not None:
            mtime = info.mtime if info.mtime.tzinfo else info.mtime.replace(tzinfo=UTC)
            if mtime > since:
                changed.append(
                    (
                        task.file.file_path,
                        f"rewritten {mtime.isoformat(timespec='seconds')}, after the attach",
                    )
                )
    return Verification(table.name()[-1], known, changed, verified_at)


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def verify(project: Project, name: str) -> Verification:
    """`describe` and the table detail: are the registered files still what was attached?"""
    _, table, _, listing = _registered(project, name)
    return _compare(table, listing, _parquet_files(listing))


def refresh(project: Project, name: str) -> RefreshReport:
    """Add the files new since registration; fail loudly if a registered file is gone (D27)
    or was rewritten under the same path (T2)."""
    catalog, table, prefix, listing = _registered(project, name)
    files = _parquet_files(listing)
    known = {t.file.file_path for t in table.scan().plan_files()}
    present = {listing.uri(f) for f in files}
    gone = sorted(known - present)
    if gone:
        raise MissingFiles(
            f"{len(gone)} registered file(s) are no longer under {prefix}: "
            + ", ".join(gone[:5])
            + (" …" if len(gone) > 5 else "")
        )
    verification = _compare(table, listing, files)
    if verification.changed:
        raise ChangedFiles(verification.sentence)
    new = [f for f in files if listing.uri(f) not in known]
    if new:
        _check_schemas(listing, [files[0], *new])
        table.add_files([listing.uri(f) for f in new])
        table = catalog.load_table(f"main.{name}")
    # everything registered is as it was at this moment: the stamp moves forward
    with table.transaction() as tx:
        tx.set_properties({VERIFIED_PROPERTY: _now()})
    table = catalog.load_table(f"main.{name}")
    rows = sum(t.file.record_count for t in table.scan().plan_files())
    return RefreshReport(name=name, added=len(new), files=len(files), rows=rows)


def _probe_bandwidth(project: Project, listing: _Listing, files: list[pafs.FileInfo]) -> None:
    """Brief D36: a timed ranged read of up to 64 MB from the largest data file, in the
    user's own bucket, cached for an hour. Skipped for local prefixes."""
    from querysolo.gauge import inputs

    if listing.scheme == "file":
        return
    cache = inputs.load_machine_cache(project.cache_dir)
    if time.time() - cache.get("bandwidth_probed_at", 0) < 3600:
        return
    largest = max(files, key=lambda f: f.size or 0)
    size = min(largest.size or 0, 64 * 2**20)
    if size <= 0:
        return
    started = time.perf_counter()
    with listing.fs.open_input_file(largest.path) as f:
        f.read(size)
    elapsed = max(time.perf_counter() - started, 1e-4)
    cache.update({"bandwidth_mbps": size * 8 / 1e6 / elapsed, "bandwidth_probed_at": time.time()})
    inputs.save_machine_cache(project.cache_dir, cache)
