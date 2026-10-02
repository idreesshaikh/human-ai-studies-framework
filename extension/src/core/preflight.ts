export interface PreflightItem {
  key: string;

  label: string;
  on: boolean;
}

const TRACKED: { key: string; label: string }[] = [
  { key: 'stuck.enabled', label: 'Stuck detection' },
  { key: 'behavior.captureEditBursts', label: 'Edit bursts' },
  { key: 'behavior.captureAiLifecycle', label: 'AI suggestion lifecycle' },
  { key: 'behavior.captureClipboard', label: 'Paste events' },
  { key: 'behavior.captureVisibleRanges', label: 'Scroll coverage' },
  { key: 'behavior.captureFocus', label: 'Focus switches' },
  { key: 'behavior.captureHeartbeat', label: 'Active/idle time' },
  { key: 'behavior.captureAttention', label: 'Time-on-code' },
];

export function preflightSummary(
  flags: Record<string, unknown>,
  producers?: unknown,
): PreflightItem[] {
  const items = TRACKED.map(({ key, label }) => ({
    key,
    label,
    on: flags[key] === true,
  }));
  if (!producers || typeof producers !== 'object' || Array.isArray(producers)) {
    return items;
  }
  for (const [id, raw] of Object.entries(
    producers as Record<string, unknown>,
  )) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) continue;
    const producer = raw as Record<string, unknown>;
    const state =
      typeof producer.state === 'string' ? producer.state : 'unavailable';
    const reason = typeof producer.reason === 'string' ? producer.reason : '';
    items.push({
      key: `producer.${id}`,
      label: `Producer: ${id}`,
      on: state === 'enabled',
    });
    if (state !== 'enabled') {
      items.push({
        key: `producer.${id}.detail`,
        label: `${id}: ${state}${reason ? ` (${reason})` : ''}`,
        on: false,
      });
    }
  }
  return items;
}
