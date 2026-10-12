# Lakelet — ship, build brief (session 10, revision 1)

> **Decided September 11, 2026: S1 to S14 accepted** (Hants, in conversation), with the build held until the real-data round (`real-data-plan.md`) is done: a real bucket, dbt views and the app's next screens come before an installer. Three items need something only Hants has: an Apple Developer account (S4), the PyPI name (S7), and a clean machine for the three-minute measurement (§6). R1 of the real-data brief notes the one effect on this one: dbt joins the bundle, so S3's size expectation grows by about 15 MB.

*September 11, 2026 · Session 10 of `lakelet-build-sessions.md` · Follows `app-v0-plan.md` (session 6, closed September 11) and `core-v0.5-plan.md`, which it does not change · The exit of this session is "Day 0 done": a partner installs Lakelet from a download and runs a query without opening a terminal, the CLI installs from PyPI, and the gauge starts correcting itself from the history it has been recording since run one.*

## 0. The idea in one paragraph

Everything the product does exists and is tested; nothing of it can be installed. The core runs from a venv, the app from `npm run tauri dev`, and the DuckDB extensions are fetched by `init`. Session 10 turns that into three things a stranger can use: a signed, notarised macOS disk image and an Ubuntu package with the Python core frozen inside and the four extensions beside it, so the installed app makes no network request at all, not even the one `init` makes today; a `lakelet` on PyPI, so `pipx install lakelet` is the CLI the docs promise; and a release workflow that builds all of it from a tag, so the second release costs nothing. On the way it measures the two numbers the earlier briefs left open (the installer's size against the "under 200 MB" claim; the frozen sidecar's spawn-to-ready against the 1.5 s launch budget; the CLI's own second is missed on a shared runner today, 1.5 s on Ubuntu's, and the log of September 11 §18 has the breakdown to trim: the imports are half of it), ships the per-machine correction the PRD promised for this session (M7), gives partners the calibration export by hand until there is a receiver, and writes the page they are onboarded from. The "one binary" claim of the deck survives as it was restated in the build spec: one installer, one `lakelet` command, whatever is inside.

---

## 1. Decisions for review (S1 to S14)

The docs already decided: a Tauri shell with the Python core as a sidecar (build spec §3), the extensions bundled by installers so nothing fetches (core brief D33, M10), a signed DMG and an AppImage with auto-update allowed to wait (PRD F0.8.5), `brew` and `pipx` as install paths (build spec §3), the correction after twenty runs in this session (M7), Windows built and not promised (app brief A14). What follows is how, and the places where the docs' wording does not survive contact with the tools.

**S1. The core is frozen with PyInstaller in one-directory mode, and the app carries that directory as a resource.**
*Recommend:* PyInstaller (`core/freeze/lakelet.spec`) producing `core/dist/lakelet/`, a folder with a `lakelet` executable, the interpreter and every wheel the package needs, built on the platform it targets. The app bundles the folder under Tauri's resources (`bundle.resources`), and the shell resolves the sidecar in this order: `LAKELET_SIDECAR` if set (development and tests, as today), else `<resource dir>/lakelet/lakelet` if the bundle has it, else `lakelet` on `PATH`. The frozen program is the whole CLI, not a serve-only build: every "Copy as command" line in the app is a line the bundled binary can run, and S9 puts it on the user's path. *Why one-directory and not one-file:* a one-file build unpacks itself into a temp folder on every launch, seconds of work for a 250 MB payload, which alone would break the 1.5 s budget; a one-directory build starts the way a venv does. *Why a resource and not `externalBin`:* Tauri's sidecar slot is one executable per target triple; a folder does not fit it. *Not chosen:* python-build-standalone plus a venv laid into the bundle (works, no import hunting, but a second packaging tool and a larger tree); Nuitka (compiles the package to C, minutes per build per platform, and the interpreter and pyarrow are still the weight); PyOxidizer (unmaintained); shipping the core as a wheel the app installs on first run (a network request the whole design forbids).
- [x] Agree
- [ ] Change:

**S2. The four DuckDB extensions are bundled beside the frozen core and loaded from there; the core learns one environment variable.**
*Recommend:* the freeze script downloads `iceberg`, `httpfs`, `excel` and `aws` for the exact DuckDB version and platform from DuckDB's extension repository at build time and lays them out as DuckDB expects (`extensions/v<version>/<platform>/<name>.duckdb_extension`) inside `core/dist/lakelet/`. The core gains `LAKELET_EXTENSION_DIR`: when set, `Engine` and `install_extensions` run `SET extension_directory` to it before `LOAD`, so `init` finds the four already installed, downloads nothing, and says "using the bundled DuckDB extensions"; the frozen entry point sets the variable from its own location when it is unset, so the shell needs to know nothing. The CLI from PyPI keeps D33 as it is (one download at `init`, announced). `lakelet audit network` from the bundle then reads zero including `init`, which is the sentence the deck makes. *Not chosen:* the `duckdb-extension-*` wheels on PyPI (a third party's, one maintainer, and the core would carry 140 MB of extensions the CLI user may never load); relying on the user's `~/.duckdb` (a download, and a version skew the moment DuckDB is upgraded).
- [x] Agree
- [ ] Change:

*Amended 2026-10-11 (`decisions-for-review_101126.md` X1–X4, agreed by Hants):* the extensions are not bundled, on any platform. Notarisation needs every Mach-O file signed by Apple, and no `.duckdb_extension` can be both Apple-signed and loadable by DuckDB (the 534 bytes of DuckDB's signature after the library are what `codesign` refuses). The frozen core does what the CLI does: `init` downloads them once from `extensions.duckdb.org`; without the network it still makes the project and says so in a sentence, and opening the project tries again. `QUERYSOLO_EXTENSION_DIR` stays, for tests and a future offline build (DuckDB built with the extensions compiled in). The freeze gate runs `init` online and every later step offline.

**S3. The installer's size is measured and the number is what the docs say; the trimming order is fixed in advance.**
*Recommend:* measure the DMG and the `.deb` as downloaded and the app as installed, and write those numbers into the build spec's row and `/docs/install`. The expectation, from the venv's weights (pyarrow 152 MB, the DuckDB library 58 MB, the four extensions 112 MB uncompressed, the rest under 40 MB, and dulwich about 1.3 MB since the versions round; its modules go into the freeze's hidden imports beside pyiceberg's and pyarrow's): 250 to 300 MB installed, 120 to 170 MB as a compressed disk image. If the download is over 200 MB, trim in this order and stop when under: pyarrow's unneeded pieces (its Flight and Substrait libraries are 35 MB of it and nothing here imports them; `dataset` stays, pyiceberg reads through it), pyarrow's tests and headers (8 MB), the test folders PyInstaller drags along, then nothing else; the extensions and the interpreter stay. If it cannot get under, the claim changes to the measured number, not the other way round. *Not chosen:* dropping pyiceberg's pyarrow path (it is how attached tables and the catalog's reads work).
- [x] Agree
- [ ] Change:

**S4. macOS: an Apple-silicon DMG, signed with a Developer ID and notarised, from CI; Intel only if a runner offers it.**
*Recommend:* the release workflow builds on GitHub's Apple-silicon macOS runner, signs with a Developer ID Application certificate and notarises through an App Store Connect API key, both held as repository secrets, and the DMG opens on a clean Mac with no Gatekeeper dialogue (that is the "no terminal" acceptance criterion in practice: an unsigned app needs the right-click dance, and a signed-but-not-notarised one needs System Settings). Needs from Hants: an Apple Developer Program membership (US$99 a year, in his name or the company's), the certificate exported once, the API key created once; the brief lists the exact secrets in §5. The minimum system is macOS 13 as the PRD says. An Intel build comes out of the same job if GitHub still offers an Intel label for public repositories (`macos-15-intel` at the time of writing); it is not promised, and a universal binary is not attempted (pyarrow and DuckDB ship per-architecture wheels, so a universal freeze is two freezes glued together). *Not chosen:* ad-hoc signing (Gatekeeper refuses it on another machine); signing on the Mac by hand (the second release would need Hants at the keyboard).
- [x] Agree
- [ ] Change:

**S5. Ubuntu: a `.deb` first, an AppImage second, both from the 22.04 runner, unsigned.**
*Recommend:* Tauri produces both from one build. The `.deb` is the path that meets "no terminal" on Ubuntu (a double-click opens the software installer); an AppImage has to be marked executable first, which on 22.04 is a file-manager checkbox at best. So `/docs/install` leads with the `.deb`, and the AppImage is there for the other distributions. Built on `ubuntu-22.04` so the glibc floor is the PRD's. No signature in Day 0 (a SHA-256 for each file in the release notes; a signing key is Day 1 with auto-update). *Not chosen:* a Snap or Flatpak (a store account and a confinement model each, for one distribution's users).
- [x] Agree
- [ ] Change:

**S6. Distribution: GitHub Releases is the source, a Homebrew tap carries the app as a cask, and the CLI's `brew` path is amended to `pipx` or `uv tool`.**
*Recommend:* a tag `v0.1.0` produces a draft GitHub Release with the DMG, the `.deb`, the AppImage and their checksums; Hants publishes it after trying the DMG. A tap (`hantswilliams/homebrew-lakelet`, one file) makes `brew install --cask lakelet` real, pointing at the release. **The CLI does not get a Homebrew formula in Day 0**: Homebrew builds Python formulae from source, and pyarrow from source means building Arrow C++, which no tap should do; the honest CLI install lines are `pipx install lakelet` and `uv tool install lakelet` from PyPI (S7), which is what `/docs/install` says and what the app's S9 offers to its own users. This amends the build spec's distribution row (`brew install lakelet` becomes `brew install --cask lakelet` for the app; the formula is Day 1, if a wheel-based formula becomes acceptable or the core is ported). *Not chosen:* a download page on the site that hosts the files itself (Pages has a size limit and no checksums story; the site links the release).
- [x] Agree
- [ ] Change:

**S7. The core is published to PyPI from the release workflow with trusted publishing; the version lives in one place.**
*Recommend:* `lakelet` on PyPI (the name's availability is in `TASKS.md` beside the trademark search; if taken, `lakelet-cli` for the package and `lakelet` stays the command), published by the workflow through PyPI's trusted publishing (no API token in secrets). The version is `lakelet/__init__.py`'s, which hatch already reads; the release workflow refuses a tag that does not equal it, and a test holds `app/src-tauri/tauri.conf.json`'s version to the same string, so the app and the core it carries can never disagree. First release `0.1.0`, from today's `0.1.0.dev0`. Python floor 3.12 as the core brief says.
- [x] Agree
- [ ] Change:

**S8. Auto-update waits for Day 1.**
*Recommend:* defer, as the PRD allows. The installed app makes no network request, and an updater is by definition one; when it comes (Day 1, with the Linux signing key) it is a setting that is off until the user turns it on, and `PRIVACY.md` describes it. In Day 0 the app's About panel shows its version and links the releases page. *Not chosen:* Tauri's updater plugin now, off by default (it is a second network story to explain before there is a first release to update from).
- [x] Agree
- [ ] Change:

**S9. The app offers "Install the `lakelet` command" and keeps the promise that every button is a CLI line.**
*Recommend:* a row in the settings panel, the way editors offer their shell command: it links the bundled `lakelet` into `~/.local/bin` (no administrator prompt; the panel says the path and, if that folder is not on the user's `PATH`, the one line that adds it). On macOS from the `.app` and on Ubuntu from the `.deb` the target is a fixed path; from an AppImage there is no stable path (the image is mounted per launch), so the row says to use `pipx` instead. A Rust command does the link; a Rust test covers it against a temp home. *Not chosen:* writing into `/usr/local/bin` (a password dialogue for a symlink).
- [x] Agree
- [ ] Change:

**S10. The correction (M7): one factor per machine and per dominant operator class, a median ratio after twenty runs, applied to local wall time only, bounded.**
*Recommend:* history already records for every run the estimate (`est_wall_local`), the actual (`actual_wall`), the machine profile hash and the operator counts, and the `corrections(machine_hash, operator_class, factor, n, updated)` table has been empty since step 4. After each recorded run the core recomputes, over the last 200 runs on this machine that ran locally to completion and took at least 0.5 s (below that the ratio is noise), the median of `actual_wall / est_wall_local`; the machine-wide factor is used once there are 20 such runs, and a per-class factor replaces it for a plan whose dominant class (the class with the largest share of the CPU estimate, which the estimator knows) has at least 10 runs of its own. Factors are clamped to [0.25, 4] and only the local wall time is multiplied: bytes and peak memory are properties of the plan and the data, not of the machine, and the burst arithmetic is the worker's, not the laptop's. The gauge sentence does not change shape; `lakelet estimate` and `gauge history` add "corrected ×0.8 from 43 runs" when a factor is in play, and `/api/query`'s headers carry the factor so the app's gauge line can say the same in its tooltip. `lakelet gauge reset` clears the table. *Gate:* PRD F0.3's acceptance ("≥ 20% reduction in median absolute log-error after 50 runs") on the TPC-H harness: 44 runs (two passes), the second pass estimated with and without the factors, the corrected median absolute log-error the lower of the two. *Not chosen:* correcting each operator's cost separately (the estimate is a `max(IO, CPU)` of sums; the per-class residual is not identifiable from the wall time alone, and a trained model is Day 1 on shared data by D8).
- [x] Agree
- [ ] Change:

**S11. Instrumentation export is `lakelet gauge export`, a JSON-lines file of exactly the fields F0.3.9 allows, sent by partners by hand; the sharing toggle stays off by default everywhere in Day 0.** *Built September 11, 2026 in the real-data round (step 4, R8), with `gauge reset` and the Gauge screen; what is left for session 10 is `PRIVACY.md` and the first-run wording.*
*Recommend:* `lakelet gauge export [--out <file>]` (and `GET /api/gauge/export`) writes one line per run with: the fingerprint hash, the operator-class counts, the estimates, the actuals, the machine profile in buckets (RAM to the nearest 8 GB, threads, disk throughput to the nearest 500 MB/s, the platform), the verdict and where it ran; never the SQL, a table name, a column name or a value, and a test asserts it by grepping the file for every table and column name the fixture has. This file is the contract the Day 1 share path sends, so the receiver is built against a format partners have already produced. The PRD's first-run toggle, default on for the app, is deferred with the receiver: a switch that sends nothing should not be on, so `share_calibration` stays `false` everywhere, the settings row says "nothing is sent yet; `lakelet gauge export` writes the file", and `PRIVACY.md` in the repo and the bundle describes every byte that can leave the machine (today: none). This is a deviation from PRD F0.3.9's default, recorded in §8.
- [x] Agree
- [ ] Change:

**S12. The engines smoke test runs again through `lakelet catalog serve`, on the Mac, as a compose profile.**
*Recommend:* `tests/smoke/` gains a variant where Spark and Trino are pointed at `lakelet catalog serve` (the real verb, a real project folder) rather than the test harness's in-process server, behind the compose `engines` profile as before; both read a Lakelet-created table on RustFS and write a row back, DuckDB sees the rows. Hants runs it on the Mac (Docker) and the transcript goes in the log; it is not in CI (a JVM and three containers). This closes the core brief's §8 row.
- [x] Agree
- [ ] Change:

*Amended September 15, 2026 (`trust-round-plan.md` T7): the README is now the public front door for a person who runs Lakelet; S13's page points at it, and the clean-machine quickstart (§6) uses `examples/sample-data/make_sample.py` so no `orders.csv` is assumed.*

**S13. Partner onboarding is one public page and one private file.**
*Recommend:* `/docs/partners` on the site: what to install and how (the DMG, the `.deb`, `pipx`), the five intake questions (format, folder layout, file count, what wrote it, whether it changes daily), what `tables attach` and `refresh` mean for a bucket that changes (D27's snapshot semantics), what leaves the machine (nothing; the export and how to send it), the 45-minute call's agenda, and the weekly check-in. The partners' answers live outside the repo (no partner names in git, as the repo rules say). *Not chosen:* a form on the site (the waitlist form is not wired either; the call is the form).
- [x] Agree
- [ ] Change:

**S14. Windows: the release workflow builds an unsigned MSI on a Windows runner and is allowed to fail; nothing is published.**
*Recommend:* one job, `continue-on-error`, so every release tells us how far Windows is (A14's "one build in session 10"). The core's probe already falls to the cached path where neither `O_DIRECT` nor `F_NOCACHE` exists, so the CLI from PyPI may run on Windows today; the PRD's open question on testing the Windows CLI in Day 0 is answered "the core suite gets a Windows runner if it passes within a day of effort; otherwise Day 1", and the day is spent inside step 2.
- [x] Agree
- [ ] Change:

---

## 2. Scope

**In session 10:** the freeze (`core/freeze/`), `LAKELET_EXTENSION_DIR`; the app bundle with the sidecar as a resource and the resolution order; real icons; the release workflow (macOS signed and notarised, Ubuntu `.deb` and AppImage, PyPI, the draft release, the Windows attempt); the tap with the cask; `/docs/install` rewritten and `/docs/app`'s "no installer yet" removed; "Install the `lakelet` command"; the About panel; `PRIVACY.md`; the correction (M7) with its CLI and API surface; `lakelet gauge export`; the `catalog serve` engines smoke; `/docs/partners`; the measurements in §6.

**Not in session 10:** auto-update and Linux signing (Day 1); the sharing receiver and the first-run toggle (Day 1); a Homebrew formula for the CLI; a universal macOS binary; Windows as a product; a Snap or Flatpak; the ask box (session 7, parked); burst (session 8); dbt and the two modes (session 9).

---

## 3. Architecture

### 3.1 The bundle

```
Lakelet.app/Contents/                         (the .deb: /usr/lib/lakelet/, /usr/bin/lakelet-app)
├─ MacOS/lakelet-app                          Tauri shell (Rust)
└─ Resources/lakelet/                         the frozen core, one directory (S1)
     ├─ lakelet                               the CLI and the sidecar, same program
     └─ _internal/                            the interpreter, pyarrow, duckdb, pyiceberg, …
```

*Amended 2026-10-11 (X1):* no `extensions/` folder; `init` downloads them into `~/.duckdb/extensions`, and the next paragraph's "installs nothing" no longer holds.

The shell finds the sidecar as S1 says and runs `lakelet serve --port 0 -C <project> --memory-limit <n>`, unchanged from session 6. The frozen entry point sets `LAKELET_EXTENSION_DIR` to `<its own dir>/extensions` when unset, so `init` from the bundle installs nothing and `Engine` loads from there. `serve.json`, the token, the CORS list and the CSP are session 6's. A release build passes no dev origin (the `cargo test --release` gate of step 5).

### 3.2 The release pipeline

```
tag v0.1.0 ──► release.yml
   ├─ check: tag == lakelet.__version__ == tauri.conf.json version
   ├─ macos (Apple silicon; Intel if a runner is offered)
   │     uv sync → pyinstaller lakelet.spec → npm run tauri build
   │     → sign (Developer ID) → notarise (API key) → Lakelet_0.1.0_aarch64.dmg + sha256
   ├─ ubuntu-22.04
   │     same freeze → tauri build → lakelet_0.1.0_amd64.deb, Lakelet_0.1.0_amd64.AppImage + sha256
   ├─ windows (continue-on-error)          → an MSI that is not uploaded
   ├─ pypi                                  → lakelet 0.1.0 (trusted publishing, sdist + wheel)
   └─ draft GitHub Release with the files and the checksums; Hants publishes
```

`app-ci.yml` and `core-ci.yml` are unchanged; the release workflow runs only on tags. The tap's cask is bumped by hand with the release's URL and checksum (one file, two lines) until there is a second release to automate it for.

### 3.3 The correction's data path

`history.record(run)` → `corrections.refresh(machine_hash)` (a median over the last 200 completed local runs of ≥ 0.5 s, per dominant class and overall) → `gauge.estimate_plan(...)` reads the machine's factors and multiplies `wall_local` → the sentence, `X-Lakelet-Correction: 0.8;43` on the query response, "corrected ×0.8 from 43 runs" in `estimate` and `gauge history`. The TPC-H harness is the calibration set for the gate.

### 3.4 Files

```
core/freeze/lakelet.spec, build.py           the PyInstaller spec; the extension download and layout
core/lakelet/corrections.py                  the reader of history and writer of `corrections` (S10)
core/lakelet/gauge/export.py                 the F0.3.9 file (S11)
core/tests/test_step10_*.py, tests/smoke/    gates
app/src-tauri/src/supervisor.rs              the resolution order; src/install_cli.rs (S9)
app/src-tauri/tauri.conf.json                bundle.resources, macOS minimum system, the icon set
.github/workflows/release.yml
PRIVACY.md
web/src/content/docs/{install,app,partners,gauge}.md
```

---

## 4. Build order

Each step ends with a test that stays in the suite, or a measurement recorded in §6. Steps 0 to 2 are the ship path and come first; 3 to 5 can follow in any order.

| Step | Builds | Gate |
|---|---|---|
| 0 | The freeze: `core/freeze/` (the spec, the hidden imports pyiceberg and pyarrow need, the extension download and layout), `LAKELET_EXTENSION_DIR` in the core with `init` saying "bundled" and `audit network` reading zero including `init` | The frozen `lakelet` runs the quickstart's eight commands from an empty `HOME` with outbound connections blocked; the core's CLI tests run against the frozen binary (`LAKELET_BIN`) on both CI runners; the app under `LAKELET_SIDECAR=core/dist/lakelet/lakelet` passes Playwright unchanged; spawn-to-ready from the frozen sidecar recorded (§6); the directory's size recorded |
| 1 | The bundle: `bundle.resources`, the sidecar resolution order (`LAKELET_SIDECAR`, the resource, `PATH`) with a Rust test, the real icon set from the brand SVG (rendered by `tauri icon`, committed; the SVG stays gitignored), the About panel, the version-equality test (S7), `PRIVACY.md` | `npm run tauri build` on the Mac gives a `.app` whose sidecar is the bundled one (the About panel names the path); `spctl` refuses it, as expected before signing; the installed size recorded |
| 2 | `release.yml` (S4, S5, S7, S14): the version check, the macOS job with signing and notarisation from secrets, the Ubuntu job, the PyPI job, the Windows attempt, the draft release with checksums | A tag `v0.1.0-rc1` produces the DMG, the `.deb`, the AppImage and a PyPI pre-release; the DMG opens on a Mac that has never seen Lakelet with no Gatekeeper dialogue and `spctl --assess` accepts it; the `.deb` installs on a 22.04 VM and the app opens; `pipx install lakelet==0.1.0rc1` on either gives a `lakelet` that runs the quickstart; the download sizes recorded against the 200 MB claim (S3) |
| 3 | Distribution and the docs: the tap with the cask, `/docs/install` (download, `brew install --cask`, `pipx`, `uv tool`; the measured sizes), `/docs/app` without "no installer yet", "Install the `lakelet` command" (S9) with its Rust test, `/docs/partners` (S13) | `brew install --cask` from the tap installs the release's DMG; the command row links `~/.local/bin/lakelet` and `lakelet --version` from a new shell answers; the three-minute measurement (§6) on the clean Mac, by Hants |
| 4 | The correction (S10): `corrections.py`, the refresh after each record, the factor in the estimate, `X-Lakelet-Correction`, the wording in `estimate` and `gauge history`, `gauge reset`, the tooltip in the app's gauge line; `/docs/gauge` says how it works and how to reset it | pytest: no factor before 20 runs, the machine-wide factor at 20, a per-class factor at 10 of that class, the clamp, `reset`; the TPC-H harness gate (two passes, the corrected pass's median absolute log-error lower); the header in the API test |
| 5 | `lakelet gauge export` and `/api/gauge/export` (S11); the `catalog serve` engines smoke (S12); the log; §6 and `TASKS.md` | pytest: the export has every F0.3.9 field and none of the fixture's table names, column names or values; the smoke transcript from the Mac in the log |

---

## 5. Toolchain

| | Version, to be pinned in step 0 |
|---|---|
| PyInstaller | 6.x current, with `pyinstaller-hooks-contrib` (the pyarrow hook) |
| Python for the freeze | 3.13 via uv, the same the suite runs |
| DuckDB extensions | not bundled (X1, 2026-10-11); `init` downloads them |
| Tauri CLI, bundler | 2.x current; `bundle.macOS.minimumSystemVersion` 13.0; `bundle.resources` |
| GitHub runners | Apple-silicon macOS (`macos-15`), `ubuntu-22.04`, `windows-latest` (allowed to fail); an Intel label if offered |
| Apple secrets | `APPLE_CERTIFICATE` (the Developer ID Application `.p12`, base64), `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_API_ISSUER`, `APPLE_API_KEY`, `APPLE_API_KEY_PATH` (the `.p8`), which Tauri's bundler reads for signing and notarisation |
| PyPI | trusted publishing from `release.yml` (`pypa/gh-action-pypi-publish`), the project registered once by Hants |
| Homebrew | a tap repository `homebrew-lakelet` with `Casks/lakelet.rb` |

---

## 6. Definition of done

*"Day 0 done" from the session map. To be measured and recorded in step 5; the clean Mac and the Ubuntu VM are Hants'.*

- [ ] **A stranger can install it.** The DMG and the `.deb` download from a published GitHub Release; `brew install --cask lakelet` works from the tap; `pipx install lakelet` from PyPI gives the CLI. Fresh-machine install to first query ≤ 3 minutes with no terminal (PRD F0.8 AC), timed by Hants on a Mac that has never seen Lakelet: download, open, drop `examples/sample-data`'s CSV, a query.
- [ ] **Nothing hidden, from the bundle.** `lakelet audit network` from the installed app's `lakelet` reads zero requests including `init`; the app's Playwright "nothing hidden" test passes against the frozen sidecar.
- [ ] **The two open numbers.** The installer's size (DMG, `.deb`, installed) against "under 200 MB", and what the docs now say. The frozen sidecar's spawn-to-ready from the app: the first launch after install (Gatekeeper reads every library once) and the second, against the 1.5 s budget.
- [ ] **The app and the core agree.** One version string, tested; the About panel names it and the sidecar's path.
- [ ] **The correction works.** No factor before 20 runs; on the TPC-H harness the corrected pass's median absolute log-error is below the uncorrected one; `gauge history` says so in one clause.
- [ ] **Partners can send data by hand.** `lakelet gauge export` writes the F0.3.9 fields and nothing else, held by a test; `/docs/partners` says how to send it; `PRIVACY.md` says nothing leaves the machine without it.
- [ ] **The engines read through the real verb.** Spark and Trino against `lakelet catalog serve`, transcript in the log.
- [ ] **Tests green** on both CI runners with the frozen binary in the core's CLI tests; `release.yml` green on a tag.

---

## 7. Known unknowns

- **The first launch on macOS.** A notarised app with several hundred Mach-O files inside (a frozen Python is one) is scanned by Gatekeeper the first time it opens, which on a laptop can take seconds; the second launch is not affected. Step 2 measures both; if the first is far over 1.5 s, the amber dot and a "first launch" line cover it, and the trim in S3 (fewer libraries) is the lever.
- **Signing what is inside a resource.** Tauri signs the app and its sidecars; executables and dynamic libraries under `Resources/` may need the bundler told (or a signing pass with the same identity before the DMG is made) for notarisation to accept them. Step 2's `spctl --assess` is the gate; the fallback is signing `Resources/lakelet` in the workflow before `tauri build` runs its own pass.
- **PyInstaller's view of pyiceberg and pyarrow.** Hidden imports (pyiceberg's catalog and IO implementations are loaded by name; pyarrow's hook covers its libraries) and pyarrow's size are step 0's; the empty-`HOME`, network-blocked quickstart is what finds a missing module.
- **The AppImage and WebKitGTK.** Whether Tauri's AppImage carries the webview or expects the system's on 22.04; the `.deb` declares the dependency either way, which is one reason it leads.
- **An Intel Mac.** Whether a free Intel runner is offered when the workflow is written; without one, Intel is "built on request" in `/docs/install`.
- **The PyPI name and the trademark** (`TASKS.md`); the package name falls back to `lakelet-cli` without the command changing.
- **The frozen sidecar and `ready_ms`.** From a venv it is 871 ms cold on the 64 GB Mac; a frozen interpreter imports from a flat directory, which is usually no slower, but the number is the point of step 0's gate.
- **Keys for people without the AWS CLI** (`decisions-for-review_092126.md` C3, agreed 2026-09-21). The installed app reaches a private bucket through an AWS profile on the machine (C1), which presumes `aws configure` or `aws sso login` has been run once. If the first outsiders say that was a wall, the candidate is O3 of that file: the shell stores a key pair in the OS keychain (macOS Keychain, Linux Secret Service; the `keyring` crate) and injects it into the sidecar's environment at start; the core stays environment-only and never reads the keychain, so the audit and privacy story do not change. Not built until they say so.

---

## 8. What this changes in the other documents

| Document | Change |
|---|---|
| `docs/lakelet-v0-build-spec.md` §3 | Desktop shell row: the measured size replaces "under 200 MB… measured in session 10". Distribution row: `brew install --cask lakelet` for the app; the CLI by `pipx install lakelet` or `uv tool install lakelet`; a formula is Day 1 (S6) |
| `docs/lakelet-day0-prd.md` | F0.8.5: met as a DMG and a `.deb` plus AppImage (S5); auto-update deferred as allowed (S8). F0.3.9: the first-run toggle and the app's default-on are deferred with the receiver; Day 0 ships the export by hand (S11). Open question 2 (Windows CLI): answered per S14 |
| `build-sessions/core-v0.5-plan.md` | §8 rows "correction factors" and "engines smoke through `catalog serve`" → done in session 10 (S10, S12); D33 gains the sentence that installers set `LAKELET_EXTENSION_DIR` (S2) |
| `build-sessions/app-v0-plan.md` §7 | The frozen sidecar's spawn-to-ready: answered with step 0's number |
| `build-sessions/lakelet-session-6-desktop-shell.md` | "Handed to session 10" items closed: the resolution order, the icons, `externalBin` stays empty (a resource instead), the release-build origin test joins the release workflow |
| `build-sessions/lakelet-build-sessions.md` | Session 10's line: "calibration toggle" becomes "the export; the toggle waits for the receiver" |
| `web/src/content/docs/install.md`, `app.md`, `index.md` | The installers exist; the status table; "no installer yet" removed |
| `README.md`, the deck's "one binary" line | Unchanged: one installer, one command |
| `TASKS.md` | Session 10 rows; the Hants-only items (the Apple account, the PyPI name, the clean machines) |
