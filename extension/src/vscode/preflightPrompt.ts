import * as vscode from 'vscode';

export interface PreflightPromptOptions {
  participantId: string;
  condition: string;
  durationMinutes: number;
  capture: string[];
  notCaptured: string[];
}

/**
 * Show the capture-consent gate as a QuickPick rather than a modal message.
 *
 * VS Code adds its own dismissal affordance to modal message dialogs. Mixing
 * that affordance with an explicit Cancel item is easy to get wrong and can
 * render duplicate Cancel buttons in older hosts. A QuickPick gives the
 * participant exactly two visible actions: begin or cancel (Esc also cancels)
 * while keeping the capture scope readable and keyboard accessible.
 */
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
        description: `${options.participantId} · ${options.condition} · ${options.durationMinutes} min`,
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
