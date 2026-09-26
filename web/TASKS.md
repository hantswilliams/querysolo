# The site — running task list

*The one file to open to know where `web/` is. Same job for the site that
`build-sessions/TASKS.md` does for the core: status lives here and nowhere else.
The site's own facts live in `src/data/` (`status.ts`, `facts.ts`, `pricing.ts`,
`nav.ts`); `/docs` describes the code and is the authority on what is built.*

**Rule this file exists to enforce:** the marketing pages may describe the plan,
but they may not imply the plan is shipped. `/docs/index.md` has the built /
not-built table; every marketing page that names an unbuilt feature carries a
dated strip that says so. Where a marketing page and `/docs` disagree, `/docs`
wins and the marketing page is the bug.

---

## Website v2: a warehouse for one — planned 2026-09-26

Scope: `build-sessions/website-story-v2-plan.md` (W1–W13), from `marketing/landing-page.md` after a review of `marketing/`, `personas/` and `research/`. PR #1 was merged 2026-09-18, so this builds on `main`.

- [ ] Hants reviews W1–W13 in the plan.
- [ ] Build steps 0–6 once agreed; the gate is in the plan.

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


## Website exploration — 2026-09-16 (this branch only)

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

## Where this came from

Review on 2026-09-11 (Hants + Claude). The marketing pages had not been touched
since 2026-09-08 (`6290775`); the only commit since that touched
`web/src/pages` was `504b657`, which added the `/docs` route. Everything built
between those dates and now — the whole desktop app (session 6, steps 0–5), real
S3, the Overture demo, `tables expire`, the fixed disk probe — was invisible on
the front of the site, while `/docs` said plainly that burst, `ask` and `mcp`
are not built. The repo is public, so both were readable at once.

Six items came out of it. Five are being done now; item 4 is deferred by
decision because it needs screenshots only Hants' Mac can take.

---

## Now

**Done 2026-09-11**, in one pass: items 1, 2, 3, 5 and 6. Item 4 is next and is
deferred deliberately (below). One thing is waiting on Hants: setting the
`PUBLIC_WAITLIST_URL` repo variable to the Formspree endpoint, without which the
waitlist still captures nothing — it just says so now instead of pretending
otherwise, and the deploy warns.

Verified: all 23 `.astro` files compile through `@astrojs/compiler`; the data
modules typecheck under `tsc --strict`; every relative import resolves; every DOM
id the scripts query exists in its template; the demo's arithmetic reproduces the
transcript numbers at the gauge's real thresholds; the server-rendered defaults
are byte-identical to the script's first render. A full `astro build` could not
be run from this session (the npm registry is blocked by egress policy on both
machines available to it), so **run `npm run build` once before pushing.**

## Next, in order

1. **Item 4 — rebuild `/app` around the real app.** Deferred 2026-09-11 by
   decision, to come back to after this pass. Ten hand-built HTML mockups today,
   of which screens 1 and 2 exist for real and differ from the mockup; the table
   detail with its snapshot list is real and is not in the mockups at all.
   Needs: screenshots of the running Tauri window (Hants' Mac, `npm run tauri
   dev` — the app has no installer yet), the measured timings under them
   (verdict 56 ms, first rows 62 ms, 66,667 rows at 143 ms over 20 M rows,
   spawn-to-ready 871 ms cold / 441 ms warm), and screens 3–6 and 9–10 moved
   into a section marked as designed-not-built. The honesty strip added in item
   2 holds the page until then.
2. **Re-check every page against `/docs` when burst lands** (session 8). The
   strip data in `src/data/status.ts` is the only place to edit.
3. **Docs follow-ups** (carried from `build-sessions/TASKS.md`): a CI check that
   `gen-cli-reference.py` is current; the quickstart transcripts stay
   illustrative until the clean-machine run replaces them; a page on `audit
   network`; a page on history's schema.

## A note on concurrent sessions

This pass overlapped with the real-data round's steps 4 and 5, which landed the
Gauge screen and `lakelet run` while it was in flight — and the other session
overwrote `public/llms.txt`, reverting an edit made here. Everything else
survived. Two consequences worth keeping:

- `src/data/status.ts` was reconciled against `src/content/docs/index.md`
  afterwards, and carries the date it was last reconciled. **Do that check
  whenever a session ships something**; it is a one-file edit and it is the
  whole point of the file existing.
- If you touch `web/` from two places at once, check `git diff` for `llms.txt`
  and `status.ts` specifically. They are the two files that summarise the whole
  build, so they are the two most likely to be written by both sides.

## Deferred, with the reason

- **`/pricing`.** The model numbers are sourced and the "where Lakelet is not
  the cheapest" section is honest. Leave it until burst is real and the ladder
  can carry measured numbers instead of Fargate list arithmetic.
- **`/how-it-runs` and `/medallion`.** Vision pages that read correctly as
  vision. They get the item-2 strip and nothing else.
- **The `[burst.tags.<tag>]` caps and `[schedules.nightly]` on `/medallion`**
  are not in the architecture spec. Decide whether to adopt before the page
  claims them. (Carried from `build-sessions/TASKS.md`.)

---

## This pass

| # | Item | Status | Touches |
|---|---|---|---|
| 1 | Waitlist stops silently discarding signups | **done**; needs the repo variable set | `layouts/Base.astro`, `components/Waitlist.astro`, `astro.config.mjs`, `.env.example`, `README.md`, `deploy-pages.yml` |
| 2 | Built-vs-planned strip, dated, one source | **done** | `data/status.ts` (new), `components/BuildState.astro` (new), `pages/app.astro`, `pages/agents.astro`, `pages/index.astro`, `public/llms.txt` |
| 3 | Overture replaces the invented demo | **done** | `data/demo.ts` (new), `components/GaugeSlider.astro`, `components/ReplayTerminal.astro`, `pages/index.astro` |
| 4 | `/app` rebuilt on the real app | **deferred** — next | — |
| 5 | Factual drift | **done** | `pages/index.astro`, `data/facts.ts`, `data/nav.ts`, `components/Verdicts.astro`, `pages/{pricing,agents,medallion,app}.astro` |
| 6 | `SITE_URL` / canonicals / robots | **done** | `astro.config.mjs`, `public/robots.txt` (deleted), `README.md` |

### Hants, before this is live

*2026-09-16: all three done. The deployed page's waitlist handler posts to `https://formspree.io/f/meaqdnjv` (read off the live build, so the repository variable is set), Hants confirmed a test submission arrived on 2026-09-15, `npm run build` has run on the Mac and in the container (21 pages), and the trust round's lede is live.*

1. **Set the repo variable.** Settings → Secrets and variables → Actions →
   Variables → New variable: name `PUBLIC_WAITLIST_URL`, value
   `https://formspree.io/f/meaqdnjv`. This is the only step nothing in the repo
   can do for itself; until it is done, every visitor who submits is told
   signups are not open — true, but not the goal — and the Pages run carries a
   warning annotation saying so.
   Then submit the form once yourself on the deployed site: Formspree holds a
   new form until its owner confirms the first submission by email.
2. `cd web && npm run build` once locally — this session could not reach the npm
   registry, so the build has not actually been run against these changes.
3. Push. Pages redeploys on any commit touching `web/`.

---

## Open decisions

- [x] **Waitlist provider: Formspree** (decided 2026-09-11). Chosen over moving
  the site to Cloudflare Pages because the site stays on GitHub Pages and the
  change is one repo variable. `functions/api/waitlist.ts` stays in the tree,
  unused and kept in sync, for the day the site does move.
  **Form: `https://formspree.io/f/meaqdnjv`** (Hants, 2026-09-11). It is in
  `web/.env` for local work and in `.env.example`; a form id is not a secret,
  because Astro inlines every `PUBLIC_` variable into the browser bundle.
  **The one manual step left:** set it as the repo variable
  `PUBLIC_WAITLIST_URL` under Settings → Secrets and variables → Actions →
  Variables. Nothing in the repo can do that for it, so the Pages workflow now
  posts a warning annotation on any deploy where the variable is missing.
- [x] **Domain: point at the real GitHub Pages URL for now** (decided
  2026-09-11). `astro.config.mjs`'s local default was `https://lakelet.dev`, a
  domain nobody owns, so every canonical and the sitemap pointed at it.
- [ ] **Buy a domain.** When bought: add it under repo Settings → Pages, set the
  `SITE_URL` repo variable, and the workflow switches `SITE_BASE` to `/` on its
  own. Nothing in the source needs editing.
- [ ] **Trademark search for "Lakelet"** (USPTO and the PyPI name). PRD D4.3
  says before publishing; the repo is already public and session 10 publishes to
  PyPI, so the name is needed by then. `lakelet-cli` is the fallback. Carried
  from `build-sessions/TASKS.md`; it is a site problem too, because the site is
  the thing that markets the name.
- [ ] **Pre-seed ask amount** — nothing on the site mentions raising; noted only
  so it is not forgotten.

---

## Item detail

### 1. The waitlist was throwing away every signup

`PUBLIC_WAITLIST_URL` was never set, so `submitWaitlist()` in `Base.astro` fell
through to `console.log` **and returned `true`**, which hid the form and showed
"You're on the list. We'll be in touch." Every call to action on all six pages
leads to that form. Signups since the site went up on 2026-09-09 are gone and
are not recoverable.

Two separate bugs, both fixed:

1. **Unconfigured is not success.** With no endpoint set, the form no longer
   confirms. It says early access is not open yet and points at the repo. The
   build prints a warning naming the variable, and the Pages workflow adds a
   GitHub Actions warning annotation, so a deploy that captures nothing cannot
   pass unnoticed.
2. **A failed POST is not success.** Already half-handled; the failure path now
   also restores the form instead of leaving a disabled button.

The honeypot field was renamed from `website` to `_gotcha`, which is the name
Formspree recognises, so a bot that fills it is dropped twice: here before the
POST, and again at the provider.

`functions/api/waitlist.ts` was written for Cloudflare Pages Functions, which
GitHub Pages does not run. It is left in place, and kept in sync, for a future
move.

### 2. Dating the vision pages

`src/data/status.ts` is the single source: one entry per surface, `built` or
`planned`, planned ones naming the session that builds them. `BuildState.astro`
renders it as a strip. It goes at the top of `/app` and `/agents` — the two
pages that describe unbuilt things in the present tense — and the homepage's
stat bar now links to `/docs` rather than to its own `#engineers` anchor, which
is where it was pointing.

When a session ships, edit `status.ts` and every page follows.

### 3. Overture instead of the invented demo

The homepage was demonstrating the gauge on a fictional 48 GB `events` table
with a `$0.41` burst cap, for a feature that is not built, driven by
`lakelet ask`, which is parked. Meanwhile a real, reproducible, no-account demo
existed in `/docs/remote` and appeared nowhere a visitor would see it.

Measured 2026-09-11 against Overture Maps release `2026-08-19.0`, from a laptop
with no AWS credentials in the shell:

- `addresses` — 472,797,160 rows, 32 files, 21.9 GB, attached with nothing copied
- `places` — 73,631,092 rows, 16 files, 10.5 GB
- `group by country` over `addresses` scans 218.9 MB (one column of 21.9 GB)
- a bounding-box count over `places` scans 104.8 MB, estimated 8 s, **ran in 4.1 s**
- `select *` over either is Red at any home link
- the laptop's measured downlink: 111 Mbps

The slider in the hero now moves the one input that genuinely differs per
visitor — link speed — over a real scan size, instead of inventing a table.
The numbers live in `src/data/demo.ts` so the page and any future copy of it
cannot drift from `/docs/remote`.

### 5. Factual drift

| Was | Is | Why it mattered |
|---|---|---|
| `$ brew install lakelet` in the hero | the real `git clone` + `uv sync` | No tap, no PyPI, no installer — session 10. `/docs/install` opens with "There are no installers yet." |
| `v0.1.0 · private beta` | `v0.1.0.dev0 · developer preview` | The package is `0.1.0.dev0` and is not on PyPI. There is also no beta to be in. |
| `brew · pipx · signed DMG` | `from source · installers at Day 1` | None of the three exist. The DMG additionally needs the Apple Developer membership (US$99/yr) that has not been bought. |
| `dbt Core 2 · Rust runtime` | `dbt Core 1.12` | `core/pyproject.toml` pins `dbt-core>=1.12.4`, `dbt-duckdb>=1.11.0`. |
| "Source opens with the Day 1 launch" | a link to the repo | The repo has been public since `7f0ff4a`. The site was hiding its own best asset. |

`facts.ts` also had three entries, newest 2026-08-26, all about other people's
releases. It now carries what Lakelet itself has shipped, which is the thing a
visitor cannot find anywhere else.

### 6. Canonicals pointed at a domain nobody owns

**Note for local dev:** `base` now defaults to `/lakelet/` as well, so
`npm run dev` serves at `http://localhost:4321/lakelet/` and a plain
`npm run build` is the production build. A base-path bug should break on the
first local page load rather than on the first deploy.


`astro.config.mjs` defaulted `site` to `https://lakelet.dev`. The Pages workflow
overrides it correctly, so production canonicals were right, but `robots.txt`
was **not** generated: `src/pages/robots.txt.ts` builds the sitemap URL from
`site` + `base` correctly, and a *static* `public/robots.txt` with a hardcoded
`https://lakelet.dev/sitemap-index.xml` was shadowing it. The static file is
deleted and the route does its job.

---

## Done

- 2026-09-09 — the site went live on GitHub Pages; `/docs` added (`504b657`).
- 2026-09-11 — review; this file; items 1, 2, 3, 5 and 6 built. Waitlist wired to
  `https://formspree.io/f/meaqdnjv` (honeypot renamed to `_gotcha` so Formspree
  filters it too; the Pages workflow warns on a deploy with no endpoint).
  Reconciled afterwards with the round's steps 4 and 5: the Gauge screen is real,
  so `/app` screen 5 is marked built, and `lakelet run` is real, so the homepage
  says so and only `--burst auto` is marked unbuilt. Three new files
  carry the rules the pages now follow: `src/data/status.ts` (built vs planned),
  `src/data/demo.ts` (the measured Overture numbers), `src/components/BuildState.astro`.
  `public/robots.txt` deleted so the generated route works. `public/llms.txt` now
  opens with the build state, so an agent reading the site cannot claim an
  unbuilt feature exists.
