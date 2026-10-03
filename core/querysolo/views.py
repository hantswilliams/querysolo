# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Views in QuerySolo's catalog (real-data brief R6): a dbt `view` model, or anything else
that wants a named query, becomes an Iceberg view with one DuckDB SQL representation, kept
as a metadata file under the warehouse and a row in the catalog. DuckDB's Iceberg catalog
cannot hold a view, so the engine is given a DuckDB view of the same name in its own
session (`memory.main`) at every start and after every change here; Spark reads the
same views through the REST catalog."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pyiceberg.catalog import Catalog
from pyiceberg.schema import assign_fresh_schema_ids

from querysolo.catalog import viewmeta
from querysolo.catalog.store import NotFound
from querysolo.project import NAMESPACE

if TYPE_CHECKING:
    from querysolo.project import Project


class NoSuchView(Exception):
    pass


class BadView(Exception):
    """The SQL does not bind against the catalog (DuckDB's message follows)."""


class Views:
    def __init__(self, project: Project) -> None:
        self.project = project

    def list(self) -> list[viewmeta.ViewInfo]:
        return [self.get(name) for name in self.project.store.list_views(NAMESPACE)]

    def get(self, name: str) -> viewmeta.ViewInfo:
        try:
            location = self.project.store.get_view(NAMESPACE, name)
        except NotFound as e:
            raise NoSuchView(name) from e
        return viewmeta.describe_view(
            name, viewmeta.read_view_metadata(self.project.metadata_io, location), location
        )

    def current(self) -> dict[str, str]:
        """``{name: sql}`` for the engine."""
        return {v.name: v.sql for v in self.list()}

    def _schema(self, sql: str):
        import duckdb

        try:
            arrow = self.project.engine.execute(f"SELECT * FROM ({sql}) LIMIT 0").to_arrow_table()
        except duckdb.Error as e:
            raise BadView(str(e).splitlines()[0]) from e
        return assign_fresh_schema_ids(Catalog._convert_schema_if_needed(arrow.schema))

    def put(
        self, name: str, sql: str, properties: dict[str, str] | None = None
    ) -> viewmeta.ViewInfo:
        """Create or replace. The SQL is bound against the catalog first, so a view that
        cannot run is never recorded; its result's columns are the view's schema."""
        if name in self.project.store.list_tables(NAMESPACE):
            raise BadView(f"{name} is a table")
        schema = self._schema(sql)
        mio = self.project.metadata_io
        try:
            current_location = self.project.store.get_view(NAMESPACE, name)
        except NotFound:
            current_location = None
        if current_location is None:
            location = f"{self.project.warehouse_url}/{NAMESPACE}/{name}"
            metadata = viewmeta.new_view_metadata(
                location, NAMESPACE, sql, schema, properties or {}
            )
            version = 0
        else:
            base = viewmeta.read_view_metadata(mio, current_location)
            if viewmeta.current_sql(base) == sql and not properties:
                return self.get(name)  # nothing to change: no new version
            metadata = viewmeta.replaced_view_metadata(base, sql, schema, properties or {})
            location = metadata["location"]
            version = int(current_location.rsplit("/", 1)[1].split("-", 1)[0]) + 1
        new_location = viewmeta.view_metadata_location(location, version)
        viewmeta.write_view_metadata(mio, metadata, new_location)
        self.project.store.put_view(NAMESPACE, name, new_location)
        self.sync_engine()
        self.project.tables.refresh_agents_md()
        return self.get(name)

    def drop(self, name: str) -> None:
        try:
            self.project.store.drop_view(NAMESPACE, name)
        except NotFound as e:
            raise NoSuchView(name) from e
        self.sync_engine()
        self.project.tables.refresh_agents_md()

    def sync_engine(self) -> None:
        """The engine's session gets a DuckDB view per catalog view. A view over a view
        binds only once the first exists, so what fails is tried again after the others;
        what still fails is left out (its `put` would have refused it) and the rest stand."""
        engine = self.project.engine
        pending = self.current()
        for name in set(engine.views) - set(pending):
            engine.drop_view(name)
        for _ in range(len(pending) + 1):
            failed: dict[str, str] = {}
            for name, sql in pending.items():
                try:
                    engine.put_view(name, sql)
                except Exception:  # noqa: BLE001 - DuckDB's binder, tried again below
                    failed[name] = sql
            if not failed or len(failed) == len(pending):
                break
            pending = failed
