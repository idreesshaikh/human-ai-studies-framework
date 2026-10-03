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

  settings: Record<string, unknown>;

  block?: unknown;

  legs?: unknown;

  producers?: unknown;

  sessionManifest?: unknown;
}

const PREFIX = 'tern.';

export function overlayFlags(cfg: CaptureConfig): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(cfg.settings)) {
    if (k.startsWith(PREFIX)) out[k.slice(PREFIX.length)] = v;
  }
  return out;
}

export function configChanged(
  applied: string | undefined,
  incoming: string,
): boolean {
  return applied !== incoming;
}

export function shouldApplyCaptureConfig(
  sessionActive: boolean,
  applied: string | undefined,
  incoming: string,
): boolean {
  return !sessionActive && configChanged(applied, incoming);
}

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
