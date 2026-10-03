# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Object storage settings and file systems (brief D36): the user's own AWS credentials
from the standard environment, never from querysolo.toml. AWS_ENDPOINT_URL points at a
self-hosted store; with no keys in the environment every client falls back to its default
credential chain."""

from __future__ import annotations

import json
import os
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pyarrow.fs as pafs

QUERYSOLO_PREFIX = "_querysolo"
#: The same folder in buckets written before the rename (rename plan R4); discover skips both.
LEGACY_PREFIX_FOLDER = "_lakelet"
_REGIONS: dict[str, str] = {}  # bucket -> region, resolved once per process


@dataclass
class S3Settings:
    endpoint: str | None
    access_key: str | None
    secret_key: str | None
    region: str

    @classmethod
    def from_env(cls) -> S3Settings:
        return cls(
            endpoint=os.environ.get("AWS_ENDPOINT_URL") or None,
            access_key=os.environ.get("AWS_ACCESS_KEY_ID") or None,
            secret_key=os.environ.get("AWS_SECRET_ACCESS_KEY") or None,
            region=os.environ.get("AWS_REGION")
            or os.environ.get("AWS_DEFAULT_REGION")
            or "us-east-1",
        )

    def describe(self) -> dict[str, Any]:
        """What ``/api/health`` and the app say about credentials (real-data brief R4):
        whether keys are in the environment, the profile the default chain will use (a
        named one, or ``default`` when AWS's own files have a ``[default]`` section;
        decision C1), or nothing, plus the region and any self-hosted endpoint. Never
        the keys."""
        profile = os.environ.get("AWS_PROFILE") or None
        if self.access_key and self.secret_key:
            source = "environment"
        elif profile or _has_default_profile():
            source = "profile"
            profile = profile or "default"
        else:
            source = "none"
        return {
            "configured": source != "none",
            "source": source,
            "profile": profile,
            "region": self.region,
            "endpoint": self.endpoint,
        }

    def io_properties(self) -> dict[str, str]:
        """pyiceberg FileIO properties; empty values are left out so the default chain applies."""
        props = {"s3.region": self.region}
        if self.endpoint:
            props["s3.endpoint"] = self.endpoint
        if self.access_key and self.secret_key:
            props["s3.access-key-id"] = self.access_key
            props["s3.secret-access-key"] = self.secret_key
        return props

    def duckdb_secret(self) -> str | None:
        """The CREATE SECRET for the engine, or None when the default chain should be used."""
        if not (self.access_key and self.secret_key):
            return None
        parts = [
            "TYPE s3",
            f"KEY_ID '{self.access_key}'",
            f"SECRET '{self.secret_key}'",
            f"REGION '{self.region}'",
        ]
        if self.endpoint:
            url = urlsplit(self.endpoint)
            parts += [
                f"ENDPOINT '{url.netloc}'",
                "URL_STYLE 'path'",
                f"USE_SSL {'true' if url.scheme == 'https' else 'false'}",
            ]
        return "CREATE OR REPLACE SECRET querysolo_s3 (" + ", ".join(parts) + ")"

    def filesystem(
        self, scheme: str, anonymous: bool = False, bucket: str | None = None
    ) -> pafs.FileSystem:
        """``anonymous`` (real-data brief R3): unsigned requests for a public bucket, in the
        region S3 reports for that bucket rather than the one the environment assumes
        (a wrong region is a 301 the SDK does not follow)."""
        if scheme == "file":
            return pafs.LocalFileSystem()
        if scheme != "s3":
            raise ValueError(f"unsupported scheme {scheme}://")
        kwargs: dict = {"region": self.region}
        if anonymous:
            kwargs["anonymous"] = True
            if bucket:
                kwargs["region"] = self.bucket_region(bucket)
        if self.endpoint:
            url = urlsplit(self.endpoint)
            kwargs["endpoint_override"] = url.netloc
            kwargs["scheme"] = url.scheme or "http"
        if not anonymous and self.access_key and self.secret_key:
            kwargs["access_key"] = self.access_key
            kwargs["secret_key"] = self.secret_key
        return pafs.S3FileSystem(**kwargs)

    def bucket_region(self, bucket: str) -> str:
        """The region a public bucket lives in, asked of S3 itself (an unsigned HEAD, once
        per bucket per process); a self-hosted store has no regions and answers with the
        configured one."""
        if self.endpoint:
            return self.region
        if bucket not in _REGIONS:
            try:
                _REGIONS[bucket] = pafs.resolve_s3_region(bucket)
            except OSError:
                _REGIONS[bucket] = self.region
        return _REGIONS[bucket]

    def anonymous_secret(self, bucket: str, region: str) -> str:
        """A DuckDB secret scoped to one public bucket with no key, so its requests go out
        unsigned; the longest matching scope wins over the project's default secret."""
        name = "querysolo_public_" + "".join(c if c.isalnum() else "_" for c in bucket)
        parts = [
            "TYPE s3",
            "PROVIDER config",
            f"SCOPE 's3://{bucket}'",
            f"REGION '{region}'",
        ]
        if self.endpoint:
            url = urlsplit(self.endpoint)
            parts += [
                f"ENDPOINT '{url.netloc}'",
                "URL_STYLE 'path'",
                f"USE_SSL {'true' if url.scheme == 'https' else 'false'}",
            ]
        return f"CREATE OR REPLACE SECRET {name} (" + ", ".join(parts) + ")"


def _has_default_profile() -> bool:
    """Whether AWS's own files name a ``[default]`` profile the credential chain will
    pick up with nothing in the environment: ``~/.aws/credentials`` (or the file
    ``AWS_SHARED_CREDENTIALS_FILE`` points at) or ``~/.aws/config``. Only the section
    name is looked for; the values are never read."""
    home = Path.home() / ".aws"
    files = [Path(os.environ.get("AWS_SHARED_CREDENTIALS_FILE") or home / "credentials")]
    files.append(Path(os.environ.get("AWS_CONFIG_FILE") or home / "config"))
    for file in files:
        try:
            lines = file.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        if any(line.strip() == "[default]" for line in lines):
            return True
    return False


@dataclass
class BucketCheck:
    """What ``querysolo bucket check`` found (decisions P1): the credentials the environment
    offers, whether the prefix can be listed, and whether one object could be written under
    it and deleted again — so a project's first import is not the first thing to fail."""

    prefix: str
    credentials: dict[str, Any]
    read: bool = False
    write: bool = False
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.read and self.write

    def sentence(self) -> str:
        source = self.credentials.get("source")
        where = (
            "keys from the environment"
            if source == "environment"
            else f"the profile {self.credentials.get('profile')}"
            if source == "profile"
            else "no credentials in the environment"
        )
        if self.ok:
            return f"{self.prefix} is writable with {where}; one object was written and removed."
        if self.error:
            return f"{self.prefix}: {self.error} ({where})."
        return f"{self.prefix} could not be checked ({where})."

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "ok": self.ok, "sentence": self.sentence()}


def check_prefix(prefix: str, settings: S3Settings | None = None) -> BucketCheck:
    """Try the prefix the way a project would use it: list it, then write one object under
    it and delete it. Nothing else is touched; a prefix that did not exist keeps the
    zero-byte folder marker the file system leaves (the S3 console leaves the same when a
    folder is made). A failure is reported in the store's words rather than raised."""
    settings = settings or S3Settings.from_env()
    prefix = prefix.strip()
    result = BucketCheck(prefix=prefix, credentials=settings.describe())
    if not prefix.startswith("s3://"):
        result.error = "a warehouse is an s3://bucket/prefix"
        return result
    _, path = split_uri(prefix)
    path = path.rstrip("/")
    bucket = path.split("/")[0]
    if not bucket or "/" not in path:
        result.error = "a warehouse is an s3://bucket/prefix, with a prefix under the bucket"
        return result
    try:
        fs = settings.filesystem("s3", bucket=bucket)
        fs.get_file_info(pafs.FileSelector(path, allow_not_found=True))
        result.read = True
    except OSError as e:
        result.error = _store_words(e)
        return result
    probe = f"{path}/.querysolo-check-{secrets.token_hex(4)}"
    try:
        with fs.open_output_stream(probe) as f:
            f.write(b"querysolo bucket check\n")
        fs.delete_file(probe)
        result.write = True
    except OSError as e:
        result.error = _store_words(e)
    return result


def _store_words(e: OSError) -> str:
    """The store's reason, on one line, without the SDK's framing."""
    text = " ".join(str(e).split())
    for marker in ("AWS Error ", "Error "):
        if marker in text:
            text = text.split(marker, 1)[1]
            break
    if " (Request ID:" in text:
        text = text.split(" (Request ID:", 1)[0]
    return text[:300]


PUBLIC_BUCKETS_FILE = "public-buckets.json"


def load_public_buckets(querysolo_dir: Path) -> dict[str, str]:
    """``{bucket: region}`` of the buckets this project reads anonymously (real-data brief
    R3), kept in ``.querysolo/public-buckets.json`` by ``tables attach --anonymous`` so the
    engine can create their secrets at every start."""
    path = querysolo_dir / PUBLIC_BUCKETS_FILE
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def save_public_bucket(querysolo_dir: Path, bucket: str, region: str) -> None:
    buckets = load_public_buckets(querysolo_dir)
    buckets[bucket] = region
    path = querysolo_dir / PUBLIC_BUCKETS_FILE
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(buckets, indent=2, sort_keys=True) + "\n")
    tmp.replace(path)


def split_uri(uri: str) -> tuple[str, str]:
    """``s3://bucket/a/b`` -> (``s3``, ``bucket/a/b``); ``file:///x`` -> (``file``, ``/x``)."""
    url = urlsplit(uri)
    if url.scheme == "file":
        return "file", url.path
    if url.scheme == "s3":
        return "s3", f"{url.netloc}{url.path}"
    if not url.scheme:
        return "file", uri
    raise ValueError(f"unsupported location {uri}")


def join_uri(scheme: str, path: str) -> str:
    return f"file://{path}" if scheme == "file" else f"{scheme}://{path}"
