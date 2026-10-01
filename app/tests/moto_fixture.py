# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""A stand-in bucket for the attach test (real-data brief R4, step 2): an in-process Moto
server with a public-read bucket holding three plain Parquet files under ``raw/events/``,
the way a partner's pipeline would have left them. Prints ``moto <endpoint>`` once ready,
then waits; when the file named as its argument appears, a fourth file is written so the
test can refresh. Killed by the Playwright teardown. Moto enforces ACLs as S3 does, so
the bucket and every object are granted public-read and the anonymous path is real."""

from __future__ import annotations

import sys

# Before the slow imports, so a timeout in the test says whether this process started at all.
print("moto fixture: importing", file=sys.stderr, flush=True)

import logging  # noqa: E402
import os  # noqa: E402
import signal  # noqa: E402
import tempfile  # noqa: E402
import time  # noqa: E402

import boto3  # noqa: E402
import duckdb  # noqa: E402
from moto.server import ThreadedMotoServer  # noqa: E402

BUCKET = "querysolo-test"
PREFIX = "raw/events"


def main() -> None:
    flag = sys.argv[1]
    logging.getLogger("werkzeug").setLevel(logging.ERROR)
    server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
    server.start()
    time.sleep(0.3)
    endpoint = f"http://127.0.0.1:{server._server.socket.getsockname()[1]}"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id="test",
        aws_secret_access_key="test",
        region_name="us-east-1",
    )
    client.create_bucket(Bucket=BUCKET, ACL="public-read")

    def put(i: int) -> None:
        with tempfile.NamedTemporaryFile(suffix=".parquet", delete=False) as f:
            path = f.name
        duckdb.sql(
            f"COPY (SELECT range AS id, 'c' || (range % 10) AS customer, range * 1.5 AS amt "
            f"FROM range({i * 1000}, {i * 1000 + 1000})) TO '{path}' (FORMAT parquet)"
        )
        with open(path, "rb") as data:
            client.put_object(
                Bucket=BUCKET, Key=f"{PREFIX}/part-{i}.parquet", Body=data, ACL="public-read"
            )
        os.unlink(path)

    for i in range(3):
        put(i)
    print(f"moto {endpoint}", flush=True)

    stop = False

    def on_term(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, on_term)
    parent = os.getppid()
    added = False
    while not stop and os.getppid() == parent:  # gone with the Playwright runner, whatever else
        if not added and os.path.exists(flag):
            put(3)
            added = True
            print("added part-3", flush=True)
        time.sleep(0.2)
    server.stop()


if __name__ == "__main__":
    main()
