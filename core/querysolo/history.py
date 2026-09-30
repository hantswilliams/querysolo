# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""``.querysolo/history.db`` (brief D7, §3.4): every run, with everything the calibration
model will ever need, including the SQL text, which never leaves the machine."""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import event

SCHEMA_VERSION = 3

metadata = sa.MetaData()

runs = sa.Table(
    "runs",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
    sa.Column("querysolo_version", sa.String(32), nullable=False),
    sa.Column("duckdb_version", sa.String(32), nullable=False),
    sa.Column("fingerprint", sa.String(64), nullable=False),
    sa.Column("sql_hash", sa.String(64), nullable=False),
    sa.Column("sql_text", sa.Text, nullable=False),
    sa.Column("tables", sa.Text, nullable=False),  # JSON
    sa.Column("operator_counts", sa.Text, nullable=False),  # JSON
    sa.Column("pruning", sa.String(16)),
    sa.Column("machine_hash", sa.String(64), nullable=False),
    sa.Column("machine", sa.Text, nullable=False),  # JSON
    sa.Column("throughput_local_mbps", sa.Float),
    sa.Column("bandwidth_mbps", sa.Float),
    sa.Column("est_bytes", sa.BigInteger),
    sa.Column("est_peak_mem", sa.BigInteger),
    sa.Column("est_wall_local", sa.Float),
    sa.Column("est_wall_burst", sa.Float),
    sa.Column("est_cost_burst", sa.Float),
    sa.Column("verdict", sa.String(16)),
    sa.Column("reason", sa.Text),
    sa.Column("ran", sa.Boolean, nullable=False),
    sa.Column("ran_where", sa.String(16), nullable=False),
    sa.Column("actual_rows_scanned", sa.BigInteger),
    sa.Column("actual_bytes", sa.BigInteger),
    sa.Column("actual_peak_mem", sa.BigInteger),
    sa.Column("actual_peak_rss", sa.BigInteger),
    sa.Column("actual_spill", sa.BigInteger),
    sa.Column("actual_wall", sa.Float),
    sa.Column("actual_cost", sa.Float),
    sa.Column("retries", sa.Integer, nullable=False, default=0),
    sa.Column("error", sa.Text),
)

# Which question a run answered: one row per run, so every run of a question is kept
# (schema 2, 2026-09-20: the Changes feed lists them all; before it, one row per question,
# the latest). The question's last run is the newest row.
question_runs = sa.Table(
    "question_runs",
    metadata,
    sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), primary_key=True),
    sa.Column("slug", sa.String(255), nullable=False, index=True),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
)

# Which dbt model a `querysolo run` built (real-data brief R5, the app's Models panel): the
# model's unique id per run, kept the way a question's runs are; its last run is the newest.
model_runs = sa.Table(
    "model_runs",
    metadata,
    sa.Column("run_id", sa.Integer, sa.ForeignKey("runs.id"), primary_key=True),
    sa.Column("unique_id", sa.String(255), nullable=False, index=True),
    sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
)

corrections = sa.Table(
    "corrections",
    metadata,
    sa.Column("machine_hash", sa.String(64), primary_key=True),
    sa.Column("operator_class", sa.String(64), primary_key=True),
    sa.Column("factor", sa.Float, nullable=False),
    sa.Column("n", sa.Integer, nullable=False),
    sa.Column("updated", sa.DateTime(timezone=True), nullable=False),
)

meta = sa.Table(
    "meta",
    metadata,
    sa.Column("key", sa.String(64), primary_key=True),
    sa.Column("value", sa.Text, nullable=False),
)

JSON_COLUMNS = ("tables", "operator_counts", "machine")


def _keep_every_run(c: sa.Connection) -> None:
    """Schema 1 → 2: `model_runs` and `question_runs` keyed by the run rather than by the
    model or question, so runs accumulate instead of replacing. The rows a schema-1 file
    holds (one per model and per question, the latest) are carried over."""
    for table, key in ((model_runs, "unique_id"), (question_runs, "slug")):
        name = table.name
        c.execute(sa.text(f"ALTER TABLE {name} RENAME TO {name}_v1"))
        table.create(c)
        c.execute(
            sa.text(
                f"INSERT INTO {name} (run_id, {key}, ts) SELECT run_id, {key}, ts FROM {name}_v1"
            )
        )
        c.execute(sa.text(f"DROP TABLE {name}_v1"))


def _rename_version_column(c: sa.Connection) -> None:
    """Schema 3 (2026-09-30, rename plan R5): the product's version column follows the
    product's name. SQLite renames a column in place, keeping every row. A file created
    after the rename already has the new column and needs nothing."""
    columns = {row[1] for row in c.execute(sa.text("PRAGMA table_info(runs)"))}
    if "lakelet_version" in columns:
        c.execute(sa.text("ALTER TABLE runs RENAME COLUMN lakelet_version TO querysolo_version"))


#: Numbered migrations from an older schema (trust round T4), each run once, in order.
MIGRATIONS: list = [(2, _keep_every_run), (3, _rename_version_column)]


@dataclass
class Run:
    fingerprint: str
    sql_hash: str
    sql_text: str
    querysolo_version: str
    duckdb_version: str
    machine_hash: str
    machine: dict[str, Any]
    tables: list[dict[str, Any]] = field(default_factory=list)
    operator_counts: dict[str, int] = field(default_factory=dict)
    pruning: str | None = None
    throughput_local_mbps: float | None = None
    bandwidth_mbps: float | None = None
    est_bytes: int | None = None
    est_peak_mem: int | None = None
    est_wall_local: float | None = None
    est_wall_burst: float | None = None
    est_cost_burst: float | None = None
    verdict: str | None = None
    reason: str | None = None
    ran: bool = False
    ran_where: str = "local"
    actual_rows_scanned: int | None = None
    actual_bytes: int | None = None
    actual_peak_mem: int | None = None
    actual_peak_rss: int | None = None
    actual_spill: int | None = None
    actual_wall: float | None = None
    actual_cost: float | None = None
    retries: int = 0
    error: str | None = None
    id: int | None = None
    ts: datetime | None = None


def _utc(ts: datetime | None) -> datetime | None:
    """SQLite keeps no offset, so a timestamp read back is naive; it was written as UTC and
    is UTC again here, so ``isoformat()`` carries the offset and a browser in any zone reads
    the instant rather than a local time an hour out."""
    return ts.replace(tzinfo=UTC) if ts is not None and ts.tzinfo is None else ts


def _without(row, key: str) -> dict:
    return {k: v for k, v in dict(row).items() if k != key}


def _run(row) -> Run:
    data = dict(row)
    for column in JSON_COLUMNS:
        data[column] = json.loads(data[column])
    data["ts"] = _utc(data.get("ts"))
    return Run(**data)


class History:
    def __init__(self, path: Path) -> None:
        self.engine = sa.create_engine(
            f"sqlite:///{path}", connect_args={"check_same_thread": False, "timeout": 5}
        )

        @event.listens_for(self.engine, "connect")
        def _pragmas(dbapi_conn, _record) -> None:
            dbapi_conn.execute("PRAGMA journal_mode=WAL")
            dbapi_conn.execute("PRAGMA busy_timeout=5000")

        metadata.create_all(self.engine)
        from querysolo.schema import ensure_schema

        try:
            ensure_schema(self.engine, meta, SCHEMA_VERSION, MIGRATIONS, "history")
        except Exception:
            self.engine.dispose()
            raise

    def close(self) -> None:
        self.engine.dispose()

    def record(self, run: Run) -> int:
        values = {k: v for k, v in asdict(run).items() if k not in ("id", "ts")}
        for column in JSON_COLUMNS:
            values[column] = json.dumps(values[column])
        values["ts"] = datetime.now(UTC)
        with self.engine.begin() as c:
            run_id = c.execute(runs.insert().values(**values)).inserted_primary_key[0]
        run.id, run.ts = run_id, values["ts"]
        return run_id

    def recent(self, n: int = 50) -> list[Run]:
        with self.engine.connect() as c:
            rows = c.execute(runs.select().order_by(runs.c.id.desc()).limit(n)).mappings().all()
        return [_run(row) for row in rows]

    def all_runs(self) -> Iterator[Run]:
        """Every run, oldest first, one at a time (the export, the summary)."""
        with self.engine.connect() as c:
            for row in c.execute(runs.select().order_by(runs.c.id)).mappings():
                yield _run(row)

    def summary(self) -> dict[str, Any]:
        """What the Gauge screen's tiles say (real-data brief R8): runs recorded, the share
        of completed local runs whose actual wall time is within 2x of the estimate either
        way, and Green runs that took over three minutes (the gauge's promise broken)."""
        recorded = compared = within = green_over = 0
        for run in self.all_runs():
            recorded += 1
            if run.ran_where != "local" or not run.ran or run.error:
                continue
            est, actual = run.est_wall_local, run.actual_wall
            if est and actual and est > 0 and actual > 0:
                compared += 1
                if 0.5 <= actual / est <= 2.0:
                    within += 1
            if run.verdict == "green" and actual and actual > 180:
                green_over += 1
        return {
            "runs": recorded,
            "compared": compared,
            "within_2x": within,
            "within_2x_share": (within / compared) if compared else None,
            "green_over_3min": green_over,
        }

    def reset(self) -> int:
        """`querysolo gauge reset`: forget every recorded run, the questions' last runs and
        the correction factors. Returns the runs removed."""
        with self.engine.begin() as c:
            c.execute(question_runs.delete())
            c.execute(model_runs.delete())
            c.execute(corrections.delete())
            removed = c.execute(runs.delete()).rowcount
        return removed

    def record_model_run(self, unique_id: str, run_id: int) -> None:
        with self.engine.begin() as c:
            c.execute(
                model_runs.insert().values(unique_id=unique_id, ts=datetime.now(UTC), run_id=run_id)
            )

    def model_last_run(self, unique_id: str) -> Run | None:
        with self.engine.connect() as c:
            row = (
                c.execute(
                    runs.select()
                    .join(model_runs, model_runs.c.run_id == runs.c.id)
                    .where(model_runs.c.unique_id == unique_id)
                    .order_by(model_runs.c.run_id.desc())
                    .limit(1)
                )
                .mappings()
                .first()
            )
        return None if row is None else _run(row)

    def model_and_question_runs(self) -> list[tuple[str, str, Run]]:
        """Every run a model or a question has (decisions L2, the Changes feed):
        ``("model", unique_id, run)`` and ``("question", slug, run)``, in no order."""
        out: list[tuple[str, str, Run]] = []
        with self.engine.connect() as c:
            for row in (
                c.execute(
                    sa.select(model_runs.c.unique_id, runs).join(
                        runs, model_runs.c.run_id == runs.c.id
                    )
                )
                .mappings()
                .all()
            ):
                out.append(("model", row["unique_id"], _run(_without(row, "unique_id"))))
            for row in (
                c.execute(
                    sa.select(question_runs.c.slug, runs).join(
                        runs, question_runs.c.run_id == runs.c.id
                    )
                )
                .mappings()
                .all()
            ):
                out.append(("question", row["slug"], _run(_without(row, "slug"))))
        return out

    def record_question_run(self, slug: str, run_id: int) -> None:
        with self.engine.begin() as c:
            c.execute(question_runs.insert().values(slug=slug, ts=datetime.now(UTC), run_id=run_id))

    def question_last_run(self, slug: str) -> datetime | None:
        with self.engine.connect() as c:
            ts = c.execute(
                sa.select(sa.func.max(question_runs.c.ts)).where(question_runs.c.slug == slug)
            ).scalar()
        return _utc(ts)
