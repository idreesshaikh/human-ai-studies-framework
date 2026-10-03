export type ProbeState = 'idle' | 'chunk-accepted' | 'probe-pending';

export type ProbeKind = 'predict-output' | 'locate-change';

export interface ChunkReference {
  editBurstId: string;

  agentTool?: string;

  agentModelId?: string;
}

export interface ChunkMeta {
  editBurstId: string;
  file: string;
  linesTouched: number;
  charsAdded: number;

  language?: string;
}

export interface ProbeDescriptor {
  promptKind: ProbeKind;

  timeboxMs: number;
}

export interface ProbeResponse {
  chunkRef: ChunkReference;
  promptKind: ProbeKind;

  answer?: string;

  correct?: boolean | null;
  msToAnswer: number;
  expired: boolean;
}

export interface ComprehensionProbeConfig {
  enabled: boolean;
  cadence: 'every-chunk' | 'sampled';

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
  onProbe: (
    meta: ChunkMeta,
    descriptor: ProbeDescriptor,
    chunkRef: ChunkReference,
  ) => void;

  onProbeResponse: (response: ProbeResponse) => void;
}

interface ActiveProbe {
  meta: ChunkMeta;
  descriptor: ProbeDescriptor;
  chunkRef: ChunkReference;
  startedAt: number;
}

let _nextBurstId = 0;

export function nextBurstId(): number {
  return ++_nextBurstId;
}

export function resetBurstId(): void {
  _nextBurstId = 0;
}

export function predictOutput(meta: ChunkMeta): ProbeDescriptor | null {
  if (meta.linesTouched < 2) return null;
  return { promptKind: 'predict-output', timeboxMs: 30_000 };
}

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

  cancelProbe(): void {
    this.active_ = undefined;
    this._state = 'idle';
  }

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

  dispose(): void {
    this.cancelProbe();
  }

  private shouldSample(): boolean {
    if (this.config.cadence === 'every-chunk') return true;
    const rate = this.config.sampleRate > 0 ? this.config.sampleRate : 1;
    const divisor = Math.round(1 / rate);
    return divisor <= 1 || this.burstCount % divisor === 0;
  }

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
