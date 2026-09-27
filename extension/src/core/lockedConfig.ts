/**
 * The frozen, session-start-resolved capture config that replaces reading
 * `vscode.workspace.getConfiguration('tern')` live once a study session is
 * paired. Portable core: this module only shapes the merged data  -  the
 * adapter decides WHEN to build it (session start, never mid-run) and reads
 * `locked` to fall back to live settings while unpaired.
 */

/**
 * Keys resolved from the pairing redeem or local environment, never from the
 * protocol overlay. The protocol carries example values for these (e.g. the
 * pilot protocol's `output.httpEndpoint` is
 * `http://127.0.0.1:8000/ingest/events`), so locking them would clobber the
 * real server endpoint issued at pairing. Mirrors `IDENTITY_KEYS` in
 * `vscode/pairing.ts`, which excludes a similar set from `applyConfig` for
 * the same reason.
 */
export const IDENTITY_KEYS: ReadonlySet<string> = new Set([
  'participantId',
  'condition',
  'studyId',
  'output.httpEndpoint',
  'output.directory',
  'session.id',
]);

export interface LockedConfig {
  readonly locked: boolean;
  get<T>(key: string, fallback: T): T;
  has(key: string): boolean;
  lockedValue(key: string): unknown;
  keys(): string[];
}

const PREFIX = 'tern.';

/**
 * The extension's own declared defaults, read from `package.json`'s
 * configuration contribution. Never throws and never partially trusts  -  a
 * malformed packageJSON means an empty default set, not a crash at session
 * start over a shape VS Code itself hands us as `any`.
 */
export function extensionDefaults(
  packageJSON: unknown,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  if (!packageJSON || typeof packageJSON !== 'object') return out;
  const pkg = packageJSON as Record<string, unknown>;
  const contributes = pkg.contributes;
  if (!contributes || typeof contributes !== 'object') return out;
  const configuration = (contributes as Record<string, unknown>).configuration;
  if (!configuration || typeof configuration !== 'object') return out;
  const properties = (configuration as Record<string, unknown>).properties;
  if (!properties || typeof properties !== 'object') return out;

  for (const [key, value] of Object.entries(
    properties as Record<string, unknown>,
  )) {
    if (!key.startsWith(PREFIX)) continue;
    if (!value || typeof value !== 'object') continue;
    if (!Object.hasOwn(value as object, 'default')) continue;
    out[key.slice(PREFIX.length)] = (value as Record<string, unknown>).default;
  }
  return out;
}

function frozenConfig(locked: boolean, values: Record<string, unknown>) {
  const map = Object.freeze({ ...values });
  return Object.freeze({
    locked,
    get<T>(key: string, fallback: T): T {
      return Object.hasOwn(map, key) ? (map[key] as T) : fallback;
    },
    has(key: string): boolean {
      return Object.hasOwn(map, key);
    },
    lockedValue(key: string): unknown {
      return map[key];
    },
    keys(): string[] {
      return Object.keys(map);
    },
  });
}

/**
 * Resolves the effective config once, at session start. Unpaired, the
 * result is a pass-through (`locked: false`) so the adapter keeps reading
 * live VS Code settings exactly as today  -  standalone/local testing is
 * unaffected. Paired, the overlay (protocol) wins over the extension's own
 * defaults, identity keys are stripped so the redeem-issued values are never
 * shadowed, and the result is frozen so nothing downstream can mutate it
 * back into a live read.
 */
export function buildLockedConfig(opts: {
  defaults: Record<string, unknown>;
  overlay: Record<string, unknown>;
  paired: boolean;
}): LockedConfig {
  if (!opts.paired) return frozenConfig(false, {});

  const merged: Record<string, unknown> = {
    ...opts.defaults,
    ...opts.overlay,
  };
  for (const key of IDENTITY_KEYS) delete merged[key];
  return frozenConfig(true, merged);
}
