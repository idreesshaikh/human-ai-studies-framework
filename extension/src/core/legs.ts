export const LEG_IDS = ['metrics', 'behavioral', 'cognitive', 'agent'] as const;

export type LegId = (typeof LEG_IDS)[number];

export type LegState = 'enabled' | 'disabled' | 'unavailable';

export interface LegToggle {
  label: string;
  description: string;

  consentRelevant: boolean;
  currentValue: unknown;
}

export interface Leg {
  id: LegId;
  label: string;
  description: string;
  state: LegState;
  toggles: LegToggle[];
}

const FALLBACK: Record<LegId, { label: string; description: string }> = {
  metrics: {
    label: 'Static metrics',
    description: 'Measures the shape of the code you produce.',
  },
  behavioral: {
    label: 'Behavioral',
    description: 'Records what you did in the editor  -  never what you wrote.',
  },
  cognitive: {
    label: 'Cognitive',
    description: 'Asks how you are finding the work, in short probes.',
  },
  agent: {
    label: 'Agent interaction',
    description: 'Records your coding-agent turns on the same timeline.',
  },
};

const CONSENT_RELEVANT_TAILS = [
  'snapshot.enabled',
  'captureWorkspaceSnapshots',
];

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v);
}

function readToggle(raw: unknown): LegToggle | undefined {
  if (!isRecord(raw)) return undefined;
  const label = raw['label'];
  const description = raw['description'];
  if (typeof label !== 'string' || typeof description !== 'string') {
    return undefined;
  }
  const path = Array.isArray(raw['path']) ? raw['path'].join('.') : '';
  return {
    label,
    description,
    consentRelevant: CONSENT_RELEVANT_TAILS.some((tail) => path.endsWith(tail)),
    currentValue: raw['currentValue'],
  };
}

function readState(raw: unknown): LegState {
  return raw === 'enabled' || raw === 'disabled' ? raw : 'unavailable';
}

export function readLegs(cfg: CaptureConfigLike | undefined): Leg[] {
  const summaries = new Map<string, Record<string, unknown>>();
  if (cfg && Array.isArray(cfg.legs)) {
    for (const entry of cfg.legs) {
      if (isRecord(entry) && typeof entry['leg'] === 'string') {
        summaries.set(entry['leg'], entry);
      }
    }
  }

  return LEG_IDS.map((id) => {
    const summary = summaries.get(id);
    if (!summary) {
      return {
        id,
        label: FALLBACK[id].label,
        description: FALLBACK[id].description,
        state: 'unavailable' as const,
        toggles: [],
      };
    }
    const toggles = Array.isArray(summary['toggles'])
      ? summary['toggles']
          .map(readToggle)
          .filter((t): t is LegToggle => t !== undefined)
      : [];
    return {
      id,
      label:
        typeof summary['label'] === 'string'
          ? summary['label']
          : FALLBACK[id].label,
      description:
        typeof summary['description'] === 'string'
          ? summary['description']
          : FALLBACK[id].description,
      state: readState(summary['state']),
      toggles,
    };
  });
}

export interface CaptureConfigLike {
  legs?: unknown;
}

export function activeLegCount(legs: Leg[]): number {
  return legs.filter((l) => l.state === 'enabled').length;
}

export function capturesContent(legs: Leg[]): boolean {
  return legs.some(
    (leg) =>
      leg.state === 'enabled' &&
      leg.toggles.some((t) => t.consentRelevant && t.currentValue === true),
  );
}
