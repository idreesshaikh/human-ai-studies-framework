import {
  LabelledPair,
  classStats,
  confusionMatrix,
  misclassified,
  summariseStuck,
} from './metrics';
import { replayEditScenario, replayStuckScenario } from './replay';
import { EDIT_SCENARIOS, EditScenario, STUCK_SCENARIOS } from './scenarios';

export const DISCLAIMER =
  'Scripted scenarios characterise rule behaviour and known failure modes against the signals as modelled here; they are NOT an accuracy estimate for real developer sessions.';

export const ORIGIN_LABELS = ['human', 'ai', 'paste', 'undo-redo'];

const pct = (v: number | null): string =>
  v === null ? 'n/a' : `${(v * 100).toFixed(0)}%`;
const secs = (ms: number): string => `${(ms / 1000).toFixed(0)}s`;

function editSection(title: string, scenarios: EditScenario[]): string[] {
  const outcomes = scenarios.flatMap((s) => replayEditScenario(s));
  const pairs: LabelledPair[] = outcomes;
  const m = confusionMatrix(pairs, ORIGIN_LABELS);
  const known = new Map(
    scenarios.filter((s) => s.knownFailure).map((s) => [s.id, s.knownFailure]),
  );
  const wrong = misclassified(pairs);
  const lines = [
    `## ${title}`,
    '',
    `${scenarios.length} scenarios, ${pairs.length} bursts, ${pairs.length - wrong.length} classified as labelled, ${wrong.length} not.`,
    '',
    'Confusion matrix (rows expected, columns actual):',
    '',
    ['expected\\actual', ...ORIGIN_LABELS].join(' | '),
    ...ORIGIN_LABELS.map((l, i) => [l, ...m[i]].join(' | ')),
    '',
    'class | precision | recall | support',
    ...classStats(m, ORIGIN_LABELS).map(
      (c) =>
        `${c.label} | ${pct(c.precision)} | ${pct(c.recall)} | ${c.support}`,
    ),
    '',
    'Misclassified bursts:',
  ];
  if (!wrong.length) lines.push('  none');
  for (const w of wrong) {
    const why = known.get(w.id);
    lines.push(
      `  ${why ? 'Known failure' : 'UNEXPECTED'}: ${w.id}#${w.index} expected ${w.expected}, got ${w.actual}${why ? ` - ${why}` : ''}`,
    );
  }
  lines.push('');
  return lines;
}

export function renderReport(recording?: EditScenario): string {
  const lines = [DISCLAIMER, '', '# Validation report', ''];
  lines.push(
    ...editSection('Edit-origin classifier (scripted)', EDIT_SCENARIOS),
  );

  const results = STUCK_SCENARIOS.map(replayStuckScenario);
  const sum = summariseStuck(results);
  const ttd = sum.timeToDetectMs;
  lines.push('## Stuck detector (scripted)', '');
  lines.push('scenario | ground truth | fires | time to first fire');
  for (const r of results) {
    const first = r.fires.length
      ? secs(r.fires[0].atMs - (r.stuck ? r.stuckFromMs : 0))
      : '-';
    const s = STUCK_SCENARIOS.find((x) => x.id === r.id)!;
    lines.push(
      `${r.id} | ${r.stuck ? 'stuck' : 'not stuck'} | ${r.fires.length} | ${first}${s.knownFalseAlarm ? ` | Known failure: ${s.knownFalseAlarm}` : ''}`,
    );
  }
  lines.push(
    '',
    `Stuck scenarios detected: ${sum.detected}/${sum.stuckScenarios}`,
    `Time to detect: ${ttd.length ? ttd.map(secs).join(', ') : 'n/a'}`,
    `False alarms: ${sum.falseAlarms} over ${sum.nonStuckHours.toFixed(2)} simulated non-stuck hours`,
    `False alarms per simulated hour: ${sum.falseAlarmsPerHour === null ? 'n/a' : sum.falseAlarmsPerHour.toFixed(1)}`,
    '(Ground truth is fuzzy, so per-event precision is deliberately not reported.)',
    '',
  );

  if (recording) {
    lines.push(
      ...editSection('Real-session recording (user supplied)', [recording]),
    );
  }
  return lines.join('\n');
}
