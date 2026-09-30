# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The schema version both SQLite stores write and, since the trust round (T4), read back.
A file written by a newer QuerySolo is refused with the sentence saying which; an older one is
migrated forward through the numbered migrations, each once, in order. There are no
migrations yet: the mechanism is here so that the first schema change is safe to make."""

from __future__ import annotations

from collections.abc import Callable

import sqlalchemy as sa

from querysolo import __version__

Migration = tuple[int, Callable[[sa.Connection], None]]


class SchemaTooNew(Exception):
    """The file's schema is newer than this QuerySolo knows; nothing was touched."""


def ensure_schema(
    engine: sa.Engine,
    meta: sa.Table,
    current: int,
    migrations: list[Migration],
    what: str,
) -> int:
    """Read the ``schema_version`` row of ``meta`` (create it for a new file), refuse a
    newer one, run the migrations an older one needs, and record which QuerySolo last wrote
    the file. Returns the version the file is at afterwards."""
    with engine.begin() as c:
        rows = {
            k: v
            for k, v in c.execute(sa.select(meta.c.key, meta.c.value)).all()
            if k in ("schema_version", "written_by")
        }
        if "schema_version" not in rows:
            c.execute(meta.insert().values(key="schema_version", value=str(current)))
            c.execute(meta.insert().values(key="written_by", value=__version__))
            return current
        version = int(rows["schema_version"])
        if version > current:
            by = rows.get("written_by") or "a newer version"
            raise SchemaTooNew(
                f"this project's {what} was written by a newer QuerySolo ({by}, schema "
                f"{version}); this is {__version__}, which reads schema {current} — upgrade "
                "QuerySolo, or open the project with the version that wrote it"
            )
        for target, migrate in sorted(migrations, key=lambda m: m[0]):
            if version < target <= current:
                migrate(c)
                version = target
                c.execute(
                    meta.update().where(meta.c.key == "schema_version").values(value=str(version))
                )
        if rows.get("written_by") != __version__:
            if "written_by" in rows:
                c.execute(meta.update().where(meta.c.key == "written_by").values(value=__version__))
            else:
                c.execute(meta.insert().values(key="written_by", value=__version__))
        return version
