import * as vscode from 'vscode';
import {
  AI_CONDITION_ITEM,
  END_SURVEY_ITEMS,
  LikertItem,
} from '../core/surveys';
import { StudyCondition } from '../core/types';

export interface EndSurveyResult {
  responses: Record<string, number>;
  comments: string;
  msToComplete: number;
}

/**
 * End-of-study questionnaire in a webview panel - the one moment where
 * taking screen space is fine. Styled as a frosted-glass card over the
 * editor theme colors.
 */
export function showEndSurvey(
  condition: StudyCondition,
): Promise<EndSurveyResult | undefined> {
  const items: LikertItem[] = [...END_SURVEY_ITEMS];
  if (condition === 'ai-assisted') items.push(AI_CONDITION_ITEM);

  const panel = vscode.window.createWebviewPanel(
    'cognitiveOverlay.endSurvey',
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
        <div class="scale">
          <span class="edge">${escapeHtml(item.lowLabel)}</span>
          ${Array.from({ length: item.points }, (_, i) => {
            const v = i + 1;
            return `<label><input type="radio" name="${item.id}" value="${v}"><span>${v}</span></label>`;
          }).join('')}
          <span class="edge">${escapeHtml(item.highLabel)}</span>
        </div>
      </fieldset>`,
    )
    .join('\n');

  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta http-equiv="Content-Security-Policy"
      content="default-src 'none'; style-src 'unsafe-inline'; script-src 'nonce-${nonce}';">
<style>
  :root { color-scheme: light dark; }
  body {
    margin: 0; padding: 32px 16px 64px;
    display: flex; justify-content: center;
    font-family: var(--vscode-font-family);
    color: var(--vscode-foreground);
    background:
      radial-gradient(1000px 500px at 15% -10%, color-mix(in srgb, var(--vscode-button-background) 22%, transparent), transparent 60%),
      radial-gradient(800px 500px at 110% 110%, color-mix(in srgb, var(--vscode-charts-purple, #a78bfa) 16%, transparent), transparent 60%),
      var(--vscode-editor-background);
  }
  .card {
    width: min(680px, 100%);
    padding: 28px 32px;
    border-radius: 16px;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 14%, transparent);
    background: color-mix(in srgb, var(--vscode-editor-background) 62%, transparent);
    backdrop-filter: blur(18px) saturate(1.3);
    -webkit-backdrop-filter: blur(18px) saturate(1.3);
    box-shadow: 0 18px 50px rgba(0,0,0,0.28);
  }
  h1 { font-size: 1.25em; font-weight: 600; margin: 0 0 4px; }
  p.sub { margin: 0 0 24px; opacity: 0.7; font-size: 0.9em; }
  fieldset.q {
    border: none; margin: 0 0 20px; padding: 14px 16px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--vscode-foreground) 4%, transparent);
  }
  legend { font-weight: 500; padding: 0 4px; }
  .scale { display: flex; align-items: center; gap: 6px; margin-top: 10px; flex-wrap: wrap; }
  .scale .edge { font-size: 0.75em; opacity: 0.6; min-width: 70px; }
  .scale .edge:last-child { text-align: right; }
  .scale label { position: relative; cursor: pointer; }
  .scale input { position: absolute; opacity: 0; inset: 0; cursor: pointer; }
  .scale label span {
    display: flex; align-items: center; justify-content: center;
    width: 34px; height: 34px; border-radius: 50%;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 25%, transparent);
    font-size: 0.85em; transition: all 0.12s ease;
  }
  .scale label:hover span { border-color: var(--vscode-button-background); }
  .scale input:checked + span {
    background: var(--vscode-button-background);
    color: var(--vscode-button-foreground);
    border-color: transparent;
    transform: scale(1.08);
  }
  textarea {
    width: 100%; box-sizing: border-box; min-height: 80px;
    margin-top: 6px; padding: 10px 12px; border-radius: 10px;
    border: 1px solid color-mix(in srgb, var(--vscode-foreground) 20%, transparent);
    background: color-mix(in srgb, var(--vscode-editor-background) 70%, transparent);
    color: var(--vscode-foreground); font-family: inherit; resize: vertical;
  }
  button {
    margin-top: 20px; padding: 10px 26px; border: none; border-radius: 10px;
    background: var(--vscode-button-background); color: var(--vscode-button-foreground);
    font-size: 1em; cursor: pointer;
  }
  button:disabled { opacity: 0.45; cursor: default; }
  .hint { font-size: 0.8em; opacity: 0.6; margin-left: 12px; }
</style>
</head>
<body>
  <div class="card">
    <h1>Thanks - the session is complete</h1>
    <p class="sub">A few quick questions about how it felt. All answers are anonymous within the study dataset.</p>
    ${rows}
    <fieldset class="q">
      <legend>Anything else about the session? (optional)</legend>
      <textarea id="comments" placeholder="Where you got stuck, what helped, what got in the way…"></textarea>
    </fieldset>
    <button id="submit" disabled>Submit &amp; finish</button>
    <span class="hint" id="progress"></span>
  </div>
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
