import * as os from 'os';
import * as path from 'path';
import * as vscode from 'vscode';
import { EditBurst } from '../core/behavior';
import { Recorder } from '../core/recorder';
import { newSessionId, StudySession } from '../core/session';
import { DEFAULT_STUCK_CONFIG, StuckDetector } from '../core/stuckDetector';
import { FATIGUE_ITEM } from '../core/surveys';
import {
  EditorSignal,
  EventSink,
  SCHEMA_VERSION,
  SessionSnapshot,
  StuckAnswer,
  StuckRegion,
  StudyCondition,
} from '../core/types';
import {
  BehaviorCapture,
  environmentSnapshotPayload,
  registerBehaviorCommands,
} from './behavior';
import { ComprehensionProbeMachine } from '../core/comprehensionProbe';
import { ComprehensionPromptController } from './comprehensionPrompt';
import { showEndSurvey } from './endSurvey';
import { LikertPromptHandle, showLikertQuickPick } from './fatiguePrompt';
import { VscodeIdeHealthAdapter } from './ideHealth';
import {
  getStoredCredential,
  getPairedIdentity,
  enforcePairedSettings,
  pairingState,
  pairFromConnectionString,
  registerPairing,
  refreshConfigAtSessionStart,
  STATE_BLOCK,
  STATE_MANIFEST,
} from './pairing';
import { preflightSummary } from '../core/preflight';
import { confirmPreflight } from './preflightPrompt';
import { wireEditorSignals } from './signals';
import { CompositeSink, HttpSink, JsonlSink } from './sinks';
import { SessionStatusBar } from './statusBar';
import { registerSidebar, SidebarSession } from './sidebar';
import { StuckPromptController } from './stuckPrompt';

const SNAPSHOT_KEY = 'tern.activeSession';

const SNAPSHOT_EVERY_TICKS = 15;

const RESUMPTION_LAG_MAX_MS = 5 * 60_000;

interface RunningStudy {
  session: StudySession;
  recorder: Recorder;
  sink: EventSink;

  httpSink?: HttpSink;
  detector: StuckDetector;
  stuckPrompt: StuckPromptController;
  behavior?: BehaviorCapture;
  comprehensionProbe?: ComprehensionProbeMachine;
  comprehensionPrompt?: ComprehensionPromptController;
  ideHealth?: VscodeIdeHealthAdapter;
  signalSub: vscode.Disposable;
  dataFile: string;
  fatiguePending: boolean;
  activeFatiguePrompt?: LikertPromptHandle;
  ending: boolean;
  ticksSinceSnapshot: number;

  awaitingResumption?: { promptType: string; closedAt: number };
  lastBlurAt?: number;
}

let statusBar: SessionStatusBar;
let sidebar: { refresh: () => void; dispose: () => void };
let study: RunningStudy | undefined;
let extContext: vscode.ExtensionContext;
let sinkErrorShown = false;

function sidebarSession(): SidebarSession {
  const s = study;
  if (!s) {
    return { active: false, paused: false };
  }
  const paired = getPairedIdentity(extContext);
  return {
    active: true,
    ending: s.ending,
    paused: s.session.paused,
    participantId:
      paired?.participantId ??
      vscode.workspace.getConfiguration('tern').get<string>('participantId'),
    dataFile: s.dataFile,
    written: s.recorder.nextSeq,
    mirrored: s.httpSink ? s.httpSink.deliveredCount : s.recorder.nextSeq,
  };
}

export function activate(context: vscode.ExtensionContext): void {
  extContext = context;
  statusBar = new SessionStatusBar();
  context.subscriptions.push(statusBar);

  sidebar = registerSidebar(context, sidebarSession);
  context.subscriptions.push({ dispose: () => sidebar.dispose() });
  const pairedOnActivation = getPairedIdentity(context);
  if (pairedOnActivation) void enforcePairedSettings(pairedOnActivation);

  context.subscriptions.push(
    vscode.commands.registerCommand('tern.startSession', () => startSession()),
    vscode.commands.registerCommand('tern.endSession', () =>
      endSession('manual'),
    ),
    vscode.commands.registerCommand('tern.pauseSession', pauseSession),
    vscode.commands.registerCommand('tern.resumeSession', resumeSession),
    vscode.commands.registerCommand('tern.logFatigueNow', () =>
      runFatiguePrompt('manual'),
    ),
    vscode.commands.registerCommand(
      'tern.respondStuck',
      (answer: StuckAnswer) => study?.stuckPrompt.resolve(answer),
    ),
    vscode.commands.registerCommand('tern.answerProbe', (kind: string) => {
      const s = study?.comprehensionPrompt;
      if (!s) return;
      void vscode.window
        .showInputBox({
          title: `Comprehension probe (${kind})`,
          prompt:
            kind === 'predict-output'
              ? 'What will this code print or return?'
              : 'Briefly describe which line changed the behavior',
          ignoreFocusOut: false,
        })
        .then((answer) => {
          if (answer !== undefined) s.resolveAnswer(answer);
        });
    }),
    vscode.commands.registerCommand('tern.skipProbe', () => {
      const s = study?.comprehensionPrompt;
      if (!s) return;
      s.resolveAnswer('');
    }),
    vscode.commands.registerCommand('tern.statusMenu', statusMenu),
    vscode.commands.registerCommand('tern.openDataFolder', openDataFolder),

    registerBehaviorCommands(() => study?.behavior),
    registerPairing(context, () => sidebar.refresh()),
    vscode.window.registerUriHandler({
      handleUri(uri: vscode.Uri) {
        const params = new URLSearchParams(uri.query);
        const c = params.get('c');
        if (uri.path === '/pair' && c)
          void pairFromConnectionString(context, c, () => sidebar.refresh());
      },
    }),
  );

  void offerCrashRecovery();
}

export function deactivate(): void {
  if (study) {
    study.session.dispose();
    teardownStudy(false);
  }
}

function cfg<T>(key: string, fallback: T): T {
  return vscode.workspace.getConfiguration('tern').get<T>(key, fallback);
}

function dataDirectory(): string {
  if (getPairedIdentity(extContext)) {
    return path.join(extContext.globalStorageUri.fsPath, 'study-data');
  }
  const configured = cfg('output.directory', '');
  if (configured) return configured;
  const ws = vscode.workspace.workspaceFolders?.[0];
  if (ws) return path.join(ws.uri.fsPath, '.study-data');
  return path.join(extContext.globalStorageUri.fsPath, 'study-data');
}

async function startSession(): Promise<void> {
  if (study) {
    void vscode.window.showWarningMessage(
      'A study session is already running. End it first.',
    );
    return;
  }

  const paired = getPairedIdentity(extContext);
  let participantId: string;
  let condition: StudyCondition;
  if (paired) {
    participantId = paired.participantId;
    condition = paired.condition as StudyCondition;
  } else {
    const enteredId = await vscode.window.showInputBox({
      title: 'Participant ID',
      prompt: 'Identifier for this participant (e.g. P07)',
      value: cfg('participantId', ''),
      ignoreFocusOut: true,
      validateInput: (v) =>
        v.trim() ? undefined : 'Participant ID is required',
    });
    if (!enteredId) return;
    participantId = enteredId.trim();

    const conditionPick = await vscode.window.showQuickPick(
      [
        {
          label: 'AI-assisted',
          description: 'Participant works with the AI agent/LLM',
          value: 'ai-assisted' as StudyCondition,
        },
        {
          label: 'Unassisted',
          description: 'Participant works without AI',
          value: 'unassisted' as StudyCondition,
        },
        { label: 'Unspecified', value: 'unspecified' as StudyCondition },
      ],
      { title: 'Study condition (A/B arm)', ignoreFocusOut: true },
    );
    if (!conditionPick) return;
    condition = conditionPick.value;
  }

  const durationMin = cfg('session.durationMinutes', 60);
  const sessionTag = `${participantId}_${new Date()
    .toISOString()
    .replace(/[:.]/g, '-')}`;
  const dataFile = path.join(dataDirectory(), `${sessionTag}.jsonl`);

  const preparedSessionId = paired ? '' : cfg('session.id', '').trim();
  const plannedSessionId = preparedSessionId || newSessionId();
  if (preparedSessionId) {
    await vscode.workspace
      .getConfiguration('tern')
      .update('session.id', '', vscode.ConfigurationTarget.Workspace);
  }

  const credential = await refreshConfigAtSessionStart(
    extContext,
    Boolean(study),
    plannedSessionId,
  );

  const wsCfg = vscode.workspace.getConfiguration('tern');
  const knownPreflightKeys = [
    'stuck.enabled',
    'behavior.captureEditBursts',
    'behavior.captureAiLifecycle',
    'behavior.captureClipboard',
    'behavior.captureVisibleRanges',
    'behavior.captureFocus',
    'behavior.captureHeartbeat',
    'behavior.captureAttention',
  ];
  const flags: Record<string, unknown> = {};
  for (const key of knownPreflightKeys) {
    const val = wsCfg.inspect<unknown>(key);
    flags[key] =
      val?.workspaceValue ?? val?.globalValue ?? val?.defaultValue ?? false;
  }
  const manifest = pairingState<Record<string, unknown>>(
    extContext,
    STATE_MANIFEST,
  );
  const items = preflightSummary(flags, manifest?.producers);
  const accepted = await confirmPreflight({
    participantId,
    durationMinutes: durationMin,
    capture: items.filter((i) => i.on).map((i) => i.label),
    notCaptured: items.filter((i) => !i.on).map((i) => i.label),
  });
  if (!accepted) return;

  bootSession({
    participantId,
    condition,
    dataFile,
    durationMs: durationMin * 60_000,
    fatigueIntervalMs: cfg('fatigue.intervalMinutes', 15) * 60_000,
    credential,
    plannedSessionId,
    taskId: pairingState<{ taskId?: string }>(extContext, STATE_BLOCK)?.taskId,
  });

  study!.recorder.record('session_start', {
    plannedDurationMin: durationMin,
    fatigueIntervalMin: cfg('fatigue.intervalMinutes', 15),
    fatigueJitterPercent: cfg('fatigue.jitterPercent', 20),
    ide: 'vscode',
    ideVersion: vscode.version,
    extensionVersion: extContext.extension.packageJSON.version,
    platform: os.platform(),
    workspace: vscode.workspace.workspaceFolders?.[0]?.name ?? null,
  });
  study!.recorder.record('environment_snapshot', {
    ...environmentSnapshotPayload(
      extContext,
      `${os.platform()} ${os.release()}`,
    ),

    captureConfigVersion:
      pairingState<string>(extContext, 'tern.captureConfigVersion') ?? '',
  });
  persistSnapshot();

  void vscode.window.showInformationMessage(
    `Study session started for ${durationMin} minutes. ` +
      'You can forget about it now - the timer lives in the status bar.',
  );
}

interface BootConfig {
  participantId: string;
  condition: StudyCondition;
  dataFile: string;
  durationMs: number;
  fatigueIntervalMs: number;

  credential?: string;

  plannedSessionId?: string;
  taskId?: string;
  restore?: {
    sessionId: string;
    startedAtEpochMs: number;
    pausedMsAccumulated: number;
    startSeq: number;
  };
}

function bootSession(boot: BootConfig): void {
  const sinks: EventSink[] = [
    new JsonlSink(boot.dataFile, (err) => reportSinkError(err)),
  ];
  const endpoint = cfg('output.httpEndpoint', '');
  if (endpoint) sinks.push(new HttpSink(endpoint, undefined, boot.credential));
  const sink = new CompositeSink(sinks);

  const detector = new StuckDetector(
    {
      ...DEFAULT_STUCK_CONFIG,
      stuckAfterMs: cfg('stuck.thresholdSeconds', 90) * 1000,
      cooldownMs: cfg('stuck.cooldownMinutes', 5) * 60_000,
    },
    (region) => {
      if (!study || study.ending || study.session.paused) return;
      study.recorder.record('stuck_detected', { ...region });
      study.stuckPrompt.show(region);
      detector.notePromptShown();
    },
  );

  const stuckPrompt = new StuckPromptController((res) =>
    onStuckResolved(res.answer, res.msToAnswer, res.region),
  );

  const comprehensionProbeEnabled = cfg('comprehensionProbe.enabled', false);
  let comprehensionProbe: ComprehensionProbeMachine | undefined;
  let comprehensionPrompt: ComprehensionPromptController | undefined;
  if (comprehensionProbeEnabled) {
    comprehensionProbe = new ComprehensionProbeMachine(
      {
        enabled: true,
        cadence: cfg<'every-chunk' | 'sampled'>(
          'comprehensionProbe.cadence',
          'every-chunk',
        ),
        sampleRate: cfg('comprehensionProbe.sampleRate', 1),
        probeTypes: cfg<Array<'predict-output' | 'locate-change'>>(
          'comprehensionProbe.probeTypes',
          ['predict-output', 'locate-change'],
        ),
      },
      {
        onProbe: (meta, descriptor, chunkRef) => {
          if (!study || study.ending || study.session.paused) return;
          comprehensionPrompt?.show(meta, descriptor, chunkRef);
        },
        onProbeResponse: (response) => {
          if (!study || study.ending) return;
          study.recorder.record('comprehension_probe_response', {
            chunkRef: response.chunkRef,
            promptKind: response.promptKind,
            answer: response.answer ?? null,
            correct: response.correct ?? null,
            msToAnswer: response.msToAnswer,
            expired: response.expired,
          });
          armResumptionLag('comprehension');
        },
      },
    );
    comprehensionPrompt = new ComprehensionPromptController((response) => {
      const probe = study?.comprehensionProbe;
      if (!probe) return;
      if (response.expired || response.answer === '') {
        probe.expire();
      } else {
        probe.answer(response.answer ?? '');
      }
    });
  }

  let ideHealth: VscodeIdeHealthAdapter | undefined;
  if (cfg('ideHealth.enabled', false)) {
    ideHealth = new VscodeIdeHealthAdapter(
      { debounceMs: cfg('ideHealth.debounceSeconds', 10) * 1000 },
      (event) => {
        if (!study || study.ending || study.session.paused) return;
        study.recorder.record(event.type, {
          errorCount: event.errorCount,
          warningCount: event.warningCount,
          buildInvocations: event.buildInvocations,
          testInvocations: event.testInvocations,
        });
      },
    );
  }

  const session = new StudySession(
    {
      participantId: boot.participantId,
      condition: boot.condition,
      durationMs: boot.durationMs,
      fatigueIntervalMs: boot.fatigueIntervalMs,
      fatigueJitterRatio: cfg('fatigue.jitterPercent', 20) / 100,
      fatigueQuietTailMs: cfg('fatigue.quietTailMinutes', 5) * 60_000,
    },
    {
      onFatigueDue: () => void runFatiguePrompt('scheduled'),
      onEnded: (reason) => void finishStudy(reason),
      onTick: (remaining) => onTick(remaining),
    },
    boot.restore,

    boot.plannedSessionId,
  );

  const recorder = new Recorder(
    sink,
    {
      sessionId: session.id,
      participantId: boot.participantId,
      condition: boot.condition,
      taskId: boot.taskId ?? cfg('session.taskId', ''),
    },
    {
      startSeq: boot.restore ? boot.restore.startSeq : 0,
      monoOffsetMs: boot.restore ? session.elapsedMs : 0,
      onSinkError: (err) => reportSinkError(err),
    },
  );

  study = {
    session,
    recorder,
    sink,
    detector,
    stuckPrompt,
    comprehensionProbe,
    comprehensionPrompt,
    ideHealth,
    signalSub: wireEditorSignals(
      detector,
      cfg('stuck.languages', [] as string[]),
      onEditorSignal,
    ),
    dataFile: boot.dataFile,
    fatiguePending: false,
    ending: false,
    ticksSinceSnapshot: 0,
  };

  if (cfg('stuck.enabled', true)) detector.start();

  if (cfg('behavior.enabled', true)) {
    const behavior = new BehaviorCapture({
      record: (type, payload) => {
        const cur = study;
        if (!cur || cur.ending || cur.session.paused) return;
        cur.recorder.record(type, payload);

        if (
          type === 'edit_burst' &&
          payload.origin === 'ai' &&
          cur.comprehensionProbe
        ) {
          const burst = payload as unknown as EditBurst & {
            editBurstId?: string;
          };
          const burstId = burst.editBurstId ?? `burst_${Date.now()}`;
          const language =
            typeof burst.file === 'string'
              ? (burst.file.split('.').pop() ?? undefined)
              : undefined;
          cur.comprehensionProbe.acceptChunk(
            {
              editBurstId: burstId,
              file: burst.file ?? '',
              linesTouched: burst.linesTouched ?? 0,
              charsAdded: burst.charsAdded ?? 0,
              language,
            },
            {
              editBurstId: burstId,
              agentTool: cfg('session.agentTool', undefined) || undefined,
              agentModelId: cfg('session.agentModelId', undefined) || undefined,
            },
          );
        }
      },
    });
    study.behavior = behavior;
    behavior.start();
  }
  void vscode.commands.executeCommand('setContext', 'tern.sessionActive', true);

  statusBar.tick(session.remainingMs);
  sidebar.refresh();
}

function onTick(remaining: number): void {
  const s = study;
  if (!s) return;
  if (s.session.paused) {
    statusBar.paused(remaining);
  } else {
    statusBar.tick(remaining);
  }

  if (++s.ticksSinceSnapshot >= SNAPSHOT_EVERY_TICKS) {
    s.ticksSinceSnapshot = 0;
    persistSnapshot();
  }
}

async function finishStudy(reason: 'elapsed' | 'manual'): Promise<void> {
  const s = study;
  if (!s || s.ending) return;

  s.behavior?.pause('session-end');
  s.ending = true;
  statusBar.debrief();
  sidebar.refresh();

  s.detector.stop();
  s.stuckPrompt.resolve('dismissed');
  s.activeFatiguePrompt?.cancel();

  s.recorder.record('session_timer_ended', {
    reason,
    actualDurationMs: s.session.elapsedMs,
    pausedMs: s.session.pausedMsAccumulated,
  });

  const survey = await showEndSurvey();
  if (survey) {
    s.recorder.record('end_survey_response', { ...survey });
  } else {
    s.recorder.record('end_survey_skipped', {});
  }

  s.recorder.record('session_end', { reason });
  await s.recorder.flush();

  const file = s.dataFile;
  await clearSnapshot();
  teardownStudy(true);

  void vscode.window
    .showInformationMessage(
      `Study session complete - data saved to ${path.basename(file)}.`,
      'Open Data Folder',
    )
    .then((choice) => {
      if (choice) void openDataFolder();
    });
}

function endSession(reason: 'manual'): void {
  if (!study) {
    void vscode.window.showInformationMessage('No study session is running.');
    return;
  }
  study.session.end(reason);
}

function pauseSession(): void {
  const s = study;
  if (!s || s.ending || s.session.paused) return;

  s.behavior?.pause('session-pause');
  s.session.pause();
  s.detector.stop();
  s.activeFatiguePrompt?.cancel();
  s.stuckPrompt.resolve('dismissed');
  s.comprehensionProbe?.cancelProbe();
  s.comprehensionPrompt?.cancel();
  s.recorder.record('session_paused', {
    minutesIntoSession: minutesIntoSession(),
  });
  persistSnapshot();
  statusBar.paused(s.session.remainingMs);
  sidebar.refresh();
}

function resumeSession(): void {
  const s = study;
  if (!s || s.ending || !s.session.paused) return;
  const thisPauseMs = s.session.resume();
  if (cfg('stuck.enabled', true)) s.detector.start();
  s.behavior?.resume();
  s.recorder.record('session_resumed', {
    cause: 'manual',
    totalPausedMs: s.session.pausedMsAccumulated,
    thisPauseMs,
  });
  persistSnapshot();
  statusBar.tick(s.session.remainingMs);
  sidebar.refresh();
}

function teardownStudy(resetStatusBar: boolean): void {
  if (!study) return;
  study.behavior?.dispose();
  study.comprehensionProbe?.dispose();
  study.comprehensionPrompt?.dispose();
  study.ideHealth?.dispose();
  study.signalSub.dispose();
  study.detector.dispose();
  study.stuckPrompt.dispose();
  study.session.dispose();
  study.sink.dispose();
  study = undefined;
  void vscode.commands.executeCommand(
    'setContext',
    'tern.sessionActive',
    false,
  );
  if (resetStatusBar) statusBar.idle();
  sidebar.refresh();
}

function persistSnapshot(): void {
  const s = study;
  if (!s || s.ending) return;
  const snapshot: SessionSnapshot & { savedAtEpochMs: number } = {
    schemaVersion: SCHEMA_VERSION,
    sessionId: s.session.id,
    participantId: s.session.cfg.participantId,
    condition: s.session.cfg.condition,
    startedAtEpochMs: s.session.startedAt,
    plannedDurationMs: s.session.cfg.durationMs,
    fatigueIntervalMs: s.session.cfg.fatigueIntervalMs,
    pausedMsAccumulated: s.session.pausedMsAccumulated,
    dataFile: s.dataFile,
    savedAtEpochMs: Date.now(),
  };
  void extContext.workspaceState.update(SNAPSHOT_KEY, snapshot);
}

async function clearSnapshot(): Promise<void> {
  await extContext.workspaceState.update(SNAPSHOT_KEY, undefined);
}

function isRestorableSnapshot(
  snap: SessionSnapshot & { savedAtEpochMs: number },
): boolean {
  if (snap.schemaVersion > SCHEMA_VERSION) return false;
  return (
    typeof snap.sessionId === 'string' &&
    snap.sessionId.length > 0 &&
    typeof snap.dataFile === 'string' &&
    snap.dataFile.length > 0 &&
    Number.isFinite(snap.startedAtEpochMs) &&
    Number.isFinite(snap.plannedDurationMs) &&
    Number.isFinite(snap.fatigueIntervalMs) &&
    Number.isFinite(snap.pausedMsAccumulated) &&
    Number.isFinite(snap.savedAtEpochMs)
  );
}

async function offerCrashRecovery(): Promise<void> {
  const snap = extContext.workspaceState.get<
    SessionSnapshot & { savedAtEpochMs: number }
  >(SNAPSHOT_KEY);
  if (!snap) return;

  if (!isRestorableSnapshot(snap)) {
    await clearSnapshot();
    return;
  }

  const choice = await vscode.window.showWarningMessage(
    `An interrupted study session for ${snap.participantId} was found ` +
      '(the IDE closed mid-session). Resume it?',
    { modal: false },
    'Resume session',
    'Discard',
  );
  if (choice === 'Discard' || choice === undefined) {
    await clearSnapshot();
    return;
  }

  const gapMs = Math.max(0, Date.now() - snap.savedAtEpochMs);
  const startSeq = JsonlSink.lastSeqIn(snap.dataFile) + 1;

  const credential = await getStoredCredential(extContext);

  bootSession({
    participantId: snap.participantId,
    condition: snap.condition,
    dataFile: snap.dataFile,
    durationMs: snap.plannedDurationMs,
    fatigueIntervalMs: snap.fatigueIntervalMs,
    credential,
    restore: {
      sessionId: snap.sessionId,
      startedAtEpochMs: snap.startedAtEpochMs,

      pausedMsAccumulated: snap.pausedMsAccumulated + gapMs,
      startSeq,
    },
  });

  study!.recorder.record('session_resumed', {
    cause: 'crash-recovery',
    downtimeMs: gapMs,
    totalPausedMs: study!.session.pausedMsAccumulated,
  });
  persistSnapshot();
}

function onEditorSignal(signal: EditorSignal): void {
  const s = study;
  if (!s || s.ending) return;

  switch (signal.kind) {
    case 'blur':
      s.lastBlurAt = signal.at;
      s.recorder.record('window_blur', {
        minutesIntoSession: minutesIntoSession(),
      });
      break;
    case 'focus':
      s.recorder.record('window_focus', {
        awayMs: s.lastBlurAt ? signal.at - s.lastBlurAt : null,
        minutesIntoSession: minutesIntoSession(),
      });
      s.lastBlurAt = undefined;
      break;
    case 'edit': {
      const waiting = s.awaitingResumption;
      if (waiting) {
        s.awaitingResumption = undefined;
        const lagMs = signal.at - waiting.closedAt;
        if (lagMs <= RESUMPTION_LAG_MAX_MS) {
          s.recorder.record('post_prompt_resumption', {
            promptType: waiting.promptType,
            lagMs,
          });
        }
      }
      break;
    }
  }
}

function armResumptionLag(promptType: string): void {
  if (!study || study.ending) return;
  study.awaitingResumption = { promptType, closedAt: Date.now() };
}

function onStuckResolved(
  answer: StuckAnswer,
  msToAnswer: number,
  region: StuckRegion,
): void {
  if (!study) return;
  study.recorder.record('stuck_response', { answer, msToAnswer, region });
  study.detector.notePromptShown();
  armResumptionLag('stuck');
  if (answer === 'hint') {
    study.recorder.record('hint_requested', { region });
    void vscode.window.showInformationMessage(
      'Hint request logged - the study facilitator has been notified.',
    );
  }
}

async function runFatiguePrompt(
  trigger: 'scheduled' | 'manual',
): Promise<void> {
  const s = study;
  if (!s || s.ending || s.fatiguePending || s.session.paused) return;
  s.fatiguePending = true;
  statusBar.attention(true);
  const dueAt = Date.now();

  try {
    if (trigger === 'scheduled') {
      const pauseMs = cfg('fatigue.waitForPauseSeconds', 4) * 1000;
      const deadline = Date.now() + 60_000;
      while (Date.now() < deadline) {
        const sinceEdit = Date.now() - s.detector.lastEditTime;
        if (sinceEdit >= pauseMs) break;
        await delay(1000);
        if (!study || study.ending || study.session.paused) return;
      }
    } else {
      s.session.deferNextFatigue();
    }

    const deferralMs = Date.now() - dueAt;
    s.recorder.record('fatigue_prompt_shown', { trigger, deferralMs });
    s.detector.notePromptShown();
    const handle = showLikertQuickPick(FATIGUE_ITEM);
    s.activeFatiguePrompt = handle;
    const result = await handle.result;
    s.activeFatiguePrompt = undefined;
    s.recorder.record('fatigue_response', {
      trigger,
      scaleId: FATIGUE_ITEM.id,
      points: FATIGUE_ITEM.points,
      value: result.value,
      skipped: result.skipped,
      cancelled: result.cancelled,
      msToAnswer: result.msToAnswer,
      deferralMs,
      minutesIntoSession: minutesIntoSession(),
    });
    if (!result.cancelled) armResumptionLag('fatigue');
  } finally {
    s.fatiguePending = false;
    s.activeFatiguePrompt = undefined;
    statusBar.attention(false);
  }
}

async function statusMenu(): Promise<void> {
  if (!study) {
    await startSession();
    return;
  }
  const paused = study.session.paused;
  const items = [
    paused
      ? {
          label: '$(debug-start) Resume session (break over)',
          action: 'resume',
        }
      : { label: '$(debug-pause) Pause session (break)', action: 'pause' },
    { label: '$(pulse) Log fatigue now', action: 'fatigue' },
    { label: '$(debug-stop) End study session', action: 'end' },
  ];
  if (!getPairedIdentity(extContext)) {
    items.splice(2, 0, {
      label: '$(folder-opened) Open data folder',
      action: 'data',
    });
  }
  const pick = await vscode.window.showQuickPick(items, {
    title: 'TERN - session menu',
  });
  if (pick?.action === 'pause') pauseSession();
  if (pick?.action === 'resume') resumeSession();
  if (pick?.action === 'fatigue') void runFatiguePrompt('manual');
  if (pick?.action === 'data') void openDataFolder();
  if (pick?.action === 'end') endSession('manual');
}

async function openDataFolder(): Promise<void> {
  if (getPairedIdentity(extContext)) {
    void vscode.window.showInformationMessage(
      'Study data is managed by the researcher and the study server.',
    );
    return;
  }
  await vscode.env.openExternal(vscode.Uri.file(dataDirectory()));
}

function minutesIntoSession(): number {
  return study ? Math.round(study.session.elapsedMs / 60_000) : 0;
}

function reportSinkError(err: unknown): void {
  if (sinkErrorShown) return;
  sinkErrorShown = true;
  void vscode.window.showErrorMessage(
    `TERN: a data write failed (${String(err)}). ` +
      'The extension switched to a fallback write path - check disk space ' +
      'and the data folder before the next session.',
  );
}

function delay(ms: number): Promise<void> {
  return new Promise((r) => setTimeout(r, ms));
}
