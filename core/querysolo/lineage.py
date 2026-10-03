# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Table-level lineage (versions brief G8): what a table, a view or a model reads and what
reads it, from what the project already knows — the dbt manifest of the last compile
(compiled first when it is missing or older than the models) and the catalog. Nothing is
parsed here: a `ref()` or `source()` is the manifest's, a table a model names bare in its
SQL and the tables a catalog view binds to come from DuckDB's own parse of the statement,
the way the gauge resolves a view (`query._through_views`). Column-level lineage is Day 3."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from querysolo.gauge import inputs
from querysolo.register import table_property

if TYPE_CHECKING:
    from querysolo.project import Project

#: How an edge is known: a dbt `ref()`, a dbt `source()`, a table named bare in a model's
#: SQL, or the SQL of a catalog view that did not come from dbt.
VIAS = ("ref", "source", "sql", "view")
KINDS = ("table", "view", "model")


class NoSuchNode(Exception):
    """Not a table or view in the catalog, and not a model in the project."""


@dataclass
class Edge:
    name: str
    #: "table" or "view" in the catalog, or "model" for a dbt model not built yet.
    kind: str
    via: str
    #: 1 for what the node reads (or what reads it) directly; more with `--depth`.
    depth: int = 1


@dataclass
class Lineage:
    name: str
    kind: str
    upstream: list[Edge] = field(default_factory=list)
    downstream: list[Edge] = field(default_factory=list)
    #: The dbt model that builds this table or view; `imported` for a table QuerySolo wrote
    #: from files or SQL; `attached from <prefix>` for one registered in place; None for a
    #: model never built and for a view put in the catalog by hand.
    built_by: str | None = None
    #: When: the model's last successful `querysolo run` from history, or the table's
    #: current snapshot; ISO 8601, UTC.
    last_built: str | None = None
    #: True when this call compiled the models first because the manifest was stale.
    compiled: bool = False


@dataclass
class _Node:
    name: str
    kind: str
    model_uid: str | None = None
    source: str | None = None  # an attached table's prefix
    freshness: datetime | None = None
    upstream: list[Edge] = field(default_factory=list)
    #: A model's compiled SQL from the manifest; empty when the last compile skipped it.
    compiled: str = ""


#: A model's state (decisions V3): the state, why, and when — see ``Graph.states``.
ModelState = tuple[str, str | None, str | None]


class Graph:
    """Every table and view in the catalog and every model in the manifest, one node per
    name (a table model and the table it built are the same node), with its upstream
    edges; downstream is the reverse. Built once per call; a project's graph is small."""

    def __init__(self, project: Project, compile_if_stale: bool = True) -> None:
        self.project = project
        self.nodes: dict[str, _Node] = {}
        self.compiled = False
        for info in project.tables.list(views=False):
            self.nodes[info.name] = _Node(
                info.name, "table", source=info.source, freshness=info.freshness
            )
        views = {v.name: v for v in project.views.list()}
        for v in views.values():
            self.nodes[v.name] = _Node(
                v.name,
                "view",
                model_uid=table_property(v.properties, "querysolo.dbt-model"),
                freshness=datetime.fromtimestamp(v.timestamp_ms / 1000, tz=UTC),
            )
        models = self._models(compile_if_stale)
        for uid, node in models.items():
            name = node["name"]
            ours = self.nodes.get(name)
            if ours is None:
                ours = self.nodes[name] = _Node(name, "model")
            ours.model_uid = uid
            ours.compiled = (node.get("compiled_code") or "").strip()
        # edges: the manifest's first, then what the SQL names that the manifest did not
        for node in models.values():
            ours = self.nodes[node["name"]]
            for dep in node.get("depends_on", {}).get("nodes", []):
                if dep in models:
                    ours.upstream.append(self._edge(models[dep]["name"], "ref"))
                elif dep.startswith("source."):
                    ours.upstream.append(self._edge(dep.rsplit(".", 1)[1], "source"))
            self._add_sql_edges(ours, node.get("compiled_code") or "", "sql")
        for v in views.values():
            ours = self.nodes[v.name]
            if ours.model_uid is None or ours.model_uid not in models:
                self._add_sql_edges(ours, v.sql, "view")

    def _models(self, compile_if_stale: bool) -> dict[str, dict[str, Any]]:
        from querysolo.dbt import runner

        try:
            manifest, self.compiled = runner.manifest(self.project, compile_if_stale)
        except (runner.DbtMissing, FileNotFoundError):
            return {}  # no dbt, or never compiled and not asked to: the catalog's half stands
        return {
            uid: node
            for uid, node in manifest.get("nodes", {}).items()
            if node.get("resource_type") == "model"
        }

    def _edge(self, name: str, via: str) -> Edge:
        node = self.nodes.get(name)
        return Edge(name=name, kind=node.kind if node else "table", via=via)

    def _add_sql_edges(self, node: _Node, sql: str, via: str) -> None:
        if not sql.strip():
            return
        try:
            names = inputs.base_tables(self.project.engine, sql)
        except Exception:  # noqa: BLE001 - SQL DuckDB cannot parse has no lineage of its own
            return
        known = {e.name for e in node.upstream}
        for name in names:
            if name in self.nodes and name != node.name and name not in known:
                node.upstream.append(self._edge(name, via))
                known.add(name)

    def downstream_of(self, name: str) -> list[Edge]:
        out = []
        for other in self.nodes.values():
            for e in other.upstream:
                if e.name == name:
                    out.append(Edge(name=other.name, kind=other.kind, via=e.via))
        return out

    def _walk(self, name: str, depth: int, step) -> list[Edge]:
        """Breadth first to ``depth`` levels, each name once at the level it was first
        reached; a cycle (a view over itself cannot exist, but a stale manifest could say
        anything) ends where it started."""
        out: list[Edge] = []
        seen = {name}
        queue = deque([(name, 0)])
        while queue:
            current, level = queue.popleft()
            if level >= depth:
                continue
            for e in step(current):
                if e.name in seen:
                    continue
                seen.add(e.name)
                out.append(Edge(e.name, e.kind, e.via, level + 1))
                queue.append((e.name, level + 1))
        return out

    def lineage(self, name: str, depth: int = 1) -> Lineage:
        node = self.nodes.get(name)
        if node is None:
            raise NoSuchNode(f"no table, view or model named {name}")
        result = Lineage(name=name, kind=node.kind, compiled=self.compiled)
        # a `source()` can name a table the catalog does not have: an edge, not a node
        result.upstream = self._walk(
            name, depth, lambda n: self.nodes[n].upstream if n in self.nodes else []
        )
        result.downstream = self._walk(name, depth, self.downstream_of)
        result.built_by, result.last_built = self._built(node)
        return result

    def states(self) -> dict[str, ModelState]:
        """Every model's state (decisions V3), in dependency order so a model sees the
        state of what it reads: `never` (no successful run in history), `edited` (the
        compiled SQL's hash differs from the one that run recorded), `upstream` (a model
        it reads is not fresh, or a table or view it reads changed after the run), else
        `fresh`. The reason names the nearest thing that changed; the time is when."""
        out: dict[str, ModelState] = {}

        def visit(name: str) -> None:
            if name in out:
                return
            node = self.nodes[name]
            out[name] = ("fresh", None, None)  # provisional, so a cycle ends here
            for e in node.upstream:
                if e.name in self.nodes and self.nodes[e.name].model_uid is not None:
                    visit(e.name)
            out[name] = self._model_state(node, out)

        for name, node in self.nodes.items():
            if node.model_uid is not None:
                visit(name)
        return out

    def _model_state(self, node: _Node, states: dict[str, ModelState]) -> ModelState:
        from querysolo.query import sql_hash

        run = self.project.history.model_last_run(node.model_uid or "")
        if run is None:
            return "never", "never built", None
        if not run.ran or run.error:
            return "never", "the last run failed", run.ts.isoformat() if run.ts else None
        if node.compiled and run.sql_hash and sql_hash(node.compiled) != run.sql_hash:
            return "edited", "the SQL changed since the last run", None
        for e in node.upstream:
            before = states.get(e.name)
            if before is not None and before[0] != "fresh":
                return "upstream", f"{e.name} is out of date", before[2]
            up = self.nodes.get(e.name)
            if up is not None and up.freshness is not None and run.ts and up.freshness > run.ts:
                return "upstream", f"{e.name} changed", up.freshness.isoformat()
        return "fresh", None, None

    def whole(self) -> dict[str, Any]:
        """The graph as the Lineage screen draws it (decisions L1): every node with its
        kind and, for a model, its state; every edge with how it is known. An edge to a
        name that is not a node (a `source()` the catalog lacks) is left out."""
        states = self.states()
        nodes = [
            {
                "name": n.name,
                "kind": n.kind,
                "model": n.model_uid is not None,
                "state": states[n.name][0] if n.name in states else None,
                "state_reason": states[n.name][1] if n.name in states else None,
                "source": n.source,
                "freshness": n.freshness.isoformat() if n.freshness else None,
            }
            for n in self.nodes.values()
        ]
        edges = [
            {"from": e.name, "to": n.name, "via": e.via}
            for n in self.nodes.values()
            for e in n.upstream
            if e.name in self.nodes
        ]
        return {"nodes": nodes, "edges": edges, "compiled": self.compiled}

    def downstream_runs(self, name: str) -> list[tuple[int, str, datetime]]:
        """Every model downstream of ``name`` (any depth) that has a successful run, with
        its depth and that run's time; one history read per model."""
        out: list[tuple[int, str, datetime]] = []
        for e in self._walk(name, len(self.nodes) + 1, self.downstream_of):
            node = self.nodes.get(e.name)
            if node is None or node.model_uid is None:
                continue
            run = self.project.history.model_last_run(node.model_uid)
            if run is not None and run.ran and not run.error and run.ts:
                out.append((e.depth, e.name, run.ts))
        return sorted(out, key=lambda t: (t[0], t[1]))

    def affected_models(self, name: str, since: datetime) -> list[str]:
        """The models downstream of ``name`` whose last successful run is older than
        ``since`` — what a commit to the table at that time made out of date (decisions
        L3). Dependency order: by depth, then name."""
        return [n for _, n, ts in self.downstream_runs(name) if ts < since]

    def _built(self, node: _Node) -> tuple[str | None, str | None]:
        when = node.freshness.isoformat() if node.freshness else None
        if node.kind == "model":
            return None, None  # never built: nothing in the catalog carries its name
        if node.model_uid is not None:
            # history's run first; a table built by a bare `dbt run` has only its snapshot
            run = self.project.history.model_last_run(node.model_uid)
            if run is not None and run.ran and run.ts:
                when = run.ts.isoformat()
            return node.model_uid.rsplit(".", 1)[1], when
        if node.kind == "view":
            return None, when
        if node.source:
            return f"attached from {node.source}", when
        return "imported", when


def lineage(project: Project, name: str, depth: int = 1) -> Lineage:
    """`querysolo lineage <name>` and `GET /api/lineage/{name}`."""
    return Graph(project).lineage(name, depth)


def whole(project: Project) -> dict[str, Any]:
    """`querysolo lineage --all --json` and `GET /api/lineage`: the whole graph."""
    return Graph(project).whole()


__all__ = ["KINDS", "VIAS", "Edge", "Graph", "Lineage", "NoSuchNode", "lineage", "whole"]
