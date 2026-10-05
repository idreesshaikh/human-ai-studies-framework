export interface SendState {
  /** Epoch ms of the last POST the server accepted. */
  lastSuccessAt?: number;
  /** Events buffered and not yet accepted by the server. */
  pending: number;
}

function age(ms: number): string {
  const s = Math.max(0, Math.round(ms / 1000));
  return s < 60 ? `${s}s` : `${Math.round(s / 60)}m`;
}

/** Truthful upload status for the Data view, from what the sink observed. */
export function describeSend(
  s: SendState,
  now: number,
): { detail: string; warn: boolean } {
  const base =
    s.lastSuccessAt === undefined
      ? 'No send yet'
      : `Last sent ${age(now - s.lastSuccessAt)} ago`;
  if (s.pending > 0) {
    return { detail: `${base}, ${s.pending} not yet sent`, warn: true };
  }
  return { detail: base, warn: false };
}
