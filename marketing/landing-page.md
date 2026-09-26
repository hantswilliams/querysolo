# The landing page, rebuilt around "a warehouse for one"

*A plan, not a build · 2026-09-24 · The site is `web/`, Astro, in the dark/lime direction chosen 2026-09-16 and redesigned around Lookahead in PR #1, which is open for Hants' review. This plan builds on that page: it changes the headline, the category word and the order of sections, and keeps the interactive demo, the diagram, the folder section and the generated status block. Nothing here is applied until the plan is agreed.*

## The page in one breath

Hero · Know what fits · Know what changed · Nothing leaves, any engine reads · Not an editor, not a cloud warehouse · Three doors · For one, then for a team · Built and planned · Get it.

The order is the argument: the verdict first because it is the one thing nobody has; the record second because it is what makes the verdict trustworthy; trust third because it is what lets the reader install; how it fits fourth because by then they want to know where it sits; the doors fifth because by then they want to start; the boundary sixth because an honest page says it before the pricing page does.

## The sections

Each: the headline, the copy's job, what is shown, who it is written for (internal, per `personas/`), and the built-or-planned marks.

### 0. Navigation

Unchanged: How it runs · App · Docs · Pricing · GitHub. The hero chip changes from "Local lakehouse / Open source / Developer preview" to **"A warehouse for one / Open source / Developer preview"**.

### 1. Hero

**Headline:** A warehouse for one.
**Subtitle:** the one-liner from `warehouse-for-one.md` §2.
**Under it, quieter:** the "next" line.
**Call to action:** "Get it from source" with "macOS and Linux · no account" beside it; becomes "Download" when the signed installer ships (`ship-v0-plan.md`).
**Shown:** the real window, the verdict and its sentence above the first rows (`docs/screenshots/query-verdict.png`, retaken by `app/scripts/screenshots.mjs`).
**For:** everyone; the solo analyst first, because the first ten minutes are their whole product.
**Marks:** every clause built.

### 2. Know what fits

**Headline:** Before you run it, know.
**Job:** show the verdict as a decision with a sentence, not a colour. The four verdicts by name, each with an example sentence. The fair comparison in one line: *BigQuery shows the bytes. This shows the minutes, and refuses.*
**Shown:** the interactive Lookahead demo the site already has: six scenarios, the slider, local or S3, the assumptions. It is the strongest asset on the site and stays.
**For:** every persona; the platform analyst's comparison sentence lives here; the agent's "cost before the run" too.
**Marks:** built. When the fact-and-forecast split lands (E1 in the session log), this section gains one sentence: *the bytes and the files are a fact from the manifests; the seconds are a forecast, and it says how sure.*

### 3. Know what changed

**Headline:** After it runs, know what changed.
**Job:** the record, and the one sentence nobody else can write: a change to the data counts. Every model knows whether it is fresh, edited, out of date or never built; a table's new snapshot marks everything that reads it stale, because the tables and the models share one catalog; run only what is stale does exactly that; every run is recorded against its estimate; the Changes feed puts the data's snapshots, the models' runs and the code's commits in one list. The fair comparison in one line: *dbt sees a changed model. Renart sees a changed file. This also sees changed data.* Then the on-ramp, so there is something to keep track of, in two sentences, one per reader: *A question you keep becomes a model with two checks and a version. If you have never used dbt, you just did.* and *If you have, the model you wrote gets a verdict, its checks, a version and a state, without leaving your editor.* The second sentence is the line drawn on 2026-09-24: the product runs and remembers; the editor writes. Saving is not the headline, because saving is not unique.
**Shown:** the Changes screen, then a model's state and its Review diff, then the Models screen in Simple mode.
**For:** the dbt person and the solo analyst, in that order.
**Marks:** built.

### 4. Nothing leaves. Any engine reads.

**Headline:** Your machine. Your bucket. Your tables.
**Job:** the measured zero, `PRIVACY.md` in a sentence, the scope of "nothing leaves" in the same paragraph, then the open format: Parquet and Iceberg in a folder or in your bucket, read by Spark, Trino, pyiceberg, BigQuery and Databricks as they are.
**Shown:** the existing "The files are yours" folder tree (`warehouse/`, `models/`, `.lakelet/`, `.git/`, `lakelet.toml`) moves here from the bottom of the page.
**For:** the consultant and the researcher (the zero), the dbt person and the platform analyst (any engine).
**Marks:** built; S3 only, and the page says "your bucket" without naming a second provider.

### 5. Not an editor. Not a cloud warehouse.

**Headline:** unchanged from the current "How it fits" section: *Beside your editor. Under your SQL.*
**Job:** the current section, tightened to three sentences: your editor writes it; the product runs it, keeps the tables, and shows what happened; every button shows the command it is. The current "warehouse you don't need BigQuery for" paragraph shortens to its last clause, that nothing moves when a table outgrows the laptop.
**For:** the dbt person and the data scientist.
**Marks:** built.

### 6. Three doors

**Headline:** Start with what you have.
**Job:** three cards, no persona words. *A file*: drop it, a table in seconds, the types written down (built). *A bucket*: point at the Parquet, nothing copied, public data needs no credentials (built, S3). *A warehouse you do not own*: pull a slice onto the laptop, refreshable, and let the verdict say what fits here (planned, marked as such on the card, `decisions-for-review_092426.md` N2). Each card links to its docs page.
**For:** the three analyst-shaped personas; this is where the page routes readers without naming them.
**Marks:** two built, one planned and marked.

### 7. For one, then for a team

**Headline:** For one, today.
**Job:** the honest paragraph the dbt person would otherwise write themselves after an hour: one machine, one writer, one folder; no users, no permissions, nothing that runs unattended. Then what "for a team" will mean, one catalog over one bucket with one history, and that it is planned. Link to pricing, where the Team card is "proposed". This is where "solo today" is said in those words (N1).
**Shown:** nothing; text.
**For:** the dbt person; the learner reads it as "free, mine, no card".
**Marks:** the boundary is a fact; the team sentence is planned and says so.

### 8. Built and planned

The generated status block, unchanged (`web/src/data/status.ts`, `gen-readme-status.py`). It is the page's proof that the marks above are honest.

### 9. Get it

From source today, with the ten-minute quickstart; the waitlist (Formspree, live); the installer line when it ships. The learner's CTA is the quickstart; the data scientist's is PyPI, which does not exist yet and is not promised on the page.

## What changes from the site as it is

| Now | After |
|---|---|
| Headline "Your data, near or far. Know what fits." | "A warehouse for one." |
| Chip "Local lakehouse" | "A warehouse for one" |
| "lakehouse" as the category, on the landing page and the App page | "warehouse" with its scope in the same sentence; "lakehouse" survives only in docs where it names the format lineage |
| "Lakelet Lookahead" | "Lookahead", the gauge's own name, so the rename does not cascade |
| The folder section last | the folder section fourth, as the trust beat |
| "How it fits" fourth | fifth, tightened |
| No routing section | "Three doors", the N2 doors as cards, one marked planned |
| Pricing: Local · Team (proposed) · Burst (proposed) | "For one" (free, today) · "For a team" (proposed) · Burst under it (proposed); an "Agents" card only if B2 in the session log is agreed |
| Medallion page | kept; its subtitle gains "for one" |
| Agents page | kept; the budget stays marked planned |
| How it runs | kept |

## What the page must not do

- Say team, shared, collaborate or burst as a feature, or show a burst number.
- Name a persona. The doors and the two sentences in §3 do the routing.
- Lead with DuckDB, Iceberg or dbt. They appear in the "built on" line under the hero and in §4 as the format any engine reads.
- Promise Windows, PyPI or the installer before they exist. "Get it from source" until then.
- Compound the product name with a feature name anywhere.

## Checks before it ships

- The site's pytest checks (66 at the last count) updated for the new headline and chip; every route still 200.
- Every feature sentence traced to `status.ts`; the status block regenerated; the README's lede changed in the same commit so the two never disagree.
- Desktop and 390px review, per `website-story-v1-plan.md`'s routine.
- The screenshots retaken if the app's chrome changed since 2026-09-22.
- PR #1's review resolved first, so this is a second pass on the merged page, not a fork of an unmerged one.
