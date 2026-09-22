# Lakelet — running task list

*The one file to open to know where the build is. Updated every session; dates are when a status changed. "Now" names the brief the build is on. The briefs say what each step is and what its gate is (`ship-v0-plan.md` next, the versions round having closed 2026-09-17; `core-v0.5-plan.md` for the core, `app-v0-plan.md` for the desktop shell, both still authoritative for what they cover; a decision belonging to no brief is a dated `decisions-for-review_<MMDDYY>.md`); `lakelet-build-sessions.md` is the map of the sessions; the dated logs (`lakelet-build-sessions_<MMDDYY>.md`) say what happened. This file only says where we are and what comes next.*

## Complete data-story website — 2026-09-16, this branch only

Scope: `build-sessions/website-story-v1-plan.md` (repository root).

- [x] Apply the selected dark/lime direction to all marketing and documentation routes.
- [x] Move the diagram before Lookahead and introduce provider-neutral “Open storage & compute” wording (2026-09-17). Build and 65 checks pass; desktop/mobile reviewed.
- [x] Prototype the question/local-or-S3 Lookahead flow on the homepage: six model-backed illustrative scenarios, responsive diagram and gauge, keyboard controls, assumptions. Build and 65 checks pass.
- [x] Apply the approved local/S3 headline and Lakelet Lookahead name. Production build and 61 checks pass; desktop/mobile copy and demo reviewed.
- [x] Restore the homepage laptop / S3 / worker / catalog diagram in dark/lime, with responsive labels and explicit planned publishing/worker paths. Build and 61 checks pass.
- [x] Responsive site navigation, native mobile menu, documentation navigation, footer, and source-installation calls to action.
- [x] Reuse the interactive scan visualization on the homepage and how-it-runs page.
- [x] Actual app image, current feature status, fourth verdict, and recovery documentation.
- [x] Import committed website documentation/status from trust round `3c60296`.
- [x] Clearly label proposed Team/Burst pricing and other unavailable features.
- [x] Show a usable GitHub fallback when no signup endpoint is configured.
- [x] Production build: 25 pages; 60 pytest checks pass at `/lakelet/` and `/`, including configured signup markup. All 25 preview routes return HTTP 200.
- [x] Browser review: desktop, 390px and 360px phones; menus, docs navigation, experiment, and disclosures verified.
- [x] User authorized committing and publishing this separate website branch to GitHub (2026-09-17).
- [x] User approved merging committed remote main into this website branch (2026-09-18); resolve design/docs/log conflicts and reconcile newly shipped features.
- [x] Combined website verified: 25-page build, 66 website checks, README status check, desktop/mobile review; core/app exactly match remote main `d0f1324`. Merge ready for the existing website branch; publication remains authorized.
- [x] Opened [PR #1: Redesign the website around Lakelet Lookahead](https://github.com/hantswilliams/lakelet/pull/1) from this branch to main (2026-09-18).
- [ ] User review before merging this website into main or deploying it.


## Website exploration — parallel branch, 2026-09-16

Scope: `website-exploration-plan.md` in `build-sessions/`; isolated branch
`codex/website-exploration` at base `97ee6aa`. This is independent of the core steps.

- [x] Separate worktree and dedicated local preview.
- [x] Comparison page plus product, interactive data story, and editorial concepts.
- [x] Actual app screenshot using generated data, with provenance.
- [x] Production build and 14 persistent pytest checks pass.
- [x] Desktop/mobile browser checks; radio, keyboard slider and details controls work.
- [x] Exploration routes carry noindex and are excluded from the sitemap.
- [x] User selected 02 / Data story; complete-site implementation stays in this worktree.

Results: `build-sessions/lakelet-build-sessions_091626.md` (from repository root).

## Now

**The lineage screens and S3 writes** (`decisions-for-review_091726.md`, W1, W2, L1, L2, L3 all agreed by Hants 2026-09-18), built in the order L3, L1, W1, W2, L2 — **all five built 2026-09-18**, awaiting Hants' Mac run and commit; the log is `lakelet-build-sessions_091826.md`. **Ship** (`ship-v0-plan.md`) is next and stays **held** (Hants, 2026-09-17). The versions round closed 2026-09-17 and is on `main` (`984d834`).

| Item | What | Status |
|---|---|---|
| L3 | `affects` on every snapshot in `describe` (the models whose last run predates it, in dependency order); the table detail's rows with the names as links, the line under the list and **Run what changed** | **built** 2026-09-18; 1 pytest, 1 Vitest, `models.spec` |
| L1 | `Graph.states()` and `Graph.whole()`, `GET /api/lineage`, `lakelet lineage --all`; the **Lineage** screen (`lib/graph.ts` layering, `screens/Lineage.tsx` SVG), nodes by state, a node a link | **built** 2026-09-18; 1 pytest, 5 Vitest, `models.spec` |
| W1 | An `s3://` warehouse first-class: `init --warehouse`, every verb against it, Where in the app, the docs | **built** 2026-09-18; 2 pytest, `bucket.spec` (tenth sidecar) |
| W2 | `lakelet tables publish <name> s3://…` through `relocate`'s rewriter; the route and the button | **built** 2026-09-18; 2 pytest, 1 Vitest, `attach.spec` |
| L2 | `lakelet changes` / `GET /api/changes` and the Changes screen, the Recent strip | **built** 2026-09-18; 4 pytest, 6 Vitest, `versions.spec` |

**The trust round** (`trust-round-plan.md`, T1 to T8) is on `main` since `3c60296`; the versions round's detail is in `lakelet-build-sessions_091626.md` (step 4, V3) and `lakelet-build-sessions_091726.md` (step 5, the close).

| Step | What | Status |
|---|---|---|
| 0 | T1: build-then-swap replace, `<name>__lakelet_replace`, the interrupted state, `lakelet tables rename`, `expire`'s guard | **built** 2026-09-15; 6 tests |
| 1 | T2: `lakelet.verified-at`, size and time against the listing in `refresh` and `describe`, `ChangedFiles`, `tables attach --replace`, the detail's line and **Register again**; `/docs/tables`, `/docs/remote` | **built** 2026-09-15; 5 tests, 1 Vitest |
| 2 | T3: the `none` verdict through the core, CLI, API, history, export; the app's gauge line, DAG, cards and Gauge screen; `core-nightly.yml` | **built** 2026-09-15; 7 tests, 3 Vitest, 1 Playwright; `/docs/gauge` |
| 3 | T4: `schema.py` (refuse newer, migrate older, `written_by`), `test_recovery.py` one test per sentence, `/docs/recovery`; the catalog names a full disk (507) | **built** 2026-09-15; 9 tests |
| 4 | T6: `LoopbackOnly` (Host, Origin, Content-Type refusals) on `/v1` and `/api`; `PRIVACY.md`, `SECURITY.md` | **built** 2026-09-15; 4 tests |
| 5 | T5: `moved_from` detection, `lakelet relocate` (manifests, manifest lists, position-delete files, metadata), `POST /api/relocate`, `moved_from` in health, the Tables screen's sentence and **Relocate**, the ninth sidecar | **built** 2026-09-15; 4 tests, 1 Playwright |
| 6 | T7/T8: the lede and the "next" line, the README rewritten with the generated status block (`gen-readme-status.py`, the `readme` CI job), `AGENTS.md`'s pointer, `status.ts` reconciled, `/docs/install` on the sample script, the issue template, the archives removed, the CLI reference | **built** 2026-09-15; the screenshot, the outsider and the waitlist check are Hants' |

**Session 9, the rest** (`versions-plan.md`). G1 to G10 accepted 2026-09-12 with no amendments; G11 added and decided the same day; G3's and G4's sentences corrected in the brief where they were wrong. All six steps built and verified on the Mac: 0 to 2 on 2026-09-12, 3 on 2026-09-15 (`97ee6aa`), 4 on 2026-09-17, 5 the same day. The detail is in `lakelet-build-sessions_091226.md` (steps 0 to 2), `lakelet-build-sessions_091526.md` (step 3), `lakelet-build-sessions_091626.md` (step 4 and V3) and `lakelet-build-sessions_091726.md` (step 5).

| Step | What | Status |
|---|---|---|
| 0 | dulwich in the package, `lakelet/versions.py`, `init` makes the repository and its first commit, `question save` commits with the title and the author, the `git:` reason | **built** 2026-09-12; Mac 190 passed, 5 skipped |
| — | **G11**: dbt's usage statistics off for `lakelet run` and for the profile Lakelet writes; `audit network`'s quickstart builds a model so the zero covers it | **built** 2026-09-12; the Mac suite went 267 s → 96 s |
| 1 | `lakelet versions` and `restore`, the three routes with the diff, `[git] auto_commit` and the run-time commit, the settings row | **built** 2026-09-12 |
| 2 | **Save as question** on the query screen: the title box, 409 `question_exists` → Replace it, the notice with the checks and the version | **built** 2026-09-12; the eighth sidecar came with it |
| 3 | The Versions section on the model detail, both modes, Restore (G6); `GET /api/git` for the panel's line | **built** 2026-09-15; Mac green, committed `97ee6aa` |
| 4 | `lakelet lineage`, `GET /api/lineage/{name}`, the lines on the table and model details (G8); **V3**: the per-model state (fresh, edited, upstream changed, never built) on the DAG and the cards, `lakelet run --stale` and **Refresh what changed** | **built** 2026-09-16 in the container — lineage: `lakelet/lineage.py`, the verb (`--depth`, `--json`), the route, the app's Reads from / Feeds lines with their links (3 pytest, 4 Vitest, `models.spec`); V3: `state`/`state_reason`/`state_since` on every planned model, the DAG's column and the cards' sentence, `lakelet run --stale` and **Run what changed**, then what changed shown (the SQL diff since the run, the table's commits since, the blamed model as a link) and the Review section above the DAG with the whole-SQL toggle (3 pytest, 10 Vitest, `save-question.spec`). Core 248 passed, Vitest 83, Playwright 28; **Mac green 2026-09-17** |
| 5 | Docs, the log, `TASKS.md`, the CLI reference (the close) | **built** 2026-09-17: `/docs/tables#lineage`, `/docs/dbt` ("Is it out of date?", `--stale`), `/docs/app`, `/docs/api`, `/docs` index; `status.ts` lineage → built and the README block regenerated; the CLI reference; D15, D32, S3, F0.4.5, F0.9.2 and the session map amended (§8); `astro build` 21 pages |

Gates as of 2026-09-17 (the versions round closed): core **248 passed, 10 skipped** in the container and on the Mac, Vitest **83**, Playwright **28** against nine sidecars, `tsc` clean, `astro build` 21 pages, `gen-readme-status.py --check` current, `cargo test` 8 (unchanged; it cannot build in the container). `audit network` zero, with a dbt model built inside the guards.

**Dark mode**, built 2026-09-12 and belonging to no brief (`decisions-for-review_091226.md` D1): the app follows the operating system and a **System | Light | Dark** switch in the bar overrides it, remembered per window. `src/styles/theme.css` holds the dark palette, app-only, because `tokens.css` is the site's copy and is not edited here; `lib/chart.ts` reads its colours off the document so Vega is drawn in the theme the window is in. 8 Vitest tests and `tests/theme.spec.ts` in a real window. The core is untouched.

**The real-data round** (`real-data-plan.md`, R1 to R10 accepted 2026-09-11, R3 amended) is built, steps 0 to 6, and verified on the Mac the same day; `lakelet-build-sessions_091126.md` §9 to §18 has it step by step. What is left of it, not yet done: the Spark read of a view through `catalog serve` (`tests/smoke/`), re-measuring the ship brief's S3 size expectation now that the `lakelet[dbt]` extra exists, and the week of daily use, which is Hants'.

## Next, in order

Decided 2026-09-11 (Hants, in conversation). Each item names the document that specifies it.

1. ~~Core: the disk-throughput probe~~ **done 2026-09-11** (`decisions-for-review_091126.md` 1 to 3): the probe reads with the cache bypassed (`O_DIRECT`, `F_NOCACHE`), the method is recorded, `lakelet gauge probe` measures again, health and the app's tile flag a cached figure. To run on the Mac: `lakelet gauge probe` in `~/lakelet-demo`.
2. ~~Core: snapshot expiry~~ **done 2026-09-11** (decision 4): `lakelet tables expire [<name>|--all] [--keep-days N]`, `catalog.keep_snapshots_days` (7, settable), `describe` names what is reclaimable, `POST /api/tables/{name}/expire`; attached tables refused; orphans from `import --replace` swept after an hour's grace. Five tests in `test_expire.py`.
3. ~~**The real-data round**~~ **built 2026-09-11, steps 0 to 6** (what is left of it is in "Now") (`real-data-plan.md`, session 9 widened; decided 2026-09-11 to come before ship): real S3 (the step 8 suite against Hants' bucket; the demo bucket), attach from the app, the table detail, the Gauge screen with `gauge export`, `lakelet run` with the DAG by verdict, dbt `view` models as Iceberg views in the catalog, the Models panel and Simple/Technical, the first Arrow flush. Git auto-commit and screen 9 go to the round after. **R1 to R10 accepted 2026-09-11 (R3 amended); all seven steps built and verified on the Mac the same day. Left of the round: the Spark view read (`tests/smoke/`), and the week of use.**
4. **Session 10, ship** (`lakelet-build-sessions.md`): signed installers with the sidecar and the DuckDB extensions bundled (D33), the "under 200 MB" claim measured, the frozen sidecar's spawn-to-ready measured against the 1.5 s budget (the app brief's last known unknown), brew tap, the per-operator-class correction (M7), the `catalog serve` engines smoke test through the real verb, instrumentation export, partner onboarding. **Brief written and S1 to S14 accepted 2026-09-11 (`ship-v0-plan.md`); the build follows the real-data round.**
5. ~~**Session 9, the rest**~~ **done 2026-09-17** (`versions-plan.md`, G1 to G11 decided 2026-09-12): git commits on save and on run through dulwich, `lakelet versions` and `restore`, save-as-question from the query screen, screen 9 as the model panel's Versions section, table-level lineage (D32), and V3 on top of it (each model's state, `lakelet run --stale`, the Review of what changed). Left of the brief's §6: the outsider's run and Hants' own use of versions and lineage on his project.
6. **Session 8, burst end to end**: control plane, job token, cap → budget, catalog lease pushing the metadata tree (D26), `publish`. Partner intake (five questions) runs before it. Session 3 (the Fargate worker spike, throwaway) can run any time in parallel and should run before this.
7. **Session 5, `lakelet mcp`** (after session 8, M6).

**Parked**: **Session 7, the ask box** and `lakelet ask` (M11), deprioritised 2026-09-11; ⌘/Ctrl+K stays reserved for it, and the settings for model providers with it.

**Needs another machine, or Hants, not a build step** (from the core's definition of done and the PRD):

- [ ] Clean-machine quickstart on a Mac and an Ubuntu under ten minutes (core brief §6, step 7 gate).
- [ ] Reference-laptop (16 GB) timings: `LAKELET_PERF=1` CSV imports, the ten-thousand-file registration against RustFS, the TPC-H SF1 time table with `LAKELET_TPCH=1`; the v0 gauge constants were tuned on an 18-thread, 64 GB machine.
- [ ] Demo-path bucket (core brief §6): a Lakelet-owned bucket with a public dataset, prepared with `tables attach` and nothing else, Red with the bandwidth sentence from a laptop, pyiceberg reading it from another process.
- [ ] Trademark search for "Lakelet" (USPTO, and the PyPI name); PRD D4.3 says before publishing, and the repo is public. Session 10 publishes to PyPI (`ship-v0-plan.md` S7), so the name is needed then; `lakelet-cli` is the fallback.
- [ ] An Apple Developer Program membership (US$99 a year) for signing and notarising the DMG (`ship-v0-plan.md` S4): the Developer ID certificate and an App Store Connect API key, into the repository's secrets.
- [ ] A clean Mac (never seen Lakelet) and an Ubuntu 22.04 VM for session 10's install measurements (`ship-v0-plan.md` §6).
- [x] The Open Data dataset (`real-data-plan.md` R3 as amended): Overture Maps `addresses` (21.9 GB, 32 files, 472.8 M rows) and `places`, attached from the Mac with no credentials 2026-09-11; `/docs/remote` has the commands and numbers. pyiceberg read it anonymously from another process (126,285 rows of a bounding-box scan).
- [x] AWS for the real-data round (`real-data-plan.md` R2): the private bucket and its IAM user exist and the S3 tests ran against them 2026-09-11 (`/docs/remote` has the policy and the command). Keys stay in the shell's environment, never in the repo or `lakelet.toml`; the bucket's name carries the account id and stays out of the logs. No demo bucket: R3 amended to an AWS Open Data dataset.
- [ ] The founder uses the app daily on a real dataset for a week (app brief §6). `examples/sample-data/make_sample.py` and any CSV are enough to start.
- [ ] **Trust round, Hants' items** (`lakelet-build-sessions_091526b.md` §9): ~~the Mac run~~ (green, committed `3c60296` 2026-09-16); ~~the waitlist~~ (the live build posts to the Formspree endpoint, confirmed 2026-09-16 by reading the deployed page; a test submission arrived 2026-09-15); ~~the README's screenshot~~ (taken 2026-09-16, `docs/screenshots/query-verdict.png`, revenue by month on the sample data); one outsider from clone to a saved question; the address in `SECURITY.md`.

## The map

The sessions of `lakelet-build-sessions.md`, with where each stands. That file is the authority on scope; this table is the only place status lives.

| Session | What | Status | Specified by |
|---|---|---|---|
| 1–2, 4 | Core v0: catalog, engine, import, query and history, gauge, questions, CLI, remote read-only, local API | **done** 2026-09-08; CI green 2026-09-09; step 7's clean-machine quickstart and the demo bucket outstanding (above) | `core-v0.5-plan.md` |
| 3 | Fargate worker spike (throwaway) | not started; any time, needs AWS | `lakelet-build-sessions.md` |
| 6 | Desktop shell: Tauri, sidecar, screens 1 and 2, chart, recovery, settings | **done** 2026-09-11 (steps 0–5); the week of daily use is Hants' | `app-v0-plan.md` |
| 7 | Ask box, `lakelet ask` | **parked** 2026-09-11 | `lakelet-build-sessions.md` |
| 8 | Burst end to end | not started; partner intake first | `lakelet-build-sessions.md` |
| 5 | `lakelet mcp` | not started; after 8 | `lakelet-build-sessions.md` |
| 9 | dbt and the Simple/Technical screens, widened with real S3 and three app screens; then versions, save from the app, lineage and the per-model state | **done** 2026-09-17; the real-data round's steps 0 to 6 built 2026-09-11, the versions round's steps 0 to 5 by 2026-09-17; left: the Spark view read (`tests/smoke/`) and the week of use | `real-data-plan.md`, `versions-plan.md` |
| 10 | Ship: installers, brew tap, correction, smoke test, instrumentation, onboarding | **next**; S1 to S14 accepted 2026-09-11; the versions round is closed, so its build can start | `ship-v0-plan.md` |

## Session 6, the desktop shell (`app-v0-plan.md` §4)

| Step | Status | What it left behind |
|---|---|---|
| 0 | done 2026-09-10 | `app/` (Tauri 2, React, Vite, the site's tokens); the Rust supervisor with `cargo test`s against a fake sidecar; the status dot and health panel; Playwright against a real sidecar; `app-ci.yml`. Core: `serve --memory-limit`, `LAKELET_DEV_ORIGIN` (the shell sets it in debug builds only, A12 amended). Mac: green dot, tiles. |
| 1 | done 2026-09-10 | `projects.rs`: the recent ten, the memory share (60% of RAM halved per further window), `init` for a folder without `lakelet.toml`, one window per project, close kills the sidecar; the welcome screen; `ready_ms` on the session and the "core ready in" tile. Mac: 38.3 then 19.1 GiB across two windows; spawn to ready 871 ms cold, 441 ms warm. |
| 2 | done 2026-09-10 | Screen 1: the tables panel with an updated column (core `TableInfo.freshness`), the drop zone (Tauri drag-drop, "Choose files…", a typed path), the preview with types and notes (a folder answers a list; `lakelet import <folder> --preview` too), import with replace-or-append on a 409, "Copy as command" from `lib/command.ts`; `Open…` as a menu of recent projects. Mac: an 18-column CSV from Finder; wide tables scroll inside their panel. |
| 3 | done 2026-09-10 | Screen 2: CodeMirror with completion, the verdict from the headers before any row, the streaming Arrow grid (100,000-row cap), Red as a refusal with "Run anyway", Esc. Core: `X-Lakelet-*` exposed over CORS; a client that goes away interrupts DuckDB and the run is recorded as stopped early. Mac: verdict at 56 ms, first rows at 62 ms, 66,667 rows at 143 ms over 20 M rows; the tests pick ⌘ as Mod and insert SQL as text. |
| 4 | done 2026-09-10 | The auto-chart (`lib/chart.ts`, Vega-Lite through `vega-interpreter` so no `unsafe-eval`); the window's `restarted` and `down` reactions with "Restart the core"; the settings panel over new core verbs `lakelet config show|set` and `/api/settings`, rewriting one line of `lakelet.toml` in place; ⌘/Ctrl+, and ⌘/Ctrl+K; dates, times and decimals converted per Arrow type in the grid; `examples/sample-data/`. Mac: the line chart in the Tauri window, two kills, a setting saved. |
| 5 | done 2026-09-11 | §6 measured and recorded line by line in the brief (all but the week of daily use, which is Hants'); `/docs/app` on the site; `lakelet-session-6-desktop-shell.md`; two more gates for "nothing hidden" (every request across both screens goes to the dev server or the sidecar; a release build passes no dev origin, `cargo test --release`); Yellow in the gauge-line tests. |

Gates as of 2026-09-11 (night): Playwright 22 against seven real sidecars (a 20 M-row table, a Moto bucket, a zero-day retention, a dbt project), Vitest 47, `cargo test` 8, core 170 in the container (the S3 files against a real bucket by hand on the Mac); CI green on macOS and Ubuntu for `core`, `app` and Pages.

## Core v0, the steps of `core-v0.5-plan.md` §4

All nine done on the Mac 2026-09-08 and green on both CI runners 2026-09-09 (`core #2`); the Postgres variant green. Test files `core/tests/test_step<N>_*.py`. Outstanding from the gates: step 3's timings on the reference laptop; step 7's clean-machine quickstart (both under "Needs another machine" above).

Definition of done (core brief §6): tests green on both runners ✓; budgets measured 2026-09-08 (gauge line 4 to 6 ms warm; second estimate 17 ms; `lakelet sql` to gauge line 0.81 s; query overhead beyond DuckDB 12 to 17 ms) ✓; nothing hidden (`audit network` zero, `/api` 401 without the token, loopback only) ✓; quickstart on clean machines ✗; demo path ✗.

## Open items that are not steps

- [ ] The catalog's `create_table` answers a failure inside `create_metadata` (pyiceberg refusing V3, 2026-09-21) with a bare 500 and a non-JSON body, which pyiceberg reports as "Invalid JSON"; the exception handler should turn it into the catalog's JSON error shape. Seen in a probe, not in the app.
- [ ] **V1 (format-version 3), a fact for it:** pyiceberg 0.12 refuses to *write* V3 metadata (`NotImplementedError`, apache/iceberg-python#1551), so a V3 table cannot be created through the catalog until pyiceberg can; DuckDB's writer can make one. Found 2026-09-21 while probing the geometry column.

Open:

- [x] The first Arrow batch reaching the app carries several thousand rows: it did not; the screen's stopwatch read the count late (2026-09-11, real-data step 3). The first batch is one 1,000-row batch, asserted.
- [ ] Re-export `deck/lakelet-executive-summary.pdf` from the edited docx (no LibreOffice on the Mac).
- [x] **History keeps one run per model and per question** (L2, 2026-09-18): `model_runs` and `question_runs` hold the latest run only, so `lakelet changes` shows each model's last run beside every one of its snapshots. Showing every run means keeping every row (a numbered history migration, T4) and is a decision, not a reading; the feed says what it lists. **Decided 2026-09-20 (Hants): keep every run.** History schema 2, the first migration; `lakelet-build-sessions_092026.md`. A retention or a switch for it, if the rows ever weigh, is a later decision.
- [x] **The app's welcome screen cannot make a bucket-warehouse project** (W1, 2026-09-18): `init --warehouse s3://…` is CLI-only, because the field belongs in the Tauri side's project box (`src-tauri/src/projects.rs` runs `init`) and Rust does not compile in the container. Done 2026-09-20: the container compiles the shell now (GTK and WebKit dev packages installed), `prepare` takes the warehouse, `open_project` carries it, the welcome screen has an **Advanced** box; `cargo test` 9, `Welcome.test.tsx`.
- [x] `old/deck-before-090826/` stays in history: decided 2026-09-15 (T8, agreed) — a force push on a public repository with CI and Pages on `main` is a risk with no reader waiting on it.
- [ ] `docs/lakelet-financial-plan.docx` is gitignored but still says Burrow inside; `docs/lakelet-product-spec.md` mentions Burrow once.
- [ ] Plan filename versus internal revision number; cosmetic.
- [ ] **`lakelet audit network` counts connections, not name resolutions.** The guard patches `socket.socket.connect` but not `socket.getaddrinfo`, so on a machine without DNS an attempt to reach a host *by name* is never counted, and the self-check (a bare IP) still passes. The zero is measured on a machine with DNS and unmeasured without one. Counting a non-loopback resolution as an attempt would close it and would change what the command reports, so it is a decision; the log of 2026-09-12 §2 has the measurement.
- [x] Three transfer archives at the repo root removed (2026-09-15, T8).
- [ ] `deploy-pages.yml` still has the older action majors; bump when next touched.
- [x] From the first screenshot session (2026-09-16): the grid's column widths follow the longest cell of the first column, so a two-column result puts the number far right of its header; the "Copy as command" line's `'\''month'\''` is correct shell quoting but unreadable, `lakelet sql --file` would read better when the SQL contains quotes. Both done 2026-09-18 (`lakelet-build-sessions_091826.md` §9): columns sized to what they hold; a line with a single quote and nothing `"…"` would interpret goes in double quotes.
- [x] `test_step7_cli.py`'s export test forbade the literal `990`, which a hash or a float in the export can contain by chance; `987654` now (2026-09-18).
- [x] `lakelet run <selector>` (and `--plan`) echoes the first selected model's compiled SQL on stdout before the DAG: dbt's `compile` prints it when a selection is given. Found 2026-09-16 while looking at lineage output; harmless, but it is in the way of `lakelet run --plan | …`. Done 2026-09-18: dbt's stdout log level is off under `lakelet run` (its file log is kept); `test_run` holds it.
- [ ] Known unknowns still open in the core brief's §7: the 150 ms gauge budget on a never-read table (PRD allows 800 ms uncached); how much of DuckDB's filter rendering the predicate parser needs for real workloads; partner prefixes with drift or path-only partitions (fixtures pass; intake decides); the lease carrying a metadata tree. The sidecar memory split closed with A8.

Closed:

- [x] The disk-throughput probe measured the page cache; now bypassed, with `lakelet gauge probe` for existing projects (2026-09-11).
- [x] Snapshot expiry and orphan-file removal: `lakelet tables expire` (2026-09-11).

- [x] Query overhead beyond DuckDB measured as its own test (2026-09-09).
- [x] `duckdb-extension-*` PyPI wheels: a third-party repackaging, kept out of CI; a convenience for sandboxes that cannot reach `extensions.duckdb.org` (2026-09-09).
- [x] CI actions bumped to the Node 24 runtimes (2026-09-09).
- [x] The `-q` addopt removed from `pyproject.toml` (2026-09-09).
- [x] Repo hygiene commit `7f0ff4a`, signed (2026-09-09). Commits before it are unsigned; fine for the author's own work; `git commit -s` from then on.
- [x] RustFS in `compose.yaml`; the `s3://` tests pass against it (2026-09-08).
- [x] Spark and Trino read and write a Lakelet table through the catalog (2026-09-08); session 10 repeats it through `catalog serve`.
- [x] The credential chain: a machine with no AWS credentials opens a project; `s3://` operations say which variables to set (2026-09-09).
- [x] The descriptor leak: `Project.close()` disposes the pools; a test holds 20 open/close cycles to six leaked descriptors (2026-09-09).

## The site (`web/`, live at hantswilliams.github.io/lakelet)

- [x] `PUBLIC_WAITLIST_URL`: Formspree, set as a repository variable; the deployed page carries the endpoint (confirmed 2026-09-16).
- [ ] Domain: when bought, add under Settings → Pages and set `SITE_URL`.
- [x] Screenshots (2026-09-22): `app/scripts/screenshots.mjs` retakes every capture on the landing page, `/app`, `/docs/app` and the README from the browser harness; the welcome screen and New project dialog still want a Mac capture (log §15).
- [ ] Docs follow-ups: a CI check that `gen-cli-reference.py` is current; the quickstart transcripts are illustrative until the clean-machine run replaces them; a page on `audit network` and one on history's schema.
- [x] `/docs/app` (2026-09-11), and the overview's status table names the app.
- [ ] The medallion page's `[burst.tags.<tag>]` caps and `[schedules.nightly]` are not in the architecture spec; decide whether to adopt.
- [x] Developer docs (2026-09-09): `/docs` with the pages under `web/src/content/docs/`, the CLI reference generated, `llms.txt`, the nav's GitHub link; `/docs/transactions` on what DuckDB-Iceberg refuses inside one transaction.

## Decisions waiting on Hants

**`decisions-for-review_092126.md` F1** agreed and **built** 2026-09-22 (log §16): the empty `data/` in a project is DuckDB-Iceberg's, made in the process's cwd on the first CREATE TABLE; the shell now starts the sidecar in the project folder (cargo asserts `cwd=`), the core removes the empty folder after a statement and after a dbt run (`test_a_create_table_leaves_no_stray_data_folder_in_the_cwd`). **For Hants: file `build-sessions/upstream-duckdb-iceberg-data-dir.md` on duckdb/duckdb-iceberg** and put the link here; the workaround in `engine.py` goes when it is fixed. The ship brief's installer smoke (§6) should create a table from a Dock launch.

**`decisions-for-review_092126.md` C1–C3** (2026-09-21 evening): where a bucket's credentials live. Hants agreed in chat ("I like that idea — the AWS profile name per project"); **C1 and C2 built** the same evening (log §14): the shell's `projects.json` and `aws_profiles`, `AWS_PROFILE` on the sidecar, `describe()` saying `profile`/`default`, `lakelet --profile`, the picker in New project… and Settings → Bucket, the three sentences, `/docs/remote` Credentials, `PRIVACY.md`. Gates: cargo 13, `test_a_profile_is_reported_when_the_chain_would_use_one`, `NewProject.test.tsx`, `SettingsPanel.test.tsx`. **C3** (the keychain deferred to the ship brief) is a note, not a build. All three ticked Agree by Hants 2026-09-21; C3's line is in `ship-v0-plan.md` §7. Mac run: `tauri dev`, New project… → In a bucket → Profile.

**`decisions-for-review_092126.md` Q1** agreed 2026-09-21 and **built** the same day: a question card's **See the answer** (Technical: **Rows**) — the workspace with `select * from <question>` run; a question never refreshed is refreshed first. `Models.test.tsx`, `save-question.spec`, `/docs/app`. With it, a core fix: a client gone before the first byte left the engine lock held (`test_a_client_gone_before_the_first_byte_frees_the_lock`).

**`trust-round-plan.md` T1 to T8**: decided 2026-09-15, all agreed, built the same day (above).

**`decisions-for-review_092026.md` P1, U1, U2, U3, U4 agreed 2026-09-20; P2 skipped for now** (Hants: it needs more thought). Built in the order U4, U3, U2+U1, P1 — **all five built 2026-09-20**, awaiting Hants' Mac run (`tauri dev` for the dialog and the folder it makes) and commit; the log is `lakelet-build-sessions_092026.md`.

| Item | What | Status |
|---|---|---|
| U4 | The app icon from the site's mark, macOS and Linux sets, the site favicon | **built** 2026-09-20 |
| U3 | One palette from one token file, the green family, the gauge keeps its name | **built** 2026-09-20; `palette.test.tsx`, screenshots seen by Hants |
| U2 | The sidebar with the table explorer | **built** 2026-09-20; `Sidebar.test.tsx`, `Explorer.test.tsx`, screenshots to Hants |
| U1 | The query workspace: editor over results, split | **built** 2026-09-20; `Split.test.tsx`, the specs and `/docs/app` updated, the README screenshot retaken |
| P1 | New project…: in this folder, or in a bucket, with a credential check | **built** 2026-09-20; `test_bucket_check.py`, cargo (the shell's check and the new folder), `NewProject.test.tsx`, `bucket.spec` on the tenth sidecar |
| P2 | The hosting model — skipped 2026-09-20, needs more thought; a brief when it is taken up | held |

**`decisions-for-review_091726.md` W1, W2, L1, L2, L3** (2026-09-17, from Hants' two questions after the round closed: is writing to S3 handled — partly, at the catalog layer, not as a product path — and how to show the lineage of file and Iceberg changes): W1 an `s3://` warehouse first-class at `init`; W2 `lakelet tables publish` (the PRD's `publish`, pulled forward from session 8 through `relocate`'s rewriter); L1 a Lineage screen (the graph, drawn by the app); L2 a Changes feed across tables, models and versions; L3 each snapshot naming the models it made out of date. Ship (`ship-v0-plan.md`) is held behind whatever is chosen (Hants, 2026-09-17: not publishing yet).

**`decisions-for-review_091526.md` V1, V2, V4** (2026-09-15, from the four articles in `research/`; `research/README.md` has the links): V1 format-version 3 for new tables after a spike; V2 `lakelet tables compact`; V4 the durability sentence, Renart and Duckle as comparables, the unsourced figures kept out. V1 first: V2 depends on its result. **V3 decided 2026-09-16** (a per-model state and `lakelet run --stale`): built inside step 4 of the versions round.

Decided: `decisions-for-review_091226.md` D1 (dark mode, 2026-09-12, built the same day); `versions-plan.md` G1 to G10 (2026-09-12, no amendments; one correction of fact recorded under G3 when step 0 was built); `real-data-plan.md` R1 to R10 (2026-09-11, R3 amended the same day); `ship-v0-plan.md` S1 to S14 (2026-09-11), build held until the real-data round; `decisions-for-review_091126.md`, all four (2026-09-11), shipped the same day; `app-v0-plan.md` A1 to A14 (2026-09-10); `decisions-for-review_090926.md`, all three (2026-09-09); the order of what follows step 5 (2026-09-11, above).

## Done

- 2026-09-17 — **The versions round closed** (step 5): the docs for lineage and the state, `status.ts` and the README block, the CLI reference, the §8 amendments, the session map. Step 4's Mac run green. See `lakelet-build-sessions_091726.md`.
- 2026-09-16 — **Versions step 4**: `lakelet lineage`, `GET /api/lineage/{name}`, the Reads from / Feeds lines with their links on every detail; **V3** decided and built on top of it — every model's state (fresh, edited, upstream, never) with why, when and what changed (the SQL diff since the run, the table's commits since, the blamed model as a link), `lakelet run --stale`, Run what changed, the Review section. The waitlist confirmed from the live build; the README's screenshot. See `lakelet-build-sessions_091626.md`.
- 2026-09-15 (later) — **The trust round**, T1 to T8, decided and built: safe replace, changed-file detection, the fourth verdict, schema versions and `/docs/recovery`, the catalog's refusals with `PRIVACY.md` and `SECURITY.md`, `lakelet relocate`, the lede and the README. See `lakelet-build-sessions_091526b.md`.
- 2026-09-15 — History's timestamps read back naive from SQLite and reached the app an hour out in London: one `_utc` on every read path, with a test (the Mac found it in `models.spec.ts`; the UTC container could not).
- 2026-09-15 — The research read and recorded (`decisions-for-review_091526.md`, `research/README.md`, `research/` gitignored). Versions step 3 built: the Versions section on the model detail (Technical: the log, the diff, Gauge then/now, Restore with its line, the git line; Simple: History on the card, sentences, one button), `versions.status` and `GET /api/git` in the core. See `lakelet-build-sessions_091526.md`.
- 2026-09-07 — Review of the original brief; `core-v0.1-plan.md` (revision 3) with D19 to D24; measurements on DuckDB 1.5.5 and pyiceberg 0.12.
- 2026-09-08 — Remote-data decisions R1 to R6 accepted; `core-v0.2-plan.md`. MinIO replaced by Moto, measured. Site and deck compared; M1 to M12 accepted; `core-v0.3-plan.md`, `core-v0.4-plan.md`. §10 wording applied to `web/src` and the deck. Readiness review; gitignore decision; `CLAUDE.md`, `AGENTS.md`, README; `core-v0.5-plan.md` (revision 7). Steps 0 through 9 built and their gates passing on the Mac; Postgres, RustFS, Spark and Trino verified through `compose.yaml`.
- 2026-09-09 — Repo hygiene commit `7f0ff4a`; CI failed then green after the credential chain and descriptor-leak fixes; developer docs on the site; the dbt materialisation through the catalog; `/docs/transactions`; the desktop shell brief.
- 2026-09-10 — `app-v0-plan.md` A1 to A14 accepted; steps 0 to 4 of the desktop shell built, each verified on the Mac; core additions along the way (`serve --memory-limit`, `LAKELET_DEV_ORIGIN`, `freshness`, folder preview, verdict headers over CORS, interrupt on disconnect, `config show|set`, `/api/settings`); `examples/sample-data/`. See `lakelet-build-sessions_091026.md`.
- 2026-09-11 — Session 7 deprioritised; this file restructured (Now, Next in order, the map); the two core items decided (`decisions-for-review_091126.md`) and built: the probe with the cache bypassed and `lakelet gauge probe`, `lakelet tables expire` with `keep_snapshots_days`; step 5 of the app brief, closing session 6; the session 10 brief written and accepted (`ship-v0-plan.md`), held behind the real-data round, whose brief was written (`real-data-plan.md`). See `lakelet-build-sessions_091126.md` and `lakelet-session-6-desktop-shell.md`.
- 2026-09-12 — `versions-plan.md` G1 to G11 decided; steps 0, 1 and 2 built and verified on the Mac: git in the core and a commit for every save, `lakelet versions` and `restore` with the three routes, `[git] auto_commit` and a version on every run, **Save as question** on the query screen. G11 out of a test failure: dbt's usage statistics off wherever Lakelet invokes or configures it, and `audit network`'s quickstart building a model so the zero covers `lakelet run`. Two bugs Hants caught in review (the checks mark comparing the file rather than the model's entry; the run-time commit before the Red refusal) and two the Mac caught that the container could not (a spec sharing a sidecar; `localStorage.clear` on a Node that shadows jsdom's). Dark mode for the app, `decisions-for-review_091226.md` D1. See `lakelet-build-sessions_091226.md`.
- 2026-09-11 (later) — The real-data round, steps 0 to 6, built and verified on the Mac in one day: the S3 suite against a real bucket and the metadata cache; `--anonymous` and Overture as the demo; attach from the app; the table detail, the first flush, row counts with deletes; the Gauge screen with export and reset; `lakelet run`, the dbt plugin in the package, views as Iceberg views in the catalog (R6's write path is `lakelet run`'s, documented for dbt users); the Models screen, Simple and Technical mode, the view's own detail. Commits `fca9850`, `682cbf5`, `a038a89` and step 6's. See `lakelet-build-sessions_091126.md` §9 to §18.
