// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The tables' state and verbs (app brief screen 1, real-data R4 and R7, trust T2 and T5,
// W2, L3), held by the window rather than a screen since decisions U1 and U2: the explorer
// in the sidebar starts a preview or opens a detail from any screen, and the Tables screen
// shows the preview or the detail in its results pane. A dropped path is previewed with
// /api/preview; import is /api/import on a click, in the mode the core allows (409
// table_exists offers replace or append); the list refreshes after. An s3:// prefix is
// previewed the same way and attached in place with /api/tables/attach; an attached
// table's Refresh is /api/tables/{name}/refresh.

import { useEffect, useState } from 'react';
import { Api, ApiError, humanBytes, type ImportMode, type Preview, type TableDescription, type TableInfo } from './api';
import { attachCommand, expireCommand, importCommand, defaultName, isRemote, publishCommand, refreshCommand, relocateCommand, runCommand } from './command';
import { onDrop, pickFiles, type Session } from './session';
import type { Mode } from './vocabulary';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));
const humanFiles = (n: number | null | undefined) => `${(n ?? 0).toLocaleString()} ${n === 1 ? 'file' : 'files'}`;

export interface Pending {
  path: string;
  folder: boolean;
  remote: boolean;
  anonymous: boolean;
  previews: Preview[];
  name: string;
  mode: ImportMode;
  exists?: string;
  error?: string;
}

export interface Done {
  line: string;
  text: string;
}

export interface Detail {
  table: TableDescription;
  sample?: Record<string, unknown>[];
  error?: string;
}

export interface UseTablesOptions {
  /** Undefined until the sidecar is up: every verb is then a no-op. */
  session?: Session;
  tables: TableInfo[];
  /** Screen 8: the notices' words (`model` or `question`). */
  mode: Mode;
  onChanged: () => Promise<void>;
  /** After a relocate: health and tables are read again. */
  onRelocated?: () => Promise<void>;
  /** A preview or a detail is about to show: the window brings the Tables screen up. */
  onShow?: () => void;
}

export function useTables({ session, tables, mode, onChanged, onRelocated, onShow }: UseTablesOptions) {
  const api = session ? new Api(session) : undefined;
  const [over, setOver] = useState(false);
  const [busy, setBusy] = useState<string>();
  const [dropError, setDropError] = useState<string>();
  const [pending, setPending] = useState<Pending>();
  const [done, setDone] = useState<Done>();
  const [detail, setDetail] = useState<Detail>();

  // A9: a drop previews first. Many files dropped at once: the first is previewed and the
  // rest are named, until a partner asks for more (brief §7's last unknown).
  async function preview(paths: string[], anonymous = false) {
    const path = paths[0];
    if (!path || !api) return;
    onShow?.();
    setDropError(undefined);
    setDone(undefined);
    setDetail(undefined);
    const remote = isRemote(path);
    setBusy(remote ? 'listing the prefix…' : `reading ${path.split(/[\\/]/).pop()}…`);
    try {
      const previews = await api.preview(path, undefined, anonymous);
      const folder = !remote && !/\.(csv|tsv|parquet|json|jsonl|xlsx)$/i.test(path); // a file the core previewed has one of its extensions
      setPending({ path, folder, remote, anonymous, previews, name: folder ? '' : previews[0].name, mode: 'create' });
      if (paths.length > 1) setDropError(`${paths.length} files dropped; previewing the first. Drop a folder to import several at once.`);
    } catch (e: unknown) {
      setDropError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  async function doImport(mode: ImportMode) {
    if (!pending || !api) return;
    const name = pending.folder ? undefined : pending.name.trim() || defaultName(pending.path);
    setPending({ ...pending, mode, error: undefined });
    setBusy('importing…');
    try {
      const imported = await api.import(pending.path, mode, name);
      setDone({
        line: importCommand(pending.path, mode, name),
        text: `Imported ${imported.map((t) => `${t.name} (${t.rows.toLocaleString()} rows)`).join(', ')}.`,
      });
      setPending(undefined);
      await onChanged();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === 'table_exists') {
        const m = /table (\S+) exists/.exec(e.message);
        setPending({ ...pending, mode, exists: m?.[1] ?? name ?? pending.path });
      } else {
        setPending({ ...pending, mode, error: message(e) });
      }
    } finally {
      setBusy(undefined);
    }
  }

  async function attach() {
    if (!pending || !api) return;
    const name = pending.name.trim() || pending.previews[0].name;
    setPending({ ...pending, error: undefined });
    setBusy('attaching…');
    try {
      const info = await api.attach(name, pending.path, pending.anonymous);
      setDone({
        line: attachCommand(name, pending.path, pending.anonymous),
        text: `Attached ${info.name} (${info.rows.toLocaleString()} rows in ${humanFiles(pending.previews[0].files)}) in place; nothing was copied.`,
      });
      setPending(undefined);
      await onChanged();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === 'table_exists') {
        setPending({ ...pending, exists: name, error: `Table ${name} already exists; pick another name.` });
      } else {
        setPending({ ...pending, error: message(e) });
      }
    } finally {
      setBusy(undefined);
    }
  }

  async function refresh(name: string) {
    if (!api) return;
    setDropError(undefined);
    setBusy(`refreshing ${name}…`);
    try {
      const r = await api.refresh(name);
      setDone({
        line: refreshCommand(name),
        text: `Refreshed ${r.name}: ${r.added} ${r.added === 1 ? 'file' : 'files'} added; ${r.files} files, ${r.rows.toLocaleString()} rows.`,
      });
      await onChanged();
      if (detail?.table.name === name) setDetail({ table: await api.describe(name) });
    } catch (e: unknown) {
      if (detail?.table.name === name) setDetail({ ...detail, error: message(e) });
      else setDropError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  /** `querysolo run --stale` from a table's detail (L3): its commits made models out of date. */
  async function runStale() {
    if (!detail || !api) return;
    const name = detail.table.name;
    setDropError(undefined);
    setBusy('building what changed…');
    try {
      const r = await api.run([], false, true);
      const built = r.selected ?? r.results.map((x) => x.name);
      setDone({
        line: runCommand([], { stale: true }),
        text: built.length === 0 ? `Every ${mode === 'simple' ? 'question' : 'model'} is up to date; nothing ran.` : r.ok ? `Built ${built.join(', ')} in ${r.seconds.toFixed(1)} s.` : `${r.results.filter((x) => x.status !== 'success').length} of ${r.results.length} failed.`,
      });
      await onChanged();
      setDetail({ table: await api.describe(name) });
    } catch (e: unknown) {
      setDetail((d) => (d ? { ...d, error: message(e) } : d));
    } finally {
      setBusy(undefined);
    }
  }

  /** `querysolo tables publish` (W2): the detail's box; a dry run only reports, a real one
   *  refreshes the list and the detail and says what moved. */
  async function publish(name: string, prefix: string, dryRun: boolean, yes: boolean) {
    if (!api) throw new Error('the core is not running');
    const r = await api.publish(name, prefix, dryRun, yes);
    if (!dryRun) {
      setDone({
        line: publishCommand(name, prefix, { yes }),
        text: `Published ${r.name} to ${r.target}: ${r.copied} ${r.copied === 1 ? 'file' : 'files'} copied${r.skipped ? `, ${r.skipped} already there` : ''}, ${humanBytes(r.bytes)}; the local files are orphans for expire.`,
      });
      await onChanged();
      setDetail({ table: await api.describe(name) });
    }
    return r;
  }

  /** `querysolo relocate` (T5): the folder moved; the tables' locations are rewritten under it. */
  async function relocate() {
    if (!api) return;
    setDropError(undefined);
    setBusy('relocating…');
    try {
      const r = await api.relocate();
      setDone({
        line: relocateCommand(),
        text: `Relocated ${r.relocated.length} ${r.relocated.length === 1 ? 'table' : 'tables'} from ${r.old_root ?? 'where they were'}: ${r.relocated.join(', ') || 'none'}${r.skipped.length ? `; skipped ${r.skipped.join(', ')}` : ''}.`,
      });
      await onChanged();
      if (onRelocated) await onRelocated();
    } catch (e: unknown) {
      setDropError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  /** `querysolo tables attach --replace <name> <prefix>` (T2): after the prefix's files changed. */
  async function reattach(name: string, source: string, anonymous: boolean) {
    if (!api) return;
    setDropError(undefined);
    setBusy(`registering ${name} again…`);
    try {
      const info = await api.attach(name, source, anonymous, true);
      setDone({
        line: attachCommand(name, source, anonymous, true),
        text: `Registered ${info.name} again: ${info.rows.toLocaleString()} rows in place at ${source}.`,
      });
      await onChanged();
      if (detail?.table.name === name) setDetail({ table: await api.describe(name) });
    } catch (e: unknown) {
      if (detail?.table.name === name) setDetail({ ...detail, error: message(e) });
      else setDropError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  // An open detail follows the table: a statement on screen 2 that wrote it (a delete, an
  // insert) changes the list, and the detail re-reads `describe` when its row changes.
  const detailName = detail?.table.name;
  const detailKey = tables.find((t) => t.name === detailName)?.freshness ?? null;
  useEffect(() => {
    if (!detailName || !detailKey || !api) return;
    let live = true;
    api.describe(detailName).then((table) => { if (live) setDetail((d) => (d && d.table.name === detailName ? { ...d, table } : d)); }).catch(() => {});
    return () => { live = false; };
  }, [detailName, detailKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // R7: a row opens `describe` as a panel; sample and expire are the verbs they say.
  async function open(name: string) {
    if (!api) return;
    onShow?.();
    setDropError(undefined);
    setPending(undefined);
    setBusy(`describing ${name}…`);
    try {
      setDetail({ table: await api.describe(name) });
    } catch (e: unknown) {
      setDropError(message(e));
    } finally {
      setBusy(undefined);
    }
  }

  async function sample() {
    if (!detail || !api) return;
    setBusy('reading rows…');
    try {
      setDetail({ ...detail, sample: await api.sample(detail.table.name), error: undefined });
    } catch (e: unknown) {
      setDetail({ ...detail, error: message(e) });
    } finally {
      setBusy(undefined);
    }
  }

  async function expire() {
    if (!detail || !api) return;
    const name = detail.table.name;
    setBusy('expiring…');
    try {
      const r = await api.expire(name);
      setDone({
        line: expireCommand(name),
        text: `Expired ${r.snapshots_removed} of ${r.snapshots_before} ${r.snapshots_before === 1 ? 'snapshot' : 'snapshots'} of ${r.name}; ${r.files_removed} ${r.files_removed === 1 ? 'file' : 'files'} removed, ${humanBytes(r.bytes_reclaimed)} reclaimed.`,
      });
      await onChanged();
      setDetail({ table: await api.describe(name) });
    } catch (e: unknown) {
      setDetail({ ...detail, error: message(e) });
    } finally {
      setBusy(undefined);
    }
  }

  async function choose() {
    try {
      const paths = await pickFiles();
      if (paths.length) await preview(paths);
    } catch (e: unknown) {
      setDropError(message(e));
    }
  }

  useEffect(() => {
    const off = onDrop((e) => {
      if (e.kind === 'drop') { setOver(false); void preview(e.paths); }
      else setOver(e.kind === 'over');
    });
    return () => { off.then((f) => f()); };
  }, [session?.port, session?.token]); // eslint-disable-line react-hooks/exhaustive-deps -- a restart brings a new session and a new listener

  return {
    over, busy, dropError, pending, done, detail,
    preview, doImport, attach, refresh, runStale, publish, relocate, reattach, open, sample, expire, choose,
    setPending, setDetail,
  };
}

export type TablesWork = ReturnType<typeof useTables>;
