# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Saved questions (brief D30, D16, §3.6): a question is a dbt model from the first save,
``models/questions/<slug>.sql`` plus an entry in ``models/questions/schema.yml`` with the
title as its description and two default checks. ``run`` executes the SQL through the gauge
without invoking dbt; ``last_run`` lives in history, so a run touches no file."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from querysolo import versions
from querysolo.project import identifier

if TYPE_CHECKING:
    from querysolo.project import Project
    from querysolo.query import Result

RETURNS_ROWS_TEST = """{% test returns_rows(model) %}
-- QuerySolo's first default check: the question still returns rows.
select 1 as missing where not exists (select 1 from {{ model }})
{% endtest %}
"""


class NoSuchQuestion(Exception):
    pass


@dataclass
class Question:
    slug: str
    title: str
    sql: str
    path: Path
    created: datetime | None
    last_run: datetime | None
    #: The version this save recorded (versions brief G3): the commit's id, or None when the
    #: save changed nothing. ``git`` says why there is no commit when the repository could not
    #: be written (G9); the save itself still wrote the files. A question read back off disk
    #: carries neither: they belong to the save that made it.
    commit: str | None = None
    git: str | None = None


class Questions:
    def __init__(self, project: Project) -> None:
        self.project = project
        self.dir = project.root / "models" / "questions"
        self.schema_path = self.dir / "schema.yml"

    # -- files ---------------------------------------------------------------------

    def _schema(self) -> dict[str, Any]:
        if self.schema_path.exists():
            data = yaml.safe_load(self.schema_path.read_text(encoding="utf-8")) or {}
        else:
            data = {}
        data.setdefault("version", 2)
        data.setdefault("models", [])
        return data

    def _write_schema(self, data: dict[str, Any]) -> None:
        self.schema_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    def _ensure_generic_test(self) -> Path | None:
        """Written once per project; the path when this call wrote it, so the save that did
        commits it too."""
        path = self.project.root / "tests" / "generic" / "returns_rows.sql"
        if path.exists():
            return None
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(RETURNS_ROWS_TEST, encoding="utf-8")
        return path

    def _sql_path(self, slug: str) -> Path:
        return self.dir / f"{slug}.sql"

    @staticmethod
    def strip_header(text: str) -> str:
        lines = text.splitlines()
        while lines and lines[0].startswith("-- "):
            lines.pop(0)
        return "\n".join(lines).strip()

    def write_entry(self, slug: str, title: str, sql: str) -> None:
        """The question's ``schema.yml`` entry: the title as the description, the two default
        checks, and the ``created`` date kept when there was one. Written by ``save`` and
        again by a restore, so the checks always match the file beside them (G5)."""
        first_column = self.project.engine.execute(f"DESCRIBE {sql}").fetchone()[0]
        data = self._schema()
        entry = next((m for m in data["models"] if m.get("name") == slug), None)
        created = (entry or {}).get("meta", {}).get("querysolo", {}).get("created") or datetime.now(
            UTC
        ).isoformat()
        new_entry = {
            "name": slug,
            "description": title,
            "config": {"materialized": "table"},
            "meta": {"querysolo": {"title": title, "created": created}},
            "data_tests": ["returns_rows"],
            "columns": [{"name": first_column, "data_tests": ["not_null"]}],
        }
        if entry is None:
            data["models"].append(new_entry)
        else:
            entry.clear()
            entry.update(new_entry)
        self._write_schema(data)

    # -- operations ----------------------------------------------------------------

    def save(self, title: str, sql: str) -> Question:
        slug = identifier(title)
        # Before anything is written: a question that does not bind is refused.
        self.project.engine.execute(f"DESCRIBE {sql}")
        self.dir.mkdir(parents=True, exist_ok=True)
        is_new = not self._sql_path(slug).exists()
        written_test = self._ensure_generic_test()
        now = datetime.now(UTC)

        self.write_entry(slug, title, sql)
        self._sql_path(slug).write_text(
            f"-- {title}\n-- saved by querysolo on {now:%Y-%m-%d}\n{sql.strip()}\n",
            encoding="utf-8",
        )
        question = self.get(slug)
        # The save is a version: the model, its checks, and the generic test the first save
        # of a project writes. Nothing else of the user's is staged (versions brief G3).
        written = [self._sql_path(slug), self.schema_path]
        if written_test is not None:
            written.append(written_test)
        result = versions.commit(
            self.project.root, written, f"{'save' if is_new else 'update'} question: {title}"
        )
        question.commit, question.git = result.id, result.reason
        return question

    def get(self, slug: str) -> Question:
        path = self._sql_path(slug)
        entry = next((m for m in self._schema()["models"] if m.get("name") == slug), None)
        if entry is None or not path.exists():
            raise NoSuchQuestion(slug)
        created = entry.get("meta", {}).get("querysolo", {}).get("created")
        return Question(
            slug=slug,
            title=entry.get("description", slug),
            sql=self.strip_header(path.read_text(encoding="utf-8")),
            path=path,
            created=datetime.fromisoformat(created) if created else None,
            last_run=self.project.history.question_last_run(slug),
        )

    def list(self) -> list[Question]:
        return [
            self.get(m["name"])
            for m in self._schema()["models"]
            if m.get("name") and self._sql_path(m["name"]).exists()
        ]

    def run(self, slug: str, allow_red: bool = False) -> Result:
        """The gauge first, then the SQL, never dbt; ``last_run`` is recorded in history
        when the result completes."""
        question = self.get(slug)
        result = self.project.query(question.sql, allow_red=allow_red)
        result.question_slug = slug
        return result
