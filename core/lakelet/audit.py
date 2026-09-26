# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""``lakelet audit network`` (brief D33, §6 "nothing hidden"): run the local quickstart in
a throwaway project with every outbound connection blocked, and report each attempt.

Two layers are watched. Python sockets are patched so any connection to a non-loopback
address is recorded and refused. DuckDB has its own HTTP client, so the engine is pointed at
a small loopback proxy (``SET http_proxy``) that forwards loopback targets and records and
refuses everything else; every DuckDB request passes through it. Both guards check
themselves before the quickstart runs, so a reported zero is a measured zero.

The audit refuses to run if the extensions are not installed yet, because their one-time
download would happen below the guards and go unseen.
"""

from __future__ import annotations

import http.client
import os
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
SELF_CHECK_HOST = "203.0.113.1"  # TEST-NET-3: never routable


def _where(address: object) -> str:
    if isinstance(address, tuple) and len(address) >= 2:
        return f"{address[0]}:{address[1]}"
    return str(address)


def _guard_sockets(attempts: list[str]) -> None:
    real_connect = socket.socket.connect
    real_connect_ex = socket.socket.connect_ex

    def blocked(address: object) -> bool:
        host = address[0] if isinstance(address, tuple) else str(address)
        return str(host) not in LOOPBACK

    def connect(self, address, *args, **kwargs):
        if blocked(address):
            attempts.append(_where(address))
            raise OSError(f"lakelet audit: outbound connection to {_where(address)} blocked")
        return real_connect(self, address, *args, **kwargs)

    def connect_ex(self, address, *args, **kwargs):
        if blocked(address):
            attempts.append(_where(address))
            return 111
        return real_connect_ex(self, address, *args, **kwargs)

    socket.socket.connect = connect  # type: ignore[method-assign]
    socket.socket.connect_ex = connect_ex  # type: ignore[method-assign]


def _start_proxy(attempts: list[str]) -> str:
    """A forwarding proxy on a loopback port for DuckDB's HTTP client."""

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _handle(self) -> None:
            if self.command == "CONNECT":
                host, _, port = self.path.partition(":")
                target = None
            else:
                target = urlsplit(self.path)
                host, port = target.hostname or "", target.port or 80
            if host not in LOOPBACK or target is None:
                attempts.append(f"{self.command} {host}:{port}")
                self.send_error(403, "lakelet audit: blocked")
                return
            length = int(self.headers.get("Content-Length", 0) or 0)
            body = self.rfile.read(length) if length else None
            headers = {
                k: v
                for k, v in self.headers.items()
                if k.lower() not in ("proxy-connection", "connection")
            }
            path = target.path or "/"
            if target.query:
                path += "?" + target.query
            upstream = http.client.HTTPConnection(host, int(port), timeout=60)
            upstream.request(self.command, path, body=body, headers=headers)
            response = upstream.getresponse()
            data = response.read()
            self.send_response(response.status)
            for k, v in response.getheaders():
                if k.lower() not in ("transfer-encoding", "connection", "content-length"):
                    self.send_header(k, v)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(data)
            self.close_connection = True

        do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_CONNECT = _handle

        def log_message(self, *_args) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return f"127.0.0.1:{server.server_address[1]}"


def _build_models(project) -> str:
    """`lakelet run` is the one verb that hands the work to someone else's code, and dbt
    sends anonymous usage statistics unless it is told not to (versions brief G11), so the
    audit has to run it or the reported zero is only about Lakelet's own code."""
    from lakelet.dbt.runner import DbtMissing, run

    try:
        report = run(project)
    except DbtMissing:
        return "not run: dbt is not installed (`pip install 'lakelet[dbt]'`)"
    except Exception as e:  # noqa: BLE001 - the numbers below are still worth reporting
        return f"failed: {type(e).__name__}: {str(e).splitlines()[0]}"
    return f"{len(report.results)} model(s) built"


def main() -> int:
    import duckdb

    from lakelet.engine import INSTALLED_EXTENSIONS, connect

    installed = {
        name
        for (name,) in connect()
        .execute("select extension_name from duckdb_extensions() where installed")
        .fetchall()
    }

    missing = set(INSTALLED_EXTENSIONS) - installed
    if missing:
        names = ", ".join(sorted(missing))
        print(f"cannot audit: extensions not installed yet ({names}); run `lakelet init` once")
        return 1

    python_attempts: list[str] = []
    duckdb_attempts: list[str] = []
    _guard_sockets(python_attempts)
    os.environ["LAKELET_HTTP_PROXY"] = _start_proxy(duckdb_attempts)

    # Self-checks: both guards must see and stop a deliberate attempt.
    try:
        socket.create_connection((SELF_CHECK_HOST, 80), timeout=1)
    except OSError:
        pass
    python_ok = python_attempts == [f"{SELF_CHECK_HOST}:80"]
    python_attempts.clear()

    from lakelet import Project

    root = Path(tempfile.mkdtemp()) / "audit"
    Project.init(root, probe_mb=8)
    with Project.open(root) as p:
        try:
            p.engine.execute(f"select * from read_parquet('http://{SELF_CHECK_HOST}/x.parquet')")
        except duckdb.Error:
            pass
        duckdb_ok = any(SELF_CHECK_HOST in a for a in duckdb_attempts)
        duckdb_attempts.clear()

        csv = root / "orders.csv"
        p.engine.execute(
            f"COPY (SELECT range AS id, 'c' || (range % 10) AS customer, range * 1.5 AS amt "
            f"FROM range(10000)) TO '{csv}' (HEADER)"
        )
        p.tables.import_file(csv)
        p.estimate("select customer, sum(amt) from orders group by 1")
        list(p.query("select count(*) from orders"))
        p.questions.save("Revenue by customer", "select customer, sum(amt) from orders group by 1")
        list(p.questions.run("revenue_by_customer"))
        dbt = _build_models(p)

    print("quickstart ran: init, import, estimate, sql, question save, question run")
    print(f"lakelet run, which invokes dbt: {dbt}")
    print(f"self-check, python socket guard: {'ok' if python_ok else 'FAILED'}")
    print(f"self-check, duckdb http proxy: {'ok' if duckdb_ok else 'FAILED'}")
    print(f"python outbound connection attempts: {len(python_attempts)}")
    for attempt in python_attempts:
        print(f"  {attempt}")
    print(f"duckdb http requests beyond loopback: {len(duckdb_attempts)}")
    for attempt in duckdb_attempts[:20]:
        print(f"  {attempt}")
    ok = python_ok and duckdb_ok and not python_attempts and not duckdb_attempts
    print(
        "nothing left the machine"
        if ok
        else "something tried to leave the machine, or a guard failed"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
