# Lakelet build session — 2026-09-24

*Ship, step 0: the freeze (`ship-v0-plan.md` S1–S3, walked in `ship-dmg-steps.md` step 1) and, later the same day once step 0 was green on the Mac (292 MB after the trim, `--check` passed), step 1: the bundle (S4–S8, `ship-dmg-steps.md` step 2). Both built and gated on Linux in the container; the Mac runs are Hants'. Earlier the same day: `decisions-for-review_092426.md` N1–N3 (persona and order) and `ship-dmg-steps.md`, both written, neither built.*

## 1. `LAKELET_EXTENSION_DIR` and the five extensions (`core/lakelet/engine.py`, `audit.py`, `dbt/plugin.py`, `cli`)

Every DuckDB connection the core opens now comes through `engine.connect()`, which runs `SET extension_directory` to the bundled folder when `LAKELET_EXTENSION_DIR` is set (S2) and does nothing otherwise, so the CLI from PyPI keeps D33 as it is. dbt-duckdb opens its own connection; Lakelet's plugin sets the same setting in `configure_connection`. `init` says "using the bundled DuckDB extensions in … (no download)". One fact S2 did not have: `iceberg` pulls in `avro` on its first LOAD (manifests are Avro) and would fetch it on its own — so the bundle carries **five** extensions, `INSTALLED_EXTENSIONS = EXTENSIONS + ("avro",)`, and `init`'s one download installs the five too. `test_the_bundled_extension_folder_is_used_and_nothing_is_fetched` lays a temp folder out as DuckDB expects, hides `HOME`, and runs `init` and a query from it.

## 2. The freeze (`core/freeze/`)

`lakelet.spec` (PyInstaller one-directory, S1), `entry.py` (sets `LAKELET_EXTENSION_DIR` from its own location when unset), `build.py` (the three steps: PyInstaller, the extensions for the running DuckDB's version and platform — downloaded, or `--extensions-from ~/.duckdb/extensions` for a build with no network, which is how the container built — then S3's trim; `--check` is the gate). A `freeze` dependency group; `core/build/` gitignored (`dist/` already was). The hidden-import list is narrow on purpose: `pyiceberg.catalog.rest` and `pyiceberg.io.pyarrow` only (the Glue, Hive and fsspec catalogs would drag boto3 and s3fs in), dbt's adapter and plugin loader, dulwich, SQLite's dialect; excluded: boto3/botocore (26 MB; pyiceberg imports it inside a function for SigV4), psycopg (the Postgres store is the team catalog's), cryptography via urllib3's pyOpenSSL contrib, the fsspec remotes, dbt-duckdb's other plugins. The trim: pyarrow's Flight library (30 MB), Gandiva, tests, headers; zstandard's cffi copy (12 MB); babel's locale data to root and English (30 MB — dbt's agate imports babel). S3 assumed `libarrow_substrait` was optional; it is not — pyarrow's core `lib` links against it (6 MB, stays).

The gate found four things in order, each fixed: `pyparsing` imports `unittest` (un-excluded); the substrait library (above); dbt-duckdb lists its built-in plugins with `os.listdir` on its package folder, so the folder is shipped as files (`collect_data_files(..., include_py_files=True)`); and `audit network` re-ran itself with `python -m lakelet.audit`, which a frozen binary cannot — frozen, it spawns `lakelet audit _run` (a hidden command, the same entry point). One more, in the gate itself rather than the freeze: blocking the network with `HTTP_PROXY` pointed at a dead port made DuckDB route the *loopback* catalog through it too; `NO_PROXY=127.0.0.1` fixes the gate, and a machine with a corporate proxy and no loopback exemption would hit the same — an open item in `TASKS.md`.

**Gate, on Linux:** `freeze/build.py --check` runs `init`, `import`, `tables list`, `sql`, `question save`, `run` (dbt, one model built), `lineage --all` and `audit network` from an empty `HOME` with the network unreachable — "nothing left the machine", `init` on the bundled folder. `tests/test_frozen.py` runs the same behind `LAKELET_BIN` and is skipped without it. Playwright **32** against the frozen sidecar (`LAKELET_SIDECAR=core/dist/lakelet/lakelet`; `tests/sidecar.ts` takes the fixtures' python from the venv when the sidecar has none beside it; one timing flake on `step2-import` under two workers, passing alone). Core **268** (12 skipped).

**Numbers (Linux x86_64, for §6; the Mac's are the ones the docs will say):** `dist/lakelet` 480 MB before the trim, **403 MB** after — the five extensions 122, pyarrow 107, DuckDB's library 58, the executable with the bytecode archive 31, zstandard 12, the rest under 10 each. That is above S3's 250–300 estimate; the extensions alone are 122 MB uncompressed on Linux (the macOS arm64 files are smaller), and the compressed DMG is the number that matters against "under 200 MB". Spawn-to-ready from the frozen sidecar ~1.7 s with ten sidecars starting at once on this box, against ~1.4 s for the venv the same way; the Mac's single-sidecar figure is the budget's.

## 3. For Hants, on the Mac

    cd core
    uv sync --group freeze
    uv run --group freeze python freeze/build.py        # downloads the five extensions for osx_arm64
    uv run --group freeze python freeze/build.py --check
    du -sh dist/lakelet

Then the app against it, once: `cd ../app && LAKELET_SIDECAR=$PWD/../core/dist/lakelet/lakelet npm run e2e`, and `npm run tauri dev` with the same variable to read spawn-to-ready in the status strip. What breaks on macOS and not here is most likely a dylib pyarrow or DuckDB loads by name; the traceback names it and the fix is one line in the spec. Step 1 (the bundle) follows.

## 4. Open, after step 0

The Mac numbers (in: 352 MB before the trim, 292 MB after, `--check` green, 2026-09-24). `HTTP_PROXY` and loopback (above). The `step2-import` timing under load with the slower-starting frozen sidecar — a longer `openReady` timeout if it repeats on the Mac.

## 5. Step 1, the bundle (`app/src-tauri`, `app/src`, `core/freeze/build.py`)

**The sidecar's resolution order** (S4, S8): `supervisor::sidecar_executable(resource_dir)` returns `LAKELET_SIDECAR` when set, else `<resources>/lakelet/lakelet` (`.exe` on Windows) when that file exists, else `lakelet` for `PATH` to find. `SidecarConfig::new` keeps passing `None` (the tests and `tauri dev` run the way they did); the app's setup passes `app.path().resource_dir()`. One cargo test, `the_sidecar_is_the_variable_then_the_bundled_one_then_path`, lays a resource folder out in a temp dir and checks the three cases in order. Cargo **14**.

**`tauri.conf.json`**: `bundle.targets` `["app", "dmg", "deb", "appimage"]`, `bundle.resources` maps `../../core/dist/lakelet/` to `lakelet/` inside the bundle (`Contents/Resources/lakelet/lakelet` on macOS, `/usr/lib/Lakelet/lakelet/lakelet` in the deb), `macOS.minimumSystemVersion` 13.0 (S6). The build fails plainly when `core/dist/lakelet/` is missing — step 0 has to have run first, which is the order `ship-dmg-steps.md` gives.

**About** (S8): a `#[tauri::command] about` returns the app's version, the sidecar's path and where it came from — `environment` (the variable), `bundled` (under the resource dir) or `path`. `session.ts` `about()`, and an About row in Settings (`setting-about`, the path in a right-to-left-ellipsised `code` so the tail stays readable, a link to Releases). Vitest **126** (+1, the row).

**The version test** (S7): `tests/test_step0_skeleton.py::test_the_app_and_the_core_agree_on_the_version` reads `core/pyproject.toml`, `app/src-tauri/tauri.conf.json` and `Cargo.toml` and compares the release triple — S7 as written wanted the strings equal, and they cannot be: Python spells a pre-release `0.1.0.dev0` and Cargo/Tauri `0.1.0-dev.0` or nothing at all, so the amendment is *same release triple, the pre-release tag in each ecosystem's own spelling*; a core without a tag requires an app without one, so a release cannot ship with a `.devN` core by accident. Skeleton tests 6.

**The trim, one more thing** (`build.py`): the first Linux bundle failed with "resource path libarrow_flight.so.2500 doesn't exist" — S3's trim removed the library and left PyInstaller's symlink to it dangling. Removing dangling links was not enough: Tauri's bundler *dereferences* symlinks, and PyInstaller links every pyarrow library into `_internal/` under a second name, so the deb carried pyarrow twice (+99 MB installed). The trim now removes every symlink in `dist/lakelet/` — and the Mac gate showed the two platforms want different things: on Linux the modules' runpath is `$ORIGIN` (`pyarrow/`, where the real files are), so the links simply go; on macOS PyInstaller rewrites every rpath to `@loader_path/..` (`_internal/`, where the *links* were), so the first Mac run failed with `Library not loaded: @rpath/libarrow_python.2500.dylib`, and there the file now moves to where its link was. One copy of each either way; the gate is what proves it per platform. `folder_size` counts each inode once so the printed sizes are the bundle's, not the links'. **Hants' Mac dist needs one more `build.py` run** for this, before the bundle.

**The extension download, second time on the Mac**: DuckDB's own `INSTALL` got an HTTP 302 from `http://extensions.duckdb.org` (the morning's run had worked; the network answers a redirect to https now, and DuckDB's built-in downloader follows none). `lay_out_extensions` now copies the five from the machine's own `~/.duckdb/extensions/<version>/<platform>/` first — `lakelet init` and the app put them there, the same files — and only downloads what is not there, falling back to `LOAD httpfs` and `INSTALL … FROM 'https://extensions.duckdb.org'` when plain http fails. `--extensions-from` still names another folder.

**Dry run, Linux x86_64** (`npm run tauri build -- --bundles deb`, no signing): **`Lakelet_0.1.0_amd64.deb` 160 MB**, **388 MB installed** (the same as `dist/lakelet` after the symlink trim — nothing duplicated, nothing missing); the gate passes against the sidecar extracted from the deb (`LAKELET_BIN=<extracted>/usr/lib/Lakelet/lakelet/lakelet uv run --group freeze python freeze/build.py --check` → "the quickstart ran from an empty HOME with no network"). tsc, Vitest 126, cargo 14, Playwright unchanged from §2.

## 6. For Hants, on the Mac (step 1)

    cd core
    uv run --group freeze python freeze/build.py            # again: the new trim removes the symlinks
    uv run --group freeze python freeze/build.py --check
    du -sh dist/lakelet
    cd ../app/src-tauri && cargo test && cd ..
    npm run tauri build -- --target aarch64-apple-darwin

Expect `Lakelet.app` and `Lakelet_0.1.0_aarch64.dmg` under `app/src-tauri/target/aarch64-apple-darwin/release/bundle/{macos,dmg}/`; `Contents/Resources/lakelet/lakelet` inside the app. For §6 of the brief: the `.app` and `.dmg` sizes, the About row's path and "bundled", spawn-to-ready in the status strip from the installed app, and `spctl --assess --type execute Lakelet.app` — *rejected* is the expected answer until step 3 (signing). Opening it: right-click → Open, or `xattr -dr com.apple.quarantine`.

## 7. Open, after step 1

The Mac `.app`/`.dmg` numbers and the About path. Signing and entitlements (step 3) wait on the Apple enrolment; `release.yml` (step 4) and first-run (step 5) after. The Linux `.deb` is a dry run, not a deliverable: no `.desktop` review, no AppImage tried.
