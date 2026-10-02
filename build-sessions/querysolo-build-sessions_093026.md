# QuerySolo build session — 2026-09-30

*The rename, Lakelet → QuerySolo: `rename-querysolo-plan.md`, R1–R10 all agreed by Hants the same day. This is the first log under the new name; earlier logs keep theirs (R8). Worktree `../lakelet-rename`, branch `rename/querysolo`, cut from website v2, which was committed first on its own branch as `ddbb74e` (R1). All changes are staged on the branch, not committed.*

## 0. Baseline

On `rename/querysolo` before any change, every suite was green:

| Suite | Result |
|---|---|
| core pytest | 274 passed, 7 skipped |
| Vitest | 126 |
| `tsc` | clean |
| `cargo test` | 14 |
| Playwright against real sidecars | 31 |
| site pytest | 95 |
| README status check | current |

**One gap that predates the rename:** `cargo test` fails on any clone that has not built the frozen core, because `tauri.conf.json` bundles `core/dist/<name>/` and the build script refuses a missing resource path. For the runs here, an empty placeholder folder (not tracked) stands in.

## 1. Core

- **The mechanical rename:**
  - `git mv core/lakelet core/querysolo` and `freeze/lakelet.spec` → `querysolo.spec`.
  - Every text file in `core/`: `lakelet` → `querysolo`, `Lakelet` → `QuerySolo`, `LAKELET_` → `QUERYSOLO_`.
  - `uv lock`: the package entry only, and no dependency versions changed.
  - The command is `querysolo`, with no alias (R2).
- **`layout.py` (R3)** renames a pre-rename project in place, once, on open:
  - `.lakelet/` → `.querysolo/`
  - the two dbt macro files `init` wrote, with their `lakelet__` macros
  - the `.gitignore` line and `AGENTS.md`
  - `lakelet.toml` last, so an interrupted migration is finished by the next open
  - It is called from `Project.open`, `Project.init` and the three CLI commands that read the settings file without opening the project.
  - A folder with both layouts is refused, and nothing moves.
  - `Project._record_rename` writes `renamed_from = lakelet <date>` into the catalog's `meta` table.
- **Table properties (R4):** `register.table_property` reads `querysolo.*` first, then `lakelet.*`. It is used in all eight places that read one: `register`, `relocate`, `tables` ×2, `lineage`, the manifest cache, the dbt runner. Tables are never rewritten.
- **The replace suffix:** `__querysolo_replace`, with `__lakelet_replace` still recognised by recovery, the catalog server and `register`.
- **History (R5):** schema 3 renames `lakelet_version` → `querysolo_version`, only when the old column is there. The calibration export writes the new name.
- **Three things the plan did not list, found while building:**
  - **The dbt macros.** The runner writes `macros/<name>_views.sql` when absent. After a plain rename an old project would have held both files, with the same macros defined twice, and dbt refuses that. The migration renames them.
  - **`_lakelet/` in buckets.** Table metadata attached with `--metadata-in-bucket` lives under `bucket/_lakelet/`. Existing tables keep working (the catalog holds full paths), but `discover` would have offered the old folder as a dataset. It now skips both folders, with a Moto test.
  - **The DuckDB alias.** The catalog is attached to DuckDB as `querysolo` (was `lakelet`). Nothing the product generates names it: recorded views store `"main"."x"`, and unqualified names resolve through the search path. SQL a person wrote with an explicit `lakelet.main.x` will need editing. This is not migrated, deliberately: it would be a guess at a person's SQL.
- **Tests:**
  - `test_rename_migration.py` (6): migrate and keep everything, run once, refuse both layouts, old properties read (the new name wins), the old suffix recognised, history migration 3.
  - `test_step8_remote.py` gains the `discover` test.
  - Three existing tests changed because of the rename, not the behaviour: history's pinned schema (2 → 3), the `init` commit's file list (`querysolo.toml` now sorts after `macros/`), and the expire hint (82 characters wraps at the runner's 80 columns, so the assertion ignores wrapping).

## 2. Freeze, CI, compose

- The workflows (env vars, the Postgres test user and database, the sidecar path) and the issue template.
- `compose.yaml`, Spark's catalog name, and `compose/trino/lakelet.properties` → `querysolo.properties`. The Trino catalog is named by its file, and the smoke tests expect `querysolo`.

## 3. App (R6)

- Identifier `dev.querysolo.app`, product name QuerySolo.
- The sidecar at `<resources>/querysolo/querysolo`, set by `QUERYSOLO_SIDECAR`.
- The Cargo package `querysolo-app` (library `querysolo_app_lib`) and the npm package `querysolo-app`.
- Every UI string, and the icon source file names (the art is unchanged, R9).
- `projects::adopt_legacy_data` copies `projects.json` and `recent.json` from the sibling `dev.lakelet.app` folder once, only files the new folder lacks, and never moves them. It is called at startup and has one Rust test.

## 4. Site (R7)

- Every page, component, data file and doc. The base is `/querysolo/`.
- `/explore/querysolo` loses its "working name" strip and its note about the old command.
- The CLI reference is regenerated from the renamed help text. It also picked up the `audit` subcommand's page, which the committed copy had been missing.
- `web/TASKS.md` is untouched: it is a record (R8).

## 5. Words (R8, R9)

- **Renamed:** README, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `PRIVACY.md`, `NOTICE`, `docs/` (contents; the spec files keep their names, because the history links to them), `examples/` (`~/querysolo-demo`), `marketing/`, `personas/`, `research/`.
- **The session-log rule** in `CLAUDE.md` and `AGENTS.md` now names both log prefixes.
- **The marketing placeholder:** "Lakelet (working name; TBD\*)" → QuerySolo, with the rule sentences rewritten by hand.
- **`marketing/names.md`** was restored after the sweep changed its history. It gains a "Decided: QuerySolo" section with the OneQuery, 1query, SoloQuery, UnoQuery and QuerySolo findings and the 2026-09-30 checks.
- **Not touched:** the deck generator in `deck/` (gitignored, outside the branch). The 26 Sep deck still says Lakelet.

## 6. What the tests showed

| Suite | Baseline | After |
|---|---|---|
| core pytest | 274 passed, 7 skipped | **282 passed, 7 skipped** (+6 migration, +1 `discover`, +1 name) |
| Vitest | 126 | 126 |
| `tsc` | clean | clean |
| `cargo test` | 14 | **15** (+1 data-folder copy) |
| Playwright | 31 | 31 |
| site pytest | 95 | 95 at `/querysolo/`, 95 at `/` |
| README status check | current | current |

- `test_name.py` (R8) fails on a planted stray `Lakelet` in `NOTICE`, and passes on the branch.
- The frozen build: see §8.

## 7. Open

- **Your projects, on the Mac.** The first open with the new version renames the project folder's contents in place. Make a copy of one real project first, open the copy, and check tables, questions, versions, history and a `querysolo run`. This is the plan's last gate and needs your machine.
- **A DMG** under the new name: `npm run tauri build` on the Mac, now that the frozen core is green (§8).
- **Screenshots.** The app screenshots on the site and in `docs/screenshots/` still show "lakelet" in the app's top bar. They need retaking with `app/scripts/screenshots.mjs`.
- **Yours (R7, R10):** the repository rename to `hantswilliams/querysolo` just before merging, the domains, the GitHub and npm organisations, a PyPI placeholder, and the USPTO clearance search.
- **The icon (R9)** and the deck: a design step and a new deck revision of their own.
- **Commits.** The branch is staged but not committed. Committing, pushing and merging are your calls.

## 8. The frozen build, on the Mac

`uv run --group freeze python freeze/build.py`, then `--check`: `dist/querysolo` is 352 MB before the trim and 292 MB after (the same as under the old name). The check runs from an empty `HOME` with no network: the quickstart, including `querysolo run` (dbt, one model built), with zero Python outbound connection attempts and zero DuckDB requests beyond loopback. "Nothing left the machine."

## 9. The mark (`logo-querysolo-plan.md`, L1–L6 all agreed)

- **L1:** the rename committed on its own first (`7d91343`). This round is the second commit.
- **The mark (L2):** the prompt, `>_`, with a lime cursor.
  - **App icon masters:** off-white chevron and lime cursor on the deep green. The macOS one is on the Big Sur canvas (an 824 tile inset 100); the Linux one fills the canvas.
  - **Favicon:** the Linux master.
  - **Rendering:** the masters go to 1024 px PNGs in Playwright's Chromium, through the new `app/scripts/icon-masters.mjs`. That replaces the `cairosvg` step, which needs a Cairo library this Mac does not have.
  - **Icon set:** `npx tauri icon` for both folders, pruned back to the six files the config names. `icons/README.md` is updated.
  - **Checked** at 256, 128, 64, 32 and 16 px on light and dark: it reads at 16.
- **Headers (L3):** the site header (`Brand.astro`), the design-study header (`exploration/Wordmark.astro`) and the app window (`App.tsx`) draw the chevron and "query" in ink, and the cursor and "solo" in the accent (lime on dark, deep green on light).
  - The site's header CSS had coloured the whole wordmark lime. The first browser review caught that, and it was fixed before this commit.
  - `Logo.astro`, still unused, is redrawn rather than deleted (L6).
- **Art only (L4):** the home page's layout is unchanged.
- **Screenshots (L5):** retaken with `app/scripts/screenshots.mjs` from a throwaway sample project: `make_sample.py`, the three saved questions (revenue by region, top customers, refunds by product) and a `run`, against a real `querysolo serve` and the app's dev server.
  - Ten images on the site, plus `docs/screenshots/query-verdict.png` for the README.
  - The provenance note and the README caption say September 30.
- **Tests:** site 95 at both bases; Vitest 126; `tsc` clean; `cargo test` 15; README check current; `test_name.py` green.
- **Open:** a DMG built on your Mac, to see the new Dock icon.

## 10. CI on `main` was red before the rename; fixed on this branch

After PR #2 merged, GitHub Actions showed two failures that predate the rename:

- **app (Linux and macOS):** `cargo test` failed in the build script, because `tauri.conf.json` bundles `core/dist/<name>/` (ship step 1) and a fresh checkout has no such folder. This is the gap noted in §0. `app-ci.yml` now creates the empty folder before `cargo test`.
- **core (macOS):** `test_changes.py::test_the_cli_and_the_route` failed with "Invalid control character". `changes --json` and `lineage --json` printed through Rich without `soft_wrap`, so a JSON line longer than the terminal (80 columns on CI, with its long temporary paths) was broken inside a string.
  - Both now pass `soft_wrap=True`.
  - `test_json_survives_a_narrow_terminal` runs both at `COLUMNS=40`. It fails without the fix and passes with it.
  - `estimate --json` uses Rich's `print_json`, which does not wrap, and was already safe.

## 11. The pull request's first checks

The pull request ran CI on the renamed code for the first time. Three jobs failed: both `core` jobs and `app` on macOS.

- **core (Linux and macOS): lint, not tests.** The rename made names two characters longer, and 30 lines crossed Ruff's 100-column limit or its formatting. Ruff runs before pytest, so the tests never ran.
  - Fixed with `ruff format` (13 files) and `ruff check --fix` (two import blocks).
  - The eight remaining long lines were wrapped by hand, with no change to the text they produce.
  - `ruff check` and `ruff format --check` are clean.
- **app (macOS): the Moto test bucket did not start within 30 s.**
  - It printed nothing and did not exit. The fixture flushes its ready line, so it was not output buffering. It passes on Ubuntu and on this Mac, which points to a cold start: a fresh virtualenv compiling boto3, botocore and Moto on first import on a slow macOS runner.
  - Three changes:
    - CI's `uv sync` now compiles bytecode.
    - The wait is 120 s.
    - The fixture writes "moto fixture: importing" to stderr before its heavy imports, so a future timeout shows whether the process started.
  - This is a likely cause, not a confirmed one. The next macOS run will tell.
- **Locally:** core 283 passed, 7 skipped (with the narrow-terminal test); Playwright 31.
- **Second run, 2026-10-01.** The Moto fix held: the bucket started, and 31 of 32 tests passed on macOS.
  - **The one failure:** `save-question.spec.ts` pressed `Control+a` to replace the SQL box's text. In CodeMirror on a Mac, select-all is ⌘A and Ctrl+A moves to the line's start, so the new SQL was prepended to the old and the query failed. A failed query never sets `data-done-ms`, which is why the test timed out.
  - **The fix:** `ControlOrMeta+a`, Playwright's portable modifier. The test passes locally. Why it passed on this Mac before is not explained.
- **Third run.** `save-question` now passed, and two `versions.spec` tests failed on macOS. The second failed only because the first stopped before its restore.
  - **What the log shows:** in the first test, the version list showed two rows (the count check passed), then re-rendered and did not show a second row within 5 s.
  - **What was ruled out:** it does not reproduce locally, in parallel or with CI's single worker and file order. And `save-question`, which shares the sidecar and now runs to its end, waits for its last run to report fresh before it finishes.
  - **Best explanation:** timing on the slow macOS runner, not confirmed.
  - **Changes:** the version-list assertions wait 30 s, and `app-ci.yml` now uploads `app/test-results/` (traces, page snapshots) when a job fails. If this was not timing, the next failure can be read rather than guessed at.
- **Fourth run.** The versions tests passed with their 30 s waits. A different spec failed the same way: `bucket.spec.ts` waited 5 s for its first query.
  - The uploaded trace settled it: the page's status line read "estimating…". The first estimate on a bucket table probes bandwidth by reading from Moto, and on the macOS runner that probe alone took more than 5 s. That run was slower than the last (the 20M-row import took 6.3 s against 3.3 s).
  - Three different specs missing 5 s waits on one slow runner is one cause, not three. Fixing them one CI round at a time would keep finding the next.
  - **Changes:** `playwright.config.ts` sets the assertion wait to 15 s when `CI` is set, and keeps 5 s locally, so a slowdown still shows on a laptop. The bucket test's first query gets 30 s, with the reason beside it. No assertion changed what it checks.
