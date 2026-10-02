import * as vscode from 'vscode';
import {
  readLegs,
  activeLegCount,
  capturesContent,
  Leg,
  LegState,
} from '../core/legs';
import { SessionBlock } from '../core/captureConfig';
import {
  pairingState,
  STATE_BLOCK,
  STATE_LEGS,
  STATE_PAIRED,
  STATE_PENDING,
} from './pairing';

export interface SidebarSession {
  active: boolean;

  ending?: boolean;
  paused: boolean;
  participantId?: string;
  dataFile?: string;

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

class Row extends vscode.TreeItem {
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

export class SessionView extends BaseProvider {
  constructor(
    private readonly probe: SessionProbe,
    private readonly context: vscode.ExtensionContext,
  ) {
    super();
  }

  private block(): SessionBlock | undefined {
    return pairingState<SessionBlock>(this.context, STATE_BLOCK);
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
          ? [new Row('Participant', s.participantId, 'account')]
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
      rows.push(new Row('Participant', s.participantId, 'account'));
    }

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

export class CaptureView extends BaseProvider {
  constructor(private readonly context: vscode.ExtensionContext) {
    super();
  }

  private legs(): Leg[] {
    return readLegs({ legs: pairingState(this.context, STATE_LEGS) });
  }

  protected roots(): Row[] {
    const legs = this.legs();
    const pending = pairingState<string>(this.context, STATE_PENDING);
    const paired = pairingState<boolean>(this.context, STATE_PAIRED);
    const rows: Row[] = [];

    if (legs.every((l) => l.state === 'unavailable')) {
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

    if (paired) {
      rows.push(
        new Row('Study capture', 'Configured by the researcher', 'shield'),
      );
      for (const leg of legs.filter((leg) => leg.state === 'enabled')) {
        rows.push(new Row(leg.label, 'Active for this study', 'check'));
      }
      return rows;
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

  activeCount(): number {
    return activeLegCount(this.legs());
  }
}

export class DataView extends BaseProvider {
  constructor(
    private readonly probe: SessionProbe,
    private readonly context: vscode.ExtensionContext,
  ) {
    super();
  }

  protected roots(): Row[] {
    const s = this.probe();
    if (pairingState<boolean>(this.context, STATE_PAIRED)) {
      const rows: Row[] = [
        new Row('Study data', 'Managed by the researcher', 'shield'),
        new Row('Sent to study server', 'Connected', 'cloud-upload'),
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
      return rows;
    }
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

export function registerSidebar(
  context: vscode.ExtensionContext,
  probe: SessionProbe,
): { refresh: () => void; dispose: () => void } {
  const session = new SessionView(probe, context);
  const capture = new CaptureView(context);
  const data = new DataView(probe, context);

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
