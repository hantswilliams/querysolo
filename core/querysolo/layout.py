# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Projects made before the rename (build-sessions/rename-querysolo-plan.md, R3). The product
was called Lakelet until 2026-09-30, and a project it made keeps its state in `.lakelet/` and
its settings in `lakelet.toml`. The first time QuerySolo opens such a folder it renames them in
place, with the two dbt macro files `init` wrote (the runner would otherwise add a second
copy of the same macros), the `.gitignore` line and `AGENTS.md`. The settings file moves
last, so an interrupted migration is finished by the next open. A folder holding both
layouts is refused and nothing is touched."""

from __future__ import annotations

from pathlib import Path

OLD = "lakelet"
OLD_DIR, NEW_DIR = f".{OLD}", ".querysolo"
OLD_TOML, NEW_TOML = f"{OLD}.toml", "querysolo.toml"
MACROS = ((f"macros/{OLD}.sql", "macros/querysolo.sql"), (f"macros/{OLD}_views.sql", "macros/querysolo_views.sql"))


class LayoutConflict(Exception):
    """The folder holds both the old and the new layout; nothing was moved."""


def _renamed(text: str) -> str:
    return text.replace(OLD, "querysolo").replace("Lakelet", "QuerySolo")


def migrate(root: str | Path) -> bool:
    """Rename a pre-rename project in place. Returns True when it did, False for a project
    already in the current layout or a folder that is not a project."""
    root = Path(root)
    old_toml, new_toml = root / OLD_TOML, root / NEW_TOML
    if not old_toml.exists():
        return False
    if new_toml.exists():
        raise LayoutConflict(
            f"{root} has both {OLD_TOML} and {NEW_TOML}; keep the one that is current and "
            "remove the other, then open it again"
        )
    if (root / OLD_DIR).exists() and (root / NEW_DIR).exists():
        raise LayoutConflict(f"{root} has both {OLD_DIR}/ and {NEW_DIR}/; keep one and open it again")
    for old, new in MACROS:
        if (root / old).exists() and (root / new).exists():
            raise LayoutConflict(f"{root} has both {old} and {new}; keep one and open it again")

    if (root / OLD_DIR).exists():
        (root / OLD_DIR).rename(root / NEW_DIR)
    for old, new in MACROS:
        if (root / old).exists():
            (root / new).write_text(_renamed((root / old).read_text()))
            (root / old).unlink()
    gitignore = root / ".gitignore"
    if gitignore.exists():
        lines = gitignore.read_text().splitlines()
        gitignore.write_text("\n".join(f"{NEW_DIR}/" if line.strip() == f"{OLD_DIR}/" else line for line in lines) + "\n")
    agents = root / "AGENTS.md"
    if agents.exists():
        agents.write_text(_renamed(agents.read_text()))
    old_toml.rename(new_toml)
    return True
