#!/usr/bin/env python3
# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""The README's "What is built, what is planned" block, generated from
``web/src/data/status.ts`` — the one place on the site that knows — so the README and the
site cannot disagree (trust round T7). Run from the repository root:

    python3 web/scripts/gen-readme-status.py            # rewrite the block in README.md
    python3 web/scripts/gen-readme-status.py --check    # exit 1 if README.md is stale (CI)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STATUS = ROOT / "web" / "src" / "data" / "status.ts"
README = ROOT / "README.md"
START, END = "<!-- status:start -->", "<!-- status:end -->"

ENTRY = re.compile(
    r"\{\s*id:\s*'(?P<id>[^']*)',\s*label:\s*'(?P<label>[^']*)',\s*state:\s*'(?P<state>built|planned)',"
    r"\s*detail:\s*(?P<q>[\"'])(?P<detail>[^}]*?)(?P=q),?"
    r"(?:\s*session:\s*'(?P<session>[^']*)',?)?(?:\s*href:\s*'(?P<href>[^']*)',?)?\s*\}",
    re.DOTALL,
)


def render(source: str) -> str:
    as_of = re.search(r"export const asOf = '([^']+)'", source).group(1)
    entries = [m.groupdict() for m in ENTRY.finditer(source)]
    if not entries:
        raise SystemExit("gen-readme-status: no surfaces parsed from status.ts")
    built = [e for e in entries if e["state"] == "built"]
    planned = [e for e in entries if e["state"] == "planned"]
    site = "https://hantswilliams.github.io/querysolo"
    lines = [
        START,
        f"*Generated from `web/src/data/status.ts` (as of {as_of}); `python3 web/scripts/gen-readme-status.py` rewrites it, CI checks it.*",
        "",
        "**Built, from source, today**",
        "",
    ]
    for e in built:
        link = f" — [docs]({site}{e['href']})" if e.get("href") else ""
        lines.append(f"- **{e['label']}**: {e['detail']}{link}")
    lines += ["", "**Planned, not built** (the site marks these the same way)", ""]
    for e in planned:
        when = f" *({e['session']})*" if e.get("session") else ""
        lines.append(f"- **{e['label']}**: {e['detail']}{when}")
    lines.append(END)
    return "\n".join(lines)


def main() -> int:
    check = "--check" in sys.argv[1:]
    block = render(STATUS.read_text(encoding="utf-8"))
    readme = README.read_text(encoding="utf-8")
    if START not in readme or END not in readme:
        raise SystemExit(f"gen-readme-status: README.md has no {START} … {END} block")
    head, rest = readme.split(START, 1)
    _, tail = rest.split(END, 1)
    updated = head + block + tail
    if check:
        if updated != readme:
            print("README.md's status block is stale: run python3 web/scripts/gen-readme-status.py")
            return 1
        print("README.md's status block is current")
        return 0
    README.write_text(updated, encoding="utf-8")
    print(f"README.md: status block rewritten ({len(block.splitlines())} lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
