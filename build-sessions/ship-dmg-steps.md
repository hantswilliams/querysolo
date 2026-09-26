# The macOS DMG, step by step

*September 24, 2026 · The "how" for `ship-v0-plan.md` steps 0–2 on the Mac path only (S1–S4, S7, S9 are decided; this file adds no decisions). Ubuntu, PyPI and the tap follow the same workflow later and are not here. Two columns of work: what Hants does once (accounts, certificates, the clean Mac), and what gets built in sessions (the freeze, the bundle, the workflow). Each step ends with a thing you can see. Read it once, mark what you have, then the first session is step 1.*

---

## The shape of it

A DMG is three things stacked: the **frozen core** (`core/dist/lakelet/`, a folder with a `lakelet` executable, Python, pyarrow, DuckDB and the four extensions; S1, S2), the **Tauri bundle** that carries that folder as a resource and produces `Lakelet.app` (step 1 of the brief), and **signing and notarisation** so a stranger's Mac opens it with no dialogue (S4). The first two can be done and measured today with no Apple account; the third needs the account and is the part that fails in interesting ways. So the order is: freeze → local unsigned build → account and certificate → local signed build → the workflow → a tag that produces the DMG → the clean-Mac test.

---

## Step 0 — What Hants does before anything (an hour, spread over a few days)

**0.1 Apple Developer Program.** Enrol at developer.apple.com (US$99/year; in your name or the company's — the name is what Gatekeeper shows as the developer, so decide which). Enrolment takes up to 48 hours for an individual, longer for an organisation (a D-U-N-S number is required for a company). Nothing else in step 0 can happen until it is approved.

**0.2 The Developer ID Application certificate.** In Xcode (Settings → Accounts → Manage Certificates → + → Developer ID Application) or at developer.apple.com → Certificates. Then in Keychain Access, export the certificate *with its private key* as a `.p12` with a password. Two facts to keep: `base64 -i cert.p12 | pbcopy` becomes the `APPLE_CERTIFICATE` secret, the password becomes `APPLE_CERTIFICATE_PASSWORD`, and `security find-identity -v -p codesigning` prints the identity string ("Developer ID Application: Name (TEAMID)") that becomes `APPLE_SIGNING_IDENTITY`.

**0.3 The App Store Connect API key** (for notarisation without your Apple ID password). App Store Connect → Users and Access → Integrations → App Store Connect API → Team keys → +, role Developer. Download the `.p8` once (it cannot be downloaded again). Keep the Key ID and the Issuer ID: `APPLE_API_KEY` (the id), `APPLE_API_ISSUER` (the issuer), and the `.p8` file's contents become `APPLE_API_KEY_PATH` in the workflow (written to a temp file at build time).

**0.4 The six secrets in the repository.** GitHub → Settings → Secrets and variables → Actions: `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_KEY_PATH` (the `.p8` contents). Tauri's bundler reads exactly these names. None of them go in the repo, `lakelet.toml`, or this file.

**0.5 A clean Mac.** The three-minute measurement (§6 of the brief) needs a Mac that has never seen Lakelet, a venv, or `~/.duckdb`. Cheapest: a second user account on your Mac (System Settings → Users & Groups; log in as it; Gatekeeper behaves the same); better: a friend's Mac or a fresh macOS VM (UTM or Apple's Virtualization framework on Apple silicon). Decide which before step 6.

**0.6 The PyPI name** is not needed for the DMG, but the tag that produces the DMG will also try to publish the CLI; until PyPI trusted publishing is set up, the workflow's PyPI job is `continue-on-error` so the DMG does not wait on it.

---

## Step 1 — The freeze (a session; nothing Apple)

Builds `core/freeze/` per S1 and S2. On the Mac, from `core/`:

- `core/freeze/lakelet.spec`: PyInstaller one-directory, entry `lakelet.cli:app` via a tiny `core/freeze/entry.py` that sets `LAKELET_EXTENSION_DIR` to `<its own folder>/extensions` when unset, then calls the CLI. Hidden imports for pyiceberg's catalog and IO modules (loaded by name: `pyiceberg.catalog.rest`, `pyiceberg.io.pyarrow`, `pyiceberg.io.fsspec`), dulwich's, dbt's adapters (`dbt.adapters.duckdb`, `dbt.include.duckdb`, and the `dbt` plugins directory as data), and the `lakelet.dbt.plugin` module; pyarrow's hook from `pyinstaller-hooks-contrib`. Excludes for the S3 trim list (pyarrow's Flight and Substrait libraries, tests, headers).
- `core/freeze/extensions.py`: downloads `iceberg`, `httpfs`, `excel`, `aws` for `v1.5.5` and `osx_arm64` from `extensions.duckdb.org` and lays them out as `extensions/v1.5.5/osx_arm64/<name>.duckdb_extension` inside `dist/lakelet/`.
- The core learns `LAKELET_EXTENSION_DIR` (`engine.py`'s `SET extension_directory` before `LOAD`; `install_extensions` finds them installed and `init` says "using the bundled DuckDB extensions").
- `uv run --group freeze pyinstaller freeze/lakelet.spec` → `core/dist/lakelet/lakelet`.

*What you see:* `core/dist/lakelet/lakelet --version` answers; from an empty `HOME` with outbound blocked (`sudo pfctl` rules on the Mac, or simply unplug), the quickstart's eight commands run and `lakelet audit network` reads zero including `init`; `du -sh core/dist/lakelet` is the first number for S3 (expect 250–300 MB). The core's CLI tests run against the frozen binary with `LAKELET_BIN`; the app's Playwright suite passes with `LAKELET_SIDECAR=core/dist/lakelet/lakelet`; the app's status strip shows spawn-to-ready from the frozen sidecar (the second number for §6).

*Where it fails first:* a missing hidden import shows up as `ModuleNotFoundError` on the first command that needs it — that is what the empty-`HOME` quickstart is for. Budget half a day for the hunt.

---

## Step 2 — The bundle, unsigned, on your Mac (a session)

Builds step 1 of the brief.

- `tauri.conf.json`: `bundle.resources: ["../../core/dist/lakelet/**"]` (the folder lands at `Lakelet.app/Contents/Resources/lakelet/`), `bundle.macOS.minimumSystemVersion: "13.0"`, `bundle.targets: ["app", "dmg"]`, the DMG's window (`bundle.macOS.dmg`: the app on the left, the Applications shortcut on the right; a background image is optional and gitignored with the brand assets), the real icon set already in `icons/` (U4).
- `supervisor.rs`'s `sidecar_executable()` gains the middle case: `LAKELET_SIDECAR` if set, else `<resource dir>/lakelet/lakelet` if it exists (`app.path().resource_dir()`), else `lakelet` on `PATH`; a Rust test for the order against a temp resource dir.
- The About panel (version, the sidecar's resolved path, a link to the releases page) — S8 says the version is shown there; the version-equality test (S7) holds `tauri.conf.json`, `Cargo.toml` and `lakelet/__init__.py` to one string.
- `cd app && npm run tauri build -- --target aarch64-apple-darwin`.

*What you see:* `app/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/Lakelet_0.1.0_aarch64.dmg` and `…/macos/Lakelet.app`. Drag it to Applications on your own Mac; it opens (your Mac trusts what you built). About names `…/Resources/lakelet/lakelet`. `du -sh Lakelet.app` and `ls -la *.dmg` are the installed and download sizes for S3. `spctl --assess --type execute Lakelet.app` says *rejected* — expected, nothing is signed yet.

*Where it fails first:* PyInstaller's folder contains hundreds of `.dylib` and `.so` files; Tauri copies resources without touching them, so this step works. It is the next step that cares about them.

---

## Step 3 — Signed and notarised, still on your Mac (a session, after 0.1–0.3)

The step the brief's §7 flags: Tauri signs `Lakelet.app` and its `externalBin`, but not the executables and libraries under `Resources/`, and notarisation rejects an app with unsigned Mach-O files inside. So the build gets one extra pass, run *before* Tauri's own signing, and a hardened-runtime entitlements file for the Python inside.

- `app/src-tauri/entitlements.plist`: `com.apple.security.cs.allow-unsigned-executable-memory`, `com.apple.security.cs.disable-library-validation`, `com.apple.security.cs.allow-dyld-environment-variables` — the three a frozen CPython with C extensions needs under the hardened runtime (without them the sidecar dies on launch with a `dyld` or JIT error and no useful message). `bundle.macOS.entitlements` points at it.
- `app/scripts/sign-sidecar.sh`: `find core/dist/lakelet -type f \( -perm +111 -o -name '*.dylib' -o -name '*.so' \) -exec codesign --force --options runtime --timestamp --entitlements entitlements.plist --sign "$APPLE_SIGNING_IDENTITY" {} +`, then the `lakelet` executable itself last. Tauri's `beforeBundleCommand` runs it. Deep-signing in the right order matters (inner libraries before the executable that links them); the script signs everything then the entry point.
- With the six variables in your shell (from 0.2 and 0.3), `npm run tauri build` signs the app, submits the DMG to Apple's notary service (a few minutes), and staples the ticket.

*What you see:* `spctl --assess --type execute -vv Lakelet.app` says *accepted, source=Notarized Developer ID*; `codesign --verify --deep --strict --verbose=2 Lakelet.app` is silent; `xcrun stapler validate Lakelet_0.1.0_aarch64.dmg` says the ticket is stapled. Then the clean account from 0.5: download the DMG, open, drag, launch — no right-click, no System Settings. First launch will pause while Gatekeeper reads every library (the §7 unknown; time it), second launch is the real spawn-to-ready.

*Where it fails first:* notarisation's rejection email lists each unsigned or wrongly-signed file by path; the script's `find` is what to fix. The other classic failure is a library signed without `--timestamp` or without `--options runtime`; the log names it.

---

## Step 4 — The workflow (a session)

`.github/workflows/release.yml`, triggered by a tag `v*`:

- A version job: the tag equals `lakelet/__init__.py`'s version and `tauri.conf.json`'s, else stop.
- The macOS job on `macos-15` (Apple silicon): checkout, uv, `uv sync --group freeze`, step 1's freeze, the four extensions downloaded for `osx_arm64`, Node and Rust, the six secrets into the environment (the `.p8` written to a temp path for `APPLE_API_KEY_PATH`), `npm run tauri build -- --target aarch64-apple-darwin`, `spctl --assess` on the result as a gate, the DMG and its `sha256` uploaded as artifacts. An Intel job is the same with `macos-15-intel` and `x86_64-apple-darwin` if the label is offered, `continue-on-error`.
- A release job: a *draft* GitHub Release for the tag with the DMG, the checksums and a body that names the sizes. Draft, so Hants tries it before it is public (S6).
- The PyPI job and the Ubuntu job from the brief's step 2, `continue-on-error` until they are set up, so the DMG never waits on them.

*What you see:* push `v0.1.0-rc1`; twenty minutes later a draft release with a DMG built by nobody's laptop. Download it on the clean account; the same checks as step 3 pass on a file that never touched your Mac. Delete the rc release after.

---

## Step 5 — First-run, on the DMG (small, but it is the persona's first minute)

Per N1, the installed app is the analyst's first sight of the product, so three things belong in the same session as the DMG:

- The welcome screen's first line for an installed app: "New project…" leads; "Open a folder…" second; the line about `LAKELET_SIDECAR` and `npm run tauri dev` is developer text and appears only when the sidecar came from `LAKELET_SIDECAR`.
- "Install the `lakelet` command" in Settings (S9): the Rust command that links `~/.local/bin/lakelet` to the bundled binary, with the `PATH` sentence when needed.
- The credentials story from the Dock (C1): the New project dialog's profile picker works with no shell, which is the whole reason C1 was built before ship; verify it on the clean account with a `~/.aws/credentials` present.

*What you see:* on the clean account, from download to a chart on `sample/orders.csv`, timed with a stopwatch, under three minutes, no terminal. That number goes into §6 and `/docs/install`.

---

## Step 6 — Publish

Tag `v0.1.0`, let the workflow make the draft, try the DMG once more on the clean account, publish the release, and put the DMG's link and the measured sizes into `/docs/install` and the README's install section (the "no installer yet" lines go). The tap and the cask (S6) can follow the same day: one file, `Casks/lakelet.rb`, pointing at the release's DMG and its sha256.

---

## What can be done before the Apple account arrives

Steps 1, 2, 4 (without the signing lines active), and the first-run work in 5. Only step 3 and the signed half of 4 wait on 0.1–0.4. If the enrolment takes its 48 hours, the freeze and the unsigned bundle fill them.

## Rough time

Step 0: an hour of yours plus Apple's waiting. Step 1: a day (the hidden-import hunt is the variable). Step 2: half a day. Step 3: half a day if notarisation accepts on the second try, a day if the resources signing needs iteration. Step 4: half a day. Step 5: half a day. Step 6: an hour. About four working days of sessions once the account exists.
