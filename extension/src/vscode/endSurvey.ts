import * as vscode from 'vscode';
import { endSurveyItems, LikertItem } from '../core/surveys';

export interface EndSurveyResult {
  responses: Record<string, number>;
  comments: string;
  msToComplete: number;
}

/**
 * End-of-study questionnaire using the editor's colors and native controls.
 */
export function showEndSurvey(
  condition: string,
): Promise<EndSurveyResult | undefined> {
  const items = endSurveyItems(condition);

  const panel = vscode.window.createWebviewPanel(
    'tern.endSurvey',
    'Study Debrief',
    vscode.ViewColumn.Active,
    { enableScripts: true, retainContextWhenHidden: true },
  );
  const nonce = Math.random().toString(36).slice(2);
  panel.webview.html = renderHtml(items, nonce);

  const shownAt = Date.now();
  return new Promise((resolve) => {
    let settled = false;
    panel.webview.onDidReceiveMessage((msg) => {
      if (msg?.kind !== 'submit' || settled) return;
      settled = true;
      resolve({
        responses: msg.responses as Record<string, number>,
        comments: String(msg.comments ?? ''),
        msToComplete: Date.now() - shownAt,
      });
      panel.dispose();
    });
    panel.onDidDispose(() => {
      if (!settled) {
        settled = true;
        resolve(undefined);
      }
    });
  });
}

function renderHtml(items: LikertItem[], nonce: string): string {
  const rows = items
    .map(
      (item) => `
      <fieldset class="q" data-id="${item.id}">
        <legend>${escapeHtml(item.question)}</legend>
        <div class="scale" aria-describedby="${item.id}-scale">
          ${Array.from({ length: item.points }, (_, i) => {
            const v = i + 1;
            return `<label><input type="radio" name="${item.id}" value="${v}" aria-describedby="${item.id}-scale"><span>${v}</span></label>`;
          }).join('')}
        </div>
        <p class="scale-labels" id="${item.id}-scale"><span>1 — ${escapeHtml(item.lowLabel)}</span><span>${item.points} — ${escapeHtml(item.highLabel)}</span></p>
      </fieldset>`,
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Study debrief</title>
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<style>
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body {
    margin: 0; padding: 32px 16px 64px;
    display: flex; justify-content: center;
    font-family: var(--vscode-font-family);
    color: var(--vscode-foreground);
    background: var(--vscode-editor-background);
  }
  .card {
    width: min(680px, 100%);
    padding: 28px 32px;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 14%, transparent);
    background: var(--vscode-editor-background);
  }
  h1 { font-size: 1.25em; font-weight: 600; margin: 0 0 4px; }
  p.sub { margin: 0 0 24px; color: var(--vscode-descriptionForeground); line-height: 1.5; }
  fieldset.q {
    border: none; margin: 0 0 20px; padding: 14px 16px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--vscode-foreground) 4%, transparent);
  }
  legend { font-weight: 500; padding: 0 4px; }
  .scale { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
  .scale-labels { display: flex; flex-wrap: wrap; justify-content: space-between; gap: 6px 16px; margin: 8px 0 0; font-size: 0.9em; color: var(--vscode-descriptionForeground); }
  .scale label { position: relative; cursor: pointer; }
  .scale input { position: absolute; opacity: 0; inset: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }
  .scale label span {
    display: flex; align-items: center; justify-content: center;
    width: 44px; height: 44px; border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 25%, transparent);
    font-size: 1em;
  }
  .scale label:hover span { border-color: var(--vscode-button-background); }
  .scale input:checked + span {
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
    border-color: transparent;
  }
  .scale input:focus-visible + span, textarea:focus-visible, button:focus-visible {
    outline: 2px solid var(--vscode-focusBorder); outline-offset: 3px;
  }
  @media (forced-colors: active) {
    .scale input:checked + span { border: 3px solid Highlight; font-weight: bold; }
    .scale input:focus-visible + span, textarea:focus-visible, button:focus-visible { outline-color: Highlight; }
  }
  @media (max-width: 480px) {
    body { padding: 16px 12px 32px; }
    .card { padding: 16px 12px; }
    fieldset.q { padding: 12px 0; }
  }
  textarea {
    width: 100%; box-sizing: border-box; min-height: 80px;
    margin-top: 6px; padding: 10px 12px; border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 20%, transparent);
    background: color-mix(in srgb, var(--vscode-editor-background) 70%, transparent);
    color: var(--vscode-foreground); font-family: inherit; font-size: 1rem; resize: vertical;
  }
  button {
    margin-top: 20px; padding: 10px 26px; border: none; border-radius: 10px;
    background: var(--vscode-button-background); color: var(--vscode-button-foreground);
    font: inherit; min-height: 44px; cursor: pointer;
  }
  button:disabled { opacity: 0.45; cursor: default; }
  .hint { display: block; margin-top: 12px; color: var(--vscode-descriptionForeground); }
</style>
</head>
<body>
  <main class="card">
    <h1>Thanks - the session is complete</h1>
    <p class="sub">A few questions about your experience. Answers are linked to your participant ID and session in the study dataset.</p>
    ${rows}
    <fieldset class="q">
      <legend id="comments-label">Anything else about the session? (optional)</legend>
      <textarea id="comments" aria-labelledby="comments-label" placeholder="Where you got stuck, what helped, what got in the way…"></textarea>
    </fieldset>
    <button id="submit" disabled>Submit &amp; finish</button>
    <span class="hint" id="progress" role="status"></span>
  </main>
  <script nonce="${nonce}">
    const vscode = acquireVsCodeApi();
    const ids = ${JSON.stringify(items.map((i) => i.id))};
    const submit = document.getElementById('submit');
    const progress = document.getElementById('progress');
    function update() {
      const answered = ids.filter(id => document.querySelector('input[name="' + id + '"]:checked'));
      submit.disabled = answered.length !== ids.length;
      progress.textContent = answered.length + ' / ' + ids.length + ' answered';
    }
    document.addEventListener('change', update);
    update();
    submit.addEventListener('click', () => {
      const responses = {};
      for (const id of ids) {
        const el = document.querySelector('input[name="' + id + '"]:checked');
        if (el) responses[id] = parseInt(el.value, 10);
      }
      vscode.postMessage({
        kind: 'submit',
        responses,
        comments: document.getElementById('comments').value,
      });
    });
  </script>
</body>
</html>`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
