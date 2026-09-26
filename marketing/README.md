# Marketing

The words for the product, kept beside the code so they are held to the same rule as the site: say what is built, mark what is planned, and never a number that was not measured. Started 2026-09-24 from the positioning conversation (`build-sessions/lakelet-build-sessions_092426b.md`), after the six personas in `personas/`. `brand/` (gitignored) holds the marks and assets; this folder holds words and is in git.

## Files

| File | What it is |
|---|---|
| `warehouse-for-one.md` | The concept: what the phrase says, the one-liner, the tagline, the three beats, the vocabulary, the voice, the comparisons we make and the claims we do not |
| `landing-page.md` | The landing page rebuilt around the label: the sections in order, each with its headline, its job, what it shows, who it is for; what changes from the site as it is; what the page must not do |
| `personas-fit.md` | The label against the six personas: the sentence each hears, the section written for them, the feature that wins, the wall we disclose, the door they walk through |
| `guidebook.md` | The deck's source: fourteen slides that summarise the three files above, one screen each, in a small markdown format the renderer reads |
| `build_guidebook.py` | Renders `guidebook.md` to `warehouse-for-one-guidebook.pptx` in the site's dark/lime palette: `uv run --no-project --with python-pptx python marketing/build_guidebook.py` |
| `warehouse-for-one-guidebook.pptx` | Generated, gitignored like `deck/`; rebuild it after editing the markdown |
| `names.md` | Name candidates against the test, with PyPI, `.com`, `.dev` and `.io` checked on 2026-09-24 and the known collisions; ranked; no trademark search yet |

## Rules for every file here

- **`web/src/data/status.ts` is the authority on built and planned.** A sentence that names a feature is checked there. A planned feature is on the "next" line, never in a feature sentence.
- **The product name is a token.** Lakelet is the working name; TBD\* marks where the final name goes (decided in the ship brief's S7 window). Copy never compounds the name with a feature: the gauge is "the verdict" or "Lookahead", not "Lakelet Lookahead", so a rename does not cascade.
- **Numbers come from `docs/facts-and-messaging.md` or a dated measurement in a session log.** Market sizes and unverified figures stay out, per `research/README.md`. A burst number is arithmetic from a plan and is not used.
- **"Nothing leaves your machine" is scoped exactly as `PRIVACY.md` scopes it:** the one extension download at `init`, and the buckets and bursts you ask for.
- **Comparisons are fair.** BigQuery shows bytes before a run. The sandbox is free and real. MotherDuck is DuckDB in the cloud. We say what they do, and what we do that they do not.
- **Personas are internal.** The page never says "analyst" or "dbt person"; it offers doors (a file, a bucket, a warehouse you do not own) and lets the reader pick.
- **"Team", "shared", "collaborate" and "burst" do not appear as features** until the catalog round and the worker exist (`decisions-for-review_092426.md` N1).
