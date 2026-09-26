# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""The frozen program's entry point (ship brief S1, S2). One job before the CLI runs: name
the bundled DuckDB extensions, which the freeze lays out beside this executable as
``extensions/v<version>/<platform>/<name>.duckdb_extension``, so every connection reads
them from there and the installed app never downloads. A `LAKELET_EXTENSION_DIR` already
in the environment wins, which is how a test points the binary elsewhere."""

from __future__ import annotations

import multiprocessing
import os
import sys


def main() -> None:
    if getattr(sys, "frozen", False) and "LAKELET_EXTENSION_DIR" not in os.environ:
        here = os.path.dirname(os.path.abspath(sys.executable))
        bundled = os.path.join(here, "extensions")
        if os.path.isdir(bundled):
            os.environ["LAKELET_EXTENSION_DIR"] = bundled
    from lakelet.cli import run

    run()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
