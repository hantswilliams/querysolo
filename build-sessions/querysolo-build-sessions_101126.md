# QuerySolo build session — 2026-10-11

*Ship step 3 (`ship-dmg-steps.md`): a DMG signed with the Developer ID and notarised by Apple, on Hants' Mac. Branch `ship/signing`, cut from `main` at `9066ebe`. The signing found that S2 (the extensions bundled) cannot stand on macOS; `decisions-for-review_101126.md` X1–X4 amend it, all four agreed by Hants the same day.*

## 0. Hants, before the session

- The Developer ID Application certificate in the login keychain (`security find-identity -v -p codesigning`: one valid identity, team `C8GPBEE4QF`), exported as a `.p12`.
- An App Store Connect API key (`.p8`), kept in the repository root, gitignored by name.
- Six repository secrets: `APPLE_CERTIFICATE`, `APPLE_CERTIFICATE_PASSWORD`, `APPLE_SIGNING_IDENTITY`, `APPLE_API_KEY`, `APPLE_API_ISSUER`, `APPLE_API_PRIVATE_KEY` (the `.p8`'s contents; the workflow writes it to a file for `APPLE_API_KEY_PATH`).
- The four variables Tauri reads in the local `.env` (gitignored, never tracked).

## 1. Signing the frozen core

- `app/src-tauri/entitlements.plist`: the hardened runtime's three exceptions (`allow-unsigned-executable-memory`, `disable-library-validation`, `allow-dyld-environment-variables`); `bundle.macOS.entitlements` points at it.
- `app/scripts/sign-core.sh`, Tauri's `beforeBundleCommand`: every Mach-O file under `core/dist/querysolo/` (found with `file`, not by extension), the libraries first and the executable last, with `--options runtime --timestamp` and the entitlements. Without `APPLE_SIGNING_IDENTITY`, or off macOS, it does nothing, so an unsigned build and the Linux packages are unchanged.
- 55 libraries and the executable signed in about 19 s; `codesign --verify --strict` passes on each one checked.

## 2. The extensions cannot be both (X1–X4)

Tested against all five extensions:

| The file | `codesign` | DuckDB |
|---|---|---|
| as shipped (534 bytes of DuckDB's metadata and signature after the library) | refuses: "main executable failed strict validation" | loads |
| cut back to the end of `__LINKEDIT` | signs and verifies | refuses: "The metadata at the end of the file is invalid", even with `allow_unsigned_extensions` |
| cut, signed, the 534 bytes put back | verification fails | loads with `allow_unsigned_extensions` |

The notary service opens nested archives, so packing them does not help. Hants agreed X1–X4:

- **X1, X2:** no extensions in the freeze on any platform; `init` downloads them as the CLI always has.
- **X3:** a failed download no longer stops `init`.
  - `install_extensions` raises `ExtensionsMissing` with the sentence and DuckDB's reason (the `(ERROR …)` it ends a failed download with, e.g. "Could not establish connection").
  - `init` catches it, makes the project, exits 0 and prints the sentence.
  - `Engine`, on a failed `LOAD`, tries the download once, then raises the sentence.
  - `_open` and `serve` print it with no traceback.
  - The app needs no change: it already shows `init`'s output in a notice and a sidecar's early exit as its error.
- **X4:** `freeze/build.py --check` runs `init` with the network into the empty HOME (it must say "installed DuckDB extensions"), and every later step offline. `lay_out_extensions`, `duckdb_target` and `--extensions-from` are gone.

The bundled extensions from the earlier freezes were moved out of `core/dist` to the session's scratchpad before signing.

## 3. Notarised

- `npm run tauri build -- --target aarch64-apple-darwin` with the `.env` loaded.
- **The first run failed at notarisation.** `APPLE_API_KEY_PATH` held a bare file name, and notarytool runs from `app/src-tauri`. It now holds the absolute path, and the key file is `chmod 600`.
- **The second run:**
  - The app was accepted (submission `4bedc1b1-…`) and its ticket stapled.
  - `spctl --assess --type execute -vv`: *accepted, source=Notarized Developer ID*.
  - `codesign --verify --deep --strict`: OK.
  - `stapler validate`: OK.
- **Tauri signs the DMG but does not notarise it.** `spctl --assess --type open` on the DMG said *rejected, source=Unnotarized Developer ID*.
  - Done by hand: `xcrun notarytool submit <dmg> --wait` (accepted, `99214bcd-…`), then `xcrun stapler staple`.
  - The DMG is now *accepted, source=Notarized Developer ID*, with its ticket stapled.
  - `release.yml` (step 4) must do the same.
- `QuerySolo_0.1.0_aarch64.dmg`: 88 MB. This build was made before X1's code, from a core with no extensions folder.

## 3a. Rebuilt from this session's core

- The app was notarised (`4715b9ff-…`) and stapled. The DMG was notarised by hand (`0a57d76f-…`) and stapled.
- `spctl` accepts both as *Notarized Developer ID*, and `codesign --verify --deep --strict` passes on the app.
- Sizes: the DMG is 88 MB, and the installed app 205 MB (was 292 MB for the core alone with the extensions).
- The signed core inside the app, under the hardened runtime:
  - `--version` answers.
  - Offline, `init` prints X3's sentence and exits 0.
  - From an empty HOME with the network, `init` downloads the five extensions and `sql "select 42"` answers. So the Apple-signed process loads DuckDB-signed extensions under `disable-library-validation`, as X1 assumed.

## 4. Tests

| Gate | Result |
|---|---|
| `tests/test_step0_skeleton.py` | 8 passed. Two new tests: `init` offline makes the project, prints X3's sentence and exits 0, and opening it fails with the same sentence; a project without its extensions downloads them once on open (the download stood in for by a copy from the cache) and not again |
| core suite | 285 passed, 7 skipped (first run, alongside the freeze: the startup-budget timing test failed under load; alone and in a quiet rerun it passes) |
| `cargo test` | 15 passed |
| `freeze/build.py` | 206 MB after the trim (was 292 MB with the extensions) |
| `freeze/build.py --check` | green: `init` downloaded into the empty HOME; import, tables, sql, question, run, lineage offline; `audit network` zero |
| the frozen binary, offline | `init` exits 0 with the sentence; `tables list` exits 1 with `cannot open:` and the same sentence, no traceback |
| `ruff check`, `ruff format --check` | clean |
| README status check | current |

## 5. Docs

- `ship-v0-plan.md`: amendment notes on S2 and §3.1; the pipeline drawing and the versions table lose the extensions.
- `ship-dmg-steps.md`: renamed to QuerySolo throughout, and corrected:
  - step 1's extension lines;
  - 0.3 and 0.4 for `APPLE_API_PRIVATE_KEY` and a key path that must be absolute;
  - step 3: the script as built, and the DMG's own notarisation;
  - step 4.
- `PRIVACY.md`, `/docs/install`: the one download (about 80 MB), the same in the app, and what happens offline.
- README and `status.ts`: "the extensions bundled" removed from the installers line.
- The `engine.py`, `entry.py` and dbt plugin comments.

## 6. Open

- The clean-Mac test: download the DMG on another Mac or user account, open it, launch, and time the first launch. Hants has no second Mac yet.
- Step 4, `release.yml`: the DMG's notarisation and staple as above; `APPLE_API_PRIVATE_KEY` to a temp file.
- The open-time sentence starts "cannot open: the project is ready, but …". X3 asked for the same sentence and it is that, but it reads oddly after "cannot open". Also, any failure of the download gets "could not reach it", even one that is not the network's (seen: a HOME that does not exist, "Can't find the home directory"). To review.
- Not committed: everything on `ship/signing`.
