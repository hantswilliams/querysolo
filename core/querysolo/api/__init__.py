# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The local HTTP API (brief §3.6, D3, D17, D22): the same operations as the CLI verbs over
loopback, on the same server as the catalog, under ``querysolo serve``. Every ``/api`` route
needs the per-launch bearer token from ``serve.json``; ``/v1`` stays open on loopback. Query
results stream as Arrow IPC with the gauge's verdict in the response headers.

The engine is one DuckDB connection, so requests that touch it are serialised."""

from __future__ import annotations

import asyncio
import dataclasses
import threading
import time
from collections.abc import AsyncIterator, Iterator
from datetime import datetime
from typing import TYPE_CHECKING, Any

import anyio
import duckdb
import pyarrow as pa
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from querysolo import __version__, relocate, remote
from querysolo.engine import CatalogConflict
from querysolo.gauge import inputs
from querysolo.project import identifier
from querysolo.query import Interrupted, RedRefused
from querysolo.questions import NoSuchQuestion
from querysolo.register import ChangedFiles, MissingFiles, NotRegistrable
from querysolo.tables import NoSuchTable, NotExpirable, TableExists, UnsupportedFile
from querysolo.versions import NoHistory, NoSuchModel

if TYPE_CHECKING:
    from querysolo.project import Project

ARROW_STREAM = "application/vnd.apache.arrow.stream"
TAURI_ORIGINS = ["tauri://localhost", "http://tauri.localhost", "https://tauri.localhost"]
#: The verdict travels in headers so a window shows it before the first row (brief D3);
#: a browser only lets a cross-origin page read headers the server names.
VERDICT_HEADERS = ["X-QuerySolo-Verdict", "X-QuerySolo-Words", "X-QuerySolo-Reason"]


class ImportBody(BaseModel):
    path: str
    name: str | None = None
    mode: str = "create"


class PreviewBody(BaseModel):
    path: str
    name: str | None = None
    anonymous: bool = False  # for an s3:// prefix: a public bucket, no credentials


class AttachBody(BaseModel):
    name: str
    source: str
    metadata_in_bucket: bool = False
    anonymous: bool = False
    replace: bool = False  # register again over an existing table (T2)


class SqlBody(BaseModel):
    sql: str
    allow_red: bool = False
    batch_rows: int = 1000


class EstimateBody(BaseModel):
    sql: str


class ExpireBody(BaseModel):
    keep_days: int | None = None


class PublishBody(BaseModel):
    prefix: str
    dry_run: bool = False
    #: Publish even when the copy would take longer than the gauge's yellow threshold (W2).
    yes: bool = False


class SettingBody(BaseModel):
    key: str
    value: str


class RestoreBody(BaseModel):
    id: str


class QuestionBody(BaseModel):
    title: str
    sql: str
    #: A title whose slug is already saved is refused with 409 unless this is set, so the app
    #: can offer "Replace it" the way an import that meets an existing table does (G7). The
    #: CLI's `question save` updates in place and does not ask.
    replace: bool = False


class ProbeBody(BaseModel):
    mb: int = 512


class DbtRunBody(BaseModel):
    select: list[str] = []
    burst: str = "never"
    run_anyway: bool = False
    #: V3: build only the models that are not fresh (`querysolo run --stale`).
    stale: bool = False


class RunBody(BaseModel):
    allow_red: bool = False


def _plain(value: Any) -> Any:
    """Dataclasses, datetimes and paths into JSON-ready values."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in dataclasses.asdict(value).items()}
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    if hasattr(value, "__fspath__"):
        return str(value)
    return value


def _estimate_json(estimate) -> dict[str, Any]:
    data = _plain(estimate)
    data.pop("plan", None)
    data["line"] = estimate.line
    return data


def _arrow_stream(result) -> Iterator[bytes]:
    class Sink:
        """The file-like surface pyarrow expects of a Python sink; bytes are handed to the
        response as each batch is written."""

        closed = False

        def __init__(self) -> None:
            self.parts: list[bytes] = []
            self.written = 0

        def write(self, data: bytes) -> int:
            self.parts.append(bytes(data))
            self.written += len(data)
            return len(data)

        def writable(self) -> bool:
            return True

        def readable(self) -> bool:
            return False

        def seekable(self) -> bool:
            return False

        def tell(self) -> int:
            return self.written

        def flush(self) -> None:
            pass

        def close(self) -> None:
            pass

    sink = Sink()
    writer = None
    try:
        for batch in result:
            if writer is None:
                writer = pa.ipc.new_stream(sink, batch.schema)
            writer.write_batch(batch)
            yield b"".join(sink.parts)
            sink.parts.clear()
        if writer is None:
            writer = pa.ipc.new_stream(sink, result._reader.schema)
        writer.close()
        yield b"".join(sink.parts)
    finally:
        result.close()


async def _stream_until_gone(
    batches: Iterator[bytes], interrupt: Any, request: Request, release: Any
) -> AsyncIterator[bytes]:
    """Feed the sync Arrow stream to the response; when the client goes away mid-query
    (the app's Esc closes the fetch), interrupt the engine so the statement stops now
    rather than running to completion for nobody, and the result closes as stopped early.
    ``release`` closes the result and frees the engine lock, and is called here rather
    than from inside the generator: a client gone before the first byte cancels the
    response before ``next`` ever ran, and a generator that never started runs no
    ``finally`` — the lock stayed held and every later query waited on it."""
    abandoned = False
    try:
        while True:
            chunk = await anyio.to_thread.run_sync(next, batches, None, abandon_on_cancel=True)
            if chunk is None:
                return
            yield chunk
    except (asyncio.CancelledError, GeneratorExit):
        # The abandoned thread may still be inside next(); the interrupt makes DuckDB
        # return, then the generator can be closed and the lock freed. Done on a thread so
        # the cancelled response is not held up.
        abandoned = True
        threading.Thread(target=_stop, args=(batches, interrupt, release), daemon=True).start()
        raise
    finally:
        if not abandoned:
            release()


def _stop(batches: Iterator[bytes], interrupt: Any, release: Any) -> None:
    interrupt()
    try:
        for _ in range(600):  # up to a minute for DuckDB to notice; it takes milliseconds
            try:
                batches.close()
                return
            except ValueError:  # generator already executing: the thread has not returned yet
                time.sleep(0.1)
    finally:
        release()


async def _query_watching_disconnect(request: Request, start: Any, interrupt: Any) -> Any:
    """Run ``start`` (the estimate and the statement's first execution) on a thread while
    watching for the client to disconnect; a disconnect interrupts the engine."""
    task = asyncio.ensure_future(anyio.to_thread.run_sync(start))
    try:
        while not task.done():
            if await request.is_disconnected():
                interrupt()
                break
            await asyncio.sleep(0.05)
        return await task
    except asyncio.CancelledError:
        interrupt()
        raise


def _plan_json(m: Any) -> dict[str, Any]:
    return {
        "name": m.name,
        "unique_id": m.unique_id,
        "materialized": m.materialized,
        "depends_on": m.depends_on,
        "compiled_sql": m.compiled_sql,
        "verdict": m.verdict,
        "words": m.words,
        "reason": m.reason,
        "est_wall_local": m.est_wall_local,
        "est_bytes": m.est_bytes,
        "error": m.error,
        "description": m.description,
        "path": m.path,
        "tests": [dataclasses.asdict(t) for t in m.tests],
        "last_run": (
            {k: v for k, v in dataclasses.asdict(m.last_run).items() if k != "sql_text"}
            if m.last_run
            else None
        ),
        "state": m.state,
        "state_reason": m.state_reason,
        "state_since": m.state_since,
        "state_diff": m.state_diff,
        "state_changes": m.state_changes,
    }


def create_router(project: Project, token: str) -> APIRouter:
    router = APIRouter(prefix="/api")
    lock = threading.Lock()

    def authorised(request: Request) -> None:
        header = request.headers.get("authorization", "")
        if header != f"Bearer {token}":
            raise HTTPException(401, {"error": "unauthorised", "message": "bearer token required"})

    def error(status: int, kind: str, message: str, **extra: Any) -> JSONResponse:
        return JSONResponse({"error": kind, "message": message, **extra}, status_code=status)

    guarded = [Depends(authorised)]

    # -- health -----------------------------------------------------------------------

    @router.get("/health", dependencies=guarded)
    def health() -> dict[str, Any]:
        with lock:
            machine = inputs.machine_profile(project.engine, str(project.root))
        cache = inputs.load_machine_cache(project.cache_dir)
        return {
            "querysolo": __version__,
            "duckdb": duckdb.__version__,
            "project": project.config.project.name,
            "root": str(project.root),
            "machine": machine,
            "throughput_local_mbps": cache.get("throughput_local_mbps"),
            "throughput_probe": inputs.probe_method(cache),
            "bandwidth_mbps": cache.get("bandwidth_mbps"),
            "aws": project.s3.describe(),
            # the folder this project's tables were written in, when it is not this one (T5)
            "moved_from": relocate.moved_from(project),
        }

    @router.post("/bucket/check", dependencies=guarded)
    def bucket_check(body: dict[str, Any]) -> dict[str, Any]:
        """`querysolo bucket check` (decisions P1): the app's New project dialog, from a
        window that has a core; the welcome screen asks the shell to run the CLI."""
        return remote.check_prefix(str(body.get("prefix", ""))).to_dict()

    @router.post("/relocate", dependencies=guarded)
    def relocate_project() -> dict[str, Any]:
        """`querysolo relocate`: the tables' locations rewritten under this folder."""
        with lock:
            return _plain(relocate.relocate(project))

    # -- tables -----------------------------------------------------------------------

    @router.get("/tables", dependencies=guarded)
    def tables() -> list[dict[str, Any]]:
        with lock:
            return _plain(project.tables.list())

    @router.get("/tables/discover", dependencies=guarded)
    def discover(prefix: str, anonymous: bool = False):
        with lock:
            try:
                return _plain(project.tables.discover(prefix, anonymous=anonymous))
            except NotRegistrable as e:
                return error(400, "not_registrable", str(e))

    @router.get("/tables/{name}", dependencies=guarded)
    def describe(name: str):
        with lock:
            try:
                return _plain(project.tables.describe(name))
            except NoSuchTable:
                return error(404, "no_such_table", f"no table named {name}")

    @router.get("/tables/{name}/sample", dependencies=guarded)
    def sample(name: str, n: int = 5, truncate: int | None = 80):
        with lock:
            try:
                return _plain(project.tables.sample(name, n=n, truncate=truncate))
            except NoSuchTable:
                return error(404, "no_such_table", f"no table named {name}")

    @router.post("/preview", dependencies=guarded)
    def preview(body: PreviewBody):
        """A file's preview, or a folder's: one per file `import` would take, as a list."""
        from pathlib import Path

        with lock:
            try:
                if body.path.startswith("s3://"):
                    return _plain(
                        project.tables.preview_remote(body.path, anonymous=body.anonymous)
                    )
                if Path(body.path).is_dir():
                    return _plain(project.tables.preview_dir(body.path))
                return _plain(project.tables.preview(body.path, name=body.name))
            except (UnsupportedFile, FileNotFoundError) as e:
                return error(400, "bad_file", str(e))
            except NotRegistrable as e:
                return error(400, "not_registrable", str(e))

    @router.post("/import", dependencies=guarded)
    def import_(body: ImportBody):
        from pathlib import Path

        with lock:
            try:
                if Path(body.path).is_dir():
                    infos = project.tables.import_dir(body.path, mode=body.mode)
                else:
                    infos = [project.tables.import_file(body.path, name=body.name, mode=body.mode)]
            except TableExists as e:
                return error(409, "table_exists", f"table {e} exists; use mode replace or append")
            except (UnsupportedFile, FileNotFoundError) as e:
                return error(400, "bad_file", str(e))
            except CatalogConflict as e:
                return error(409, "catalog_conflict", str(e))
        return _plain(infos)

    @router.post("/tables/attach", dependencies=guarded)
    def attach(body: AttachBody):
        with lock:
            try:
                return _plain(
                    project.tables.attach(
                        body.name,
                        body.source,
                        metadata_in_bucket=body.metadata_in_bucket,
                        anonymous=body.anonymous,
                        replace=body.replace,
                    )
                )
            except TableExists:
                return error(409, "table_exists", f"table {body.name} exists")
            except NotRegistrable as e:
                return error(400, "not_registrable", str(e))

    @router.post("/tables/{name}/refresh", dependencies=guarded)
    def refresh(name: str):
        with lock:
            try:
                return _plain(project.tables.refresh(name))
            except NoSuchTable:
                return error(404, "no_such_table", f"no table named {name}")
            except (NotRegistrable, MissingFiles, ChangedFiles) as e:
                return error(409, "refresh_failed", str(e))

    @router.post("/tables/{name}/expire", dependencies=guarded)
    def expire(name: str, body: ExpireBody | None = None):
        """`querysolo tables expire`: the one route that deletes data files."""
        with lock:
            try:
                return _plain(
                    project.tables.expire(name, keep_days=body.keep_days if body else None)
                )
            except NoSuchTable:
                return error(404, "no_such_table", f"no table named {name}")
            except NotExpirable as e:
                return error(409, "not_expirable", str(e))

    @router.post("/tables/{name}/publish", dependencies=guarded)
    def publish_table(name: str, body: PublishBody):
        """`querysolo tables publish` (decisions W2): the table moved into a bucket, every
        snapshot kept; `dry_run` counts and weighs first."""
        from querysolo.relocate import NotPublishable, publish

        with lock:
            try:
                cap = None if body.yes else project.config.gauge.yellow_max_seconds
                report = publish(project, name, body.prefix, dry_run=body.dry_run, cap_seconds=cap)
            except NoSuchTable:
                return error(404, "no_such_table", f"no table named {name}")
            except NotPublishable as e:
                return error(409, "not_publishable", str(e))
            if not body.dry_run:
                project.tables.refresh_agents_md()
        return _plain(report)

    # -- settings (the panel is `querysolo config set`) ---------------------------------

    def _settings() -> dict[str, Any]:
        from querysolo.config import current_settings

        return {
            "settings": current_settings(project.config),
            "path": str(project.root / "querysolo.toml"),
            "note": "read at start; a running core keeps its values until it restarts",
        }

    @router.get("/settings", dependencies=guarded)
    def settings() -> dict[str, Any]:
        return _settings()

    @router.put("/settings", dependencies=guarded)
    def set_setting(body: SettingBody):
        from querysolo.config import Config, NotSettable, parse_setting, set_value

        try:
            parsed = parse_setting(body.key, body.value)
        except NotSettable as e:
            return error(400, "not_settable", str(e))
        toml = project.root / "querysolo.toml"
        with lock:
            toml.write_text(
                set_value(toml.read_text(encoding="utf-8"), body.key, parsed), encoding="utf-8"
            )
            project.config = Config.load(toml)
        return _settings()

    # -- the gauge and queries ------------------------------------------------------

    @router.post("/estimate", dependencies=guarded)
    def estimate(body: EstimateBody):
        with lock:
            try:
                return _estimate_json(project.estimate(body.sql))
            except duckdb.Error as e:
                return error(400, "sql_error", str(e).splitlines()[0])

    async def _run(
        request: Request,
        sql: str,
        allow_red: bool,
        batch_rows: int,
        question_slug: str | None = None,
    ):
        await anyio.to_thread.run_sync(lock.acquire)
        try:
            result = await _query_watching_disconnect(
                request,
                lambda: project.query(sql, allow_red=allow_red, batch_rows=batch_rows),
                project.engine.interrupt,
            )
        except Interrupted:
            lock.release()
            return error(499, "stopped", "the client went away before the first row")
        except RedRefused as e:
            lock.release()
            return error(409, "red_refused", e.estimate.reason, estimate=_estimate_json(e.estimate))
        except CatalogConflict as e:
            lock.release()
            return error(409, "catalog_conflict", str(e))
        except duckdb.Error as e:
            lock.release()
            return error(400, "sql_error", str(e).splitlines()[0])
        if question_slug:
            result.question_slug = question_slug
        headers = {}
        if result.estimate is not None:
            headers = {
                "X-QuerySolo-Verdict": result.estimate.verdict,
                "X-QuerySolo-Words": result.estimate.words,
                "X-QuerySolo-Reason": result.estimate.reason,
            }
        released = threading.Event()

        def release() -> None:
            """Once: the result recorded as it stands, the engine free for the next query."""
            if released.is_set():
                return
            released.set()
            try:
                result.close()
            finally:
                lock.release()

        return StreamingResponse(
            _stream_until_gone(_arrow_stream(result), project.engine.interrupt, request, release),
            media_type=ARROW_STREAM,
            headers=headers,
        )

    @router.post("/query", dependencies=guarded)
    async def query(body: SqlBody, request: Request):
        return await _run(request, body.sql, body.allow_red, body.batch_rows)

    # -- questions --------------------------------------------------------------------

    @router.get("/questions", dependencies=guarded)
    def questions() -> list[dict[str, Any]]:
        return _plain(project.questions.list())

    @router.post("/questions", dependencies=guarded)
    def save_question(body: QuestionBody):
        with lock:
            slug = identifier(body.title)
            if not body.replace and any(q.slug == slug for q in project.questions.list()):
                return error(
                    409,
                    "question_exists",
                    f"a question called {slug} is already saved; replace it to overwrite",
                    slug=slug,
                )
            try:
                return _plain(project.questions.save(body.title, body.sql))
            except duckdb.Error as e:
                return error(400, "sql_error", str(e).splitlines()[0])

    @router.post("/questions/{slug}/run", dependencies=guarded)
    async def run_question(slug: str, request: Request, body: RunBody | None = None):
        try:
            question = project.questions.get(slug)
        except NoSuchQuestion:
            return error(404, "no_such_question", f"no question named {slug}")
        return await _run(
            request, question.sql, body.allow_red if body else False, 1000, question_slug=slug
        )

    # -- versions (versions brief G5) --------------------------------------------------

    @router.get("/git", dependencies=guarded)
    def git_status():
        """The one line the model panel says about git (G6): `git · main · origin not set`."""
        return project.versions.status()

    @router.get("/versions/{name}", dependencies=guarded)
    def versions(name: str):
        try:
            return _plain(project.versions.list(name))
        except NoSuchModel:
            return error(404, "no_such_model", f"no model or question named {name}")
        except NoHistory as e:
            return error(404, "no_history", str(e))

    @router.get("/versions/{name}/{version_id}", dependencies=guarded)
    def version_sql(name: str, version_id: str):
        try:
            return {"name": name, "id": version_id, "sql": project.versions.sql(name, version_id)}
        except NoSuchModel:
            return error(404, "no_such_model", f"no model or question named {name}")
        except NoHistory as e:
            return error(404, "no_history", str(e))

    @router.post("/versions/{name}/restore", dependencies=guarded)
    def restore_version(name: str, body: RestoreBody):
        with lock:
            try:
                result = project.versions.restore(name, body.id)
            except NoSuchModel:
                return error(404, "no_such_model", f"no model or question named {name}")
            except NoHistory as e:
                return error(404, "no_history", str(e))
            except duckdb.Error as e:
                return error(400, "sql_error", str(e).splitlines()[0])
            return {"name": name, "commit": result.id, "git": result.reason}

    # -- lineage (versions brief G8) ---------------------------------------------------

    @router.get("/lineage", dependencies=guarded)
    def lineage_all():
        """The whole graph for the Lineage screen (decisions L1): every table, view and
        model with its kind and state, every edge with how it is known."""
        from querysolo.dbt import runner
        from querysolo.lineage import whole

        with lock:
            try:
                return whole(project)
            except runner.DbtFailed as e:
                return error(400, "dbt", str(e))

    @router.get("/changes", dependencies=guarded)
    def changes_feed(since: str | None = None, last: int = 50, name: str | None = None):
        """`querysolo changes` (decisions L2): snapshots, runs and versions merged by time,
        newest first; `since` as the CLI takes it, `name` for one table, model or question."""
        from querysolo.changes import changes, parse_since

        try:
            cutoff = parse_since(since) if since else None
        except ValueError as e:
            return error(400, "bad_since", str(e))
        with lock:
            return [c.as_dict() for c in changes(project, since=cutoff, last=last, name=name)]

    @router.get("/lineage/{name}", dependencies=guarded)
    def lineage(name: str, depth: int = 1):
        """What a table, view or model reads and what reads it, with how each edge is
        known; compiles the models first when the manifest is older than they are."""
        from querysolo.dbt import runner
        from querysolo.lineage import NoSuchNode
        from querysolo.lineage import lineage as _lineage

        with lock:
            try:
                return _plain(_lineage(project, name, max(1, depth)))
            except NoSuchNode:
                return error(404, "no_such_node", f"no table, view or model named {name}")
            except runner.DbtFailed as e:
                return error(400, "dbt", str(e))

    # -- history ----------------------------------------------------------------------

    @router.get("/history", dependencies=guarded)
    def history(last: int = 50) -> list[dict[str, Any]]:
        return _plain(project.history.recent(last))

    # -- dbt: the DAG through the gauge (real-data brief R5) -----------------------------

    @router.get("/run/plan", dependencies=guarded)
    def run_plan(select: str | None = None):
        from querysolo.dbt import runner

        with lock:
            try:
                models = runner.plan(project, select.split(",") if select else None)
            except (runner.DbtMissing, runner.DbtFailed) as e:
                return error(400, "dbt", str(e))
        return [_plan_json(m) for m in models]

    @router.post("/run", dependencies=guarded)
    def run_models(body: DbtRunBody | None = None):
        from querysolo.dbt import runner

        body = body or DbtRunBody()
        with lock:
            try:
                report = runner.run(
                    project,
                    body.select or None,
                    burst=body.burst,
                    run_anyway=body.run_anyway,
                    stale=body.stale,
                )
            except runner.NoBurstYet as e:
                return error(400, "no_burst_yet", str(e))
            except runner.RedRefusedRun as e:
                return error(409, "red_refused", str(e))
            except (runner.DbtMissing, runner.DbtFailed) as e:
                return error(400, "dbt", str(e))
        return {
            "models": [_plan_json(m) for m in report.models],
            "results": [dataclasses.asdict(r) for r in report.results],
            "views_recorded": report.views_recorded,
            "views_dropped": report.views_dropped,
            "seconds": report.seconds,
            "ok": report.ok,
            "selected": report.selected,
        }

    # -- the gauge screen (real-data brief R8) -----------------------------------------

    @router.get("/gauge/summary", dependencies=guarded)
    def gauge_summary() -> dict[str, Any]:
        return project.history.summary()

    @router.post("/gauge/export", dependencies=guarded)
    def gauge_export() -> dict[str, Any]:
        """`querysolo gauge export`: the file is written into the project, nothing is sent."""
        path, count = project.export_gauge()
        return {"path": str(path), "runs": count}

    @router.post("/gauge/reset", dependencies=guarded)
    def gauge_reset() -> dict[str, Any]:
        return {"removed": project.history.reset()}

    @router.post("/gauge/probe", dependencies=guarded)
    def gauge_probe(body: ProbeBody | None = None) -> dict[str, Any]:
        """`querysolo gauge probe`: measure the disk again; the health tiles read the result."""
        from querysolo.project import run_probe

        probe = run_probe(project.root, body.mb if body else 512)
        return {"mbps": probe.mbps, "method": probe.method, "size_bytes": probe.size_bytes}

    return router
