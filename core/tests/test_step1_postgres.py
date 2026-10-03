# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 1 gate, second dialect: the same store schema and the same round trip on Postgres,
when QUERYSOLO_TEST_PG_URL points at one (brief D5)."""

import os
import uuid

import pytest
import sqlalchemy as sa

from tests.catalog_helpers import pyiceberg_round_trip, serve

PG_URL = os.environ.get("QUERYSOLO_TEST_PG_URL")

pytestmark = pytest.mark.skipif(not PG_URL, reason="QUERYSOLO_TEST_PG_URL is not set")


@pytest.fixture
def served(tmp_path):
    schema = f"querysolo_test_{uuid.uuid4().hex[:8]}"
    engine = sa.create_engine(PG_URL)
    with engine.begin() as c:
        c.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    url = PG_URL + ("&" if "?" in PG_URL else "?") + f"options=-csearch_path%3D{schema}"
    s = serve(url, f"file://{tmp_path}/warehouse")
    yield s
    s.stop()
    with engine.begin() as c:
        c.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))


def test_pyiceberg_round_trip_on_postgres(served) -> None:
    pyiceberg_round_trip(served.url, served.warehouse)
