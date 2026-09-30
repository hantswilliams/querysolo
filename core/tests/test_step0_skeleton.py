# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 0 gate: the skeleton imports, the entry point answers, the engines are the ones
the brief pins (D15), and the three DuckDB extensions load from the cache the CI warms."""

from pathlib import Path

import duckdb
import pyiceberg
from typer.testing import CliRunner

import querysolo
from querysolo.cli import app


def test_package_has_a_version() -> None:
    assert querysolo.__version__


def test_cli_prints_the_version() -> None:
    result = CliRunner().invoke(app, ["--version"])
    assert result.exit_code == 0
    assert result.output.strip() == f"querysolo {querysolo.__version__}"


def test_engine_versions_match_the_brief() -> None:
    major, minor = (int(part) for part in duckdb.__version__.split(".")[:2])
    assert (major, minor) == (1, 5), duckdb.__version__
    assert pyiceberg.__version__.startswith("0.12."), pyiceberg.__version__


def test_the_three_extensions_load() -> None:
    con = duckdb.connect()
    con.execute("INSTALL iceberg; INSTALL httpfs; INSTALL excel; INSTALL aws")
    con.execute("LOAD iceberg; LOAD httpfs; LOAD excel; LOAD aws")
    loaded = {
        name
        for (name,) in con.execute(
            "select extension_name from duckdb_extensions() where loaded"
        ).fetchall()
    }
    assert {"iceberg", "httpfs", "excel", "aws"} <= loaded


def test_the_bundled_extension_folder_is_used_and_nothing_is_fetched(tmp_path, monkeypatch) -> None:
    """Ship brief S2: with QUERYSOLO_EXTENSION_DIR set to a folder laid out as DuckDB expects
    (`v<version>/<platform>/<name>.duckdb_extension`; five files — `iceberg` pulls in
    `avro` on its first LOAD, which the bundle must carry), every connection loads from there,
    `init` reports "bundled" and installs nothing, and a project answers a query — with
    the machine's own ~/.duckdb hidden, so a fallback to it would show as a failure."""
    import shutil

    from querysolo import Project
    from querysolo.engine import INSTALLED_EXTENSIONS, connect

    con = duckdb.connect()
    platform = con.execute("pragma platform").fetchone()[0]
    version = con.execute("select version()").fetchone()[0]
    source = con.execute("select current_setting('extension_directory')").fetchone()[0] or str(
        Path.home() / ".duckdb" / "extensions"
    )
    con.close()
    bundled = tmp_path / "extensions" / version / platform
    bundled.mkdir(parents=True)
    for name in INSTALLED_EXTENSIONS:
        shutil.copy(f"{source}/{version}/{platform}/{name}.duckdb_extension", bundled)

    monkeypatch.setenv("QUERYSOLO_EXTENSION_DIR", str(tmp_path / "extensions"))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))  # no ~/.duckdb to fall back to
    (tmp_path / "home").mkdir()
    loaded = {
        name
        for (name,) in connect()
        .execute("LOAD iceberg; select extension_name from duckdb_extensions() where loaded")
        .fetchall()
    }
    assert "iceberg" in loaded

    root = tmp_path / "proj"
    result = CliRunner().invoke(app, ["init", str(root), "--probe-mb", "0"])
    assert result.exit_code == 0, result.output
    assert "using the bundled DuckDB extensions" in " ".join(result.output.split())
    assert "installed DuckDB extensions" not in result.output
    with Project.open(root) as p:
        assert p.engine.execute("select 1").fetchone() == (1,)


def test_the_app_and_the_core_agree_on_the_version() -> None:
    """Ship brief S7: one version, in `querysolo/__init__.py`; the app's `tauri.conf.json` and
    `Cargo.toml` carry the same release (major.minor.patch). The pre-release tag is spelled
    per ecosystem — `0.1.0.dev0` / `0.1.0rc1` in PEP 440, `0.1.0-rc.1` in semver — so the
    triple is what must agree, and a core with no pre-release tag needs the app to have none."""
    import json
    import re
    import tomllib
    from pathlib import Path

    app_dir = Path(__file__).resolve().parents[2] / "app" / "src-tauri"
    tauri = json.loads((app_dir / "tauri.conf.json").read_text(encoding="utf-8"))["version"]
    cargo_toml = tomllib.loads((app_dir / "Cargo.toml").read_text(encoding="utf-8"))
    cargo = cargo_toml["package"]["version"]
    core = querysolo.__version__
    triple = lambda v: re.match(r"(\d+\.\d+\.\d+)", v).group(1)  # noqa: E731
    assert triple(core) == triple(tauri) == triple(cargo), (core, tauri, cargo)
    core_is_release = re.fullmatch(r"\d+\.\d+\.\d+", core) is not None
    app_is_release = "-" not in tauri and "-" not in cargo
    if core_is_release:
        assert app_is_release, (core, tauri, cargo)
