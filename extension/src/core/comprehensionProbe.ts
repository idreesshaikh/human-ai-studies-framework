/**
 * Comprehension-probe state machine  -  vscode-free, injected clock (NFR-3).
 *
 * Satisfies FR-INST-19 (comprehension probes for accepted AI chunks) and
 * FR-DASH-12 (protocol-configured cadence). The machine transitions:
 *   idle → chunk-accepted → probe-pending → answered | expired
 *
 * An external caller (the adapter layer, via behavior.ts burst signals)
 * determines *when* a chunk is truly accepted (survived the undo window)
 * and calls acceptChunk(). The machine handles sampling, probe-type
 * selection, metadata sufficiency, and the answer/timeout lifecycle.
 *
 * NEVER captures, logs, or transmits code content (FR-ETH-2).
 */

export type ProbeState = 'idle' | 'chunk-accepted' | 'probe-pending';

export type ProbeKind = 'predict-output' | 'locate-change';

export interface ChunkReference {
  /** The edit-burst id this probe joins back to. */
  editBurstId: string;
  /** Which agent tool produced the chunk (e.g. 'claude-code'). */
  agentTool?: string;
  /** The model id that produced the chunk (e.g. 'claude-sonnet-4-20250514'). */
  agentModelId?: string;
}

/**
 * Chunk metadata  -  only what FR-ETH-2 permits: shapes, sizes, and a
 * stable reference. NEVER code text.
 */
export interface ChunkMeta {
  editBurstId: string;
  file: string;
  linesTouched: number;
  charsAdded: number;
  /** Language inferred from file extension (never code text). */
  language?: string;
}

export interface ProbeDescriptor {
  promptKind: ProbeKind;
  /** Maximum time (ms) the probe will wait for an answer before expiring. */
  timeboxMs: number;
}

export interface ProbeResponse {
  chunkRef: ChunkReference;
  promptKind: ProbeKind;
  /** The participant's free-text answer (null on timeout/expiry). */
  answer?: string;
  /** Whether the answer was correct (probe-type-dependent, nullable). */
  correct?: boolean | null;
  msToAnswer: number;
  expired: boolean;
}

export interface ComprehensionProbeConfig {
  enabled: boolean;
  cadence: 'every-chunk' | 'sampled';
  /** Fraction of chunks to probe (0–1, only meaningful when cadence is
   *  sampled). Defaults to 1 (probe every eligible chunk when cadence is
   *  every-chunk). */
  sampleRate: number;
  probeTypes: ProbeKind[];
}

export const DEFAULT_COMPREHENSION_PROBE_CONFIG: ComprehensionProbeConfig = {
  enabled: true,
  cadence: 'every-chunk',
  sampleRate: 1,
  probeTypes: ['predict-output', 'locate-change'],
};

export interface ProbeCallbacks {
  /** Fired when a probe is ready to be shown (probe-pending → adapter). */
  onProbe: (
    meta: ChunkMeta,
    descriptor: ProbeDescriptor,
    chunkRef: ChunkReference,
  ) => void;
  /** Fired when a probe is answered or expires. */
  onProbeResponse: (response: ProbeResponse) => void;
}

/** Internal state of an active probe. Timer managed by the adapter. */
interface ActiveProbe {
  meta: ChunkMeta;
  descriptor: ProbeDescriptor;
  chunkRef: ChunkReference;
  startedAt: number;
}

let _nextBurstId = 0;

/** Deterministic burst counter (monotonic, never resets). */
export function nextBurstId(): number {
  return ++_nextBurstId;
}

export function resetBurstId(): void {
  _nextBurstId = 0;
}

/**
 * Pure function: produce a predict-output probe descriptor from chunk
 * metadata. Returns null if the chunk is too small for a meaningful probe.
 */
export function predictOutput(meta: ChunkMeta): ProbeDescriptor | null {
  if (meta.linesTouched < 2) return null;
  return { promptKind: 'predict-output', timeboxMs: 30_000 };
}

/**
 * Pure function: produce a locate-change probe descriptor from chunk
 * metadata. Returns null if the chunk is too small for a meaningful probe.
 */
export function locateChange(meta: ChunkMeta): ProbeDescriptor | null {
  if (meta.linesTouched < 2) return null;
  return { promptKind: 'locate-change', timeboxMs: 30_000 };
}

const PROBE_GENERATORS: Record<
  ProbeKind,
  (meta: ChunkMeta) => ProbeDescriptor | null
> = {
  'predict-output': predictOutput,
  'locate-change': locateChange,
};

export interface Disposable {
  dispose(): void;
}

/**
 * Comprehension-probe state machine.
 *
 * Thread-safe assumptions: all calls are serialised from a single event
 * loop (no locking needed).
 */
export class ComprehensionProbeMachine implements Disposable {
  private _state: ProbeState = 'idle';
  private active_: ActiveProbe | undefined;
  private burstCount = 0;

  constructor(
    private readonly config: ComprehensionProbeConfig,
    private readonly callbacks: ProbeCallbacks,
    private readonly clock: () => number = Date.now,
  ) {}

  get state(): ProbeState {
    return this._state;
  }

  /**
   * Signal that an AI-produced chunk was accepted (survived the undo window).
   *
   * Transitions: idle → chunk-accepted. If sampling and metadata checks
   * pass, immediately transitions to probe-pending and fires onProbe.
   */
  acceptChunk(meta: ChunkMeta, chunkRef: ChunkReference): void {
    if (this._state !== 'idle') return;
    if (!this.config.enabled) return;

    this._state = 'chunk-accepted';
    this.burstCount++;

    if (!this.shouldSample()) {
      this._state = 'idle';
      return;
    }

    const descriptor = this.pickProbeType(meta);
    if (!descriptor) {
      this._state = 'idle';
      return;
    }

    this._state = 'probe-pending';
    this.active_ = {
      meta,
      descriptor,
      chunkRef,
      startedAt: this.clock(),
    };
    this.callbacks.onProbe(meta, descriptor, chunkRef);
  }

  /**
   * Cancel a pending probe (chunk was undone or superseded before the probe
   * was answered/expired). Safe to call in any state.
   */
  cancelProbe(): void {
    this.active_ = undefined;
    this._state = 'idle';
  }

  /**
   * Record an answer to the active probe.
   *
   * Transitions: probe-pending → idle, fires onProbeResponse.
   */
  answer(answer: string, correct?: boolean | null): void {
    const a = this.active_;
    if (!a) return;
    this.active_ = undefined;
    this._state = 'idle';
    this.callbacks.onProbeResponse({
      chunkRef: a.chunkRef,
      promptKind: a.descriptor.promptKind,
      answer,
      correct: correct ?? null,
      msToAnswer: this.clock() - a.startedAt,
      expired: false,
    });
  }

  /**
   * Expire the active probe (called by the adapter's timeout).
   *
   * Transitions: probe-pending → idle, fires onProbeResponse with expired:true.
   */
  expire(): void {
    const a = this.active_;
    if (!a || this._state !== 'probe-pending') return;
    this.active_ = undefined;
    this._state = 'idle';
    this.callbacks.onProbeResponse({
      chunkRef: a.chunkRef,
      promptKind: a.descriptor.promptKind,
      msToAnswer: this.clock() - a.startedAt,
      expired: true,
    });
  }

  /**
   * Dispose of the machine, cancelling any active probe.
   */
  dispose(): void {
    this.cancelProbe();
  }

  /** Sampling decision: should this chunk produce a probe? */
  private shouldSample(): boolean {
    if (this.config.cadence === 'every-chunk') return true;
    const rate = this.config.sampleRate > 0 ? this.config.sampleRate : 1;
    const divisor = Math.round(1 / rate);
    return divisor <= 1 || this.burstCount % divisor === 0;
  }

  /** Pick the first configured probe type that can generate a descriptor
   *  for the given metadata. Returns null if none apply. */
  private pickProbeType(meta: ChunkMeta): ProbeDescriptor | null {
    for (const kind of this.config.probeTypes) {
      const gen = PROBE_GENERATORS[kind];
      if (!gen) continue;
      const descriptor = gen(meta);
      if (descriptor) return descriptor;
    }
    return null;
  }
}
