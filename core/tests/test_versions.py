# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Versions step 0 gate (versions brief §4, G2, G3, G9): ``init`` makes the folder a git
repository and commits what it wrote, a folder already in one is left as it is, every save is
a commit with the title and git's own author, an unchanged save commits nothing, nothing of
the user's is swept into QuerySolo's commit, and a repository that cannot be written comes back
as a reason instead of an exception."""

import os
import stat

import pytest
from dulwich.repo import Repo

from querysolo import Project, versions

SQL = "select customer, sum(amt) as revenue from orders group by 1"


def log(root):
    """The commits on the current branch, newest first, as (message, author)."""
    with Repo.discover(str(root)) as repo:
        return [
            (e.commit.message.decode().strip(), e.commit.author.decode()) for e in repo.get_walker()
        ]


def tracked(root):
    """Every path in the newest commit's tree."""
    from dulwich.object_store import iter_tree_contents

    with Repo.discover(str(root)) as repo:
        head = repo[repo.refs[b"HEAD"]]
        return sorted(p.decode() for p, _, _ in iter_tree_contents(repo.object_store, head.tree))


def use_gitconfig(monkeypatch, path, text=None):
    """Point git's global configuration at a file of this test's own, through the same two
    environment variables git itself reads, so no test depends on the machine's identity."""
    if text is not None:
        path.write_text(text, encoding="utf-8")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(path))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")


@pytest.fixture
def gitconfig(tmp_path, monkeypatch):
    """An identity to commit as."""
    use_gitconfig(
        monkeypatch,
        tmp_path / "gitconfig",
        "[user]\n\tname = Ada Lovelace\n\temail = ada@example.com\n",
    )


@pytest.fixture
def project(tmp_path, gitconfig):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=8)
    p = Project.open(root)
    p.engine.execute(
        "CREATE TABLE querysolo.main.orders AS SELECT range AS id, 'c' || (range % 5) AS customer, "
        "(range * 1.5)::DOUBLE AS amt FROM range(1000)"
    )
    yield p
    p.close()


# -- init (G2) ---------------------------------------------------------------------------


def test_init_makes_the_folder_a_repository_and_commits_what_it_wrote(tmp_path, gitconfig) -> None:
    root = tmp_path / "acme"
    report = Project.init(root, probe_mb=0)

    assert report.repository == "created" and report.git is None
    assert report.commit and len(report.commit) == 40
    assert (root / ".git").is_dir()
    with Repo.discover(str(root)) as repo:
        assert repo.refs.read_ref(b"HEAD") == b"ref: refs/heads/main"

    assert log(root) == [("querysolo init", "Ada Lovelace <ada@example.com>")]
    assert tracked(root) == [
        ".gitignore",
        "AGENTS.md",
        "dbt_project.yml",
        "macros/querysolo.sql",
        "macros/querysolo_views.sql",
        "models/.gitkeep",
        "querysolo.toml",
    ]


def test_init_never_commits_the_catalog_the_warehouse_or_the_cache(tmp_path, gitconfig) -> None:
    """G9: the commit carries model files and configuration, never data, history or cache."""
    root = tmp_path / "acme"
    Project.init(root, probe_mb=8)
    assert (root / ".querysolo" / "catalog.db").exists()  # written, and not committed
    assert not [p for p in tracked(root) if p.startswith((".querysolo/", "warehouse/"))]


def test_an_existing_repository_is_used_as_it_is(tmp_path, gitconfig) -> None:
    root = tmp_path / "theirs"
    root.mkdir()
    Repo.init(str(root), default_branch=b"refs/heads/main").close()
    report = Project.init(root, probe_mb=0)

    assert report.repository == "existing" and report.commit is None
    with Repo.discover(str(root)) as repo:
        assert repo.refs.as_dict() == {}  # init committed nothing; the first save will


def test_a_project_inside_a_monorepo_uses_the_monorepo(tmp_path, gitconfig) -> None:
    Repo.init(str(tmp_path), default_branch=b"refs/heads/main").close()
    report = Project.init(tmp_path / "analytics" / "lakehouse", probe_mb=0)
    assert report.repository == "existing" and report.commit is None
    assert not (tmp_path / "analytics" / "lakehouse" / ".git").exists()


# -- save (G3) ---------------------------------------------------------------------------


def test_a_save_is_a_commit_with_the_title_and_the_author(project) -> None:
    q = project.questions.save("Revenue by customer", SQL)

    assert q.commit and q.git is None
    assert log(project.root)[0] == (
        "save question: Revenue by customer",
        "Ada Lovelace <ada@example.com>",
    )
    assert [p for p in tracked(project.root) if p.startswith(("models/questions", "tests/"))] == [
        "models/questions/revenue_by_customer.sql",
        "models/questions/schema.yml",
        "tests/generic/returns_rows.sql",
    ]


def test_a_second_save_is_a_second_version_and_an_unchanged_save_is_none(project) -> None:
    first = project.questions.save("Revenue by customer", SQL)
    again = project.questions.save("Revenue by customer", SQL + " order by 2 desc")
    unchanged = project.questions.save("Revenue by customer", SQL + " order by 2 desc")

    assert again.commit and again.commit != first.commit
    assert unchanged.commit is None and unchanged.git is None
    messages = [m for m, _ in log(project.root)]
    assert messages[:3] == [
        "update question: Revenue by customer",
        "save question: Revenue by customer",
        "querysolo init",
    ]


def test_a_save_commits_its_own_files_and_leaves_the_users_work_alone(project) -> None:
    """G3's *not chosen*: `git add -A` would sweep a developer's work in progress into
    QuerySolo's commit. Neither their staged change nor their untracked file may appear."""
    from dulwich import porcelain

    (project.root / "models" / "theirs.sql").write_text("select 1\n", encoding="utf-8")
    (project.root / "notes.md").write_text("mine\n", encoding="utf-8")
    with Repo.discover(str(project.root)) as repo:
        repo.get_worktree().stage(["models/theirs.sql"])

    project.questions.save("Revenue by customer", SQL)

    assert "models/theirs.sql" not in tracked(project.root)
    with Repo.discover(str(project.root)) as repo:
        status = porcelain.status(repo)
    assert status.staged["add"] == [b"models/theirs.sql"]  # still staged, still theirs
    assert [bytes(p) for p in status.untracked] == [b"notes.md"]


def test_a_project_made_before_this_version_gets_its_repository_on_its_next_save(
    tmp_path, gitconfig
) -> None:
    """G2: opening a folder never writes to it, so a project from before versions existed
    becomes a repository on the save that needs one."""
    root = tmp_path / "older"
    Project.init(root, probe_mb=8)
    import shutil

    shutil.rmtree(root / ".git")  # as if init had never made one

    with Project.open(root) as p:
        p.engine.execute("CREATE TABLE querysolo.main.orders AS SELECT 1 AS id, 2.0 AS amt")
        q = p.questions.save("All orders", "select * from orders")
    assert q.commit and (root / ".git").is_dir()
    assert [m for m, _ in log(root)] == ["save question: All orders"]


def test_the_author_falls_back_to_the_os_user_when_git_has_no_identity(
    tmp_path, monkeypatch
) -> None:
    """G3: a machine, or a CI runner, with no git identity still commits."""
    import getpass
    import socket

    use_gitconfig(monkeypatch, tmp_path / "no-such-gitconfig")

    root = tmp_path / "proj"
    Project.init(root, probe_mb=0)
    [(_, author)] = log(root)
    assert author == f"{getpass.getuser()} <{getpass.getuser()}@{socket.gethostname()}>"


def test_a_global_commit_gpgsign_does_not_make_a_save_fail(tmp_path, monkeypatch) -> None:
    """The brief's §7 known unknown: a developer's `commit.gpgsign = true` must not fail a
    save. QuerySolo builds the commit object itself and signs nothing, so the commit is made
    and is unsigned."""
    use_gitconfig(
        monkeypatch,
        tmp_path / "gitconfig",
        "[user]\n\tname = Ada Lovelace\n\temail = ada@example.com\n\tsigningkey = ABCD1234\n"
        "[commit]\n\tgpgsign = true\n[tag]\n\tgpgsign = true\n",
    )

    root = tmp_path / "proj"
    report = Project.init(root, probe_mb=8)
    assert report.commit and report.git is None

    with Project.open(root) as p:
        p.engine.execute("CREATE TABLE querysolo.main.orders AS SELECT 1 AS id, 2.0 AS amt")
        q = p.questions.save("All orders", "select * from orders")
    assert q.commit and q.git is None
    with Repo.discover(str(root)) as repo:
        assert repo[repo.refs[b"HEAD"]].gpgsig is None


# -- when git cannot be written (G9) -----------------------------------------------------


def test_a_broken_repository_is_a_reason_and_the_files_are_still_saved(project) -> None:
    """A `.git` that points nowhere: the save writes its files, the response carries
    `git: <reason>`, and nothing raises."""
    import shutil

    shutil.rmtree(project.root / ".git")
    (project.root / ".git").write_text("gitdir: /nowhere/at/all\n", encoding="utf-8")

    q = project.questions.save("Revenue by customer", SQL)
    assert q.commit is None and q.git
    assert q.path.exists() and q.sql == SQL


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0, reason="root writes a read-only folder anyway"
)
def test_a_read_only_repository_is_a_reason(project) -> None:
    git = project.root / ".git"
    before = git.stat().st_mode
    os.chmod(git, stat.S_IRUSR | stat.S_IXUSR)
    try:
        q = project.questions.save("Revenue by customer", SQL)
    finally:
        os.chmod(git, before)
    assert q.commit is None and q.git and q.path.exists()


def test_init_with_a_git_that_is_not_a_repository_still_makes_the_project(
    tmp_path, gitconfig
) -> None:
    """G9: a project without a repository works exactly as before, one sentence poorer."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / ".git").write_text("not a repository\n", encoding="utf-8")
    report = Project.init(root, probe_mb=0)
    assert report.repository is None and report.commit is None and report.git
    assert (root / "querysolo.toml").exists() and (root / ".querysolo" / "catalog.db").exists()


# -- the module's own surface --------------------------------------------------------------


def test_commit_ignores_paths_the_repository_ignores(project) -> None:
    """G9: nothing ignored can be committed, whatever a caller passes."""
    data = project.root / "warehouse" / "rows.parquet"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_bytes(b"not really parquet")
    result = versions.commit(project.root, [data], "should not happen")
    assert result.id is None and result.unchanged and result.reason is None
    assert "warehouse/rows.parquet" not in tracked(project.root)


def test_short_is_seven_characters() -> None:
    assert versions.short("8fa16a2e966b62a736bbadfaec83c3870064cc17") == "8fa16a2"
