# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""``querysolo.toml`` (brief §3.3). The core validates the sections it reads and carries every
other section and unknown key through untouched, so a file written by a later version still
opens here."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

READ_SECTIONS = ("project", "catalog", "engine", "gauge", "git")


class _Section(BaseModel):
    model_config = ConfigDict(extra="allow")


class ProjectSection(_Section):
    name: str
    warehouse: str = "./warehouse"


class CatalogSection(_Section):
    mode: Literal["local", "team", "external"] = "local"
    url: str | None = None
    #: `querysolo tables expire` keeps this many days of snapshots (decision 4, September 11).
    keep_snapshots_days: int = 7


class EngineSection(_Section):
    memory_limit: str = "auto"
    threads: int | str = "auto"


class GitSection(_Section):
    #: Versions brief G4: `querysolo run` records a version of the models it builds. True by
    #: default; false stops the run-time commit. A save commits either way, because a save
    #: with no version is the one thing the product promises not to do.
    auto_commit: bool = True


class GaugeSection(_Section):
    green_max_seconds: float = 60
    yellow_max_seconds: float = 600
    green_max_memory_fraction: float = 0.6
    share_calibration: bool = False


#: What `querysolo config set` and the app's settings panel may change: the keys the core
#: reads whose value is the user's to choose. The thresholds stay in the file for a hand.
SETTABLE: dict[str, type] = {
    "engine.memory_limit": str,
    "engine.threads": str,
    "gauge.share_calibration": bool,
    "catalog.keep_snapshots_days": int,
    "git.auto_commit": bool,
}


class NotSettable(ValueError):
    """A key `querysolo config set` does not take."""


def parse_setting(key: str, value: str) -> str | int | bool:
    """A CLI or API value into what the file takes: `auto` or `8GB` for the limit; `auto`
    or an integer for threads; true/false for the toggle."""
    if key not in SETTABLE:
        raise NotSettable(f"{key} is not a setting; one of {', '.join(SETTABLE)}")
    if key in ("gauge.share_calibration", "git.auto_commit"):
        if value.lower() in ("true", "yes", "on", "1"):
            return True
        if value.lower() in ("false", "no", "off", "0"):
            return False
        raise NotSettable(f"{key} takes true or false, not {value!r}")
    if key == "engine.threads":
        if value == "auto":
            return "auto"
        if value.isdigit() and int(value) > 0:
            return int(value)
        raise NotSettable(f"{key} takes auto or a positive integer, not {value!r}")
    if key == "catalog.keep_snapshots_days":
        if value.isdigit():
            return int(value)
        raise NotSettable(f"{key} takes a number of days (0 keeps only the current snapshot)")
    if value == "auto" or _SIZE.fullmatch(value.strip()):
        return value.strip()
    raise NotSettable(f"{key} takes auto or a size such as 8GB or 512MiB, not {value!r}")


_SIZE = re.compile(r"\d+(\.\d+)?\s*(B|KB|MB|GB|TB|KiB|MiB|GiB|TiB)", re.IGNORECASE)


def _toml_literal(value: str | int | bool) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_value(text: str, key: str, value: str | int | bool) -> str:
    """`querysolo.toml` with one key set, everything else (comments, order, other sections)
    left as it was: the line is rewritten in place when it exists, added at the end of its
    section when it does not, and the section is added when it is missing."""
    section, name = key.split(".", 1)
    lines = text.splitlines(keepends=True)
    literal = _toml_literal(value)
    in_section = False
    section_end = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("["):
            if in_section:
                section_end = i
                break
            in_section = stripped.split("#")[0].strip() == f"[{section}]"
            continue
        if in_section and (stripped.startswith(f"{name} =") or stripped.startswith(f"{name}=")):
            comment = ""
            if "#" in line.split("=", 1)[1]:
                after = line.split("=", 1)[1]
                comment = after[after.index("#") :].rstrip("\n")
                pad = " " * max(1, 33 - len(name) - 3 - len(literal))  # the column init uses
                lines[i] = f"{name} = {literal}{pad}{comment}\n"
            else:
                lines[i] = f"{name} = {literal}\n"
            return "".join(lines)
    if in_section:
        end = section_end if section_end is not None else len(lines)
        while end > 0 and lines[end - 1].strip() == "":
            end -= 1
        lines.insert(end, f"{name} = {literal}\n")
        return "".join(lines)
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    lines.append(f"\n[{section}]\n{name} = {literal}\n")
    return "".join(lines)


def current_settings(config: Config) -> dict[str, str | int | bool]:
    """The settable keys and their values, for `config show` and the panel."""
    return {
        "engine.memory_limit": config.engine.memory_limit,
        "engine.threads": config.engine.threads,
        "gauge.share_calibration": config.gauge.share_calibration,
        "catalog.keep_snapshots_days": config.catalog.keep_snapshots_days,
        "git.auto_commit": config.git.auto_commit,
    }


class Config(BaseModel):
    project: ProjectSection
    catalog: CatalogSection = Field(default_factory=CatalogSection)
    engine: EngineSection = Field(default_factory=EngineSection)
    gauge: GaugeSection = Field(default_factory=GaugeSection)
    git: GitSection = Field(default_factory=GitSection)
    extra: dict[str, Any] = Field(default_factory=dict)
    """Sections the core does not read (``burst``, ``agents``, anything newer), verbatim."""

    @classmethod
    def load(cls, path: Path) -> Config:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        known = {section: data.pop(section) for section in READ_SECTIONS if section in data}
        return cls(**known, extra=data)


def render_default(name: str, warehouse: str = "./warehouse") -> str:
    """The file ``init`` writes: the brief's §3.3, with the sections core v0 does not read
    present so the file is already valid for the sessions that will. ``warehouse`` is
    `./warehouse` or an `s3://bucket/prefix` (`init --warehouse`, decisions W1); it is fixed
    at init, because tables carry absolute locations."""
    note = (
        "# ./warehouse, or s3://bucket/prefix: fixed at init"
        if warehouse == "./warehouse"
        else "# fixed at init; a bucket table carries its absolute location"
    )
    return f'''[project]
name = "{name}"
warehouse = "{warehouse}"        {note}

[catalog]
mode = "local"                    # local | team | external
keep_snapshots_days = 7           # querysolo tables expire keeps this many days of snapshots

[engine]
memory_limit = "auto"             # DuckDB default, 80% of RAM
threads = "auto"

[git]
auto_commit = true                # record a version on every save and run; false stops the
                                  # run-time commit, a save is a version either way

[gauge]
green_max_seconds = 60
yellow_max_seconds = 600
green_max_memory_fraction = 0.6
share_calibration = false         # CLI default off; the app asks on first run

[burst]                           # read from session 8 on
default = "prompt"
max_cost_per_run_usd = 5.00

[agents]                          # read from session 5 on
allow = []
'''
