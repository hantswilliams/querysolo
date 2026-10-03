# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 1 gate, second client: pyiceberg's RestCatalog reads and writes through QuerySolo's
catalog on SQLite and a file:// warehouse (brief D6). DuckDB, concurrency, s3:// and
Postgres have their own files."""

import logging

import pyarrow as pa
import pytest
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import NoSuchTableError

from tests.catalog_helpers import SCHEMA, pyiceberg_round_trip, serve


@pytest.fixture
def served(tmp_path):
    s = serve(f"sqlite:///{tmp_path}/catalog.db", f"file://{tmp_path}/warehouse")
    s.root = tmp_path
    yield s
    s.stop()


def test_pyiceberg_round_trip(served) -> None:
    pyiceberg_round_trip(served.url, served.warehouse)
    with pytest.raises(NoSuchTableError):
        RestCatalog("querysolo", uri=served.url).load_table("main.orders2")


def test_a_stale_commit_is_refused_then_pyiceberg_retries(served, caplog) -> None:
    """The server answers 409 to a stale commit (D5); pyiceberg refreshes and retries on its
    own, so both appends land. Recorded for D23: the client side of the 409 story."""
    cat = RestCatalog("querysolo", uri=served.url)
    cat.create_namespace("main")
    cat.create_table("main.t", schema=SCHEMA)
    one, two = cat.load_table("main.t"), cat.load_table("main.t")
    one.append(pa.table({"id": [1], "amt": [1.0]}))
    with caplog.at_level(logging.WARNING, logger="pyiceberg.table"):
        two.append(pa.table({"id": [2], "amt": [2.0]}))
    assert "concurrent update, retrying" in caplog.text
    assert any(m == "POST" and c == 409 for m, _, c in served.log)
    assert cat.load_table("main.t").scan().to_arrow().num_rows == 2
    # v0, v1, v2: the refused attempt failed validation before anything was written
    assert len(list((served.root / "warehouse/main/t/metadata").glob("*.metadata.json"))) == 3


def test_multi_level_namespaces_are_a_clean_400(served) -> None:
    cat = RestCatalog("querysolo", uri=served.url)
    with pytest.raises(Exception, match="single level"):
        cat.create_namespace(("a", "b"))
