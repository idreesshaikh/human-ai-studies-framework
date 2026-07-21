/**
 * The versioned, protocol-derived capture config the IDE receives on pair and
 * re-pulls at each session start. Portable core: this module only shapes the
 * data — WHEN it is applied (a session boundary, never mid-run: wall #6) is
 * the adapter's job.
 */

export interface CaptureConfig {
  captureConfigVersion: string;
  producer: string;
  /** Flat `tern.*` settings from the middleware. */
  settings: Record<string, unknown>;
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
 * applied mid-run — this is what the adapter's `refreshConfigAtSessionStart`
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
