# Lakelet — the remote catalog round

*September 23, 2026 · A brief for the catalog beyond the laptop · Follows `ship-v0-plan.md` (held) and decision P2 of `decisions-for-review_092026.md` (skipped, "needs more thought") · Amends `docs/lakelet-architecture.md` §3.3–3.4 and `lakelet.toml`'s `[catalog]` section, which already names the three modes (`local | team | external`) without building two of them · Tick Agree or write the change on each of R0 to R6. Nothing is built until it is decided.*

## 0. The idea in one paragraph

Every table operation in Lakelet already goes over the Iceberg REST protocol: DuckDB is `ATTACH`ed to a REST catalog, pyiceberg talks to the same one, dbt's connection gets the same address. It just happens that the catalog is our own FastAPI server on SQLite, bound to loopback, started by `lakelet serve`. So "a remote catalog" is not a new subsystem; it is the question of *which* REST catalog a project points at and *who runs it*, and the answer has three layers that should land in this order. First, **bring your own catalog**: a project's `lakelet.toml` names a REST catalog someone else runs — Cloudflare R2 Data Catalog, Apache Polaris (or Snowflake's hosted Open Catalog), Lakekeeper, AWS S3 Tables or Glue — and the core points its clients there instead of starting its own. That is the step that makes "two people, one bucket, the SQL in git" real, and it costs configuration, auth plumbing and a conformance probe, because the REST spec has optional corners that Lakelet's verbs lean on. Second, **ship our own catalog as something you can run**: it exists, the smoke test runs it against Spark and Trino, and on Postgres with real auth and credential vending it is the self-host tier and the very binary a hosted tier would run. Third, **host it** — P2's Team tier — which stays where P2 put it, after ship, in `team-v0-plan.md`, once the first two layers have shown what people actually connect to. The reasoning for that order is competitive: a hosted REST endpoint is becoming a commodity (R2 sells one for a few dollars a month, Snowflake gives Open Catalog away, AWS bundles S3 Tables), so Lakelet's reason to exist above the catalog is the layer the app already draws — the gauge across everyone's machines, the questions, the lineage, the history that burst will be priced from — and that layer should work over *any* REST catalog before it is tied to ours. A spike (R0) comes before any of it is decided in detail, because the list of what survives on each catalog is a fact to measure, not an opinion.

## 1. Decisions for review (R0 to R6)

**R0. A one-afternoon spike before the round is scheduled: point a project at R2 Data Catalog and at a local Lakekeeper, and record which Lakelet verbs survive on each.**

*Why:* the REST spec's optional parts are exactly the ones Lakelet uses. Views (`view` models are recorded as Iceberg views; Polaris and Lakekeeper have the views API, S3 Tables and Glue do not, R2 is to be checked), `register` (attach-in-place; some catalogs refuse it), multi-table `transactions/commit`, `metrics`, `rename`, and the properties Lakelet writes (`lakelet.source`, `lakelet.anonymous`, `lakelet.verified-at`). DuckDB's extension has compatibility flags for partial catalogs (`STAGE_CREATE_TABLES`, `DISABLE_MULTI_TABLE_COMMIT`, `SKIP_CREATE_TABLE_METADATA_UPDATES`) and supports REST catalogs only over S3, S3 Tables and GCS storage — not Azure, not local files.

*Recommend:* a throwaway branch, a real R2 bucket and catalog on Hants' Cloudflare account (the free tier covers it), Lakekeeper from its container on the Mac, and one table: `import`, `sql` (read and `CREATE TABLE AS`), `question save` + `run` with a `table` model and a `view` model, `tables attach` of a public prefix, `tables expire`, `tables rename`, `describe`, `changes`, `lineage`. The output is a table in this file's §7: verb × catalog × works / works with a flag / refused. Nothing merges.

*Gate:* the table, filled in, with the exact error text for each refusal.

- [ ] Agree
- [ ] Change:

---

**R1. Bring your own catalog: `[catalog] mode = "external"` with a URL, an auth kind and a warehouse, and `lakelet serve` starts no catalog of its own.**

*Recommend:* `lakelet.toml` already has `catalog.mode` and `catalog.url`; this fills them in. `lakelet catalog attach <url> --warehouse s3://bucket/prefix [--auth bearer|oauth2|sigv4]` (the verb the architecture doc names) writes the section and checks the catalog (R2 below); `lakelet init --catalog <url>` does the same at init, and the app's New project dialog gains a third choice under "The tables": **In a shared catalog** (Simple) / **External REST catalog** (Technical) beside "In this folder" and "In a bucket you own". With `mode = "external"`, `Project.open` skips the local catalog: DuckDB `ATTACH`es the remote (with `ACCESS_DELEGATION_MODE 'vended_credentials'` when the catalog offers it, else the project's own AWS profile from C1), pyiceberg's `RestCatalog` is built from the same section, and the dbt profile the core rewrites at start carries the remote address. A remote catalog implies a bucket warehouse (DuckDB's storage rule), so this is the W1 path with the catalog moved; `warehouse/` is not made and `relocate` has nothing to do. `.lakelet/catalog.db` is not created; `history.db`, the cache and the dbt target stay local and per person; the questions and models are shared the way they already are, through git. The secret — a bearer token, an OAuth2 client id and secret, or the AWS profile for SigV4 — is never in `lakelet.toml`: it is `LAKELET_CATALOG_TOKEN` / `LAKELET_CATALOG_CLIENT_ID` + `_SECRET` in the environment for the CLI, and for the app the C1 pattern extended — a per-machine entry in the shell's `projects.json` naming the profile, and (decision C3's keychain, brought forward if R1 is agreed) the token itself in the OS keychain, injected into the sidecar's environment at start. The core stays environment-only.

*Not chosen:* speaking Glue's, Unity's or S3 Tables' native APIs (each has a REST endpoint; REST is the spec, and DuckDB and pyiceberg both speak it); a `mode = "team"` distinct from `"external"` (the hosted tier is an external catalog with a Lakelet URL; one code path); syncing a remote catalog into the local SQLite (two sources of truth); Azure now (DuckDB cannot read a REST catalog over ADLS today; the docs say so).

*Gates:* pytest against the suite's own catalog run as if remote (`lakelet catalog serve` on Postgres in `compose.yaml`, reached over a non-loopback address with a bearer token — the first test of `mode = "external"` needs no third party); the real-catalog tests behind `LAKELET_CATALOG_URL`, skipped without it, the way the real-bucket tests are; `lakelet run` records a view on a catalog that has the views API and says so plainly on one that does not (R4); the app's dialog and Settings show the catalog's URL and the verdict of the check.

- [ ] Agree
- [ ] Change:

---

**R2. `lakelet catalog check <url>` says, before a project depends on it, which of Lakelet's verbs this catalog can carry.**

*Recommend:* the `bucket check` idea for catalogs: `GET /v1/config` (the catalog's own declared endpoints and defaults), then a namespace list, a table create-and-drop under a `lakelet-check-<hex>` name in a scratch namespace, a view create-and-drop, a `register` of a one-file prefix, a rename, and a multi-table commit — each reported as *yes*, *no* or *not offered* (the spec lets a catalog omit endpoints in `/v1/config`; a missing one is not an error, it is a fact). The output is one sentence per verb and a `--json` form; the app's dialog shows it under the URL field the way the bucket check's sentence sits under the prefix. The check is what R0's table becomes once it is code: the spike is done by hand once, the check does it forever.

*Not chosen:* guessing from the catalog's vendor (URLs lie; capabilities change); refusing catalogs that miss an endpoint (a catalog without views is fine for a project with no view models).

*Gates:* pytest — the check against Lakelet's own catalog says yes to everything; against a stub that omits views and register says so; `/docs/catalog` gains a "Using another catalog" section with the check's sentences.

- [ ] Agree
- [ ] Change:

---

**R3. The core says what it cannot do on this catalog instead of failing halfway: a view model on a catalog without the views API is built as a table and the card says so; `attach` on a catalog without `register` is refused with the reason.**

*Recommend:* `Project` carries the catalog's capability set (from R2's probe at open, cached in `.lakelet/catalog-capabilities.json` with the config's ETag or a day's TTL). `lakelet run` on a catalog with no views API materialises `view` models as tables (a one-line change in the view macro's branch) and prints "this catalog cannot keep views; `stg_orders` was built as a table"; the Models screen's card says the same in the Simple words ("answered live" becomes "saved as a table on this catalog"). `tables attach` on a catalog without `register` refuses before listing the prefix: "this catalog cannot register files in place; import copies them, or use a catalog that can". Multi-table commits fall back to one commit per table when the catalog says so, with DuckDB's `DISABLE_MULTI_TABLE_COMMIT`.

*Not chosen:* emulating views client-side (a view the other engines cannot see is not a view); silently downgrading (the whole product is saying what will happen before it does).

*Gates:* pytest with the stub catalog from R2; the Simple and Technical sentences in `vocabulary.ts`; `/docs/dbt` and `/docs/tables` name the two limits.

- [ ] Agree
- [ ] Change:

---

**R4. Lakelet's own catalog becomes a thing you can run for a team: `lakelet catalog serve` on Postgres, in a container, with bearer-token users and STS credential vending, and it passes Apache Iceberg's REST compatibility kit.**

*Recommend:* the server already runs on Postgres for the second-dialect tests and is what the smoke test's Spark and Trino talk to; this packages it. A `Dockerfile` under `core/` (the frozen sidecar of the ship brief, `lakelet catalog serve --bind 0.0.0.0 --store postgresql://…`), a `--users` file or table of bearer tokens with a per-token role (read, write, admin) — the T6 loopback guard is relaxed only when `--bind` is explicit and TLS is in front — and credential vending: with `--vend-role arn:aws:iam::…:role/lakelet-catalog` the catalog answers `X-Iceberg-Access-Delegation: vended-credentials` by calling STS `AssumeRole` with a session policy scoped to the table's prefix and returning the short-lived keys in `config`, so laptops and workers never hold a long-lived key (the architecture doc §3.4). The customer creates that one role and pastes its ARN — consistent with P2's "no provisioning in the customer's account": they make the role, we only assume it. Before it is offered to anyone, the server runs Apache Iceberg's REST Compatibility Kit (the `iceberg-open-api` RCK tests) in CI, so "it is a real catalog" is a test result, not a claim. `compose.yaml`'s `engines` profile becomes the worked example: one command starts the catalog, RustFS, Spark and Trino, and the docs walk through a Lakelet project and a Spark session sharing a table.

*Not chosen:* auth beyond bearer tokens for the self-host tier (OAuth2 client credentials is the hosted tier's problem and P2's brief); a web UI for the self-hosted catalog (the app's screens over `/api` are the UI; a catalog is an endpoint); vending for GCS and R2 now (each has its own token model; AWS first, the others when a user has one).

*Gates:* the RCK green in CI against the Postgres store; pytest for vending (Moto's STS, a session policy that names the prefix, a token expiring and being re-vended — DuckDB reused expired vended credentials once, duckdb-iceberg #1352, so the test covers the refresh); the smoke test extended so Spark writes and Lakelet reads through the vended path; `/docs/catalog` "Running the catalog for a team".

- [ ] Agree
- [ ] Change:

---

**R5. The hosted catalog (P2's Team tier) stays a separate brief, written after R1 to R4 have run and ship has happened; nothing in this round assumes it.**

*Recommend:* R1's external mode is what a hosted Lakelet catalog would be from the laptop's point of view — an external catalog with a Lakelet URL and an OAuth2 client — so nothing hosted-specific belongs here. `team-v0-plan.md` decides tenancy, sign-up, OAuth2, billing and the portal (P2 said the portal is the app's screens served from the catalog). What this round must not do is make that harder: no assumption in the core that a catalog is single-tenant, no capability that only Lakelet's own catalog has (R2's probe applies to ours too), and the `lakelet.*` table properties documented as the contract a hosted catalog would read.

- [ ] Agree
- [ ] Change:

---

**R6. The site and docs say what is true at each step: "works with any Iceberg REST catalog" only after R1 and R2 land, "run it for your team" only after R4, and "hosted" stays *planned*.**

*Recommend:* `web/src/data/status.ts` gains three rows (external catalog, self-hosted catalog, hosted catalog) that the README block and the status table read; `/docs/catalog` grows the two sections named above; `/how-it-runs` gets the picture with a remote catalog in it (today it draws the local one); the landing page's "How it fits" column two gains one sentence when R1 lands ("or share one catalog with a team"). Nothing before the gate is green.

- [ ] Agree
- [ ] Change:

---

## 2. Scope

In: the spike; external mode in `lakelet.toml`, `catalog attach`, `init --catalog`, the New project choice; the capability probe and `catalog check`; the graceful limits for views, register and multi-table commits; the container, auth, vending and the compatibility kit for the self-host tier; docs and status. Out: the hosted tier (R5), Azure storage, GCS and R2 vending, a catalog UI, Nessie-style branching, migrating a local project's tables into a remote catalog (`tables publish` per table already exists and is the path; a whole-project move is a later verb).

## 3. Architecture notes

The core's clients already take a catalog URL: `Project.catalog_url` feeds DuckDB's `ATTACH`, pyiceberg's `RestCatalog`, and the dbt profile the core rewrites at start. External mode swaps the source of that URL and adds auth; the seam is `Project.open` and `engine.py`'s attach. The loopback guard (T6) is a property of the *local* server and is untouched. History, the gauge's cache and manifests stay in `.lakelet/` per machine — the gauge does not need the catalog to be local, it needs the table statistics, which it reads through the same REST client either way (manifest lists from the bucket). `relocate` is local-only by construction. `expire` commits through pyiceberg and works on any catalog that accepts a commit; the orphan sweep stays local-only as `/docs/remote` says. The catalog server's store is already dialect-neutral (SQLAlchemy Core, SQLite and Postgres tested); vending is a new module beside `server.py` that only activates with `--vend-role`.

## 4. Build order

| Step | What | Gate |
|---|---|---|
| 0 | R0 the spike on R2 Data Catalog and Lakekeeper | §7's table filled in, errors quoted |
| 1 | R2 `catalog check` and the capability probe, against our own catalog and a stub | pytest; the sentences |
| 2 | R1 external mode: config, `catalog attach`, `init --catalog`, `Project.open`, the app's dialog and Settings row, the secret through the environment and the shell | pytest against our catalog over Postgres reached as remote; the real-catalog tests skipped without `LAKELET_CATALOG_URL`; Playwright on an eleventh sidecar |
| 3 | R3 the graceful limits | pytest with the stub; vocabulary; docs |
| 4 | R4 container, bearer users, vending, the compatibility kit in CI, the compose example | RCK green; vending tests on Moto STS; the smoke test through vending |
| 5 | R6 docs, status rows, the pictures | site tests and build |

Roughly: the spike an afternoon, steps 1–3 a week, step 4 a week (the RCK will find things), step 5 a day.

## 5. Toolchain

No new core dependencies for R1–R3 (pyiceberg's `RestCatalog` and DuckDB's iceberg extension already speak OAuth2, bearer and SigV4; `boto3` is present for STS through pyarrow's dependencies — to confirm at step 4, else `boto3` is added as an optional `[catalog]` extra). The compatibility kit is Apache Iceberg's `iceberg-open-api` test module, run from a container in CI. Lakekeeper and Polaris containers for the spike and, if R0 finds them worth it, for a nightly compatibility job. Cloudflare R2 for the spike on Hants' account; the tests never need it.

## 6. Definition of done

- [ ] A project made with `lakelet init --catalog https://… --warehouse s3://…` on R2 Data Catalog or Lakekeeper imports a file, answers a query, saves and runs a question, and a second machine opening the same git repository sees the same tables.
- [ ] `lakelet catalog check` on that catalog says in sentences what works, and the app's dialog shows the same before Create.
- [ ] A `view` model on a catalog without views is built as a table and both the CLI and the card say so; `attach` on a catalog without `register` refuses with the reason.
- [ ] `docker run lakelet-catalog` on Postgres passes the REST Compatibility Kit, and a laptop with no AWS key reads and writes a table through vended credentials.
- [ ] Spark (from `compose.yaml`'s profile) writes a table that Lakelet reads, through the same self-hosted catalog and the same vending.
- [ ] The docs and the status rows say exactly this and nothing more.

## 7. Known unknowns (R0 fills in the table)

| verb | R2 Data Catalog | Lakekeeper | Polaris | S3 Tables | Glue REST |
|---|---|---|---|---|---|
| create / insert / drop | | | | | |
| views (create, read) | | | | | |
| register (attach in place) | | | | | |
| multi-table commit | | | | | |
| rename | | | | | |
| metrics | | | | | |
| table properties round-trip | | | | | |
| vended credentials | | | | | |

- **Views on R2.** Unknown; if absent, R3's fallback is the first thing a solo R2 user meets.
- **DuckDB and expired vended credentials.** duckdb-iceberg #1352 says a scan can reuse expired vended keys; the extension version we ship must be past the fix or R4's tests must show the refresh works.
- **pyiceberg and `X-Iceberg-Access-Delegation`.** pyiceberg 0.12 sends the header and takes the vended keys from the load-table response; `register` and `expire` go through pyiceberg, so vending must work on both clients, not only DuckDB.
- **The dbt plugin's connection.** It builds its own DuckDB connection from the profile; external mode must give it the same `ATTACH` options (auth, delegation) the engine uses, or a model writes with the wrong credentials.
- **Storage the catalog says versus storage DuckDB reads.** A catalog's `config` may point at a warehouse root the extension cannot read (Azure); the check must say so rather than let the first import fail.
- **Two people, one history.** `history.db` and the gauge's record are per machine; a team's runs are not merged. That is by design here and the hosted tier's problem later; the docs say it.

## 8. What this changes in the other documents

| Document | Change |
|---|---|
| `docs/lakelet-architecture.md` §3.3–3.4 | `mode = "external"` is built as R1; `catalog attach` as designed; vending as R4; the Polaris row becomes "BYO Polaris, Lakekeeper, R2, S3 Tables, Glue" |
| `docs/lakelet-product-spec.md` | the tier table: Free (local), Self-host (your catalog, any REST catalog), Team (hosted, planned) |
| `web/src/data/status.ts`, README block | three rows (R6) |
| `/docs/catalog`, `/docs/remote`, `/docs/dbt`, `/docs/tables` | the sections named in R2–R4 |
| `decisions-for-review_092026.md` P2 | referenced, not reopened; R5 keeps it a separate brief |
| `decisions-for-review_092126.md` C3 | the keychain moves from "candidate" to "needed by R1" if R1 is agreed with the app storing a catalog token |
| `ship-v0-plan.md` §7 | a line: the installed app must be able to open an external-catalog project with no shell (C1 + the keychain) |

---

*Order, if agreed: R0 first and alone (an afternoon, before anything else is scheduled); then R2 → R1 → R3 as one round of about a week; R4 as a second round; R6 with each. R5 is a note. None of it before ship unless Hants moves ship again; the spike can happen any time.*
