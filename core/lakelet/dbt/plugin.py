# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""The dbt-duckdb plugin (brief D9; lifted from the step 2 spike in the real-data round):
dbt-duckdb calls ``configure_connection`` on every connection it opens, which is where
Lakelet's catalog gets attached, the search path set as the engine sets it (tables in
``lakelet.main``, views in the session's ``memory.main``), and the catalog's views given
to the session so a model can ``ref()`` a view that ``lakelet run`` recorded earlier."""

from __future__ import annotations

import json
import os
import urllib.request
from typing import Any

from dbt.adapters.duckdb.plugins import BasePlugin
from duckdb import DuckDBPyConnection

SEARCH_PATH = "lakelet.main,memory.main"
DEFAULT_CHAIN_SECRET = "CREATE OR REPLACE SECRET lakelet_s3 (TYPE s3, PROVIDER credential_chain)"


def _quote(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def catalog_views(catalog_url: str) -> dict[str, str]:
    """``{name: sql}`` of the catalog's views, through the REST routes (the plugin runs
    in dbt's process, which may not be Lakelet's)."""
    base = catalog_url.rstrip("/")
    with urllib.request.urlopen(f"{base}/v1/lakelet/namespaces/main/views", timeout=10) as r:
        names = [i["name"] for i in json.load(r)["identifiers"]]
    out: dict[str, str] = {}
    for name in names:
        with urllib.request.urlopen(
            f"{base}/v1/lakelet/namespaces/main/views/{name}", timeout=10
        ) as r:
            md = json.load(r)["metadata"]
        current = next(v for v in md["versions"] if v["version-id"] == md["current-version-id"])
        out[name] = next(rep["sql"] for rep in current["representations"] if rep["type"] == "sql")
    return out


class Plugin(BasePlugin):
    def initialize(self, config: dict[str, Any]) -> None:
        self.catalog_url = config["catalog_url"]

    def configure_connection(self, conn: DuckDBPyConnection) -> None:
        # dbt-duckdb opens this connection itself; the bundled extension folder (S2), when
        # the installer set it, applies here too so a model build never fetches.
        directory = os.environ.get("LAKELET_EXTENSION_DIR")
        if directory:
            conn.execute("SET extension_directory = ?", [directory])
        conn.execute("LOAD iceberg; LOAD httpfs")
        # as the engine (`engine.py`): a GeoParquet column stays the binary the catalog says
        conn.execute("SET enable_geoparquet_conversion = false")
        # A table in a bucket (decisions W1: an `s3://` warehouse, or a table attached
        # from one) needs the same credentials the engine has: explicit keys from the
        # environment, else the AWS default chain, which is tried and left alone when it
        # resolves nothing — a local project never needs it.
        from lakelet.remote import S3Settings

        secret = S3Settings.from_env().duckdb_secret()
        try:
            conn.execute(secret or DEFAULT_CHAIN_SECRET)
        except Exception:  # noqa: BLE001 - no credentials anywhere: local tables still build
            if secret:
                raise
        conn.execute(
            f"ATTACH 'lakelet' AS lakelet (TYPE ICEBERG, ENDPOINT '{self.catalog_url}', "
            "AUTHORIZATION_TYPE 'none', DEFAULT_SCHEMA 'main')"
        )
        conn.execute(f"SET search_path = '{SEARCH_PATH}'")
        pending = catalog_views(self.catalog_url)
        for _ in range(len(pending) + 1):  # a view over a view binds once the first exists
            failed: dict[str, str] = {}
            for name, sql in pending.items():
                try:
                    conn.execute(f"CREATE OR REPLACE VIEW memory.main.{_quote(name)} AS {sql}")
                except Exception:  # noqa: BLE001 - tried again after the others
                    failed[name] = sql
            if not failed or len(failed) == len(pending):
                break
            pending = failed

    def configure_cursor(self, cursor: DuckDBPyConnection) -> None:
        """dbt-duckdb runs each model on a cursor, a new DuckDB connection that shares the
        attached databases and the memory views but not the session's search path."""
        cursor.execute(f"SET search_path = '{SEARCH_PATH}'")
