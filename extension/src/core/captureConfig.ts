/**
 * The versioned, protocol-derived capture config the IDE receives on pair and
 * re-pulls at each session start. Portable core: this module only shapes the
 * data — WHEN it is applied (a session boundary, never mid-run: wall #6) is
 * the adapter's job.
 */

export interface CaptureConfig {
  captureConfigVersion: string;
  producer: string;
  /** Flat `cognitiveOverlay.*` settings from the middleware. */
  settings: Record<string, unknown>;
}

const PREFIX = 'cognitiveOverlay.';

/** The capture flags to apply, with the `cognitiveOverlay.` prefix removed. */
export function overlayFlags(cfg: CaptureConfig): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cfg.settings)) {
    if (k.startsWith(PREFIX)) out[k.slice(PREFIX.length)] = v;
  }
  return out;
}

/** True if the incoming config differs from what is already applied. */
export function configChanged(applied: string | undefined, incoming: string): boolean {
  return applied !== incoming;
}
