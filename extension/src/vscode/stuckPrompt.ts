import * as vscode from 'vscode';
import { StuckAnswer, StuckRegion } from '../core/types';

export interface StuckResolution {
  answer: StuckAnswer;
  msToAnswer: number;
  region: StuckRegion;
}

interface ActivePrompt {
  id: number;
  uri: vscode.Uri;
  range: vscode.Range;
  region: StuckRegion;
  shownAt: number;
  timeout: ReturnType<typeof setTimeout>;
}

const AUTO_DISMISS_MS = 60_000;

/**
 * The inline "overlay on the code": a soft rectangular border drawn around
 * the region the participant appears stuck on, with clickable CodeLens
 * actions rendered directly above it. No modal, no focus steal - the
 * participant can keep typing and the prompt quietly times out if ignored.
 */
export class StuckPromptController
  implements vscode.CodeLensProvider, vscode.Disposable
{
  private readonly changeEmitter = new vscode.EventEmitter<void>();
  readonly onDidChangeCodeLenses = this.changeEmitter.event;

  private readonly decoration = vscode.window.createTextEditorDecorationType({
    isWholeLine: true,
    border: '1px solid',
    borderColor: new vscode.ThemeColor('editorInfo.foreground'),
    borderRadius: '4px',
    backgroundColor: 'rgba(120, 170, 255, 0.06)',
    overviewRulerColor: new vscode.ThemeColor('editorInfo.foreground'),
    overviewRulerLane: vscode.OverviewRulerLane.Right,
  });

  private active?: ActivePrompt;
  private nextId = 1;
  private readonly disposables: vscode.Disposable[] = [];

  constructor(private readonly onResolved: (r: StuckResolution) => void) {
    this.disposables.push(
      vscode.languages.registerCodeLensProvider({ scheme: 'file' }, this),
      // Re-paint the border when the participant switches editors.
      vscode.window.onDidChangeVisibleTextEditors(() => this.paint()),
    );
  }

  get hasActivePrompt(): boolean {
    return this.active !== undefined;
  }

  show(region: StuckRegion): void {
    // One prompt at a time; a new detection while one is visible is dropped.
    if (this.active) return;

    const uri = vscode.Uri.file(region.file);
    const doc = vscode.workspace.textDocuments.find(
      (d) => d.uri.fsPath === uri.fsPath,
    );
    const lastLine = doc ? doc.lineCount - 1 : region.endLine;
    const start = Math.min(region.startLine, lastLine);
    const end = Math.min(region.endLine, lastLine);

    this.active = {
      id: this.nextId++,
      uri,
      range: new vscode.Range(start, 0, end, Number.MAX_SAFE_INTEGER),
      region,
      shownAt: Date.now(),
      timeout: setTimeout(() => this.resolve('timeout'), AUTO_DISMISS_MS),
    };
    this.paint();
    this.changeEmitter.fire();
  }

  resolve(answer: StuckAnswer): void {
    const p = this.active;
    if (!p) return;
    clearTimeout(p.timeout);
    this.active = undefined;
    this.paint();
    this.changeEmitter.fire();
    this.onResolved({
      answer,
      msToAnswer: Date.now() - p.shownAt,
      region: p.region,
    });
  }

  provideCodeLenses(document: vscode.TextDocument): vscode.CodeLens[] {
    const p = this.active;
    if (!p || document.uri.fsPath !== p.uri.fsPath) return [];
    const anchor = new vscode.Range(
      p.range.start.line,
      0,
      p.range.start.line,
      0,
    );
    const lens = (title: string, answer?: StuckAnswer): vscode.CodeLens =>
      new vscode.CodeLens(anchor, {
        title,
        command: answer ? 'tern.respondStuck' : '',
        arguments: answer ? [answer] : undefined,
      });
    return [
      lens('$(pulse) You seem to be lingering here - stuck?'),
      lens('Yes, I’m stuck', 'yes'),
      lens('No, just thinking', 'no'),
      lens('$(lightbulb) I’d like a hint', 'hint'),
      lens('$(close) Dismiss', 'dismissed'),
    ];
  }

  private paint(): void {
    for (const editor of vscode.window.visibleTextEditors) {
      const ranges =
        this.active && editor.document.uri.fsPath === this.active.uri.fsPath
          ? [this.active.range]
          : [];
      editor.setDecorations(this.decoration, ranges);
    }
  }

  dispose(): void {
    if (this.active) clearTimeout(this.active.timeout);
    this.active = undefined;
    this.decoration.dispose();
    this.changeEmitter.dispose();
    for (const d of this.disposables) d.dispose();
  }
}
