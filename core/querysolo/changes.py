# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""`querysolo changes` (decisions L2): everything that happened to the project, newest first,
across tables, models and versions, from three sources the core already keeps — the
catalog's snapshots, history's runs, git's commits — merged by time. Nothing is recorded
here; the feed reads what is there."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import PurePosixPath
from typing import TYPE_CHECKING, Any

from querysolo.project import NAMESPACE

if TYPE_CHECKING:
    from querysolo.project import Project

KINDS = ("snapshot", "run", "version")
TARGETS = ("table", "model", "question", "project")


@dataclass
class Change:
    """One entry. ``kind`` says which source: a table's ``snapshot`` (with its operation and
    rows, and ``affects``, the models it made out of date — decisions L3), a model's or a
    question's ``run`` (every one history holds, since schema 2), or a ``version`` (a git
    commit touching the models: a save, a restore, a run-time commit).
    ``name`` is what the entry is about and ``target`` what kind of thing that is, for the
    link; a version names every model and question it touched in ``names``."""

    when: datetime
    kind: str
    name: str | None
    target: str
    operation: str | None = None
    snapshot_id: int | None = None
    added_rows: int | None = None
    deleted_rows: int | None = None
    affects: list[str] = field(default_factory=list)
    ok: bool | None = None
    seconds: float | None = None
    verdict: str | None = None
    error: str | None = None
    id: str | None = None
    author: str | None = None
    message: str | None = None
    names: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["when"] = self.when.isoformat()
        return d

    def sentence(self) -> str:
        """The CLI's line, in Technical words; the app builds the mode's own."""
        if self.kind == "snapshot":
            what = _snapshot_words(self.operation, self.added_rows, self.deleted_rows)
            tail = f"; made out of date: {', '.join(self.affects)}" if self.affects else ""
            return f"{self.name}: {what}{tail}"
        if self.kind == "run":
            verb = "answered" if self.target == "question" else "built"
            if not self.ok:
                return f"{self.name} failed to build: {self.error or 'no reason recorded'}"
            took = f" in {self.seconds:.1f} s" if self.seconds is not None else ""
            verdict = f", {self.verdict.capitalize()}" if self.verdict else ""
            return f"{self.name} {verb}{took}{verdict}"
        who = f" · by {_author_name(self.author)}" if self.author else ""
        return f"{self.message}{who} ({self.id})"


def _snapshot_words(operation: str | None, added: int | None, deleted: int | None) -> str:
    if added and deleted:
        return f"{added:,} rows added, {deleted:,} deleted"
    if added:
        return f"{added:,} rows added"
    if deleted:
        return f"{deleted:,} rows deleted"
    return {
        "append": "rows appended",
        "overwrite": "rows replaced",
        "delete": "rows deleted",
        "replace": "rewritten",
    }.get(operation or "", operation or "changed")


def _author_name(author: str) -> str:
    return re.sub(r"\s*<[^>]*>\s*$", "", author).strip() or author


_SINCE = re.compile(r"^(\d+)([mhdw])$")


def parse_since(text: str) -> datetime:
    """``2d``, ``12h``, ``30m``, ``1w``, or an ISO date or datetime (a date is its midnight
    UTC). Anything else raises ValueError."""
    m = _SINCE.match(text.strip())
    if m:
        n, unit = int(m.group(1)), m.group(2)
        delta = {"m": "minutes", "h": "hours", "d": "days", "w": "weeks"}[unit]
        return datetime.now(UTC) - timedelta(**{delta: n})
    try:
        parsed = datetime.fromisoformat(text.strip())
    except ValueError:
        raise ValueError(f"--since takes 2d, 12h, 30m, 1w or an ISO date, not {text!r}") from None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def changes(
    project: Project,
    since: datetime | None = None,
    last: int = 50,
    name: str | None = None,
) -> list[Change]:
    """The feed, newest first: at most ``last`` entries, not older than ``since``, and with
    ``name`` only the entries about that table, model or question (a version that touched
    it counts)."""
    out = [*_snapshots(project), *_runs(project), *_versions(project, last)]
    if since is not None:
        out = [c for c in out if c.when >= since]
    if name is not None:
        out = [c for c in out if c.name == name or name in c.names]
    out.sort(key=lambda c: c.when, reverse=True)
    return out[:last]


def _snapshots(project: Project) -> list[Change]:
    from querysolo.lineage import Graph

    graph = Graph(project, compile_if_stale=False)
    out: list[Change] = []
    for table in project.store.list_tables(NAMESPACE):
        try:
            md = project.tables._metadata(table)
        except FileNotFoundError:
            continue  # a moved folder (T5): the list marks it; nothing to say here
        runs = graph.downstream_runs(table)
        for snap in md.snapshots:
            when = datetime.fromtimestamp(snap.timestamp_ms / 1000, tz=UTC)
            props = snap.summary.additional_properties if snap.summary else {}
            out.append(
                Change(
                    when=when,
                    kind="snapshot",
                    name=table,
                    target="table",
                    operation=snap.summary.operation.value if snap.summary else None,
                    snapshot_id=snap.snapshot_id,
                    added_rows=_count(props, "added-records"),
                    deleted_rows=_count(props, "added-position-deletes"),
                    affects=[n for _, n, ts in runs if ts < when],
                )
            )
    return out


def _count(props: dict[str, str], key: str) -> int | None:
    value = props.get(key)
    return int(value) if value is not None else None


def _runs(project: Project) -> list[Change]:
    out: list[Change] = []
    for target, key, run in project.history.model_and_question_runs():
        if run.ts is None:
            continue
        out.append(
            Change(
                when=run.ts,
                kind="run",
                name=key.rsplit(".", 1)[-1] if target == "model" else key,
                target=target,
                ok=bool(run.ran and not run.error),
                seconds=run.actual_wall,
                verdict=run.verdict,
                error=run.error,
            )
        )
    return out


def _versions(project: Project, last: int) -> list[Change]:
    """The commits that touched ``models/``, newest first, at most ``last`` of them: the
    names are the models and questions whose file each one changed."""
    from datetime import timezone

    from dulwich.diff_tree import tree_changes

    from querysolo.versions import open_repository

    repo = open_repository(project.root)
    if repo is None:
        return []
    out: list[Change] = []
    with repo:
        worktree = PurePosixPath(repo.path)
        try:
            prefix = PurePosixPath(project.root.resolve()).relative_to(worktree)
        except ValueError:
            prefix = PurePosixPath()
        models = prefix / "models"
        store = repo.object_store
        try:
            walker = repo.get_walker(paths=[str(models).encode()], max_entries=last)
        except KeyError:
            return []  # a repository with no commits yet
        for entry in walker:
            commit = entry.commit
            parent_tree = store[commit.parents[0]].tree if commit.parents else None
            touched: dict[str, str] = {}  # name -> question | model
            for change in tree_changes(store, parent_tree, commit.tree):
                path = change.new.path or change.old.path
                if path is None:
                    continue
                rel = PurePosixPath(path.decode("utf-8", "replace"))
                if rel.suffix != ".sql" or not rel.is_relative_to(models):
                    continue
                touched[rel.stem] = "question" if rel.parent == models / "questions" else "model"
            # one file touched: the entry is about it; several, or none: about the project
            name, target = next(iter(touched.items())) if len(touched) == 1 else (None, "project")
            out.append(
                Change(
                    when=datetime.fromtimestamp(
                        commit.commit_time,
                        tz=timezone(timedelta(seconds=commit.commit_timezone)),
                    ).astimezone(UTC),
                    kind="version",
                    name=name,
                    target=target,
                    id=commit.id.decode()[:7],
                    author=commit.author.decode("utf-8", "replace"),
                    message=commit.message.decode("utf-8", "replace").strip().splitlines()[0],
                    names=sorted(touched),
                )
            )
    return out
