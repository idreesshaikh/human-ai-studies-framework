import * as vscode from 'vscode';
import { StuckDetector } from '../core/stuckDetector';
import { EditorSignal } from '../core/types';

/**
 * Maps native VS Code editor events onto the core's normalized EditorSignal
 * stream. This file is the entire "sensor" surface of the adapter - the
 * JetBrains port re-implements exactly this mapping and nothing else.
 *
 * Every signal is fed to the stuck detector AND to an optional `tap`, which
 * the extension uses to record attention events (focus/blur) and to measure
 * resumption lag after prompts. The heavy behavioral telemetry (per-edit
 * logging, tab switches, clipboard) is deliberately NOT recorded here - that
 * is the behavior-capture leg's job; duplicating it would bloat this dataset.
 */
export function wireEditorSignals(
  detector: StuckDetector,
  languages: string[],
  tap?: (signal: EditorSignal) => void,
): vscode.Disposable {
  const watched = (doc: vscode.TextDocument): boolean => {
    if (doc.uri.scheme !== 'file') return false;
    return languages.length === 0 || languages.includes(doc.languageId);
  };

  const emit = (signal: EditorSignal): void => {
    detector.signal(signal);
    tap?.(signal);
  };

  const subs: vscode.Disposable[] = [
    vscode.window.onDidChangeTextEditorSelection((e) => {
      if (!watched(e.textEditor.document)) return;
      emit({
        kind: 'selection',
        file: e.textEditor.document.uri.fsPath,
        line: e.selections[0]?.active.line ?? 0,
        at: Date.now(),
      });
    }),

    vscode.window.onDidChangeTextEditorVisibleRanges((e) => {
      if (!watched(e.textEditor.document)) return;
      const r = e.visibleRanges[0];
      if (!r) return;
      emit({
        kind: 'scroll',
        file: e.textEditor.document.uri.fsPath,
        line: Math.round((r.start.line + r.end.line) / 2),
        topLine: r.start.line,
        bottomLine: r.end.line,
        at: Date.now(),
      });
    }),

    vscode.workspace.onDidChangeTextDocument((e) => {
      if (!watched(e.document) || e.contentChanges.length === 0) return;
      emit({
        kind: 'edit',
        file: e.document.uri.fsPath,
        at: Date.now(),
      });
    }),

    vscode.window.onDidChangeWindowState((e) => {
      emit({ kind: e.focused ? 'focus' : 'blur', at: Date.now() });
    }),
  ];

  return vscode.Disposable.from(...subs);
}
