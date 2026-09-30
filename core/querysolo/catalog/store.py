# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Catalog state on SQLAlchemy Core: namespaces, tables, meta. SQLite now, Postgres when
the team catalog ships; one schema for both (brief D5).

Concurrency is the compare-and-swap in ``update_table``: the row moves from the expected
metadata location to the new one only if nobody moved it first. SQLite serialises writers,
so that update is atomic; a rowcount of zero is a conflict and the caller answers 409.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

SCHEMA_VERSION = 1
#: Numbered migrations from an older schema (trust round T4): ``(target_version, fn)``,
#: run in order on open. None yet.
MIGRATIONS: list = []

#: `import --replace` builds the new table under `<name>` + this suffix first, then drops the
#: old one and renames (trust round T1). The catalog gives such a table the *final* name's
#: location, so the swap never moves data; a user's table may not end in it.
REPLACE_SUFFIX = "__querysolo_replace"
#: The same suffix before the rename (rename plan R4); recovery still recognises it.
LEGACY_REPLACE_SUFFIX = "__lakelet_replace"

metadata = sa.MetaData()

namespaces = sa.Table(
    "namespaces",
    metadata,
    sa.Column("name", sa.String(255), primary_key=True),
    sa.Column("properties", sa.Text, nullable=False),
)

tables = sa.Table(
    "tables",
    metadata,
    sa.Column("namespace", sa.String(255), sa.ForeignKey("namespaces.name"), primary_key=True),
    sa.Column("name", sa.String(255), primary_key=True),
    sa.Column("metadata_location", sa.Text, nullable=False),
    sa.Column("previous_metadata_location", sa.Text),
    sa.Column("leased_until", sa.DateTime(timezone=True)),  # the catalog lease, session 8
    sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
)

views = sa.Table(
    "views",
    metadata,
    sa.Column("namespace", sa.String(255), sa.ForeignKey("namespaces.name"), primary_key=True),
    sa.Column("name", sa.String(255), primary_key=True),
    sa.Column("metadata_location", sa.Text, nullable=False),
    sa.Column("created", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
)

meta = sa.Table(
    "meta",
    metadata,
    sa.Column("key", sa.String(64), primary_key=True),
    sa.Column("value", sa.Text, nullable=False),
)


class NotFound(Exception):
    pass


class AlreadyExists(Exception):
    pass


class Conflict(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


class Store:
    def __init__(self, url: str) -> None:
        is_sqlite = url.startswith("sqlite")
        connect_args = {"check_same_thread": False, "timeout": 5} if is_sqlite else {}
        self.engine = sa.create_engine(url, connect_args=connect_args)
        if is_sqlite:

            @event.listens_for(self.engine, "connect")
            def _pragmas(dbapi_conn, _record) -> None:
                dbapi_conn.execute("PRAGMA journal_mode=WAL")
                dbapi_conn.execute("PRAGMA busy_timeout=5000")
                dbapi_conn.execute("PRAGMA foreign_keys=ON")

        metadata.create_all(self.engine)
        from querysolo.schema import ensure_schema

        try:
            ensure_schema(self.engine, meta, SCHEMA_VERSION, MIGRATIONS, "catalog")
        except Exception:
            self.engine.dispose()
            raise

    def close(self) -> None:
        """Release the pooled connections; on SQLite each holds the db and its -wal file."""
        self.engine.dispose()

    # -- namespaces -----------------------------------------------------------------

    def list_namespaces(self) -> list[str]:
        with self.engine.connect() as c:
            return list(
                c.execute(sa.select(namespaces.c.name).order_by(namespaces.c.name)).scalars()
            )

    def create_namespace(self, name: str, properties: dict[str, str]) -> None:
        try:
            with self.engine.begin() as c:
                c.execute(namespaces.insert().values(name=name, properties=json.dumps(properties)))
        except IntegrityError as e:
            raise AlreadyExists(name) from e

    def get_namespace(self, name: str) -> dict[str, str]:
        with self.engine.connect() as c:
            row = c.execute(
                sa.select(namespaces.c.properties).where(namespaces.c.name == name)
            ).scalar()
        if row is None:
            raise NotFound(name)
        return json.loads(row)

    def drop_namespace(self, name: str) -> None:
        with self.engine.begin() as c:
            if c.execute(sa.select(sa.func.count()).where(tables.c.namespace == name)).scalar():
                raise Conflict(f"namespace {name} is not empty")
            if not c.execute(namespaces.delete().where(namespaces.c.name == name)).rowcount:
                raise NotFound(name)

    # -- tables ---------------------------------------------------------------------

    def list_tables(self, namespace: str) -> list[str]:
        self.get_namespace(namespace)
        with self.engine.connect() as c:
            return list(
                c.execute(
                    sa.select(tables.c.name)
                    .where(tables.c.namespace == namespace)
                    .order_by(tables.c.name)
                ).scalars()
            )

    def get_table(self, namespace: str, name: str) -> str:
        """The table's current metadata location."""
        with self.engine.connect() as c:
            row = c.execute(
                sa.select(tables.c.metadata_location).where(
                    tables.c.namespace == namespace, tables.c.name == name
                )
            ).scalar()
        if row is None:
            raise NotFound(f"{namespace}.{name}")
        return row

    def create_table(self, namespace: str, name: str, metadata_location: str) -> None:
        self.get_namespace(namespace)
        now = _now()
        try:
            with self.engine.begin() as c:
                c.execute(
                    tables.insert().values(
                        namespace=namespace,
                        name=name,
                        metadata_location=metadata_location,
                        created=now,
                        updated=now,
                    )
                )
        except IntegrityError as e:
            raise AlreadyExists(f"{namespace}.{name}") from e

    def update_table(self, namespace: str, name: str, expected: str, new: str) -> None:
        """Compare-and-swap: move the row from ``expected`` to ``new`` or raise Conflict."""
        with self.engine.begin() as c:
            moved = c.execute(
                tables.update()
                .where(
                    tables.c.namespace == namespace,
                    tables.c.name == name,
                    tables.c.metadata_location == expected,
                )
                .values(metadata_location=new, previous_metadata_location=expected, updated=_now())
            ).rowcount
        if moved == 1:
            return
        self.get_table(namespace, name)  # raises NotFound if the table is gone
        raise Conflict(f"{namespace}.{name} moved past {expected}")

    def drop_table(self, namespace: str, name: str) -> None:
        with self.engine.begin() as c:
            deleted = c.execute(
                tables.delete().where(tables.c.namespace == namespace, tables.c.name == name)
            ).rowcount
        if not deleted:
            raise NotFound(f"{namespace}.{name}")

    # -- views (real-data brief R6): Iceberg views, one metadata file each -----------------

    def list_views(self, namespace: str) -> list[str]:
        self.get_namespace(namespace)
        with self.engine.connect() as c:
            return list(
                c.execute(
                    sa.select(views.c.name)
                    .where(views.c.namespace == namespace)
                    .order_by(views.c.name)
                ).scalars()
            )

    def get_view(self, namespace: str, name: str) -> str:
        with self.engine.connect() as c:
            row = c.execute(
                sa.select(views.c.metadata_location).where(
                    views.c.namespace == namespace, views.c.name == name
                )
            ).scalar()
        if row is None:
            raise NotFound(f"view {namespace}.{name}")
        return row

    def put_view(self, namespace: str, name: str, metadata_location: str) -> bool:
        """Create or replace: returns True when the view was new."""
        self.get_namespace(namespace)
        now = _now()
        with self.engine.begin() as c:
            moved = c.execute(
                views.update()
                .where(views.c.namespace == namespace, views.c.name == name)
                .values(metadata_location=metadata_location, updated=now)
            ).rowcount
            if moved:
                return False
            c.execute(
                views.insert().values(
                    namespace=namespace,
                    name=name,
                    metadata_location=metadata_location,
                    created=now,
                    updated=now,
                )
            )
        return True

    def drop_view(self, namespace: str, name: str) -> None:
        with self.engine.begin() as c:
            deleted = c.execute(
                views.delete().where(views.c.namespace == namespace, views.c.name == name)
            ).rowcount
        if not deleted:
            raise NotFound(f"view {namespace}.{name}")

    def rename_table(self, namespace: str, name: str, new_namespace: str, new_name: str) -> None:
        self.get_namespace(new_namespace)
        try:
            with self.engine.begin() as c:
                moved = c.execute(
                    tables.update()
                    .where(tables.c.namespace == namespace, tables.c.name == name)
                    .values(namespace=new_namespace, name=new_name, updated=_now())
                ).rowcount
        except IntegrityError as e:
            raise AlreadyExists(f"{new_namespace}.{new_name}") from e
        if not moved:
            raise NotFound(f"{namespace}.{name}")
