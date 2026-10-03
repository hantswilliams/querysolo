// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The preview before an import (app brief A9): the columns with their DuckDB and Iceberg
// types and any note about the coercion, the first rows, the table name, and the import
// button with the CLI line it stands for. A folder is one of these per file. A remote
// prefix (real-data brief R4) shows one footer's columns, the files and bytes it would
// register in place, and "Attach" with `querysolo tables attach` as its line.

import { humanBytes, type ImportMode, type Preview } from '../lib/api';
import { attachCommand, importCommand } from '../lib/command';
import { Command } from './Command';

export interface PreviewPanelProps {
  path: string;
  folder: boolean;
  previews: Preview[];
  name: string;
  mode: ImportMode;
  /** The table that already exists, when the core answered 409: replace or append. */
  exists?: string;
  busy?: string;
  error?: string;
  onName: (name: string) => void;
  onImport: (mode: ImportMode) => void;
  /** A remote prefix: register it in place under `name`. */
  onAttach?: () => void;
  onCancel: () => void;
}

const fileName = (p: string) => p.replace(/[\\/]+$/, '').split(/[\\/]/).pop() ?? p;

function Columns({ preview }: { preview: Preview }) {
  return (
    <div className="preview-file" data-testid={`preview-${preview.name}`}>
      {preview.remote && (
        <p className="muted" data-testid="remote-summary">
          {(preview.files ?? 0).toLocaleString()} Parquet {preview.files === 1 ? 'file' : 'files'}, {humanBytes(preview.bytes ?? 0)}, read in place{preview.anonymous ? ' without credentials' : ''}; nothing is copied. The columns are one file's; attach checks every file has the same.
        </p>
      )}
      <table className="columns">
        <thead><tr><th>Column</th><th>{preview.remote ? 'Arrow' : 'DuckDB'}</th><th>Iceberg</th><th>Note</th></tr></thead>
        <tbody>
          {preview.columns.map((c) => (
            <tr key={c.name}>
              <td className="mono">{c.name}</td>
              <td className="mono muted">{c.duckdb_type}</td>
              <td className="mono">{c.iceberg_type}</td>
              <td className="note">{c.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {preview.sample.length > 0 && (
        <table className="sample">
          <thead><tr>{preview.columns.map((c) => <th key={c.name}>{c.name}</th>)}</tr></thead>
          <tbody>
            {preview.sample.map((row, i) => (
              <tr key={i}>{row.map((v, j) => <td key={j} className="mono">{v === null ? '∅' : String(v)}</td>)}</tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function PreviewPanel({ path, folder, previews, name, mode, exists, busy, error, onName, onImport, onAttach, onCancel }: PreviewPanelProps) {
  const remote = previews[0]?.remote === true;
  const line = remote
    ? attachCommand(name.trim() || previews[0].name, path, previews[0].anonymous)
    : importCommand(path, mode, folder ? undefined : name);
  return (
    <section className="preview" data-testid="preview">
      <header>
        {folder ? (
          <h2>{fileName(path)}<span className="muted"> → {previews.length} {previews.length === 1 ? 'table' : 'tables'}</span></h2>
        ) : (
          <h2>
            {fileName(path)}<span className="muted"> → </span>
            <input type="text" value={name} onChange={(e) => onName(e.target.value)} aria-label="Table name" data-testid="table-name" className="mono" />
          </h2>
        )}
        <button type="button" className="quiet" onClick={onCancel} disabled={!!busy}>Cancel</button>
      </header>
      {previews.length === 0 && <p className="muted">Nothing to import here: no CSV, TSV, Parquet, JSON, JSONL or Excel file in this folder.</p>}
      {previews.map((p) => (
        <div key={p.source}>
          {folder && <h3 className="mono">{fileName(p.source)}<span className="muted"> → {p.name}</span></h3>}
          <Columns preview={p} />
        </div>
      ))}
      {error && <div className="error" data-testid="import-error"><pre>{error}</pre></div>}
      <footer>
        {remote ? (
          <button type="button" className="primary" onClick={onAttach} disabled={!!busy || !!exists} data-testid="attach">
            {busy ?? `Attach as ${name.trim() || previews[0].name}`}
          </button>
        ) : exists ? (
          <div className="exists" data-testid="exists">
            <span>Table <code>{exists}</code> already exists.</span>
            <button type="button" className="primary" onClick={() => onImport('replace')} disabled={!!busy} data-testid="replace">Replace it</button>
            <button type="button" className="primary" onClick={() => onImport('append')} disabled={!!busy} data-testid="append">Append to it</button>
          </div>
        ) : (
          <button type="button" className="primary" onClick={() => onImport('create')} disabled={!!busy || previews.length === 0} data-testid="import">
            {busy ?? (folder ? `Import ${previews.length} tables` : 'Import')}
          </button>
        )}
        <Command line={line} />
      </footer>
    </section>
  );
}
