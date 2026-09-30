# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The verdict's words and its one sentence (brief D28, PRD F0.3.5): the site's words after
the coloured dot, the dominant factor, and the burst half for Yellow and Red."""

from __future__ import annotations

from typing import Any

WORDS = {
    "green": "Runs here",
    "yellow": "Runs here, slowly",
    "red": "Needs more machine",
    # A scan the gauge could not attribute to a catalog table (trust round T3): no figures,
    # no colour, and never Green. The statement still runs.
    "none": "Not estimated",
}
DOTS = {"green": "●", "yellow": "●", "red": "●", "none": "○"}


def human_bytes(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1000 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1000
    return f"{n:.1f} TB"


def human_seconds(s: float) -> str:
    if s < 1:
        return f"~{s:.1f} s"
    if s < 60:
        return f"~{s:.0f} s"
    if s < 3600:
        return f"~{s / 60:.0f} min"
    return f"~{s / 3600:.1f} h"


def human_cost(usd: float) -> str:
    return f"${usd:.2f}"


def reason(numbers: dict[str, Any], remote_source: str | None, bandwidth_mbps: float | None) -> str:
    """Everything after the verdict words."""
    if numbers["verdict"] == "none":
        outside = numbers.get("unattributed") or []
        n = len(outside)
        return f"{n} scan{'s' if n != 1 else ''} outside the catalog: {', '.join(outside)}"
    parts = [f"scans {human_bytes(numbers['bytes_scanned'])}"]
    if remote_source:
        parts[0] += f" from {remote_source}"
    if numbers["spill_bytes"]:
        parts.append(
            f"peak {human_bytes(numbers['peak_memory'])} of "
            f"{human_bytes(numbers['memory_limit'])} limit · spills"
        )
    elif numbers["verdict"] == "green":
        parts.append("fits in memory")
    wall = human_seconds(numbers["wall_local"])
    if remote_source and bandwidth_mbps:
        shown = f"{bandwidth_mbps:.1f}" if bandwidth_mbps < 10 else f"{bandwidth_mbps:.0f}"
        wall += f" at your {shown} Mbps"
    parts.append(wall)
    if numbers["verdict"] != "green":
        parts.append(
            f"burst {human_seconds(numbers['wall_burst'])} · cap {human_cost(numbers['cap'])}"
        )
    return " · ".join(parts)


def line(verdict: str, reason_text: str) -> str:
    return f"{DOTS[verdict]} {WORDS[verdict]} · {reason_text}"
