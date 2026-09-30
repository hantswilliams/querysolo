---
title: A real bucket
description: What QuerySolo needs from AWS to attach your data, the IAM policy for the test suite's own bucket, the environment variables, and what the suite writes and removes.
section: Develop
order: 3
---

QuerySolo reads Parquet in S3 in place (`tables attach`, see [Tables](/docs/tables)) and, by default, writes nothing to the bucket: the Iceberg metadata for an attached table lives under the project's own `warehouse/` on your machine, and the data files are read where they are. A read-only user is enough for that. Writing into a bucket happens only when you ask for it: a project whose warehouse *is* a bucket (below), `--metadata-in-bucket` on an attach, and the test suite.

## A warehouse in a bucket

```bash
querysolo init ~/acme --warehouse s3://your-bucket/acme
```

Every table this project writes — an import, a `CREATE TABLE`, a `table` model built by `querysolo run` — puts its data files and its Iceberg metadata under `s3://your-bucket/acme/main/<table>/`; nothing goes under the project folder but the catalog (`.querysolo/catalog.db`), history and the dbt files. The warehouse is fixed at `init`: tables carry absolute locations, so it is not a setting (`config set project.warehouse` is refused) and there is no `warehouse/` folder to move, so `querysolo relocate` has nothing to do for such a project. Everything else works as on a local warehouse, and the suite runs the whole path against the same store the attach tests use: import, writes through SQL, `querysolo run` with a table and a view model, `describe`, `expire` (the expired snapshots' files are deleted in the bucket; the orphan sweep of unreferenced files is local-only, and a bucket keeps what no snapshot references until you remove it), versions, and pyiceberg reading every table from another process. The gauge treats the tables as remote and estimates by the bandwidth figure, as it does an attached table, so a scan that would be Green on a local disk may be Yellow here; that is the honest answer. The app's explorer says **bucket** for such a table and the detail names the location, and the app makes such a project from **New project… → In a bucket you own**: the prefix is checked first (`querysolo bucket check s3://bucket/prefix`: the credentials, a list, one object written and removed), then the folder is made with `init --warehouse`.

The credentials are the ones below; `querysolo run` hands the same ones to dbt's connections, so a model over a bucket table builds without any profile of its own. A read-only user is not enough for a bucket warehouse: the policy needs `PutObject` and `DeleteObject` under the prefix as well as `GetObject` and `ListBucket`.

A project on a local warehouse can still put one table in a bucket: `querysolo tables publish <name> s3://bucket/prefix` copies its files there, rewrites its metadata and moves the catalog to it in one commit, every snapshot kept, and the table is read from the bucket from then on; see [Tables](/docs/tables#publishing-a-table-into-a-bucket). It needs the same write policy under that prefix.

## Credentials

QuerySolo holds no key. The keys live where AWS puts them — `~/.aws/credentials` after `aws configure`, or the short-lived cache of `aws sso login`, or an instance role — and QuerySolo names a **profile**; there is no key in `querysolo.toml`, none in the app, and the app never asks for one. In a terminal, `querysolo --profile <name> …` or `AWS_PROFILE` picks the profile, and with neither the AWS default chain applies (the `[default]` section, or keys in the environment: `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are used first when both are set). In the app the profile is a per-project setting kept on this machine — chosen in **New project…** under the bucket's prefix, or later in **Settings → Bucket**, from the names in `~/.aws/config` and `~/.aws/credentials` (names only; nothing else in those files is read, and nothing is written) — and the core is started with it. A machine with no AWS files needs `aws configure` once, or `aws sso login`, and the dialog says so. `AWS_REGION` names the region (`us-east-1` when unset) and `AWS_ENDPOINT_URL` points at a self-hosted store; on AWS itself leave it unset. `/api/health` reports `aws: {configured, source, profile, region}` — `source` is `environment`, `profile` (named, or `default` when the files have one) or `none` — so the app can say, before you type a prefix, whether the core it started has credentials at all; it never reports a key.

A read-only user for your own data needs this on the bucket that holds it:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::YOUR-BUCKET" },
    { "Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "arn:aws:s3:::YOUR-BUCKET/*" }
  ]
}
```

## Public buckets need nothing

A bucket that allows anonymous access is read with `--anonymous` and no credentials at all; [Tables](/docs/tables) has the two commands. The datasets in [AWS's Registry of Open Data](https://registry.opendata.aws/) are the case this is for: AWS carries the egress, so a full scan costs nobody anything, and a fresh machine with no AWS account can attach one and ask the gauge what a query would cost.

### Try it: Overture Maps, no account needed

[Overture Maps](https://registry.opendata.aws/overture/) publishes its releases as Parquet in a public bucket, one prefix per theme and type, with one schema across the files of a type. Tested September 11, 2026 against release `2026-08-19.0` from a laptop with no AWS credentials in the shell:

```bash
querysolo init ~/querysolo-open && cd ~/querysolo-open
querysolo tables discover --anonymous s3://overturemaps-us-west-2/release/2026-08-19.0/
querysolo tables attach addresses --anonymous s3://overturemaps-us-west-2/release/2026-08-19.0/theme=addresses/type=address/
querysolo tables attach places    --anonymous s3://overturemaps-us-west-2/release/2026-08-19.0/theme=places/type=place/
querysolo estimate 'select country, count(*) from addresses group by 1'
querysolo sql "select count(*) from places where bbox.xmin between -73.2 and -73.0 and bbox.ymin between 40.85 and 40.95"
```

`discover` on the release lists six themes from 5.6 GB to 277 GB. `addresses` registered as 472,797,160 rows in 32 files (21.9 GB) and `places` as 73,631,092 rows in 16 files (10.5 GB), with nothing copied and the metadata under the project's own `warehouse/`. The gauge then reads the manifests it wrote: `count(*)` scans nothing, a `group by country` over the addresses scans 218.9 MB (one column of 21.9 GB) and says about 16 s at that laptop's 111 Mbps, a bounding-box count over the places scans 104.8 MB and ran in 4.1 s against an estimate of 8 s; `select *` over either table is Red at any home link. Pick a release from `discover` rather than copying the one above; Overture retires old releases.

Overture's `geometry` column is GeoParquet: WKB bytes with a `geo` entry in the footer. QuerySolo registers it as `binary` and reads it as the bytes, with DuckDB's own GeoParquet conversion turned off in the engine — on a machine with the `spatial` extension the reader would otherwise turn the column into GEOMETRY and the Iceberg scan then fail to cast it back, refusing every read of the table. The geometry is one function away: `st_astext(st_geomfromwkb(geometry))`, and `st_geomfromwkb`, `st_astext`, `st_aswkb` are in core DuckDB 1.5; the spatial extension's functions work on the same value once loaded.

## When a file changes under the same path

Attach registers files as they are; the table's statistics — row counts, column bounds the gauge prunes on — describe those files. A file later rewritten under the same key is caught by `refresh` and by `describe`: its size is compared with the manifest's, and its modification time with the last verification (attach, or the last refresh that found nothing changed). `refresh` names the file and refuses; `querysolo tables attach --replace <name> <prefix>` registers the prefix again. Two seconds of grace absorb S3's second-resolution `LastModified` and a store clock a little ahead of yours. The [Tables page](/docs/tables) has the sentence.

## The test suite against a real bucket

The S3 tests (`tests/test_step1_s3.py`, the catalog with its files in a bucket; `tests/test_step8_remote.py`, attach, refresh, discover, the bandwidth probe) run against an in-process Moto server by default and in CI. To run the same tests against a real bucket, make a bucket that is the suite's own (it writes and deletes in it) and an IAM user with this policy on that bucket only:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": ["s3:ListBucket"], "Resource": "arn:aws:s3:::querysolo-suite" },
    { "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"],
      "Resource": "arn:aws:s3:::querysolo-suite/*" }
  ]
}
```

Then, from `core/`:

```bash
export QUERYSOLO_TEST_S3_BUCKET=querysolo-suite
export AWS_ACCESS_KEY_ID=…  AWS_SECRET_ACCESS_KEY=…  AWS_REGION=us-east-1
uv run pytest tests/test_step1_s3.py tests/test_step8_remote.py -v
```

What it does in the bucket: everything a run writes goes under `querysolo-tests/<date>-<id>/` (the plain Parquet prefixes the tests attach, the catalog warehouses of the step 1 tests) and under `_querysolo/` (the `--metadata-in-bucket` layout, which is at the bucket root by design), and both are removed when each test module ends, and again at the start of the next run in case an earlier one crashed. The bucket itself is never created or deleted, and a bucket name that does not answer to the credentials stops the run before anything is written. The fixtures are a few megabytes; the ten-thousand-file registration is gated behind `QUERYSOLO_PERF=1` and writes ten thousand small objects, which is a few cents of requests.

`QUERYSOLO_TEST_S3_ENDPOINT` (or `AWS_ENDPOINT_URL`) instead of a bucket name points the suite at a self-hosted store such as the RustFS in `compose.yaml`, where the bucket `querysolo-test` is created if missing, as it always was.

## What the results mean

Against Moto the numbers are the container's; against a real bucket they are your link's. The attach test prints nothing but passes only if registration copied no object; the bandwidth test prints the second estimate's time (under 150 ms with the manifests cached) and the probe's figure is in `.querysolo/cache/machine.json` of the test project. The figures from the reference runs are in `build-sessions/`.
