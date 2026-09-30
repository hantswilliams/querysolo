// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// Save as question (versions brief G7): the button under the query, and the one-line box it
// opens. The title is the only thing asked; the slug comes from it the way the CLI derives
// it. A title already saved is a 409 from the core and becomes "Replace it", the way an
// import onto an existing table does. The notice says the two checks the save wrote and the
// version it recorded, with the CLI line beside it.

import { useState } from 'react';
import { Api, ApiError, type Question } from '../lib/api';
import { questionSaveCommand, questionSlug } from '../lib/command';
import { words, type Mode } from '../lib/vocabulary';
import { Command } from './Command';

const message = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** What the save wrote, in the words the core's two default checks are: `returns_rows` on
 *  the model and `not_null` on its first column (D30). The first column is the query's, so
 *  the app reads it from the columns already on the screen. */
export function checksSentence(firstColumn: string | undefined): string {
  const second = firstColumn ? `\`${firstColumn}\` is never empty` : 'its first column is never empty';
  return `returns at least one row; ${second}`;
}

export interface SaveQuestionProps {
  api: Api;
  sql: string;
  mode: Mode;
  /** The first column of the result on the screen, for the sentence about the checks. */
  firstColumn?: string;
  /** The gauge said Red and it was run anyway, or not run: saving is still allowed (G7). */
  red?: boolean;
  onSaved?: () => void;
}

export function SaveQuestion({ api, sql, mode, firstColumn, red, onSaved }: SaveQuestionProps) {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [busy, setBusy] = useState(false);
  const [exists, setExists] = useState<string>();
  const [error, setError] = useState<string>();
  const [saved, setSaved] = useState<Question>();

  const label = mode === 'simple' ? 'Save this question' : 'Save as question';

  async function save(replace: boolean) {
    setBusy(true);
    setError(undefined);
    try {
      const question = await api.saveQuestion(title.trim(), sql, replace);
      setSaved(question);
      setOpen(false);
      setExists(undefined);
      setTitle('');
      onSaved?.();
    } catch (e: unknown) {
      if (e instanceof ApiError && e.code === 'question_exists') setExists(questionSlug(title.trim()));
      else setError(e instanceof ApiError ? `${e.code}: ${e.message}` : message(e));
    } finally {
      setBusy(false);
    }
  }

  if (saved) {
    return (
      <div className="notice" data-testid="saved-question">
        <p>
          Saved <strong>{saved.title}</strong> as <code>{saved.path.split(/[\\/]/).pop()}</code>,
          a {words(mode).model} with two {words(mode).tests}: {checksSentence(firstColumn)}.
        </p>
        {saved.commit && <p className="muted" data-testid="saved-version">Version {saved.commit.slice(0, 7)}.</p>}
        {saved.git && <p className="muted" data-testid="saved-git">git: {saved.git}; the files are saved, this save is not a version.</p>}
        <Command line={questionSaveCommand(saved.title, saved.sql)} />
        <button type="button" className="quiet" onClick={() => setSaved(undefined)} data-testid="saved-close">Close</button>
      </div>
    );
  }

  if (!open) {
    return (
      <button type="button" className="quiet" onClick={() => setOpen(true)} disabled={!sql.trim()} data-testid="save-question">
        {label}
      </button>
    );
  }

  return (
    <div className="save-question" data-testid="save-question-box">
      <label htmlFor="question-title">Give it a title</label>
      <input
        id="question-title"
        value={title}
        autoFocus
        placeholder="Revenue by customer"
        onChange={(e) => { setTitle(e.target.value); setExists(undefined); }}
        onKeyDown={(e) => { if (e.key === 'Enter' && title.trim() && !exists) void save(false); if (e.key === 'Escape') setOpen(false); }}
        data-testid="question-title"
      />
      {title.trim() && <p className="muted">It will be <code>models/questions/{questionSlug(title.trim())}.sql</code>, with two {words(mode).tests}: {checksSentence(firstColumn)}.</p>}
      {red && <p className="muted" data-testid="save-question-red">This one needs more machine than you have here. Saving it is fine: a question can be bigger than this laptop.</p>}
      {exists && (
        <p className="muted" data-testid="question-exists">
          A {words(mode).model} called <code>{exists}</code> is already saved.
        </p>
      )}
      {error && <div className="error" data-testid="save-question-error"><pre>{error}</pre></div>}
      <div className="row">
        {exists ? (
          <button type="button" className="primary" onClick={() => void save(true)} disabled={busy} data-testid="question-replace">Replace it</button>
        ) : (
          <button type="button" className="primary" onClick={() => void save(false)} disabled={busy || !title.trim()} data-testid="question-save">Save</button>
        )}
        <button type="button" className="quiet" onClick={() => { setOpen(false); setExists(undefined); setError(undefined); }} data-testid="question-cancel">Cancel</button>
      </div>
      {title.trim() && <Command line={questionSaveCommand(title.trim(), sql)} />}
    </div>
  );
}
