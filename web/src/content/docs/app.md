---
title: The desktop app
description: Running the app from source, what each screen does, the keys, how it talks to the core, and what it will never do behind your back.
section: Develop
order: 2
---

The desktop app is a window over the same core the CLI runs: a Tauri 2 shell (Rust, the system webview) that starts `querysolo serve` for the project you open and shows its answers. Every button is a CLI verb, and every action shows the exact `querysolo …` line it is, with a copy button, so nothing is reachable one way and not the other. There is no installer yet (that is session 10); today it runs from the repo.

## Running it from source

```bash
cd core && uv sync && cd ../app
npm install                                            # Node 22
export QUERYSOLO_SIDECAR=$PWD/../core/.venv/bin/querysolo  # the core the app should start
npm run tauri dev                                      # Rust stable; on Ubuntu also libwebkit2gtk-4.1-dev, librsvg2-dev, libayatana-appindicator3-dev
```

The first `tauri dev` compiles the shell (three minutes or so); after that it is seconds. `QUERYSOLO_PROJECT=~/acme npm run tauri dev` opens that folder; without it the app opens the last project you used, or the welcome screen.

## Projects and windows

The welcome screen offers **New project…**, **Open a folder…** and the ten most recent projects; once a project is open the same three are under **Open…** in the bar. Any folder can be opened: one without a `querysolo.toml` is set up first (`querysolo init <folder>`), and the window shows what was created.

**New project…** (also ⌘/Ctrl+N) is one dialog: a name, the folder it goes under (your Documents folder unless you **Choose…** another), and where the tables live — **In this folder**, the default, which is `warehouse/` next to the catalog, or **In a bucket you own**, an `s3://bucket/prefix` ([a warehouse in a bucket](/docs/remote#a-warehouse-in-a-bucket)). The words are deliberate: with a bucket the catalog and the engine are still on this machine; only the tables' files are elsewhere. The bucket's credentials are an AWS **profile** on this machine, picked under the prefix from the names in `~/.aws/config` and `~/.aws/credentials`, or the AWS default when none is chosen; QuerySolo keeps the name, per project and per machine, and never a key ([credentials](/docs/remote#credentials)). The line under the field says which will be used — *Using profile acme-data.*, or that the default will be — or, on a machine with no AWS files, that `aws configure` in a terminal once is what makes one, with the command to copy. A bucket is checked before the folder is made — **Check the bucket**, or **Check and create** does both: a list of the prefix with that profile, and one object written under it and deleted again, so the first import is not the first thing to fail. The sentence under the field says what the store answered; a check that fails leaves the folder unmade. In a terminal the check is `querysolo --profile <name> bucket check s3://…` and the whole thing is `querysolo --profile <name> init <folder> --warehouse s3://…`, the line beside the button. The profile of an open project is under **Settings → Bucket**; changing it starts the core again with the new one. Nothing is created in your account: the bucket and its policy are yours to make ([the policy is on the remote page](/docs/remote)). The folder must be new or empty; a folder that is a project already is opened instead, because a warehouse is fixed at init. Each project gets its own window and its own `querysolo serve`, so two projects never share an engine. The first window's core is given 60% of the machine's RAM as its DuckDB memory limit and each further window half of the previous share; the status strip along the bottom of the window shows the limit this window has. Closing a window stops its core. **Open…** in the bar lists the recent projects and **Other folder…** for the dialog.

The dot in the bar is the core's state: amber while it starts, green when `/api/health` answers ("core ready in N ms" is the spawn-to-ready time), amber again after a restart, red when it has stopped. If the core exits, the shell starts it once more and the tables refresh; if it exits twice inside a minute the window shows its last lines and a **Restart the core** button.

## The window

With a project open the window is the bar, a sidebar, the screen, and a status strip. The bar has the project's name, the core's dot, **Open…**, the **Simple | Technical** and **System | Light | Dark** switches and **Settings**. The sidebar has the five screens — **Tables**, **Models**, **Lineage**, **Changes**, **Gauge** (⌘/Ctrl+1 to 5; Simple mode says **Questions**, **Map** and **Recent**) — and under them the explorer: the drop zone with **Import…**, then every table and view in the catalog with its rows, where its data is and a freshness dot (green when it was written today, amber this week, grey before that; hover for the time). The explorer is there on every screen, so a table is one click away from anywhere; clicking one opens its detail on the Tables screen. Its right edge drags to the width you want (← and → move it too), and the **Collapse** button at the bottom folds it to icons; both are remembered. The strip along the bottom shows the core's version, DuckDB's, this window's memory limit, the local disk figure and how long the core took to be ready.

[![The window: the bar, the sidebar with the five screens and the explorer, the workspace with SQL over the verdict, the chart and the rows, and the status strip](/screenshots/workspace.png)](/screenshots/workspace.png)
*The window on the generated sample data: a two-column answer gets a chart. Every screenshot on this page is the real app in its browser harness against a real core, unedited.*

## The Tables screen: the workspace

The Tables screen is one workspace, two panes with a draggable split (the ↑ and ↓ keys move it too; where you leave it is remembered): the SQL box above with the verdict line under it, the results below. The results pane is where a table's detail or a file's preview opens when the explorer starts one, so "click a table, read its detail, run a query against it" happens on one screen without a scroll; **Run** puts the rows back in their place.

### Tables and import

The explorer lists every table with rows and where its data is, from `/api/tables`; size, columns and the snapshots are on the detail. Drop a file or a folder anywhere on the window, or **Import…**, or type a path in the explorer's box: the preview opens in the results pane and shows each column with its DuckDB type, the Iceberg type it becomes and any note about the coercion, plus the first rows, before anything is written. Import is one click; if the table exists you choose **Replace it** or **Append to it**. A folder imports one table per supported file (`.csv`, `.tsv`, `.parquet`, `.json`, `.jsonl`, `.xlsx`; other files are skipped). The line beside every step is `querysolo import <path> [--name n] [--replace|--append]`.

An `s3://bucket/prefix/` of Parquet typed into the same box is attached rather than imported: the preview shows one file's columns with the Iceberg type each becomes, how many files and bytes would be registered, and one button, **Attach as name**, which is `querysolo tables attach <name> s3://…`; nothing is copied. Tick **Public bucket (no credentials)** for a dataset that allows anonymous reads (the line gains `--anonymous`). The core reaches a private bucket with the project's AWS profile (**Settings → Bucket**); when this machine has no credentials the box says so before you type a prefix — choose a profile, run `aws configure` once, or tick public bucket. The explorer's entry names the prefix an attached table came from, `public` or `attached`, and its **Refresh** button is `querysolo tables refresh <name>`, adding the files written to the prefix since. [A real bucket](/docs/remote) has the policies and a public dataset to try.

Clicking a table in the explorer opens its detail in the results pane, which is `querysolo tables describe <name>` as a panel: the columns with their Iceberg types, where the data is, partitioning, the format version, every snapshot newest first (when, the operation, rows and files added, rows after, which is current and which the retention would expire), and the line saying what `expire` would reclaim. **Sample rows** is `querysolo tables sample`, **Expire snapshots** is `querysolo tables expire` and shows its report (snapshots and files removed, bytes reclaimed); an attached table has **Refresh** instead, because its files are not QuerySolo's to delete. A table built here also has **Publish to a bucket…** (`querysolo tables publish`): type an `s3://bucket/prefix`, **Weigh it** counts the files and says how long the copy would take at the measured bandwidth (`--dry-run`), **Publish** moves the table there with every snapshot, and a copy longer than the Yellow cap is refused with **Publish anyway** (`--yes`) beside the refusal; afterwards the explorer says **bucket**, the detail names the location, and a line counts the local files left for `expire`. Row counts everywhere take position deletes off, so a table rebuilt by delete-then-insert (the dbt path) shows the rows it has, not the rows its files hold.

[![A table's detail in the results pane: where it is, partitioning, last written, format, what reads it and what it feeds, the recent changes, and the columns](/screenshots/detail.png)](/screenshots/detail.png)
*`orders` in the results pane: `querysolo tables describe orders` as a panel, with the models it feeds as links.*

A view (a dbt `view` model built with `querysolo run`, or a view put in the catalog directly) is listed beside the tables and has its own detail: its query, its columns, how many versions it has and when this one was recorded, which dbt model it came from with the `querysolo run <model>` line that rewrites it, and **Sample rows**. It has no snapshots and nothing to expire, because nothing is stored for it; the rows are computed from its query each time it is asked.

### SQL, the verdict, the rows

Once the project has a table, the SQL box is the top pane, with the tables and columns for completion. ⌘/Ctrl+Enter runs (or the Run button). The verdict comes back before any row, from the response headers, as the gauge line: Green "Runs here", Yellow "Runs here, slowly", Red "Needs more machine", with the sentence (what it scans, whether it fits in memory, how long). Red is a refusal until **Run anyway**, which is `querysolo sql '…' --run-anyway`. Rows stream into the grid as the core produces them, one 1,000-row batch at a time from the first; the first rows are on screen before the query completes, and the grid keeps 100,000 rows before it says so and names `querysolo sql --format parquet` for the rest. Esc stops a running query wherever the focus is; the core stops the statement at once and history records the run as stopped early.

[![A date and a numeric column, charted as a line over the rows](/screenshots/workspace-line.png)](/screenshots/workspace-line.png)
*A date and a number: the chart is a line. The line beside Run is the same query as `querysolo sql`.*

A result of exactly two columns, one categorical and one numeric, draws a bar chart above the grid in the results pane, in the rows' order; a date or timestamp and a numeric draws a line; anything else draws nothing. The chart comes from the first 5,000 rows and has at most 40 bars.

Dates, timestamps, times and decimals show as dates, timestamps, times and numbers; null is ∅.

**Save as question** (Simple mode: **Save this question**) sits beside Run once the gauge has spoken. It asks for a title and nothing else, shows the file and the two checks it is about to write, and what comes back names them and the version the save recorded. A title already saved offers **Replace it**, the way an import onto an existing table does; a Red statement saves too, because a question may be bigger than the machine it was written on. The saved question is a dbt model, so it turns up on the Models screen with its title as its description. [Saved questions](/docs/questions) has the file it writes and the versions it accumulates.

## Light and dark

**System | Light | Dark** at the right of the bar. The palette is the site's, from one file (`web/src/styles/palette.css`) both read: the deep green on light surfaces, the lime on dark, and the same three verdict colours in either. System is the default and follows the machine, changing with it; Light and Dark override it for that window and are remembered. The switch is there before a project is open, so a dark desktop can be matched at the welcome screen.

[![The same workspace in the dark theme](/screenshots/workspace-dark.png)](/screenshots/workspace-dark.png)
*The dark theme; the verdicts keep their hues.*

The palette is the site's tokens with a dark set over them, so every screen, the SQL editor and the charts move together; the verdict colours keep their hues in both, because Green, Yellow and Red are the gauge's vocabulary and have to stay recognisable.

## The Models screen

**Models** in the sidebar is the project's dbt DAG through the gauge, screen 7 of the mockups: `querysolo run --plan` as a panel. The list has every model in dependency order with its kind (`view` or `table`), its state (`fresh`, `edited`, `upstream`, `never`; [the dbt page](/docs/dbt) says what each means), the verdict coloured, the estimate and what it scans, and its last run; the line beside the summary is `querysolo run`. Clicking a model shows its state with why and what changed (the diff of its SQL since the last run, folded to the changed lines with a **whole SQL** toggle, or the commits to the table it reads since; a model it blames is a link), the verdict's sentence, **Reads from** and **Feeds** — table-level [lineage](/docs/tables#lineage), each name a link to that detail, on the Tables screen when it is an imported table or a view put by hand — its tests from `schema.yml` (`not_null(id)`, `unique(id)`, a singular test by its name), its description and file, its compiled SQL, and its last `querysolo run` from history (when, how long, or that it failed). **Run all** is `querysolo run`; **Run this** is `querysolo run <model>`; **Run what changed (n)** is `querysolo run --stale`, lit when anything is not fresh. When anything is, a **Review** section above the DAG lists every out-of-date model in the order the run would build them, each with its reason and its diff or commits, to read through first. A Red model makes the run refuse the whole DAG, as the CLI does, until **Run anyway** (`--run-anyway`). After a run the notice says how many models built in how long and which views landed in the catalog, or that every model was up to date and nothing ran; the explorer and the Gauge screen's run list have the result at once. A `view` model is an Iceberg view in the catalog only when built this way; the reason is on [the dbt page](/docs/dbt).

[![The Models screen in Technical mode: the DAG on the left, a model's detail with its state, verdict, lineage, tests, compiled SQL and versions on the right](/screenshots/models.png)](/screenshots/models.png)
*Technical mode: a model's detail with its versions. In Simple mode the same models are question cards with **See the answer**.*

The table and view details on the Tables screen carry the same **Reads from** and **Feeds** lines after their facts, and a model not built yet is a link back to the Models screen with it selected.

The plan compiles the project with dbt each time the screen opens, so it takes a few seconds; a project without dbt installed says so with the `pip install 'querysolo[dbt]'` line, and a project without models says a model is a SQL file under `models/`.

## The Lineage screen

**Lineage** in the sidebar (Simple: **Map**) is `querysolo lineage --all` drawn: every table, view and model as a node in layers left to right — what reads nothing at the left, each node one layer after the deepest thing it reads — and every edge as lineage knows it (a `ref()` in blue, a `source()` or a table named in the SQL in grey, a catalog view's SQL dashed; hover says which). A model is coloured by its state: green-edged when fresh, amber when edited or an input changed, dashed grey when never built; the header counts what is out of date. Clicking a node opens its detail — a model on the Models screen with it selected, a table or a view on the Tables screen. The layout is the app's own (a longest-path layering and rows by what each node reads), drawn as SVG in the theme's colours; a project's graph is tens of nodes, so no graph library is carried.

[![The Lineage screen: tables on the left, the models that read them on the right](/screenshots/lineage.png)](/screenshots/lineage.png)
*Four imported tables and the three models over them, all fresh.*

## The Changes screen

**Changes** in the sidebar (Simple: **Recent**) is `querysolo changes` as a list: everything that happened to the project, newest first — a table's snapshot ("orders: append +1,200 rows · made out of date: stg"), a model's or question's last run ("by_customer built in 1.2 s, Green"), a version ("save question: Revenue by customer · Ada Lovelace") — each with when, which source it came from, and a link that opens the table's detail or the model on the Models screen. The **Name** box is the CLI's argument: type a table, view, model or question and the list is only what happened to it, and the line beside it is the command. Simple mode says the same in its words ("orders: 1,200 rows added · 1 question needs refreshing: stg", "by_customer refreshed in 1.2 s", "Revenue by customer saved, a new version"). Every table, view and model detail has a **Recent** strip — its own last five entries — with **All changes** opening this screen filtered to it. Nothing is recorded for the screen: it is read from the catalog, history and git, so it is always what the CLI would print.

[![The Changes screen: runs, snapshots and versions, newest first](/screenshots/changes.png)](/screenshots/changes.png)
*Runs, snapshots and saved versions in one list; each entry opens its detail.*

## Simple and Technical

The **Simple | Technical** switch at the right of the bar is screen 8: the same project in two vocabularies, remembered per window. Technical is everything above: model, test, view, the verdict by colour, the command line beside every button. Simple renames the Models screen **Questions** and shows the DAG as cards: a `view` model is a question *answered live*, a `table` model is *saved as a table*; each card has when it was last refreshed, whether it is up to date as a sentence ("Up to date.", "Changed since it was last refreshed.", "Out of date: orders changed 2 h ago.", "Never refreshed.") with the same diff or commits under it, the wait as a sentence ("Ready in about 2 s", "Takes a while: about 4 min", "Too big for this machine right now") instead of a colour, its checks in words (`not_null` on `id` is "id is never empty", `unique` is "id is never repeated", `accepted_values` is "one of the allowed values"), **See the answer** and **Refresh**; the top has **Refresh all** and **Refresh what changed**. **See the answer** is the Tables screen with `select * from <question>` in the box and run — the verdict line, the chart when the answer is two columns, every row in the grid, and `querysolo sql '…'` beside it — and the box is yours to edit from there; a question never refreshed says **Refresh, then see the answer** and does both. The Technical model detail has the same button as **Rows**. The command lines stay, because Simple hides vocabulary, not what the app does. The view detail follows the switch too. The mapping between the two is one small table in the app, pinned by a test, so both screens say the same words.

[![The Questions screen in Simple mode: three cards, each with See the answer, Refresh and History](/screenshots/questions.png)](/screenshots/questions.png)
*Simple mode: a question is asked and answered in one click.*

[![The answer: the workspace with select star from revenue_by_region run, the verdict, the chart and the rows](/screenshots/answer.png)](/screenshots/answer.png)
*What **See the answer** opens: the rows, with the SQL there to edit into the next question.*

## The Gauge screen

**Gauge** in the sidebar is the gauge's record, screen 5 of the mockups: this machine's line (RAM, threads, the memory limit, the disk figure, the bandwidth when a bucket has been read), three tiles (runs recorded; the share of completed local runs within 2× of their estimate on time; Green runs that took over three minutes), an estimate-versus-actual scatter on log axes with the diagonal of a perfect estimate and the verdict colouring each point, the run list (when, verdict, where it ran, estimate, actual, bytes scanned; a failed run says so, without its text), and what the gauge has learned on this machine, which is nothing until the correction factors ship. Four buttons are four verbs: `querysolo gauge history` at the top, **Export history** (`querysolo gauge export`: a file in the project, nothing sent; see [the gauge](/docs/gauge)), **Probe the disk again** (`querysolo gauge probe`), and **Reset** (`querysolo gauge reset`, which asks first).

[![The Gauge screen: the machine's line, three figures, the estimate-versus-actual scatter and the run log](/screenshots/gauge.png)](/screenshots/gauge.png)
*Estimate against actual on this machine, and the runs it learned from.*

## Settings

⌘/Ctrl+, opens the settings dialog over the window: the CLI's memory limit and thread count, how many days of snapshots `querysolo tables expire` keeps, and the calibration-sharing toggle (nothing is sent yet; the switch is there so the file is ready). Each row shows its `querysolo config set …` line. They are written into the project's `querysolo.toml` in place, comments kept; the core reads them when it starts.

## Keys

| Key | Does |
|---|---|
| ⌘/Ctrl+Enter | run the SQL |
| Esc | stop a running query; close settings or a menu |
| ⌘/Ctrl+, | settings |
| ⌘/Ctrl+K | to the SQL box (reserved for the ask box) |
| ⌘/Ctrl+1 … 5 | Tables, Models, Lineage, Changes, Gauge |
| ⌘/Ctrl+N | New project… |
| ↑ ↓ on the split | move the split between the SQL box and the results |

## How the window talks to the core

The shell spawns `querysolo serve --port 0 -C <project> --memory-limit <share>`, waits for its `serving` line, reads the port and the per-launch token from `.querysolo/serve.json`, and hands them to the window. The window calls `http://127.0.0.1:<port>/api` itself with the bearer token, and reads query results as an Arrow IPC stream; the core allows cross-origin requests from the Tauri origins only. Under `tauri dev` the window's origin is the Vite server, so a debug build of the shell also passes `QUERYSOLO_DEV_ORIGIN=http://localhost:5173` to its sidecar; a release build passes nothing, and a Rust test run with `cargo test --release` holds it to that. See [the local HTTP API](/docs/api) for the routes.

## Nothing hidden

The app makes no network request the core does not: a Playwright test records every request across the screens (a preview and import, a query with a chart, the settings panel, a Gauge export, a Models plan) and asserts the only hosts are the page's own server and the sidecar on loopback. The core's own `querysolo audit network` covers the other side. Nothing is downloaded at run time; the chart library evaluates its expressions with an interpreter so the window's content-security policy stays without `unsafe-eval`.

## Tests

```bash
cd app/src-tauri && cargo test    # the supervisor, projects and windows, against a fake sidecar
cd .. && npm test                  # Vitest: the screens' pieces, the command lines, the chart rule, the window's reactions
npm run e2e                        # Playwright against ten real `querysolo serve`s: a 20 M-row table, a stand-in bucket, a zero-day retention, a dbt project, a bucket warehouse among them
```

The Playwright suite starts its own sidecars on temp projects (and, for the attach screen, a Moto server standing in for a bucket, with public-read ACLs so the anonymous path is real; for the Models screen, a dbt project with a view model, a table model over it and two tests); nothing of yours is touched. On a laptop it runs the spec files on several workers at once and each file owns the sidecar it writes to.

## When it does not start

"The core did not start" names the sidecar it tried and the project. In development the usual cause is `QUERYSOLO_SIDECAR` unset in the shell that ran `npm run tauri dev`; the core's own error, if it printed one, is in the panel. "Load failed" in a query is WebKit's wording for a blocked request, which under `tauri dev` means the sidecar was started without the dev origin (an old shell build).
