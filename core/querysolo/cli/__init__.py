# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The ``querysolo`` command (brief §3.6, D17, D22, D28, D33): one verb per core operation
with the same name and arguments. The gauge line goes to stderr and results to stdout, a
table on a terminal and CSV when piped, so it pipes (PRD F0.6.2). Exit codes: 0 ok, 1
anything else, 2 Red refused, 4 catalog conflict after retries (D23)."""

from __future__ import annotations

import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from querysolo import __version__

app = typer.Typer(no_args_is_help=True, add_completion=False, rich_markup_mode=None)
tables_app = typer.Typer(no_args_is_help=True, help="List, describe and sample tables.")
catalog_app = typer.Typer(no_args_is_help=True, help="The Iceberg REST catalog.")
question_app = typer.Typer(no_args_is_help=True, help="Saved questions: dbt models with checks.")
gauge_app = typer.Typer(no_args_is_help=True, help="The gauge's record.")
audit_app = typer.Typer(no_args_is_help=True, help="Prove what leaves the machine.")
config_app = typer.Typer(no_args_is_help=True, help="The settings in querysolo.toml.")
bucket_app = typer.Typer(no_args_is_help=True, help="A bucket you own, before a project uses it.")
for name, sub in (
    ("tables", tables_app),
    ("catalog", catalog_app),
    ("question", question_app),
    ("gauge", gauge_app),
    ("audit", audit_app),
    ("config", config_app),
    ("bucket", bucket_app),
):
    app.add_typer(sub, name=name)

out = Console()
err = Console(stderr=True)
PROJECT_ENV = "QUERYSOLO_PROJECT"
EXIT_RED = 2
EXIT_CONFLICT = 4
VERDICT_STYLE = {"green": "green", "yellow": "yellow", "red": "red", "none": "dim"}


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"querysolo {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version", callback=_print_version, is_eager=True, help="Print the version and exit."
        ),
    ] = False,
    project: Annotated[
        Path | None,
        typer.Option("--project", "-C", help="The project folder; the current folder by default."),
    ] = None,
    profile: Annotated[
        str | None,
        typer.Option(
            "--profile",
            metavar="<name>",
            help="The AWS profile for a private bucket, as AWS_PROFILE names it.",
        ),
    ] = None,
) -> None:
    """Your laptop is the warehouse until it can't be."""
    if project is not None:
        os.environ[PROJECT_ENV] = str(project)
    if profile is not None:
        os.environ["AWS_PROFILE"] = profile


def _migrate(root: Path) -> None:
    """Rename a project made before the rename, for the commands that read querysolo.toml
    without opening the project (layout.py)."""
    from querysolo.layout import LayoutConflict, migrate

    try:
        migrate(root)
    except LayoutConflict as e:
        _fail(str(e))


def _root() -> Path:
    return Path(os.environ.get(PROJECT_ENV, ".")).resolve()


def _open():
    from querysolo import Project
    from querysolo.project import NotAProject
    from querysolo.schema import SchemaTooNew

    from querysolo.layout import LayoutConflict

    try:
        return Project.open(_root())
    except LayoutConflict as e:
        err.print(f"[red]cannot open:[/red] {e}")
        raise typer.Exit(1) from None
    except NotAProject:
        err.print(
            f"[red]not a QuerySolo project:[/red] no querysolo.toml in {_root()}; run `querysolo init`"
        )
        raise typer.Exit(1) from None
    except SchemaTooNew as e:
        err.print(f"[red]cannot open:[/red] {e}")
        raise typer.Exit(1) from None


def _sql_text(sql: str | None, file: Path | None) -> str:
    if file is not None:
        return file.read_text(encoding="utf-8")
    if sql:
        return sql
    err.print("[red]give the SQL as an argument or with -f file.sql[/red]")
    raise typer.Exit(1)


def _gauge_line(estimate) -> None:
    from querysolo.gauge.verdict import DOTS

    style = VERDICT_STYLE[estimate.verdict]
    dot = DOTS.get(estimate.verdict, "●")
    err.print(f"[{style}]{dot}[/{style}] {estimate.words} · {estimate.reason}", highlight=False)


def _fail(message: str, code: int = 1) -> None:
    err.print(f"[red]{message}[/red]", highlight=False)
    raise typer.Exit(code)


# -- init ---------------------------------------------------------------------------


@app.command()
def init(
    directory: Annotated[Path, typer.Argument(help="The folder to turn into a lakehouse.")] = Path(
        "."
    ),
    name: Annotated[
        str | None, typer.Option(help="Project name; the folder's name by default.")
    ] = None,
    probe_mb: Annotated[
        int, typer.Option(help="Size of the disk-throughput probe; 0 skips it.")
    ] = 512,
    warehouse: Annotated[
        str | None,
        typer.Option(
            "--warehouse",
            help="An s3://bucket/prefix for the tables' files; warehouse/ by default.",
        ),
    ] = None,
) -> None:
    """Turn a folder into a lakehouse: catalog, warehouse, querysolo.toml, AGENTS.md, dbt project."""
    from querysolo import Project
    from querysolo.project import ProjectExists

    try:
        report = Project.init(directory, name=name, probe_mb=probe_mb, warehouse=warehouse)
    except ProjectExists:
        _fail(f"{Path(directory).resolve()} is already a QuerySolo project")
    except ValueError as e:
        _fail(str(e))
    for relative in report.created:
        out.print(f"  {relative}", highlight=False)
    if report.repository == "existing":
        out.print(
            "  this folder is already in a git repository; saves will commit there",
            highlight=False,
        )
    elif report.commit:
        from querysolo.versions import short

        out.print(
            f"  a git repository on branch main, first version {short(report.commit)} "
            '"querysolo init"; every save is a version from here',
            highlight=False,
        )
    if report.git:
        out.print(f"  git: {report.git}", highlight=False)
    if report.extensions_installed:
        out.print(
            f"  installed DuckDB extensions {', '.join(report.extensions_installed)} into "
            f"{report.extension_directory} (the one download; nothing else fetches at query time)",
            highlight=False,
        )
    elif os.environ.get("QUERYSOLO_EXTENSION_DIR"):
        out.print(
            f"  using the bundled DuckDB extensions in {report.extension_directory} (no download)",
            highlight=False,
        )
    else:
        out.print(f"  DuckDB extensions already in {report.extension_directory}", highlight=False)
    if report.throughput_local_mbps and report.throughput_probe == "cached":
        out.print(
            f"  local disk reads at up to {report.throughput_local_mbps:,.0f} MB/s "
            "(measured through the cache; the disk itself could not be measured here)",
            highlight=False,
        )
    elif report.throughput_local_mbps:
        out.print(
            f"  local disk reads at {report.throughput_local_mbps:,.0f} MB/s", highlight=False
        )
    if warehouse:
        out.print(
            f"  every table's files go to {warehouse} (the catalog stays in .querysolo/); "
            "the AWS credential chain is read from the environment",
            highlight=False,
        )
    out.print(f"lakehouse ready in {report.root}", highlight=False)


# -- import and tables -----------------------------------------------------------


def _print_preview(preview) -> None:
    t = Table(title=f"{preview.source} → {preview.name}", show_lines=False)
    for column in ("column", "duckdb type", "iceberg type", "note"):
        t.add_column(column)
    for c in preview.columns:
        t.add_row(c.name, c.duckdb_type, c.iceberg_type, c.note)
    out.print(t)
    sample = Table(title="first rows")
    for c in preview.columns:
        sample.add_column(c.name)
    for row in preview.sample:
        sample.add_row(*[str(v) for v in row])
    out.print(sample)


def _human_bytes(n: int) -> str:
    from querysolo.gauge.verdict import human_bytes

    return human_bytes(n)


@app.command("import")
def import_(
    path: Annotated[
        Path, typer.Argument(help="A .csv .tsv .parquet .json .jsonl .xlsx file, or a folder.")
    ],
    name: Annotated[
        str | None, typer.Option(help="Table name; from the file name by default.")
    ] = None,
    replace: Annotated[
        bool, typer.Option("--replace", help="Drop and recreate an existing table.")
    ] = False,
    append: Annotated[bool, typer.Option("--append", help="Append to an existing table.")] = False,
    preview: Annotated[
        bool, typer.Option("--preview", help="Show the inferred schema and stop.")
    ] = False,
) -> None:
    """Import a file or a folder of files into Iceberg tables."""
    from querysolo.tables import ReservedName, TableExists, UnsupportedFile

    if replace and append:
        _fail("--replace and --append are exclusive")
    mode = "replace" if replace else "append" if append else "create"
    with _open() as p:
        try:
            if preview:
                previews = (
                    p.tables.preview_dir(path)
                    if path.is_dir()
                    else [p.tables.preview(path, name=name)]
                )
                for pv in previews:
                    _print_preview(pv)
                return
            infos = (
                p.tables.import_dir(path, mode=mode)
                if path.is_dir()
                else [p.tables.import_file(path, name=name, mode=mode)]
            )
        except TableExists as e:
            _fail(f"table {e} exists; --replace drops and recreates it, --append adds to it")
        except (UnsupportedFile, FileNotFoundError, ReservedName) as e:
            _fail(str(e))
    for info in infos:
        out.print(
            f"{info.name}: {info.rows:,} rows, {_human_bytes(info.bytes)}, "
            f"{len(info.columns)} columns",
            highlight=False,
        )


@tables_app.command("list")
def tables_list() -> None:
    """Tables in the catalog with rows, size, when they were last written, and location."""
    with _open() as p:
        infos = p.tables.list()
    t = Table()
    for column in ("table", "rows", "size", "columns", "updated", "where"):
        t.add_column(column)
    for i in infos:
        t.add_row(
            i.name,
            f"{i.rows:,}",
            _human_bytes(i.bytes),
            str(len(i.columns)),
            i.freshness.isoformat(timespec="seconds") if i.freshness else "",
            _where(i),
        )
    out.print(t)
    moved = [i.name for i in infos if i.needs_relocate]
    if moved:
        from querysolo import relocate as relocation

        with _open() as p:
            old = relocation.moved_from(p)
        out.print(
            f"this project was moved from {old}; {len(moved)} table(s) point at it "
            f"({', '.join(moved)}): `querysolo relocate` updates them",
            highlight=False,
            soft_wrap=True,  # a path is copied, so it is never broken across lines
        )
    for i in infos:
        if i.interrupted_replace_of:
            out.print(
                f"{i.name}: a replace of {i.interrupted_replace_of} was interrupted; "
                f"`querysolo tables rename {i.name} {i.interrupted_replace_of}` finishes it",
                highlight=False,
            )


@tables_app.command("rename")
def tables_rename(old: str, new: str) -> None:
    """Rename a table: one catalog commit, the data does not move. Finishes a replace that
    was interrupted between its drop and its rename."""
    from querysolo.tables import NoSuchTable, TableExists

    with _open() as p:
        try:
            info = p.tables.rename(old, new)
        except NoSuchTable:
            _fail(f"no table named {old}")
        except TableExists:
            _fail(f"table {new} exists")
    out.print(f"{old} is now {info.name}: {info.rows:,} rows", highlight=False)


def _where(i) -> str:
    """The list's last column: where the data is, not where the metadata is."""
    if i.kind == "view":
        return "view"
    if i.source:
        return ("public " if i.public else "attached ") + i.source
    return "local" if i.location.startswith("file://") else i.location


@tables_app.command("describe")
def tables_describe(name: str) -> None:
    """Columns, types, partitioning, freshness and the last commit of a table."""
    from querysolo.tables import NoSuchTable

    with _open() as p:
        try:
            d = p.tables.describe(name)
        except NoSuchTable:
            _fail(f"no table named {name}")
    out.print(
        f"{d.name}: {d.rows:,} rows, {_human_bytes(d.bytes)}, {d.snapshots} snapshot(s), "
        f"Iceberg v{d.format_version}",
        highlight=False,
    )
    out.print(f"partitioning: {d.partitioning}", highlight=False)
    if d.expirable_snapshots:
        out.print(
            f"{d.expirable_snapshots} snapshot(s) older than {d.keep_days} days, "
            f"{_human_bytes(d.reclaimable_bytes)} reclaimable: querysolo tables expire {d.name}",
            highlight=False,
        )
    if d.local_copy_files:
        out.print(
            f"local copy: {d.local_copy_files} file(s) still under the warehouse: "
            f"querysolo tables expire {d.name}",
            highlight=False,
        )
    if d.freshness:
        out.print(
            f"freshness: {d.freshness.isoformat(timespec='seconds')}  "
            f"last commit: {d.last_commit.get('operation')} {d.last_commit.get('snapshot_id')}",
            highlight=False,
        )
    if d.source:
        if d.verify_error:
            out.print(f"files: not verified ({d.verify_error})", highlight=False)
        elif d.changed_files:
            names = ", ".join(f"{uri} ({why})" for uri, why in d.changed_files[:5])
            out.print(
                f"files: {len(d.changed_files)} changed under the same path since the attach: "
                f"{names}; querysolo tables attach --replace {d.name} {d.source}",
                highlight=False,
            )
        else:
            out.print(f"files: verified against {d.source} at {d.verified_at}", highlight=False)
    t = Table()
    t.add_column("column")
    t.add_column("type")
    for c, typ in d.columns:
        t.add_row(c, typ)
    out.print(t)


@tables_app.command("publish")
def tables_publish(
    name: Annotated[str, typer.Argument(help="A table QuerySolo wrote, under the local warehouse.")],
    prefix: Annotated[str, typer.Argument(help="s3://bucket/prefix; the table goes under main/.")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Count and weigh the files; move nothing.")
    ] = False,
    yes: Annotated[
        bool, typer.Option("--yes", help="Publish even if the copy would take longer than the cap.")
    ] = False,
) -> None:
    """Move a table built here into a bucket, every snapshot kept: its files are copied
    under the prefix, its metadata written again there, and the catalog moved to it in one
    commit. The local files become orphans `tables expire` sweeps. An interrupted publish
    resumes: files already in the bucket at the same size are not copied twice."""
    from querysolo.relocate import NotPublishable, publish
    from querysolo.tables import NoSuchTable

    with _open() as p:
        cap = None if yes else p.config.gauge.yellow_max_seconds
        try:
            r = publish(p, name, prefix, dry_run=dry_run, cap_seconds=cap)
        except NoSuchTable:
            _fail(f"no table named {name}")
        except NotPublishable as e:
            _fail(str(e))
        if not dry_run:
            p.tables.refresh_agents_md()
    when = f", about {r.seconds:,.0f} s at the measured bandwidth" if r.seconds is not None else ""
    if r.dry_run:
        out.print(
            f"{r.name}: {r.files} file(s), {_human_bytes(r.bytes)} to copy to {r.target}{when}; "
            "nothing moved (--dry-run)",
            highlight=False,
            soft_wrap=True,
        )
        return
    out.print(
        f"published {r.name} to {r.target}: {r.copied} file(s) copied, {r.skipped} already there, "
        f"{_human_bytes(r.bytes)}; {r.metadata_files} metadata file(s) and {r.data_files} delete "
        "file(s) rewritten; the local files are orphans for `querysolo tables expire`",
        highlight=False,
        soft_wrap=True,
    )


@tables_app.command("expire")
def tables_expire(
    name: Annotated[str | None, typer.Argument(help="A table; or --all.")] = None,
    all_tables: Annotated[bool, typer.Option("--all", help="Every table QuerySolo wrote.")] = False,
    keep_days: Annotated[
        int | None,
        typer.Option("--keep-days", help="Days of snapshots to keep; querysolo.toml's by default."),
    ] = None,
) -> None:
    """Drop snapshots older than the retention and delete the files only they referenced,
    plus any file under the table that no snapshot references and that is over an hour old
    (what a previous --replace left). The current snapshot always stays; a table registered
    with `tables attach` is never touched. The one verb that deletes data files."""
    from querysolo.tables import NoSuchTable, NotExpirable

    if bool(name) == all_tables:
        _fail("give a table name, or --all")
    with _open() as p:
        names = [t.name for t in p.tables.list(views=False)] if all_tables else [name]
        for n in names:
            try:
                r = p.tables.expire(n, keep_days=keep_days)
            except NoSuchTable:
                _fail(f"no table named {n}")
            except NotExpirable as e:
                out.print(f"{n}: skipped, {e}", highlight=False)
                continue
            out.print(
                f"{n}: {r.snapshots_removed} of {r.snapshots_before} snapshot(s) expired "
                f"(keeping {r.keep_days} days), {r.files_removed} file(s) removed, "
                f"{_human_bytes(r.bytes_reclaimed)} reclaimed",
                highlight=False,
            )


@tables_app.command("sample")
def tables_sample(
    name: str, n: Annotated[int, typer.Option("-n", help="Rows to show.")] = 5
) -> None:
    """The first rows of a table."""
    from querysolo.tables import NoSuchTable

    with _open() as p:
        try:
            rows = p.tables.sample(name, n=n)
        except NoSuchTable:
            _fail(f"no table named {name}")
    _print_rows(
        [list(r.keys()) for r in rows[:1]][0] if rows else [], [list(r.values()) for r in rows]
    )


@tables_app.command("attach")
def tables_attach(
    name: str,
    source: Annotated[
        str, typer.Argument(help="s3://bucket/prefix/ of Parquet, or a …metadata.json")
    ],
    metadata_in_bucket: Annotated[
        bool,
        typer.Option(
            "--metadata-in-bucket", help="Keep the Iceberg metadata under s3://bucket/_querysolo/."
        ),
    ] = False,
    anonymous: Annotated[
        bool,
        typer.Option(
            "--anonymous",
            help="A public bucket: read it without credentials (metadata stays local).",
        ),
    ] = False,
    replace: Annotated[
        bool,
        typer.Option(
            "--replace",
            help="Register the prefix again over an existing table (after files changed).",
        ),
    ] = False,
) -> None:
    """Register remote data as a read-only Iceberg table without copying it."""
    from querysolo.register import NotRegistrable
    from querysolo.tables import ReservedName, TableExists

    with _open() as p:
        try:
            info = p.tables.attach(
                name,
                source,
                metadata_in_bucket=metadata_in_bucket,
                anonymous=anonymous,
                replace=replace,
            )
        except TableExists:
            _fail(f"table {name} exists; --replace registers the prefix again over it")
        except (NotRegistrable, ReservedName) as e:
            _fail(str(e))
    placement = "in the bucket" if metadata_in_bucket else "local"
    public = ", read without credentials" if anonymous else ""
    out.print(
        f"{info.name}: {info.rows:,} rows, {_human_bytes(info.bytes)} in place at {source}; "
        f"metadata {placement}{public}",
        highlight=False,
    )


@tables_app.command("refresh")
def tables_refresh(name: str) -> None:
    """Add the files new under a registered prefix since it was attached. Refuses if a
    registered file is gone or was rewritten under the same path since the attach."""
    from querysolo.register import ChangedFiles, MissingFiles, NotRegistrable
    from querysolo.tables import NoSuchTable

    with _open() as p:
        try:
            report = p.tables.refresh(name)
        except NoSuchTable:
            _fail(f"no table named {name}")
        except (NotRegistrable, MissingFiles, ChangedFiles) as e:
            _fail(str(e))
    out.print(
        f"{report.name}: {report.added} file(s) added; {report.files} files, {report.rows:,} rows",
        highlight=False,
    )


@tables_app.command("discover")
def tables_discover(
    prefix: Annotated[str, typer.Argument(help="s3://bucket/ or s3://bucket/prefix/")],
    anonymous: Annotated[
        bool, typer.Option("--anonymous", help="A public bucket: list it without credentials.")
    ] = False,
) -> None:
    """Candidate prefixes under a bucket, with their size and kind."""
    from querysolo.register import NotRegistrable

    with _open() as p:
        try:
            found = p.tables.discover(prefix, anonymous=anonymous)
        except NotRegistrable as e:
            _fail(str(e))
    t = Table()
    for column in ("prefix", "kind", "files", "size"):
        t.add_column(column)
    for d in found:
        t.add_row(d.prefix, d.kind, str(d.files), _human_bytes(d.bytes))
    out.print(t)


@bucket_app.command("check")
def bucket_check(
    prefix: Annotated[
        str, typer.Argument(help="s3://bucket/prefix the project's tables would use.")
    ],
    as_json: Annotated[bool, typer.Option("--json", help="The result as JSON.")] = False,
) -> None:
    """Try a bucket the way a project would (decisions P1): the credentials in the
    environment, a list of the prefix, one object written under it and removed. Nothing is
    created; no project is needed. Exit 1 when the prefix cannot be written."""
    from querysolo.remote import check_prefix

    result = check_prefix(prefix)
    if as_json:
        typer.echo(json.dumps(result.to_dict()))
    else:
        out.print(result.sentence(), highlight=False)
    if not result.ok:
        raise typer.Exit(1)


# -- sql and estimate ------------------------------------------------------------


def _print_rows(columns: list[str], rows: list[list], title: str | None = None) -> None:
    t = Table(title=title)
    for c in columns:
        t.add_column(str(c))
    for row in rows:
        t.add_row(*[str(v) for v in row])
    out.print(t)


def _emit(result, fmt: str, output: Path | None, limit: int) -> int:
    """Stream the result to stdout (or a file) in the chosen format; returns the row count."""

    if fmt == "parquet":
        import pyarrow.parquet as pq

        if output is None:
            _fail("--format parquet needs --output <file.parquet>")
        table = result.to_arrow()
        pq.write_table(table, output)
        return table.num_rows
    sink = output.open("w", encoding="utf-8", newline="") if output else sys.stdout
    total = 0
    try:
        if fmt == "csv":
            writer = None
            for batch in result:
                if writer is None:
                    writer = csv.writer(sink)
                    writer.writerow(batch.schema.names)
                for row in zip(*[c.to_pylist() for c in batch.columns], strict=True):
                    writer.writerow(row)
                total += batch.num_rows
        elif fmt == "json":
            for batch in result:
                for row in batch.to_pylist():
                    sink.write(json.dumps(row, default=str) + "\n")
                total += batch.num_rows
        else:  # table
            shown: list[list] = []
            columns: list[str] = []
            for batch in result:
                columns = columns or batch.schema.names
                if len(shown) < limit:
                    rows = zip(*[c.to_pylist() for c in batch.columns], strict=True)
                    for row in rows:
                        if len(shown) >= limit:
                            break
                        shown.append(list(row))
                total += batch.num_rows
            _print_rows(columns, shown)
            if total > limit:
                out.print(
                    f"showing {limit:,} of {total:,} rows; --format csv streams them all",
                    highlight=False,
                )
    finally:
        if output:
            sink.close()
    return total


def _run_sql(
    p, sql: str, fmt: str | None, output: Path | None, run_anyway: bool, limit: int
) -> None:
    from querysolo.engine import CatalogConflict
    from querysolo.query import RedRefused

    if fmt is None:
        fmt = "table" if sys.stdout.isatty() else "csv"
    try:
        result = p.query(sql, allow_red=run_anyway)
    except RedRefused as e:
        _gauge_line(e.estimate)
        err.print("refused; --run-anyway runs it here regardless", highlight=False)
        raise typer.Exit(EXIT_RED) from None
    except CatalogConflict as e:
        _fail(f"catalog conflict after retries: {e}", EXIT_CONFLICT)
    if result.estimate is not None:
        _gauge_line(result.estimate)
    else:
        err.print("[dim]couldn't estimate; running anyway[/dim]")
    started = time.perf_counter()
    try:
        rows = _emit(result, fmt, output, limit)
    except CatalogConflict as e:
        _fail(f"catalog conflict after retries: {e}", EXIT_CONFLICT)
    actual = result.actual
    elapsed = actual.wall if actual else time.perf_counter() - started
    err.print(f"✓ {rows:,} rows · {elapsed:.2f} s", highlight=False)


@app.command()
def sql(
    query: Annotated[str | None, typer.Argument(help="The SQL; or use -f.")] = None,
    file: Annotated[
        Path | None, typer.Option("-f", "--file", help="Read the SQL from a file.")
    ] = None,
    fmt: Annotated[
        str | None,
        typer.Option(
            "--format", help="table, csv, json or parquet; table on a terminal, csv when piped."
        ),
    ] = None,
    output: Annotated[
        Path | None, typer.Option("-o", "--output", help="Write the result to a file.")
    ] = None,
    run_anyway: Annotated[
        bool, typer.Option("--run-anyway", help="Run a Red verdict here regardless.")
    ] = False,
    limit: Annotated[int, typer.Option(help="Rows shown as a table.")] = 1000,
) -> None:
    """Run SQL: the gauge line first (stderr), then the rows (stdout)."""
    if fmt is not None and fmt not in ("table", "csv", "json", "parquet"):
        _fail("--format must be table, csv, json or parquet")
    text = _sql_text(query, file)
    with _open() as p:
        _run_sql(p, text, fmt, output, run_anyway, limit)


@app.command()
def estimate(
    query: Annotated[str | None, typer.Argument(help="The SQL; or use -f.")] = None,
    file: Annotated[
        Path | None, typer.Option("-f", "--file", help="Read the SQL from a file.")
    ] = None,
    as_json: Annotated[
        bool, typer.Option("--json", help="The numbers as JSON instead of the line.")
    ] = False,
) -> None:
    """The gauge only: verdict, bytes, memory, time, the burst half. Nothing runs."""
    text = _sql_text(query, file)
    with _open() as p:
        e = p.estimate(text)
    if as_json:
        out.print_json(
            json.dumps(
                {
                    "verdict": e.verdict,
                    "words": e.words,
                    "bytes_scanned": e.bytes_scanned,
                    "peak_memory": e.peak_memory,
                    "wall_local": e.wall_local,
                    "worker": e.worker,
                    "wall_burst": e.wall_burst,
                    "cost_burst": e.cost_burst,
                    "cap": e.cap,
                    "pruning": e.pruning,
                    "reason": e.reason,
                }
            )
        )
    else:
        from querysolo.gauge.verdict import DOTS

        style = VERDICT_STYLE[e.verdict]
        out.print(
            f"[{style}]{DOTS.get(e.verdict, '●')}[/{style}] {e.words} · {e.reason}",
            highlight=False,
        )


# -- catalog ----------------------------------------------------------------------


def _write_dbt_profile(p: Any, url: str) -> Path | None:
    """The dbt profile for a catalog this process serves (real-data brief R5), so a
    `dbt run` or `dbt test` by hand has one; nothing if the folder cannot be written."""
    from querysolo.dbt.runner import write_profile

    try:
        return write_profile(p, url)
    except OSError:
        return None


@catalog_app.command("serve")
def catalog_serve(
    port: Annotated[
        int, typer.Option(help="A fixed port for Spark, Trino, pyiceberg and other DuckDBs.")
    ] = 8181,
    host: Annotated[str, typer.Option(help="Loopback only in v0.")] = "127.0.0.1",
) -> None:
    """Expose the project's Iceberg REST catalog on a fixed loopback port."""
    import signal
    import threading

    from querysolo.catalog import EmbeddedCatalog, create_app

    if host not in ("127.0.0.1", "localhost", "::1"):
        _fail(f"v0 binds loopback only; {host} refused (brief D22)")
    p = _open()
    server = EmbeddedCatalog(create_app(p.store, warehouse=p.warehouse_url), port=port)
    url = server.start()
    profile = _write_dbt_profile(p, url)
    out.print(f"catalog at {url} (Iceberg REST, warehouse {p.warehouse_url})", highlight=False)
    out.print(
        f'pyiceberg: RestCatalog("querysolo", uri="{url}")\n'
        f"duckdb:    ATTACH 'querysolo' AS querysolo (TYPE ICEBERG, ENDPOINT '{url}', "
        "AUTHORIZATION_TYPE 'none', DEFAULT_SCHEMA 'main')\n"
        + (f"dbt:       dbt run --profiles-dir {profile.parent}\n" if profile else "")
        + "Ctrl-C stops it.",
        highlight=False,
    )
    sys.stdout.flush()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    stop.wait()
    server.stop()
    p.close()


# -- questions -------------------------------------------------------------------


@question_app.command("save")
def question_save(
    title: str,
    file: Annotated[
        Path | None, typer.Option("-f", "--file", help="Read the SQL from a file.")
    ] = None,
    query: Annotated[str | None, typer.Option("--sql", help="The SQL inline.")] = None,
) -> None:
    """Save a question as a dbt model with two default checks."""
    text = _sql_text(query, file)
    with _open() as p:
        q = p.questions.save(title, text)
    out.print(
        f"saved {q.slug}: {q.path.relative_to(p.root)} (+ schema.yml entry with 2 checks)",
        highlight=False,
    )
    if q.commit:
        from querysolo.versions import short

        out.print(f"version {short(q.commit)}", highlight=False)
    elif q.git:
        out.print(f"git: {q.git}; the files are saved, this save is not a version", highlight=False)
    else:
        out.print("no change, so no new version", highlight=False)


@question_app.command("list")
def question_list() -> None:
    """Saved questions with their last run."""
    with _open() as p:
        questions = p.questions.list()
    t = Table()
    for column in ("slug", "title", "last run"):
        t.add_column(column)
    for q in questions:
        t.add_row(
            q.slug, q.title, q.last_run.isoformat(timespec="seconds") if q.last_run else "never"
        )
    out.print(t)


@question_app.command("run")
def question_run(
    slug: str,
    fmt: Annotated[
        str | None, typer.Option("--format", help="table, csv, json or parquet.")
    ] = None,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
    run_anyway: Annotated[bool, typer.Option("--run-anyway")] = False,
    limit: Annotated[int, typer.Option()] = 1000,
) -> None:
    """Run a saved question: the gauge first."""
    from querysolo.questions import NoSuchQuestion

    with _open() as p:
        try:
            q = p.questions.get(slug)
        except NoSuchQuestion:
            _fail(f"no question named {slug}")
        _run_sql(p, q.sql, fmt, output, run_anyway, limit)
        if p.history.recent(1) and p.history.recent(1)[0].sql_text == q.sql:
            p.history.record_question_run(slug, p.history.recent(1)[0].id)


# -- run: the dbt DAG through the gauge (real-data brief R5) --------------------------


@app.command("run")
def run_models(
    select: Annotated[
        list[str] | None, typer.Argument(help="dbt selectors; none means every model.")
    ] = None,
    burst: Annotated[
        str, typer.Option("--burst", help="never (here) or auto (session 8; refuses today).")
    ] = "never",
    run_anyway: Annotated[
        bool, typer.Option("--run-anyway", help="Run the DAG here even if a model is Red.")
    ] = False,
    plan_only: Annotated[
        bool, typer.Option("--plan", help="Print the DAG with its verdicts and stop.")
    ] = False,
    stale: Annotated[
        bool,
        typer.Option(
            "--stale",
            help="Build only what is not fresh: edited, an input changed, or never built.",
        ),
    ] = False,
) -> None:
    """Build the project's dbt models through the catalog, each with its verdict first.
    A `view` model becomes a view in the catalog; a `table` model an Iceberg table. The
    DAG says each model's state: fresh, edited, upstream (an input changed) or never."""
    from querysolo.dbt import runner

    with _open() as p:
        try:
            if plan_only:
                models = runner.plan(p, select)
                out.print("\n".join(runner.dag_lines(models)), highlight=False)
                return
            report = runner.run(p, select, burst=burst, run_anyway=run_anyway, stale=stale)
        except runner.NoBurstYet as e:
            _fail(str(e))
        except runner.RedRefusedRun as e:
            err.print(str(e), highlight=False)
            raise typer.Exit(EXIT_RED) from None
        except (runner.DbtMissing, runner.DbtFailed) as e:
            _fail(str(e))
    out.print("\n".join(runner.dag_lines(report.models)), highlight=False)
    if report.selected is not None and not report.selected:
        out.print("every model is fresh; nothing to run", highlight=False)
        return
    for r in report.results:
        line = f"  {r.name}: {r.status} in {r.seconds:.2f} s"
        if r.message and r.status != "success":
            line += f" ({r.message})"
        out.print(line, highlight=False)
    if report.commit:
        from querysolo.versions import short

        out.print(f"version {short(report.commit)} recorded before the run", highlight=False)
    elif report.git:
        out.print(f"git: {report.git}", highlight=False)
    if report.views_recorded:
        out.print(f"views in the catalog: {', '.join(report.views_recorded)}", highlight=False)
    if report.views_dropped:
        out.print(f"views dropped: {', '.join(report.views_dropped)}", highlight=False)
    out.print(
        f"{len(report.results)} model(s) in {report.seconds:.1f} s"
        + ("" if report.ok else "; some failed"),
        highlight=False,
    )
    if not report.ok:
        raise typer.Exit(1)


# -- versions and restore (versions brief G5) ----------------------------------------


@app.command()
def versions(
    name: Annotated[str, typer.Argument(help="A saved question's slug, or a model's name.")],
    limit: Annotated[int, typer.Option(help="How many versions to list; newest first.")] = 20,
) -> None:
    """The versions of one question or model: every commit that changed its SQL or its
    checks, newest first."""
    from querysolo.versions import NoHistory, NoSuchModel

    with _open() as p:
        try:
            entries = p.versions.list(name)[:limit]
        except (NoHistory, NoSuchModel) as e:
            _fail(str(e))
    t = Table()
    for column in ("version", "when", "who", "what", "changed"):
        t.add_column(column)
    for v in entries:
        changed = ", ".join(
            ([] if v.sql_changed else ["checks only"])
            + (["checks changed"] if v.checks_changed else [])
        )
        t.add_row(v.short, v.when[:19].replace("T", " "), v.author, v.message, changed or "the SQL")
    out.print(t)


@app.command()
def restore(
    name: Annotated[str, typer.Argument(help="A saved question's slug, or a model's name.")],
    version: Annotated[str, typer.Argument(help="A version id, or any unambiguous prefix.")],
) -> None:
    """Put an earlier version of a question or model back. The restore is itself a version;
    nothing in the history is rewritten."""
    from querysolo.versions import NoHistory, NoSuchModel, short

    with _open() as p:
        try:
            result = p.versions.restore(name, version)
            path = p.versions.path(name).relative_to(p.root)
        except (NoHistory, NoSuchModel) as e:
            _fail(str(e))
    out.print(f"restored {name} from version {short(version)}: {path}", highlight=False)
    if result.id:
        out.print(f"version {short(result.id)}", highlight=False)
    elif result.reason:
        out.print(
            f"git: {result.reason}; the file is restored, this is not a version", highlight=False
        )
    else:
        out.print("that version is what the file already held; no new version", highlight=False)


@app.command()
def lineage(
    name: Annotated[
        str | None, typer.Argument(help="A table, a view or a model; none with --all.")
    ] = None,
    depth: Annotated[
        int, typer.Option("--depth", min=1, help="How many levels each way; 1 is direct.")
    ] = 1,
    all_: Annotated[
        bool, typer.Option("--all", help="The whole project: every node and its state, every edge.")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="The same as the API returns.")] = False,
) -> None:
    """What a table, view or model reads and what reads it, and how each edge is known:
    a dbt ref() or source(), a table named in the SQL, or a catalog view's SQL. From the
    last compile's manifest and the catalog; compiles first when the models are newer.
    --all prints the whole graph, as the app's Lineage screen draws it."""
    from querysolo.dbt import runner
    from querysolo.lineage import NoSuchNode, lineage, whole

    if all_ == (name is not None):
        _fail("give a name, or --all for the whole project")
    with _open() as p:
        try:
            result = whole(p) if all_ else lineage(p, name, depth)
        except NoSuchNode as e:
            _fail(str(e))
        except runner.DbtFailed as e:
            _fail(f"dbt could not compile the models: {e}")
    if as_json:
        out.print(json.dumps(result if all_ else _lineage_json(result), indent=2), highlight=False, soft_wrap=True)
        return
    for line in graph_lines(result) if all_ else lineage_lines(result):
        out.print(line, highlight=False, soft_wrap=True)


@app.command()
def changes(
    name: Annotated[
        str | None, typer.Argument(help="Only what happened to this table, model or question.")
    ] = None,
    since: Annotated[
        str | None, typer.Option("--since", help="2d, 12h, 30m, 1w, or an ISO date.")
    ] = None,
    last: Annotated[int, typer.Option("--last", min=1, help="At most this many entries.")] = 50,
    as_json: Annotated[bool, typer.Option("--json", help="The same as the API returns.")] = False,
) -> None:
    """Everything that happened to the project, newest first: every table's snapshots
    (and the models each made out of date), each model's and question's last run, and the
    versions git holds for the models. Read from what is there; nothing is recorded."""
    from querysolo.changes import changes, parse_since

    try:
        cutoff = parse_since(since) if since else None
    except ValueError as e:
        _fail(str(e))
    with _open() as p:
        feed = changes(p, since=cutoff, last=last, name=name)
    if as_json:
        out.print(json.dumps([c.as_dict() for c in feed], indent=2), highlight=False, soft_wrap=True)
        return
    if not feed:
        out.print("nothing yet" if name is None else f"nothing about {name}", highlight=False)
        return
    for c in feed:
        when = c.when.isoformat(timespec="seconds").replace("+00:00", " UTC").replace("T", " ")
        out.print(f"{when}  {c.kind:<8} {c.sentence()}", highlight=False, soft_wrap=True)


def graph_lines(graph: dict[str, Any]) -> list[str]:
    """`--all` as text: one line per node (kind, state), then one per edge."""
    nodes, edges = graph["nodes"], graph["edges"]
    width = max((len(n["name"]) for n in nodes), default=4)
    lines = [f"{len(nodes)} node(s), {len(edges)} edge(s)"]
    for n in nodes:
        state = f"  {n['state']}" if n.get("state") else ""
        lines.append(f"  {n['name']:<{width}}  {n['kind']:<5}{state}")
    for e in edges:
        lines.append(f"  {e['from']} -> {e['to']}  ({e['via']})")
    if graph.get("compiled"):
        lines.append("(the models were compiled first: the manifest was older than they are)")
    return lines


def _lineage_json(result) -> dict[str, Any]:
    from dataclasses import asdict

    return asdict(result)


def lineage_lines(result) -> list[str]:
    head = f"{result.name}  {result.kind}"
    if result.built_by in ("imported", None) or result.built_by.startswith("attached from "):
        head += f", {result.built_by}" if result.built_by else ""
    else:
        head += f", built by {result.built_by}"
    if result.kind == "model":
        head += ", never built"
    if result.last_built:
        head += f", {result.last_built[:19].replace('T', ' ')} UTC"
    lines = [head]
    for title, edges in (("reads from", result.upstream), ("feeds", result.downstream)):
        lines.append(f"  {title}" if edges else f"  {title}: nothing")
        width = max((len(e.name) for e in edges), default=0)
        for e in edges:
            indent = "    " + "  " * (e.depth - 1)
            lines.append(f"{indent}{e.name:<{width}}  {e.kind:<5}  {e.via}")
    if result.compiled:
        lines.append("(the models were compiled first: the manifest was older than they are)")
    return lines


@app.command()
def relocate() -> None:
    """After the project folder was moved or copied: rewrite every local table's locations
    under this folder so the tables resolve again. Every snapshot is kept; the old metadata
    files become orphans for `tables expire`. Tables attached from a bucket are skipped."""
    from querysolo import relocate as relocation

    with _open() as p:
        old = relocation.moved_from(p)
        if old is None:
            out.print("nothing to relocate: every table resolves from this folder", highlight=False)
            return
        report = relocation.relocate(p)
        p.tables.refresh_agents_md()
    out.print(
        f"relocated {len(report.relocated)} table(s) from {report.old_root} to {report.new_root}: "
        f"{', '.join(report.relocated)}; {report.metadata_files} metadata file(s) and "
        f"{report.data_files} delete file(s) rewritten"
        + (f"; skipped {', '.join(report.skipped)}" if report.skipped else ""),
        highlight=False,
    )


# -- gauge history and audit -----------------------------------------------------


# -- config -------------------------------------------------------------------------


@config_app.command("show")
def config_show() -> None:
    """The settings a hand or the app may change, with their current values."""
    from querysolo.config import Config, current_settings

    root = _root()
    _migrate(root)
    toml = root / "querysolo.toml"
    if not toml.is_file():
        _fail(f"{root} is not a QuerySolo project (no querysolo.toml)")
    for key, value in current_settings(Config.load(toml)).items():
        out.print(f"{key} = {value}", highlight=False)


@config_app.command("set")
def config_set(
    key: Annotated[
        str, typer.Argument(help="engine.memory_limit, engine.threads or gauge.share_calibration.")
    ],
    value: Annotated[str, typer.Argument(help="auto or a size; auto or a count; true or false.")],
) -> None:
    """Set one setting in querysolo.toml, leaving the rest of the file as it was. The engine
    reads its settings at start, so a running `querysolo serve` keeps the old ones."""
    from querysolo.config import NotSettable, parse_setting, set_value

    root = _root()
    _migrate(root)
    toml = root / "querysolo.toml"
    if not toml.is_file():
        _fail(f"{root} is not a QuerySolo project (no querysolo.toml)")
    try:
        parsed = parse_setting(key, value)
    except NotSettable as e:
        _fail(str(e))
    toml.write_text(set_value(toml.read_text(encoding="utf-8"), key, parsed), encoding="utf-8")
    out.print(f"{key} = {parsed}  (in {toml}; applies from the next start)", highlight=False)


@gauge_app.command("probe")
def gauge_probe(
    mb: Annotated[int, typer.Option("--mb", help="Size of the probe file.")] = 512,
) -> None:
    """Measure local disk throughput again and record it for the gauge (a project set up
    before September 11, 2026 measured the page cache, not the disk)."""
    from querysolo.project import run_probe

    root = _root()
    _migrate(root)
    if not (root / "querysolo.toml").is_file():
        _fail(f"{root} is not a QuerySolo project (no querysolo.toml)")
    probe = run_probe(root, mb)
    how = {
        "nocache": "cache bypassed",
        "direct": "cache bypassed",
        "cached": "through the cache, capped",
    }[probe.method]
    out.print(
        f"local disk reads at {probe.mbps:,.0f} MB/s ({how}); recorded in .querysolo/cache",
        highlight=False,
    )


@gauge_app.command("export")
def gauge_export(
    out_path: Annotated[
        str | None,
        typer.Option(
            "--out",
            help="Where to write; '-' for stdout. Default: .querysolo/exports/gauge-<time>.jsonl",
        ),
    ] = None,
) -> None:
    """Write the calibration record as JSON lines: fingerprint, machine class, operator
    counts, estimate, actual. Never SQL, table or column names, or values (PRD F0.3.9)."""
    from querysolo.gauge.export import export_lines

    with _open() as p:
        if out_path == "-":
            for line in export_lines(p.history.all_runs()):
                print(line)
            return
        path, count = p.export_gauge(Path(out_path) if out_path else None)
    out.print(f"{count} run(s) written to {path}", highlight=False)


@gauge_app.command("reset")
def gauge_reset(
    yes: Annotated[bool, typer.Option("--yes", help="Do not ask.")] = False,
) -> None:
    """Forget every recorded run and what the gauge learned from them."""
    with _open() as p:
        n = p.history.summary()["runs"]
        if not yes and not typer.confirm(f"Forget {n} recorded run(s) in {p.root}?"):
            raise typer.Exit(0)
        removed = p.history.reset()
    out.print(f"{removed} run(s) forgotten", highlight=False)


@gauge_app.command("history")
def gauge_history(last: Annotated[int, typer.Option("--last", help="Runs to show.")] = 20) -> None:
    """Recent runs: verdict, estimate, actual."""
    from querysolo.gauge import inputs
    from querysolo.gauge.verdict import human_bytes, human_seconds

    with _open() as p:
        runs = p.history.recent(last)
        cache = inputs.load_machine_cache(p.cache_dir)
        summary = p.history.summary()
    share = summary["within_2x_share"]
    within = (
        f"{share:.0%} within 2x on time" if share is not None else "no completed runs to compare"
    )
    out.print(
        f"{summary['runs']} run(s) recorded; {within}; "
        f"{summary['green_over_3min']} Green run(s) over 3 min",
        highlight=False,
    )
    mbps = cache.get("throughput_local_mbps")
    method = inputs.probe_method(cache)
    if mbps and method == "cached":
        out.print(
            f"local disk: up to {mbps:,.0f} MB/s, measured through the cache; "
            "run `querysolo gauge probe` to measure the disk",
            highlight=False,
        )
    elif mbps:
        out.print(f"local disk: {mbps:,.0f} MB/s (cache bypassed)", highlight=False)
    t = Table()
    for column in ("when", "verdict", "est", "actual", "bytes", "where", "sql"):
        t.add_column(column)
    for r in runs:
        t.add_row(
            r.ts.strftime("%H:%M:%S") if r.ts else "",
            r.verdict or "?",
            human_seconds(r.est_wall_local) if r.est_wall_local else "",
            human_seconds(r.actual_wall) if r.actual_wall else "",
            human_bytes(r.est_bytes) if r.est_bytes else "",
            r.ran_where,
            (r.sql_text or "").replace("\n", " ")[:60],
        )
    out.print(t)


@audit_app.command("network")
def audit_network() -> None:
    """Run the quickstart with outbound connections blocked and report every attempt."""
    import subprocess

    # The audit runs in a child so its socket guards wrap a whole process. Frozen (ship
    # brief S1), the executable is `querysolo` itself and has no `-m`: the hidden `audit
    # _run` command below is the same entry point.
    if getattr(sys, "frozen", False):
        argv = [sys.executable, "audit", "_run"]
    else:
        argv = [sys.executable, "-m", "querysolo.audit"]
    completed = subprocess.run(argv, capture_output=True, text=True)
    out.print(completed.stdout.rstrip(), highlight=False)
    if completed.returncode != 0:
        err.print(completed.stderr[-2000:], highlight=False)
        raise typer.Exit(1)


@audit_app.command("_run", hidden=True)
def audit_run_in_process() -> None:
    """The audit itself, in this process (what `audit network` spawns when frozen)."""
    from querysolo.audit import main as audit_main

    raise typer.Exit(audit_main())


# -- serve -----------------------------------------------------------------------------


@app.command()
def serve(
    port: Annotated[int, typer.Option(help="A fixed port; 0 picks a free one.")] = 0,
    host: Annotated[str, typer.Option(help="Loopback only in v0.")] = "127.0.0.1",
    memory_limit: Annotated[
        str | None,
        typer.Option(
            help="DuckDB memory limit for this process, e.g. 8GB; the app sets one per window."
        ),
    ] = None,
) -> None:
    """Run the core as the app's sidecar: catalog and API on one loopback port, named in
    .querysolo/serve.json with a per-launch token."""
    import signal
    import threading

    if host not in ("127.0.0.1", "localhost", "::1"):
        _fail(f"v0 binds loopback only; {host} refused (brief D22)")
    from querysolo import Project
    from querysolo.project import NotAProject

    try:
        p = Project.open(_root(), serve=True, port=port, memory_limit=memory_limit)
    except NotAProject:
        _fail(f"not a QuerySolo project: no querysolo.toml in {_root()}; run `querysolo init`")
    _write_dbt_profile(p, p.catalog_url)
    out.print(
        f"serving {p.catalog_url}: /api (bearer token in {p.serve_json}) and /v1 (the catalog)",
        highlight=False,
    )
    out.print("Ctrl-C stops it.", highlight=False)
    sys.stdout.flush()
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    stop.wait()
    p.close()


def run() -> None:
    app()
