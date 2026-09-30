// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Start real sidecars for the tests: `querysolo init` on a temp folder, then `querysolo serve`
// with the dev origin allowed; the session comes from serve.json exactly as the shell reads
// it, and spawn-to-ready is measured the way the shell measures it. Four are started: the
// second with half the first's memory limit, as the shell gives a second window (A8); the
// third with a 20 M-row table for the streaming gate; the fourth with the gauge thresholds
// lowered so every query is Red; the fifth with a stand-in bucket (Moto, public-read) for
// the attach screen, its credentials in the sidecar's environment; the sixth with the
// snapshot retention at zero days and an orders table, for the table detail; the seventh
// with a small dbt project (a view model, a table model over it, a schema.yml with two
// tests) for the Models screen.

import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { mkdtempSync, readFileSync, renameSync, writeFileSync, existsSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export const STATE_FILE = join(tmpdir(), 'querysolo-app-e2e.json');

export interface Started {
  project: string; port: number; token: string; pid: number; readyMs: number; memoryLimit: string;
  /** The fifth sidecar's bucket: the Moto endpoint, its pid, and the file that makes it add a fourth Parquet file. */
  s3?: { endpoint: string; pid: number; flag: string; prefix: string };
}

export interface SidecarSpec { memoryLimit: string; big?: boolean; red?: boolean; s3?: boolean; detail?: boolean; dbt?: boolean; questions?: boolean; moved?: boolean; bucket?: boolean }

// Each spec file owns what it imports into a sidecar; the files run in parallel outside CI.
// step 0 → the first; step 2 → the second (and counts its tables); steps 3 and 4 → the
// third (big) and the fourth (Red); step 4's settings → the second's querysolo.toml only;
// the real-data round's attach test → the fifth (s3); its table-detail test → the sixth;
// its models test → the seventh (dbt); the versions round's save-as-question and Versions
// section → the eighth (dbt with a question already saved twice). A spec that writes a model
// gets its own sidecar: the seventh's models test counts the models in it. The trust round's
// relocate test → the ninth (a project moved to another folder after its table was written).
// Decisions W1's bucket-warehouse test → the tenth (`init --warehouse s3://…` on Moto, an
// orders table imported into the bucket).
export const SIDECARS: SidecarSpec[] = [
  { memoryLimit: '2GB' },
  { memoryLimit: '1GB' },
  { memoryLimit: '2GB', big: true },
  { memoryLimit: '1GB', red: true },
  { memoryLimit: '1GB', s3: true },
  { memoryLimit: '1GB', detail: true },
  { memoryLimit: '1GB', dbt: true },
  { memoryLimit: '1GB', dbt: true, questions: true },
  { memoryLimit: '1GB', moved: true },
  { memoryLimit: '1GB', bucket: true },
];

/** The eighth sidecar's seeded question (versions brief G10): saved twice by the CLI before
 *  the page opens, so its history has two versions and a diff between them to draw. */
export const SEEDED_QUESTION = {
  title: 'Revenue by customer',
  slug: 'revenue_by_customer',
  first: 'select customer, sum(amt) as revenue from orders group by 1',
  second: 'select customer, sum(amt) as revenue from orders group by 1 order by 2 desc',
};

/** The seventh sidecar's dbt project: `stg` (a view over orders), `by_customer` (a table
 *  over `stg`), and two tests on `stg` in schema.yml. */
export const DBT_MODELS = {
  'stg.sql': "select id, customer, amt from {{ source('querysolo', 'orders') }} where amt > 0\n",
  'by_customer.sql': "{{ config(materialized='table') }}\nselect customer, sum(amt) as total from {{ ref('stg') }} group by 1\n",
  'schema.yml': [
    'version: 2',
    'sources:',
    '  - name: querysolo',
    '    database: querysolo',
    '    schema: main',
    '    tables: [{ name: orders }]',
    'models:',
    '  - name: stg',
    '    description: Orders with a positive amount.',
    '    columns:',
    '      - name: id',
    '        tests: [not_null, unique]',
    '',
  ].join('\n'),
};

export const BIG_ROWS = 20_000_000;

/** The venv's python beside the sidecar, for generating fixtures with DuckDB. */
export function venvPython(): string {
  // beside the sidecar in a venv; a frozen sidecar (ship brief S1) has no python beside it,
  // so the fixtures' DuckDB comes from the core's venv, or `QUERYSOLO_PYTHON` names one
  if (process.env.QUERYSOLO_PYTHON) return process.env.QUERYSOLO_PYTHON;
  const beside = join(dirname(sidecarExecutable()), 'python');
  if (existsSync(beside)) return beside;
  const here = dirname(fileURLToPath(import.meta.url));
  const venv = resolve(here, '..', '..', 'core', '.venv', 'bin', 'python');
  return existsSync(venv) ? venv : 'python3';
}

export function sidecarExecutable(): string {
  if (process.env.QUERYSOLO_SIDECAR) return process.env.QUERYSOLO_SIDECAR;
  const here = dirname(fileURLToPath(import.meta.url)); // an ES module: no __dirname
  const venv = resolve(here, '..', '..', 'core', '.venv', 'bin', 'querysolo');
  return existsSync(venv) ? venv : 'querysolo';
}

/** The stand-in bucket: `tests/moto_fixture.py` on the venv's python, ready when it prints its endpoint. */
async function startMoto(project: string): Promise<{ endpoint: string; child: ChildProcess; flag: string }> {
  const here = dirname(fileURLToPath(import.meta.url));
  const flag = join(project, 'add-more');
  const child = spawn(venvPython(), [join(here, 'moto_fixture.py'), flag], { stdio: ['ignore', 'pipe', 'pipe'] });
  const endpoint = await new Promise<string>((ok, fail) => {
    let out = '';
    child.stdout!.on('data', (d) => {
      out += d;
      const m = /moto (http:\/\/\S+)/.exec(out);
      if (m) ok(m[1]);
    });
    child.stderr!.on('data', (d) => { out += d; });
    child.on('exit', (code) => fail(new Error(`moto exited (${code}) before serving:\n${out}`)));
    setTimeout(() => fail(new Error(`moto not ready in 30 s:\n${out}`)), 30_000);
  });
  return { endpoint, child, flag };
}

export async function startSidecar({ memoryLimit, big, red, s3, detail, dbt, questions, moved, bucket }: SidecarSpec): Promise<{ started: Started; child: ChildProcess; extra?: ChildProcess }> {
  const exe = sidecarExecutable();
  let project = mkdtempSync(join(tmpdir(), 'querysolo-e2e-'));
  let moto: { endpoint: string; child: ChildProcess; flag: string } | undefined;
  const env: NodeJS.ProcessEnv = { ...process.env, QUERYSOLO_DEV_ORIGIN: 'http://localhost:5173' };
  if (s3 || bucket) {
    moto = await startMoto(project);
    Object.assign(env, { AWS_ENDPOINT_URL: moto.endpoint, AWS_ACCESS_KEY_ID: 'test', AWS_SECRET_ACCESS_KEY: 'test', AWS_REGION: 'us-east-1' });
    delete env.AWS_PROFILE;
  }
  const initArgs = ['init', project, '--probe-mb', '0', ...(bucket ? ['--warehouse', 's3://querysolo-test/warehouse'] : [])];
  const init = spawnSync(exe, initArgs, { encoding: 'utf8', env });
  if (init.status !== 0) throw new Error(`querysolo init failed:\n${init.stdout}\n${init.stderr}`);
  if (bucket) {
    // the table's data and metadata go to the bucket from the first import (decisions W1)
    writeFileSync(join(project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
    const imported = spawnSync(exe, ['-C', project, 'import', join(project, 'orders.csv')], { encoding: 'utf8', env });
    if (imported.status !== 0) throw new Error(`import failed:\n${imported.stdout}\n${imported.stderr}`);
  }
  if (moved) {
    // a table written here, then the whole folder moved: its metadata points at the old path
    writeFileSync(join(project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
    const imported = spawnSync(exe, ['-C', project, 'import', join(project, 'orders.csv')], { encoding: 'utf8' });
    if (imported.status !== 0) throw new Error(`import failed:\n${imported.stdout}\n${imported.stderr}`);
    const elsewhere = join(mkdtempSync(join(tmpdir(), 'querysolo-e2e-moved-')), 'acme');
    renameSync(project, elsewhere);
    project = elsewhere;
  }
  if (red) {
    // the thresholds the core's own Red test uses: everything is Red here
    const toml = join(project, 'querysolo.toml');
    writeFileSync(toml, readFileSync(toml, 'utf8')
      .replace('green_max_seconds = 60', 'green_max_seconds = 0.0000001')
      .replace('yellow_max_seconds = 600', 'yellow_max_seconds = 0.0000002'));
    writeFileSync(join(project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
    const imported = spawnSync(exe, ['-C', project, 'import', join(project, 'orders.csv')], { encoding: 'utf8' });
    if (imported.status !== 0) throw new Error(`import failed:\n${imported.stdout}\n${imported.stderr}`);
  }
  if (detail) {
    // the retention at zero days, so every snapshot but the current one is expirable now
    const toml = join(project, 'querysolo.toml');
    writeFileSync(toml, readFileSync(toml, 'utf8').replace('keep_snapshots_days = 7', 'keep_snapshots_days = 0'));
    writeFileSync(join(project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n');
    const imported = spawnSync(exe, ['-C', project, 'import', join(project, 'orders.csv')], { encoding: 'utf8' });
    if (imported.status !== 0) throw new Error(`import failed:\n${imported.stdout}\n${imported.stderr}`);
  }
  if (dbt) {
    writeFileSync(join(project, 'orders.csv'), 'id,customer,amt\n1,c1,1.5\n2,c2,3.0\n3,c1,4.5\n4,c2,-1.0\n');
    const imported = spawnSync(exe, ['-C', project, 'import', join(project, 'orders.csv')], { encoding: 'utf8' });
    if (imported.status !== 0) throw new Error(`import failed:\n${imported.stdout}\n${imported.stderr}`);
    for (const [name, text] of Object.entries(DBT_MODELS)) writeFileSync(join(project, 'models', name), text);
  }
  if (questions) {
    // Saved twice through the CLI, so the question has two versions (and a diff between them)
    // before any page opens. Each save is a commit; `querysolo versions` would list them.
    for (const sql of [SEEDED_QUESTION.first, SEEDED_QUESTION.second]) {
      const saved = spawnSync(exe, ['-C', project, 'question', 'save', SEEDED_QUESTION.title, '--sql', sql], { encoding: 'utf8' });
      if (saved.status !== 0) throw new Error(`question save failed:\n${saved.stdout}\n${saved.stderr}`);
    }
  }
  if (big) {
    // 20 M rows through DuckDB into Parquet, then imported as an Iceberg table
    const parquet = join(project, 'big.parquet');
    const gen = spawnSync(venvPython(), ['-c',
      `import duckdb; duckdb.sql("COPY (SELECT range AS id, random() AS x, 'c' || (range % 97) AS c, range * 3 AS y FROM range(${BIG_ROWS})) TO '${parquet}' (FORMAT parquet)")`,
    ], { encoding: 'utf8' });
    if (gen.status !== 0) throw new Error(`could not generate big.parquet:\n${gen.stderr}`);
    const t = Date.now();
    const imported = spawnSync(exe, ['-C', project, 'import', parquet], { encoding: 'utf8' });
    if (imported.status !== 0) throw new Error(`import of big.parquet failed:\n${imported.stdout}\n${imported.stderr}`);
    console.log(`big: ${BIG_ROWS.toLocaleString()} rows imported in ${((Date.now() - t) / 1000).toFixed(1)} s`);
  }
  const t0 = Date.now();
  const child = spawn(exe, ['-C', project, 'serve', '--port', '0', '--memory-limit', memoryLimit], {
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });
  await new Promise<void>((ok, fail) => {
    let out = '';
    child.stdout!.on('data', (d) => { out += d; if (out.includes('serving ')) ok(); });
    child.stderr!.on('data', (d) => { out += d; });
    child.on('exit', (code) => fail(new Error(`sidecar exited (${code}) before serving:\n${out}`)));
    setTimeout(() => fail(new Error(`sidecar not ready in 30 s:\n${out}`)), 30_000);
  });
  const serve = JSON.parse(readFileSync(join(project, '.querysolo', 'serve.json'), 'utf8'));
  const started: Started = { project, port: serve.port, token: serve.token, pid: child.pid!, readyMs: Date.now() - t0, memoryLimit };
  if (moto) started.s3 = { endpoint: moto.endpoint, pid: moto.child.pid!, flag: moto.flag, prefix: 's3://querysolo-test/raw/events/' };
  return { started, child, extra: moto?.child };
}

export async function startAll(): Promise<ChildProcess[]> {
  const children: ChildProcess[] = [];
  const states: Started[] = [];
  for (const spec of SIDECARS) {
    const { started, child, extra } = await startSidecar(spec);
    children.push(child);
    if (extra) children.push(extra);
    states.push(started);
  }
  writeFileSync(STATE_FILE, JSON.stringify(states));
  return children;
}

export function readStates(): Started[] {
  return JSON.parse(readFileSync(STATE_FILE, 'utf8')) as Started[];
}

/** The first sidecar: what the step 0 tests use. */
export function readState(): Started {
  return readStates()[0];
}

export function pageUrl(s: Started): string {
  return `/?port=${s.port}&token=${encodeURIComponent(s.token)}&project=${encodeURIComponent(s.project)}&ready_ms=${s.readyMs}`;
}
