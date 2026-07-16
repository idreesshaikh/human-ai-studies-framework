import * as vscode from 'vscode';
import { LikertItem } from '../core/surveys';

export interface LikertResult {
  value: number | null;
  msToAnswer: number;
  skipped: boolean;
  /** True when the prompt was programmatically cancelled (e.g. session end),
   *  as opposed to the participant skipping it. */
  cancelled: boolean;
}

export interface LikertPromptHandle {
  result: Promise<LikertResult>;
  /** Dismiss the prompt without participant input (records cancelled=true). */
  cancel(): void;
}

/**
 * A single-item Likert micro-survey, rendered as a QuickPick - VS Code's
 * native floating overlay (same translucent, centered panel as the command
 * palette). Keyboard-first: press 1–7 and Enter, or Esc to skip.
 */
export function showLikertQuickPick(item: LikertItem): LikertPromptHandle {
  let cancelFn: () => void = () => undefined;
  const result = new Promise<LikertResult>((resolve) => {
    const qp = vscode.window.createQuickPick();
    qp.title = item.question;
    qp.placeholder = `1 = ${item.lowLabel} · ${item.points} = ${item.highLabel} - type a number and press Enter (Esc to skip)`;
    qp.items = Array.from({ length: item.points }, (_, i) => {
      const v = i + 1;
      const hint = item.hints?.[v] ?? '';
      let label = `$(circle-large-outline) ${v}`;
      if (v === 1) label += `  -  ${item.lowLabel}`;
      if (v === item.points) label += `  -  ${item.highLabel}`;
      return { label, description: hint, alwaysShow: true };
    });
    qp.ignoreFocusOut = true;

    const shownAt = Date.now();
    let settled = false;
    const finish = (result: LikertResult) => {
      if (settled) return;
      settled = true;
      qp.hide();
      qp.dispose();
      resolve(result);
    };

    cancelFn = () =>
      finish({
        value: null,
        msToAnswer: Date.now() - shownAt,
        skipped: true,
        cancelled: true,
      });

    qp.onDidAccept(() => {
      const picked = qp.selectedItems[0];
      const match = picked?.label.match(/(\d+)/);
      finish({
        value: match ? parseInt(match[1], 10) : null,
        msToAnswer: Date.now() - shownAt,
        skipped: !match,
        cancelled: false,
      });
    });
    qp.onDidHide(() =>
      finish({
        value: null,
        msToAnswer: Date.now() - shownAt,
        skipped: true,
        cancelled: false,
      }),
    );
    qp.show();
  });
  return { result, cancel: () => cancelFn() };
}
