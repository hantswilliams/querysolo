// What is built and what is not. THE one place on the site that knows.
//
// Rule (web/TASKS.md): the marketing pages may describe the plan, but they may not
// imply the plan is shipped. Any page that names an unbuilt thing carries <BuildState/>,
// which reads this file. When a session ships, edit here and every page follows.
//
// This must agree with src/content/docs/index.md, which is the authority because it
// describes the code. Where they disagree, index.md is right and this file is the bug.

export const asOf = '2026-09-18';

// Last reconciled against src/content/docs/index.md: 2026-09-18, after S3 writes,
// table publishing, and the Lineage and Changes screens landed. This file also
// feeds README.md's status block (web/scripts/gen-readme-status.py, checked in CI).

export type State = 'built' | 'planned';

export type Surface = {
  /** stable key, used by pageState below */
  id: string;
  /** what a visitor calls it */
  label: string;
  state: State;
  /** one clause: what you can do with it today, or what has to happen first */
  detail: string;
  /** for planned things: the build session that does it (see build-sessions/) */
  session?: string;
  /** deep link into the developer docs, for built things */
  href?: string;
};

export const surfaces: Surface[] = [
  // ---- built -------------------------------------------------------------
  { id: 'cli', label: 'The CLI', state: 'built',
    detail: 'init, import, sql, estimate, tables, config — from a clone, with uv',
    href: '/docs/cli' },
  { id: 'gauge', label: 'Lookahead (the gauge)', state: 'built',
    detail: 'the verdict and its sentence before anything runs; Red refuses, and every run is recorded',
    href: '/docs/gauge' },
  { id: 'tables', label: 'Files into Iceberg tables', state: 'built',
    detail: 'CSV, TSV, Parquet, JSON, JSONL and Excel, with the type coercions written down',
    href: '/docs/tables' },
  { id: 's3', label: 'Parquet already in S3', state: 'built',
    detail: 'attach, refresh and discover a prefix in place — nothing copied, and public buckets need no credentials',
    href: '/docs/remote' },
  { id: 'catalog', label: 'The Iceberg REST catalog', state: 'built',
    detail: 'SQLite locally, served over HTTP; DuckDB, pyiceberg, Spark and Trino all read it',
    href: '/docs/catalog' },
  { id: 'questions', label: 'Saved questions as dbt models', state: 'built',
    detail: 'each one written with two checks, built through the catalog by dbt',
    href: '/docs/questions' },
  { id: 'dbtrun', label: 'querysolo run — the dbt DAG, by verdict', state: 'built',
    detail: 'every model gets its own verdict before it builds, dbt runs through the catalog, and view models become Iceberg views every engine can see',
    href: '/docs/dbt' },
  { id: 'api', label: 'The local HTTP API', state: 'built',
    detail: 'querysolo serve, loopback only, bearer token, results as an Arrow stream',
    href: '/docs/api' },
  { id: 'app', label: 'The desktop app', state: 'built',
    detail: 'from source, no installer: projects, a sidebar with the table explorer, the query workspace (SQL over the results on a split, the verdict before the rows, the streaming grid, the auto-chart, the table detail in the results pane), the Gauge screen with estimate-versus-actual, settings',
    href: '/docs/app' },
  { id: 'audit', label: 'Proof it stays put', state: 'built',
    detail: 'querysolo audit network measures zero outbound attempts on the quickstart; PRIVACY.md says exactly what is stored where',
    href: '/docs/install' },
  { id: 'versions', label: 'Every save is a version', state: 'built',
    detail: 'the project is a git repository, a save or a run is a commit, querysolo versions and restore, the Versions section on the model detail',
    href: '/docs/questions' },
  { id: 's3warehouse', label: 'A warehouse in a bucket', state: 'built',
    detail: 'querysolo init --warehouse s3://bucket/prefix puts every table\'s data and metadata in the bucket; import, run, expire and every reader work against it, tested on Moto and a real bucket; querysolo tables publish moves one local table into a bucket later, every snapshot kept',
    href: '/docs/remote' },
  { id: 'lineage', label: 'Lineage, and whether a model is out of date', state: 'built',
    detail: 'querysolo lineage says what a table, view or model reads and what reads it, and how each edge is known; every model carries a state — fresh, edited, upstream, never — with what changed, and querysolo run --stale builds only what is not',
    href: '/docs/tables#lineage' },
  { id: 'changes', label: 'What happened: the changes feed', state: 'built',
    detail: 'querysolo changes merges every table\'s snapshots, every run of each model and question and the versions git holds into one list, newest first; the app\'s Changes screen and a Recent strip on every detail read the same route',
    href: '/docs/tables#what-happened-the-changes-feed' },
  { id: 'recovery', label: 'Backups, crashes, upgrades and moves', state: 'built',
    detail: 'a copy of the folder is the backup, a failed replace keeps the old table, a moved folder is relocated, a newer schema is refused — every sentence tested',
    href: '/docs/recovery' },

  // ---- planned -----------------------------------------------------------
  { id: 'slice', label: 'A slice of a warehouse you do not own', state: 'planned',
    detail: 'the third door: pull a read-only, refreshable slice onto the laptop and let the verdict say what fits here',
    session: 'N2, after the outsider sessions' },
  { id: 'ask', label: 'The ask box (English → SQL)', state: 'planned',
    detail: 'model providers, streaming SQL, one repair pass',
    session: 'session 7 — deprioritised 2026-09-11' },
  { id: 'burst', label: 'Burst to a worker', state: 'planned',
    detail: 'the control plane, the job token, the cap, results back. Every burst number on this site is arithmetic from the plan, not a measurement',
    session: 'session 8' },
  { id: 'mcp', label: 'querysolo mcp (the agent tools)', state: 'planned',
    detail: 'the MCP server, per-tool permissions, the per-agent daily cap and the audit log',
    session: 'session 5, after session 8' },
  { id: 'team', label: 'The Team catalog', state: 'planned',
    detail: 'hosted Postgres, vended credentials, scheduled runs, compaction and alerts',
    session: 'session 8 onward' },
  { id: 'installers', label: 'Installers and a brew tap', state: 'planned',
    detail: 'signed DMG, the extensions bundled, a PyPI release. Until then: clone and uv sync',
    session: 'session 10' },
  { id: 'correction', label: 'Per-machine correction', state: 'planned',
    detail: "the gauge's constants were tuned on one machine; the record is kept, the correction is not applied yet",
    session: 'session 10' },
  { id: 'selfhosted', label: 'Self-hosted', state: 'planned',
    detail: 'the catalog and control plane in your own VPC, SSO, audit to your SIEM',
    session: 'after the Team tier' },
];

const by = (id: string): Surface => {
  const s = surfaces.find(x => x.id === id);
  if (!s) throw new Error(`src/data/status.ts: no surface "${id}"`);
  return s;
};

export const pick = (ids: string[]): Surface[] => ids.map(by);

/** Which surfaces each page should own up about, in the order they should read. */
export const pageState: Record<string, { built: string[]; planned: string[]; note: string }> = {
  app: {
    built: ['app', 'gauge', 'dbtrun', 'tables', 's3', 'lineage', 'changes'],
    planned: ['ask', 'burst', 'mcp', 'installers'],
    note: 'Screens 1, 2 and 5 are real and run today, from source, along with the table detail. The rest of this page is design, not software — it is here so you can see where it goes, and it is labelled so you never have to guess which is which.',
  },
  agents: {
    built: ['cli', 'api', 'catalog', 'gauge'],
    planned: ['mcp', 'burst', 'team'],
    note: 'This page is the specification for the agent surface, written before it is built, so that the tools, the permissions and the cap are designed in the open. None of the MCP tools below can be called today.',
  },
};
