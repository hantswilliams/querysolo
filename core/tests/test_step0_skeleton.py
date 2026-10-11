# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Step 0 gate: the skeleton imports, the entry point answers, the engines are the ones
the brief pins (D15), and the three DuckDB extensions load from the cache the CI warms."""

from pathlib import Path

import duckdb
import pyiceberg
import pytest
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


def test_the_extension_folder_is_used_and_nothing_is_fetched(tmp_path, monkeypatch) -> None:
    """With QUERYSOLO_EXTENSION_DIR set to a folder laid out as DuckDB expects
    (`v<version>/<platform>/<name>.duckdb_extension`; five files — `iceberg` pulls in
    `avro` on its first LOAD), every connection loads from there, `init` reports the folder
    and installs nothing, and a project answers a query — with the machine's own ~/.duckdb
    hidden, so a fallback to it would show as a failure. No installer sets it since
    decisions X1 (2026-10-11); tests and a future offline build do."""
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
    assert "using the DuckDB extensions in" in " ".join(result.output.split())
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


UNREACHABLE = "http://127.0.0.1:9"  # the freeze gate's proxy: an address that answers nothing


def _no_extensions_no_network(tmp_path, monkeypatch) -> Path:
    """An empty extension folder and every HTTP client, DuckDB's included, sent to a proxy
    that answers nothing: a first run on a machine with no network."""
    empty = tmp_path / "extensions"
    empty.mkdir()
    monkeypatch.setenv("QUERYSOLO_EXTENSION_DIR", str(empty))
    for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.setenv(key, UNREACHABLE)
    for key in ("NO_PROXY", "no_proxy"):
        monkeypatch.setenv(key, "127.0.0.1,localhost")  # the project's own catalog
    return empty


def test_init_without_the_network_makes_the_project_and_says_so(tmp_path, monkeypatch) -> None:
    """Decisions X3, X4: `init` that cannot download the extensions still makes the project,
    exits 0 and prints the sentence with DuckDB's reason; opening it tries once more and
    fails with the same sentence — in the CLI as a message, not a traceback."""
    from querysolo import Project
    from querysolo.engine import ExtensionsMissing

    _no_extensions_no_network(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    result = CliRunner().invoke(app, ["init", str(root), "--probe-mb", "0"])
    assert result.exit_code == 0, result.output
    assert (root / "querysolo.toml").exists()
    said = " ".join(result.output.split())
    assert (
        "the project is ready, but QuerySolo needs a one-time download of DuckDB's extensions "
        "(about 80 MB) from extensions.duckdb.org and could not reach it (" in said
    ), said
    assert "it will try again the next time the project opens" in said
    assert "Traceback" not in result.output

    with pytest.raises(ExtensionsMissing, match="one-time download"):
        Project.open(root)
    listed = CliRunner().invoke(app, ["-C", str(root), "tables", "list"])
    assert listed.exit_code == 1
    assert "one-time download" in " ".join(listed.output.split())
    assert listed.exception is None or isinstance(listed.exception, SystemExit)


def test_opening_a_project_without_its_extensions_downloads_them_once(
    tmp_path, monkeypatch
) -> None:
    """Decisions X3: a project whose extensions are missing gets one download when it opens,
    then works. The download is stood in for by a copy from this machine's cache (the
    suite does not fetch 80 MB); what is checked is that the open asks for it once."""
    import shutil

    import querysolo.engine as engine
    from querysolo import Project

    empty = _no_extensions_no_network(tmp_path, monkeypatch)
    root = tmp_path / "proj"
    assert CliRunner().invoke(app, ["init", str(root), "--probe-mb", "0"]).exit_code == 0

    con = duckdb.connect()
    platform = con.execute("pragma platform").fetchone()[0]
    version = con.execute("select version()").fetchone()[0]
    con.close()
    cache = Path.home() / ".duckdb" / "extensions" / version / platform
    calls = []

    def download() -> tuple[list[str], str]:
        calls.append(1)
        target = empty / version / platform
        target.mkdir(parents=True, exist_ok=True)
        for name in engine.INSTALLED_EXTENSIONS:
            shutil.copy(cache / f"{name}.duckdb_extension", target)
        return list(engine.INSTALLED_EXTENSIONS), str(empty)

    monkeypatch.setattr(engine, "install_extensions", download)
    with Project.open(root) as p:
        assert p.engine.execute("select 1").fetchone() == (1,)
    assert calls == [1]
    with Project.open(root) as p:  # there now: no second download
        assert p.engine.execute("select 1").fetchone() == (1,)
    assert calls == [1]
