import * as vscode from 'vscode';

/**
 * The only permanently visible UI: a small countdown in the status bar.
 * Clicking it opens the session menu (log fatigue now / end session).
 */
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
    const totalSec = Math.round(remainingMs / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    this.item.text = `$(pulse) ${m}:${s.toString().padStart(2, '0')}`;
    this.item.tooltip =
      'Study session running - click for options (log fatigue, end session)';
  }

  /** Session running but paused: freeze the countdown and flag it. */
  paused(remainingMs: number): void {
    const totalSec = Math.round(remainingMs / 1000);
    const m = Math.floor(totalSec / 60);
    const s = totalSec % 60;
    this.item.text = `$(debug-pause) ${m}:${s.toString().padStart(2, '0')} paused`;
    this.item.tooltip =
      'Study session paused - click for options (resume, end session)';
    this.item.backgroundColor = undefined;
  }

  /** Brief highlight used to softly announce a due fatigue prompt. */
  attention(on: boolean): void {
    this.item.backgroundColor = on
      ? new vscode.ThemeColor('statusBarItem.warningBackground')
      : undefined;
  }

  dispose(): void {
    this.item.dispose();
  }
}
