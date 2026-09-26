# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""The DuckDB connection (brief D9, D15, D21, D33): the three extensions loaded from the
machine's cache, the catalog attached as ``lakelet`` with ``main`` as the default schema so
bare table names work, limits from the config, and the profiler on for every statement."""

from __future__ import annotations

import json
import os
import random
import time
from pathlib import Path

import duckdb

EXTENSIONS = ("iceberg", "httpfs", "excel", "aws")
#: What an install must carry: the four the engine loads plus ``avro``, which ``iceberg``
#: pulls in on first LOAD (manifests are Avro) and would otherwise fetch on its own — the
#: one download D33 allows at ``init`` covers it, and the bundle (S2) ships it.
INSTALLED_EXTENSIONS = EXTENSIONS + ("avro",)
#: Ship brief S2: an installer bundles the four extensions beside the frozen core and names
#: the folder here; every connection then reads them from there and nothing is fetched.
#: Unset (the CLI from PyPI, development), DuckDB's own ``~/.duckdb/extensions`` applies.
EXTENSION_DIR_ENV = "LAKELET_EXTENSION_DIR"


def extension_directory() -> str | None:
    """The bundled extension folder, when the installer set it (S2), else None."""
    return os.environ.get(EXTENSION_DIR_ENV) or None


def connect() -> duckdb.DuckDBPyConnection:
    """A DuckDB connection that reads extensions from the bundled folder when there is one.
    Every connection the core opens comes through here, so the frozen app never looks at
    ``~/.duckdb`` and never downloads."""
    con = duckdb.connect()
    directory = extension_directory()
    if directory:
        con.execute("SET extension_directory = ?", [directory])
    return con


SEARCH_PATH = "lakelet.main,memory.main"


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


# The AWS default chain through the aws extension (brief D36), used when the environment
# holds no explicit keys. DuckDB 1.5 resolves the chain when the secret is created and
# refuses when nothing resolves, which is the normal state of a laptop with no AWS account.
DEFAULT_CHAIN_SECRET = "CREATE OR REPLACE SECRET lakelet_s3 (TYPE s3, PROVIDER credential_chain)"

PROFILE_METRICS = (
    "LATENCY",
    "ROWS_RETURNED",
    "CUMULATIVE_ROWS_SCANNED",
    "OPERATOR_ROWS_SCANNED",
    "OPERATOR_CARDINALITY",
    "OPERATOR_TIMING",
    "SYSTEM_PEAK_BUFFER_MEMORY",
    "SYSTEM_PEAK_TEMP_DIR_SIZE",
)


class ExtensionsMissing(RuntimeError):
    pass


class CatalogConflict(RuntimeError):
    """A commit lost the race three times (brief D23); the CLI maps it to exit 4."""


CONFLICT_MARKERS = ("Failed to commit Iceberg transaction", "409")


def is_conflict(error: Exception) -> bool:
    return all(marker in str(error) for marker in CONFLICT_MARKERS)


def remove_stray_data_dir(cwd: Path | None = None) -> bool:
    """Decisions F1: DuckDB's Iceberg extension makes ``<location>/data/`` before the
    catalog has told it the table's location, so on the first CREATE TABLE an empty
    ``data/`` appears relative to the process's working directory — in the project folder
    for the app and a `lakelet` run from it, in whatever folder a `lakelet -C` was run
    from otherwise. The real files go where the catalog said. This removes that folder
    when it is exactly that: a directory named ``data`` in the cwd, empty, and not part of
    an Iceberg table's own layout (no ``metadata/`` beside it). Anything else is left
    alone. True when something was removed."""
    here = cwd or Path.cwd()
    stray = here / "data"
    try:
        if not stray.is_dir() or stray.is_symlink() or (here / "metadata").exists():
            return False
        if any(stray.iterdir()):
            return False
        stray.rmdir()
        return True
    except OSError:
        return False


def run_with_retry(engine: Engine, sql: str, attempts: int = 3) -> None:
    """DuckDB does not retry a 409 (step 1); Lakelet re-runs the statement with jittered
    backoff, then raises CatalogConflict."""
    for attempt in range(attempts):
        try:
            engine.execute(sql)
            return
        except duckdb.Error as e:
            if not is_conflict(e) or attempt == attempts - 1:
                if is_conflict(e):
                    raise CatalogConflict(str(e)) from e
                raise
            time.sleep(random.uniform(0.1, 0.5) * (attempt + 1))


def install_extensions() -> tuple[list[str], str]:
    """``lakelet init``'s one network fetch (brief D33). Returns the extensions that were
    downloaded now and the directory they live in. With the bundled folder set (S2) the
    four are already installed there, so nothing is fetched."""
    con = connect()

    def installed() -> set[str]:
        rows = con.execute(
            "select extension_name from duckdb_extensions() where installed"
        ).fetchall()
        return {name for (name,) in rows}

    before = installed()
    con.execute("; ".join(f"INSTALL {name}" for name in INSTALLED_EXTENSIONS))
    downloaded = sorted(installed() - before)
    directory = con.execute("select current_setting('extension_directory')").fetchone()[0]
    con.close()
    return downloaded, directory or os.path.expanduser("~/.duckdb/extensions")


class Engine:
    def __init__(
        self,
        catalog_url: str,
        profile_path: Path,
        memory_limit: str = "auto",
        threads: int | str = "auto",
        s3_secret: str | None = None,
    ) -> None:
        self.con = connect()
        self.profile_path = profile_path
        try:
            self.con.execute("; ".join(f"LOAD {name}" for name in EXTENSIONS))
        except duckdb.IOException as e:
            raise ExtensionsMissing(
                "DuckDB's iceberg, httpfs, excel and aws extensions are not installed on this "
                "machine; `lakelet init` installs them once"
            ) from e
        # A GeoParquet column (a `geo` footer entry; Overture's files) is registered in the
        # catalog as `binary`, its WKB bytes. With this on, and DuckDB's spatial extension
        # on the machine, the Parquet reader turns the column into GEOMETRY on its own and
        # the Iceberg scan then fails to cast it back to binary — every read of the table
        # refused. Off, the bytes come through as they are; `st_geomfromwkb` is in core
        # DuckDB for anyone who wants the geometry.
        self.con.execute("SET enable_geoparquet_conversion = false")
        # The user's own credentials (brief D36): explicit keys from the environment, else
        # the AWS default chain. Local work never needs either, so a chain that resolves
        # nothing is kept as a message for the first s3:// operation, not raised here.
        self.s3_error: str | None = None
        if s3_secret:
            self.con.execute(s3_secret)
        else:
            self._try_default_chain()
        if memory_limit != "auto":
            self.con.execute("SET memory_limit = ?", [memory_limit])
        if threads != "auto":
            self.con.execute("SET threads = ?", [int(threads)])
        self.con.execute(
            f"ATTACH 'lakelet' AS lakelet (TYPE ICEBERG, ENDPOINT '{catalog_url}', "
            "AUTHORIZATION_TYPE 'none', DEFAULT_SCHEMA 'main')"
        )
        # Tables are lakelet.main's; views live in this session's memory.main (DuckDB's
        # Iceberg catalog cannot hold a view), so both resolve unqualified, tables first.
        self.con.execute(f"SET search_path = '{SEARCH_PATH}'")
        self._views: dict[str, str] = {}
        if proxy := os.environ.get("LAKELET_HTTP_PROXY"):
            # `lakelet audit network`: DuckDB's HTTP client is not a Python socket, so the
            # audit watches it through a loopback proxy that forwards loopback targets only.
            self.con.execute("SET http_proxy = ?", [proxy])
        settings = json.dumps({metric: "true" for metric in PROFILE_METRICS})
        self.con.execute("SET custom_profiling_settings = ?", [settings])
        self.con.execute("SET enable_profiling = 'json'")
        self.con.execute("SET profiling_output = ?", [str(profile_path)])

    def _try_default_chain(self) -> bool:
        try:
            self.con.execute(DEFAULT_CHAIN_SECRET)
        except duckdb.Error as e:
            self.s3_error = " ".join(line.strip() for line in str(e).splitlines() if line.strip())
            return False
        self.s3_error = None
        return True

    def put_view(self, name: str, sql: str) -> None:
        """This session's DuckDB view for a catalog view (real-data brief R6): the catalog's
        own cannot hold one, so it lives in memory.main and resolves through the search
        path. Raises DuckDB's error when the SQL does not bind."""
        if self._views.get(name) != sql:
            self.con.execute(f"CREATE OR REPLACE VIEW memory.main.{_quote(name)} AS {sql}")
            self._views[name] = sql

    def drop_view(self, name: str) -> None:
        self.con.execute(f"DROP VIEW IF EXISTS memory.main.{_quote(name)}")
        self._views.pop(name, None)

    @property
    def views(self) -> dict[str, str]:
        return dict(self._views)

    def allow_public(self, secret_sql: str) -> None:
        """A bucket read without credentials (real-data brief R3): one scoped secret."""
        self.con.execute(secret_sql)

    def s3_problem(self) -> str | None:
        """Before anything touches ``s3://``: None when a secret is in place, otherwise, after
        one more try at the default chain, a sentence naming what to set."""
        if self.s3_error is None or self._try_default_chain():
            return None
        return (
            "no AWS credentials: set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY (and "
            "AWS_ENDPOINT_URL for a self-hosted store), or configure the AWS default chain "
            f"({self.s3_error})"
        )

    def execute(self, sql: str, parameters: list | None = None) -> duckdb.DuckDBPyConnection:
        result = self.con.execute(sql, parameters) if parameters else self.con.execute(sql)
        remove_stray_data_dir()
        return result

    def last_profile(self) -> dict | None:
        """The profiler's JSON for the last statement that produced one."""
        if not self.profile_path.exists():
            return None
        return json.loads(self.profile_path.read_text(encoding="utf-8"))

    def interrupt(self) -> None:
        """Stop the statement running on the connection, if any (the app's Esc, a client
        that went away). DuckDB raises InterruptException in the thread running it; with
        nothing running this is a no-op and the next statement is unaffected."""
        self.con.interrupt()

    def close(self) -> None:
        self.con.close()
