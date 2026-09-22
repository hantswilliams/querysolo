# Lakelet — decisions for review, September 21, 2026

*From Hants, looking at the Questions screen in Simple mode after the September 20 batch: a question card offers Refresh and History, and no way to see the answer. One item. It belongs to no brief (the versions round's G7 put questions on the Models screen; the app brief's screen 8 gave them Simple words; neither said how the rows are reached). Tick Agree or write the change. Nothing is built until it is decided.*

*Added the same evening: **C1 to C3**, on where a bucket's credentials live, from Hants' question at the New project dialog — "is there a way of keeping the keys in a simple, secure way, without typing them every time?"*

---

## What exists today

A saved question is a dbt model, so its answer is a view or a table in the catalog: `by_customer` is in the explorer as "196 rows · local", `big_orders` as "view". The rows are reached the Technical way — click the table in the explorer and **Sample rows** (five rows, `lakelet tables sample`), or type `select * from by_customer` in the SQL box and Run (every row, with the verdict, the chart and the grid). The card says "Up to date. Ready in about under a second." and offers **Refresh** (which rebuilds it) and **History** (its versions). In Simple mode nobody will find the rows. The wording bug on the card ("about under a second") is fixed with this file; a sub-second estimate says "Ready right away."

---

**Q1. Every question card gets "See the answer", which opens the Tables screen with `select * from <question>` run — the verdict, the chart and the rows — so a question is asked and answered in one click.**

*Why it comes up:* the screenshot. The Simple vocabulary calls these questions, and a question you cannot see the answer to is not one. The pieces exist: the workspace runs SQL and shows the rows with the gauge's sentence and the auto-chart; the question is a name in the catalog.

*Recommend:* one button on the card — **See the answer** (Technical: **Rows**) beside Refresh — which switches to the Tables screen, puts `select * from <name>` in the SQL box and runs it, so the results pane shows the answer with the verdict line above it and the chart when the answer is two columns; the line beside it is `lakelet sql 'select * from <name>'`, as every action's is. The box is editable, so the next question is one edit away, which is how a person learns SQL from a question they already understand. A question that has never been refreshed has no rows yet: the button says **Refresh, then see the answer** and does both. The Technical model detail gets the same **Rows** button, since a `view` model's rows are otherwise a detail away.

*Not chosen:* rows inside the card (five rows, no chart, and the card becomes a screen); a separate "Answers" screen (the workspace is the answer screen; a sixth screen would say the app has two places for rows); a dialog (it would hide the editor, which is the way on to the next question).

*Gates:* Vitest for the card's button and the never-refreshed case; `save-question.spec` extended — save, then **See the answer**, and the grid has the question's rows with the verdict; `/docs/app`'s Simple paragraph.

- [x] Agree
- [ ] Change:

---

# Credentials for a bucket: where they live

## What exists today, and why the dialog says what it says

The rule since the first brief (D36) is that Lakelet never holds a key: the core reads AWS credentials from the environment it was started in — `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY`, or `AWS_PROFILE` naming a profile in `~/.aws/credentials` — and, when the environment has none, falls back to the AWS SDK's own default chain (DuckDB's `credential_chain` secret, pyarrow's S3 file system). No key is ever written to `lakelet.toml`, which is in git. The New project dialog's line ("set them in the shell that starts the app and restart the core") is that rule said out loud, and it is where the pain is:

- **A Mac app launched from the Dock or Finder has no shell.** It gets a near-empty environment, so under an installer (session 10) the variables can never be there; only `npm run tauri dev` from a terminal has them. The line is already wrong for the app it will become.
- **The default chain half-solves it.** If the AWS CLI is installed and `aws configure` has been run once, `~/.aws/credentials` has a `[default]` profile and the chain finds it with nothing in the environment — from the Dock too. The app's health line would then say `source: profile`... except it says `none`, because `describe()` only looks at the environment; the chain still works, the line is just wrong. And a person with several profiles (work, personal, a client) has no way to name one for a project.
- **The only thing Lakelet ever needs is a name or a pair of keys, per machine.** Which project uses which account is a per-person, per-machine fact; it does not belong in a file the team shares.

## The options, plainly

**O1. Keep it as it is: environment only.** Nothing to build, nothing to secure. Fails the Dock (above), and "restart the core after exporting two variables" is not something a Simple-mode user will do.

**O2. Lean on the AWS credential chain, and let Lakelet name the profile.** The keys live where AWS puts them (`~/.aws/credentials`, mode 600, or `aws sso login`'s short-lived cache, or an instance role); Lakelet stores only a *profile name* per project and hands it to the core as `AWS_PROFILE` when it starts the sidecar. The dialog and Settings get a **profile** field with the profiles read from `~/.aws/config`; the "no credentials" line becomes "run `aws configure` once, or pick a profile". Nothing secret is ever written by Lakelet, the SDK's rotation and SSO work unchanged, and the audit story stays "your keys, your files". The cost is that the AWS CLI (or a hand-written `~/.aws/credentials`) is a prerequisite for a private bucket — which every person with a private bucket already has.

**O3. The operating system's keychain, through the shell.** The app asks for the key pair once (a dialog), the Tauri shell stores it in the macOS Keychain or the Linux Secret Service under a Lakelet item (the `keyring` crate), and injects it into the sidecar's environment at start; the core stays environment-only and never touches the keychain. Secure (the OS encrypts it, per user, behind login), no file written by Lakelet, no AWS CLI needed. The costs: a second place keys live, which a security reviewer will ask about; macOS prompts "Lakelet wants to use your keychain" on every launch of an unsigned build (signed builds prompt once); Linux needs a running Secret Service (GNOME Keyring or KWallet), which a headless box lacks; and long-lived static keys in a keychain are exactly the thing AWS is steering people away from (SSO, roles).

**O4. Lakelet's own file, `~/.lakelet/credentials` at mode 600.** The same as `~/.aws/credentials` but ours. Strictly worse than O2 — a second plaintext secret file, with none of the SDK's tooling — listed so it is seen and set aside.

**O5. In `lakelet.toml`.** No. It is committed, and D36 says so.

**O6. Vended, short-lived credentials from a hosted catalog** (STS, prefix-scoped). The right long-term answer and the P2 direction (September 20): the laptop never holds a long-lived key at all. It needs the Team tier's catalog, which does not exist yet; nothing to build now, but the design should not make it harder.

---

**C1. Lakelet stores no key. A project names an AWS profile; the shell hands it to the core; the keys stay in AWS's own files or its SSO cache (O2).**

*Recommend:* the profile name is a per-machine app setting, kept by the shell next to `recent.json` as `projects.json` (`{"/Users/hants/acme": {"profile": "acme-data"}}`) — not in `lakelet.toml`, because two teammates use two profile names for one bucket, and not in `.lakelet/`, because the core does not choose its own environment. The shell sets `AWS_PROFILE` on the sidecar when the project has one. In the app: a **Profile** picker in the New project dialog's bucket section and in Settings under a new **Bucket** row, listing the profiles found in `~/.aws/config` and `~/.aws/credentials` (names only, read by the shell), with **default** and **none** as choices; **Check the bucket** runs with the chosen one. The CLI is `lakelet --profile <name>` or `AWS_PROFILE` as today, since a terminal has an environment. `describe()` reports `profile` whenever the chain would use one (a `[default]` section exists, or a profile is named), so the health line and the dialog stop saying "none" when there are credentials. `/docs/remote` gains a short "Credentials" section: `aws configure` once, or `aws sso login`, then pick the profile.

*Not chosen:* O3 now (a second key store, the keychain prompts, and it stores the kind of key AWS is retiring; it can be an option later for people with no AWS CLI, and O2 does not preclude it); O4 and O5 (above); asking for keys in the dialog and holding them only for the session (fine for a demo, not for a daily tool, and it teaches people to paste secrets into apps).

*Gates:* `cargo test` — the shell reads profile names from a temp `~/.aws/config`, remembers a project's choice, passes `AWS_PROFILE` to the fake sidecar (recorded in `fake-args.txt`); pytest — `describe()` says `profile` for a `[default]` credentials file and names a chosen profile; Vitest for the picker; the P1 Playwright test unchanged. `PRIVACY.md`'s "what leaves the machine" line names the profile file as read, never written.

- [x] Agree
- [ ] Change:

---

**C2. The dialog's "no credentials" line changes to say what to do on this machine, and the app never asks for a key.**

*Recommend:* with C1, the line under the prefix field becomes one of three sentences: "Using profile *acme-data*." / "No profile chosen; the AWS default profile will be used." / "No AWS credentials on this machine: run `aws configure` in a terminal once, or tick public bucket for a dataset that needs none." — the last with the `aws configure` command as a copyable line, as every action has. The word "restart the core" goes: the shell starts the sidecar with the chosen profile, so a new project needs no restart, and changing the profile of an open project restarts its core through the existing restart path.

*Gates:* Vitest for the three sentences; `/docs/app`'s New project paragraph.

- [x] Agree
- [ ] Change:

---

**C3. The keychain (O3) is deferred to the ship brief as a candidate, not built now.**

*Recommend:* record it in `ship-v0-plan.md`'s open list as "keys for people without the AWS CLI: the shell stores a pair in the OS keychain and injects it", to be decided after the first outsiders try O2 and say whether `aws configure` was a wall. If it is built, the core still never reads the keychain; it stays environment-only, so the audit and privacy story do not change.

- [x] Agree
- [ ] Change:

---

---

# The `data/` folder in a project

## What it is

Hants, looking at a project folder: `data/` is empty and nothing uses it; drop it. It turns out Lakelet does not create it. `lakelet init` writes `lakelet.toml`, `AGENTS.md`, `dbt_project.yml`, `models/`, `macros/`, `warehouse/`, `.lakelet/`; the first saved question adds `tests/generic/returns_rows.sql`. The empty `data/` appears on the first `CREATE TABLE` through DuckDB's Iceberg extension — it makes `<location>/data/` before the catalog has told it the location, so the path is `data/` relative to the process's **current directory**, and the real files then go to `warehouse/main/<table>/data/` as they should (traced 2026-09-22 with an audit hook: no Python code makes it; a `lakelet -C project sql 'create table …'` run from another folder leaves the empty `data/` in *that* folder). On Hants' Mac there is one in `app/`, `app/src-tauri/` and `core/` — wherever a process was started from. The app's shell does not set the sidecar's working directory, so the sidecar inherits the app's: the project folder under `tauri dev` only by accident, and `/` for an app launched from the Dock, where the mkdir will fail and it is not yet known whether the CREATE fails with it.

**F1. The shell starts the sidecar with the project folder as its working directory, and the core removes the empty `data/` the extension leaves there.**

*Recommend:* two small things. The shell passes `current_dir(project)` to the sidecar (and `lakelet serve`, `run`, `sql` and the rest already run from the folder the user is in, or `-C`), so a Dock-launched app has a writable, sensible cwd — this is a fix whatever else is decided, since an installed app must not depend on `/` being writable. Then the engine, after any statement that writes, removes `<cwd>/data` when it exists, is empty, and is not the project's own `warehouse/…` path — an empty folder it did not create and nothing can be in. A pytest creates a table from a temp cwd and asserts no `data/` is left; the cargo two-windows test asserts the sidecar's cwd in `fake-args.txt`. An upstream issue on duckdb/duckdb-iceberg with the repro, linked from `TASKS.md`, so the workaround can go when the extension stops doing it.

*Not chosen:* `chdir` inside the core to `.lakelet/` so the litter lands out of sight (relative paths in a user's SQL — `read_csv('orders.csv')` — would silently stop meaning the project folder); documenting it and leaving it (an empty folder with no explanation in every project, and in every folder a CLI was run from).

*Gates:* pytest for the clean cwd; cargo for the sidecar's cwd; the installer smoke test in the ship brief (§6) creates a table from a Dock launch.

- [x] Agree
- [ ] Change:

---

*Order, if agreed: C1 and C2 together (a day: the shell's profile list and setting, the sidecar's environment, `describe()`, the picker, the sentences, the docs), before P2's brief and before ship, since the installers' first-run story depends on it.*
