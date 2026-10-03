# The QuerySolo site

Live at <https://hantswilliams.github.io/querysolo/>. Running state and what is
deliberately not done yet: **`TASKS.md` in this folder**.

Static site built with [Astro](https://astro.build). Zero client-side framework; small scripts handle the data-story controls, mobile documentation navigation, and configured signup forms.

```
npm install
npm run dev        # http://localhost:4321/querysolo/   (the base path production uses)
npm run build      # -> dist/
npm run preview
```

## Data-story website (this branch)

Branch `codex/website-exploration` is developed in the separate sibling worktree
`/Users/hants/Development/Python/querysolo-website-exploration`. The selected concept,
02 / Data story, now covers the complete website: home, app, how it runs, workflows,
agent interfaces, pricing, and all developer documentation. This branch is shared
for review; integration and deployment remain separate.

```sh
npm run build
npm run preview -- --host 127.0.0.1 --port 4328
# Open http://127.0.0.1:4328/querysolo/
```

Run the website gates after building, using a Python environment with the core dependencies and pytest available:

```sh
python -m pytest tests -p no:cacheprovider
```

The existing core Python environment can run these checks. The tests cover every
page's landmarks, navigation, local links, fragments, assets, feature availability,
interactive markup, docs, and signup states. For a root-domain build, set
`SITE_BASE=/` for both the build and pytest. Set `PUBLIC_WAITLIST_URL` for both
when checking the configured form; otherwise the pricing page offers GitHub updates.

Original study routes remain at `/querysolo/explore` and its `/product`, `/story`, and
`/editorial` children. They are excluded from the sitemap and carry noindex. The real
site uses `Base.astro`, the selected theme, and `website.css`; the study keeps its
own layout. `DataStory.astro` retains the measured Overture transfer demonstration on
how-it-runs and concept 02. The homepage uses `LookaheadDemo.astro`: three questions,
local/S3 choices, the data flow, memory/spill, time, and a verdict.

Remote `main` at `d0f1324` was merged into this branch on September 18. Product
documentation and status include S3 writes, publishing, Lineage, and Changes. Core
and desktop-app source match that committed main version. Screenshot provenance
is in `public/exploration/README.md`. Scope and gates are in
`../build-sessions/website-story-v1-plan.md`; results are in the dated session log.

## Homepage Lookahead scenarios

These are illustrative model outputs, not measured query runs or visitor-machine
benchmarks. `scripts/generate_lookahead.py` defines three synthetic operator plans,
assumed table statistics, and one explicit laptop profile. It calls the existing core
estimator for local and S3 storage, and exports six results as TypeScript constants.
No query executes and no data is fetched when a visitor changes the controls.

With the core's Python dependencies available, run from `web/`:

```sh
python -B scripts/generate_lookahead.py --write  # regenerate after changing inputs
python -B scripts/generate_lookahead.py          # verify against the current model
python -B -m pytest tests -p no:cacheprovider
```

The model checks ensure location changes read time, but not bytes or peak memory;
that the examples cover both disk spill and a slow remote transfer; and that exported
values remain consistent with the core. Browser review covers all six selections,
keyboard radio controls, responsive layout, and the setup disclosure. The original
Overture experiment remains available on `/how-it-runs` for comparison.

## Layout

```
src/
  layouts/Base.astro       metadata, selected dark theme, Nav, Footer, signup handler
  components/              Nav, Footer, Logo, Fish, Waitlist, Terminal, ReplayTerminal,
                           GaugeSlider, Verdicts, CompareBars, VendorCard, WorkerLadder
  data/
    nav.ts                 nav items, CTA, footer text, "what do you use today" options
    pricing.ts             every number with a dollar sign: plans, worker ladder, modeled month
    facts.ts               the dated facts the pages cite
    status.ts              what is built and what is planned -- the ONE place; drives <BuildState/>
    demo.ts                measured Overture numbers for the original transfer demo
    lookahead.ts           homepage scenario labels and display formatting
    lookahead-estimates.ts generated illustrative estimates from the core gauge model
  styles/tokens.css        global tokens and shared primitives (page-specific CSS lives in each page)
  pages/                   index, app, how-it-runs, medallion, agents, pricing
public/                    favicon.svg, llms.txt   (robots.txt is generated: src/pages/robots.txt.ts)
functions/api/waitlist.ts  Cloudflare Pages Function that stores signups in KV
```

Clean URLs: `build.format = 'file'` emits `dist/pricing.html`, which every static host serves at `/pricing`.

## Changing things

- **A price, a vendor number, a worker size** → `src/data/pricing.ts`. The landing page bars, the pricing page cards and the size ladder all read from it.
- **Nav / footer / CTA text** → `src/data/nav.ts`.
- **A terminal transcript** → the `<pre>` inside the page; colour classes are `.p .w .g .y .r .b .o .d .k` (see `Terminal.astro`).
- **The looping demo** → `src/components/ReplayTerminal.astro` (lines are `<span class="ln ...">`; `cmd` lines are typed, `data-input="y"` pauses then types the answer).
- **Domain** → `site` in `astro.config.mjs` (drives canonical URLs, robots.txt and the sitemap); the GitHub Pages workflow overrides it via `SITE_URL` / `SITE_BASE`. The default is the GitHub Pages URL, which is where the site actually is; do not default it to a domain nobody owns.
- **"Built / planned" anywhere on the site** → `src/data/status.ts`, and every page follows. Never hand-write a build state into a page.
- **The Overture demo numbers** → `src/data/demo.ts`, which must agree with `src/content/docs/remote.md`.
- **Internal links** → always `href={url('/path')}` (from `src/lib/url.ts`) so they work under a base path.

## Deploy (GitHub Pages)

The workflow at `.github/workflows/deploy-pages.yml` (repo root) builds `web/` and publishes it on every push to `main` that touches the site.

1. In the repo: **Settings → Pages → Build and deployment → Source: GitHub Actions**. That's the only required step. The next push to `main` (or **Actions → Deploy site to GitHub Pages → Run workflow**) deploys to `https://hantswilliams.github.io/querysolo/`.
2. Links, CSS, favicon and the sitemap are all base-aware (`src/lib/url.ts`, `SITE_BASE`), so the subpath works without code changes. Always write internal links as `href={url('/pricing')}`, never `href="/pricing"`.
3. Custom domain (optional): add it under **Settings → Pages → Custom domain** (GitHub writes the `CNAME` file and handles HTTPS), point DNS at GitHub (`A` records to GitHub's Pages IPs, or a `CNAME` to `hantswilliams.github.io`), then add a repo **variable** `SITE_URL=https://querysolo.dev`. The workflow then builds with base `/` and the sitemap uses the real domain.
4. **Waitlist (required for the forms to capture anything).** GitHub Pages is static only, so `functions/api/waitlist.ts` doesn't run there. The form exists: add a repo variable `PUBLIC_WAITLIST_URL=https://formspree.io/f/meaqdnjv` (**Settings → Secrets and variables → Actions → Variables**). A form id is not a secret — Astro inlines every `PUBLIC_` variable into the browser bundle — so it is a variable, not a secret, and it lives in `.env.example` too. Any endpoint accepting a `multipart/form-data` POST with `email` and `stack` works. Without it the forms tell visitors that signups aren't open and point at the repo — they do **not** show the success state, because that silently discarded every signup between 2026-09-09 and 2026-09-11. The build prints a warning when the variable is missing.

The defaults in `astro.config.mjs` already are the GitHub Pages ones (`site` = `https://hantswilliams.github.io`, `base` = `/querysolo/`), so a plain `npm run build` is the production build and a plain `npm run dev` has the production base path. That is deliberate: a base-path bug should show up on the first local page load, not on the first deploy. To preview as a root-domain site: `SITE_URL=https://example.com SITE_BASE=/ npm run build`.

## Deploy (Cloudflare Pages)

1. Push this folder to a repo; in Cloudflare Pages create a project from it.
   Build command `npm run build`, output directory `dist`, root directory `web` (if the repo root is the parent).
2. Waitlist: create a KV namespace, bind it to the Pages project as `WAITLIST`, and set the build env var `PUBLIC_WAITLIST_URL=/api/waitlist`. Without the env var the forms say signups aren't open (they never fake success).
3. Read signups: `npx wrangler kv key list --binding WAITLIST --remote`.

Any other static host (Netlify, Vercel, GitHub Pages) serves `dist/` as-is; point `PUBLIC_WAITLIST_URL` at Formspree/Buttondown/your own endpoint instead — see the comment in `Base.astro`.
