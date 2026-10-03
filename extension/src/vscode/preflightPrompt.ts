import * as vscode from 'vscode';

export interface PreflightPromptOptions {
  participantId: string;
  durationMinutes: number;
  capture: string[];
  notCaptured: string[];
}

export function confirmPreflight(
  options: PreflightPromptOptions,
): Promise<boolean> {
  return new Promise((resolve) => {
    const quickPick = vscode.window.createQuickPick<PreflightAction>();
    quickPick.title = 'Begin study session';
    quickPick.placeholder =
      'Review the capture scope · Enter to choose · Esc to cancel';
    quickPick.ignoreFocusOut = true;
    quickPick.items = [
      {
        label: '$(play)  Begin session',
        description: `${options.participantId} · ${options.durationMinutes} min`,
        detail: [
          'Captured during this session',
          ...(options.capture.length > 0
            ? options.capture.map((label) => `  • ${label}`)
            : ['  • Nothing is enabled']),
          '',
          'Not captured',
          ...(options.notCaptured.length > 0
            ? options.notCaptured.map((label) => `  • ${label}`)
            : ['  • Nothing outside the selected capture scope']),
        ].join('\n'),
        action: 'begin',
        alwaysShow: true,
      },
      {
        label: '$(close)  Cancel',
        description: 'Return without starting the session',
        action: 'cancel',
        alwaysShow: true,
      },
    ];

    let settled = false;
    const finish = (accepted: boolean) => {
      if (settled) return;
      settled = true;
      quickPick.hide();
      quickPick.dispose();
      resolve(accepted);
    };

    quickPick.onDidAccept(() => {
      finish(quickPick.selectedItems[0]?.action === 'begin');
    });
    quickPick.onDidHide(() => finish(false));
    quickPick.show();
  });
}

interface PreflightAction extends vscode.QuickPickItem {
  action: 'begin' | 'cancel';
}
