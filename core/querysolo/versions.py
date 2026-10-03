# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Git, done for the user (versions brief G1, G2, G3, G9). One module owns the repository:
``init`` makes the project folder one and commits what it wrote, and every save commits the
files it wrote with a message a person would write.

Git is dulwich, a pure-Python library, not the ``git`` binary (G1): a fresh Mac has no
``git`` until the Command Line Tools are installed, and the first call to it pops Apple's
install dialogue, which is the "being told" Simple mode promises never happens.

The commit is built by hand rather than through dulwich's ``WorkTree.commit``, for two
reasons. A commit from the index would carry whatever else the user had staged, and the
brief says a save commits its own files and nothing else (G3). And building the object
ourselves signs nothing, so a developer's ``commit.gpgsign = true`` produces an unsigned
commit instead of an error (§7). Paths the repository ignores are dropped before staging, so
``warehouse/``, ``.querysolo/`` and anything else in ``.gitignore`` can never be committed (G9).

Nothing here reaches the network: there is no fetch and no push, so ``querysolo audit network``
still reads zero.
"""

from __future__ import annotations

import getpass
import socket
import stat
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

if TYPE_CHECKING:
    from dulwich.repo import Repo

DEFAULT_BRANCH = b"refs/heads/main"


@dataclass
class Commit:
    """What a commit attempt leaves behind. ``id`` is the full commit id when one was made.
    ``unchanged`` means the files were already what the repository holds, so there was
    nothing to record. ``reason`` is why there is no commit when the repository could not be
    opened or written; it travels to the caller as ``git:`` and nothing raises (G9)."""

    id: str | None = None
    author: str | None = None
    unchanged: bool = False
    reason: str | None = None


@dataclass
class Version:
    """One entry in a model's history (G5). ``sql_changed`` is false for a commit that
    touched only the ``schema.yml`` entry, which the list marks rather than hides;
    ``checks_changed`` is what the app shows as "checks changed" / "checks unchanged".
    ``diff`` is the unified diff of the model's own file against the version before it."""

    id: str
    when: str
    author: str
    message: str
    sql_changed: bool
    checks_changed: bool
    diff: str = ""

    @property
    def short(self) -> str:
        return self.id[:7]


def short(commit_id: str) -> str:
    """The seven characters the CLI and the app show."""
    return commit_id[:7]


def open_repository(root: Path) -> Repo | None:
    """The repository this folder is in, or None. A project inside a monorepo finds the
    monorepo's, which is the one saves commit to (G2). A ``.git`` that cannot be opened at
    all — a broken one, or a file that is not a repository — is None here and becomes a
    reason when a commit is tried (G9)."""
    from dulwich.repo import Repo

    try:
        return Repo.discover(str(root))
    except Exception:  # noqa: BLE001 - git is never allowed to fail an operation (G9)
        return None


def init_repository(root: Path) -> Repo:
    """``git init`` on the folder, on branch ``main``."""
    from dulwich.repo import Repo

    return Repo.init(str(root), default_branch=DEFAULT_BRANCH)


def status(root: Path) -> dict[str, Any]:
    """The one line the app's panel says about git (G6): whether the folder is in a
    repository, the branch HEAD is on, and the ``origin`` remote's URL when one is set.
    Read from the repository and its config, nothing else; never raises."""
    repo = open_repository(root)
    if repo is None:
        return {"repository": False, "branch": None, "origin": None}
    with repo:
        branch = origin = None
        try:
            head = repo.refs.read_ref(b"HEAD") or b""
            if head.startswith(b"ref: refs/heads/"):
                branch = head.removeprefix(b"ref: refs/heads/").decode("utf-8", "replace")
        except Exception:  # noqa: BLE001 - a line, never a failure (G9)
            pass
        try:
            url = repo.get_config_stack().get((b"remote", b"origin"), b"url")
            origin = url.decode("utf-8", "replace")
        except KeyError:
            pass
    return {"repository": True, "branch": branch, "origin": origin}


def author(repo: Repo) -> str:
    """Git's own identity, read from the same files git reads (the repository's config, the
    user's, the system's). With none set, the OS user and this host, which is what git itself
    falls back to (G3)."""
    config = repo.get_config_stack()

    def value(name: bytes) -> str | None:
        try:
            return config.get((b"user",), name).decode("utf-8", "replace")
        except KeyError:
            return None

    name = value(b"name") or getpass.getuser()
    email = value(b"email") or f"{getpass.getuser()}@{socket.gethostname()}"
    return f"{name} <{email}>"


def _relative(root: Path, worktree: Path, paths: Iterable[Path | str]) -> list[str]:
    """The paths that exist, as slash-separated paths inside the repository's working tree,
    in the order given and without repeats. A relative path is the project's; the working
    tree is a parent of it when the project sits inside a monorepo."""
    out: list[str] = []
    for path in paths:
        p = Path(path)
        full = (p if p.is_absolute() else root / p).resolve()
        if not full.exists():
            continue
        relative = full.relative_to(worktree.resolve()).as_posix()
        if relative not in out:
            out.append(relative)
    return out


def _insert(store, tree_id, parts: list[str], blob_id: bytes, mode: int) -> bytes:
    """One path into a tree, returning the new tree's id. Every tree along the way is
    rewritten; everything else in the repository is carried over untouched."""
    from dulwich.objects import Tree

    tree = store[tree_id] if tree_id is not None else Tree()
    if not isinstance(tree, Tree):  # a file where this path wants a folder
        tree = Tree()
    name = parts[0].encode()
    if len(parts) == 1:
        tree.add(name, mode, blob_id)
    else:
        sub = None
        if name in tree:
            sub_mode, sub_id = tree[name]
            if stat.S_ISDIR(sub_mode):
                sub = sub_id
        tree.add(name, stat.S_IFDIR, _insert(store, sub, parts[1:], blob_id, mode))
    store.add_object(tree)
    return tree.id


def commit(root: Path, paths: Iterable[Path | str], message: str) -> Commit:
    """Stage those paths and commit them, and nothing else. The repository is the one the
    folder is in; a project that is not in one yet gets one here, which is how a project made
    before this version gets its history on its next save (G2).

    Never raises: a repository that cannot be opened or written comes back as a ``reason``,
    and the caller's files are already on disk either way (G9).
    """
    try:
        repo = open_repository(root) or init_repository(root)
        with repo:
            return _commit(repo, root, paths, message)
    except Exception as e:  # noqa: BLE001 - git is never allowed to fail a save (G9)
        return Commit(reason=f"{type(e).__name__}: {str(e).splitlines()[0]}")


def _commit(repo: Repo, root: Path, paths: Iterable[Path | str], message: str) -> Commit:
    from dulwich.ignore import IgnoreFilterManager
    from dulwich.objects import Commit as CommitObject

    ignored = IgnoreFilterManager.from_repo(repo)
    relative = [p for p in _relative(root, Path(repo.path), paths) if not ignored.is_ignored(p)]
    if not relative:
        return Commit(unchanged=True)

    worktree = repo.get_worktree()
    worktree.stage(relative)  # the index entries for these paths only
    index = repo.open_index()

    store = repo.object_store
    try:
        head = repo.refs[b"HEAD"]  # KeyError on a repository with no commit yet
    except KeyError:
        head = None
    tree_id = store[head].tree if head else None
    for path in relative:
        entry = index[path.encode()]
        tree_id = _insert(store, tree_id, path.split("/"), entry.sha, entry.mode)
    if head is not None and tree_id == store[head].tree:
        return Commit(unchanged=True)

    who = author(repo)
    offset = -(time.altzone if time.localtime().tm_isdst > 0 else time.timezone)
    obj = CommitObject()
    obj.tree = tree_id
    obj.parents = [head] if head else []
    obj.author = obj.committer = who.encode("utf-8")
    obj.author_time = obj.commit_time = int(time.time())
    obj.author_timezone = obj.commit_timezone = offset
    obj.encoding = b"UTF-8"
    obj.message = message.encode("utf-8")
    store.add_object(obj)
    repo.refs[b"HEAD"] = obj.id
    return Commit(id=obj.id.decode(), author=who)


# -- reading the history (G5) -----------------------------------------------------------


class NoHistory(Exception):
    """There is no repository, or the file has never been committed to it: the caller shows
    the sentence saying why rather than an empty screen (G5)."""


def _blob(store, commit, path: str) -> bytes | None:
    """The file's bytes at that commit, or None when it was not in it."""
    from dulwich.object_store import tree_lookup_path

    try:
        _, sha = tree_lookup_path(store.__getitem__, commit.tree, path.encode())
    except KeyError:
        return None
    return store[sha].data


def _text(data: bytes | None) -> list[str]:
    return data.decode("utf-8", "replace").splitlines(keepends=True) if data else []


def _schema_entry(data: bytes | None, name: str):
    """One model's entry in a ``schema.yml``. Every question in a project shares that file, so
    a commit is only a version of *this* question when *its* entry changed: comparing the file
    would put every other question's save in this one's history. An unparseable file falls
    back to its bytes, so a change to it still shows rather than being swallowed."""
    if data is None:
        return None
    try:
        loaded = yaml.safe_load(data.decode("utf-8", "replace")) or {}
        for model in loaded.get("models") or []:
            if isinstance(model, dict) and model.get("name") == name:
                return model
        return None
    except Exception:  # noqa: BLE001 - a broken schema.yml is not a reason to fail a list
        return data


def log_path(
    root: Path, path: Path | str, also: Path | str | None = None, model: str | None = None
) -> list[Version]:
    """The commits that touched ``path``, newest first, each with the unified diff of that
    file against the version before it. ``also`` is the model's ``schema.yml`` and ``model``
    its name in it: a commit that touched only this model's entry is in the list, marked,
    because a change to the checks is a version of the question too (G5). A commit that
    touched the file for some other model's sake is not."""
    import difflib

    repo = open_repository(root)
    if repo is None:
        raise NoHistory("this project is not in a git repository yet; its first save makes one")
    with repo:
        worktree = Path(repo.path)
        watched = _relative(root, worktree, [p for p in (path, also) if p is not None])
        if not watched:
            raise NoHistory(f"{Path(path).name} is not a file in this project")
        sql, schema = watched[0], (watched[1] if len(watched) > 1 else None)
        store = repo.object_store
        out: list[Version] = []
        for entry in repo.get_walker(paths=[p.encode() for p in watched]):
            commit = entry.commit
            parent = store[commit.parents[0]] if commit.parents else None
            now, before = _blob(store, commit, sql), (_blob(store, parent, sql) if parent else None)
            checks_changed = (
                schema is not None
                and model is not None
                and (
                    _schema_entry(_blob(store, commit, schema), model)
                    != _schema_entry(_blob(store, parent, schema) if parent else None, model)
                )
            )
            if now == before and not checks_changed:
                continue  # the walker matched a path this commit did not actually change
            out.append(
                Version(
                    id=commit.id.decode(),
                    when=datetime.fromtimestamp(
                        commit.commit_time, tz=timezone(timedelta(seconds=commit.commit_timezone))
                    ).isoformat(),
                    author=commit.author.decode("utf-8", "replace"),
                    message=commit.message.decode("utf-8", "replace").strip(),
                    sql_changed=now != before,
                    checks_changed=checks_changed,
                    diff="".join(
                        difflib.unified_diff(_text(before), _text(now), "before", "after", n=3)
                    ),
                )
            )
        if not out:
            raise NoHistory(
                f"{Path(path).name} has no versions yet: it is not in the repository. A save "
                "records one; `querysolo run` does too unless `git.auto_commit` is false"
            )
        return out


def show(root: Path, path: Path | str, commit_id: str) -> str:
    """That version's file content. Any unambiguous prefix of the commit id is accepted."""
    repo = open_repository(root)
    if repo is None:
        raise NoHistory("this project is not in a git repository yet; its first save makes one")
    with repo:
        [relative] = _relative(root, Path(repo.path), [path])
        commit = repo.object_store[_resolve(repo, commit_id)]
        data = _blob(repo.object_store, commit, relative)
        if data is None:
            raise NoHistory(f"{Path(path).name} is not in version {short(commit_id)}")
        return data.decode("utf-8", "replace")


def _resolve(repo, commit_id: str) -> bytes:
    """A full commit id, or any unambiguous prefix of one (§3)."""
    wanted = commit_id.lower().encode()
    if len(wanted) == 40:
        return wanted
    matches = {entry.commit.id for entry in repo.get_walker() if entry.commit.id.startswith(wanted)}
    if not matches:
        raise NoHistory(f"no version {commit_id} in this project")
    if len(matches) > 1:
        raise NoHistory(f"{commit_id} matches {len(matches)} versions; give more of it")
    return matches.pop()


def changed(root: Path, paths: Iterable[Path | str]) -> list[str]:
    """Which of those paths differ from what the repository holds: the files a run would
    record (G4). Paths the repository ignores, and paths that do not exist, are not in it."""
    from dulwich.ignore import IgnoreFilterManager
    from dulwich.objects import Blob

    repo = open_repository(root)
    if repo is None:
        return []
    with repo:
        ignored = IgnoreFilterManager.from_repo(repo)
        worktree = Path(repo.path)
        try:
            head = repo.object_store[repo.refs[b"HEAD"]]
        except KeyError:
            head = None
        out = []
        for relative in _relative(root, worktree, paths):
            if ignored.is_ignored(relative):
                continue
            data = (worktree / relative).read_bytes()
            before = _blob(repo.object_store, head, relative) if head else None
            if before is None or Blob.from_string(data).id != Blob.from_string(before).id:
                out.append(relative)
        return out


# -- a project's versions (G5) ----------------------------------------------------------


class NoSuchModel(Exception):
    pass


class Versions:
    """One model's history, by the name the CLI and the app use. A saved question and a
    hand-written model are the same thing here: a file under ``models/`` with commits behind
    it. Nothing here compiles the project, so a version list costs no dbt run."""

    def __init__(self, project) -> None:
        self.project = project

    def path(self, name: str) -> Path:
        """``models/questions/<name>.sql`` for a question, otherwise the first
        ``models/**/<name>.sql``. Resolved off disk, not from the manifest, so listing a
        model's versions never waits for a compile."""
        question = self.project.root / "models" / "questions" / f"{name}.sql"
        if question.exists():
            return question
        found = sorted((self.project.root / "models").glob(f"**/{name}.sql"))
        if not found:
            raise NoSuchModel(f"no model or question named {name} under models/")
        return found[0]

    def is_question(self, path: Path) -> bool:
        return path.parent == self.project.root / "models" / "questions"

    def status(self) -> dict[str, Any]:
        """The panel's git line (G6): repository, branch, origin."""
        return status(self.project.root)

    def list(self, name: str) -> list[Version]:
        path = self.path(name)
        schema = path.parent / "schema.yml" if self.is_question(path) else None
        return log_path(self.project.root, path, schema, model=name if schema else None)

    def sql(self, name: str, commit_id: str) -> str:
        return show(self.project.root, self.path(name), commit_id)

    def restore(self, name: str, commit_id: str) -> Commit:
        """Write that version's content over the current file and commit it, so a restore is
        itself a version and ``git log`` stays linear — nothing is reset (G5). For a question
        the ``schema.yml`` entry is re-derived from the restored file, whose first comment
        line is the title (D30); for a model the file is all there is."""
        path = self.path(name)
        content = self.sql(name, commit_id)
        path.write_text(content, encoding="utf-8")
        if not self.is_question(path):
            return commit(self.project.root, [path], f"restore model: {name} to {short(commit_id)}")
        questions = self.project.questions
        title = (
            content.splitlines()[0].removeprefix("-- ").strip()
            if content.startswith("-- ")
            else name
        )
        questions.write_entry(name, title, questions.strip_header(content))
        return commit(
            self.project.root,
            [path, questions.schema_path],
            f"restore question: {title} to {short(commit_id)}",
        )
