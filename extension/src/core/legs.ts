/**
 * The four instrument legs, as the participant sees them (FR-INST-22).
 *
 * Portable core: this module only shapes the data — rendering it in a tree
 * view is the adapter's job, and nothing here imports `vscode`.
 *
 * The display state comes from the middleware's `leg_summary` (FR-DASH-13),
 * carried on the capture config. The extension deliberately does not re-derive
 * what a leg captures from the flat `tern.*` settings: two of the four legs
 * (static metrics, agent interaction) live outside that subtree entirely, so a
 * locally-derived answer would be confidently wrong about half the study.
 *
 * The rule this module exists to enforce: **a leg is never hidden.** A
 * participant can only check the consent promise (FR-ETH-2) if they can see
 * what is *not* captured as well as what is, so all four legs always come
 * back, and "we don't know" is its own state rather than a silent "off".
 */

export const LEG_IDS = ['metrics', 'behavioral', 'cognitive', 'agent'] as const;

export type LegId = (typeof LEG_IDS)[number];

/**
 * `enabled` / `disabled` are claims about the study. `unavailable` is a claim
 * about *us*: either the protocol doesn't configure this leg, or we have no
 * capture config yet. Kept distinct from `disabled` on purpose — telling a
 * participant a leg is off when we simply haven't asked is the one failure
 * mode this surface must not have.
 */
export type LegState = 'enabled' | 'disabled' | 'unavailable';

export interface LegToggle {
  label: string;
  description: string;
  /** True when this toggle governs one of the two content-touching
   *  exceptions to privacy-by-construction (FR-ETH-2) — the surface badges
   *  these so a snapshot setting never reads like a debounce setting. */
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

/** Fallback copy, used only when the middleware sent no leg summary. Kept
 *  minimal and non-committal: it names the leg without claiming what this
 *  particular study captures, which is exactly what we don't know here. */
const FALLBACK: Record<LegId, { label: string; description: string }> = {
  metrics: {
    label: 'Static metrics',
    description: 'Measures the shape of the code you produce.',
  },
  behavioral: {
    label: 'Behavioral',
    description: 'Records what you did in the editor — never what you wrote.',
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

/** Toggle paths that reach actual code content (FR-ETH-2's two scoped
 *  exceptions). Matched on the path tail the middleware sends. */
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

/**
 * The four legs to display, always in the same order, always all four.
 *
 * Pass `undefined` before a study is paired (or before the first config pull)
 * and every leg comes back `unavailable` — the honest answer, and the one the
 * empty state is written against.
 */
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

/** Just the structural bit of `CaptureConfig` this module reads, so `legs.ts`
 *  stays usable (and testable) without the full config envelope. */
export interface CaptureConfigLike {
  legs?: unknown;
}

/** How many legs are actively capturing — the one number the sidebar's
 *  collapsed header shows, and the session view's at-a-glance answer to
 *  "what is running right now?". */
export function activeLegCount(legs: Leg[]): number {
  return legs.filter((l) => l.state === 'enabled').length;
}

/**
 * True when any enabled leg captures actual code content. The surface uses
 * this to decide whether to show the standing consent reminder: the promise
 * is "no raw code content" with two scoped exceptions, and a participant
 * should not have to expand three trees to learn an exception is in force.
 */
export function capturesContent(legs: Leg[]): boolean {
  return legs.some(
    (leg) =>
      leg.state === 'enabled' &&
      leg.toggles.some((t) => t.consentRelevant && t.currentValue === true),
  );
}
