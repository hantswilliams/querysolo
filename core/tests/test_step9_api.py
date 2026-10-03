# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 9 gate (brief §4, D3, D17, D22): the API on the same loopback server as the catalog
under `serve`; 401 without the token; /v1 open; health with versions, machine profile and
cached bandwidth; the operations over HTTP with Arrow IPC results and the verdict in the
headers; serve.json at 0600 and gone on close; the CLI's serve; non-loopback refused."""

import json
import os
import stat
import subprocess
import sys
import time
import tomllib

import duckdb
import httpx
import pyarrow as pa
import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app


@pytest.fixture
def served(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    con = duckdb.connect()
    con.execute(
        f"COPY (SELECT range AS id, 'c' || (range % 10) AS customer, range * 1.5 AS amt "
        f"FROM range(1000)) TO '{tmp_path}/orders.csv' (HEADER)"
    )
    p = Project.open(root, serve=True)
    client = httpx.Client(base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"})
    yield p, client, tmp_path
    client.close()
    p.close()


def test_token_health_and_the_open_catalog(served) -> None:
    p, client, _ = served
    health = client.get("/api/health")
    assert health.json()["throughput_probe"] in ("nocache", "direct", "cached")
    aws = health.json()["aws"]
    assert set(aws) == {"configured", "source", "profile", "region", "endpoint"}
    assert aws["source"] in ("environment", "profile", "none")
    assert aws["configured"] == (aws["source"] != "none")
    assert (
        "AWS_SECRET" not in health.text
        and (os.environ.get("AWS_SECRET_ACCESS_KEY") or "\0") not in health.text
    )
    assert health.status_code == 200, health.text
    data = health.json()
    assert data["querysolo"] and data["duckdb"] == duckdb.__version__
    assert {"ram", "cores", "memory_limit"} <= set(data["machine"])
    assert data["throughput_local_mbps"] and data["throughput_local_mbps"] > 0
    assert "bandwidth_mbps" in data

    bare = httpx.get(f"{p.catalog_url}/api/health")
    assert bare.status_code == 401 and bare.json()["detail"]["error"] == "unauthorised"
    wrong = httpx.get(f"{p.catalog_url}/api/health", headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    assert httpx.get(f"{p.catalog_url}/v1/config").status_code == 200  # the catalog, no token

    info = p.serve_json.read_text()
    data = json.loads(info)
    assert data["port"] == int(p.catalog_url.rsplit(":", 1)[1]) and data["pid"] == os.getpid()
    assert data["token"] == p.token and data["started"]
    assert stat.S_IMODE(p.serve_json.stat().st_mode) == 0o600


def test_tables_over_http(served) -> None:
    p, client, tmp_path = served
    csv = str(tmp_path / "orders.csv")
    preview = client.post("/api/preview", json={"path": csv})
    assert preview.status_code == 200 and preview.json()["name"] == "orders"
    imported = client.post("/api/import", json={"path": csv})
    assert imported.status_code == 200 and imported.json()[0]["rows"] == 1000
    assert client.post("/api/import", json={"path": csv}).status_code == 409
    assert (
        client.post("/api/import", json={"path": csv, "mode": "append"}).json()[0]["rows"] == 2000
    )
    assert client.post("/api/import", json={"path": str(tmp_path / "nope.csv")}).status_code == 400

    listed = client.get("/api/tables").json()
    assert [t["name"] for t in listed] == ["orders"] and listed[0]["rows"] == 2000
    assert listed[0]["freshness"].startswith("20"), "an ISO timestamp for the panel"
    folder = client.post("/api/preview", json={"path": str(tmp_path)})
    assert folder.status_code == 200 and [p["name"] for p in folder.json()] == ["orders"]
    assert client.post("/api/preview", json={"path": str(tmp_path / "gone")}).status_code == 400
    described = client.get("/api/tables/orders").json()
    assert described["partitioning"] == "unpartitioned" and described["snapshots"] == 2
    sampled = client.get("/api/tables/orders/sample", params={"n": 2}).json()
    assert len(sampled) == 2 and set(sampled[0]) == {"id", "customer", "amt"}
    assert client.get("/api/tables/nope").status_code == 404
    assert client.post("/api/tables/nope/refresh").status_code == 404


def test_saving_a_question_whose_title_is_taken_is_409_until_replace(served) -> None:
    """Versions brief G7: the app offers "Replace it" the way an import onto an existing
    table does, so the core refuses the second save rather than overwriting silently."""
    p, client, tmp_path = served
    assert (
        client.post("/api/import", json={"path": str(tmp_path / "orders.csv")}).status_code == 200
    )
    sql = "select customer, sum(amt) as revenue from orders group by 1"
    first = client.post("/api/questions", json={"title": "Revenue by customer", "sql": sql})
    assert first.status_code == 200 and first.json()["slug"] == "revenue_by_customer"
    assert first.json()["commit"] and first.json()["git"] is None

    again = client.post("/api/questions", json={"title": "Revenue by customer", "sql": sql})
    assert again.status_code == 409
    assert (
        again.json()["error"] == "question_exists" and again.json()["slug"] == "revenue_by_customer"
    )

    replaced = client.post(
        "/api/questions",
        json={"title": "Revenue by customer", "sql": sql + " order by 2 desc", "replace": True},
    )
    assert replaced.status_code == 200 and replaced.json()["sql"].endswith("order by 2 desc")
    assert len(client.get("/api/questions").json()) == 1


def test_settings_over_http_write_querysolo_toml(served) -> None:
    p, client, tmp_path = served
    got = client.get("/api/settings").json()
    assert got["settings"] == {
        "engine.memory_limit": "auto",
        "engine.threads": "auto",
        "gauge.share_calibration": False,
        "catalog.keep_snapshots_days": 7,
        "git.auto_commit": True,  # versions brief G4
    }
    assert got["path"].endswith("querysolo.toml")
    put = client.put("/api/settings", json={"key": "gauge.share_calibration", "value": "true"})
    assert put.status_code == 200 and put.json()["settings"]["gauge.share_calibration"] is True
    put = client.put("/api/settings", json={"key": "engine.memory_limit", "value": "2GB"})
    assert put.json()["settings"]["engine.memory_limit"] == "2GB"
    bad = client.put("/api/settings", json={"key": "project.name", "value": "x"})
    assert bad.status_code == 400 and bad.json()["error"] == "not_settable"
    text = (p.root / "querysolo.toml").read_text()
    assert 'memory_limit = "2GB"' in text and "share_calibration = true" in text
    assert "# DuckDB default, 80% of RAM" in text, "the file is edited, not regenerated"
    assert p.config.engine.memory_limit == "2GB", "the running project re-read its config"
    put = client.put("/api/settings", json={"key": "catalog.keep_snapshots_days", "value": "3"})
    assert put.json()["settings"]["catalog.keep_snapshots_days"] == 3


def test_expire_over_http(served) -> None:
    p, client, tmp_path = served
    csv = str(tmp_path / "orders.csv")
    client.post("/api/import", json={"path": csv})
    client.post("/api/import", json={"path": csv, "mode": "append"})
    described = client.get("/api/tables/orders").json()
    assert described["snapshots"] == 2 and described["expirable_snapshots"] == 0
    assert described["keep_days"] == 7 and described["reclaimable_bytes"] == 0
    expired = client.post("/api/tables/orders/expire", json={"keep_days": 0})
    assert expired.status_code == 200, expired.text
    body = expired.json()
    assert body["snapshots_before"] == 2 and body["snapshots_removed"] == 1
    assert body["files_removed"] >= 1 and body["bytes_reclaimed"] > 0
    assert client.get("/api/tables/orders").json()["snapshots"] == 1
    assert client.get("/api/tables/orders").json()["rows"] == 2000
    assert client.post("/api/tables/nope/expire").status_code == 404


def test_a_client_that_goes_away_stops_the_statement_and_history_shows_the_run(served) -> None:
    """The app's Esc aborts the fetch. The engine is interrupted at once (not left running for
    nobody), the lock is free within a moment, and the run is in history as stopped early."""
    p, client, tmp_path = served
    slow = "select count(*) as n from range(100000) a, range(100000) b"  # 10^10 rows: minutes
    t0 = time.perf_counter()
    with client.stream("POST", "/api/query", json={"sql": slow}, timeout=30) as r:
        assert r.status_code == 200 and r.headers["x-querysolo-verdict"]
        # go away before the first (and only) row exists
    health = client.get("/api/health", timeout=10)  # would wait for the lock otherwise
    assert health.status_code == 200 and time.perf_counter() - t0 < 10
    for _ in range(50):
        runs = [run for run in client.get("/api/history").json() if run["sql_text"] == slow]
        if runs:
            break
        time.sleep(0.1)
    [run] = runs
    assert run["ran"] and run["error"] is None and run["actual_wall"] is not None
    assert run["actual_bytes"] is None, "stopped early: no profile was read"
    # mid-stream too: rows are flowing when the client closes
    streaming = "select range as i, random() as x from range(50000000)"
    with client.stream("POST", "/api/query", json={"sql": streaming}, timeout=30) as r:
        assert r.status_code == 200
        next(r.iter_bytes())
    assert client.get("/api/health", timeout=10).status_code == 200
    assert client.post("/api/query", json={"sql": "select 1 as one"}).status_code == 200


def test_a_client_gone_before_the_first_byte_frees_the_lock(served) -> None:
    """The request sent and the socket closed at once (the app's editor mounting twice in
    development did this): the response is cancelled before the stream's generator ever
    ran, so its `finally` never ran either, and the engine lock stayed held — every later
    query waited on it. The lock is released outside the generator now."""
    import socket
    from urllib.parse import urlsplit

    p, client, tmp_path = served
    u = urlsplit(p.catalog_url)
    body = json.dumps({"sql": "select 1 as one"}).encode()
    for _ in range(3):
        s = socket.create_connection((u.hostname, u.port))
        s.sendall(
            b"POST /api/query HTTP/1.1\r\nHost: 127.0.0.1\r\n"
            b"Authorization: Bearer " + p.token.encode() + b"\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: " + str(len(body)).encode() + b"\r\n\r\n" + body
        )
        s.close()
    t0 = time.perf_counter()
    r = client.post("/api/query", json={"sql": "select 2 as two"}, timeout=10)
    assert r.status_code == 200 and _rows(r).column("two").to_pylist() == [2]
    assert time.perf_counter() - t0 < 5


def _rows(response: httpx.Response) -> pa.Table:
    assert response.headers["content-type"].startswith("application/vnd.apache.arrow.stream")
    return pa.ipc.open_stream(response.content).read_all()


def test_estimate_and_query_stream_arrow_with_the_verdict(served) -> None:
    p, client, tmp_path = served
    client.post("/api/import", json={"path": str(tmp_path / "orders.csv")})
    sql = "select customer, count(*) as n from orders group by 1 order by 1"
    est = client.post("/api/estimate", json={"sql": sql})
    assert est.status_code == 200
    body = est.json()
    assert (
        body["verdict"] == "green" and body["line"].startswith("● Runs here") and "plan" not in body
    )

    response = client.post("/api/query", json={"sql": sql})
    assert response.status_code == 200
    assert response.headers["x-querysolo-verdict"] == "green"
    assert response.headers["x-querysolo-words"] == "Runs here"
    table = _rows(response)
    assert table.num_rows == 10 and table.column("n")[0].as_py() == 100

    bad = client.post("/api/query", json={"sql": "select * from nope"})
    assert bad.status_code == 400 and bad.json()["error"] == "sql_error"
    assert client.post("/api/query", json={"nope": 1}).status_code == 422

    runs = client.get("/api/history", params={"last": 5}).json()
    assert runs[0]["sql_text"] == "select * from nope" and runs[0]["error"]  # failures count too
    good = next(r for r in runs if r["sql_text"] == sql)
    assert good["verdict"] == "green" and good["ran"] and good["actual_wall"]


def test_the_gauge_screen_routes(served) -> None:
    """Real-data brief R8: summary, export into the project, reset, probe."""
    p, client, tmp_path = served
    client.post("/api/import", json={"path": str(tmp_path / "orders.csv")})
    _rows(client.post("/api/query", json={"sql": "select count(*) from orders"}))
    summary = client.get("/api/gauge/summary").json()
    assert summary["runs"] >= 1 and set(summary) >= {"within_2x_share", "green_over_3min"}
    exported = client.post("/api/gauge/export").json()
    assert exported["runs"] == summary["runs"] and exported["path"].startswith(str(p.root))
    from pathlib import Path

    assert "orders" not in Path(exported["path"]).read_text()
    probe = client.post("/api/gauge/probe", json={"mb": 8}).json()
    assert probe["mbps"] > 0 and probe["method"] in ("nocache", "direct", "cached")
    assert client.get("/api/health").json()["throughput_local_mbps"] == pytest.approx(probe["mbps"])
    assert client.post("/api/gauge/reset").json()["removed"] == summary["runs"]
    assert client.get("/api/gauge/summary").json()["runs"] == 0


def test_red_is_409_with_the_estimate_unless_allowed(served) -> None:
    p, client, tmp_path = served
    client.post("/api/import", json={"path": str(tmp_path / "orders.csv")})
    toml = p.root / "querysolo.toml"
    toml.write_text(
        toml.read_text()
        .replace("green_max_seconds = 60", "green_max_seconds = 0.0000001")
        .replace("yellow_max_seconds = 600", "yellow_max_seconds = 0.0000002")
    )
    p.config = type(p.config).load(toml)  # the running server re-reads its thresholds
    refused = client.post("/api/query", json={"sql": "select count(*) from orders"})
    assert refused.status_code == 409
    body = refused.json()
    assert body["error"] == "red_refused" and body["estimate"]["verdict"] == "red"
    assert "cap $" in body["estimate"]["reason"]
    allowed = client.post(
        "/api/query", json={"sql": "select count(*) from orders", "allow_red": True}
    )
    assert allowed.status_code == 200 and _rows(allowed).num_rows == 1
    assert client.get("/api/history", params={"last": 2}).json()[1]["ran_where"] == "refused"


def test_questions_over_http(served) -> None:
    p, client, tmp_path = served
    client.post("/api/import", json={"path": str(tmp_path / "orders.csv")})
    saved = client.post(
        "/api/questions",
        json={
            "title": "Revenue by customer",
            "sql": "select customer, sum(amt) as revenue from orders group by 1",
        },
    )
    assert saved.status_code == 200 and saved.json()["slug"] == "revenue_by_customer"
    assert saved.json()["last_run"] is None
    assert [q["slug"] for q in client.get("/api/questions").json()] == ["revenue_by_customer"]
    ran = client.post("/api/questions/revenue_by_customer/run")
    assert ran.status_code == 200 and _rows(ran).num_rows == 10
    assert client.get("/api/questions").json()[0]["last_run"] is not None
    assert client.post("/api/questions/nope/run").status_code == 404


def test_cors_is_for_the_tauri_origin_only(served) -> None:
    p, client, _ = served
    headers = {"Origin": "tauri://localhost", "Access-Control-Request-Method": "POST"}
    allowed = httpx.options(f"{p.catalog_url}/api/query", headers=headers)
    assert allowed.headers.get("access-control-allow-origin") == "tauri://localhost"
    other = httpx.options(
        f"{p.catalog_url}/api/query",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in other.headers


def test_serve_json_is_removed_on_close(tmp_path) -> None:
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root, serve=True)
    assert p.serve_json.exists()
    p.close()
    assert not p.serve_json.exists()


def test_the_cli_serve_from_another_process(tmp_path) -> None:
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    proc = subprocess.Popen(
        [sys.executable, "-m", "querysolo.cli", "-C", str(root), "serve"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        line = proc.stdout.readline()
        assert line.startswith("serving http://127.0.0.1:"), line
        info = json.loads((root / ".querysolo/serve.json").read_text())
        assert info["pid"] == proc.pid
        health = httpx.get(
            f"http://127.0.0.1:{info['port']}/api/health",
            headers={"Authorization": f"Bearer {info['token']}"},
        )
        assert health.status_code == 200 and health.json()["project"] == "proj"
    finally:
        proc.terminate()
        proc.wait(timeout=10)
    for _ in range(20):
        if not (root / ".querysolo/serve.json").exists():
            break
        time.sleep(0.1)
    assert not (root / ".querysolo/serve.json").exists()
    refused = CliRunner().invoke(app, ["-C", str(root), "serve", "--host", "0.0.0.0"])
    assert refused.exit_code == 1 and "loopback" in refused.output


def test_serve_memory_limit_and_the_dev_origin(tmp_path, monkeypatch) -> None:
    """App brief A8 and A12 (September 10): ``serve --memory-limit`` overrides ``[engine]``
    for this process only, and ``QUERYSOLO_DEV_ORIGIN`` joins the CORS list when set, so the
    frontend can be driven from a browser against a real sidecar; the shell never sets it."""
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    monkeypatch.setenv("QUERYSOLO_DEV_ORIGIN", "http://localhost:5173")
    with Project.open(root, serve=True, memory_limit="1GB") as p:
        token = json.loads(p.serve_json.read_text())["token"]
        health = httpx.get(
            f"{p.catalog_url}/api/health", headers={"Authorization": f"Bearer {token}"}
        )
        limit = health.json()["machine"]["memory_limit"]  # DuckDB reports 1GB as 953.6 MiB
        assert 900_000_000 <= limit <= 1_100_000_000, health.json()["machine"]
        headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"}
        allowed = httpx.options(f"{p.catalog_url}/api/query", headers=headers)
        assert allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"
        # the verdict headers are readable from the window, not just present on the wire
        run = httpx.post(
            f"{p.catalog_url}/api/query",
            json={"sql": "select 1 as one"},
            headers={"Authorization": f"Bearer {token}", "Origin": "http://localhost:5173"},
        )
        assert run.status_code == 200 and run.headers["x-querysolo-verdict"] == "green"
        exposed = run.headers.get("access-control-expose-headers", "").lower()
        assert "x-querysolo-verdict" in exposed and "x-querysolo-reason" in exposed
    monkeypatch.delenv("QUERYSOLO_DEV_ORIGIN")
    with Project.open(root, serve=True) as p:
        refused = httpx.options(
            f"{p.catalog_url}/api/query",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"},
        )
        assert "access-control-allow-origin" not in refused.headers
        assert (
            tomllib.loads((root / "querysolo.toml").read_text())["engine"]["memory_limit"] == "auto"
        )
