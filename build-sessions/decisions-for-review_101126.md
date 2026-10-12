# Decisions for review — 2026-10-11: the DuckDB extensions and notarisation

*Ship step 3 (`ship-dmg-steps.md`, a signed and notarised DMG) found that S2 in `ship-v0-plan.md` cannot stand on macOS. Each box has a recommendation; tick Agree, or write the change. The signing work that does not depend on these (the entitlements, the script that signs the frozen core, the Tauri config) goes ahead on `ship/signing` meanwhile.*

## What was found

S2 bundles the five DuckDB extensions (`iceberg`, `httpfs`, `excel`, `aws`, `avro`; 82 MB) inside the app, so the installed app never downloads anything. Notarisation requires every Mach-O file in the app to carry a Developer ID signature. The extensions are Mach-O libraries. Tested on 2026-10-11 against all five:

- **As shipped,** each extension has 534 bytes of DuckDB metadata and signature appended after the library. `codesign` refuses to sign it ("main executable failed strict validation").
- **Cut back to the library's end,** Apple signs and strictly verifies it. DuckDB then refuses to load it, even with `allow_unsigned_extensions`: "The file is not a DuckDB extension. The metadata at the end of the file is invalid."
- **Cut, signed, and the 534 bytes put back:** DuckDB loads it with `allow_unsigned_extensions`, but Apple's verification fails, so notarisation would reject it.

No file is both. Packing them in an archive inside the app does not help: the notary service opens nested archives and checks the code in them. Hiding them in a format it does not open would defeat the point of notarisation.

## Decisions

**X1. Amend S2: the extensions are not bundled. `querysolo init` downloads them once from `extensions.duckdb.org`, as it did before the bundle step.**
Why: it is DuckDB's normal path. DuckDB verifies its own signature on each extension at load. The notarised app can load them under the `disable-library-validation` entitlement the bundled Python needs anyway. `PRIVACY.md` already names this one download.
Cost: the installed app is no longer fully offline on first use. A fully offline install becomes option C (DuckDB built with the extensions compiled in), done when someone needs it.
- [x] Agree — Hants, in conversation, 2026-10-11
- [ ] Change:

**X2. Every platform the same: the Linux `.deb` and AppImage do not bundle them either.**
Why: one behaviour, one sentence in the docs, one gate. The Linux packages are not notarised and could keep the bundle, but two behaviours means two first-run stories and two sets of tests, for a platform with no users yet.
- [x] Agree
- [ ] Change: macOS only; Linux keeps the bundled extensions

**X3. When `init` cannot download them, the project is still made, and the command says so in a sentence.**
Today a failed download leaves a project folder with no extensions, and a second `init` refuses with "already a project". Instead:
- `init` catches the failure, finishes the project, exits 0, and prints: *the project is ready, but QuerySolo needs a one-time download of DuckDB's extensions (about 80 MB) from extensions.duckdb.org and could not reach it (the reason); it will try again the next time the project opens.*
- Opening a project whose extensions are missing tries the download once.
- If that fails too, the open fails with the same sentence, not a traceback.
- The app's New project dialog shows the sentence as it is.

Why: the first minute is the persona's whole product (N1). A traceback, or a project that can never be fixed by running `init` again, is the worst first run.
- [x] Agree
- [ ] Change:

**X4. The freeze gate (`freeze/build.py --check`) changes with X1.**
- `init` runs with the network reachable, into the gate's empty `HOME`, and must report the download.
- Every later step runs with the network unreachable, as now, and `audit network` must still read zero.
- A new core test checks X3's sentence: `init` with the network unreachable makes the project and prints the sentence.

Why: the gate still proves that nothing but that one download leaves the machine.
- [x] Agree
- [ ] Change:

## What this changes elsewhere

- `ship-v0-plan.md` S2 and §3.1: the bundle drawing loses `extensions/`.
- `ship-dmg-steps.md` step 1: the extension lines.
- `core/freeze/entry.py` and `engine.py`'s docstrings: no bundled folder by default; `QUERYSOLO_EXTENSION_DIR` stays for tests and a future offline build.
- `/docs/install` and `PRIVACY.md`: the one download, its size, and what happens offline.
