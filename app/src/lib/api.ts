// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The core's /api (docs: the local HTTP API), called directly from the webview.

import type { BucketCheck, Session } from './session';

export interface Health {
  querysolo: string;
  duckdb: string;
  project: string;
  root: string;
  machine: { ram?: number; threads?: number; memory_limit?: number; memory_limit_text?: string };
  throughput_local_mbps: number | null;
  /** How the disk figure was measured: cache bypassed (`nocache`, `direct`), or `cached` and capped. */
  throughput_probe?: 'nocache' | 'direct' | 'cached' | 'none';
  bandwidth_mbps: number | null;
  /** Whether the core has AWS credentials, and from where (never a key). */
  aws?: { configured: boolean; source: 'environment' | 'profile' | 'none'; profile: string | null; region: string; endpoint: string | null };
  /** The folder this project's tables were written in, when it is not this one (trust round T5). */
  moved_from?: string | null;
}

export interface TableInfo {
  name: string;
  rows: number;
  bytes: number;
  columns: [string, string][];
  location: string;
  snapshot_id: number | null;
  /** When the current snapshot was committed, ISO 8601. */
  freshness: string | null;
  /** The prefix an attached table was registered from; null for a table QuerySolo wrote. */
  source?: string | null;
  /** Read without credentials (a public bucket). */
  public?: boolean;
  /** `table`, or `view` for a catalog view (real-data R6), whose rows and bytes are 0. */
  kind?: 'table' | 'view';
  view_sql?: string | null;
  /** A replace interrupted between its drop and its rename (T1): the name it was meant to become. */
  interrupted_replace_of?: string | null;
  /** The folder moved and this table's metadata points at where it was (T5). */
  needs_relocate?: boolean;
}

/** One edge of `GET /lineage/{name}` (versions brief G8): a table or view in the catalog,
 *  or a model not built yet; `via` is how the edge is known — a dbt `ref()` or `source()`,
 *  a table named bare in the model's SQL, or a catalog view's SQL. */
export interface LineageEdge {
  name: string;
  kind: 'table' | 'view' | 'model';
  via: 'ref' | 'source' | 'sql' | 'view';
  /** 1 for a direct edge; more when the call asked for depth. */
  depth: number;
}

/** `querysolo lineage <name>`: what it reads and what reads it, and who built it. */
export interface Lineage {
  name: string;
  kind: 'table' | 'view' | 'model';
  upstream: LineageEdge[];
  downstream: LineageEdge[];
  /** The model that builds it, `imported`, `attached from <prefix>`, or null (never built; a view put by hand). */
  built_by: string | null;
  last_built: string | null;
  compiled: boolean;
}

/** One node of the whole graph (`GET /lineage`, decisions L1): a table or view in the
 *  catalog or a model not built yet; `model` says a dbt model builds it, and then `state`
 *  is its state as the Models screen shows it. */
export interface LineageNode {
  name: string;
  kind: 'table' | 'view' | 'model';
  model: boolean;
  state: ModelState | null;
  state_reason: string | null;
  /** The prefix an attached table was registered from. */
  source: string | null;
  freshness: string | null;
}

/** `querysolo changes` (decisions L2): one entry of the feed. `kind` says the source — a
 *  table's `snapshot`, a model's or question's last `run`, a git `version` — and `target`
 *  what `name` is, for the link; a version names everything it touched in `names`. */
export interface Change {
  when: string;
  kind: 'snapshot' | 'run' | 'version';
  name: string | null;
  target: 'table' | 'model' | 'question' | 'project';
  operation: string | null;
  snapshot_id: number | null;
  added_rows: number | null;
  deleted_rows: number | null;
  /** The models the snapshot made out of date (L3). */
  affects: string[];
  ok: boolean | null;
  seconds: number | null;
  verdict: string | null;
  error: string | null;
  /** The version's short id, author and message. */
  id: string | null;
  author: string | null;
  message: string | null;
  names: string[];
}

export interface ChangesQuery { since?: string; last?: number; name?: string }

/** `querysolo lineage --all`: the whole project as the Lineage screen draws it. */
export interface LineageGraph {
  nodes: LineageNode[];
  edges: { from: string; to: string; via: LineageEdge['via'] }[];
  compiled: boolean;
}

/** `POST /tables/{name}/publish` (`querysolo tables publish`, decisions W2): a table moved into a bucket. */
export interface PublishReport {
  name: string;
  source: string;
  target: string;
  files: number;
  bytes: number;
  copied: number;
  skipped: number;
  metadata_files: number;
  data_files: number;
  /** The bandwidth figure's estimate for the copy, when the cache has one. */
  seconds: number | null;
  dry_run: boolean;
}

/** `POST /relocate` (`querysolo relocate`, trust round T5). */
export interface RelocateReport {
  old_root: string | null;
  new_root: string;
  relocated: string[];
  skipped: string[];
  metadata_files: number;
  data_files: number;
}

export interface Snapshot {
  id: number;
  timestamp: string;
  operation: string | null;
  added_rows: number | null;
  added_bytes: number | null;
  added_files: number | null;
  deleted_rows: number | null;
  total_rows: number | null;
  current: boolean;
  expirable: boolean;
  /** The models this snapshot made out of date — their last run predates it — in dependency order (decisions L3). */
  affects?: string[];
}

/** `querysolo tables describe`: the list's fields plus partitioning, the snapshots, and what `expire` would take. */
export interface TableDescription extends TableInfo {
  partitioning: string;
  expirable_snapshots: number;
  reclaimable_bytes: number;
  keep_days: number;
  last_commit: { snapshot_id?: number; operation?: string | null; timestamp?: string };
  snapshots: number;
  format_version: number;
  snapshot_list: Snapshot[];
  /** A view's properties (`querysolo.dbt-model` names the dbt model it came from); empty for a table. */
  properties?: Record<string, string>;
  /** An attached table (trust round T2): when its files were last verified against the
   *  prefix, the ones changed under the same path since as `[uri, why]`, or why the
   *  prefix could not be listed. */
  verified_at?: string | null;
  changed_files?: [string, string][];
  verify_error?: string | null;
  /** A table published to a bucket (W2) whose files are still under the local warehouse, until `expire`. */
  local_copy_files?: number;
}

export interface ExpireReport {
  name: string;
  keep_days: number;
  snapshots_before: number;
  snapshots_removed: number;
  files_removed: number;
  bytes_reclaimed: number;
}

/** A recorded run (`/api/history`), the fields the Gauge screen reads. */
export interface HistoryRun {
  id: number;
  ts: string;
  verdict: string | null;
  ran: boolean;
  ran_where: string;
  est_bytes: number | null;
  est_wall_local: number | null;
  actual_wall: number | null;
  actual_bytes: number | null;
  error: string | null;
  sql_text: string;
}

export interface GaugeSummary {
  runs: number;
  compared: number;
  within_2x: number;
  within_2x_share: number | null;
  green_over_3min: number;
}

/** A test on a dbt model from `schema.yml` (Simple mode calls it a check). */
export interface ModelTest {
  name: string;
  /** `not_null`, `unique`, `accepted_values`, `relationships`, a project's own, or `singular` (a SQL file under `tests/`). */
  kind: string;
  column: string | null;
  unique_id: string;
}

/** A model's last `querysolo run`, from history. */
export interface LastRun {
  ts: string;
  ok: boolean;
  seconds: number | null;
  verdict: string | null;
  error: string | null;
  /** The hash of the compiled SQL that run built (V3: an edit since is `edited`). */
  sql_hash?: string | null;
}

/** A model's state (decisions V3, versions step 4): `fresh` (nothing it is made of changed
 *  since its last successful run), `edited` (its own SQL did), `upstream` (a table or view
 *  it reads changed, or a model it reads is not fresh), `never` (no successful run). */
export type ModelState = 'fresh' | 'edited' | 'upstream' | 'never';

/** One model of `querysolo run --plan` (`GET /api/run/plan`): compiled, estimated, in dependency order. */
export interface PlannedModel {
  name: string;
  unique_id: string;
  materialized: string;
  depends_on: string[];
  compiled_sql: string;
  verdict: string | null;
  words: string | null;
  reason: string | null;
  est_wall_local: number | null;
  est_bytes: number | null;
  /** The gauge could not estimate it (the run will say). */
  error: string | null;
  description: string;
  path: string;
  tests: ModelTest[];
  last_run: LastRun | null;
  state: ModelState | null;
  /** Why it is not fresh, naming what changed: "orders changed", "by_c is out of date",
   *  "the SQL changed since the last run", "never built", "the last run failed". */
  state_reason: string | null;
  /** When, ISO 8601, when a time is known. */
  state_since: string | null;
  /** `edited`: the unified diff of the compiled SQL the last run built against the SQL now. */
  state_diff?: string | null;
  /** `upstream` naming a table or view: what was committed to it since the run, newest first. */
  state_changes?: StateChange[];
}

/** One commit to a table (or a new version of a view) since a model's last run (V3). */
export interface StateChange {
  name: string;
  /** Iceberg's `append`, `overwrite`, `delete`, `replace`, or `new version` for a view. */
  operation: string | null;
  added_rows: number | null;
  deleted_rows: number | null;
  timestamp: string | null;
}

export interface ModelResult {
  name: string;
  status: string;
  seconds: number;
  message: string | null;
}

/** `POST /api/run`: what `querysolo run` did. */
export interface RunReport {
  models: PlannedModel[];
  results: ModelResult[];
  views_recorded: string[];
  views_dropped: string[];
  seconds: number;
  ok: boolean;
  /** A `stale` run: the models it chose because they were not fresh (empty: nothing ran); null otherwise. */
  selected?: string[] | null;
}

export interface PreviewColumn {
  name: string;
  duckdb_type: string;
  iceberg_type: string;
  note: string;
}

export interface Preview {
  name: string;
  source: string;
  columns: PreviewColumn[];
  sample: unknown[][];
  /** A remote prefix's preview (`tables attach`, not `import`): what would be registered in place. */
  remote?: boolean;
  files?: number | null;
  bytes?: number | null;
  anonymous?: boolean;
}

export type ImportMode = 'create' | 'replace' | 'append';

/** A saved question as `POST /questions` answers it (versions brief G3, G7): the model it
 *  wrote, and the version the save recorded — `commit` null when nothing changed, `git` the
 *  reason when the repository could not be written. */
export interface Question {
  slug: string;
  title: string;
  sql: string;
  path: string;
  created: string | null;
  last_run: string | null;
  commit: string | null;
  git: string | null;
}

/** One entry of a model's history (`GET /versions/{name}`, versions brief G5): a commit
 *  that changed the model's SQL or, marked, only its checks; `diff` is the unified diff of
 *  the file against the version before it, which the Versions section draws. */
export interface Version {
  id: string;
  when: string;
  /** Git's own identity: `Name <email>`. */
  author: string;
  message: string;
  sql_changed: boolean;
  checks_changed: boolean;
  diff: string;
}

/** `GET /git` (G6): the one line the model panel says about git. */
export interface GitStatus {
  repository: boolean;
  branch: string | null;
  origin: string | null;
}

/** `POST /estimate` (`querysolo estimate`), the fields the Versions section reads for "Gauge then". */
export interface Estimate {
  verdict: string;
  words: string;
  reason: string;
  wall_local: number;
  bytes_scanned: number;
}

export type SettingKey ='engine.memory_limit' | 'engine.threads' | 'gauge.share_calibration' | 'catalog.keep_snapshots_days' | 'git.auto_commit';

export interface Settings {
  settings: Record<SettingKey, string | number | boolean>;
  path: string;
  note: string;
}

/** An error the core answered with: `{error, message}` and the HTTP status. */
export class ApiError extends Error {
  constructor(public readonly status: number, public readonly code: string, message: string) {
    super(message);
  }
}

export class Api {
  constructor(private readonly session: Session) {}

  get base(): string {
    return `http://127.0.0.1:${this.session.port}/api`;
  }

  get token(): string {
    return this.session.token;
  }

  private headers(extra: Record<string, string> = {}): Record<string, string> {
    return { Authorization: `Bearer ${this.session.token}`, ...extra };
  }

  private async answer<T>(r: Response, path: string): Promise<T> {
    if (r.ok) return (await r.json()) as T;
    const text = await r.text();
    try {
      const body = JSON.parse(text) as { error?: string; message?: string };
      if (body.error) throw new ApiError(r.status, body.error, body.message ?? body.error);
    } catch (e) {
      if (e instanceof ApiError) throw e;
    }
    throw new ApiError(r.status, 'http', `${path}: ${r.status} ${text}`);
  }

  async get<T>(path: string): Promise<T> {
    return this.answer<T>(await fetch(`${this.base}${path}`, { headers: this.headers() }), path);
  }

  async post<T>(path: string, body: unknown): Promise<T> {
    const r = await fetch(`${this.base}${path}`, {
      method: 'POST',
      headers: this.headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify(body),
    });
    return this.answer<T>(r, path);
  }

  health(): Promise<Health> {
    return this.get<Health>('/health');
  }

  tables(): Promise<TableInfo[]> {
    return this.get<TableInfo[]>('/tables');
  }

  /** A file's preview, or a folder's: one per file `import` would take (A9); an `s3://`
   *  prefix's: the columns of one footer and the files it would register (real-data R4). */
  async preview(path: string, name?: string, anonymous = false): Promise<Preview[]> {
    const body: Record<string, unknown> = { path };
    if (name) body.name = name;
    if (anonymous) body.anonymous = true;
    const p = await this.post<Preview | Preview[]>('/preview', body);
    return Array.isArray(p) ? p : [p];
  }

  /** `querysolo tables attach <name> [--anonymous] <prefix>`: registered in place, nothing
   *  copied; `replace` registers the prefix again over an existing table (T2). */
  attach(name: string, source: string, anonymous = false, replace = false): Promise<TableInfo> {
    return this.post<TableInfo>('/tables/attach', { name, source, anonymous, replace });
  }

  history(last = 200): Promise<HistoryRun[]> {
    return this.get<HistoryRun[]>(`/history?last=${last}`);
  }

  gaugeSummary(): Promise<GaugeSummary> {
    return this.get<GaugeSummary>('/gauge/summary');
  }

  /** `querysolo gauge export`: written into the project, nothing sent. */
  gaugeExport(): Promise<{ path: string; runs: number }> {
    return this.post('/gauge/export', {});
  }

  /** `querysolo gauge reset --yes`. */
  gaugeReset(): Promise<{ removed: number }> {
    return this.post('/gauge/reset', {});
  }

  /** `querysolo gauge probe`: measure the disk again. */
  gaugeProbe(): Promise<{ mbps: number; method: string; size_bytes: number }> {
    return this.post('/gauge/probe', {});
  }

  describe(name: string): Promise<TableDescription> {
    return this.get<TableDescription>(`/tables/${encodeURIComponent(name)}`);
  }

  /** `querysolo tables sample <name> -n 5`: the first rows, as objects keyed by column. */
  sample(name: string, n = 5): Promise<Record<string, unknown>[]> {
    return this.get<Record<string, unknown>[]>(`/tables/${encodeURIComponent(name)}/sample?n=${n}&truncate=80`);
  }

  /** `querysolo tables expire <name>`: snapshots past the retention and the files only they used. */
  expire(name: string): Promise<ExpireReport> {
    return this.post<ExpireReport>(`/tables/${encodeURIComponent(name)}/expire`, {});
  }

  /** `querysolo tables refresh <name>`: the files new under the prefix since the attach. */
  refresh(name: string): Promise<{ name: string; added: number; files: number; rows: number }> {
    return this.post(`/tables/${encodeURIComponent(name)}/refresh`, {});
  }

  /** `querysolo run --plan [select]...`: the DAG through the gauge, nothing built. */
  runPlan(select: string[] = []): Promise<PlannedModel[]> {
    return this.get<PlannedModel[]>(select.length ? `/run/plan?select=${encodeURIComponent(select.join(','))}` : '/run/plan');
  }

  /** `querysolo run [select]... [--run-anyway]`: build the DAG here; a Red model refuses
   *  (409 `red_refused`) until `run_anyway`. */
  /** `querysolo run [<models>] [--run-anyway] [--stale]`; `stale` (V3) builds only what is not fresh. */
  run(select: string[] = [], runAnyway = false, stale = false): Promise<RunReport> {
    return this.post<RunReport>('/run', { select, burst: 'never', run_anyway: runAnyway, stale });
  }

  settings(): Promise<Settings> {
    return this.get<Settings>('/settings');
  }

  /** `querysolo config set <key> <value>`: one line of querysolo.toml rewritten in place. */
  async setSetting(key: SettingKey, value: string): Promise<Settings> {
    const r = await fetch(`${this.base}/settings`, {
      method: 'PUT',
      headers: this.headers({ 'Content-Type': 'application/json' }),
      body: JSON.stringify({ key, value }),
    });
    return this.answer<Settings>(r, '/settings');
  }

  import(path: string, mode: ImportMode, name?: string): Promise<TableInfo[]> {
    return this.post<TableInfo[]>('/import', name ? { path, name, mode } : { path, mode });
  }

  /** `querysolo question save '<title>' --sql '<sql>'`: the question becomes a dbt model with
   *  two checks, and the save is a version. A title already saved is 409 `question_exists`
   *  until `replace`, the way an import onto an existing table is (versions brief G7). */
  saveQuestion(title: string, sql: string, replace = false): Promise<Question> {
    return this.post<Question>('/questions', { title, sql, replace });
  }

  /** `querysolo versions <name>`: the model's history, newest first, with the diffs (G5). */
  versions(name: string): Promise<Version[]> {
    return this.get<Version[]>(`/versions/${encodeURIComponent(name)}`);
  }

  /** That version's SQL, as the file was. */
  versionSql(name: string, id: string): Promise<{ name: string; id: string; sql: string }> {
    return this.get(`/versions/${encodeURIComponent(name)}/${encodeURIComponent(id)}`);
  }

  /** `querysolo restore <name> <id>`: that version written back and committed as a new one;
   *  `commit` null when the file already held it. */
  restore(name: string, id: string): Promise<{ name: string; commit: string | null; git: string | null }> {
    return this.post(`/versions/${encodeURIComponent(name)}/restore`, { id });
  }

  git(): Promise<GitStatus> {
    return this.get<GitStatus>('/git');
  }

  /** `querysolo lineage --all`: the whole graph (L1). */
  lineageAll(): Promise<LineageGraph> {
    return this.get<LineageGraph>('/lineage');
  }

  /** `querysolo changes [name] [--since] [--last]`: the feed (L2). */
  changes(q: ChangesQuery = {}): Promise<Change[]> {
    const params = new URLSearchParams();
    if (q.since) params.set('since', q.since);
    if (q.last) params.set('last', String(q.last));
    if (q.name) params.set('name', q.name);
    const qs = params.toString();
    return this.get<Change[]>(`/changes${qs ? `?${qs}` : ''}`);
  }

  /** `querysolo lineage <name> --depth N`: reads from and feeds, one level by default (G8). */
  lineage(name: string, depth = 1): Promise<Lineage> {
    return this.get<Lineage>(`/lineage/${encodeURIComponent(name)}?depth=${depth}`);
  }

  /** `querysolo tables publish <name> <prefix> [--dry-run] [--yes]` (W2). 409 `not_publishable` with the reason. */
  publish(name: string, prefix: string, dryRun = false, yes = false): Promise<PublishReport> {
    return this.post<PublishReport>(`/tables/${encodeURIComponent(name)}/publish`, { prefix, dry_run: dryRun, yes });
  }

  /** `querysolo bucket check` (decisions P1) through this core, for the New project dialog. */
  checkBucket(prefix: string): Promise<BucketCheck> {
    return this.post<BucketCheck>('/bucket/check', { prefix });
  }

  /** `querysolo relocate`: after the folder moved, the tables' locations rewritten under it. */
  relocate(): Promise<RelocateReport> {
    return this.post<RelocateReport>('/relocate', {});
  }

  /** `querysolo estimate '<sql>'`: the gauge's verdict for a statement, nothing run. */
  estimate(sql: string): Promise<Estimate> {
    return this.post<Estimate>('/estimate', { sql });
  }
}

export const humanBytes = (n: number): string => {
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let i = 0;
  while (n >= 1000 && i < units.length - 1) { n /= 1000; i++; }
  return i < 2 ? `${Math.round(n)} ${units[i]}` : `${n.toFixed(1)} ${units[i]}`;
};

/** "just now", "4 min ago", "3 h ago", "2 d ago", or the date: freshness the way a panel says it. */
export const ago = (iso: string | null, now = Date.now()): string => {
  if (!iso) return '—';
  const s = Math.max(0, (now - Date.parse(iso)) / 1000);
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  if (s < 7 * 86400) return `${Math.floor(s / 86400)} d ago`;
  return iso.slice(0, 10);
};
