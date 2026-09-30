# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Shared pieces of the step 1 tests: a served catalog with a request log, the pyiceberg
round trip that every backend variant must pass, and the DuckDB attach."""

from __future__ import annotations

from types import SimpleNamespace

import duckdb
import pyarrow as pa
from fastapi import Request
from pyiceberg.catalog.rest import RestCatalog

from querysolo.catalog import EmbeddedCatalog, Store, create_app

SCHEMA = pa.schema([("id", pa.int64()), ("amt", pa.float64())])


def serve(store_url: str, warehouse: str, io_properties: dict | None = None) -> SimpleNamespace:
    store = Store(store_url)
    app = create_app(store, warehouse=warehouse, io_properties=io_properties)
    log: list[tuple[str, str, int]] = []

    @app.middleware("http")
    async def _record(request: Request, call_next):
        response = await call_next(request)
        log.append((request.method, request.url.path, response.status_code))
        return response

    server = EmbeddedCatalog(app)
    url = server.start()
    return SimpleNamespace(url=url, warehouse=warehouse, store=store, log=log, stop=server.stop)


def pyiceberg_round_trip(url: str, warehouse: str, client_properties: dict | None = None) -> None:
    cat = RestCatalog("querysolo", uri=url, **(client_properties or {}))
    cat.create_namespace("main")
    assert cat.list_namespaces() == [("main",)]

    table = cat.create_table("main.orders", schema=SCHEMA)
    assert table.metadata_location.startswith(warehouse + "/main/orders/metadata/00000-")
    table.append(pa.table({"id": [1, 2, 3], "amt": [1.0, 2.0, 3.0]}))

    again = cat.load_table("main.orders")
    assert again.scan().to_arrow().num_rows == 3
    assert "/metadata/00001-" in again.metadata_location
    assert cat.list_tables("main") == [("main", "orders")]

    cat.rename_table("main.orders", "main.orders2")
    assert cat.table_exists("main.orders2") and not cat.table_exists("main.orders")

    registered = cat.register_table(
        "main.orders3", cat.load_table("main.orders2").metadata_location
    )
    assert registered.scan().to_arrow().num_rows == 3

    cat.drop_table("main.orders3")
    cat.drop_table("main.orders2")
    assert cat.list_tables("main") == []
    cat.drop_namespace("main")
    assert cat.list_namespaces() == []


def attach(url: str, secret_sql: str | None = None) -> duckdb.DuckDBPyConnection:
    """DuckDB's attach as the engine will do it: ``DEFAULT_SCHEMA 'main'`` is required, or
    DuckDB resolves an empty schema name locally and never reaches the catalog."""
    con = duckdb.connect()
    con.execute("INSTALL iceberg; INSTALL httpfs; LOAD iceberg; LOAD httpfs")
    if secret_sql:
        con.execute(secret_sql)
    con.execute(
        f"ATTACH 'querysolo' AS querysolo (TYPE ICEBERG, ENDPOINT '{url}', "
        "AUTHORIZATION_TYPE 'none', DEFAULT_SCHEMA 'main')"
    )
    return con
