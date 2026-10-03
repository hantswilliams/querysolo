# querysolo-app

The desktop shell: a Tauri 2 window over the `querysolo` sidecar. The brief is
`../build-sessions/app-v0-plan.md`; start from the repo's `CLAUDE.md`.

```bash
# once: Rust stable, Node 22, the core's venv (cd ../core && uv sync), and on Ubuntu
#   sudo apt-get install libwebkit2gtk-4.1-dev librsvg2-dev libayatana-appindicator3-dev
npm install
export QUERYSOLO_SIDECAR=$PWD/../core/.venv/bin/querysolo   # the sidecar in development (A6)
npm run tauri dev                                        # the last project, or the welcome screen
QUERYSOLO_PROJECT=~/acme npm run tauri dev                 # a window on that folder (init runs if needed)
```

Each window is one project with its own `querysolo serve`, given 60% of RAM for the first
window and half that for each further one (A8). "Open…" in the bar opens another folder in a
new window; the recent ten are in `recent.json` under the app's data directory (A10).

The sidebar (decisions U2) has the five screens (⌘/Ctrl+1…5) and, under Tables, the
explorer: the drop zone with "Import…" and every table with its rows, where its data is and
a freshness dot. The Tables screen is the workspace (U1): the SQL box above the results on
a draggable split; drop a file or a folder on the window (or "Import…", or type a path), see
the columns and the first rows in the results pane, import on a click; click a table in the
explorer and its detail opens there. SQL: ⌘/Ctrl+Enter, the verdict before any row, rows
streaming into the grid, Esc to stop, Red as a refusal until "Run anyway"; a result of one
categorical and one numeric column draws a bar chart, a date and a numeric a line. The
status strip along the bottom is what `/api/health` says. Settings (⌘/Ctrl+,) are
`querysolo config set` on `querysolo.toml`.
If the core stops, the shell restarts it once; twice in a minute shows its last lines and a
button. Every action shows the `querysolo` line it is, with a copy button
(`src/lib/command.ts`).

Tests: `cargo test` in `src-tauri/` (the supervisor, projects and windows against a fake
sidecar), `npm test` (Vitest, the screens and the command lines), `npm run e2e` (Playwright
against real `querysolo serve`s; needs `QUERYSOLO_SIDECAR` or `../core/.venv`).

Screenshots for the README, the site and `/docs/app` come from `scripts/screenshots.mjs`:
the real app in the browser harness against a real core on the generated sample data, at
2x; the recipe is at the top of the file and `web/public/screenshots/README.md` says what
each image shows.
