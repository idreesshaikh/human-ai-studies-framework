import * as vscode from 'vscode';
import { formatRemaining } from '../core/clock';

export class SessionStatusBar implements vscode.Disposable {
  private readonly item: vscode.StatusBarItem;

  constructor() {
    this.item = vscode.window.createStatusBarItem(
      vscode.StatusBarAlignment.Right,
      1000,
    );
    this.item.command = 'tern.statusMenu';
    this.idle();
    this.item.show();
  }

  idle(): void {
    this.item.text = '$(beaker) Study: idle';
    this.item.tooltip = 'TERN - click to start a study session';
    this.item.backgroundColor = undefined;
  }

  tick(remainingMs: number): void {
    this.item.text = `$(pulse) ${formatRemaining(remainingMs)}`;
    this.item.tooltip =
      'Study session running - click for options (log fatigue, end session)';
  }

  paused(remainingMs: number): void {
    this.item.text = `$(debug-pause) ${formatRemaining(remainingMs)} paused`;
    this.item.tooltip =
      'Study session paused - click for options (resume, end session)';
    this.item.backgroundColor = undefined;
  }

  debrief(): void {
    this.item.text = '$(comment-discussion) Study: debrief';
    this.item.tooltip =
      'Study debrief open - complete it to finish the session';
    this.item.backgroundColor = undefined;
  }

  attention(on: boolean): void {
    this.item.backgroundColor = on
      ? new vscode.ThemeColor('statusBarItem.warningBackground')
      : undefined;
  }

  dispose(): void {
    this.item.dispose();
  }
}
