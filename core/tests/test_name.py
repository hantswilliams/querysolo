# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The product is QuerySolo (build-sessions/rename-querysolo-plan.md, R8). The old name may
appear only where it is history, a reference to a file that keeps its old name, or the code
that reads what the old release wrote. Anything else is a missed rename."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
OLD = re.compile("lake" + "let", re.IGNORECASE)

#: History: the session logs and plans, the site's running task list, the naming record.
HISTORY = ("build-sessions/", "old/", "web/TASKS.md", "marketing/names.md")
#: Files that keep their old names, referred to by name.
FILE_NAMES = re.compile(
    "lake" + r"let-(build-sessions|session-6|architecture|day0-prd|product-spec|v0-build-spec"
    r"|agent-first-strategy|financial-plan)",
    re.IGNORECASE,
)
#: The code that reads what the old release wrote, and the notes that date the rename.
ALLOWED = {
    "core/querysolo/layout.py": None,  # the whole module is the migration
    "core/tests/test_rename_migration.py": None,  # it builds an old project to migrate
    "core/tests/test_name.py": None,  # this file
    "core/querysolo/register.py": re.compile(r'LEGACY_PREFIX = "lakelet\."'),
    "core/querysolo/remote.py": re.compile(r'LEGACY_PREFIX_FOLDER = "_lakelet"'),
    "core/querysolo/catalog/store.py": re.compile(r'LEGACY_REPLACE_SUFFIX = "__lakelet_replace"'),
    "core/querysolo/history.py": re.compile(r"lakelet_version"),
    "app/src-tauri/src/projects.rs": re.compile(r'LEGACY_IDENTIFIER: &str = "dev\.lakelet\.app"'),
    "core/tests/test_step8_remote.py": re.compile(r"`_lakelet/`"),
}
DATED = re.compile(r"Lakelet until 2026-09-30|old name, Lakelet|called Lakelet until then")


def _tracked() -> list[str]:
    if not shutil.which("git") or not (ROOT / ".git").exists():
        pytest.skip("needs the git checkout")
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return out.stdout.splitlines()


def test_the_old_name_appears_only_where_it_is_allowed() -> None:
    stray = []
    for path in _tracked():
        if path.startswith(HISTORY):
            continue
        if OLD.search(path) and not (path.startswith("docs/") and FILE_NAMES.search(path)):
            stray.append(f"{path}: the file's own name")
        if path in ALLOWED and ALLOWED[path] is None:
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except (UnicodeDecodeError, FileNotFoundError, IsADirectoryError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            rest = DATED.sub("", FILE_NAMES.sub("", line))
            if path in ALLOWED:
                rest = ALLOWED[path].sub("", rest)
            if OLD.search(rest):
                stray.append(f"{path}:{n}: {line.strip()[:120]}")
    assert not stray, "the old name outside the allowlist:\n" + "\n".join(stray)
