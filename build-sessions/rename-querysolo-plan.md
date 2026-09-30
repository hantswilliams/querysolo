# Rename: Lakelet → QuerySolo — September 30, 2026

*A plan, not a build. The product's name changes from Lakelet to QuerySolo everywhere the product speaks: the Python package and the command, the desktop app, the site, the docs, and the words in `marketing/`. The company will have a different name; QuerySolo is the product. Registry and domain checks on 2026-09-30 found the name free on PyPI, npm (including the `@querysolo` org), crates.io, Homebrew, conda-forge, GitHub, Docker Hub, the VS Code Marketplace and both App Stores, and querysolo.com, .dev, .app, .io and .ai unregistered. No USPTO search has been made yet. Nothing is built until the boxes below are ticked.*

## What the review found

- **The scale.**
  - "lakelet" appears about 4,500 times in 342 tracked files: app 105, core 87, web 70, build-sessions 42, the rest spread thinly.
  - Twenty files carry it in their own name: the `core/lakelet/` package, `core/freeze/lakelet.spec`, the app icon sources, `compose/trino/lakelet.properties` and the session logs.
  - There are 23 `LAKELET_*` environment variables, mostly test and dev switches. `LAKELET_EXTENSION_DIR` is the one the frozen app depends on.
- **Most of it is a straight rename.** This covers module paths, imports, strings, labels, docs, the command, env vars, the Tauri product name, and the Cargo and npm package names.
- **Some of it is persisted in projects that already exist**, and a find-and-replace would break those projects:
  - The project folder's `.lakelet/` directory (catalog, history, cache, dbt) and `lakelet.toml`.
  - Iceberg table properties written into table metadata: `lakelet.source-prefix`, `lakelet.verified-at`, `lakelet.anonymous`, `lakelet.metadata-placement`, `lakelet.dbt-model`. Spark and Trino see these too.
  - The `__lakelet_replace` suffix of an interrupted table replace. Recovery looks for it by name.
  - The `lakelet_version` column in `history.db`, and the same field in the calibration export.
  - The app's data folder, named after the bundle identifier `dev.lakelet.app`, which holds `projects.json` (the recent list and each project's AWS profile).
  - The project's generated `.gitignore` and `AGENTS.md`. The dbt profile under `.lakelet/dbt` is rewritten on every run, so it follows automatically.
- **The site's address depends on the repository's name.** GitHub Pages serves the site at `/lakelet/` because the repository is `hantswilliams/lakelet`. `web/astro.config.mjs` and the site tests assume that base.
- **The website v2 work is not committed.** It lives on `web/warehouse-for-one` in `../lakelet-warehouse-for-one`, including `/explore/querysolo`. A rename branch cut from `main` today would not contain it, and the two would conflict across `web/`.
- **History should stay history.** The session logs and old plans record what was built under the old name, and rewriting them would falsify the record. `docs/` is different: it holds the living product spec.

## Review decisions

Each decision has a recommendation, the reason, and where it lands. The body below assumes the recommendation, so a Change is a targeted revert.

**R1. Commit website v2 on its branch first, then cut `rename/querysolo` from it.**
- Commit the v2 worktree to `web/warehouse-for-one` (DCO sign-off).
- Create the rename branch from that commit, in a new worktree `../lakelet-rename`.
- `main` stays as it is until you merge.

Why: the rename touches every page v2 changed. Stacking the branches avoids a three-way merge over the whole site.
Lands: step 0. If you Change: branch from `main` and rename `web/` again after v2 merges.
- [x] Agree
- [ ] Change:

**R2. A clean break for the command and the package, with no `lakelet` alias.**
- The Python package becomes `querysolo` (import and distribution), and the command becomes `querysolo`.
- `LAKELET_*` environment variables become `QUERYSOLO_*`, with no fallback.

Why: it is a developer preview with one daily user and nothing on PyPI. An alias would be code to maintain for nobody.
Lands: steps 1–2.
- [x] Agree
- [ ] Change:

**R3. Existing projects migrate themselves, once, on open.**
- A project that has `.lakelet/` and `lakelet.toml` but no `.querysolo/`: the folder and the file are renamed in place.
- Its `.gitignore` line and `AGENTS.md` are rewritten.
- The step is recorded in the schema table (`schema.py` already migrates older layouts).
- A project that has both layouts is refused, with a sentence naming both.
- Each sentence gets a test, the way `/docs/recovery` works.

Why: your own projects keep working with no command to remember. The refusal covers the one ambiguous case.
Lands: step 1.
- [x] Agree
- [ ] Change:

**R4. Table properties: write `querysolo.*`, read both.**
- New writes use `querysolo.source-prefix` and the others.
- Reads accept `querysolo.*` first, then `lakelet.*`.
- Existing tables are not rewritten: the metadata is immutable history, and a rewrite would be a commit per table.
- The replace suffix becomes `__querysolo_replace`, and recovery still recognises `__lakelet_replace`.

Why: old tables keep their verification, source prefix and model links, without a migration that touches every table's metadata.
Lands: step 1.
- [x] Agree
- [ ] Change:

**R5. The history column and the export field rename through a schema migration.**
- `history.db`'s `lakelet_version` becomes `querysolo_version`, as a numbered migration in `schema.py`.
- The calibration export writes `querysolo_version`.

Why: the export is a file other people may read, so its field should carry the product's name. The migration machinery already exists and is tested.
Lands: step 1.
- [x] Agree
- [ ] Change: leave internal column names as they are

**R6. The app's identifier becomes `dev.querysolo.app`, and the old data folder is copied across once.**
- On first launch, if the new data folder has no `projects.json` and the old one does, it is copied, never moved, so the old app still works.
- The product name becomes QuerySolo, and the sidecar folder in the bundle becomes `querysolo/`.
- `localStorage` keys (sidebar, theme) reset, which is harmless.

Why: the identifier must change before the Apple signing step (ship S3), because the signed identity fixes it. Copying keeps your recent projects and each project's AWS profile.
Lands: step 3.
- [x] Agree
- [ ] Change:

**R7. The site moves to `/querysolo/` with a repository rename that you do.**
- `astro.config.mjs` defaults to `/querysolo/`, and every link and test follows.
- You rename the GitHub repository to `hantswilliams/querysolo` just before merging. GitHub redirects the old repository URL; the old Pages URL does not redirect.
- A custom domain (querysolo.com) is a later, separate step.

Why: the base path and the repository name have to change together.
Lands: step 4 (code); the repository rename is yours.
- [x] Agree
- [ ] Change: keep `/lakelet/` until the custom domain

**R8. What stays "lakelet" on purpose.**
- The session logs and past plans in `build-sessions/`, under their old file names.
- `old/`.
- Git history.
- The dual-read code from R3 and R4, with their tests.

From this round on:
- New session logs are `querysolo-build-sessions_<MMDDYY>.md`, and `CLAUDE.md`'s instructions say so.
- `docs/` (the living spec) is renamed.

A test enforces the list: `lakelet` may appear only in an allowlist of paths and identifiers.

Why: the record stays true, the product speaks one name, and the allowlist catches anything the rename misses.
Lands: steps 5 and 6.
- [x] Agree
- [ ] Change:

**R9. The app icon and brand art are not part of this round.**
- Icon source files are renamed, but the art stays.
- The prompt mark (`brand/querysolo-logos.html`, direction C) replaces the icon in a design step of its own, before the signed installer.
- `marketing/`'s TBD\* token becomes QuerySolo.
- `marketing/names.md` records the decision and the 2026-09-30 checks.

Why: a rename should be reviewable as a rename. A new icon is a design decision with its own review.
Lands: step 5.
- [x] Agree
- [ ] Change: swap the icon to the prompt mark in this round

**R10. Claim the name before the rename is public.**
This is yours, not code:
- querysolo.com, plus .dev and .app
- the GitHub organisation `querysolo`
- the npm organisation `@querysolo`
- a PyPI placeholder `querysolo` 0.0.0, or the real 0.1 when ship lands
- a USPTO clearance search in classes 9 and 42, with the filing in the company's name

Why: merging makes the name public, and every one of those is first-come.
Lands: before the merge. It does not block the code.
- [x] Agree
- [ ] Change:

## Scope

**In:**
- **core:** the package, the CLI, config, env vars, persisted names with migration and dual-read, the dbt plugin module path, the freeze spec and `build.py`.
- **app:** Tauri config, Cargo and npm names, the sidecar lookup, UI strings, the data-folder copy, Playwright's sidecar helper.
- **web:** site name, nav, footer, docs, `llms.txt`, `status.ts`, the CLI reference regenerated from the renamed help text, the base path, the tests.
- **Root files:** README (with its generated status block), `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `PRIVACY.md`, `NOTICE`.
- **Everything else:** `.github/workflows`, `compose.yaml` and `compose/`, `examples/`, `docs/`, `marketing/`, `personas/`, and the deck generator in `deck/`, which is gitignored.

**Out:**
- The repository rename, domains, handles, the trademark search (R10).
- The icon art (R9).
- The session history (R8).
- Any behaviour change beyond the migration.

## Gate

- **Every existing suite passes on the rename branch**, with each total no lower than its baseline:
  - core pytest (274 passed, 7 skipped at the last count)
  - Vitest (126)
  - `cargo test`
  - Playwright against a real sidecar
  - the site's pytest (95 on v2)
  - `gen-readme-status.py --check`
- **New tests, written first:**
  - A project in the old layout opens, migrates, and keeps its tables, history, questions and versions.
  - A project with both layouts is refused, with its sentence.
  - An old table's `lakelet.*` properties still drive verification, the source prefix and lineage.
  - An interrupted `__lakelet_replace` is still recovered.
  - `history.db` migrates `lakelet_version`.
  - The app copies `projects.json` from the old data folder once, and never moves it.
  - The allowlist test from R8.
- **Your projects:** your real projects on the Mac open in the renamed app, with nothing lost.
- **The frozen build:** `freeze/build.py --check` is green with the renamed binary.
- **A dated session log** and both task lists are updated.

## Implementation order

0. Commit v2 on its branch (R1, with your go-ahead for the commit). Create `rename/querysolo` in `../lakelet-rename`. Run every suite and record the baseline. → verify: all green.
1. Core.
   - Do the moves first: `git mv core/lakelet core/querysolo`, and `lakelet.spec` → `querysolo.spec`.
   - Then imports, `pyproject.toml`, the command, env vars.
   - Then the persisted names: folder and file migration (R3), table-property dual-read (R4), the history migration (R5).
   - The migration tests come before the migration code.
   → verify: core suite plus the new tests green.
2. Freeze, CI and compose: the spec, `build.py`, the workflows, the Postgres test URL, the Trino catalog file. → verify: `freeze/build.py --check` on Linux, CI green on the branch.
3. App: identifier, product name, Cargo and npm names, the sidecar path and env var, UI strings, the data-folder copy with its Rust test (R6). → verify: `cargo test`, Vitest, Playwright.
4. Site: name, nav, footer, `status.ts`, docs, the regenerated CLI reference, `llms.txt`, the `/querysolo/` base (R7), the tests, the README status block. → verify: build, the site's pytest at both bases, the README check.
5. Words: the root files, `docs/`, `examples/`, `marketing/` (TBD\* → QuerySolo, the decision in `names.md`), `personas/`, the deck generator, and `CLAUDE.md`'s log-name rule (R8, R9). → verify: nothing reads "Lakelet" except the allowlist.
6. The allowlist test (R8), a full run of every suite, the session log, and both task lists. Stop for your review. Then you rename the repository and I open the pull request, or you merge it yourself.

## Gate results

*2026-09-30: detail in `querysolo-build-sessions_093026.md`.*

- [x] Baseline recorded on `rename/querysolo`: core 274/7 skipped, Vitest 126, cargo 14, Playwright 31, site 95, README current
- [x] Core renamed; migration tests green (6, plus the bucket `discover` test)
- [x] Freeze, CI and compose green: `freeze/build.py --check` green on the Mac, 292 MB (log §8); CI runs on push
- [x] App green: cargo 15, Vitest 126, Playwright 31; data folder copied (one Rust test)
- [x] Site green at `/querysolo/` and `/` (95 each); README check green
- [x] Words renamed; allowlist test green, and it fails on a planted stray
- [ ] Your projects open on the Mac with nothing lost
- [ ] Your review before the repository rename and merge
