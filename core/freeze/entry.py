# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The frozen program's entry point (ship brief S1, S2). One job before the CLI runs: when
an ``extensions/v<version>/<platform>/<name>.duckdb_extension`` folder sits beside this
executable, name it, so every connection reads the extensions from there. The freeze no
longer lays one out (decisions X1, 2026-10-11: Apple cannot sign a DuckDB extension, so
`init` downloads them); a future offline build would. A `QUERYSOLO_EXTENSION_DIR` already
in the environment wins, which is how a test points the binary elsewhere."""

from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> None:
    if getattr(sys, "frozen", False) and "QUERYSOLO_EXTENSION_DIR" not in os.environ:
        here = os.path.dirname(os.path.abspath(sys.executable))
        bundled = os.path.join(here, "extensions")
        if os.path.isdir(bundled):
            os.environ["QUERYSOLO_EXTENSION_DIR"] = bundled
    from querysolo.cli import run

    run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
