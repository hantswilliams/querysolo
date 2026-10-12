# Decisions for review — 2026-10-11: the release workflow

*Ship step 4 (`ship-dmg-steps.md`; the brief's step 2, `ship-v0-plan.md` §3.2, S4–S7, S14). The brief decides what `release.yml` builds and where it goes. These four are what it leaves open. Each box has a recommendation; tick Agree, or write the change. `release.yml` is written to the recommendations meanwhile, and nothing is tagged or published until these are ticked.*

## What step 3 settled that the workflow carries

- **The frozen core is signed before Tauri bundles it** (`sign-core.sh`, Tauri's `beforeBundleCommand`).
  - That runs before Tauri imports `APPLE_CERTIFICATE` into its own keychain.
  - So the workflow imports the `.p12` into a temporary keychain itself, first, and Tauri finds the identity there.
- **Tauri notarises the app, not the DMG.** A workflow step notarises and staples the DMG.
  - `spctl` must accept both, or the job fails.
- **`APPLE_API_PRIVATE_KEY`** (the `.p8`'s contents) is written to a temporary file, and `APPLE_API_KEY_PATH` names it.

## Decisions

**R1. The workflow can run without a tag, as a rehearsal: on a pull request that changes it, and by hand. A rehearsal builds, signs, notarises and checks everything, and publishes nothing.**
Why: a tag publishes to PyPI, and a PyPI version can never be uploaded twice. The first tag should be the first time the publish steps run, not the first time anything runs. A rehearsal's files are kept as the run's artifacts for 7 days, so the DMG can be downloaded and tried.
- [ ] Agree
- [ ] Change:

**R2. The first tag is `v0.1.0-rc1`.**
Before tagging, the versions move from `0.1.0.dev0` / `0.1.0` to:
- the core: `0.1.0rc1`
- `tauri.conf.json` and `Cargo.toml`: `0.1.0-rc.1`

The workflow compares the tag with the core and the app as PEP 440 versions, so `v0.1.0-rc1`, `0.1.0rc1` and `0.1.0-rc.1` are one version, and any other tag stops the run.
Why: the brief's gate names `v0.1.0-rc1`, and the version test (S7, amended in step 1) already spells the pre-release per ecosystem. Windows' MSI refuses a non-numeric pre-release; the Windows job is allowed to fail (S14), and it will, on the rc.
- [ ] Agree
- [ ] Change:

**R3. PyPI publishing waits for a click: the publish job runs in a GitHub environment named `pypi` with Hants as its required reviewer.**
Why: trusted publishing (S7) already needs an environment name on PyPI's side. Adding a reviewer means a tag builds everything and drafts the release, and the irreversible step waits until the DMG has been tried. The GitHub Release is a draft for the same reason (S6).
- [ ] Agree
- [ ] Change: publish on the tag with no review

**R4. The Intel DMG is built on `macos-15-intel` when the label exists, is allowed to fail, and goes into the release only if it passed.**
Why: S4 says Intel "if a runner offers it", not that it blocks a release. The Apple-silicon DMG, the `.deb` and the AppImage are what must pass.
- [ ] Agree
- [ ] Change: no Intel build in Day 0

## What Hants does, once (before the first tag, not before a rehearsal)

1. **PyPI** → the `querysolo` project → Publishing → add a GitHub publisher:
   - owner `hantswilliams`
   - repository `querysolo`
   - workflow `release.yml`
   - environment `pypi`
2. **GitHub** → the repository → Settings → Environments → New environment `pypi`. If R3 is agreed, add yourself as a required reviewer.
