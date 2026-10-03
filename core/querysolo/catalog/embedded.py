# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The catalog on a loopback port, uvicorn in a thread, for the life of the process that
opened the project (brief D3, D4). Binds 127.0.0.1 only (brief D22)."""

from __future__ import annotations

import threading
import time

import uvicorn
from fastapi import FastAPI


class EmbeddedCatalog:
    def __init__(self, app: FastAPI, port: int = 0) -> None:
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning", access_log=False)
        )
        self._thread = threading.Thread(
            target=self._server.run, name="querysolo-catalog", daemon=True
        )
        self.url = ""

    def start(self, timeout: float = 5.0) -> str:
        self._thread.start()
        deadline = time.monotonic() + timeout
        while not self._server.started:
            if time.monotonic() > deadline or not self._thread.is_alive():
                raise RuntimeError("the embedded catalog did not start")
            time.sleep(0.005)
        port = self._server.servers[0].sockets[0].getsockname()[1]
        self.url = f"http://127.0.0.1:{port}"
        return self.url

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)
