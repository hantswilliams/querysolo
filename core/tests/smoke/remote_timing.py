# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Where the time goes in an estimate over a bucket table (real-data brief, step 0).

Run from ``core/`` with the same environment as the S3 tests (``QUERYSOLO_TEST_S3_BUCKET``,
the AWS keys, ``AWS_REGION``); against Moto without them. It writes three small Parquet
files under ``querysolo-tests/<run>/timing/``, attaches them with the metadata in the bucket,
then times each phase of three consecutive estimates and prints a table, and removes what
it wrote. Nothing here is a test; it is the instrument for the 150 ms budget."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

import duckdb

from querysolo import Project
from querysolo.gauge import inputs
from tests.s3_helpers import open_store


def timed(label: str, fn, rows: list[tuple[str, float]]):
    started = time.perf_counter()
    out = fn()
    rows.append((label, (time.perf_counter() - started) * 1000))
    return out


def main() -> None:
    store = open_store()
    try:
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs")
        con.execute(store.duckdb_secret_sql())
        prefix = store.key("timing/events")
        for i in range(3):
            con.execute(
                f"COPY (SELECT range AS id, 'c' || (range % 10) AS customer, range * 1.5 AS amt "
                f"FROM range({i * 1000}, {i * 1000 + 1000})) "
                f"TO '{store.uri(prefix)}/part-{i}.parquet' (FORMAT parquet)"
            )
        con.close()
        for k, v in store.environment().items():
            os.environ[k] = v
        os.environ.pop("AWS_PROFILE", None)

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "proj"
            Project.init(root, probe_mb=8)
            p = Project.open(root)
            rows: list[tuple[str, float]] = []
            timed(
                "attach (metadata in bucket)",
                lambda: p.tables.attach("events", store.uri(prefix) + "/", metadata_in_bucket=True),
                rows,
            )
            location = p.store.get_table("main", "events")
            sql = "select sum(amt) from events where id > 2500"
            for n in (1, 2, 3):
                timed(
                    f"[{n}] EXPLAIN through DuckDB (REST load + its own S3 reads)",
                    lambda: inputs.plan_json(p.engine, sql),
                    rows,
                )
                timed(
                    f"[{n}] metadata.json through MetadataIO",
                    lambda: p.metadata_io.read(location),
                    rows,
                )
                timed(
                    f"[{n}] manifests.get (stats from the manifests)",
                    lambda: p.manifests.get("events", location),
                    rows,
                )
                timed(f"[{n}] the whole estimate", lambda: p.estimate(sql), rows)
            for setting in ("enable_http_metadata_cache=true",):
                p.engine.execute(f"SET {setting}")
                timed(f"[4] EXPLAIN with {setting}", lambda: inputs.plan_json(p.engine, sql), rows)
                timed(
                    f"[5] EXPLAIN with {setting}, again",
                    lambda: inputs.plan_json(p.engine, sql),
                    rows,
                )
            cached = sorted(
                str(f.relative_to(p.cache_dir))
                for f in (p.cache_dir / "objects").rglob("*")
                if f.is_file()
            )
            p.close()
        kind = "real" if store.real else "moto"
        print(f"\nstore: {kind}  region: {store.region}  endpoint: {store.endpoint or '(aws)'}")
        print(f"{'phase':<60} {'ms':>8}")
        for label, ms in rows:
            print(f"{label:<60} {ms:>8.0f}")
        print(f"\n{len(cached)} objects cached under .querysolo/cache/objects/:")
        for c in cached:
            print("  " + c)
    finally:
        store.stop()


if __name__ == "__main__":
    main()
