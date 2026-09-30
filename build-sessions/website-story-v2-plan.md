# Website v2: a warehouse for one — September 26, 2026

*A plan, not a build. It takes `marketing/landing-page.md` (2026-09-24) and turns it into build steps for `web/`, after a review of `marketing/`, `personas/` and `research/`. It follows `website-story-v1-plan.md`: the dark/lime design and the Lookahead demo stay; this pass changes the words, the category, and the order of the home page. Nothing is built until the boxes below are ticked. Product name: Lakelet (working name). The site keeps "Lakelet" until S7 decides the name. TBD\* is used only in planning files.*

## What the review found

- **The precondition in `landing-page.md` is already met.** It says to wait until "PR #1's review [is] resolved first". PR #1 was merged on 2026-09-18, and `main` has had site commits since then (`da6a417`, "How Lakelet fits"). The plan builds on `main` as it is.
- **The site still describes the old category.** The home hero says "Your data, near or far. Know what fits." and the chip says "Local lakehouse". "Lakehouse" also appears in `Footer.astro` ("A little lakehouse."), `nav.ts` `site.tagline`, `public/llms.txt`, and in "A lakehouse. In a folder." on the home page. "Lakelet Lookahead" appears in 7 files, including `status.ts`, and that label feeds the README's generated status block.
- **Beat 2, "Know what changed", has no section on the home page.** Lineage, Changes, `run --stale` and the per-model state are built (L1–L3, 2026-09-18). Today the home page only reaches them through "Keep a useful answer", which is the saving line that the 09-24 session ruled was not unique.
- **The home page already makes a claim the marketing rules forbid.** Its "How it fits" says "Most teams' data fits on one machine". That is unmeasured, and "team" is on the banned list. The burst paragraph beside it is marked planned, but it reads as a feature.
- **`pricing.ts` has `foot:` strings that nothing renders.** One says `brew install lakelet` (not built), one says "cents to a few dollars" (a burst number), and one says "you have a lakehouse". They are dead code, but they are wrong enough that a future edit could put them on the page.
- **The Team pricing card lists "Compaction and alerts".** The 09-24 session's open box B3 says maintenance should be free and local. The page should not decide that on its own (decision W9).
- **`research/`** has eight PDFs. Its README lists four. Three of the other four are summarised in `lakelet-build-sessions_092426b.md` §1; the fourth (Gupta, Direct Lake, about 2026-09-24) is summarised nowhere. What they mean for the page:
  - *Hasan* (200 appends; pyiceberg SqlCatalog on SQLite, DuckDB 1.5.5, so our stack) is the objection a technical reader will bring. The page must not say or imply "no maintenance". It can say that `expire` exists. Compaction is not built.
  - *Okanovic* supplies the answer to "why Iceberg": the tables outlive the tool, and a commit is one pointer swap. Her table labels a SQLite-backed *DuckLake* as "local dev only", and a reader may apply that to us. That is one more reason to say "one writer" first.
  - *Murphy* (Duckle) answers "how is this different from Duckle". It is already a row in `warehouse-for-one.md` §7. No connector-count race.
  - *Gupta* (Direct Lake) gives a framing, not a number: the pain is the silent fallback, and the verdict is the opposite of silent. His "800 ms → 25 s" has no source and is not used.
- **The personas** are all assumed, none observed. `personas-fit.md` already maps each one to a section and a door, and this plan follows it. The personas make three demands the page cannot meet with words: the installer, Windows, and PyPI. They stay off the page.
- **N1 and N2** (`decisions-for-review_092426.md`) are the basis for "written for the solo analyst first" and for "three doors". Their boxes are still unticked. N3 was taken on 09-24.
- **Out of scope:** `hants_ideas.md` (app onboarding, provisioning, app layout, and matching the app's colours to the site). These belong to the app, not the page. The name (`marketing/names.md`) waits for S7.

## Review decisions

Each decision has a recommendation, the reason, and where it lands. The body below assumes the recommendation, so a Change is a targeted revert.

**W1. Build on `main` in a separate worktree (`web/warehouse-for-one`, off `origin/main`), not in the main checkout.**
Why: the main checkout has uncommitted ship-round work in `core/` and `app/`. v1 used a worktree for the same reason. Committing and pushing stay your call.
Lands: step 0.
- [x] Agree
- [ ] Change:

**W2. Treat N1 and N2 as agreed for copy only.** The page is written for the solo analyst first, and the three doors appear, with the third marked planned. Nothing in `core/` or `app/` follows from this.
Why: the page depends on both. Neither decision changes the ship order.
Lands: steps 3 and 4. If you Change: drop the doors section and keep the order.
- [x] Agree
- [ ] Change:

**W3. The hero changes.**
- Headline: *A warehouse for one.*
- Subtitle: the one-liner from `warehouse-for-one.md` §2, with "Lakelet" in place of TBD\*.
- Under it, quieter: *Know what fits. Know what changed.*, then the "next" line.
- Chip: *A warehouse for one / Open source / Developer preview*.
- The call to action stays "Try Lakelet from source".

Why: this is the positioning from 09-24. Every clause of the one-liner is built.
Lands: step 3.
- [x] Agree
- [ ] Change:

**W4. "Lakelet Lookahead" becomes "Lookahead" everywhere on the site.** That covers the pages, `status.ts`'s label, `/docs/gauge` and the demo. The README status block is regenerated in the same commit.
Why: the product name should not be compounded with a feature, so a rename does not cascade. CI checks that the README and `status.ts` agree.
Lands: step 2.
- [x] Agree
- [ ] Change:

**W5. "Lakehouse" leaves the marketing pages, the footer, `site.tagline` and `llms.txt`.** It stays in docs only where it names the format lineage. The README's lede changes to the one-liner in the same commit. The README's "How it fits" paragraph loses "the size most teams actually have".
Why: `landing-page.md`'s own check says the README and the site must never disagree. That touches one file outside `web/`.
Lands: step 2. If you Change: do the site only and leave the README for the ship round.
- [x] Agree
- [ ] Change:

**W6. The home page is reordered to the three beats.** The final order:
1. Hero
2. Know what fits
3. Know what changed
4. Your machine, your bucket, your tables
5. Beside your editor
6. Start with what you have
7. For one, today
8. Built and planned
9. Get it

The **storage/compute diagram (`DataFlow`) moves from before the demo into section 4**, beside the folder tree. The "03 / The idea" three-column block is removed. Its three links reappear in sections 2, 3 and 6.
Why: the order is the argument (`landing-page.md`). The diagram is the storage story, not the opener. "The idea" duplicates beats 1 and 3 and carries the saving line.
Lands: step 3.
- [x] Agree
- [ ] Change:

**W7. A new "Know what changed" section, with the Changes, Lineage and Questions screenshots already in `public/screenshots/`.**
- Headline: *After it runs, know what changed.*
- The fair line: *dbt sees a changed model. Renart sees a changed file. This also sees changed data.*
- Two on-ramp sentences, one per reader, from `landing-page.md` §3.

Why: this is the beat nobody else can write, and it is built. The screenshots exist (09-22), so no retake is needed.
Lands: step 3.
- [x] Agree
- [ ] Change:

**W8. "How it fits" is tightened to three sentences.**
- *Your editor writes it; Lakelet runs it, keeps the tables and shows what happened; every button shows the command it is.*
- "Most teams' data fits on one machine" is removed.
- The three-moves paragraph keeps "point an engine you already pay for at the same tables". Burst moves to the "next" line only.

Why: "team" and burst as a feature are both on the banned list, and the "most teams" figure was never measured.
Lands: step 3.
- [x] Agree
- [ ] Change:

**W9. Pricing: "For one" (free, today) · "For a team" (proposed) · "Burst" (proposed, under it).** No Agents card (B2 undecided). "Compaction" leaves the Team card's list until B3 is decided. The dead `foot:` strings in `pricing.ts` are deleted.
Why: until B3 is decided, the page should not sell as paid something the marketing notes say should be free. The `foot:` strings contain two claims that are not true.
Lands: step 4. If you Change: keep Compaction on Team and B3 is decided the other way.
- [x] Agree
- [ ] Change:

**W10. Research-led lines.**
- (a) Section 2 gains one sentence in Gupta's framing without naming him: *No silent fallback: when it will not fit, it says so before it starts.*
- (b) Section 4 gains one sentence on why Iceberg: *Iceberg, so the tables outlive the tool.*
- (c) No "maintenance-free", "no upkeep", or compaction claim anywhere. The recovery link mentions `expire`.

Why: these are the two objections a technical reader brings from this month's reading, and the one claim Hasan's numbers would disprove.
Lands: step 3. Each part can be Changed separately.
- [x] Agree
- [ ] Change:

**W11. Add a planned `slice` surface to `status.ts`.** Label: *A slice of a warehouse you do not own*, `session: 'N2, after the outsider sessions'`. The third door card reads its state from there.
Why: the site's rule is that a page naming an unbuilt thing reads `status.ts`. That also adds a planned row to the README's status block.
Lands: step 4.
- [x] Agree
- [ ] Change:

**W12. `research/README.md` gains the four missing rows.** They are dated, each with what it changes, and link to this plan and the 09-24 log (no decisions file exists for them).
Why: the folder's own rule. The PDFs stay gitignored.
Lands: step 5.
- [x] Agree
- [ ] Change:

**W13. The `/explore` concept routes stay as they are** (noindex, out of the sitemap).
Why: removing them is housekeeping, not this pass. Flagged for a later clean-up.
Lands: nowhere.
- [x] Agree
- [ ] Change: remove them in step 4

## Scope

Four pages change:
- **Home** (`index.astro`) is rewritten and reordered.
- **Pricing** is relabelled.
- **App and How it runs** get the Lookahead rename and have "lakehouse" removed.
- **Workflows** (`medallion.astro`) gets "for one" in its subtitle and the Lookahead rename.

**Agents** gets the rename only, and its budget stays planned.

Supporting files change too: the data files (`nav.ts`, `status.ts`, `pricing.ts`), the footer, `llms.txt`, `/docs/gauge`, the README's lede and its regenerated status block, and `research/README.md`.

- No new components unless one is needed for the three door cards. If it is, it follows `VendorCard.astro`'s pattern.
- No design changes, no new screenshots, no `core/` or `app/` changes.

**Section by section,** each with where its copy comes from:

| # | Section | Copy from | Shows | Built / planned |
|---|---|---|---|---|
| 1 | Hero | `warehouse-for-one.md` §2 | chip, one-liner, two beats, next line, CTA | built; the next line is planned and says so |
| 2 | Know what fits | `landing-page.md` §2, W10a | `LookaheadDemo` (unchanged), the four verdicts by name, *BigQuery shows the bytes. This shows the minutes, and refuses.* | built |
| 3 | Know what changed | `landing-page.md` §3, W7 | changes.png, lineage.png, questions.png | built |
| 4 | Your machine. Your bucket. Your tables. | `landing-page.md` §4, W10b | `DataFlow` (moved), the folder tree (moved), zero outbound attempts measured by `lakelet audit network`, the scope of "nothing leaves" from `PRIVACY.md` | built; remote compute planned, as the diagram already marks |
| 5 | Beside your editor. Under your SQL. | W8 | text, and `AppCapture` | built |
| 6 | Start with what you have | `landing-page.md` §6 | three cards: a file, a bucket, a warehouse you do not own | two built, one planned via `status.ts` |
| 7 | For one, today | `landing-page.md` §7 | text: one machine, one writer, one folder; the team sentence planned; a link to pricing | fact; the team sentence is planned |
| 8 | Built and planned | unchanged | `CurrentState` | generated |
| 9 | Get it | unchanged | `NextStep` and the waitlist | built |

**Words that must not appear on marketing routes:** lakehouse, local-first, Lakelet Lookahead, team or collaborate as a feature, burst as a feature, production-ready, Windows, seamless, blazing, AI-powered. See `warehouse-for-one.md` §5.

## Gate

- **A test first** (`web/tests/test_website.py`, new functions):
  - The home page has "A warehouse for one" in the `h1` and in the chip.
  - No marketing route (every route except `/docs/*` and `/explore/*`) contains "lakehouse" or "Lakelet Lookahead".
  - The banned words above are absent from the home, app and pricing pages.
  - The home page's sections appear in W6's order, checked by their headings.
  - The third door card carries the planned marker.
  - `pricing.ts` has no `brew install` string.

  These fail before step 2 and pass after step 4.
- **The production build** passes. The page count is unchanged from the baseline recorded in step 0. Every route returns 200.
- **All existing site checks pass** at `/lakelet/` and at `/`.
- **`gen-readme-status.py --check`** (the CI job) passes after the README is regenerated.
- **Browser review:**
  - desktop, 390px and 360px, with no horizontal overflow
  - the Lookahead demo's six states and its keyboard slider still work
  - `DataFlow` still reads correctly in its new position
  - no console errors
- **A dated session log** and both task lists are updated.

## Implementation order

0. Create the worktree off `origin/main`, run `npm ci`, build, and run `uv run pytest` in `web/`. Record the baseline counts (pages, checks). → verify: green on the baseline.
1. Write the gate tests. → verify: they fail for the right reasons.
2. The vocabulary pass (W4, W5): the Lookahead rename, removing "lakehouse", the README lede, the status block regenerated. → verify: the rename and vocabulary tests pass, and the README check is green.
3. Rewrite and reorder the home page (W3, W6, W7, W8, W10). → verify: the order and hero tests pass; build; browser pass on the home page.
4. Pricing (W9), the `slice` surface and door cards (W11), and the subtitles on App, Workflows and Agents. → verify: every gate test passes.
5. The rows in `research/README.md` (W12). A status line at the top of `marketing/landing-page.md`: "built by `website-story-v2-plan.md` on <date>", and its stale PR #1 precondition marked resolved. → verify: the files read correctly.
6. Full gate, the session log, both task lists. Stop for your review before any commit, push or deploy.

## Gate results

*2026-09-26, on branch `web/warehouse-for-one` in `../lakelet-warehouse-for-one`, off local `main` at `eaca640` (not `origin/main`: local `main` was two commits ahead and held this plan). Detail in `lakelet-build-sessions_092626.md`.*

- [x] Baseline recorded: 25 pages, 66 checks, README check current.
- [x] Gate tests written, failing: 26 new checks failed on the baseline, for the reasons expected.
- [x] Vocabulary pass; README check green.
- [x] Home page rebuilt.
- [x] Pricing, doors, sub-pages.
- [x] Research rows; landing-page.md status line.
- [x] Build 25 pages; 92 checks pass at `/lakelet/` and at `/`; browser review at 1440, 390 and 360 px; session log.
- [ ] Your review before merging or deploying.
