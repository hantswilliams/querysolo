# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 1 gate, s3:// warehouse: the same catalog with its metadata and data files on S3.
Runs against Moto's threaded server in the default suite; against a real bucket when
QUERYSOLO_TEST_S3_BUCKET (or a self-hosted QUERYSOLO_TEST_S3_ENDPOINT) and the AWS keys are
set (brief D16; tests/s3_helpers.py)."""

import pytest
from pyiceberg.catalog.rest import RestCatalog

from tests.catalog_helpers import attach, pyiceberg_round_trip, serve
from tests.s3_helpers import open_store


@pytest.fixture(scope="module")
def s3():
    store = open_store()
    yield store
    store.stop()


@pytest.fixture
def served(tmp_path, s3):
    prefix = s3.uri(s3.key(tmp_path.name))
    s = serve(f"sqlite:///{tmp_path}/catalog.db", prefix, io_properties=s3.props)
    s.s3 = s3
    yield s
    s.stop()


def test_pyiceberg_round_trip_on_s3(served) -> None:
    pyiceberg_round_trip(served.url, served.warehouse, client_properties=served.s3.props)


def test_duckdb_writes_to_an_s3_warehouse(served) -> None:
    RestCatalog("querysolo", uri=served.url, **served.s3.props).create_namespace("main")
    con = attach(served.url, secret_sql=served.s3.duckdb_secret_sql())
    con.execute("CREATE TABLE querysolo.main.orders (id BIGINT, amt DOUBLE)")
    con.execute("INSERT INTO querysolo.main.orders VALUES (1, 1.0), (2, 2.0)")
    assert con.execute("SELECT sum(amt) FROM querysolo.main.orders").fetchone()[0] == 3.0
    table = RestCatalog("querysolo", uri=served.url, **served.s3.props).load_table("main.orders")
    assert table.scan().to_arrow().num_rows == 2
    assert table.metadata_location.startswith("s3://")
