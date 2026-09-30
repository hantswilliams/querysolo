// The homepage demo's numbers. Every one of these was measured, not modelled.
//
// Source: src/content/docs/remote.md, "Try it: Overture Maps, no account needed" --
// a laptop with no AWS credentials in its shell, against Overture Maps release
// 2026-08-19.0, on 2026-09-11. If that page changes, change this file with it.
//
// Why this replaced the old demo (web/TASKS.md, item 3): the homepage used to show a
// fictional 48 GB `events` table bursting to a worker for $0.41, driven by `querysolo ask`.
// Burst is not built and `ask` is parked, so the one thing the page had to prove -- that
// the gauge is real -- was the one thing a visitor could not check. This they can check:
// it is a public bucket, the commands are five lines, and no account is involved.

export const overture = {
  release: '2026-08-19.0',
  measuredOn: '2026-09-11',
  bucket: 's3://overturemaps-us-west-2',
  registry: 'https://registry.opendata.aws/overture/',
  /** the laptop the numbers below were measured on */
  laptopMbps: 111,

  addresses: {
    name: 'addresses',
    prefix: 's3://overturemaps-us-west-2/release/2026-08-19.0/theme=addresses/type=address/',
    rows: 472_797_160,
    files: 32,
    /** total size of the Parquet, GB */
    gb: 21.9,
  },
  places: {
    name: 'places',
    prefix: 's3://overturemaps-us-west-2/release/2026-08-19.0/theme=places/type=place/',
    rows: 73_631_092,
    files: 16,
    gb: 10.5,
  },
} as const;

/**
 * Two queries over the same 21.9 GB table. The difference between them is the whole
 * argument for the gauge: one column is 218.9 MB and runs here; every column is 21.9 GB
 * and does not. `scanMb` is measured from the manifests the attach wrote.
 */
export const demoQueries = [
  {
    id: 'grouped',
    sql: 'select country, count(*) from addresses group by 1',
    scanMb: 218.9,
    of: '21.9 GB',
    why: 'one column, read straight from the manifests',
  },
  {
    id: 'everything',
    sql: 'select * from addresses',
    scanMb: 21_900,
    of: '21.9 GB',
    why: 'every column of every file — nothing to prune',
  },
] as const;

/**
 * The gauge's own thresholds, from `[gauge]` in querysolo.toml (see /docs/config).
 * Green under 60 s, Yellow to 600 s, Red at or above it — or when remote bytes
 * cannot arrive inside that window at the measured bandwidth.
 */
export const thresholds = { greenMaxSeconds: 60, yellowMaxSeconds: 600 } as const;

/** Seconds for `mb` megabytes over a `mbps` megabit link. The gauge's I/O term. */
export const secondsAt = (mb: number, mbps: number) => (mb * 8) / mbps;

export const verdictFor = (seconds: number): 'green' | 'yellow' | 'red' =>
  seconds >= thresholds.yellowMaxSeconds ? 'red'
  : seconds >= thresholds.greenMaxSeconds ? 'yellow'
  : 'green';

export const verdictWords = {
  green: 'Runs here',
  yellow: 'Runs here, slowly',
  red: 'Needs more machine',
} as const;

export const fmtRows = (n: number) => n.toLocaleString('en-US');
