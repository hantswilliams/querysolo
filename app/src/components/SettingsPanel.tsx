// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Settings (app brief, session 6 scope): only what the core reads from querysolo.toml, the
// engine's memory limit and threads, plus the calibration-sharing toggle with nothing behind
// it yet. Each save is `querysolo config set`, shown beside it. The engine reads these at
// start; the app gives each window its own memory share regardless (A8). The Bucket row
// (decisions C1) is the shell's, not the file's: the AWS profile this project's bucket is
// reached with, on this machine — a name, never a key.

import { useEffect, useState } from 'react';
import { Api, type SettingKey, type Settings } from '../lib/api';
import { configCommand } from '../lib/command';
import { Command } from './Command';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

const FIELDS: Array<{ key: SettingKey; label: string; help: string; kind: 'text' | 'bool' }> = [
  { key: 'engine.memory_limit', label: 'Memory limit for the CLI', help: '"auto" (DuckDB\'s 80% of RAM) or a size such as 8GB. Each app window gets its own share of RAM instead.', kind: 'text' },
  { key: 'engine.threads', label: 'Threads', help: '"auto" or a count.', kind: 'text' },
  { key: 'gauge.share_calibration', label: 'Share calibration', help: 'Whether this project would contribute anonymous gauge calibration. Nothing is sent yet; the switch is here so the file is ready.', kind: 'bool' },
  { key: 'catalog.keep_snapshots_days', label: 'Keep snapshots for', help: 'Days of table history `querysolo tables expire` keeps; the current snapshot always stays. Expiry runs only when asked.', kind: 'text' },
  { key: 'git.auto_commit', label: 'Record a version on every save and run', help: 'Off means a run records no version. Saving a question is always a version, whatever this says.', kind: 'bool' },
];

/** The Bucket row (C1), inside the app only: the profiles on this machine, the project's, and
 *  the change, after which the shell starts the core again with it. */
export interface BucketSetting {
  profiles: string[];
  profile: string | null;
  onProfile: (profile: string | null) => Promise<void>;
}

/** The About row (ship brief S8), inside the app only: the version and the sidecar's origin. */
export interface AboutInfo {
  version: string;
  sidecar: string;
  sidecar_source: 'bundled' | 'environment' | 'path';
}

const SOURCE_WORDS: Record<AboutInfo['sidecar_source'], string> = {
  bundled: 'the core that came with the app',
  environment: 'the core named by QUERYSOLO_SIDECAR (development)',
  path: 'the querysolo on your PATH',
};

export function SettingsPanel({ api, bucket, about, onClose }: { api: Api; bucket?: BucketSetting; about?: AboutInfo | null; onClose: () => void }) {
  const [settings, setSettings] = useState<Settings>();
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState<string>();
  const [changing, setChanging] = useState(false);

  useEffect(() => {
    api.settings().then((s) => {
      setSettings(s);
      // what the file says seeds the boxes; a value typed before the answer arrived stays
      setDrafts((d) => ({ ...Object.fromEntries(Object.entries(s.settings).map(([k, v]) => [k, String(v)])), ...d }));
    }).catch((e: unknown) => setError(message(e)));
  }, [api]);

  async function save(key: SettingKey, value: string) {
    setError(undefined);
    setSaved(undefined);
    try {
      const s = await api.setSetting(key, value);
      setSettings(s);
      setDrafts((d) => ({ ...d, [key]: String(s.settings[key]) }));
      setSaved(key);
    } catch (e: unknown) {
      setError(message(e));
    }
  }

  return (
    <section className="settings" data-testid="settings" role="dialog" aria-label="Settings">
      <header>
        <h2>Settings</h2>
        <button type="button" className="quiet" onClick={onClose} data-testid="settings-close">Close (Esc)</button>
      </header>
      {settings && <p className="muted">These are in <code>{settings.path}</code>; the core reads them when it starts.</p>}
      {error && <div className="error" data-testid="settings-error"><pre>{error}</pre></div>}
      {settings && FIELDS.map((f) => {
        const draft = drafts[f.key] ?? '';
        const current = String(settings.settings[f.key]);
        return (
          <div className="setting" key={f.key} data-testid={`setting-${f.key}`}>
            <label>
              <b>{f.label}</b>
              <span className="muted">{f.help}</span>
            </label>
            <div className="control">
              {f.kind === 'bool' ? (
                <input
                  type="checkbox"
                  checked={draft === 'true'}
                  onChange={(e) => { const v = e.target.checked ? 'true' : 'false'; setDrafts((d) => ({ ...d, [f.key]: v })); void save(f.key, v); }}
                  aria-label={f.label}
                  data-testid={`input-${f.key}`}
                />
              ) : (
                <>
                  <input
                    type="text"
                    value={draft}
                    onChange={(e) => setDrafts((d) => ({ ...d, [f.key]: e.target.value }))}
                    onKeyDown={(e) => { if (e.key === 'Enter') void save(f.key, draft); }}
                    aria-label={f.label}
                    className="mono"
                    data-testid={`input-${f.key}`}
                  />
                  <button type="button" className="quiet" onClick={() => void save(f.key, draft)} disabled={draft.trim() === current} data-testid={`save-${f.key}`}>
                    {saved === f.key ? 'saved' : 'Save'}
                  </button>
                </>
              )}
              <Command line={configCommand(f.key, draft.trim() || current)} />
            </div>
          </div>
        );
      })}
      {bucket && (
        <div className="setting" data-testid="setting-bucket">
          <label>
            <b>Bucket</b>
            <span className="muted">The AWS profile this project's bucket is reached with, on this machine. The keys stay in AWS's own files; changing it starts the core again. In a terminal it is <code>querysolo --profile {bucket.profile ?? '<name>'} …</code>, or <code>AWS_PROFILE</code>.</span>
          </label>
          <div className="control">
            <select
              value={bucket.profile ?? ''}
              aria-label="Bucket profile"
              data-testid="input-bucket-profile"
              disabled={changing}
              onChange={(e) => {
                const v = e.target.value || null;
                setError(undefined);
                setChanging(true);
                bucket.onProfile(v).catch((err: unknown) => setError(message(err))).finally(() => setChanging(false));
              }}
            >
              <option value="">the AWS default</option>
              {bucket.profiles.filter((p) => p !== 'default').map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            {changing && <span className="muted">starting the core again…</span>}
          </div>
        </div>
      )}
      {about && (
        <div className="setting" data-testid="setting-about">
          <label>
            <b>About</b>
            <span className="muted">QuerySolo {about.version}. Every button here is a <code>querysolo</code> line; the app runs {SOURCE_WORDS[about.sidecar_source]}.</span>
          </label>
          <div className="control about">
            <code className="mono" data-testid="about-sidecar" title={about.sidecar}>{about.sidecar}</code>
            <a href="https://github.com/hantswilliams/querysolo/releases" target="_blank" rel="noreferrer">Releases ↗</a>
          </div>
        </div>
      )}
      <div className="keys">
        <h3>Keys</h3>
        <dl>
          <dt>⌘/Ctrl+Enter</dt><dd>run the SQL</dd>
          <dt>Esc</dt><dd>stop a running query; close this panel</dd>
          <dt>⌘/Ctrl+K</dt><dd>to the SQL box (the ask box, in a later session)</dd>
          <dt>⌘/Ctrl+,</dt><dd>settings</dd>
          <dt>⌘/Ctrl+1 … 5</dt><dd>Tables, Models, Lineage, Changes, Gauge</dd>
          <dt>⌘/Ctrl+N</dt><dd>New project…</dd>
        </dl>
      </div>
    </section>
  );
}
