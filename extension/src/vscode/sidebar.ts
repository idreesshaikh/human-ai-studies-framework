import * as vscode from 'vscode';
import {
  readLegs,
  activeLegCount,
  capturesContent,
  Leg,
  LegState,
} from '../core/legs';
import { SessionBlock } from '../core/captureConfig';
import { STATE_BLOCK, STATE_LEGS, STATE_PENDING } from './pairing';

/**
 * The study, in the sidebar (FR-INST-22).
 *
 * Three views answer the three questions a participant actually has: *am I in
 * a session?*, *what is being captured right now?*, and *where is my data
 * going?* Before this the only permanent surface was a countdown in the status
 * bar, which cannot answer any of them.
 *
 * Tree views rather than a webview, deliberately: they inherit VS Code's
 * theming, keyboard navigation, and screen-reader behaviour, which is most of
 * NFR-12's bar met by construction instead of re-implemented in HTML  -  and
 * they cannot execute anything, which matters on a surface that renders
 * server-supplied strings.
 *
 * Passive by construction (NFR-1): these providers read state and never drive
 * the recorder. If a provider throws, the session is unaffected.
 */

/** What the sidebar needs to know about the running session. Supplied by
 *  `extension.ts` as a getter so this module holds no session state of its
 *  own and cannot keep a finished session alive. */
export interface SidebarSession {
  active: boolean;
  /** The session is closed to capture while the end survey is on screen. */
  ending?: boolean;
  paused: boolean;
  participantId?: string;
  condition?: string;
  dataFile?: string;
  /** Events written locally vs. mirrored upstream  -  a `seq` gap here is how
   *  loss stays detectable (NFR-2), so it belongs on the participant's
   *  surface, not only in a log file. */
  written?: number;
  mirrored?: number;
}

export type SessionProbe = () => SidebarSession;

const STATE_ICONS: Record<LegState, string> = {
  enabled: 'pass-filled',
  disabled: 'circle-slash',
  unavailable: 'question',
};

const STATE_WORDS: Record<LegState, string> = {
  enabled: 'Recording',
  disabled: 'Off for this study',
  unavailable: 'Not part of this study',
};

/** One row. `kind` keeps the three providers' node types apart without a
 *  class hierarchy nobody needs. */
class Row extends vscode.TreeItem {
  /** Make this row activate a command when clicked or pressed with Enter.
   *  Returns `this` so rows stay declarative at the call site. */
  runs(command: string, title: string): Row {
    this.command = { command, title };
    return this;
  }

  constructor(
    label: string,
    description?: string,
    icon?: string,
    collapsible: vscode.TreeItemCollapsibleState = vscode
      .TreeItemCollapsibleState.None,
    public readonly children: Row[] = [],
  ) {
    super(label, collapsible);
    if (description !== undefined) this.description = description;
    if (icon) this.iconPath = new vscode.ThemeIcon(icon);
  }
}

abstract class BaseProvider implements vscode.TreeDataProvider<Row> {
  private readonly emitter = new vscode.EventEmitter<Row | undefined>();
  readonly onDidChangeTreeData = this.emitter.event;

  refresh(): void {
    this.emitter.fire(undefined);
  }

  getTreeItem(el: Row): vscode.TreeItem {
    return el;
  }

  getChildren(el?: Row): Row[] {
    return el ? el.children : this.roots();
  }

  protected abstract roots(): Row[];
}

/** View 1  -  Session. The start/pause/end actions that were previously only
 *  reachable through the status-bar quick-pick. */
export class SessionView extends BaseProvider {
  constructor(
    private readonly probe: SessionProbe,
    private readonly context: vscode.ExtensionContext,
  ) {
    super();
  }

  /** The task this session was assigned, if the study declares tasks. */
  private block(): SessionBlock | undefined {
    return this.context.workspaceState.get<SessionBlock>(STATE_BLOCK);
  }

  protected roots(): Row[] {
    const s = this.probe();
    if (!s.active) {
      return [
        new Row('No session running', undefined, 'circle-outline'),
        new Row('Start a session', undefined, 'play').runs(
          'tern.startSession',
          'Start session',
        ),
      ];
    }
    if (s.ending) {
      return [
        new Row(
          'Debrief in progress',
          'Answer the questions to finish',
          'comment-discussion',
        ),
        ...(s.participantId
          ? [
              new Row(
                'You are',
                `${s.participantId} · ${s.condition ?? ''}`.trim(),
                'account',
              ),
            ]
          : []),
      ];
    }
    const rows = [
      new Row(
        s.paused ? 'Paused' : 'Recording',
        s.paused ? 'Timer paused' : 'Timer in status bar',
        s.paused ? 'debug-pause' : 'record',
      ),
    ];
    if (s.participantId) {
      rows.push(
        new Row(
          'You are',
          `${s.participantId} · ${s.condition ?? ''}`.trim(),
          'account',
        ),
      );
    }
    /* What this session is actually for. A participant who is told only
     * their condition has to guess at the work; the researcher chose the
     * task and counterbalanced its order, so it belongs on screen. */
    const block = this.block();
    if (block) {
      rows.push(
        new Row(
          block.title,
          `Task ${block.index + 1} of ${block.of}`,
          'checklist',
        ),
      );
      if (block.description) {
        rows.push(new Row(block.description, undefined, 'note'));
      }
      if (block.materials) {
        rows.push(new Row('Materials', block.materials, 'repo'));
      }
    }
    return rows;
  }
}

/** View 2  -  Capture. All four legs, always. */
export class CaptureView extends BaseProvider {
  constructor(private readonly context: vscode.ExtensionContext) {
    super();
  }

  private legs(): Leg[] {
    return readLegs({ legs: this.context.workspaceState.get(STATE_LEGS) });
  }

  protected roots(): Row[] {
    const legs = this.legs();
    const pending = this.context.workspaceState.get<string>(STATE_PENDING);
    const rows: Row[] = [];

    if (legs.every((l) => l.state === 'unavailable')) {
      // The empty state is the most-seen screen in the extension: it is what a
      // participant meets before pairing, so it says what to do next.
      rows.push(
        new Row('Not connected to a study', undefined, 'debug-disconnect'),
        new Row('Connect to a study', undefined, 'link').runs(
          'tern.connectToStudy',
          'Connect to study',
        ),
      );
      return rows;
    }

    if (capturesContent(legs)) {
      // The standing exception to "no raw code content" (FR-ETH-2). Surfaced
      // at the top so it is never something a participant has to go digging
      // through three expanded trees to discover.
      rows.push(
        new Row(
          'This study stores code',
          'workspace snapshots are on',
          'shield',
        ),
      );
    }

    if (pending) {
      rows.push(
        new Row(
          'A change is waiting',
          'applies at your next session start',
          'history',
        ),
      );
    }

    for (const leg of legs) {
      const children = leg.toggles.map(
        (t) =>
          new Row(
            t.label,
            typeof t.currentValue === 'boolean'
              ? t.currentValue
                ? 'on'
                : 'off'
              : String(t.currentValue ?? ' - '),
            t.consentRelevant ? 'shield' : undefined,
          ),
      );
      for (const [i, t] of leg.toggles.entries()) {
        children[i].tooltip = t.description;
      }
      const row = new Row(
        leg.label,
        STATE_WORDS[leg.state],
        STATE_ICONS[leg.state],
        children.length
          ? vscode.TreeItemCollapsibleState.Collapsed
          : vscode.TreeItemCollapsibleState.None,
        children,
      );
      row.tooltip = leg.description;
      rows.push(row);
    }
    return rows;
  }

  /** The count the container badge shows: legs actually recording. */
  activeCount(): number {
    return activeLegCount(this.legs());
  }
}

/** View 3  -  Data. Where it goes, and whether any of it went missing. */
export class DataView extends BaseProvider {
  constructor(private readonly probe: SessionProbe) {
    super();
  }

  protected roots(): Row[] {
    const s = this.probe();
    const conf = vscode.workspace.getConfiguration('tern');
    const endpoint = conf.get<string>('output.httpEndpoint');
    const rows: Row[] = [
      new Row(
        'Stored on this machine',
        s.dataFile ?? conf.get<string>('output.directory') ?? '.study-data',
        'folder',
      ),
      new Row(
        'Sent to the study server',
        endpoint ? endpoint : 'not connected  -  local only',
        endpoint ? 'cloud-upload' : 'circle-slash',
      ),
    ];
    if (s.active && s.written !== undefined) {
      const missing = s.written - (s.mirrored ?? 0);
      rows.push(
        new Row(
          'Events this session',
          missing > 0
            ? `${s.written} recorded, ${missing} not yet sent`
            : `${s.written} recorded`,
          missing > 0 ? 'warning' : 'check',
        ),
      );
    }
    rows.push(
      new Row('Open the data folder', undefined, 'go-to-file').runs(
        'tern.openDataFolder',
        'Open data folder',
      ),
    );
    return rows;
  }
}

/** Register all three views. Returns a refresh callback the session lifecycle
 *  calls; the sidebar never polls. */
export function registerSidebar(
  context: vscode.ExtensionContext,
  probe: SessionProbe,
): { refresh: () => void; dispose: () => void } {
  const session = new SessionView(probe, context);
  const capture = new CaptureView(context);
  const data = new DataView(probe);

  const trees = [
    vscode.window.createTreeView('tern.session', { treeDataProvider: session }),
    vscode.window.createTreeView('tern.capture', { treeDataProvider: capture }),
    vscode.window.createTreeView('tern.data', { treeDataProvider: data }),
  ];

  const refresh = (): void => {
    session.refresh();
    capture.refresh();
    data.refresh();
    const n = capture.activeCount();
    // The badge answers "is anything recording?" without opening the view.
    trees[1].badge = n
      ? { value: n, tooltip: `${n} of 4 legs recording` }
      : undefined;
  };

  refresh();
  return {
    refresh,
    dispose: () => trees.forEach((t) => t.dispose()),
  };
}
