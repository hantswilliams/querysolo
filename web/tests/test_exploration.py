# Copyright 2026 Lakelet contributors
# SPDX-License-Identifier: Apache-2.0
"""Website exploration gate. Run `npm run build`, then pytest this file.

Exercise built HTML, not source strings: links and assets must exist under the GitHub
Pages base, review pages must stay out of search, and interactive controls need labels.
"""

import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

DIST = Path(__file__).resolve().parents[1] / "dist"
BASE = os.environ.get("SITE_BASE", "/lakelet").rstrip("/")
ROUTES = ["explore", "explore/product", "explore/story", "explore/editorial", "explore/querysolo"]


class Page(HTMLParser):
    def __init__(self, path: Path):
        super().__init__()
        self.tags = []
        self.text = []
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))

    def handle_data(self, text):
        self.text.append(text)

    def elements(self, tag):
        return [attrs for name, attrs in self.tags if name == tag]


def built_file(path: str) -> Path:
    relative = unquote(path.removeprefix(BASE)).strip("/")
    target = DIST / relative
    if target.is_file():
        return target
    if not relative:
        return DIST / "index.html"
    return DIST / f"{relative}.html"


@pytest.mark.parametrize("route", ROUTES)
def test_review_page_is_accessible_and_has_navigation(route):
    path = DIST / f"{route}.html"
    assert path.is_file(), "Run npm run build first"
    page = Page(path)
    assert len(page.elements("h1")) == 1
    assert page.elements("html")[0]["lang"] == "en"
    assert any(m.get("name") == "robots" and "noindex" in m["content"] for m in page.elements("meta"))
    nav = page.elements("a")
    assert len([a for a in nav if a.get("aria-current") == "page"]) == 1
    for destination in ROUTES:
        assert any(a.get("href") == f"{BASE}/{destination}" for a in nav)
    assert any(a.get("href") == "#main" for a in nav)
    assert page.elements("main")[0].get("id") == "main"


@pytest.mark.parametrize("route", ROUTES)
def test_local_links_fragments_and_assets_resolve(route):
    page = Page(DIST / f"{route}.html")
    for tag, attrs in page.tags:
        value = attrs.get("href") if tag in {"a", "link"} else attrs.get("src")
        if not value:
            continue
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc:
            continue
        if parsed.path:
            assert parsed.path.startswith(f"{BASE}/"), value
            target = built_file(parsed.path)
        else:
            target = DIST / f"{route}.html"
        assert target.is_file(), (route, value, target)
        if parsed.fragment:
            ids = [attrs.get("id") for _, attrs in Page(target).tags]
            assert parsed.fragment in ids, (route, value)


@pytest.mark.parametrize("route", ROUTES[1:])
def test_current_capabilities_and_preview_requirements_are_explicit(route):
    text = " ".join(Page(DIST / f"{route}.html").text)
    for phrase in ["Developer preview", "Available today", "Planned", "not available yet", "macOS", "Linux", "source"]:
        assert phrase in text
    assert "Installers and a brew tap" in text
    assert "Burst to a worker" in text


def test_review_pages_are_excluded_from_sitemap():
    sitemap = "".join(p.read_text() for p in DIST.glob("sitemap*.xml"))
    assert "/docs" in sitemap, "Keep normal pages in the sitemap"
    assert "/explore" not in sitemap


def test_product_image_has_real_asset_accessible_text_and_provenance():
    page = Page(DIST / "explore/product.html")
    image = page.elements("img")[0]
    assert len(image["alt"]) > 40
    assert built_file(image["src"]).stat().st_size > 10000
    text = " ".join(page.text)
    assert "Actual application UI" in text
    assert "generated sample data" in text


def test_experiment_explains_limits_and_has_native_labeled_controls():
    page = Page(DIST / "explore/story.html")
    text = " ".join(page.text)
    assert "Illustration of transfer time only" in text
    assert "not a live query" in text
    assert len([i for i in page.elements("input") if i.get("type") == "radio"]) == 2
    slider = next(i for i in page.elements("input") if i.get("type") == "range")
    assert any(label.get("for") == slider["id"] for label in page.elements("label"))
    assert any(attrs.get("aria-live") == "polite" for _, attrs in page.tags)
