# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Versions brief G8, step 4: table-level lineage for a table, a view and a model, with
how every edge is known (`ref`, `source`, a table named in the SQL, a catalog view's SQL),
in both directions, to a depth; built by whom and when; the CLI and the route. Against a
real dbt project: the manifest is compiled when it is missing or older than the models."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import httpx
import pytest
from typer.testing import CliRunner

from querysolo import Project
from querysolo.cli import app
from querysolo.dbt import runner
from querysolo.lineage import VIAS, NoSuchNode, lineage, whole

pytest.importorskip("dbt.cli.main")


def _models(root: Path) -> None:
    (root / "models" / "stg_orders.sql").write_text("select id, c, amt from src where amt > 0\n")
    (root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select c, sum(amt) as total from {{ ref('stg_orders') }} group by 1\n"
    )
    (root / "models" / "top.sql").write_text(
        "select c from {{ ref('by_c') }} order by total desc limit 1\n"
    )
    (root / "models" / "sources.yml").write_text(
        "version: 2\nsources:\n  - name: raw\n    database: querysolo\n    schema: main\n"
        "    tables:\n      - name: src\n"
    )
    (root / "models" / "from_source.sql").write_text(
        "select count(*) as n from {{ source('raw', 'src') }}\n"
    )


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "proj"
    Project.init(root, probe_mb=0)
    _models(root)
    p = Project.open(root, serve=True)
    p.engine.execute(
        "create table querysolo.main.src as "
        "select range as id, 'c' || (range % 3) as c, range * 1.5 as amt from range(300)"
    )
    p.questions.save("Total", "select sum(amt) as total from src")
    p.views.put("src_v", "select id from src where id > 200")
    yield p
    p.close()


def _edges(edges) -> dict[str, tuple[str, str, int]]:
    return {e.name: (e.kind, e.via, e.depth) for e in edges}


def test_a_table_a_view_and_a_model_after_a_run_with_via_on_every_edge(project) -> None:
    p = project
    report = runner.run(p)
    assert report.ok

    src = lineage(p, "src")
    assert src.kind == "table" and src.built_by == "imported" and src.last_built
    assert src.upstream == []
    assert _edges(src.downstream) == {
        "stg_orders": ("view", "sql", 1),
        "from_source": ("view", "source", 1),
        "total": ("table", "sql", 1),
        "src_v": ("view", "view", 1),
    }

    by_c = lineage(p, "by_c")
    assert by_c.kind == "table" and by_c.built_by == "by_c"
    [uid] = [m.unique_id for m in report.models if m.name == "by_c"]
    run = p.history.model_last_run(uid)
    assert by_c.last_built == run.ts.isoformat()
    assert _edges(by_c.upstream) == {"stg_orders": ("view", "ref", 1)}
    assert _edges(by_c.downstream) == {"top": ("view", "ref", 1)}

    stg = lineage(p, "stg_orders")
    assert stg.kind == "view" and stg.built_by == "stg_orders" and stg.last_built
    assert _edges(stg.upstream) == {"src": ("table", "sql", 1)}

    src_v = lineage(p, "src_v")
    assert src_v.kind == "view" and src_v.built_by is None and src_v.last_built
    assert _edges(src_v.upstream) == {"src": ("table", "view", 1)}
    assert src_v.downstream == []

    total = lineage(p, "total")  # the saved question: a table model with bare SQL, no ref()
    assert total.kind == "table" and total.built_by == "total"
    assert _edges(total.upstream) == {"src": ("table", "sql", 1)}

    for node in (src, by_c, stg, src_v, total):
        for e in node.upstream + node.downstream:
            assert e.via in VIAS, (node.name, e)


def test_a_model_never_built_depth_and_the_compile_when_the_models_are_newer(project) -> None:
    p = project
    top = lineage(p, "top")
    assert top.compiled, "no manifest yet: the models are compiled first"
    assert top.kind == "model" and top.built_by is None and top.last_built is None
    assert _edges(top.upstream) == {"by_c": ("model", "ref", 1)}
    assert top.downstream == []

    deep = lineage(p, "top", depth=3)
    assert not deep.compiled, "the manifest is current: nothing compiled"
    assert _edges(deep.upstream) == {
        "by_c": ("model", "ref", 1),
        "stg_orders": ("model", "ref", 2),
        "src": ("table", "sql", 3),
    }
    down = lineage(p, "src", depth=2)
    assert _edges(down.downstream) == {
        "stg_orders": ("model", "sql", 1),
        "from_source": ("model", "source", 1),
        "total": ("model", "sql", 1),
        "src_v": ("view", "view", 1),
        "by_c": ("model", "ref", 2),
    }  # top is three away

    # an edited model is newer than the manifest: the next call compiles again
    time.sleep(0.05)
    (p.root / "models" / "top.sql").write_text(
        "select c from {{ ref('stg_orders') }} order by amt desc limit 1\n"
    )
    manifest = runner.manifest_path(p)
    os.utime(manifest, (manifest.stat().st_mtime - 5, manifest.stat().st_mtime - 5))
    edited = lineage(p, "top")
    assert edited.compiled and _edges(edited.upstream) == {"stg_orders": ("model", "ref", 1)}

    with pytest.raises(NoSuchNode):
        lineage(p, "nowhere")


def test_the_cli_and_the_route(project) -> None:
    p = project
    runner.run(p, select=["stg_orders", "by_c"])
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage", "by_c"])
    assert r.exit_code == 0, r.output
    text = "".join(r.output.split())
    assert text.startswith("by_ctable,builtbyby_c,")
    assert "readsfromstg_ordersviewref" in text
    assert "feedstopmodelref" in text
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage", "top", "--depth", "2", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["kind"] == "model" and [e["depth"] for e in data["upstream"]] == [1, 2]
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage", "nowhere"])
    assert r.exit_code == 1 and "no table, view or model named nowhere" in r.output

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    body = client.get("/api/lineage/src_v").json()
    assert body == {
        "name": "src_v",
        "kind": "view",
        "upstream": [{"name": "src", "kind": "table", "via": "view", "depth": 1}],
        "downstream": [],
        "built_by": None,
        "last_built": body["last_built"],
        "compiled": False,
    }
    assert body["last_built"].endswith("+00:00")
    deep = client.get("/api/lineage/src", params={"depth": 3}).json()
    assert {e["name"]: e["depth"] for e in deep["downstream"]}["top"] == 3
    assert client.get("/api/lineage/nowhere").status_code == 404
    client.close()


def test_the_whole_graph_with_states_the_route_and_the_cli(project) -> None:
    """Decisions L1: the Lineage screen's graph — every node once with its kind and, for a
    model, its state; every edge with how it is known; and the route and `--all`."""
    p = project
    graph = whole(p)
    names = {n["name"]: n for n in graph["nodes"]}
    assert set(names) == {"src", "src_v", "stg_orders", "by_c", "top", "from_source", "total"}
    assert names["src"] == {
        "name": "src",
        "kind": "table",
        "model": False,
        "state": None,
        "state_reason": None,
        "source": None,
        "freshness": names["src"]["freshness"],
    }
    assert names["src_v"]["kind"] == "view" and names["src_v"]["state"] is None
    assert all(names[m]["state"] == "never" for m in ("stg_orders", "by_c", "top", "total"))
    edges = {(e["from"], e["to"]): e["via"] for e in graph["edges"]}
    assert edges == {
        ("src", "stg_orders"): "sql",
        ("stg_orders", "by_c"): "ref",
        ("by_c", "top"): "ref",
        ("src", "from_source"): "source",
        ("src", "total"): "sql",
        ("src", "src_v"): "view",
    }
    assert graph["compiled"] is True

    # after a run every model is fresh; after an edit the states follow the chain
    runner.run(p)
    (p.root / "models" / "by_c.sql").write_text(
        "{{ config(materialized='table') }}\n"
        "select c, count(*) as n from {{ ref('stg_orders') }} group by 1\n"
    )
    names = {n["name"]: n for n in whole(p)["nodes"]}
    assert names["by_c"]["state"] == "edited" and names["top"]["state"] == "upstream"
    assert names["top"]["state_reason"] == "by_c is out of date"
    assert names["stg_orders"]["state"] == "fresh" and names["by_c"]["kind"] == "table"

    import httpx

    client = httpx.Client(
        base_url=p.catalog_url, headers={"Authorization": f"Bearer {p.token}"}, timeout=60
    )
    body = client.get("/api/lineage").json()
    assert {n["name"] for n in body["nodes"]} == set(names) and len(body["edges"]) == 6
    client.close()
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage", "--all", "--json"])
    assert r.exit_code == 0, r.output
    assert json.loads(r.output)["edges"] == body["edges"]
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage", "--all"])
    assert r.exit_code == 0, r.output
    text = "".join(r.output.split())
    assert text.startswith("7node(s),6edge(s)") and "by_ctableedited" in text
    assert "src->stg_orders(sql)" in text
    r = CliRunner().invoke(app, ["-C", str(p.root), "lineage"])
    assert r.exit_code == 1 and "give a name, or --all" in r.output
