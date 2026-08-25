/**
 * The versioned, protocol-derived capture config the IDE receives on pair and
 * re-pulls at each session start. Portable core: this module only shapes the
 * data  -  WHEN it is applied (a session boundary, never mid-run: wall #6) is
 * the adapter's job.
 */

/** What this session was assigned: a task, under a condition, at a known
 *  position in the participant's sequence. Display only  -  the join keys the
 *  editor actually stamps come from `settings`. Optional because an older
 *  middleware won't send it and a study need not declare tasks. */
export interface SessionBlock {
  index: number;
  of: number;
  taskId: string;
  condition: string;
  title: string;
  description: string;
  materials: string;
}

export interface CaptureConfig {
  captureConfigVersion: string;
  producer: string;
  /** Flat `tern.*` settings from the middleware. */
  settings: Record<string, unknown>;
  /** The assigned block, when the server sent one. Validate with
   *  `readBlock` rather than trusting the shape. */
  block?: unknown;
  /**
   * The four legs and their state, for display only (FR-INST-22). Served
   * alongside `settings` by the middleware's `leg_summary`. Optional and
   * untyped here because an older middleware won't send it  -  `readLegs`
   * in `legs.ts` validates the shape and degrades rather than trusting it.
   * Never applied: only `settings` configures capture.
   */
  legs?: unknown;
  /** Producer capability state; configuration is not receipt. */
  producers?: unknown;
  /** Shared session contract consumed by TERN and external producers. */
  sessionManifest?: unknown;
}

const PREFIX = 'tern.';

/** The capture flags to apply, with the `tern.` prefix removed. */
export function overlayFlags(cfg: CaptureConfig): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cfg.settings)) {
    if (k.startsWith(PREFIX)) out[k.slice(PREFIX.length)] = v;
  }
  return out;
}

/** True if the incoming config differs from what is already applied. */
export function configChanged(
  applied: string | undefined,
  incoming: string,
): boolean {
  return applied !== incoming;
}

/**
 * Wall #6, made a checkable value: an incoming capture config is applied
 * only when no session is currently active, and only when its version
 * differs from what's already applied. A version bump discovered while a
 * session is running must be deferred to the next session start, never
 * applied mid-run  -  this is what the adapter's `refreshConfigAtSessionStart`
 * consults before calling `applyConfig`, so a future call-site mistake (e.g.
 * a mid-session poll) fails closed instead of silently violating the wall.
 */
export function shouldApplyCaptureConfig(
  sessionActive: boolean,
  applied: string | undefined,
  incoming: string,
): boolean {
  return !sessionActive && configChanged(applied, incoming);
}

/**
 * The assigned block, or undefined when the server sent none or sent
 * something unusable.
 *
 * Never throws and never partially trusts: a malformed block means the
 * session runs without one  -  the settings still configure capture exactly as
 * before  -  rather than the editor rendering half a task or crashing at
 * session start over a display field.
 */
export function readBlock(cfg: CaptureConfig): SessionBlock | undefined {
  const raw = cfg.block;
  if (!raw || typeof raw !== 'object') return undefined;
  const b = raw as Record<string, unknown>;
  const taskId = typeof b.taskId === 'string' ? b.taskId : '';
  const condition = typeof b.condition === 'string' ? b.condition : '';
  if (!taskId || !condition) return undefined;
  const num = (v: unknown, fallback: number) =>
    typeof v === 'number' && Number.isFinite(v) ? v : fallback;
  const str = (v: unknown) => (typeof v === 'string' ? v : '');
  return {
    index: num(b.index, 0),
    of: num(b.of, 1),
    taskId,
    condition,
    title: str(b.title) || taskId,
    description: str(b.description),
    materials: str(b.materials),
  };
}
