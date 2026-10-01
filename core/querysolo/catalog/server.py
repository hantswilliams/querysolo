# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The Iceberg REST catalog's routes (brief D4, D6, D22). Paths and JSON shapes follow the
spec; request and response bodies are pyiceberg's own models where it has them.

Namespaces are single level in v0 (brief D36); a multi-level name is a 400, not a misparse.
No token on ``/v1`` in local mode (brief D22).

What the two clients actually do, learned in step 1: pyiceberg creates tables in one
request; DuckDB stages the create, writes its data files, then commits through the
single-table commit endpoint with an ``assert-create`` requirement, and expects the
table's ``data/`` directory to exist on a local warehouse.
"""

from __future__ import annotations

import errno
import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pyiceberg.catalog.rest import (
    CommitTableResponse,
    ConfigResponse,
    ListNamespaceResponse,
    ListTableResponseEntry,
    ListTablesResponse,
    NamespaceResponse,
    RegisterTableRequest,
    TableIdentifier,
    TableResponse,
)
from pyiceberg.exceptions import CommitFailedException
from pyiceberg.partitioning import PartitionSpec
from pyiceberg.schema import Schema
from pyiceberg.table.sorting import SortOrder
from pyiceberg.table.update import TableRequirement, TableUpdate
from pyiceberg.typedef import IcebergBaseModel

from querysolo.catalog import commit as ic
from querysolo.catalog import viewmeta
from querysolo.catalog.store import (
    LEGACY_REPLACE_SUFFIX,
    REPLACE_SUFFIX,
    AlreadyExists,
    Conflict,
    NotFound,
    Store,
)

PREFIX = "querysolo"
NAMESPACE_SEPARATOR = "\x1f"


class BadRequest(Exception):
    pass


class CreateTableBody(IcebergBaseModel):
    """The spec's CreateTableRequest with the optional fields optional; pyiceberg's own
    model requires ``location`` although its client omits it."""

    name: str
    location: str | None = None
    table_schema: Schema = Field(alias="schema")
    partition_spec: PartitionSpec | None = Field(default=None, alias="partition-spec")
    write_order: SortOrder | None = Field(default=None, alias="write-order")
    stage_create: bool = Field(default=False, alias="stage-create")
    properties: dict[str, str] = Field(default_factory=dict)


class CommitTableBody(IcebergBaseModel):
    """The spec's CommitTableRequest with ``identifier`` optional, as the spec says and as
    the Java client (Spark, Trino) sends it on the per-table endpoint."""

    identifier: TableIdentifier | None = None
    requirements: tuple[TableRequirement, ...] = ()
    updates: tuple[TableUpdate, ...] = ()


class CreateNamespaceRequest(BaseModel):
    namespace: list[str]
    properties: dict[str, str] = Field(default_factory=dict)


class RenameTableRequest(BaseModel):
    source: TableIdentifier
    destination: TableIdentifier


class CommitTransactionRequest(BaseModel):
    table_changes: list[CommitTableBody] = Field(alias="table-changes")


def _error(status: int, kind: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"error": {"message": message, "type": kind, "code": status}}
    )


def _json(model: Any, status: int = 200) -> Response:
    return Response(
        content=model.model_dump_json(), media_type="application/json", status_code=status
    )


def _namespace(encoded: str) -> str:
    parts = encoded.split(NAMESPACE_SEPARATOR)
    if len(parts) != 1 or not parts[0]:
        raise BadRequest("QuerySolo namespaces are single level in v0")
    return parts[0]


def _identifier_namespace(identifier: TableIdentifier) -> str:
    """pyiceberg's TableIdentifier wraps the namespace in a root model."""
    parts = identifier.namespace.root
    return _namespace(NAMESPACE_SEPARATOR.join(parts))


def _ensure_local_layout(location: str) -> None:
    """DuckDB writes data files under ``<location>/data`` and does not create the directory;
    on a local warehouse the catalog owns the layout, so it makes both directories."""
    if location.startswith("file://"):
        path = location.removeprefix("file://")
    elif "://" not in location:
        path = location
    else:
        return
    for sub in ("data", "metadata"):
        os.makedirs(os.path.join(path, sub), exist_ok=True)


#: The hosts a request may name (trust round T6). The server binds loopback only (D22);
#: this is the second half: a page on a domain re-pointed at 127.0.0.1 after it loaded (DNS
#: rebinding) reaches the socket with its own domain in ``Host``, and is refused here.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "[::1]"})


def _host_name(host: str) -> str:
    """The name in a ``Host`` header, without the port: ``[::1]:8181`` → ``[::1]``."""
    if host.startswith("["):
        return host.split("]", 1)[0] + "]"
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


def refused(
    method: str, path: str, headers: dict[str, str], api_origins: frozenset[str]
) -> str | None:
    """Why a request is not one an engine or the app would send (T6), or None.

    Three refusals close what a browser page can do to a loopback server that carries no
    token on ``/v1``: a ``Host`` that is not loopback (DNS rebinding); an ``Origin`` header
    at all on ``/v1`` (no engine sends one, every browser does) or one the app's CORS does
    not allow on ``/api``; and a body that is not JSON (the ``text/plain`` and form posts a
    page can send without a preflight). None of the four engines is affected: their
    requests name loopback, carry no ``Origin``, and post JSON."""
    host = _host_name(headers.get("host", ""))
    if host not in LOOPBACK_HOSTS:
        return f"Host {host or '(none)'} is not loopback; this server answers 127.0.0.1 only"
    origin = headers.get("origin")
    if origin is not None and (not path.startswith("/api") or origin not in api_origins):
        return f"requests with Origin {origin} are not accepted on {path}"
    if method in ("POST", "PUT", "PATCH") and headers.get("content-length", "0") not in ("", "0"):
        content_type = headers.get("content-type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return f"a body must be application/json, not {content_type or '(none)'}"
    return None


class LoopbackOnly:
    """The refusals as a plain ASGI middleware. Not Starlette's ``BaseHTTPMiddleware``: that
    wraps every response in a streaming shim that breaks the query route's handling of a
    client that goes away mid-stream (the app's Esc), which the interrupt test caught."""

    def __init__(self, app, api_origins: frozenset[str]) -> None:
        self.app = app
        self.api_origins = api_origins

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope["headers"]}
        why = refused(scope["method"], scope["path"], headers, self.api_origins)
        if why is None:
            await self.app(scope, receive, send)
            return
        response = _error(403, "Forbidden", why)
        await response(scope, receive, send)


def create_app(
    store: Store,
    warehouse: str,
    io_properties: dict[str, str] | None = None,
    cache_dir: Path | None = None,
    api_origins: list[str] | None = None,
) -> FastAPI:
    app = FastAPI(title="QuerySolo Iceberg REST catalog", docs_url=None, redoc_url=None)
    mio = ic.MetadataIO(io_properties or {}, cache_dir=cache_dir)
    warehouse = warehouse.rstrip("/")
    app.add_middleware(LoopbackOnly, api_origins=frozenset(api_origins or ()))

    @app.exception_handler(NotFound)
    async def _not_found(_: Request, e: NotFound) -> JSONResponse:
        return _error(404, "NoSuchTableException", str(e))

    @app.exception_handler(AlreadyExists)
    async def _exists(_: Request, e: AlreadyExists) -> JSONResponse:
        return _error(409, "AlreadyExistsException", str(e))

    @app.exception_handler(Conflict)
    async def _conflict(_: Request, e: Conflict) -> JSONResponse:
        return _error(409, "CommitFailedException", str(e))

    @app.exception_handler(OSError)
    async def _os_error(_: Request, e: OSError) -> JSONResponse:
        # A disk that is full or a folder that cannot be written (trust round T4): the
        # commit fails before the catalog changes, and the sentence names the cause rather
        # than a bare 500. 507 is "insufficient storage"; the engines report the status.
        status = 507 if e.errno == errno.ENOSPC else 500
        return _error(status, type(e).__name__, f"{e.strerror or e}: the catalog was not changed")

    @app.exception_handler(CommitFailedException)
    async def _commit_failed(_: Request, e: CommitFailedException) -> JSONResponse:
        return _error(409, "CommitFailedException", str(e))

    @app.exception_handler(BadRequest)
    async def _bad_request(_: Request, e: BadRequest) -> JSONResponse:
        return _error(400, "BadRequestException", str(e))

    @app.get("/v1/config")
    def config(warehouse: str | None = None) -> Response:  # noqa: ARG001  the client's hint
        return _json(ConfigResponse(defaults={}, overrides={"prefix": PREFIX}))

    # -- namespaces -----------------------------------------------------------------

    @app.get("/v1/{prefix}/namespaces")
    def list_namespaces(prefix: str) -> Response:
        return _json(ListNamespaceResponse(namespaces=[(n,) for n in store.list_namespaces()]))

    @app.post("/v1/{prefix}/namespaces")
    def create_namespace(prefix: str, body: CreateNamespaceRequest) -> Response:
        name = _namespace(NAMESPACE_SEPARATOR.join(body.namespace))
        store.create_namespace(name, body.properties)
        return _json(NamespaceResponse(namespace=(name,), properties=body.properties))

    @app.get("/v1/{prefix}/namespaces/{ns}")
    def get_namespace(prefix: str, ns: str) -> Response:
        name = _namespace(ns)
        return _json(NamespaceResponse(namespace=(name,), properties=store.get_namespace(name)))

    @app.head("/v1/{prefix}/namespaces/{ns}")
    def head_namespace(prefix: str, ns: str) -> Response:
        store.get_namespace(_namespace(ns))
        return Response(status_code=204)

    @app.delete("/v1/{prefix}/namespaces/{ns}")
    def drop_namespace(prefix: str, ns: str) -> Response:
        store.drop_namespace(_namespace(ns))
        return Response(status_code=204)

    # -- tables ---------------------------------------------------------------------

    def _load(ns: str, table: str) -> TableResponse:
        location = store.get_table(ns, table)
        return TableResponse(metadata_location=location, metadata=mio.read(location), config={})

    @app.get("/v1/{prefix}/namespaces/{ns}/tables")
    def list_tables(prefix: str, ns: str) -> Response:
        name = _namespace(ns)
        entries = [
            ListTableResponseEntry(namespace=(name,), name=t) for t in store.list_tables(name)
        ]
        return _json(ListTablesResponse(identifiers=entries))

    @app.post("/v1/{prefix}/namespaces/{ns}/tables")
    def create_table(prefix: str, ns: str, body: CreateTableBody) -> Response:
        name = _namespace(ns)
        store.get_namespace(name)
        # A replace's temporary table shares the final name's folder (T1): the swap renames
        # the catalog entry and moves no data; the old files become orphans `expire` sweeps.
        folder = body.name.removesuffix(REPLACE_SUFFIX).removesuffix(LEGACY_REPLACE_SUFFIX)
        location = (body.location or f"{warehouse}/{name}/{folder}").rstrip("/")
        table_metadata = ic.create_metadata(
            body.table_schema, location, body.partition_spec, body.write_order, body.properties
        )
        _ensure_local_layout(location)
        if body.stage_create:
            return _json(TableResponse(metadata_location=None, metadata=table_metadata, config={}))
        metadata_location = ic.metadata_location(location, 0)
        mio.write(table_metadata, metadata_location)
        store.create_table(name, body.name, metadata_location)
        return _json(
            TableResponse(metadata_location=metadata_location, metadata=table_metadata, config={})
        )

    @app.post("/v1/{prefix}/namespaces/{ns}/register")
    def register_table(prefix: str, ns: str, body: RegisterTableRequest) -> Response:
        name = _namespace(ns)
        table_metadata = mio.read(body.metadata_location)
        store.create_table(name, body.name, body.metadata_location)
        return _json(
            TableResponse(
                metadata_location=body.metadata_location, metadata=table_metadata, config={}
            )
        )

    @app.get("/v1/{prefix}/namespaces/{ns}/tables/{table}")
    def load_table(prefix: str, ns: str, table: str) -> Response:
        return _json(_load(_namespace(ns), table))

    @app.head("/v1/{prefix}/namespaces/{ns}/tables/{table}")
    def head_table(prefix: str, ns: str, table: str) -> Response:
        store.get_table(_namespace(ns), table)
        return Response(status_code=204)

    def _commit(ns: str, table: str, body: CommitTableBody) -> CommitTableResponse:
        current_location = store.get_table(ns, table)
        base = mio.read(current_location)
        new_metadata = ic.apply_commit(base, current_location, body.requirements, body.updates)
        new_location = ic.metadata_location(
            new_metadata.location, ic.parse_version(current_location) + 1
        )
        mio.write(new_metadata, new_location)
        store.update_table(ns, table, expected=current_location, new=new_location)
        return CommitTableResponse(metadata_location=new_location, metadata=new_metadata)

    def _commit_create(ns: str, table: str, body: CommitTableBody) -> CommitTableResponse:
        """The second half of a staged create."""
        new_metadata = ic.apply_commit(None, None, body.requirements, body.updates)
        _ensure_local_layout(new_metadata.location)
        new_location = ic.metadata_location(new_metadata.location, 0)
        mio.write(new_metadata, new_location)
        store.create_table(ns, table, new_location)
        return CommitTableResponse(metadata_location=new_location, metadata=new_metadata)

    @app.post("/v1/{prefix}/namespaces/{ns}/tables/{table}")
    def commit_table(prefix: str, ns: str, table: str, body: CommitTableBody) -> Response:
        name = _namespace(ns)
        try:
            store.get_table(name, table)
        except NotFound:
            if any(r.type == "assert-create" for r in body.requirements):
                return _json(_commit_create(name, table, body))
            raise
        return _json(_commit(name, table, body))

    @app.post("/v1/{prefix}/transactions/commit")
    def commit_transaction(prefix: str, body: CommitTransactionRequest) -> Response:
        for change in body.table_changes:
            if change.identifier is None:
                raise BadRequest("every table change in a transaction needs an identifier")
            ns = _identifier_namespace(change.identifier)
            try:
                store.get_table(ns, change.identifier.name)
            except NotFound:
                _commit_create(ns, change.identifier.name, change)
            else:
                _commit(ns, change.identifier.name, change)
        return Response(status_code=204)

    @app.delete("/v1/{prefix}/namespaces/{ns}/tables/{table}")
    def drop_table(
        prefix: str,
        ns: str,
        table: str,
        purgeRequested: bool = False,  # noqa: N803
    ) -> Response:
        store.drop_table(_namespace(ns), table)
        return Response(status_code=204)

    # -- views (real-data brief R6): the REST view routes, the view spec's JSON --------------

    @app.get("/v1/{prefix}/namespaces/{ns}/views")
    def list_views(prefix: str, ns: str) -> JSONResponse:
        name = _namespace(ns)
        return JSONResponse(
            {"identifiers": [{"namespace": [name], "name": v} for v in store.list_views(name)]}
        )

    def _view(ns: str, view: str) -> JSONResponse:
        location = store.get_view(ns, view)
        return JSONResponse(
            {
                "metadata-location": location,
                "metadata": viewmeta.read_view_metadata(mio, location),
                "config": {},
            }
        )

    @app.get("/v1/{prefix}/namespaces/{ns}/views/{view}")
    def load_view(prefix: str, ns: str, view: str) -> JSONResponse:
        return _view(_namespace(ns), view)

    @app.head("/v1/{prefix}/namespaces/{ns}/views/{view}")
    def head_view(prefix: str, ns: str, view: str) -> Response:
        store.get_view(_namespace(ns), view)
        return Response(status_code=204)

    @app.post("/v1/{prefix}/namespaces/{ns}/views")
    async def create_view(prefix: str, ns: str, request: Request) -> JSONResponse:
        """A client's create: the schema and the first version come in the body; the
        location is the warehouse's unless given."""
        name = _namespace(ns)
        store.get_namespace(name)
        body = await request.json()
        view = body["name"]
        if view in store.list_views(name):
            raise AlreadyExists(f"view {name}.{view}")
        location = (body.get("location") or f"{warehouse}/{name}/{view}").rstrip("/")
        version = dict(body["view-version"])
        version["version-id"] = 1
        version.setdefault("timestamp-ms", int(time.time() * 1000))
        metadata = {
            "view-uuid": str(uuid.uuid4()),
            "format-version": 1,
            "location": location,
            "schemas": [{**body["schema"], "schema-id": version.get("schema-id", 0)}],
            "current-version-id": 1,
            "versions": [version],
            "version-log": [{"timestamp-ms": version["timestamp-ms"], "version-id": 1}],
            "properties": dict(body.get("properties") or {}),
        }
        _ensure_local_layout(location)
        metadata_location = viewmeta.view_metadata_location(location, 0)
        viewmeta.write_view_metadata(mio, metadata, metadata_location)
        store.put_view(name, view, metadata_location)
        return _view(name, view)

    @app.post("/v1/{prefix}/namespaces/{ns}/views/{view}")
    async def commit_view(prefix: str, ns: str, view: str, request: Request) -> JSONResponse:
        """A replace: `add-schema`, `add-view-version` and `set-current-view-version`
        applied to the current metadata; other updates are set-properties or ignored."""
        name = _namespace(ns)
        current_location = store.get_view(name, view)
        base = viewmeta.read_view_metadata(mio, current_location)
        body = await request.json()
        metadata = {**base, "schemas": list(base["schemas"]), "versions": list(base["versions"])}
        metadata["version-log"] = list(base["version-log"])
        metadata["properties"] = dict(base.get("properties", {}))
        last_schema = max(s["schema-id"] for s in metadata["schemas"])
        last_version = max(v["version-id"] for v in metadata["versions"])
        for update in body.get("updates", []):
            action = update.get("action")
            if action == "add-schema":
                schema = dict(update["schema"])
                if schema.get("schema-id", -1) < 0 or schema.get("schema-id") == last_schema:
                    last_schema += 1
                    schema["schema-id"] = last_schema
                metadata["schemas"].append(schema)
            elif action == "add-view-version":
                version = dict(update["view-version"])
                last_version += 1
                version["version-id"] = last_version
                if version.get("schema-id", -1) < 0:
                    version["schema-id"] = last_schema
                version.setdefault("timestamp-ms", int(time.time() * 1000))
                metadata["versions"].append(version)
            elif action == "set-current-view-version":
                wanted = update.get("view-version-id", -1)
                target = last_version if wanted == -1 else wanted
                metadata["current-version-id"] = target
                stamp = next(
                    v["timestamp-ms"] for v in metadata["versions"] if v["version-id"] == target
                )
                metadata["version-log"].append({"timestamp-ms": stamp, "version-id": target})
            elif action == "set-properties":
                metadata["properties"].update(update.get("updates", {}))
            elif action == "remove-properties":
                for key in update.get("removals", []):
                    metadata["properties"].pop(key, None)
        new_location = viewmeta.view_metadata_location(
            metadata["location"], int(current_location.rsplit("/", 1)[1].split("-", 1)[0]) + 1
        )
        viewmeta.write_view_metadata(mio, metadata, new_location)
        store.put_view(name, view, new_location)
        return _view(name, view)

    @app.delete("/v1/{prefix}/namespaces/{ns}/views/{view}")
    def drop_view(prefix: str, ns: str, view: str) -> Response:
        store.drop_view(_namespace(ns), view)
        return Response(status_code=204)

    @app.post("/v1/{prefix}/tables/rename")
    def rename_table(prefix: str, body: RenameTableRequest) -> Response:
        store.rename_table(
            _identifier_namespace(body.source),
            body.source.name,
            _identifier_namespace(body.destination),
            body.destination.name,
        )
        return Response(status_code=204)

    @app.post("/v1/{prefix}/namespaces/{ns}/tables/{table}/metrics")
    def report_metrics(prefix: str, ns: str, table: str) -> Response:
        return Response(status_code=204)

    return app
