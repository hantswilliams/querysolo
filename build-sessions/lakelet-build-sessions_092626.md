# Lakelet build session — 2026-09-26

*The site rebuilt around "a warehouse for one": `website-story-v2-plan.md`, W1–W13 all agreed by Hants the same day. The plan came from a review of `marketing/`, `personas/` and `research/` in the first half of the session. Nothing in `core/` or `app/` changed. Built on branch `web/warehouse-for-one` in the worktree `../lakelet-warehouse-for-one`. The branch came off local `main` at `eaca640`, which was two commits ahead of `origin/main` and held the plan. Nothing committed or pushed.*

## 1. The gate first

Six new tests in `web/tests/test_website.py` (26 parametrised checks):
- the hero and the tab title
- the home sections in the order of the three beats, with the lines each beat needs
- the doors' states read from `status.ts`, the third one planned
- "Lakelet Lookahead" absent from every route, and "lakehouse" absent from every marketing route
- the banned words absent from home, app and pricing; "Windows" is matched case-sensitively because the App page says "project windows"
- pricing: "For one" and then "For a team", no Compaction, no `brew install` or `foot:` in `pricing.ts`

All 26 failed on the baseline, for the reasons expected.

## 2. The vocabulary pass (W4, W5, W11)

- **"Lakelet Lookahead" → "Lookahead"** in `gauge.md` (its title is the docs nav's label, which is why every docs page failed), `DataStory`, `LookaheadDemo`, `status.ts`, App and How it runs.
- **"lakehouse" out of the shared parts of the site:** the footer ("A warehouse for one."), `site.tagline` (so the home tab reads "Lakelet — A warehouse for one"), `llms.txt`, and the docs index's first sentence.
- **Still says "lakehouse", on purpose:** `docs/cli.md` and `docs/install.md`. They carry `lakelet init`'s own help text and output, which live in the core.
- **The README:** the lede is now the one-liner; "`init` makes it a lakehouse" became "a warehouse"; "the size most teams actually have" became "a warehouse for one". The status block was regenerated and the check is current.
- **A planned `slice` surface** in `status.ts`, with a matching "Not yet" row in `docs/index.md`. The README block gains its row.

## 3. The home page (W3, W6, W7, W8, W10)

`index.astro` is rewritten.
- **Hero:** the chip, "A warehouse for one.", the one-liner, "Know what fits. Know what changed.", and "Planned next: …".
- **01, Know what fits:** the demo, with its heading changed to "Before you run it, know.", the four verdicts by name, "No silent fallback", and the BigQuery line.
- **02, Know what changed (new):** three columns over the Lineage, Changes and Questions screenshots already in `public/screenshots/`.
- **03, the storage diagram:** retitled "Your machine. Your bucket. Your tables." and moved here from the top of the page.
- **The folder section:** "A warehouse. In a folder.", with "Iceberg, so the tables outlive the tool", the measured zero and its scope from `PRIVACY.md`, and a recovery link naming `expire`.
- **04, How it fits:** three short columns. "Most teams" and the burst paragraph are gone. The app capture moved in from the old "05 / The workspace" section.
- **05, Three doors:** state from `status.ts`.
- **06, For one, today:** the one-writer paragraph and the planned team sentence.
- **Then** the status block and the call to action, unchanged.
- **Removed:** "03 / The idea", whose three links moved into beats 1–3.

## 4. Pricing and sub-pages (W9)

- The cards are now "For one", "For a team" and "Burst".
- "Compaction and alerts" became "Freshness and test alerts".
- The three unrendered `foot:` strings are gone from `pricing.ts`.
- Workflows' subtitle opens with "A warehouse for one:".
- Agents needed no change, since it never used "Lakelet Lookahead".

## 5. Research and marketing (W12)

- `research/README.md` gains four rows: Okanovic, Hasan, Murphy and Gupta. Each has its date, what it changes, and which numbers are not used.
- `marketing/landing-page.md` gains a status line. It says the page is built, that the PR #1 precondition is resolved, and records the two places the build differs from it: the diagram's position and the section numbering.

## 6. What the tests showed

- **Baseline:** 25 pages, 66 passed, README current.
- **After:** 25 pages. **92 passed** at `/lakelet/` and **92 passed** at `SITE_BASE=/`. `gen-readme-status.py --check` is current.
- **Browser** (Playwright from `app/node_modules`, against `astro preview`):
  - no horizontal overflow at 1440, 390 or 360 px on home, pricing, app, how-it-runs, workflows, agents and `docs/gauge`
  - the demo's six states: Runs here, Runs here slowly, Runs here, Runs here slowly, Runs here slowly, Needs more machine
  - arrow keys move the question
  - no console errors
- **One false alarm:** "Skip to content" showed in one section capture at 390 px. The link measures at top −100 px with nothing focused, so it was the capture tool, not the page.

## 7. Open

- **Hants' review of the branch,** then commit (DCO), merge and deploy. All three are his calls.
- **`pricing.ts` still holds unrendered plan data** that the page's rules would reject if it were ever shown: Local's feature list naming ask-in-English and MCP, Team's "compaction", and the vendor comparison with burst arithmetic. It is not deleted, because W9 named only `foot:`. It is a candidate for the next clean-up.
- **How it runs** still ends on "Bursting is the next part of the story". It is marked planned, and it is out of W's scope.
- **`lakelet init --help`** says "Turn a folder into a lakehouse". The CLI reference is generated from it, so the word changes in the core, not on the site.
- **`/explore` stays** (W13).
