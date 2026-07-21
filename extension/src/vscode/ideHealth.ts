import * as vscode from 'vscode';
import {
  IdeHealthCollector,
  type IdeHealthConfig,
  type HealthEventSink,
} from '../core/ideHealth';

/** Adapter that wires VS Code's diagnostics API to the core IdeHealthCollector.
 *
 * Subscribes to onDidChangeDiagnostics to capture error/warning counts,
 * and provides a method for the task harness to signal build/test invocations.
 * Gated by the effective tern.ideHealth.enabled flag (checked at
 * session start, never mid-session — wall #6).
 */
export class VscodeIdeHealthAdapter implements vscode.Disposable {
  private _collector: IdeHealthCollector;
  private _diagListener: vscode.Disposable;
  private _disposables: vscode.Disposable[] = [];

  constructor(
    config: IdeHealthConfig,
    onFlush: HealthEventSink,
    clock: () => number = () => Date.now(),
  ) {
    this._collector = new IdeHealthCollector(config, onFlush, clock);
    this._diagListener = vscode.languages.onDidChangeDiagnostics(() => {
      const all = vscode.languages.getDiagnostics();
      let errors = 0;
      let warnings = 0;
      for (const [, diagnostics] of all) {
        for (const d of diagnostics) {
          if (d.severity === vscode.DiagnosticSeverity.Error) errors += 1;
          else if (d.severity === vscode.DiagnosticSeverity.Warning)
            warnings += 1;
        }
      }
      // Emit the *delta* since the last flush — the collector resets on flush.
      this._collector.recordDiagnostics(errors, warnings);
    });
    this._disposables.push(this._diagListener);
  }

  /** Signal a build invocation (called by the task harness or terminal watcher). */
  recordBuild(): void {
    this._collector.recordInvocation('build');
  }

  /** Signal a test invocation. */
  recordTest(): void {
    this._collector.recordInvocation('test');
  }

  /** Force-flush pending counts. */
  flush(): void {
    this._collector.flush();
  }

  /** Reset counters (e.g. on session start). */
  reset(): void {
    this._collector.reset();
  }

  dispose(): void {
    this._collector.dispose();
    for (const d of this._disposables) d.dispose();
    this._disposables = [];
  }
}
