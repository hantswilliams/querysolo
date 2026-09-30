# querysolo

The Python core of QuerySolo: the Iceberg REST catalog, the DuckDB engine, the gauge, history, the CLI and the local API. The build brief is `../build-sessions/core-v0.N-plan.md` (highest N); start from the repo's `CLAUDE.md`.

```
uv sync          # once
uv run pytest    # the suite; every step's gate lives here
uv run querysolo --version
```
