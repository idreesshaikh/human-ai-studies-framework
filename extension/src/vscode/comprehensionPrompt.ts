import * as vscode from 'vscode';
import {
  ChunkMeta,
  ChunkReference,
  ProbeDescriptor,
  ProbeResponse,
} from '../core/comprehensionProbe';

interface ActivePrompt {
  meta: ChunkMeta;
  descriptor: ProbeDescriptor;
  chunkRef: ChunkReference;
  uri: vscode.Uri;
  range: vscode.Range;
  shownAt: number;
  timeout: ReturnType<typeof setTimeout>;
}

const DEFAULT_TIMEOUT_MS = 30_000;

export class ComprehensionPromptController
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
  private readonly disposables: vscode.Disposable[] = [];

  constructor(private readonly onResponse: (response: ProbeResponse) => void) {
    this.disposables.push(
      vscode.languages.registerCodeLensProvider({ scheme: 'file' }, this),
      vscode.window.onDidChangeVisibleTextEditors(() => this.paint()),
    );
  }

  show(
    meta: ChunkMeta,
    descriptor: ProbeDescriptor,
    chunkRef: ChunkReference,
  ): void {
    if (this.active) return;

    const uri = vscode.Uri.file(meta.file);
    const editors = vscode.window.visibleTextEditors.filter(
      (e) => e.document.uri.fsPath === uri.fsPath,
    );
    if (editors.length === 0) return;

    const doc = editors[0].document;
    const lastLine = doc.lineCount - 1;
    const start = Math.min(0, lastLine);
    const end = Math.min(meta.linesTouched - 1, lastLine);

    const timebox =
      descriptor.timeboxMs > 0 ? descriptor.timeboxMs : DEFAULT_TIMEOUT_MS;

    this.active = {
      meta,
      descriptor,
      chunkRef,
      uri,
      range: new vscode.Range(start, 0, end, Number.MAX_SAFE_INTEGER),
      shownAt: Date.now(),
      timeout: setTimeout(() => this.expire(), timebox),
    };
    this.paint();
    this.changeEmitter.fire();
  }

  private expire(): void {
    const p = this.active;
    if (!p) return;
    const msToAnswer = Date.now() - p.shownAt;
    this.active = undefined;
    this.paint();
    this.changeEmitter.fire();
    this.onResponse({
      chunkRef: p.chunkRef,
      promptKind: p.descriptor.promptKind,
      msToAnswer,
      expired: true,
    });
  }

  resolveAnswer(answer: string): void {
    const p = this.active;
    if (!p) return;
    clearTimeout(p.timeout);
    const msToAnswer = Date.now() - p.shownAt;
    this.active = undefined;
    this.paint();
    this.changeEmitter.fire();
    this.onResponse({
      chunkRef: p.chunkRef,
      promptKind: p.descriptor.promptKind,
      answer,
      msToAnswer,
      expired: false,
    });
  }

  cancel(): void {
    const p = this.active;
    if (!p) return;
    clearTimeout(p.timeout);
    this.active = undefined;
    this.paint();
    this.changeEmitter.fire();
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
    const lens = (
      title: string,
      command?: string,
      args?: unknown[],
    ): vscode.CodeLens =>
      new vscode.CodeLens(anchor, {
        title,
        command: command ?? '',
        arguments: args,
      });

    if (p.descriptor.promptKind === 'predict-output') {
      return [
        lens('$(question) What will this code print or return?'),
        lens('$(check) Answer: choose...', 'tern.answerProbe', [
          'predict-output',
        ]),
        lens('$(close) Skip', 'tern.skipProbe'),
      ];
    }

    return [
      lens('$(question) Which line changed the behavior?'),
      lens('$(check) Answer: choose...', 'tern.answerProbe', ['locate-change']),
      lens('$(close) Skip', 'tern.skipProbe'),
    ];
  }

  private paint(): void {
    const p = this.active;
    for (const editor of vscode.window.visibleTextEditors) {
      editor.setDecorations(
        this.decoration,
        p && editor.document.uri.fsPath === p.uri.fsPath ? [p.range] : [],
      );
    }
  }

  dispose(): void {
    this.cancel();
    this.decoration.dispose();
    for (const d of this.disposables) d.dispose();
  }
}
