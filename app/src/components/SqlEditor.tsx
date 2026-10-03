// Copyright 2026 QuerySolo contributors
// SPDX-License-Identifier: Apache-2.0
// The SQL box (app brief A3): CodeMirror 6 with the SQL language, table and column names
// for completion, Cmd/Ctrl+Enter to run, Escape to cancel (F0.8.6).

import { useEffect, useRef } from 'react';
import { EditorState, Compartment } from '@codemirror/state';
import { EditorView, keymap, lineNumbers, highlightActiveLine, placeholder } from '@codemirror/view';
import { defaultKeymap, history, historyKeymap, indentWithTab } from '@codemirror/commands';
import { syntaxHighlighting, HighlightStyle, bracketMatching } from '@codemirror/language';
import { tags } from '@lezer/highlight';
import { autocompletion, closeBrackets, completionKeymap } from '@codemirror/autocomplete';
import { sql, PostgreSQL } from '@codemirror/lang-sql';

/** The SQL's colours from the palette the app shares with the site (decisions U3), so the
 *  editor reads the same in light and dark rather than wearing CodeMirror's light default
 *  on a dark panel: keywords in the brand colour, strings Green, numbers amber, comments
 *  muted. The tokens are CSS variables, which a highlight style takes as any colour. */
const highlight = HighlightStyle.define([
  { tag: [tags.keyword, tags.operatorKeyword], color: 'var(--lake)', fontWeight: '600' },
  { tag: [tags.string, tags.special(tags.string)], color: 'var(--local)' },
  { tag: [tags.number, tags.bool, tags.null], color: 'var(--slow)' },
  { tag: [tags.comment, tags.lineComment, tags.blockComment], color: 'var(--muted)', fontStyle: 'italic' },
  { tag: [tags.typeName, tags.standard(tags.name)], color: 'var(--ink-soft)' },
]);

export interface SqlEditorProps {
  value: string;
  onChange: (sql: string) => void;
  onRun: () => void;
  onCancel: () => void;
  /** Table name to column names, for completion. */
  schema: Record<string, string[]>;
  autoFocus?: boolean;
}

export function SqlEditor({ value, onChange, onRun, onCancel, schema, autoFocus }: SqlEditorProps) {
  const host = useRef<HTMLDivElement>(null);
  const view = useRef<EditorView | undefined>(undefined);
  const language = useRef(new Compartment());
  const handlers = useRef({ onChange, onRun, onCancel });
  handlers.current = { onChange, onRun, onCancel };

  useEffect(() => {
    if (!host.current) return;
    const state = EditorState.create({
      doc: value,
      extensions: [
        lineNumbers(),
        history(),
        highlightActiveLine(),
        bracketMatching(),
        closeBrackets(),
        autocompletion(),
        syntaxHighlighting(highlight),
        language.current.of(sql({ dialect: PostgreSQL, schema, upperCaseKeywords: false })),
        placeholder('select … from …   (⌘/Ctrl+Enter runs, Esc cancels)'),
        keymap.of([
          ...completionKeymap, // first, so Escape closes an open completion before it means cancel
          { key: 'Mod-Enter', run: () => { handlers.current.onRun(); return true; } },
          { key: 'Escape', run: () => { handlers.current.onCancel(); return true; } },
          ...defaultKeymap,
          ...historyKeymap,
          indentWithTab,
        ]),
        EditorView.updateListener.of((u) => { if (u.docChanged) handlers.current.onChange(u.state.doc.toString()); }),
        EditorView.theme({
          '&': { fontSize: '13.5px', fontFamily: 'var(--mono)' },
          '.cm-content': { fontFamily: 'var(--mono)', minHeight: '96px', padding: '8px 0' },
          '.cm-line': { padding: '0 8px' },
          '.cm-gutter.cm-lineNumbers .cm-gutterElement': { padding: '0 6px 0 10px' },
          '.cm-gutters': { background: 'var(--bg)', color: 'var(--muted)', border: 'none' },
          '.cm-activeLine': { backgroundColor: 'var(--head)' },
          '.cm-activeLineGutter': { backgroundColor: 'var(--head)' },
          '.cm-cursor': { borderLeftColor: 'var(--ink)' },
          '&.cm-focused .cm-selectionBackground, .cm-selectionBackground, ::selection': { backgroundColor: 'var(--cloud)' },
          '.cm-tooltip': { background: 'var(--panel)', border: '1px solid var(--line)', color: 'var(--ink)' },
          '.cm-tooltip-autocomplete ul li[aria-selected]': { background: 'var(--cloud)', color: 'var(--ink)' },
          '&.cm-focused': { outline: 'none' },
        }),
      ],
    });
    const v = new EditorView({ state, parent: host.current });
    view.current = v;
    // not when something else has the keyboard already (a path being typed into the
    // explorer while this chunk arrived): the editor loads lazily and must not steal it
    const active = document.activeElement;
    if (autoFocus && (!active || active === document.body)) v.focus();
    return () => { v.destroy(); view.current = undefined; };
  }, []); // created once; the schema and the value are pushed in below

  useEffect(() => {
    view.current?.dispatch({ effects: language.current.reconfigure(sql({ dialect: PostgreSQL, schema, upperCaseKeywords: false })) });
  }, [schema]);

  useEffect(() => {
    const v = view.current;
    if (v && v.state.doc.toString() !== value) {
      v.dispatch({ changes: { from: 0, to: v.state.doc.length, insert: value } });
    }
  }, [value]);

  return <div className="sql-editor" ref={host} data-testid="sql-editor" />;
}
