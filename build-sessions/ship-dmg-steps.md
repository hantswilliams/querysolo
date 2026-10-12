# The macOS DMG, step by step

*September 24, 2026 · The "how" for `ship-v0-plan.md` steps 0–2 on the Mac path only (S1–S4, S7, S9 are decided; this file adds no decisions). Ubuntu, PyPI and the tap follow the same workflow later and are not here. Two columns of work: what Hants does once (accounts, certificates, the clean Mac), and what gets built in sessions (the freeze, the bundle, the workflow). Each step ends with a thing you can see. Read it once, mark what you have, then the first session is step 1.*

---

## The shape of it

A DMG is three things stacked: the **frozen core** (`core/dist/querysolo/`, a folder with a `querysolo` executable, Python, pyarrow and DuckDB; S1, with S2 amended: the extensions are downloaded at `init`, not bundled — decisions X1, 2026-10-11), the **Tauri bundle** that carries that folder as a resource and produces `QuerySolo.app` (step 1 of the brief), and **signing and notarisation** so a stranger's Mac opens it with no dialogue (S4). The first two can be done and measured today with no Apple account; the third needs the account and is the part that fails in interesting ways. So the order is: freeze → local unsigned build → account and certificate → local signed build → the workflow → a tag that produces the DMG → the clean-Mac test.

---

## Step 0 — What Hants does before anything (an hour, spread over a few days)

**0.1 Apple Developer Program.** Enrol at developer.apple.com (US$99/year; in your name or the company's — the name is what Gatekeeper shows as the developer, so decide which). Enrolment takes up to 48 hours for an individual, longer for an organisation (a D-U-N-S number is required for a company). Nothing else in step 0 can happen until it is approved.

**0.2 The Developer ID Application certificate.** In Xcode (Settings → Accounts → Manage Certificates → + → Developer ID Application) or at developer.apple.com → Certificates. Then in Keychain Access, export the certificate *with its private key* as a `.p12` with a password. Two facts to keep: `base64 -i cert.p12 | pbcopy` becomes the `APPLE_CERTIFICATE` secret, the password becomes `APPLE_CERTIFICATE_PASSWORD`, and `security find-identity -v -p codesigning` prints the identity string ("Developer ID Application: Name (TEAMID)") that becomes `APPLE_SIGNING_IDENTITY`.

**0.3 The App Store Connect API key** (for notarisation without your Apple ID password). App Store Connect → Users and Access → Integrations → App Store Connect API → Team keys → +, role Developer. Download the `.p8` once (it cannot be downloaded again). Keep the Key ID and the Issuer ID: `APPLE_API_KEY` (the id), `APPLE_API_ISSUER` (the issuer). Tauri's `APPLE_API_KEY_PATH` is a *path* to the `.p8` file: on your Mac, the file's absolute path (a bare file name fails, because notarytool runs from `app/src-tauri`); in the workflow, the `APPLE_API_PRIVATE_KEY` secret (the `.p8`'s contents) written to a temp file at build time.

**0.4 The six secrets in the repository.** GitHub → Settings → Secrets and variables → Actions: `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_PRIVATE_KEY` (the `.p8` contents; the workflow writes it to a file and sets `APPLE_API_KEY_PATH`). Tauri's bundler reads the other five by name. None of them go in the repo, `querysolo.toml`, or this file.

**0.5 A clean Mac.** The three-minute measurement (§6 of the brief) needs a Mac that has never seen QuerySolo, a venv, or `~/.duckdb`. Cheapest: a second user account on your Mac (System Settings → Users & Groups; log in as it; Gatekeeper behaves the same); better: a friend's Mac or a fresh macOS VM (UTM or Apple's Virtualization framework on Apple silicon). Decide which before step 6.

**0.6 The PyPI name** is not needed for the DMG, but the tag that produces the DMG will also try to publish the CLI; until PyPI trusted publishing is set up, the workflow's PyPI job is `continue-on-error` so the DMG does not wait on it.

---

## Step 1 — The freeze (a session; nothing Apple)

Builds `core/freeze/` per S1 and S2. On the Mac, from `core/`:

- `core/freeze/querysolo.spec`: PyInstaller one-directory, entry `querysolo.cli:app` via a tiny `core/freeze/entry.py` that sets `QUERYSOLO_EXTENSION_DIR` to `<its own folder>/extensions` when that folder exists (the freeze no longer makes one), then calls the CLI. Hidden imports for pyiceberg's catalog and IO modules (loaded by name: `pyiceberg.catalog.rest`, `pyiceberg.io.pyarrow`, `pyiceberg.io.fsspec`), dulwich's, dbt's adapters (`dbt.adapters.duckdb`, `dbt.include.duckdb`, and the `dbt` plugins directory as data), and the `querysolo.dbt.plugin` module; pyarrow's hook from `pyinstaller-hooks-contrib`. Excludes for the S3 trim list (pyarrow's Flight and Substrait libraries, tests, headers).
- No extensions in the freeze (decisions X1, X2, 2026-10-11): each `.duckdb_extension` carries DuckDB's signature after the library, which `codesign` refuses, and a copy cut back so Apple will sign it is one DuckDB refuses to load. So the frozen core does what the CLI does: `init` downloads the five (`iceberg`, `httpfs`, `excel`, `aws`, `avro`; about 80 MB) from `extensions.duckdb.org` once, into `~/.duckdb/extensions`. Without the network, `init` still makes the project and says so in a sentence, and opening it tries again (X3). `QUERYSOLO_EXTENSION_DIR` stays, for tests and a future offline build.
- `uv run --group freeze pyinstaller freeze/querysolo.spec` → `core/dist/querysolo/querysolo`.

*What you see:* `core/dist/querysolo/querysolo --version` answers; from an empty `HOME` with outbound blocked (`sudo pfctl` rules on the Mac, or simply unplug), `init` downloads the extensions with the network on, then the quickstart's other seven commands run with it off and `querysolo audit network` reads zero (`freeze/build.py --check`, decisions X4); `du -sh core/dist/querysolo` is the first number for S3 (expect 250–300 MB). The core's CLI tests run against the frozen binary with `QUERYSOLO_BIN`; the app's Playwright suite passes with `QUERYSOLO_SIDECAR=core/dist/querysolo/querysolo`; the app's status strip shows spawn-to-ready from the frozen sidecar (the second number for §6).

*Where it fails first:* a missing hidden import shows up as `ModuleNotFoundError` on the first command that needs it — that is what the empty-`HOME` quickstart is for. Budget half a day for the hunt.

---

## Step 2 — The bundle, unsigned, on your Mac (a session)

Builds step 1 of the brief.

- `tauri.conf.json`: `bundle.resources: ["../../core/dist/querysolo/**"]` (the folder lands at `QuerySolo.app/Contents/Resources/querysolo/`), `bundle.macOS.minimumSystemVersion: "13.0"`, `bundle.targets: ["app", "dmg"]`, the DMG's window (`bundle.macOS.dmg`: the app on the left, the Applications shortcut on the right; a background image is optional and gitignored with the brand assets), the real icon set already in `icons/` (U4).
- `supervisor.rs`'s `sidecar_executable()` gains the middle case: `QUERYSOLO_SIDECAR` if set, else `<resource dir>/querysolo/querysolo` if it exists (`app.path().resource_dir()`), else `querysolo` on `PATH`; a Rust test for the order against a temp resource dir.
- The About panel (version, the sidecar's resolved path, a link to the releases page) — S8 says the version is shown there; the version-equality test (S7) holds `tauri.conf.json`, `Cargo.toml` and `querysolo/__init__.py` to one string.
- `cd app && npm run tauri build -- --target aarch64-apple-darwin`.

*What you see:* `app/src-tauri/target/aarch64-apple-darwin/release/bundle/dmg/QuerySolo_0.1.0_aarch64.dmg` and `…/macos/QuerySolo.app`. Drag it to Applications on your own Mac; it opens (your Mac trusts what you built). About names `…/Resources/querysolo/querysolo`. `du -sh QuerySolo.app` and `ls -la *.dmg` are the installed and download sizes for S3. `spctl --assess --type execute QuerySolo.app` says *rejected* — expected, nothing is signed yet.

*Where it fails first:* PyInstaller's folder contains hundreds of `.dylib` and `.so` files; Tauri copies resources without touching them, so this step works. It is the next step that cares about them.

---

## Step 3 — Signed and notarised, still on your Mac (a session, after 0.1–0.3)

The step the brief's §7 flags: Tauri signs `QuerySolo.app` and its `externalBin`, but not the executables and libraries under `Resources/`, and notarisation rejects an app with unsigned Mach-O files inside. So the build gets one extra pass, run *before* Tauri's own signing, and a hardened-runtime entitlements file for the Python inside.

- `app/src-tauri/entitlements.plist`: `com.apple.security.cs.allow-unsigned-executable-memory`, `com.apple.security.cs.disable-library-validation`, `com.apple.security.cs.allow-dyld-environment-variables` — the three a frozen CPython with C extensions needs under the hardened runtime (without them the sidecar dies on launch with a `dyld` or JIT error and no useful message). `bundle.macOS.entitlements` points at it.
- `app/scripts/sign-core.sh` (as built: every file `file` calls Mach-O): `find core/dist/querysolo -type f \( -perm +111 -o -name '*.dylib' -o -name '*.so' \) -exec codesign --force --options runtime --timestamp --entitlements entitlements.plist --sign "$APPLE_SIGNING_IDENTITY" {} +`, then the `querysolo` executable itself last. Tauri's `beforeBundleCommand` runs it. Deep-signing in the right order matters (inner libraries before the executable that links them); the script signs everything then the entry point.
- With the four variables in your shell (`APPLE_SIGNING_IDENTITY`, `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_KEY_PATH`; from 0.2 and 0.3), `npm run tauri build` signs the app, submits *the app* to Apple's notary service (a few minutes) and staples its ticket. It signs the DMG but does not notarise it, and `spctl` rejects a downloaded DMG that is not; so after the build, `xcrun notarytool submit <dmg> --key "$APPLE_API_KEY_PATH" --key-id "$APPLE_API_KEY" --issuer "$APPLE_API_ISSUER" --wait` and `xcrun stapler staple <dmg>` (done by hand 2026-10-11; the workflow does it in step 4).

*What you see:* `spctl --assess --type execute -vv QuerySolo.app` says *accepted, source=Notarized Developer ID*; `codesign --verify --deep --strict --verbose=2 QuerySolo.app` is silent; `xcrun stapler validate QuerySolo_0.1.0_aarch64.dmg` says the ticket is stapled. Then the clean account from 0.5: download the DMG, open, drag, launch — no right-click, no System Settings. First launch will pause while Gatekeeper reads every library (the §7 unknown; time it), second launch is the real spawn-to-ready.

*Where it fails first:* notarisation's rejection email lists each unsigned or wrongly-signed file by path; the script's `find` is what to fix. The other classic failure is a library signed without `--timestamp` or without `--options runtime`; the log names it.

---

## Step 4 — The workflow (a session)

`.github/workflows/release.yml`, triggered by a tag `v*`:

- A version job: the tag equals `querysolo/__init__.py`'s version and `tauri.conf.json`'s, else stop.
- The macOS job on `macos-15` (Apple silicon): checkout, uv, `uv sync --group freeze`, step 1's freeze, Node and Rust, the secrets into the environment (`APPLE_API_PRIVATE_KEY` written to a temp path for `APPLE_API_KEY_PATH`), `npm run tauri build -- --target aarch64-apple-darwin`, the DMG notarised and stapled (step 3), `spctl --assess` on the app and the DMG as a gate, the DMG and its `sha256` uploaded as artifacts. An Intel job is the same with `macos-15-intel` and `x86_64-apple-darwin` if the label is offered, `continue-on-error`.
- A release job: a *draft* GitHub Release for the tag with the DMG, the checksums and a body that names the sizes. Draft, so Hants tries it before it is public (S6).
- The PyPI job and the Ubuntu job from the brief's step 2, `continue-on-error` until they are set up, so the DMG never waits on them.

*What you see:* push `v0.1.0-rc1`; twenty minutes later a draft release with a DMG built by nobody's laptop. Download it on the clean account; the same checks as step 3 pass on a file that never touched your Mac. Delete the rc release after.

---

## Step 5 — First-run, on the DMG (small, but it is the persona's first minute)

Per N1, the installed app is the analyst's first sight of the product, so three things belong in the same session as the DMG:

- The welcome screen's first line for an installed app: "New project…" leads; "Open a folder…" second; the line about `QUERYSOLO_SIDECAR` and `npm run tauri dev` is developer text and appears only when the sidecar came from `QUERYSOLO_SIDECAR`.
- "Install the `querysolo` command" in Settings (S9): the Rust command that links `~/.local/bin/querysolo` to the bundled binary, with the `PATH` sentence when needed.
- The credentials story from the Dock (C1): the New project dialog's profile picker works with no shell, which is the whole reason C1 was built before ship; verify it on the clean account with a `~/.aws/credentials` present.

*What you see:* on the clean account, from download to a chart on `sample/orders.csv`, timed with a stopwatch, under three minutes, no terminal. That number goes into §6 and `/docs/install`.

---

## Step 6 — Publish

Tag `v0.1.0`, let the workflow make the draft, try the DMG once more on the clean account, publish the release, and put the DMG's link and the measured sizes into `/docs/install` and the README's install section (the "no installer yet" lines go). The tap and the cask (S6) can follow the same day: one file, `Casks/querysolo.rb`, pointing at the release's DMG and its sha256.

---

## What can be done before the Apple account arrives

Steps 1, 2, 4 (without the signing lines active), and the first-run work in 5. Only step 3 and the signed half of 4 wait on 0.1–0.4. If the enrolment takes its 48 hours, the freeze and the unsigned bundle fill them.

## Rough time

Step 0: an hour of yours plus Apple's waiting. Step 1: a day (the hidden-import hunt is the variable). Step 2: half a day. Step 3: half a day if notarisation accepts on the second try, a day if the resources signing needs iteration. Step 4: half a day. Step 5: half a day. Step 6: an hour. About four working days of sessions once the account exists.
