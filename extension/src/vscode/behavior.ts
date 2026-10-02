import * as crypto from 'crypto';
import * as vscode from 'vscode';
import {
  BurstAggregator,
  DEFAULT_BURST_CONFIG,
  EditBurst,
} from '../core/behavior';
import {
  AttentionExit,
  AttentionTracker,
  DEFAULT_ATTENTION_CONFIG,
} from '../core/attention';
import { CaptureFilterConfig, shouldCapture } from '../core/captureFilter';
import { FirstLastDebouncer, TrailingDebouncer } from '../core/debounce';
import { DEFAULT_IDLE_CONFIG, IdleDetector } from '../core/idle';

export interface BehaviorPort {
  record(type: string, payload: Record<string, unknown>): void;
}

const PENDING_MATCH_WINDOW_MS = 1_500;

const SUGGESTION_SESSION_GAP_MS = 2_000;

const COPY_HASH_TTL_MS = 30 * 60_000;
const MAX_COPY_HASHES = 8;

function cfg<T>(key: string, fallback: T): T {
  return vscode.workspace
    .getConfiguration('tern.behavior')
    .get<T>(key, fallback);
}

interface FileMeta {
  languageId: string;
  workspaceRelativePath?: string;
}

function fileMeta(doc: vscode.TextDocument): FileMeta {
  const inWorkspace =
    doc.uri.scheme === 'file' &&
    vscode.workspace.getWorkspaceFolder(doc.uri) !== undefined;
  return {
    languageId: doc.languageId,
    workspaceRelativePath: inWorkspace
      ? vscode.workspace.asRelativePath(doc.uri, false)
      : undefined,
  };
}

export class BehaviorCapture implements vscode.Disposable {
  private readonly subs: vscode.Disposable[] = [];
  private readonly aggregator: BurstAggregator;
  private readonly attention: AttentionTracker;
  private readonly idle: IdleDetector;
  private readonly focusDebouncer: FirstLastDebouncer<Record<string, unknown>>;
  private readonly rangeDebouncers = new Map<
    string,
    TrailingDebouncer<Record<string, unknown>>
  >();
  private readonly filterCfg: CaptureFilterConfig;
  private readonly visibleRangeDebounceMs: number;

  private readonly copySalt = crypto.randomBytes(16).toString('hex');
  private recentCopies: { hash: string; at: number }[] = [];
  private pendingPaste?: { at: number };
  private pendingAiAccept?: { at: number; suggestionId: string };

  private lastInlineQueryAt = Number.NEGATIVE_INFINITY;
  private suggestionShownAt = 0;
  private suggestionSeq = 0;
  private currentSuggestionId?: string;

  private readonly erroredSources = new Set<string>();

  constructor(private readonly port: BehaviorPort) {
    this.filterCfg = {
      languages: cfg('languages', ['python']),
      workspaceInternalOnly: cfg('workspaceInternalOnly', true),
    };
    this.visibleRangeDebounceMs = cfg('visibleRangeDebounceMs', 500);

    this.aggregator = new BurstAggregator(
      {
        ...DEFAULT_BURST_CONFIG,
        gapMs: cfg('burstGapMs', 2_000),
        aiCorrelationMs: cfg('aiCorrelationMs', 500),
        aiBlockCharThreshold: cfg('aiBlockCharThreshold', 80),
        aiBlockMaxDurationMs: cfg('aiBlockMaxDurationMs', 50),
        pasteCorrelationMs: cfg('pasteCorrelationMs', 100),
      },
      (burst) => this.onBurst(burst),
    );

    this.attention = new AttentionTracker(
      {
        ...DEFAULT_ATTENTION_CONFIG,
        regionRadiusLines: cfg('attentionRegionRadiusLines', 3),
        minDwellMs: cfg('attentionMinDwellMs', 1_500),
      },
      (event) => {
        if (cfg('captureAttention', true)) {
          this.port.record('attention', { ...event });
        }
      },
    );

    this.idle = new IdleDetector(
      {
        ...DEFAULT_IDLE_CONFIG,
        windowMs: cfg('idleWindowSeconds', 120) * 1000,
      },
      (state) => {
        this.attention.setPresent(state === 'active', Date.now());
        if (cfg('captureHeartbeat', true)) {
          this.port.record('heartbeat', { state });
        }
      },
    );

    this.focusDebouncer = new FirstLastDebouncer(
      cfg('focusDebounceMs', 250),
      (payload) => this.port.record('editor_focus', payload),
    );

    this.wireListeners();
  }

  start(): void {
    this.aggregator.start();
    this.idle.start();
  }

  pause(reason: AttentionExit = 'session-pause'): void {
    this.aggregator.flush();
    this.aggregator.stop();
    this.attention.flush(Date.now(), reason);
    this.idle.stop();
  }

  resume(): void {
    this.aggregator.start();
    this.attention.setPresent(true, Date.now());
    this.idle.start();
  }

  dispose(): void {
    this.aggregator.dispose();
    this.attention.dispose();
    this.idle.dispose();
    this.focusDebouncer.dispose();
    for (const d of this.rangeDebouncers.values()) d.dispose();
    this.rangeDebouncers.clear();
    for (const s of this.subs) s.dispose();
    this.recentCopies = [];
  }

  private wireListeners(): void {
    this.subs.push(
      vscode.window.onDidChangeActiveTextEditor((editor) =>
        this.guard('focus', () => this.onActiveEditor(editor)),
      ),
      vscode.window.onDidChangeWindowState((state) =>
        this.guard('window-state', () => this.onWindowState(state)),
      ),
      vscode.window.onDidChangeTextEditorVisibleRanges((e) =>
        this.guard('visible-range', () => this.onVisibleRanges(e)),
      ),
      vscode.window.onDidChangeTextEditorSelection((e) =>
        this.guard('selection', () => this.onSelection(e)),
      ),
      vscode.workspace.onDidChangeTextDocument((e) =>
        this.guard('document-change', () => this.onDocumentChange(e)),
      ),
      vscode.workspace.onDidSaveTextDocument((doc) =>
        this.guard('save', () => this.onSave(doc)),
      ),
    );

    if (cfg('captureAiLifecycle', true)) {
      this.subs.push(
        vscode.languages.registerInlineCompletionItemProvider(
          { pattern: '**' },
          {
            provideInlineCompletionItems: () => {
              this.guard('inline-query', () => this.onInlineQuery());
              return [];
            },
          },
        ),
      );
    }

    if (cfg('captureAttention', true)) {
      this.subs.push(
        vscode.languages.registerHoverProvider(
          { pattern: '**' },
          {
            provideHover: (doc, pos) => {
              this.guard('hover', () => this.onHover(doc, pos));
              return undefined;
            },
          },
        ),
      );
    }
  }

  private onActiveEditor(editor: vscode.TextEditor | undefined): void {
    const now = Date.now();
    this.idle.activity(now);

    if (cfg('captureAttention', true)) {
      const captured =
        editor !== undefined &&
        shouldCapture(this.filterCfg, fileMeta(editor.document));
      if (!captured) this.attention.flush(now, 'file-switch');
    }
    if (!editor || !cfg('captureFocus', true)) return;
    const meta = fileMeta(editor.document);
    this.focusDebouncer.push({
      file: meta.workspaceRelativePath ?? 'external',
      languageId: meta.languageId,
      groupCount: vscode.window.tabGroups.all.length,
    });
  }

  private onWindowState(state: vscode.WindowState): void {
    if (state.focused) this.idle.activity(Date.now());

    this.attention.setPresent(state.focused, Date.now());
    if (!cfg('captureFocus', true)) return;
    this.port.record('editor_focus', {
      state: state.focused ? 'focused' : 'blurred',
    });
  }

  private onSelection(e: vscode.TextEditorSelectionChangeEvent): void {
    const now = Date.now();
    this.idle.activity(now);
    if (!cfg('captureAttention', true)) return;
    const meta = fileMeta(e.textEditor.document);
    if (!shouldCapture(this.filterCfg, meta)) {
      this.attention.flush(now, 'file-switch');
      return;
    }
    this.attention.look(
      'cursor',
      meta.workspaceRelativePath ?? 'external',
      e.selections[0].active.line,
      now,
    );
  }

  private onHover(doc: vscode.TextDocument, pos: vscode.Position): void {
    const now = Date.now();
    this.idle.activity(now);
    if (!cfg('captureAttention', true)) return;
    const meta = fileMeta(doc);
    if (!shouldCapture(this.filterCfg, meta)) {
      this.attention.flush(now, 'file-switch');
      return;
    }
    this.attention.look(
      'hover',
      meta.workspaceRelativePath ?? 'external',
      pos.line,
      now,
    );
  }

  private onVisibleRanges(e: vscode.TextEditorVisibleRangesChangeEvent): void {
    this.idle.activity(Date.now());
    if (!cfg('captureVisibleRanges', true)) return;
    const meta = fileMeta(e.textEditor.document);
    if (!shouldCapture(this.filterCfg, meta)) return;
    const r = e.visibleRanges[0];
    if (!r) return;

    const key = e.textEditor.document.uri.toString();
    let debouncer = this.rangeDebouncers.get(key);
    if (!debouncer) {
      debouncer = new TrailingDebouncer(this.visibleRangeDebounceMs, (p) =>
        this.port.record('visible_range', p),
      );
      this.rangeDebouncers.set(key, debouncer);
    }
    debouncer.push({
      file: meta.workspaceRelativePath ?? 'external',
      topLine: r.start.line,
      bottomLine: r.end.line,
      totalLines: e.textEditor.document.lineCount,
    });
  }

  private onDocumentChange(e: vscode.TextDocumentChangeEvent): void {
    if (e.document.uri.scheme !== 'file' || e.contentChanges.length === 0) {
      return;
    }
    const now = Date.now();
    this.idle.activity(now);

    const meta = fileMeta(e.document);
    if (!shouldCapture(this.filterCfg, meta)) return;

    let charsAdded = 0;
    let charsDeleted = 0;
    let lines = 0;
    let insertedText = '';
    for (const c of e.contentChanges) {
      charsAdded += c.text.length;
      charsDeleted += c.rangeLength;
      const newlines = (c.text.match(/\n/g) ?? []).length;
      lines += Math.max(
        c.range.end.line - c.range.start.line + 1,
        newlines + 1,
      );
      insertedText += c.text;
    }

    if (cfg('captureAttention', true) && charsAdded + charsDeleted > 0) {
      this.attention.edit(
        meta.workspaceRelativePath ?? 'external',
        e.contentChanges[0].range.start.line,
        now,
      );
    }

    this.matchPendingPaste(now, meta, charsAdded, insertedText);
    this.matchPendingAiAccept(now, charsAdded, insertedText);

    if (cfg('captureEditBursts', true)) {
      const undoRedo =
        e.reason === vscode.TextDocumentChangeReason.Undo ||
        e.reason === vscode.TextDocumentChangeReason.Redo;
      this.aggregator.change({
        fileKey: meta.workspaceRelativePath ?? 'external',
        charsAdded,
        charsDeleted,
        lines,
        tsMono: now,
        undoRedo,
      });
    }
  }

  private onBurst(burst: EditBurst): void {
    this.port.record('edit_burst', { ...burst });
  }

  private onSave(doc: vscode.TextDocument): void {
    this.idle.activity(Date.now());
    if (!cfg('captureSaves', true)) return;
    const meta = fileMeta(doc);
    if (!shouldCapture(this.filterCfg, meta)) return;
    this.port.record('file_save', {
      file: meta.workspaceRelativePath ?? 'external',
      charCount: doc.getText().length,
      lineCount: doc.lineCount,
    });
  }

  noteCopy(): void {
    this.guard('copy', () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor || !cfg('captureClipboard', true)) return;
      if (fileMeta(editor.document).workspaceRelativePath === undefined) {
        return;
      }
      const text = editor.selections
        .map((sel) =>
          sel.isEmpty
            ? editor.document.lineAt(sel.active.line).text + '\n'
            : editor.document.getText(sel),
        )
        .join('\n');
      if (!text) return;
      this.recentCopies.push({ hash: this.hash(text), at: Date.now() });
      if (this.recentCopies.length > MAX_COPY_HASHES) {
        this.recentCopies.shift();
      }
    });
  }

  notePaste(): void {
    this.guard('paste', () => {
      if (!cfg('captureClipboard', true)) return;
      this.pendingPaste = { at: Date.now() };
    });
  }

  noteInlineAccept(): void {
    this.guard('inline-accept', () => {
      if (!cfg('captureAiLifecycle', true)) return;
      this.pendingAiAccept = {
        at: Date.now(),
        suggestionId: this.currentSuggestionId ?? this.newSuggestionId(),
      };
    });
  }

  noteInlineDismiss(): void {
    this.guard('inline-dismiss', () => {
      if (!cfg('captureAiLifecycle', true)) return;
      this.port.record('ai_suggestion', {
        suggestionId: this.currentSuggestionId ?? this.newSuggestionId(),
        action: 'dismissed',
        visibleMs: Date.now() - this.suggestionShownAt,
      });
      this.currentSuggestionId = undefined;
    });
  }

  private onInlineQuery(): void {
    if (!cfg('captureAiLifecycle', true)) return;
    const now = Date.now();
    if (now - this.lastInlineQueryAt > SUGGESTION_SESSION_GAP_MS) {
      const suggestionId = this.newSuggestionId();
      this.suggestionShownAt = now;
      this.port.record('ai_suggestion', { suggestionId, action: 'shown' });
    }
    this.lastInlineQueryAt = now;
  }

  private matchPendingAiAccept(
    now: number,
    charsAdded: number,
    insertedText: string,
  ): void {
    const pending = this.pendingAiAccept;
    if (!pending) return;
    if (now - pending.at > PENDING_MATCH_WINDOW_MS) {
      this.pendingAiAccept = undefined;
      return;
    }
    if (charsAdded === 0) return;
    this.pendingAiAccept = undefined;
    this.aggregator.noteAiAccept(now);
    this.port.record('ai_suggestion', {
      suggestionId: pending.suggestionId,
      action: 'accepted',
      visibleMs: pending.at - this.suggestionShownAt,
      charCount: charsAdded,
      lineCount: (insertedText.match(/\n/g) ?? []).length + 1,
    });
    this.currentSuggestionId = undefined;
  }

  private matchPendingPaste(
    now: number,
    meta: FileMeta,
    charsAdded: number,
    insertedText: string,
  ): void {
    const pending = this.pendingPaste;
    if (!pending) return;
    if (now - pending.at > PENDING_MATCH_WINDOW_MS) {
      this.pendingPaste = undefined;
      return;
    }
    if (charsAdded === 0) return;
    this.pendingPaste = undefined;
    this.aggregator.notePaste(now);

    const cutoff = now - COPY_HASH_TTL_MS;
    this.recentCopies = this.recentCopies.filter((c) => c.at >= cutoff);
    const pastedHash = this.hash(insertedText);
    const internal = this.recentCopies.find((c) => c.hash === pastedHash);

    this.port.record('clipboard_paste', {
      charCount: charsAdded,
      lineCount: (insertedText.match(/\n/g) ?? []).length + 1,
      ...(internal ? { msSinceInternalCopy: now - internal.at } : {}),
      targetFile: meta.workspaceRelativePath ?? 'external',
    });
  }

  private hash(text: string): string {
    return crypto
      .createHash('sha256')
      .update(this.copySalt + text)
      .digest('hex');
  }

  private newSuggestionId(): string {
    this.currentSuggestionId = `sg-${++this.suggestionSeq}`;
    return this.currentSuggestionId;
  }

  private guard(source: string, fn: () => void): void {
    try {
      fn();
    } catch (err) {
      if (this.erroredSources.has(source)) return;
      this.erroredSources.add(source);
      try {
        this.port.record('behavior_sensor_error', {
          source,
          message: String(err),
        });
      } catch {
        // Even the error report is best-effort.
      }
    }
  }
}

export function registerBehaviorCommands(
  capture: () => BehaviorCapture | undefined,
): vscode.Disposable {
  const wrap = (
    id: string,
    note: (c: BehaviorCapture) => void,
    delegate: string,
  ): vscode.Disposable =>
    vscode.commands.registerCommand(id, async () => {
      try {
        const c = capture();
        if (c) note(c);
      } finally {
        await vscode.commands.executeCommand(delegate);
      }
    });

  return vscode.Disposable.from(
    wrap(
      'tern.behavior.copy',
      (c) => c.noteCopy(),
      'editor.action.clipboardCopyAction',
    ),
    wrap(
      'tern.behavior.cut',
      (c) => c.noteCopy(),
      'editor.action.clipboardCutAction',
    ),
    wrap(
      'tern.behavior.paste',
      (c) => c.notePaste(),
      'editor.action.clipboardPasteAction',
    ),
    wrap(
      'tern.behavior.acceptInline',
      (c) => c.noteInlineAccept(),
      'editor.action.inlineSuggest.commit',
    ),
    wrap(
      'tern.behavior.dismissInline',
      (c) => c.noteInlineDismiss(),
      'editor.action.inlineSuggest.hide',
    ),
  );
}

const AI_EXTENSION_PATTERN =
  /copilot|claude|codeium|cursor|tabnine|continue|cody|supermaven|windsurf/i;

export function environmentSnapshotPayload(
  context: vscode.ExtensionContext,
  platform: string,
): Record<string, unknown> {
  const extensionVersions: Record<string, string> = {
    [context.extension.id]: String(
      context.extension.packageJSON.version ?? 'unknown',
    ),
  };
  for (const ext of vscode.extensions.all) {
    if (AI_EXTENSION_PATTERN.test(ext.id)) {
      extensionVersions[ext.id] = String(ext.packageJSON?.version ?? 'unknown');
    }
  }
  const session = vscode.workspace.getConfiguration('tern.session');
  const agentTool = session.get<string>('agentTool', '');
  const agentModelId = session.get<string>('agentModelId', '');
  return {
    vscodeVersion: vscode.version,
    extensionVersions,
    os: platform,
    ...(agentTool ? { agentTool } : {}),
    ...(agentModelId ? { agentModelId } : {}),
    taskId: session.get<string>('taskId', ''),
  };
}
