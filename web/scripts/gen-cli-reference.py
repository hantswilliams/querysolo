# Copyright 2026 QuerySolo contributors
# SPDX-License-Identifier: Apache-2.0
"""Write src/content/docs/cli.md from the CLI's own --help text, so the reference cannot
drift from the code. Run from web/:

    uv run --project ../core python scripts/gen-cli-reference.py
"""

from __future__ import annotations

import os
from pathlib import Path

import click
import typer
from querysolo import __version__
from querysolo.cli import app

os.environ["TERM"] = "dumb"
os.environ["NO_COLOR"] = "1"
WIDTH = 88

OUT = Path(__file__).resolve().parent.parent / "src" / "content" / "docs" / "cli.md"

HEADER = f"""---
title: CLI reference
description: Every querysolo verb with its arguments and options, generated from the CLI's own help text.
section: Reference
order: 1
---

Generated from `querysolo --help` and every subcommand's help at version `{__version__}`
by `web/scripts/gen-cli-reference.py`. Do not edit by hand; re-run the script after a
CLI change.

Every verb runs against the project in the current folder; `-C <path>` points at another
one, and `--profile <name>` names the AWS profile for a private bucket, as `AWS_PROFILE`
would ([credentials](/docs/remote#credentials)). The gauge line goes to stderr and rows to stdout, so `querysolo sql … > out.csv` keeps
the two apart. Exit codes: `0` ran; `1` an error, named on stderr; `2` a Red verdict that
was refused (add `--run-anyway`); `4` a catalog conflict after retries.

"""


def help_text(cmd: click.Command, name: str, parent: click.Context | None) -> str:
    ctx = click.Context(
        cmd,
        info_name=name,
        parent=parent,
        terminal_width=WIDTH,
        max_content_width=WIDTH,
    )
    return cmd.get_help(ctx).rstrip() + "\n", ctx


def walk(
    cmd: click.Command,
    name: str,
    parent: click.Context | None,
    out: list[str],
    depth: int,
) -> None:
    text, ctx = help_text(cmd, name, parent)
    heading = "#" * min(depth + 1, 4)
    out.append(f"{heading} `{ctx.command_path}`\n\n```text\n{text}```\n\n")
    if hasattr(cmd, "list_commands"):  # a group; typer's click fork is not click.Group
        for sub in cmd.list_commands(ctx):
            walk(cmd.get_command(ctx, sub), sub, ctx, out, depth + 1)


def main() -> None:
    root = typer.main.get_command(app)
    parts: list[str] = [HEADER]
    walk(root, "querysolo", None, parts, 1)
    OUT.write_text("".join(parts), encoding="utf-8")
    print(f"wrote {OUT.relative_to(Path.cwd())}")


if __name__ == "__main__":
    main()
