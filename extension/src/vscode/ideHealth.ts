import * as vscode from 'vscode';
import {
  IdeHealthCollector,
  type IdeHealthConfig,
  type HealthEventSink,
} from '../core/ideHealth';

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

      this._collector.recordDiagnostics(errors, warnings);
    });
    this._disposables.push(this._diagListener);
  }

  recordBuild(): void {
    this._collector.recordInvocation('build');
  }

  recordTest(): void {
    this._collector.recordInvocation('test');
  }

  flush(): void {
    this._collector.flush();
  }

  reset(): void {
    this._collector.reset();
  }

  dispose(): void {
    this._collector.dispose();
    for (const d of this._disposables) d.dispose();
    this._disposables = [];
  }
}
