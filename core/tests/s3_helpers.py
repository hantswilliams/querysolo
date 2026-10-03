# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""One object store for the S3 tests (brief D16; real-data brief R2).

By default an in-process Moto server with a throwaway bucket. Two environment variables
point the same tests at a real store instead:

* ``QUERYSOLO_TEST_S3_BUCKET`` names an existing bucket the suite may write to. It is never
  created and never deleted; the suite writes under ``querysolo-tests/<run>/`` and under
  ``_querysolo/`` (the metadata-in-bucket layout, brief D26) and removes both when the module
  ends. Use a bucket that is the suite's own.
* ``QUERYSOLO_TEST_S3_ENDPOINT`` (or ``AWS_ENDPOINT_URL``) points at a self-hosted store such
  as the RustFS in ``compose.yaml``. Without a bucket name the bucket ``querysolo-test`` is
  created there if missing, as before.

The credentials are ``AWS_ACCESS_KEY_ID`` and ``AWS_SECRET_ACCESS_KEY``, the region
``AWS_REGION`` (``us-east-1`` when unset); on AWS itself leave the endpoint unset.
``docs/remote`` on the site has the IAM policy and the cost."""

from __future__ import annotations

import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

import boto3

RUN_ROOT = "querysolo-tests"
METADATA_ROOT = "_querysolo/"


@dataclass
class S3Store:
    bucket: str
    endpoint: str | None
    key_id: str
    secret: str
    region: str
    real: bool
    run: str
    client: Any
    _server: Any = field(default=None, repr=False)
    writer_con: Any = field(default=None, repr=False)  # the tests' plain-DuckDB writer

    # -- names -------------------------------------------------------------------------
    def key(self, name: str) -> str:
        """A key under this run's prefix, so a real bucket can be cleaned afterwards."""
        return f"{self.run}/{name}"

    def uri(self, key: str) -> str:
        return f"s3://{self.bucket}/{key}"

    # -- client settings ---------------------------------------------------------------
    @property
    def props(self) -> dict[str, str]:
        """pyiceberg FileIO properties."""
        p = {
            "s3.access-key-id": self.key_id,
            "s3.secret-access-key": self.secret,
            "s3.region": self.region,
        }
        if self.endpoint:
            p["s3.endpoint"] = self.endpoint
        return p

    def duckdb_secret_sql(self) -> str:
        parts = [
            "TYPE s3",
            f"KEY_ID '{self.key_id}'",
            f"SECRET '{self.secret}'",
            f"REGION '{self.region}'",
        ]
        if self.endpoint:
            url = urlsplit(self.endpoint)
            parts += [
                f"ENDPOINT '{url.netloc}'",
                "URL_STYLE 'path'",
                f"USE_SSL {'true' if url.scheme == 'https' else 'false'}",
            ]
        return "CREATE SECRET (" + ", ".join(parts) + ")"

    def environment(self) -> dict[str, str]:
        """What a ``Project`` reads (``querysolo.remote.S3Settings``)."""
        env = {
            "AWS_ACCESS_KEY_ID": self.key_id,
            "AWS_SECRET_ACCESS_KEY": self.secret,
            "AWS_REGION": self.region,
        }
        if self.endpoint:
            env["AWS_ENDPOINT_URL"] = self.endpoint
        return env

    # -- housekeeping ------------------------------------------------------------------
    def keys(self, prefix: str) -> set[str]:
        pages = self.client.get_paginator("list_objects_v2").paginate(
            Bucket=self.bucket, Prefix=prefix
        )
        return {o["Key"] for page in pages for o in page.get("Contents", [])}

    def delete_prefix(self, prefix: str) -> int:
        keys = sorted(self.keys(prefix))
        for i in range(0, len(keys), 1000):
            chunk = keys[i : i + 1000]
            self.client.delete_objects(
                Bucket=self.bucket, Delete={"Objects": [{"Key": k} for k in chunk], "Quiet": True}
            )
        return len(keys)

    def clean(self) -> None:
        """Remove what the suite writes to a real bucket: this run's prefix and the
        metadata-in-bucket layout, which is at the bucket root by design (D26)."""
        if self.real:
            self.delete_prefix(self.run + "/")
            self.delete_prefix(METADATA_ROOT)

    def stop(self) -> None:
        if self.writer_con is not None:
            self.writer_con.close()
        self.clean()
        if self._server is not None:
            self._server.stop()


def open_store() -> S3Store:
    bucket = os.environ.get("QUERYSOLO_TEST_S3_BUCKET")
    endpoint = os.environ.get("QUERYSOLO_TEST_S3_ENDPOINT") or os.environ.get("AWS_ENDPOINT_URL")
    region = os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "us-east-1"
    run = f"{RUN_ROOT}/{datetime.now(UTC):%Y%m%d-%H%M%S}-{secrets.token_hex(2)}"
    server = None
    if bucket or endpoint:
        try:
            key_id, secret = os.environ["AWS_ACCESS_KEY_ID"], os.environ["AWS_SECRET_ACCESS_KEY"]
        except KeyError as e:
            raise RuntimeError(
                f"{e.args[0]} is not set; the real-store run needs both AWS keys in the "
                "environment (docs/remote)"
            ) from None
    else:
        logging.getLogger("werkzeug").setLevel(logging.ERROR)
        from moto.server import ThreadedMotoServer

        server = ThreadedMotoServer(ip_address="127.0.0.1", port=0, verbose=False)
        server.start()
        time.sleep(0.3)
        endpoint = f"http://127.0.0.1:{server._server.socket.getsockname()[1]}"
        key_id = secret = "test"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key_id,
        aws_secret_access_key=secret,
        region_name=region,
    )
    if bucket:
        try:
            client.head_bucket(Bucket=bucket)
        except Exception as e:  # noqa: BLE001 - botocore's class depends on the store
            raise RuntimeError(
                f"QUERYSOLO_TEST_S3_BUCKET={bucket} is not reachable with these credentials "
                f"({e}); the suite never creates a real bucket"
            ) from None
    else:
        bucket = "querysolo-test"
        if bucket not in {b["Name"] for b in client.list_buckets().get("Buckets", [])}:
            client.create_bucket(Bucket=bucket)
    store = S3Store(
        bucket=bucket,
        endpoint=endpoint,
        key_id=key_id,
        secret=secret,
        region=region,
        real=server is None,
        run=run,
        client=client,
        _server=server,
    )
    store.clean()  # a crashed earlier run may have left the metadata layout behind
    return store
