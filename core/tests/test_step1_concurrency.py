# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 1 gate: 100 commits from ten concurrent processes, each with its own embedded
catalog on the same SQLite file, lose nothing (brief D3, D5)."""

import subprocess
import sys
from pathlib import Path

import pyarrow as pa
import pytest
from pyiceberg.catalog.rest import RestCatalog

from tests.catalog_helpers import serve

PROCESSES, COMMITS = 10, 10


@pytest.fixture
def served(tmp_path):
    s = serve(f"sqlite:///{tmp_path}/catalog.db", f"file://{tmp_path}/warehouse")
    s.store_url = f"sqlite:///{tmp_path}/catalog.db"
    yield s
    s.stop()


def test_hundred_commits_from_ten_processes_lose_nothing(served) -> None:
    cat = RestCatalog("querysolo", uri=served.url)
    cat.create_namespace("main")
    cat.create_table("main.t", schema=pa.schema([("writer", pa.int64()), ("i", pa.int64())]))

    script = Path(__file__).with_name("concurrent_writer.py")
    procs = [
        subprocess.Popen(
            [sys.executable, str(script), served.store_url, served.warehouse, str(w), str(COMMITS)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        for w in range(PROCESSES)
    ]
    outs = [p.communicate(timeout=300) for p in procs]
    for p, (_out, err) in zip(procs, outs, strict=True):
        assert p.returncode == 0, err[-2000:]
    retries = sum(int(out.strip()) for out, _ in outs)

    table = cat.load_table("main.t")
    rows = table.scan().to_arrow().to_pydict()
    assert len(rows["i"]) == PROCESSES * COMMITS
    assert sorted(zip(rows["writer"], rows["i"], strict=True)) == [
        (w, i) for w in range(PROCESSES) for i in range(COMMITS)
    ]
    assert len(table.metadata.snapshots) == PROCESSES * COMMITS
    print(f"\n{PROCESSES * COMMITS} commits landed; {retries} conflicts were retried")
