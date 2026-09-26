# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""Ship brief step 0's gate, against a frozen binary: `LAKELET_BIN=dist/lakelet/lakelet
uv run pytest tests/test_frozen.py`. Skipped when the variable is unset, so the ordinary
suite is unchanged; CI's release job sets it after the freeze. The gate itself is
`freeze/build.py --check` — the quickstart from an empty HOME with the network unreachable,
including `lakelet run` (dbt) and `audit network` reading zero — and this runs it."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

BIN = os.environ.get("LAKELET_BIN")
pytestmark = pytest.mark.skipif(not BIN, reason="LAKELET_BIN names no frozen binary")
CORE = Path(__file__).resolve().parent.parent


def test_the_frozen_binary_answers_and_names_its_version() -> None:
    import lakelet

    r = subprocess.run([BIN, "--version"], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and r.stdout.strip() == f"lakelet {lakelet.__version__}"


def test_the_quickstart_runs_from_an_empty_home_with_no_network() -> None:
    r = subprocess.run(
        [sys.executable, "freeze/build.py", "--check"],
        cwd=CORE,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert r.returncode == 0, r.stdout[-4000:] + r.stderr[-2000:]
    assert "nothing left the machine" in r.stdout
    assert "check: the quickstart ran" in r.stdout
