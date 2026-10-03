# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Iceberg view metadata (the view spec, format version 1), written and read as JSON by
QuerySolo's own catalog (real-data brief R6). A view is one SQL representation in DuckDB's
dialect and the schema of its result; every replace adds a version and moves
``current-version-id``. pyiceberg has no view writer, so the file is built here, in the
shape the spec gives, which is what Spark's REST client reads."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from pyiceberg.schema import Schema

from querysolo.catalog.commit import MetadataIO

DIALECT = "duckdb"
ENGINE_NAME = "querysolo"


@dataclass
class ViewInfo:
    name: str
    sql: str
    schema: Schema
    location: str
    metadata_location: str
    version_id: int
    timestamp_ms: int
    properties: dict[str, str]
    versions: int


def _version(version_id: int, schema_id: int, sql: str, namespace: str) -> dict[str, Any]:
    return {
        "version-id": version_id,
        "schema-id": schema_id,
        "timestamp-ms": int(time.time() * 1000),
        "summary": {"engine-name": ENGINE_NAME},
        "representations": [{"type": "sql", "sql": sql, "dialect": DIALECT}],
        "default-namespace": [namespace],
    }


def new_view_metadata(
    location: str, namespace: str, sql: str, schema: Schema, properties: dict[str, str]
) -> dict[str, Any]:
    version = _version(1, 0, sql, namespace)
    return {
        "view-uuid": str(uuid.uuid4()),
        "format-version": 1,
        "location": location,
        "schemas": [json.loads(schema.model_dump_json())],
        "current-version-id": 1,
        "versions": [version],
        "version-log": [{"timestamp-ms": version["timestamp-ms"], "version-id": 1}],
        "properties": dict(properties),
    }


def replaced_view_metadata(
    base: dict[str, Any], sql: str, schema: Schema, properties: dict[str, str]
) -> dict[str, Any]:
    """The next version: a new schema when the columns changed, the new representation,
    the log extended; earlier versions stay so the history reads."""
    schemas = list(base["schemas"])
    new_schema = json.loads(schema.model_dump_json())
    schema_id = next(
        (s["schema-id"] for s in schemas if s.get("fields") == new_schema.get("fields")), None
    )
    if schema_id is None:
        schema_id = max(s["schema-id"] for s in schemas) + 1
        new_schema["schema-id"] = schema_id
        schemas.append(new_schema)
    versions = list(base["versions"])
    version_id = max(v["version-id"] for v in versions) + 1
    namespace = versions[-1].get("default-namespace", ["main"])[0]
    version = _version(version_id, schema_id, sql, namespace)
    return {
        **base,
        "schemas": schemas,
        "current-version-id": version_id,
        "versions": versions + [version],
        "version-log": list(base["version-log"])
        + [{"timestamp-ms": version["timestamp-ms"], "version-id": version_id}],
        "properties": {**base.get("properties", {}), **properties},
    }


def view_metadata_location(location: str, version: int) -> str:
    return f"{location}/metadata/{version:05d}-{uuid.uuid4()}.view.metadata.json"


def write_view_metadata(mio: MetadataIO, metadata: dict[str, Any], location: str) -> None:
    with mio.io.new_output(location).create(overwrite=False) as f:
        f.write(json.dumps(metadata, indent=2).encode())


def read_view_metadata(mio: MetadataIO, location: str) -> dict[str, Any]:
    with mio.io.new_input(location).open() as f:
        return json.loads(f.read())


def current_sql(metadata: dict[str, Any]) -> str:
    current = next(
        v for v in metadata["versions"] if v["version-id"] == metadata["current-version-id"]
    )
    return next(r["sql"] for r in current["representations"] if r["type"] == "sql")


def describe_view(name: str, metadata: dict[str, Any], metadata_location: str) -> ViewInfo:
    current = next(
        v for v in metadata["versions"] if v["version-id"] == metadata["current-version-id"]
    )
    schema = next(s for s in metadata["schemas"] if s["schema-id"] == current["schema-id"])
    return ViewInfo(
        name=name,
        sql=current_sql(metadata),
        schema=Schema.model_validate(schema),
        location=metadata["location"],
        metadata_location=metadata_location,
        version_id=current["version-id"],
        timestamp_ms=current["timestamp-ms"],
        properties=dict(metadata.get("properties", {})),
        versions=len(metadata["versions"]),
    )
