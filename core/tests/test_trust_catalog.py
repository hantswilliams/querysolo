# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Trust round T6: the catalog's ``/v1`` answers only requests that name loopback and refuses
what a browser page can send — a ``Host`` that is not loopback (DNS rebinding), an ``Origin``
header at all on ``/v1`` or one the app's CORS does not allow on ``/api``, and a body that is
not JSON. The engines' own requests are unchanged: the DuckDB, pyiceberg, Spark and Trino
suites are the proof, and one request here shaped like theirs."""

from __future__ import annotations

import httpx
import pytest

from querysolo import Project


@pytest.fixture
def served(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root, serve=True)
    yield p
    p.close()


def _client(p: Project) -> httpx.Client:
    return httpx.Client(base_url=p.catalog_url, timeout=30)


def _api_headers(p: Project) -> dict[str, str]:
    return {"Authorization": f"Bearer {p.token}"}


def test_a_host_that_is_not_loopback_is_refused_on_both_prefixes(served) -> None:
    with _client(served) as c:
        for path, headers in (("/v1/config", {}), ("/api/health", _api_headers(served))):
            r = c.get(path, headers={**headers, "Host": "evil.example:8181"})
            assert r.status_code == 403, path
            assert "not loopback" in r.json()["error"]["message"]
        # the same requests as an engine sends them
        assert c.get("/v1/config").status_code == 200
        assert c.get("/api/health", headers=_api_headers(served)).status_code == 200
        for host in ("127.0.0.1:1", "localhost:1", "[::1]:1", "localhost"):
            assert c.get("/v1/config", headers={"Host": host}).status_code == 200, host


def test_an_origin_header_is_refused_on_v1_and_an_unknown_one_on_api(served) -> None:
    with _client(served) as c:
        r = c.get("/v1/config", headers={"Origin": "http://evil.example"})
        assert r.status_code == 403 and "Origin" in r.json()["error"]["message"]
        r = c.get("/v1/config", headers={"Origin": "tauri://localhost"})
        assert r.status_code == 403  # no engine sends one; the app never talks to /v1
        r = c.get("/api/health", headers={**_api_headers(served), "Origin": "http://evil.example"})
        assert r.status_code == 403
        r = c.get("/api/health", headers={**_api_headers(served), "Origin": "tauri://localhost"})
        assert r.status_code == 200  # the app's own origin, as CORS allows it


def test_a_body_that_is_not_json_is_refused_before_any_route(served) -> None:
    with _client(served) as c:
        body = '{"namespace": ["evil"]}'
        r = c.post("/v1/querysolo/namespaces", content=body, headers={"Content-Type": "text/plain"})
        assert r.status_code == 403 and "application/json" in r.json()["error"]["message"]
        r = c.post(
            "/v1/querysolo/namespaces",
            content="namespace=evil",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 403
        assert "evil" not in c.get("/v1/querysolo/namespaces").text  # no route was reached
        r = c.post(
            "/api/estimate",
            content='{"sql": "select 1"}',
            headers={**_api_headers(served), "Content-Type": "text/plain"},
        )
        assert r.status_code == 403
        # JSON, as the engines and the app send it, goes through
        r = c.post("/v1/querysolo/namespaces", json={"namespace": ["fine"]})
        assert r.status_code == 200, r.text
        r = c.post("/api/estimate", json={"sql": "select 1"}, headers=_api_headers(served))
        assert r.status_code == 200


def test_the_two_documents_exist_and_say_what_the_server_does() -> None:
    import pathlib

    repo = pathlib.Path(__file__).resolve().parents[2]
    privacy = (repo / "PRIVACY.md").read_text(encoding="utf-8")
    security = (repo / "SECURITY.md").read_text(encoding="utf-8")
    for needle in ("127.0.0.1", "Host", "Origin", "application/json", "audit network", "history"):
        assert needle in privacy, needle
    assert "advisor" in security.lower() and "@" in security
