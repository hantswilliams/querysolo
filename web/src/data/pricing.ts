// Single source of truth for every number on the site that has a dollar sign.
// index.astro and pricing.astro both read from here.

export const plans = [
  { id: 'local', name: 'Local', price: '$0', unit: '', tag: 'forever · open source · Apache 2.0',
    blurb: 'Desktop app and CLI, the gauge, dbt runner, table-level lineage. Your bucket. Forever.',
    features: [
      ['Desktop app and CLI', 'for macOS and Linux'],
      ['', 'SQL editor, ask-in-English, dbt Core runner, table-level lineage'],
      ['The gauge', 'on every query and every dbt run'],
      ['', 'Local Iceberg REST catalog (SQLite) and Parquet on disk'],
      ['', 'Publish to your own S3 bucket; GCS and R2 later'],
      ['', 'MCP server for agents, with a per-agent daily cap'],
      ['', 'Unlimited data, unlimited queries, on your machine'],
    ] },
  { id: 'team', name: 'Team', price: '$24', unit: '/ person / month', tag: 'early pricing · private beta',
    blurb: 'Shared catalog, scheduled runs, compaction, freshness and test alerts.',
    features: [
      ['Shared catalog', 'so every laptop sees the same tables (hosted Postgres, Iceberg REST, Polaris-compatible)'],
      ['', 'Short-lived, prefix-scoped credentials vended per user and per job'],
      ['Scheduled dbt runs', 'on burst workers, with a per-project cap'],
      ['', 'Compaction, snapshot expiry, orphan-file cleanup'],
      ['', 'Freshness and test alerts'],
      ['', 'Warm worker pool for sub-5-second burst starts'],
    ] },
  { id: 'burst', name: 'Burst', price: 'cost + 15%', unit: '', tag: 'per run · no minimum · no idle',
    blurb: "Workers in your bucket's region, sized to the run, capped before it starts.",
    features: [
      ['', "Worker sized from the gauge's memory estimate, launched in your bucket's region"],
      ['Hard cap', 'shown before you click; the worker is killed at the cap'],
      ['', 'Billed per second of actual run time; nothing between runs'],
      ['', 'On-demand in the beta; spot follows'],
      ['', "Runs on QuerySolo's account in the beta; bring your own account later"],
      ['', 'Every run reports estimate vs. actual, which makes the next estimate better'],
    ] },
] as const;

export const seatPrice = 24;
export const burstMargin = 0.15;

// AWS Fargate list, on-demand, us-east-1: $0.04048/vCPU-hr, $0.004445/GB-hr
export const workerLadder = [
  { size: 'S',  vcpu: 4,  mem: 16,  listHr: 0.23 },
  { size: 'M',  vcpu: 8,  mem: 32,  listHr: 0.46 },
  { size: 'L',  vcpu: 16, mem: 64,  listHr: 0.92 },
  { size: 'XL', vcpu: 16, mem: 120, listHr: 1.17 },
].map(w => ({ ...w, withMarginHr: +(w.listHr * (1 + burstMargin)).toFixed(2), fiveMin: +((w.listHr * (1 + burstMargin)) / 12).toFixed(2) }));

// The modeled month: five people, 38 GB, 1,240 dbt runs, dashboards keep a warehouse awake ~8 h/day.
export const scenario = {
  people: 5, dataGb: 38, runs: 1240, burstRuns: 9,
  label: 'One data team of five, one month',
  meta: '38 GB of tables · 1,240 dbt runs · a few dashboards. Modeled at list prices.',
};

export type Vendor = { id: string; name: string; total: number; why: string; lines: [string, string][]; us?: boolean };

export const vendors: Vendor[] = [
  { id: 'snowflake', name: 'Snowflake', total: 1345,
    why: 'Standard edition, $2 per credit. A Small warehouse burns 2 credits an hour and stays awake through the workday because dashboards and hourly dbt keep resetting the 10-minute auto-suspend.',
    lines: [['Small warehouse, 8 hrs/day × 30 days, 2 credits/hr × $2', '$960'], ['Two weekends the warehouse was left on (2 × 48 hrs)', '$384'], ['Storage, 38 GB at ~$23/TB', '$1'], ['Month', '$1,345']] },
  { id: 'databricks', name: 'Databricks', total: 673,
    why: "Serverless SQL at $0.70 per DBU. The smallest serverless warehouse (2X-Small) is 4 DBU an hour, so $2.80 an hour whenever it's awake. Serverless bundles the cloud VM cost; classic SQL is cheaper per DBU but adds 50–100% in EC2.",
    lines: [['2X-Small serverless, 8 hrs/day × 30 days × $2.80', '$672'], ['Storage in your S3', '$1'], ['Month', '$673']] },
  { id: 'motherduck', name: 'MotherDuck', total: 312,
    why: "Five people means the Business plan ($250 per org per month); the free Lite tier stops at three users and 10 GB. Compute is $0.60 an hour on the smallest (Pulse) instance, billed per second, and MotherDuck's hybrid execution decides for you what runs where. Your data lives in MotherDuck's storage, not your bucket.",
    lines: [['Business plan', '$250'], ['~100 hrs of Pulse compute (dbt + dashboards)', '$60'], ['Storage, 38 GB × $0.04', '$2'], ['Month', '$312']] },
  { id: 'bigquery', name: 'BigQuery', total: 289,
    why: 'On-demand, $6.25 per TiB scanned, first TiB free. There is no warehouse to leave on, which is why BigQuery is the closest competitor at this size. The bill scales with bytes scanned, so it climbs with every dashboard refresh and every un-partitioned model.',
    lines: [['1,240 runs scanning ~38 GB each ≈ 47 TB, minus 1 TiB free', '$288'], ['Storage, 38 GB at $0.02/GB', '$1'], ['Month', '$289']] },
  { id: 'querysolo', name: 'QuerySolo', total: 124, us: true,
    why: '1,231 of the 1,240 runs get a green verdict and run on laptops. Nine get a red one and burst to a 64 GB worker for about twenty minutes each. Five Team seats for the shared catalog. Storage is your own S3 bill.',
    lines: [['1,231 runs on laptops', '$0.00'], ['9 burst runs, L worker (16 vCPU / 64 GB), on-demand, ~20 min each', '$3.17'], ['Team catalog, 5 × $24', '$120.00'], ['Your S3 bucket, 38 GB × $0.023', '$0.87'], ['Month', '$124.04']] },
];

export const soloVendor: Vendor = { id: 'solo', name: 'Solo, on QuerySolo', total: 4,
  why: "One person doesn't need a shared catalog. The same workload on the Local tier is the S3 bill plus whatever you burst.",
  lines: [['All local runs', '$0.00'], ['9 burst runs', '$3.17'], ['Your S3 bucket', '$0.87'], ['Month', '$4.04']] };

export const fmt = (n: number) => '$' + n.toLocaleString('en-US');
export const maxTotal = Math.max(...vendors.map(v => v.total));
