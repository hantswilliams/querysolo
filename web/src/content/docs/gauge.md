---
title: Lookahead
description: QuerySolo’s query gauge. The verdict before a query runs; what the line says, how it is decided, and what is recorded afterwards.
section: Guide
order: 1
---

**Lookahead** is the query gauge: an estimate of the work before you run it.

Every `sql`, `estimate` and question run starts with an estimate of three numbers, bytes scanned, peak memory and wall time, and a verdict in one line. `sql` prints the line to stderr and then runs; `estimate` prints it and stops. Nothing in the estimate executes the query.

## The line

```text
● Runs here · scans 61.4 MB · fits in memory · ~0.3 s
● Runs here, slowly · scans 2.1 GB · peak 9.8 GB of 12.8 GB limit · spills · ~2 min · burst ~1 min · cap $0.50
● Needs more machine · scans 346.4 MB from s3://acme-exports/events/ · ~9 min at your 4.6 Mbps · burst ~2 min · cap $0.50
```

The dot is green, yellow or red on a terminal. The words after it are the verdict, then the reason, dot-separated:

| Part | When it appears | What it is |
|---|---|---|
| `scans N` | always | Bytes the plan reads after partition and file pruning, for the projected columns only. `from s3://…` names the prefix when a table's data files are remote. |
| `fits in memory` | Green | Estimated peak under the limit. |
| `peak N of M limit · spills` | when the peak exceeds DuckDB's memory limit | The estimate expects DuckDB to spill to disk, and the time includes it. |
| `~T` | always | Estimated wall time here. `at your N Mbps` follows it for remote data, from the measured bandwidth to the bucket. |
| `burst ~T · cap $C` | Yellow and Red | What the same query would take on the smallest cloud worker that fits it, and the hard cost cap that run would carry. Arithmetic only in v0: bursting is not built, the numbers are the plan's. |

## The verdict rule

With the thresholds from [`[gauge]` in `querysolo.toml`](/docs/config):

1. **Red** if the estimated wall time is at or above `yellow_max_seconds` (600 s by default), or the estimated peak exceeds RAM plus free disk, or the table is remote and the bytes to scan cannot arrive within `yellow_max_seconds` at the measured bandwidth.
2. **Yellow** if the estimate spills, or wall time is at or above `green_max_seconds` (60 s), or the peak is above `green_max_memory_fraction` (0.6) of the memory limit.
3. **Green** otherwise.
4. **Not estimated** — the fourth state, `none`, a hollow dot — when the statement reads something the gauge has no statistics for: a file read by function (`read_parquet('…')`, `read_csv`), a DuckDB temp or native table, anything outside the catalog. The line says which: `○ Not estimated · 1 scan outside the catalog: read_parquet`. No bytes, wall or cost are reported, the verdict is never Green, the statement still runs (it is not a refusal), history records `none`, and `gauge export` leaves such runs out of the calibration file. Before the trust round of September 2026 an unattributed scan counted as zero bytes and came out Green; it does not any more.

A Red verdict on `sql` and `question run` is refused: the line goes to stderr, nothing to stdout, and the exit code is 2. `--run-anyway` runs it here regardless, and the run is recorded either way. Over the [HTTP API](/docs/api) the same refusal is a 409 carrying the estimate, and `allow_red: true` overrides it.

## Where the numbers come from

- **The plan.** DuckDB's `EXPLAIN` in JSON gives the operator tree, the projected columns and the filters pushed down to each scan.
- **Pruning.** The pushed-down filters are translated into pyiceberg expressions and evaluated against the table's manifests, so a filter on a partition or a sorted column drops whole files. The result reports `pruning` as `full` (every filter understood), `partial` or `none`. Anything the translator does not understand is dropped, which only makes the estimate larger, never smaller.
- **Bytes.** Per-file sizes from the manifests, times the share of each file that the projected columns occupy, from one Parquet footer per snapshot.
- **Memory.** The largest operator in the plan: a hash join's build side, a group-by's output, or a sort's input, each as rows times an in-memory row width (Parquet bytes per row times 2.5) with a 1.5× allowance for hashing, plus a 128 MB buffer. DuckDB's own row estimates feed this, capped at four times the largest scan because they can run away on chained joins.
- **Time.** The larger of the I/O time (bytes over the disk throughput `init` measured, or the bucket bandwidth for remote data) and the CPU time (a nanoseconds-per-row cost per operator class, times rows, over the thread count at 70% efficiency), plus the time to write and read back any spill.
- **The machine.** RAM, free disk, thread count and the memory limit, read from DuckDB and the OS each run, plus the throughput from `.querysolo/cache/machine.json`.

The throughput is measured once, at `init`: QuerySolo writes 512 MB of random bytes in the warehouse and reads them back, both with the page cache bypassed (`O_DIRECT` on Linux, `F_NOCACHE` on macOS; the write too, because macOS serves pages the write left in memory even to a `F_NOCACHE` read), so the figure is the disk's and not the cache's; a 64 GB machine reading through the cache would report tens of thousands of MB/s and the gauge would call every local scan free. Where the cache cannot be bypassed the figure is measured through it, capped at 7,000 MB/s and labelled `cached` in `querysolo gauge history` and `/api/health`. `querysolo gauge probe` measures again, which a project set up before September 11, 2026 should run once.

The constants are v0: calibrated on TPC-H at scale factor 1 on one 18-thread machine, where 18 of 22 queries land within 2× on time and all 22 within 1.5× on bytes. They will be wrong by a factor on a different machine until per-machine correction arrives; the bytes number is the trustworthy one, the time number is the shape.

## Budgets

Measured on the machine the constants were tuned on: an estimate with warm caches takes 4 to 6 ms against a 150 ms budget; the second estimate on a table whose metadata is in a bucket, 17 ms; `querysolo sql` from process start to the gauge line, 0.81 s against 1 s. The first estimate on a never-read table has to read its manifests and can take longer; the cache under `.querysolo/cache/` is what makes the second one fast.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Ran. |
| `1` | An error, named on stderr: a bad file, an unknown table, SQL that does not bind. |
| `2` | Red, refused. Nothing ran. |
| `4` | A catalog conflict that three retries with backoff did not clear: another writer committed to the same table at the same moment. Re-run. |

`3` is reserved for a burst that was refused or killed, when bursting exists.

## The record

Every run is a row in `.querysolo/history.db` (`runs`), whether or not it succeeded. `querysolo gauge history` shows the recent ones; `/api/history` returns them as JSON. A row carries: the SQL text and its hash, a fingerprint that follows the tables' snapshot ids, the tables read, the operator counts and the pruning result, the machine profile and its hash, the estimate (bytes, peak memory, wall time here, wall time and cost on a worker), the verdict and reason, whether it ran and where, and the actuals from DuckDB's profiler: rows scanned, bytes, peak buffer memory, peak process RSS, spill, wall time, plus retries and any error text.

The SQL text stays in the file and is never sent anywhere. A `question_runs` table records the last run of each saved question, and a `corrections` table is in place for the per-operator correction factors that a later version will learn from the pairs.

`querysolo gauge history` opens with the record's summary: runs recorded, the share of completed local runs whose actual wall time was within 2× of the estimate either way, and Green runs that took over three minutes (the promise broken). The app's Gauge screen shows the same, with the run list and an estimate-versus-actual scatter on log axes.

## Export and reset

`querysolo gauge export` writes the record as JSON lines, one per run, to `.querysolo/exports/gauge-<time>.jsonl` (`--out <file>`, or `-` for stdout). It holds exactly what PRD F0.3.9 allows to leave a machine: the fingerprint hash, the machine as a class (platform, architecture, RAM to the nearest 8 GB, the memory limit to the nearest 4 GB, cores, threads, on battery), the disk figure to the nearest 500 MB/s and the bandwidth to the nearest 50 Mbps, the operator-class counts and the pruning result, the estimate, the verdict and where it ran, the actuals, retries, and whether the run failed. It never holds the SQL, its hash, a table or column name, a value, the gauge's sentence (which names a source prefix) or an error's text. Nothing sends it: a design partner sends the file by hand, and the Day 1 sharing path will send this same shape and nothing more. The `share_calibration` setting stays off until that path exists.

`querysolo gauge reset` (`--yes` to skip the question; the app asks on the screen) forgets every recorded run, the questions' last runs and the correction factors. `querysolo gauge probe` measures the disk again.
