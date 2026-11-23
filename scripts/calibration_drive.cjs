#!/usr/bin/env node
/*
 * Drive a real VS Code window through a scripted calibration rehearsal.
 *
 * For dry runs and regression checks of the instrument only. Sessions an agent
 * drives are never calibration data: the calibration measures what TERN sees
 * when a person takes each route.
 *
 *   node scripts/calibration_drive.cjs STEPS.json [--out ACTIONS.jsonl]
 *
 * Launches an isolated VS Code (its own user-data and extensions folders, from
 * CALIBRATION_HOME/dry/vscode-*) on CALIBRATION_HOME/workspace with a debugging
 * port, connects with Playwright over CDP, runs the steps, and writes one JSON
 * line per action with wall-clock times: event-level ground truth to compare
 * with TERN's rows. Prints a JSON summary on stdout.
 *
 * Steps (each an object with "do"):
 *   start {participant?, condition?}   StudyLoop: Start Study Session
 *   end                                StudyLoop: End Study Session
 *   open {file}                        quick-open a workspace file
 *   goto {line}                        move the cursor to a line
 *   type {text, wpm?, typos?, seed?, keepIndent?}
 *                                      human-like typing: per-key jitter,
 *                                      occasional typo + backspace, bursts
 *   paste {text}                       put text on the clipboard, press Cmd+V
 *   palettePaste {text}                same text, pasted via the command palette
 *                                      (bypasses the Cmd+V keybinding, like the
 *                                      Edit menu)
 *   copyLine                           select the current line and press Cmd+C
 *   key {keys, times?}                 e.g. "Meta+Z", "Escape", "F2"
 *   command {name}                     run a command palette entry by title
 *   save                               Cmd+S
 *   pause {ms}                         idle
 *   reload {resume?}                   Developer: Reload Window, reconnect, then
 *                                      answer TERN's "interrupted session"
 *                                      notification (default "Resume session")
 *   notification {button}             click a button on a notification toast
 *   relaunch                           start VS Code again after a crash
 *   ghost {accept: tab|word|mouse|none, waitMs?}
 *                                      wait for Copilot's grey text (Alt+\
 *                                      triggers it) and accept it that way;
 *                                      logs whether any appeared
 *   chatOpen / chatMode {mode}         open the chat view; pick Agent or Ask
 *   chatAsk {prompt, waitMs?}          send a chat message, wait for the answer
 *   chatUse {how: insert|apply|copy}   use the last code block in the answer
 *   keep                               click Keep on pending chat edits
 *   crash                              kill VS Code without ending the session
 */
'use strict';

const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const REPO = path.resolve(__dirname, '..');
const { chromium } = require(path.join(REPO, 'platform', 'node_modules', 'playwright'));
const HOME = process.env.CALIBRATION_HOME || path.join(os.homedir(), 'ai-use-calibration');
const CODE = '/Applications/Visual Studio Code.app/Contents/MacOS/Code';
const PORT = Number(process.env.CALIBRATION_CDP_PORT || 9333);

function rng(seed) {
  let s = seed >>> 0 || 1;
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32);
}

class Driver {
  constructor(outPath) {
    this.out = outPath ? fs.openSync(outPath, 'a') : null;
    this.actions = [];
  }

  log(action, extra = {}) {
    const row = { ts: new Date().toISOString(), action, ...extra };
    this.actions.push(row);
    if (this.out !== null) fs.writeSync(this.out, JSON.stringify(row) + '\n');
  }

  async launch() {
    const dry = path.join(HOME, 'dry');
    this.proc = spawn(
      CODE,
      [
        '--user-data-dir', path.join(dry, 'vscode-user'),
        '--extensions-dir', path.join(dry, 'vscode-ext'),
        `--remote-debugging-port=${PORT}`,
        '--new-window',
        '--disable-workspace-trust',
        path.join(HOME, 'workspace'),
      ],
      { detached: true, stdio: 'ignore' },
    );
    this.proc.unref();
    this.log('launch', { pid: this.proc.pid });
    await this.connect();
  }

  async connect() {
    for (let i = 0; i < 60; i++) {
      try {
        this.browser = await chromium.connectOverCDP(`http://127.0.0.1:${PORT}`);
        break;
      } catch {
        await sleep(500);
      }
    }
    if (!this.browser) throw new Error('could not connect to VS Code over CDP');
    for (let i = 0; i < 60; i++) {
      const pages = this.browser.contexts().flatMap((c) => c.pages());
      this.page = pages.find((p) => p.url().includes('workbench'));
      if (this.page) break;
      await sleep(500);
    }
    if (!this.page) throw new Error('no workbench window');
    await this.page.waitForSelector('.monaco-workbench', { timeout: 60000 });
    await sleep(4000); // let extensions activate
  }

  async palette(name) {
    await this.page.keyboard.press('Meta+Shift+P');
    await this.page.waitForSelector('.quick-input-widget:not([style*="display: none"]) input', { timeout: 10000 });
    await this.page.keyboard.type(name, { delay: 15 });
    await sleep(600);
    await this.page.keyboard.press('Enter');
    await sleep(800);
  }

  async quickInputText() {
    return this.page.evaluate(() => {
      const w = document.querySelector('.quick-input-widget');
      return w && w.style.display !== 'none' ? w.innerText : '';
    });
  }

  async clipboard(text) {
    execFileSync('pbcopy', { input: text });
  }

  async humanType(text, { wpm = 55, typos = 0.03, seed = 7, keepIndent = false } = {}) {
    const rand = rng(seed);
    const perChar = 60000 / (wpm * 5);
    for (const line of text.split('\n').map((l, i, a) => (i < a.length - 1 ? l + '\n' : l))) {
      // The editor auto-indents; keepIndent types the given indentation on top,
      // which is how a person ends up with wrong indentation.
      const body = keepIndent ? line : line.replace(/^[ \t]+/, '');
      for (const ch of body) {
        if (ch === '\n') {
          await this.page.keyboard.press('Escape'); // close any suggestion first
          await this.page.keyboard.press('Enter');
        } else {
          if (rand() < typos && /[a-z]/i.test(ch)) {
            await this.page.keyboard.type(String.fromCharCode(97 + Math.floor(rand() * 26)));
            await sleep(perChar * (1 + rand()));
            await this.page.keyboard.press('Backspace');
          }
          await this.page.keyboard.insertText(ch);
        }
        // jitter, with an occasional thinking pause that ends an edit burst
        await sleep(rand() < 0.02 ? 2200 + rand() * 2500 : perChar * (0.4 + rand() * 1.2));
      }
    }
  }

  async run(step) {
    const p = this.page;
    switch (step.do) {
      case 'start': {
        await this.palette('StudyLoop: Start Study Session');
        await p.keyboard.type(step.participant ?? 'operator', { delay: 20 });
        await p.keyboard.press('Enter');
        await sleep(800);
        await p.keyboard.type(step.condition ?? 'Unspecified', { delay: 20 });
        await sleep(400);
        await p.keyboard.press('Enter');
        await sleep(1200);
        const preflight = await this.quickInputText();
        this.log('preflight', { text: preflight.slice(0, 1500) });
        await p.keyboard.type('Begin session', { delay: 15 });
        await sleep(400);
        await p.keyboard.press('Enter');
        await sleep(1500);
        break;
      }
      case 'end': {
        await this.palette('StudyLoop: End Study Session');
        await sleep(2000);
        for (let i = 0; i < 3; i++) {
          if (!(await this.quickInputText())) break;
          await p.keyboard.press('Escape');
          await sleep(500);
        }
        // The end survey is a webview tab; TERN writes session_end only once it
        // is answered or closed, so close it (skip) unless step.keepSurvey.
        const survey = await p.evaluate(() =>
          [...document.querySelectorAll('.tab.active .label-name')].map((e) => e.textContent),
        );
        this.log('endSurveyTab', { tabs: survey });
        if (!step.keepSurvey) {
          await p.keyboard.press('Meta+W');
          await sleep(2000);
        }
        break;
      }
      case 'open':
        await p.keyboard.press('Meta+P');
        await sleep(500);
        await p.keyboard.type(step.file, { delay: 20 });
        await sleep(700);
        await p.keyboard.press('Enter');
        await sleep(1000);
        break;
      case 'goto':
        await p.keyboard.press('Control+G');
        await sleep(300);
        await p.keyboard.type(String(step.line));
        await p.keyboard.press('Enter');
        await sleep(300);
        break;
      case 'type':
        await this.humanType(step.text, step);
        break;
      case 'paste':
        await this.clipboard(step.text);
        await sleep(300);
        await p.keyboard.press('Meta+V');
        await sleep(600);
        break;
      case 'palettePaste':
        await this.clipboard(step.text);
        await this.palette('Paste');
        break;
      case 'copyLine':
        await p.keyboard.press('Meta+L'); // expand selection to the line
        await sleep(200);
        await p.keyboard.press('Meta+C');
        await sleep(300);
        break;
      case 'key':
        for (let i = 0; i < (step.times ?? 1); i++) {
          await p.keyboard.press(step.keys);
          await sleep(step.times ? 120 : 400);
        }
        break;
      case 'command':
        await this.palette(step.name);
        break;
      case 'save':
        await p.keyboard.press('Meta+S');
        await sleep(1200);
        break;
      case 'pause':
        await sleep(step.ms);
        break;
      case 'reload':
        await this.palette('Developer: Reload Window');
        await sleep(3000);
        await this.browser.close().catch(() => {});
        await this.connect();
        if (step.resume !== false) await this.clickNotification('Resume session');
        break;
      case 'notification':
        await this.clickNotification(step.button);
        break;
      case 'crash':
        this.killAll('SIGKILL');
        await sleep(1500);
        break;
      case 'relaunch':
        await this.launch();
        break;
      case 'ghost':
        await this.ghost(step);
        break;
      case 'chatOpen':
        await p.keyboard.press('Control+Meta+I');
        await sleep(2500);
        this.log('chatOpen', {
          chatInputs: await p.locator('.interactive-input-part .monaco-editor').count(),
        });
        break;
      case 'chatMode': {
        const picker = p.locator('.interactive-input-part .action-item', {
          hasText: /^(Agent|Ask|Edit|Plan)$/,
        });
        await picker.first().click({ timeout: 8000 });
        await sleep(800);
        await p.locator('.monaco-list-row', { hasText: new RegExp(`^${step.mode}`) })
          .first().click({ timeout: 8000 });
        await sleep(800);
        this.log('chatMode', { mode: step.mode });
        break;
      }
      case 'chatAsk': {
        const blocks = p.locator('.interactive-result-code-block');
        const before = await blocks.count();
        await p.locator('.interactive-input-part .monaco-editor').first().click();
        await p.keyboard.insertText(step.prompt);
        await p.keyboard.press('Enter');
        let after = before;
        for (let i = 0; i < (step.waitMs ?? 90000) / 1000; i++) {
          await sleep(1000);
          after = await blocks.count();
          if (after > before) break;
        }
        await sleep(5000); // let the answer finish streaming
        const answer = await p.locator('.interactive-response').last().innerText()
          .catch(() => '');
        this.log('chatAnswer', {
          newCodeBlocks: (await blocks.count()) - before,
          answerChars: answer.length,
          answerStart: answer.slice(0, 160),
        });
        break;
      }
      case 'chatUse': {
        const label = { insert: 'Insert At Cursor', apply: 'Apply in Editor', copy: 'Copy' }[step.how];
        const block = p.locator('.interactive-result-code-block').last();
        await block.hover();
        await sleep(800);
        const button = block.locator(`[aria-label^="${label}"]`).first();
        try {
          await button.click({ timeout: 8000 });
          this.log('chatUse', { how: step.how, clicked: true });
        } catch {
          this.log('chatUse', { how: step.how, clicked: false });
        }
        await sleep(3000);
        break;
      }
      case 'keep': {
        const keep = p.locator('.monaco-button, .action-label', { hasText: /^(Keep|Accept)$/ });
        try {
          await keep.first().click({ timeout: 8000 });
          this.log('keep', { clicked: true });
        } catch {
          this.log('keep', { clicked: false });
        }
        await sleep(1500);
        break;
      }
      default:
        throw new Error(`unknown step ${JSON.stringify(step)}`);
    }
  }

  /** Every process of this isolated instance, found by its user-data folder. */
  killAll(signal) {
    let pids = [];
    try {
      pids = execFileSync('pgrep', ['-f', path.join(HOME, 'dry', 'vscode-user')])
        .toString().split(/\s+/).filter(Boolean).map(Number);
    } catch {
      /* none left */
    }
    for (const pid of pids) {
      try {
        process.kill(pid, signal);
      } catch {
        /* already gone */
      }
    }
    this.log('kill', { signal, pids });
  }

  async ghost({ accept = 'tab', waitMs = 15000 } = {}) {
    const p = this.page;
    const grey = p.locator('.monaco-editor .ghost-text');
    let seen = false;
    for (let i = 0; i < waitMs / 1000; i++) {
      if (i === 2 || i === 8) await p.keyboard.press('Alt+Backslash'); // trigger
      await sleep(1000);
      if ((await grey.count()) > 0) {
        seen = true;
        break;
      }
    }
    const text = seen ? (await grey.allInnerTexts()).join('').slice(0, 200) : '';
    let accepted = false;
    if (seen && accept === 'tab') {
      await p.keyboard.press('Tab');
      accepted = true;
    } else if (seen && accept === 'word') {
      for (let i = 0; i < 4; i++) {
        await p.keyboard.press('Meta+ArrowRight');
        await sleep(300);
      }
      accepted = true;
    } else if (seen && accept === 'mouse') {
      // The view-lines layer intercepts pointer events, so move the real
      // pointer over the grey text instead of using an actionability check.
      const box = await grey.last().boundingBox();
      if (box) await p.mouse.move(box.x + box.width / 2, box.y + box.height / 2, { steps: 8 });
      await sleep(1500);
      const hint = p.locator('.inlineSuggestionsHints [aria-label^="Accept"], .inlineSuggestionsHints .action-label', {
        hasText: /Accept/,
      });
      try {
        await hint.first().click({ timeout: 5000 });
        accepted = true;
      } catch {
        const any = p.locator('[aria-label^="Accept"]').first();
        try {
          await any.click({ timeout: 3000 });
          accepted = true;
        } catch {
          /* no toolbar */
        }
      }
    }
    this.log('ghost', { accept, seen, accepted, chars: text.length });
    await sleep(1500);
  }

  async clickNotification(button) {
    const target = this.page.locator('.notifications-toasts .monaco-button', { hasText: button });
    try {
      await target.first().click({ timeout: 15000 });
      this.log('notification', { clicked: button });
      await sleep(2000);
    } catch {
      this.log('notification', { missing: button });
    }
  }

  async close() {
    try {
      await this.page.keyboard.press('Meta+Q');
      await sleep(2500);
    } catch {
      /* already gone */
    }
    this.killAll('SIGTERM');
  }
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function main() {
  const [stepsPath, ...rest] = process.argv.slice(2);
  if (!stepsPath) {
    console.error('usage: calibration_drive.cjs STEPS.json [--out ACTIONS.jsonl]');
    process.exit(2);
  }
  const outIndex = rest.indexOf('--out');
  const driver = new Driver(outIndex >= 0 ? rest[outIndex + 1] : null);
  const steps = JSON.parse(fs.readFileSync(stepsPath, 'utf8'));
  let error = null;
  try {
    await driver.launch();
    for (const step of steps) {
      driver.log('step', { step: { ...step, text: step.text?.slice(0, 80) } });
      await driver.run(step);
    }
  } catch (e) {
    error = String(e && e.stack ? e.stack : e);
    driver.log('error', { error });
  }
  if (steps.at(-1)?.do !== 'crash') await driver.close();
  console.log(JSON.stringify({ ok: !error, error, actions: driver.actions.length }));
  process.exit(error ? 1 : 0);
}

main();
