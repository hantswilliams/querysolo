# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Build the frozen core (ship brief S1–S3) in three steps, from `core/`:

    uv run --group freeze python freeze/build.py            # freeze, extensions, trim, sizes
    uv run --group freeze python freeze/build.py --check    # then run the quickstart from an
                                                            # empty HOME with no network

1. PyInstaller on `freeze/querysolo.spec` → `dist/querysolo/` (the executable and `_internal/`).
2. The DuckDB extensions the core needs, for the running DuckDB's exact version and this
   platform, laid out as DuckDB expects under `dist/querysolo/extensions/` (S2): copied from
   this machine's `~/.duckdb/extensions` (or `--extensions-from <dir>`) when they are
   there, else downloaded by DuckDB itself. Five files: the four the engine loads and
   `avro`, which `iceberg` pulls in.
3. The trim S3 fixes in advance: pyarrow's Flight, Substrait and Gandiva libraries, its
   tests and headers — nothing in the core imports them. `--no-trim` keeps them, to
   measure the difference.

The sizes before and after the trim are printed and belong in the session log."""

from __future__ import annotations

import argparse
import os
import platform as platform_module
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CORE = Path(__file__).resolve().parent.parent
DIST = CORE / "dist" / "querysolo"

# S3's trim list, the files: pyarrow's optional libraries and what only its own tests need.
TRIM_GLOBS = [
    "_internal/pyarrow/libarrow_flight*",
    "_internal/pyarrow/libarrow_python_flight*",
    # not libarrow_substrait: pyarrow's core `lib` module links against it (S3's list
    # assumed it was optional; it is 6 MB and stays)
    "_internal/pyarrow/libgandiva*",
    "_internal/pyarrow/_flight*",
    "_internal/pyarrow/_substrait*",
    "_internal/pyarrow/gandiva*",
    "_internal/pyarrow/tests",
    "_internal/pyarrow/include",
    "_internal/pyarrow/src",
    "_internal/zstandard/_cffi*",  # the C backend is what runs; the cffi one is a second copy
]
# babel (dbt's agate uses it to parse numbers) ships locale data for every language on
# earth, 30 MB; the core formats nothing localised, so the root and English files stay.
BABEL_KEEP = {"root.dat", "en.dat", "en_US.dat", "en_001.dat", "en_150.dat"}


def duckdb_target() -> tuple[str, str, list[str]]:
    """The DuckDB version and platform string the running interpreter's DuckDB reports,
    and the extensions to bundle — from the same package the freeze carries."""
    import duckdb

    from querysolo.engine import INSTALLED_EXTENSIONS

    con = duckdb.connect()
    version = con.execute("select version()").fetchone()[0]
    target = con.execute("pragma platform").fetchone()[0]
    con.close()
    return version, target, list(INSTALLED_EXTENSIONS)


def freeze() -> None:
    print("1. PyInstaller", flush=True)
    subprocess.run(
        [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "freeze/querysolo.spec"],
        cwd=CORE,
        check=True,
    )


def lay_out_extensions(source: Path | None) -> Path:
    """The five extensions under ``dist/querysolo/extensions/``, laid out by DuckDB itself:
    ``SET extension_directory`` to the bundle folder and ``INSTALL`` each, so the download,
    the checksum and the layout are DuckDB's own (its extension CDN refuses a plain
    ``urllib`` client, and the layout has changed between versions). With
    ``--extensions-from``, copied from a folder already laid out that way instead."""
    import duckdb

    version, target, names = duckdb_target()
    root = DIST / "extensions"
    folder = root / version / target
    folder.mkdir(parents=True, exist_ok=True)
    print(f"2. DuckDB extensions {version} {target}: {', '.join(names)}", flush=True)
    missing = [name for name in names if not (folder / f"{name}.duckdb_extension").exists()]
    if not missing:
        return folder
    # first, the machine's own cache (`~/.duckdb/extensions`, where `querysolo init` and the
    # app put them, or `--extensions-from`): same files, no download
    cache = source or Path.home() / ".duckdb" / "extensions"
    for name in list(missing):
        cached = cache / version / target / f"{name}.duckdb_extension"
        if cached.exists():
            shutil.copy(cached, folder)
            missing.remove(name)
    if not missing:
        return folder
    con = duckdb.connect()
    con.execute("SET extension_directory = ?", [str(root)])
    try:
        con.execute("; ".join(f"INSTALL {name}" for name in missing))
    except duckdb.HTTPException as e:
        # DuckDB's own downloader speaks plain http and follows no redirect; a network that
        # answers 302 (http→https) needs httpfs loaded, then the https repository
        print(f"   plain http failed ({str(e).splitlines()[0]}); trying https", flush=True)
        con.execute("LOAD httpfs")
        con.execute(
            "; ".join(f"INSTALL {name} FROM 'https://extensions.duckdb.org'" for name in missing)
        )
    con.close()
    for name in names:
        if not (folder / f"{name}.duckdb_extension").exists():
            raise SystemExit(f"DuckDB did not install {name} into {folder}")
    return folder


def folder_size(path: Path) -> int:
    """Bytes on disk, each file once (pyarrow's libraries have symlinked aliases)."""
    seen: set[int] = set()
    total = 0
    for f in path.rglob("*"):
        if f.is_file() and not f.is_symlink():
            st = f.stat()
            if st.st_ino not in seen:
                seen.add(st.st_ino)
                total += st.st_size
    return total


def trim() -> None:
    print("3. trim (S3): pyarrow's Flight, Substrait, Gandiva, tests and headers", flush=True)
    for pattern in TRIM_GLOBS:
        for path in DIST.glob(pattern):
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    # PyInstaller keeps pyarrow's shared libraries in `_internal/pyarrow/` and links each
    # into `_internal/` under a second name. Tauri's bundler copies a symlink as a file,
    # which would carry pyarrow twice (+100 MB installed), so no symlink survives the trim.
    # Which name the loader wants differs: on Linux the modules' runpath is `$ORIGIN`
    # (`pyarrow/`), so the links simply go; on macOS PyInstaller rewrites every rpath to
    # `@loader_path/..` (`_internal/`), so the file moves to where the link was. The
    # `--check` gate is what proves it on each platform.
    for path in DIST.rglob("*"):
        if path.is_symlink():
            target = path.resolve()
            path.unlink()
            if platform_module.system() == "Darwin" and target.is_file():
                shutil.move(target, path)
    locale_data = DIST / "_internal" / "babel" / "locale-data"
    if locale_data.is_dir():
        for path in locale_data.iterdir():
            if path.name not in BABEL_KEEP:
                path.unlink()


def check() -> int:
    """The gate: the quickstart's commands from an empty HOME with the network unreachable,
    against the frozen binary. Any fetch, any missing module, any wrong path fails here."""
    default = DIST / ("querysolo.exe" if platform_module.system() == "Windows" else "querysolo")
    exe = Path(os.environ.get("QUERYSOLO_BIN") or default)
    if not exe.exists():
        print(f"no frozen binary at {exe}; run without --check first")
        return 2
    sample = CORE.parent / "examples" / "sample-data" / "make_sample.py"
    with tempfile.TemporaryDirectory() as tmp:
        home = Path(tmp) / "home"
        home.mkdir()
        data = Path(tmp) / "sample"
        subprocess.run([sys.executable, str(sample), str(data)], check=True, capture_output=True)
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": str(home),
            "USERPROFILE": str(home),
            # the network, unreachable: every HTTP client honours these, and the proxy
            # address answers nothing
            "HTTP_PROXY": "http://127.0.0.1:9",
            "HTTPS_PROXY": "http://127.0.0.1:9",
            "http_proxy": "http://127.0.0.1:9",
            "https_proxy": "http://127.0.0.1:9",
            "NO_PROXY": "127.0.0.1,localhost",
            "no_proxy": "127.0.0.1,localhost",
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
        }
        for key in ("QUERYSOLO_EXTENSION_DIR", "TMPDIR", "TEMP", "TMP", "SYSTEMROOT"):
            if key in os.environ:
                env[key] = os.environ[key]
        project = Path(tmp) / "acme"
        steps = [
            ["init", str(project), "--probe-mb", "0"],
            ["-C", str(project), "import", str(data / "orders.csv")],
            ["-C", str(project), "tables", "list"],
            ["-C", str(project), "sql", "select region, count(*) from orders group by 1"],
            [
                "-C",
                str(project),
                "question",
                "save",
                "By region",
                "--sql",
                "select region, count(*) as n from orders group by 1",
            ],
            ["-C", str(project), "run"],
            ["-C", str(project), "lineage", "--all"],
            ["-C", str(project), "audit", "network"],
        ]
        for args in steps:
            print(f"   querysolo {' '.join(args)}", flush=True)
            r = subprocess.run([str(exe), *args], env=env, capture_output=True, text=True, cwd=tmp)
            if r.returncode != 0:
                print(r.stdout[-3000:])
                print(r.stderr[-3000:])
                print(f"FAILED: querysolo {' '.join(args)} exited {r.returncode}")
                return 1
            if args[0] == "init" and "bundled DuckDB extensions" not in r.stdout:
                print(r.stdout)
                print("FAILED: init did not use the bundled extensions")
                return 1
            if args[-1] == "network" and "0 " not in r.stdout and "no " not in r.stdout.lower():
                print(r.stdout)
        print("check: the quickstart ran from an empty HOME with no network")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check", action="store_true", help="run the gate against an existing dist/querysolo"
    )
    parser.add_argument("--no-trim", action="store_true", help="keep pyarrow's optional libraries")
    parser.add_argument(
        "--extensions-from",
        type=Path,
        help="copy the extensions from a folder laid out like ~/.duckdb/extensions "
        "instead of downloading",
    )
    args = parser.parse_args()
    if args.check:
        return check()
    freeze()
    lay_out_extensions(args.extensions_from)
    before = folder_size(DIST)
    if not args.no_trim:
        trim()
    after = folder_size(DIST)
    print(f"dist/querysolo: {before / 1e6:,.0f} MB before the trim, {after / 1e6:,.0f} MB after")
    return 0


if __name__ == "__main__":
    sys.exit(main())
