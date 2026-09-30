# -*- mode: python ; coding: utf-8 -*-
# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
# The freeze (ship brief S1): PyInstaller in one-directory mode, so the frozen `querysolo`
# starts the way a venv does instead of unpacking 250 MB into a temp folder on every launch.
# `freeze/build.py` runs this, then lays the DuckDB extensions beside the result (S2) and
# trims what nothing imports (S3). Run from `core/`:
#
#   uv run --group freeze python freeze/build.py
#
# What PyInstaller cannot see on its own, and why each line is here:
# - pyiceberg loads its catalog and IO implementations by name from a string in the
#   catalog properties (`type: rest`, `py-io-impl`), never by an import statement;
# - dbt loads its adapter (`dbt.adapters.duckdb`), the adapter's plugins, and QuerySolo's own
#   plugin module (`querysolo.dbt.plugin`, named in the profile) through importlib;
# - dbt's macros are data files under `dbt/include/…`, and dbt reads its own version and
#   the adapter's from package metadata;
# - dulwich, sqlalchemy's dialects and uvicorn's workers are found by name too.
# The gate for this list is `freeze/build.py --check`: the quickstart's commands from an
# empty HOME with the network unreachable. A missing module shows there, not here.

import os
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

here = Path(SPECPATH)
core = here.parent

hidden = [
    # pyiceberg: chosen by name from catalog properties — the REST catalog and the pyarrow
    # IO are the two the core names; the others (Glue, Hive, DynamoDB, fsspec) would drag
    # boto3, s3fs and their friends in for nothing
    *collect_submodules("pyiceberg.catalog.rest"),
    "pyiceberg.io.pyarrow",
    # dbt: the adapter, its plugin loader, QuerySolo's plugin, the parsers dbt picks at runtime
    *collect_submodules("dbt.adapters.duckdb"),
    *collect_submodules("dbt.adapters"),
    *collect_submodules("dbt_common"),
    *collect_submodules("dbt.include"),
    "querysolo.dbt.plugin",
    # the rest of the core's by-name imports (SQLite is the catalog store an installer
    # carries; the Postgres dialect is the team catalog's and comes with its own server)
    *collect_submodules("dulwich"),
    *collect_submodules("sqlalchemy.dialects.sqlite"),
    *collect_submodules("uvicorn"),
    *collect_submodules("anyio._backends"),
    "psutil",
]

datas = [
    # dbt's macros and starter files, and the metadata dbt and pyiceberg read at start
    *collect_data_files("dbt", include_py_files=False),
    *collect_data_files("dbt.include", include_py_files=False),
    # dbt-duckdb lists its built-in plugins with os.listdir on its own package folder, so
    # the folder has to exist on disk, not only inside the archive
    *collect_data_files("dbt.adapters.duckdb.plugins", include_py_files=True),
    *copy_metadata("dbt-core"),
    *copy_metadata("dbt-adapters"),
    *copy_metadata("dbt-common"),
    *copy_metadata("dbt-duckdb"),
    *copy_metadata("pyiceberg"),
    *copy_metadata("querysolo"),
]

# S3's trim list, the modules: nothing in the core imports pyarrow's Flight, Substrait or
# Gandiva; their shared libraries are removed after the build by `build.py`.
excludes = [
    # optional paths the graph would follow from an installed-but-unused package: boto3
    # (pyiceberg's SigV4 and Glue paths, imported inside functions), psycopg (the Postgres
    # dialect), pyOpenSSL's cryptography (urllib3's optional contrib), the fsspec remotes
    "boto3",
    "botocore",
    "s3transfer",
    "psycopg",
    "psycopg_binary",
    "psycopg_pool",
    "cryptography",
    "OpenSSL",
    "urllib3.contrib.pyopenssl",
    "s3fs",
    "gcsfs",
    "adlfs",
    "paramiko",
    "dbt.adapters.duckdb.plugins.glue",
    "dbt.adapters.duckdb.plugins.gsheet",
    "dbt.adapters.duckdb.plugins.excel",
    "dbt.adapters.duckdb.plugins.sqlalchemy",
    "dbt.adapters.duckdb.plugins.motherduck",
    "dbt.adapters.duckdb.plugins.unity",
    "dbt.adapters.duckdb.plugins.delta",
    "dbt.adapters.duckdb.plugins.iceberg",
    "pyarrow.flight",
    "pyarrow._flight",
    "pyarrow.substrait",
    "pyarrow._substrait",
    "pyarrow.gandiva",
    "pyarrow.tests",
    "tkinter",
    "test",
    "pydoc_data",
    "moto",
    "pytest",
    "IPython",
    "matplotlib",
    "numpy.testing",
]

a = Analysis(
    [str(here / "entry.py")],
    pathex=[str(core)],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="querysolo",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="querysolo",
)
