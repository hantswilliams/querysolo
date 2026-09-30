# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Prototype gate: honest provenance, accessible controls, and model-backed scenarios."""
import importlib.util
from pathlib import Path

from test_exploration import DIST, Page

WEB = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("lookahead_generator", WEB / "scripts/generate_lookahead.py")
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


def test_published_scenarios_match_the_core_model():
    assert (WEB / "src/data/lookahead-estimates.ts").read_text() == generator.render()


def test_location_changes_read_time_not_query_memory_or_bytes():
    for pair in generator.scenarios().values():
        local, remote = pair["local"], pair["s3"]
        assert local["bytes_scanned"] == remote["bytes_scanned"]
        assert local["peak_memory"] == remote["peak_memory"]
        assert local["spill_bytes"] == remote["spill_bytes"]
        assert remote["wall_local"] > local["wall_local"]


def test_examples_cover_memory_pressure_and_transfer_limits():
    cases = generator.scenarios()
    assert cases["summary"]["local"]["verdict"] == "green"
    assert cases["join"]["local"]["peak_memory"] > cases["summary"]["local"]["peak_memory"]
    assert cases["sort"]["local"]["verdict"] == "yellow"
    assert cases["sort"]["local"]["spill_bytes"] > 0
    assert cases["sort"]["s3"]["verdict"] == "red"
    assert cases["sort"]["s3"]["io_seconds"] > 600


def test_home_demo_labels_controls_assumptions_and_a_live_summary():
    page = Page(DIST / "index.html")
    text = " ".join(page.text)
    questions = [i for i in page.elements("input") if i.get("name") == "lookahead-question"]
    storage = [i for i in page.elements("input") if i.get("name") == "lookahead-storage"]
    assert {i["value"] for i in questions} == {"summary", "join", "sort"}
    assert {i["value"] for i in storage} == {"local", "s3"}
    labels = {l.get("for") for l in page.elements("label")}
    assert all(i["type"] == "radio" and i["id"] in labels for i in questions + storage)
    assert sum("checked" in i for i in questions) == 1
    assert sum("checked" in i for i in storage) == 1
    assert any(a.get("aria-live") == "polite" and a.get("aria-atomic") == "true" for _, a in page.tags)
    for phrase in ["Illustrative scenarios", "not a live query", "Example laptop", "12 GB", "100 Mbps", "Estimated time", "Peak memory"]:
        assert phrase in text
    assert page.elements("noscript")
    assert page.elements("script")
