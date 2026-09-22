# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""`lakelet run` (real-data brief R5; PRD F0.7.3): compile the project's dbt models, run
each one's compiled SQL through the gauge in dependency order, print the DAG with a verdict
per model, then run it through dbt with Lakelet's plugin. A `view` model is recorded in
Lakelet's catalog afterwards (R6). Every model's estimate and actual go into history like
a query's. `--burst auto` is session 8's and refuses until then."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import duckdb

from lakelet import __version__
from lakelet.engine import remove_stray_data_dir
from lakelet.gauge import inputs
from lakelet.history import Run
from lakelet.query import sql_hash

if TYPE_CHECKING:
    from lakelet.project import Project

DBT_MODEL_PROPERTY = "lakelet.dbt-model"


class DbtMissing(Exception):
    """dbt-core and dbt-duckdb are not installed: `pip install 'lakelet[dbt]'`."""


class NoBurstYet(Exception):
    """`--burst auto`: there is no burst yet (session 8); `--burst never` runs everything here."""


class RedRefusedRun(Exception):
    """A model the gauge calls Red; `--run-anyway` runs the DAG regardless."""


class DbtFailed(Exception):
    pass


@dataclass
class ModelTest:
    """A test from `schema.yml` on a model (the app's Models panel shows them; Simple mode
    calls them checks): `not_null`, `unique`, `accepted_values`, `relationships`, or
    `singular` for a test written as SQL under `tests/`."""

    name: str
    kind: str
    column: str | None
    unique_id: str


@dataclass
class LastRun:
    """The model's last `lakelet run`, from history: when, whether dbt succeeded, its wall
    time and the verdict the gauge gave it then."""

    ts: str
    ok: bool
    seconds: float | None
    verdict: str | None
    error: str | None
    #: The hash of the compiled SQL that run built (decisions V3: an edit since is `edited`),
    #: and the SQL itself for the diff; the API leaves the text out of the JSON.
    sql_hash: str | None = None
    sql_text: str | None = None


#: A model's state (decisions-for-review V3, built in versions step 4): `fresh` (nothing it
#: is made of changed since its last successful run), `edited` (its own SQL did), `upstream`
#: (a table it reads has a newer snapshot, a view it reads a newer version, or a model it
#: reads is not fresh), `never` (no successful run in history). `lakelet run --stale` builds
#: every model that is not fresh.
STATES = ("fresh", "edited", "upstream", "never")


@dataclass
class PlannedModel:
    name: str
    unique_id: str
    materialized: str
    depends_on: list[str]
    compiled_sql: str
    verdict: str | None = None
    words: str | None = None
    reason: str | None = None
    est_wall_local: float | None = None
    est_bytes: int | None = None
    error: str | None = None
    estimate: Any = None
    description: str = ""
    path: str = ""
    tests: list[ModelTest] = field(default_factory=list)
    last_run: LastRun | None = None
    state: str | None = None
    #: Why it is not fresh, naming what changed ("orders changed", "by_c is out of date",
    #: "the SQL changed since the last run", "never built", "the last run failed");
    #: `state_since` is when, ISO 8601, when a time is known.
    state_reason: str | None = None
    state_since: str | None = None
    #: What changed, so the state is shown and not only said: for `edited`, the unified
    #: diff of the compiled SQL the last run built against the SQL now; for `upstream`
    #: naming a table or view, its snapshots (or versions) since that run, newest first,
    #: each ``{name, operation, added_rows, deleted_rows, timestamp}``.
    state_diff: str | None = None
    state_changes: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ModelResult:
    name: str
    status: str
    seconds: float
    message: str | None = None


@dataclass
class RunReport:
    models: list[PlannedModel]
    results: list[ModelResult] = field(default_factory=list)
    views_recorded: list[str] = field(default_factory=list)
    views_dropped: list[str] = field(default_factory=list)
    seconds: float = 0.0
    #: The version this run recorded before building (versions brief G4), or None when
    #: nothing had changed or `git.auto_commit` is false; `git` says why there is none when
    #: the repository could not be written.
    commit: str | None = None
    git: str | None = None
    #: `--stale`: the models the run chose because they were not fresh (empty when every
    #: model was, and nothing ran); None for a run that was not `--stale`.
    selected: list[str] | None = None

    @property
    def ok(self) -> bool:
        return all(r.status == "success" for r in self.results)


def _dbt():
    try:
        from dbt.cli.main import dbtRunner
    except ImportError as e:  # pragma: no cover - the extra is in the dev environment
        raise DbtMissing(
            "dbt is not installed: `pip install 'lakelet[dbt]'` (or `uv sync` in a clone)"
        ) from e
    return dbtRunner()


def profiles_yml(catalog_url: str) -> str:
    return f"""# Written by Lakelet (`lakelet run`, `lakelet serve`, `lakelet catalog serve`) with
# the address of the catalog that process serves; it is good while that process runs.
# For a `dbt run` or `dbt test` by hand: `lakelet catalog serve` in one terminal, then
# `dbt run --profiles-dir .lakelet/dbt` in another. Build with `lakelet run` to record views.

# dbt sends anonymous usage statistics to its own collector unless it is told not to.
# `lakelet run` sets dbt's `DO_NOT_TRACK` for its own invocations; this turns it off for a
# `dbt` you run by hand through this profile, so nothing leaves the machine on either path
# (versions brief G11). Your own profiles are your own business; this is the one Lakelet
# writes, and Lakelet rewrites it whenever a process starts.
config:
  send_anonymous_usage_stats: false

lakelet:
  target: local
  outputs:
    local:
      type: duckdb
      path: ":memory:"
      schema: main
      threads: 1
      plugins:
        - module: lakelet.dbt.plugin
          config:
            catalog_url: "{catalog_url}"
"""


def write_profile(project: Project, catalog_url: str | None = None) -> Path:
    """`.lakelet/dbt/profiles.yml` for the catalog at ``catalog_url`` (this process's by
    default). `lakelet run` writes it before every dbt call; `lakelet serve` and
    `lakelet catalog serve` write it when they start, so `dbt run --profiles-dir
    .lakelet/dbt` works by hand for as long as one of them is up."""
    dbt_dir = project.lakelet_dir / "dbt"
    dbt_dir.mkdir(parents=True, exist_ok=True)
    path = dbt_dir / "profiles.yml"
    path.write_text(profiles_yml(catalog_url or project.catalog_url))
    return path


def _paths(project: Project) -> tuple[Path, Path, Path]:
    from lakelet.project import LAKELET_VIEW_MACROS

    dbt_dir = project.lakelet_dir / "dbt"
    write_profile(project)
    # A project set up before views existed gets Lakelet's view macros the way `init`
    # writes them: only if the file is absent, never over a file that is there.
    view_macros = project.root / "macros" / "lakelet_views.sql"
    if not view_macros.exists():
        view_macros.parent.mkdir(parents=True, exist_ok=True)
        view_macros.write_text(LAKELET_VIEW_MACROS)
    return dbt_dir, dbt_dir / "target", dbt_dir / "logs"


def _invoke(project: Project, verb: str, args: list[str]) -> Any:
    dbt_dir, target, logs = _paths(project)
    runner = _dbt()
    # The view materialisation warns under a bare `dbt run` (its views are that session's
    # only); under `lakelet run` they are recorded afterwards, so it stays quiet.
    os.environ["LAKELET_RUN"] = "1"
    # dbt sends anonymous usage statistics to its own collector unless told not to, and
    # `lakelet run` is the one verb that invokes it. Nothing Lakelet does leaves the machine
    # (D33), so dbt does not either; `DO_NOT_TRACK` is dbt's own switch for it and sets
    # `SEND_ANONYMOUS_USAGE_STATS` to false. A user who wants to send dbt statistics runs
    # `dbt` themselves. Versions brief G11.
    os.environ["DO_NOT_TRACK"] = "1"
    result = runner.invoke(
        [
            verb,
            "--project-dir",
            str(project.root),
            "--profiles-dir",
            str(dbt_dir),
            "--target-path",
            str(target),
            "--log-path",
            str(logs),
            "--no-use-colors",
            "--quiet",
            # `compile --select <model>` prints that model's compiled SQL on stdout even
            # under --quiet, ahead of Lakelet's own DAG; the stdout log level off keeps
            # stdout Lakelet's, and the file log under .lakelet/dbt/logs keeps dbt's
            # default. Failures still arrive as the result's exception below.
            "--log-level",
            "none",
            "--log-level-file",
            "debug",
            *args,
        ]
    )
    remove_stray_data_dir()  # F1: dbt's own DuckDB connection leaves the same empty folder
    if not result.success and result.exception is not None:
        raise DbtFailed(str(result.exception).splitlines()[0])
    return result


def _selection(select: list[str]) -> list[str]:
    return ["--select", *select] if select else []


def _ordered(models: dict[str, PlannedModel]) -> list[PlannedModel]:
    """Dependency order: a model after everything it refs."""
    done: list[PlannedModel] = []
    seen: set[str] = set()

    def visit(uid: str) -> None:
        if uid in seen or uid not in models:
            return
        seen.add(uid)
        for dep in models[uid].depends_on:
            visit(dep)
        done.append(models[uid])

    for uid in sorted(models):
        visit(uid)
    return done


def manifest_path(project: Project) -> Path:
    return project.lakelet_dir / "dbt" / "target" / "manifest.json"


def manifest_is_stale(project: Project) -> bool:
    """No manifest from a compile yet, or a file under `models/` newer than it."""
    path = manifest_path(project)
    if not path.exists():
        return True
    written = path.stat().st_mtime
    models = project.root / "models"
    return any(f.stat().st_mtime > written for f in models.rglob("*") if f.is_file())


def manifest(project: Project, compile_if_stale: bool = True) -> tuple[dict[str, Any], bool]:
    """The last compile's `manifest.json`, compiled first when it is missing or older than
    the models (versions brief G8, lineage). The second value says whether this call
    compiled. With ``compile_if_stale`` false a stale manifest is read as it is."""
    compiled = False
    if compile_if_stale and manifest_is_stale(project):
        _invoke(project, "compile", [])
        compiled = True
    data = json.loads(manifest_path(project).read_text(encoding="utf-8"))
    if compile_if_stale and not compiled and _partly_compiled(data):
        # a `lakelet run <selector>` compiled only what it selected: the other models'
        # SQL is missing, and what a model names bare in its SQL is lineage too
        _invoke(project, "compile", [])
        data = json.loads(manifest_path(project).read_text(encoding="utf-8"))
        compiled = True
    return data, compiled


def _partly_compiled(manifest: dict[str, Any]) -> bool:
    return any(
        node.get("resource_type") == "model" and not node.get("compiled_code")
        for node in manifest.get("nodes", {}).values()
    )


def plan(project: Project, select: list[str] | None = None) -> list[PlannedModel]:
    """Compile, then estimate every model's compiled SQL in dependency order, giving the
    engine each view model as it goes so the models after it bind."""
    _invoke(project, "compile", _selection(select or []))
    _, target, _ = _paths(project)
    manifest = json.loads((target / "manifest.json").read_text())
    models: dict[str, PlannedModel] = {}
    for uid, node in manifest["nodes"].items():
        if node.get("resource_type") != "model" or not node.get("compiled_code"):
            continue
        models[uid] = PlannedModel(
            name=node["name"],
            unique_id=uid,
            materialized=node.get("config", {}).get("materialized", "view"),
            depends_on=[
                d for d in node.get("depends_on", {}).get("nodes", []) if d in manifest["nodes"]
            ],
            compiled_sql=node["compiled_code"].strip(),
            description=node.get("description") or "",
            path=node.get("original_file_path") or node.get("path") or "",
            tests=model_tests(manifest, uid),
        )
    for m in models.values():
        m.last_run = _last_run(project, m.unique_id)
    ordered = _ordered(models)
    existing = set(project.store.list_tables("main"))
    stand_ins: list[str] = []
    try:
        for m in ordered:
            try:
                est = project.estimate(_stand_in(m.compiled_sql, stand_ins))
            except Exception as e:  # noqa: BLE001 - the gauge never blocks; the run will say
                m.error = str(e).splitlines()[0]
                continue
            m.estimate = est
            m.verdict, m.words, m.reason = est.verdict, est.words, est.reason
            m.est_wall_local, m.est_bytes = est.wall_local, est.bytes_scanned
            if m.materialized == "view" or m.name not in existing:
                # A view model, or a table not built yet: the models after it bind
                # against its query, which for a table is a stand-in until the run.
                try:
                    project.engine.put_view(m.name, _stand_in(m.compiled_sql, stand_ins))
                    if m.materialized != "view":
                        stand_ins.append(m.name)
                except Exception as e:  # noqa: BLE001
                    m.error = str(e).splitlines()[0]
    finally:
        for name in stand_ins:
            project.engine.drop_view(name)
    _states(project, ordered)
    return ordered


def _states(project: Project, ordered: list[PlannedModel]) -> None:
    """Each model's state (V3) from lineage's graph (the manifest is the one just
    compiled, so nothing compiles again; `Graph.states` has the rules), then what
    changed behind it."""
    from lakelet.lineage import Graph

    graph = Graph(project, compile_if_stale=False)
    states = graph.states()
    for m in ordered:
        m.state, m.state_reason, m.state_since = states.get(m.name, ("never", "never built", None))
        m.state_diff, m.state_changes = _what_changed(project, m, graph)


def model_tests(manifest: dict[str, Any], model_uid: str) -> list[ModelTest]:
    """The tests the manifest attaches to a model: a generic test (`not_null`, `unique`,
    `accepted_values`, `relationships`, or a project's own) names its column; a singular
    test (a SQL file under `tests/`) depends on the model and has no column."""
    out: list[ModelTest] = []
    for uid, node in sorted(manifest["nodes"].items()):
        if node.get("resource_type") != "test":
            continue
        attached = node.get("attached_node")
        depends = node.get("depends_on", {}).get("nodes", [])
        if attached != model_uid and (attached or model_uid not in depends):
            continue
        meta = node.get("test_metadata") or {}
        column = node.get("column_name") or (meta.get("kwargs") or {}).get("column_name")
        out.append(
            ModelTest(
                name=node["name"],
                kind=meta.get("name") or "singular",
                column=column,
                unique_id=uid,
            )
        )
    return out


def _last_run(project: Project, unique_id: str) -> LastRun | None:
    run = project.history.model_last_run(unique_id)
    if run is None:
        return None
    return LastRun(
        ts=run.ts.isoformat() if run.ts else "",
        ok=run.ran and not run.error,
        seconds=run.actual_wall,
        verdict=run.verdict,
        error=run.error,
        sql_hash=run.sql_hash,
        sql_text=run.sql_text,
    )


def _what_changed(project: Project, m: PlannedModel, graph: Any) -> tuple[str | None, list]:
    """The evidence behind a state that is not fresh: the SQL diff since the last run for
    `edited`; for `upstream` naming a table or view, what was committed to it since."""
    import difflib

    r = m.last_run
    if m.state == "edited" and r is not None and r.sql_text is not None:
        before, now = r.sql_text.splitlines(), m.compiled_sql.splitlines()
        # the whole SQL as context, so a reader can see the change where it sits; the
        # app folds it to the changed lines and shows the whole on request
        lines = difflib.unified_diff(
            before, now, "last run", "now", n=max(len(before), len(now)), lineterm=""
        )
        return "\n".join(lines), []
    if m.state == "upstream" and r is not None and r.ts and m.state_reason:
        name, _, what = m.state_reason.rpartition(" ")
        if what == "changed":
            return None, _committed_since(project, graph, name, datetime.fromisoformat(r.ts))
    return None, []


def _committed_since(project: Project, graph: Any, name: str, since: datetime) -> list:
    node = graph.nodes.get(name)
    if node is None:
        return []
    if node.kind == "view":
        return [
            {
                "name": name,
                "operation": "new version",
                "added_rows": None,
                "deleted_rows": None,
                "timestamp": node.freshness.isoformat() if node.freshness else None,
            }
        ]
    try:
        md = project.tables._metadata(name)
    except Exception:  # noqa: BLE001 - a table that does not resolve (moved, T5) has no list
        return []
    out = []
    for snap in sorted(md.snapshots, key=lambda s: s.timestamp_ms, reverse=True):
        when = datetime.fromtimestamp(snap.timestamp_ms / 1000, tz=since.tzinfo)
        if when <= since:
            break
        props = snap.summary.additional_properties if snap.summary else {}
        out.append(
            {
                "name": name,
                "operation": snap.summary.operation.value if snap.summary else None,
                "added_rows": int(props["added-records"]) if "added-records" in props else None,
                "deleted_rows": (
                    int(props["added-position-deletes"])
                    if "added-position-deletes" in props
                    else None
                ),
                "timestamp": when.isoformat(),
            }
        )
    return out


def unqualified(sql: str) -> str:
    """dbt qualifies every `ref()` with the database (`"lakelet"."main"."t"`, or
    `"memory"."main"."v"` for a view); the view recorded in the catalog says `"main"."t"`,
    which DuckDB resolves through the search path and Spark through the default
    namespace, so the same SQL reads in both."""
    return sql.replace('"lakelet"."main".', '"main".').replace('"memory"."main".', '"main".')


def _stand_in(sql: str, names: list[str]) -> str:
    """For the estimate only: a table model not built yet is referred to by dbt as
    `"lakelet"."main"."name"`; the stand-in view for it lives in `memory.main`."""
    for name in names:
        for pattern in (f'"lakelet"."main"."{name}"', f"lakelet.main.{name}"):
            sql = sql.replace(pattern, f'"memory"."main"."{name}"')
    return sql


def run(
    project: Project,
    select: list[str] | None = None,
    burst: str = "never",
    run_anyway: bool = False,
    stale: bool = False,
) -> RunReport:
    """``stale`` (V3, `lakelet run --stale`, the app's Refresh what changed): plan the
    whole project and build only the models that are not fresh, in dependency order; when
    every model is fresh nothing runs and the report says so."""
    if burst != "never":
        raise NoBurstYet(
            "--burst auto is session 8's; there is no burst yet. `--burst never` runs "
            "everything here."
        )
    started = time.perf_counter()
    planned = plan(project, None if stale else select)
    report = RunReport(models=planned)
    chosen = planned
    if stale:
        chosen = [m for m in planned if m.state != "fresh"]
        select = [m.name for m in chosen]
        report.selected = list(select)
        if not chosen:
            report.seconds = time.perf_counter() - started
            return report
    red = [m.name for m in chosen if m.verdict == "red"]
    if red and not run_anyway:
        raise RedRefusedRun(
            f"{len(red)} model(s) need more machine: {', '.join(red)}. `--run-anyway` runs "
            "the DAG here regardless."
        )
    # After the refusal and before dbt: a run that never happened records no version (G4).
    report.commit, report.git = _record_version(project, planned)
    result = _invoke(project, "run", _selection(select or []))
    by_name = {m.name: m for m in planned}
    for r in result.result.results if result.result else []:
        report.results.append(
            ModelResult(
                name=r.node.name,
                status=str(r.status),
                seconds=float(r.execution_time or 0.0),
                message=(str(r.message).splitlines()[0] if r.message else None),
            )
        )
    # The views first, then the runs: a model's state (V3) compares what it reads against
    # the time its run was recorded, and a view it reads gets its version here.
    _record_views(project, planned, report, prune=not select)
    for r in report.results:
        m = by_name.get(r.name)
        if m is not None and m.estimate is not None:
            _record(project, m, r.status, r.seconds)
    report.seconds = time.perf_counter() - started
    return report


def _record_version(project: Project, planned: list[PlannedModel]) -> tuple[str | None, str | None]:
    """Before dbt builds anything, a version of what it is about to build (versions brief
    G4), so a model edited in an editor has history in the app and not only questions. The
    files are the ones the manifest names, plus the project's own dbt files; the message
    names the models whose file changed. Nothing changed means no commit.

    ``git.auto_commit = false`` turns this off for a developer who keeps their own git.
    Saves still commit: a save with no version is the one thing the product promises not
    to do."""
    from lakelet import versions

    if not project.config.git.auto_commit:
        return None, None
    by_path = {m.path: m.name for m in planned if m.path}
    candidates = [*by_path, "dbt_project.yml", *_macro_files(project)]
    changed = versions.changed(project.root, candidates)
    if not changed:
        return None, None
    names = sorted({by_path[p] for p in changed if p in by_path})
    what = f"{', '.join(names)} changed" if names else "project files changed"
    result = versions.commit(project.root, changed, f"run: {what}")
    return result.id, result.reason


def _macro_files(project: Project) -> list[str]:
    macros = project.root / "macros"
    return [str(p.relative_to(project.root)) for p in sorted(macros.glob("*.sql"))]


def _record(project: Project, m: PlannedModel, status: str, seconds: float) -> None:
    """A model's run in history, as a query's would be (D7): the estimate from the plan,
    the actual wall time from dbt."""
    est = m.estimate
    profile = inputs.machine_profile(project.engine, str(project.root))
    cache = inputs.load_machine_cache(project.cache_dir)
    run = Run(
        fingerprint=est.fingerprint,
        sql_hash=sql_hash(m.compiled_sql),
        sql_text=m.compiled_sql,
        lakelet_version=__version__,
        duckdb_version=duckdb.__version__,
        machine_hash=inputs.machine_hash(profile),
        machine=profile,
        tables=[{k: v for k, v in t.items() if k != "source"} for t in est.tables],
        operator_counts=inputs.operator_counts(est.plan),
        pruning=est.pruning,
        throughput_local_mbps=cache.get("throughput_local_mbps"),
        bandwidth_mbps=cache.get("bandwidth_mbps"),
        est_bytes=est.bytes_scanned,
        est_peak_mem=est.peak_memory,
        est_wall_local=est.wall_local,
        est_wall_burst=est.wall_burst,
        est_cost_burst=est.cost_burst,
        verdict=est.verdict,
        reason=est.reason,
        ran=status == "success",
        ran_where="local",
        actual_wall=seconds if status == "success" else None,
        error=None if status == "success" else f"dbt: {status}",
    )
    run_id = project.history.record(run)
    project.history.record_model_run(m.unique_id, run_id)


def _record_views(
    project: Project, planned: list[PlannedModel], report: RunReport, prune: bool
) -> None:
    """After the run: every view model that built becomes (or updates) a catalog view; on
    a run of the whole project, a catalog view that came from a dbt model no longer in
    the project is dropped."""
    ok = {r.name for r in report.results if r.status == "success"}
    for m in planned:
        if m.materialized == "view" and m.name in ok:
            project.views.put(
                m.name, unqualified(m.compiled_sql), {DBT_MODEL_PROPERTY: m.unique_id}
            )
            report.views_recorded.append(m.name)
    if not prune:
        return
    names = {m.name for m in planned}
    for view in project.views.list():
        if DBT_MODEL_PROPERTY in view.properties and view.name not in names:
            project.views.drop(view.name)
            report.views_dropped.append(view.name)


def dag_lines(models: list[PlannedModel]) -> list[str]:
    """One line per model, the CLI's DAG: name, materialisation, verdict, the estimate, and
    the state with its reason (V3)."""
    from lakelet.gauge.verdict import human_seconds

    width = max((len(m.name) for m in models), default=4)
    out = []
    for m in models:
        if m.error:
            out.append(f"  {m.name:<{width}}  {m.materialized:<5}  ?      {m.error}")
            continue
        est = human_seconds(m.est_wall_local) if m.est_wall_local is not None else ""
        state = state_words(m)
        out.append(
            f"  {m.name:<{width}}  {m.materialized:<5}  {m.verdict or '?':<6} {est:<8}  {state}"
        )
    return out


def state_words(m: PlannedModel) -> str:
    """`fresh`, or the state and why: `upstream: orders changed`, `edited: the SQL changed
    since the last run`, `never: never built`."""
    if m.state in (None, "fresh"):
        return m.state or ""
    return f"{m.state}: {m.state_reason}" if m.state_reason else str(m.state)
