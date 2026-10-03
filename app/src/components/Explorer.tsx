// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The explorer (decisions U2), the sidebar's lower half: every table and view in the
// catalog from /api/tables — name, rows, where its data is (local, a bucket, an attached
// prefix, public or not, a view) and the freshness dot, whose colour is how long ago the
// table was last written — under the drop zone and Import…. A row opens the table's detail
// on the Tables screen (real-data brief R7); an attached table offers Refresh (D27).

import { ago, type Health, type TableInfo } from '../lib/api';
import { DropZone } from './DropZone';

export interface ExplorerProps {
  tables: TableInfo[];
  busy?: string;
  /** True inside the app, where a drop carries paths and there is a file dialog. */
  native: boolean;
  /** A drag is over the window (the app's event). */
  over: boolean;
  /** The core's credentials, from health, for the drop zone's line. */
  aws?: Health['aws'];
  onPaths: (paths: string[], anonymous?: boolean) => void;
  onChoose: () => void;
  onRefresh: (name: string) => void;
  onOpen: (name: string) => void;
  /** The table whose detail is open, marked in the list. */
  open?: string;
}

function Where({ t }: { t: TableInfo }) {
  if (t.kind === 'view') return <span title={t.view_sql ?? ''} data-testid={`where-${t.name}`}>view</span>;
  if (!t.source && t.location.startsWith('s3://')) {
    // a bucket warehouse (decisions W1): QuerySolo's own table, its files in the bucket
    return <span title={t.location} className="where" data-testid={`where-${t.name}`}>bucket <span className="mono muted">{t.location.replace(/^s3:\/\//, '').split('/')[0]}/…</span></span>;
  }
  if (!t.source) return <span>local</span>;
  return (
    <span title={t.source} className="where" data-testid={`where-${t.name}`}>
      {t.public ? 'public' : 'attached'} <span className="mono muted">{t.source.replace(/^s3:\/\//, '').split('/')[0]}/…</span>
    </span>
  );
}

const DAY = 24 * 3600 * 1000;

/** The dot's colour: written today, this week, or longer ago. */
export function freshnessClass(iso: string | null | undefined, now = Date.now()): 'today' | 'week' | 'old' | 'none' {
  if (!iso) return 'none';
  const age = now - new Date(iso).getTime();
  if (Number.isNaN(age)) return 'none';
  return age < DAY ? 'today' : age < 7 * DAY ? 'week' : 'old';
}

export function Explorer({ tables, busy, native, over, aws, onPaths, onChoose, onRefresh, onOpen, open }: ExplorerProps) {
  return (
    <section className="explorer" data-testid="tables" aria-label="Tables">
      <DropZone native={native} over={over} busy={busy} aws={aws} onPaths={onPaths} onChoose={onChoose} />
      <h2>Tables{tables.length > 0 && <span className="muted"> · {tables.length}</span>}</h2>
      {tables.length === 0 ? (
        <p className="muted">No tables yet. Drop a CSV, Parquet, Excel or JSON file above, or run <code>querysolo import &lt;file&gt;</code>.</p>
      ) : (
        <ul className="entries">
          {tables.map((t) => (
            <li key={t.name} data-testid={`table-${t.name}`}>
              <button type="button" className={`entry${open === t.name ? ' on' : ''}`} onClick={() => onOpen(t.name)} aria-current={open === t.name ? 'true' : undefined} title={`querysolo tables describe ${t.name}`}>
                <span className="name mono">{t.name}</span>
                <span className="facts">
                  <span className="rows">{t.kind === 'view' || t.needs_relocate ? '—' : `${t.rows.toLocaleString()} rows`}</span>
                  {t.needs_relocate ? <span className="failed" data-testid={`moved-${t.name}`}>needs relocate</span> : t.interrupted_replace_of ? <span className="failed">a replace of {t.interrupted_replace_of} was interrupted: querysolo tables rename</span> : <Where t={t} />}
                </span>
                <i className={`dot ${freshnessClass(t.freshness)}`} title={t.freshness ? `updated ${ago(t.freshness)}` : 'never written'} data-testid={`fresh-${t.name}`} />
              </button>
              {t.source && (
                <button type="button" className="quiet small" onClick={() => onRefresh(t.name)} disabled={!!busy} data-testid={`refresh-${t.name}`} title={`querysolo tables refresh ${t.name}`}>Refresh</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
