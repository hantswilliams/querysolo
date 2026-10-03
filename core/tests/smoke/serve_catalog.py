# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Smoke test only: serve the catalog on 0.0.0.0 inside the compose network so Spark and
Trino can reach it. The product binds loopback only (brief D22); this script is test
infrastructure, started by compose.yaml's ``catalog`` service, never by the CLI."""

import os

import boto3
import uvicorn

from querysolo.catalog import Store, create_app


def main() -> None:
    endpoint = os.environ["QUERYSOLO_SMOKE_S3_ENDPOINT"]
    key, secret = os.environ["AWS_ACCESS_KEY_ID"], os.environ["AWS_SECRET_ACCESS_KEY"]
    bucket = os.environ.get("QUERYSOLO_SMOKE_BUCKET", "querysolo-test")
    s3 = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name="us-east-1",
    )
    if bucket not in {b["Name"] for b in s3.list_buckets().get("Buckets", [])}:
        s3.create_bucket(Bucket=bucket)
    props = {
        "s3.endpoint": endpoint,
        "s3.access-key-id": key,
        "s3.secret-access-key": secret,
        "s3.region": "us-east-1",
    }
    app = create_app(
        Store("sqlite:////tmp/smoke-catalog.db"),
        warehouse=f"s3://{bucket}/smoke",
        io_properties=props,
    )
    uvicorn.run(app, host="0.0.0.0", port=8181, log_level="info")  # noqa: S104  compose network only


if __name__ == "__main__":
    main()
