# The QuerySolo mark on the site and in the app — September 30, 2026

*A plan, not a build. The rename (`rename-querysolo-plan.md`) changed every word, but left the art as it was (R9). Lakelet's wave-and-fish mark is still in the site header, the favicon, the app's own window and the app icon, and the app screenshots on the site show the old name in the app's top bar. This round replaces the art and retakes the screenshots. Since the rename: `querysolo` 0.0.0 is on PyPI, and Hants built the DMG under the new name.*

## Where the old mark is

| Place | File | What it shows today |
|---|---|---|
| Site header | `web/src/components/Brand.astro` | wave-and-fish + "querysolo" |
| Site wordmark (unused on live pages) | `web/src/components/Logo.astro` | fish + wordmark |
| Design-study header | `web/src/components/exploration/Wordmark.astro` | wave-and-fish |
| Favicon | `web/public/favicon.svg` | the app icon's master: deep green tile, lime wave and fish |
| The app's window | `app/src/App.tsx` | the wave-and-fish in the sidebar header |
| App icon masters | `app/src-tauri/icons/src/querysolo-{mac,linux}.svg` | the same mark; every size (`icon.icns`, `icon.ico`, the PNGs, `linux/`) is generated from these |
| Screenshots | `web/public/screenshots/*.png`, `docs/screenshots/query-verdict.png` | the old name and mark in the app's top bar |

## Review decisions

Each decision has a recommendation, the reason, and where it lands. The body assumes the recommendation.

**L1. Commit the rename on its branch first.**
The rename is 309 staged changes on `rename/querysolo`. Commit it as one signed-off commit, then do this round as a second commit on the same branch.
Why: a rename should be reviewable as a rename, and the art as art. Two commits keep them apart in one pull request.
- [x] Agree
- [ ] Change:

**L2. The mark is the prompt, direction C: `>_` with a lime cursor.**
This is the mark on `brand/querysolo-logos-mosaic.html` and `/explore/querysolo`.
- **App icon:** the deep-green tile with the prompt in off-white and the cursor in lime, on the Big Sur canvas for macOS and full-bleed for Linux, the way the masters are drawn today.
- **Favicon:** the same tile.
- **Site header and the app's window:** the bare mark in `currentColor` beside "query**solo**".

Why: it's the mark you chose for the brand page, it reads at 16 px, and it says "command line" and "one query". The gauge-Q directions stay in `brand/` as an alternative for later.
- [x] Agree
- [ ] Change:

**L3. The wordmark is lowercase `querysolo` with "solo" in the accent colour, in every header.**
The accent is lime on dark and deep green on light. In running text, the name is QuerySolo.
Why: the casing recommended on `querysolo-logos.html`, and the one the command uses.
- [x] Agree
- [ ] Change:

**L4. Art only, not a redesign of the home page.**
The live pages keep the v2 layout; only the mark and wordmark change. `/explore/querysolo` stays a study. Adopting its brick hero and look for the home page would be a design round of its own.
Why: a small, reviewable change now. The bigger visual question deserves its own look.
- [x] Agree
- [ ] Change: make `/explore/querysolo` the home page in this round

**L5. Retake every screenshot with `app/scripts/screenshots.mjs`.**
That's the real app in its browser harness against a real sidecar on the generated sample data, so they show the new name and mark. The provenance notes stay accurate, with a new date.
Why: the site and README otherwise show a product called Lakelet.
- [x] Agree
- [ ] Change:

**L6. Remove the unused `Logo.astro`, or leave it.**
It's referenced nowhere on the built site. Recommend: redraw it with the new mark rather than delete it, since removing unused code is a separate decision (`claude/karpathy.md`).
- [x] Agree
- [ ] Change: delete it

## Gate

- **Site:** it builds; its pytest passes at `/querysolo/` and at `/`; a browser review at 1440 and 390 px shows the new mark in the header and the favicon.
- **App:** Vitest and `tsc` pass, and `cargo test` passes. The icon set is regenerated from the new masters, with the same six files the config names. `npm run tauri build` makes a `.app` whose Dock icon is the prompt (on your Mac).
- **Screenshots:** retaken. The `/app` gallery and the app guide still show every screen (the site tests count them).
- **Records:** a session log and the task lists are updated.

## Implementation order

0. Commit the rename (L1).
1. The mark as SVG: the icon masters (mac and linux), the favicon, and the header and window marks from one set of paths. → verify: side by side at 16, 32, 64, 128 and 1024 px.
2. Site: `Brand.astro`, `Wordmark.astro`, `Logo.astro`, the favicon. → verify: build, tests, browser review.
3. App: the mark in `App.tsx`; regenerate the icon set (`cairosvg`, `npx tauri icon`, prune per `icons/README.md`). → verify: Vitest, `tsc`, cargo, icon file list.
4. Screenshots (L5). → verify: site tests; each image looked at.
5. Session log, task lists; stop for your review.

## Gate results

*2026-09-30: detail in `querysolo-build-sessions_093026.md` §9.*

- [x] Rename committed (`7d91343`)
- [x] Mark drawn; checked at 256, 128, 64, 32 and 16 px on light and dark
- [x] Site green: 95 at `/querysolo/` and `/`; header and favicon reviewed at 1440 and 390 px
- [x] App green: Vitest 126, `tsc`, cargo 15; icon set regenerated, the same six files in each folder
- [x] Screenshots retaken (ten on the site, and the README's)
- [ ] Your review; a DMG built with the new icon on your Mac
