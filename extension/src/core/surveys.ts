/**
 * Survey instrument definitions. Kept as data so adapters render them with
 * whatever native UI fits (QuickPick in VS Code, popup in JetBrains) and so
 * researchers can tweak wording in exactly one place.
 */

export interface LikertItem {
  id: string;
  question: string;
  lowLabel: string;
  highLabel: string;
  /** Number of scale points (7 => answers 1..7). */
  points: number;
  minimum?: number;
  step?: number;
  /** Optional per-point descriptions shown next to the numbers. */
  hints?: Record<number, string>;
}

/** The in-flow fatigue probe. One question, two seconds, keyboard-only. */
export const FATIGUE_ITEM: LikertItem = {
  id: 'fatigue',
  question: 'How mentally fatigued do you feel right now?',
  lowLabel: 'Completely fresh',
  highLabel: 'Exhausted',
  points: 7,
  hints: { 1: 'wide awake', 4: 'neutral', 7: 'can barely focus' },
};

/**
 * End-of-study questionnaire - a NASA-TLX-inspired workload battery on the
 * same 7-point scale, so all Likert data lands in one comparable unit.
 */
export const END_SURVEY_ITEMS: LikertItem[] = [
  {
    id: 'mental_demand',
    question: 'How mentally demanding was the task?',
    lowLabel: 'Very low',
    highLabel: 'Very high',
    points: 7,
  },
  {
    id: 'effort',
    question:
      'How hard did you have to work to accomplish your level of performance?',
    lowLabel: 'Very little',
    highLabel: 'Very hard',
    points: 7,
  },
  {
    id: 'frustration',
    question: 'How insecure, discouraged, irritated, or annoyed were you?',
    lowLabel: 'Not at all',
    highLabel: 'Extremely',
    points: 7,
  },
  {
    id: 'time_pressure',
    question: 'How hurried or rushed was the pace of the task?',
    lowLabel: 'Very relaxed',
    highLabel: 'Very rushed',
    points: 7,
  },
  {
    id: 'perceived_performance',
    question:
      'How successful were you in accomplishing what you were asked to do?',
    lowLabel: 'Failure',
    highLabel: 'Perfect',
    points: 7,
  },
  {
    id: 'comprehension',
    question: 'How well did you understand the code you worked with?',
    lowLabel: 'Not at all',
    highLabel: 'Completely',
    points: 7,
  },
];

/** Extra item appended only in the AI-assisted condition. */
export const AI_CONDITION_ITEM: LikertItem = {
  id: 'ai_reliance',
  question: 'How much did you rely on the AI assistant to make progress?',
  lowLabel: 'Not at all',
  highLabel: 'Entirely',
  points: 7,
};

/** Resolve the debrief from the session's locked assignment. */
export function endSurveyItems(condition: string): LikertItem[] {
  return condition === 'ai-assisted'
    ? [...END_SURVEY_ITEMS, AI_CONDITION_ITEM]
    : [...END_SURVEY_ITEMS];
}

/** Protocol v6 instruments. These definitions travel in the locked capture config. */
export interface SurveyInstrument {
  id: string;
  version: string;
  title: string;
  timing: 'pre-task' | 'post-task';
  conditions?: string[];
  items: Array<{
    id: string;
    text: string;
    scale: {
      min: number;
      max: number;
      step?: number;
      lowLabel: string;
      highLabel: string;
    };
    reverse?: boolean;
  }>;
  scoring: 'mean' | 'sum' | 'sus' | 'none';
  validation?: string;
}

export function readInstruments(
  value: unknown,
  condition: string,
  timing: SurveyInstrument['timing'],
): SurveyInstrument[] {
  if (!Array.isArray(value)) return [];
  return value.filter((candidate): candidate is SurveyInstrument => {
    if (!candidate || typeof candidate !== 'object') return false;
    const i = candidate as SurveyInstrument;
    if (
      !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(i.id) ||
      typeof i.version !== 'string' ||
      typeof i.title !== 'string' ||
      i.timing !== timing ||
      !Array.isArray(i.items) ||
      !i.items.length ||
      !['mean', 'sum', 'sus', 'none'].includes(i.scoring)
    )
      return false;
    if (
      i.conditions &&
      (!Array.isArray(i.conditions) || !i.conditions.includes(condition))
    )
      return false;
    const ids = new Set<string>();
    return i.items.every((item) => {
      if (
        !item ||
        !/^[A-Za-z0-9][A-Za-z0-9_-]*$/.test(item.id) ||
        ids.has(item.id) ||
        typeof item.text !== 'string' ||
        !item.scale
      )
        return false;
      ids.add(item.id);
      const { min, max, step = 1, lowLabel, highLabel } = item.scale;
      const count = (max - min) / step;
      return (
        [min, max, step].every(Number.isFinite) &&
        max > min &&
        step > 0 &&
        count <= 100 &&
        Number.isInteger(count) &&
        typeof lowLabel === 'string' &&
        typeof highLabel === 'string'
      );
    });
  });
}

export function instrumentItems(instrument: SurveyInstrument): LikertItem[] {
  return instrument.items.map((item) => ({
    id: item.id,
    question: item.text,
    lowLabel: item.scale.lowLabel,
    highLabel: item.scale.highLabel,
    points: (item.scale.max - item.scale.min) / (item.scale.step ?? 1) + 1,
    minimum: item.scale.min,
    step: item.scale.step ?? 1,
  }));
}

export function scoreInstrument(
  instrument: SurveyInstrument,
  responses: Record<string, number>,
): number | null {
  const values: number[] = [];
  for (const item of instrument.items) {
    let value = responses[item.id];
    const { min, max, step = 1 } = item.scale;
    if (
      !Number.isFinite(value) ||
      value < min ||
      value > max ||
      Math.abs((value - min) / step - Math.round((value - min) / step)) > 1e-8
    )
      return null;
    if (item.reverse) value = min + max - value;
    if (instrument.scoring === 'sus') value -= min;
    values.push(value);
  }
  if (!values.length || instrument.scoring === 'none') return null;
  const sum = values.reduce((total, value) => total + value, 0);
  return instrument.scoring === 'sus'
    ? sum * 2.5
    : instrument.scoring === 'sum'
      ? sum
      : sum / values.length;
}

export function validateResponses(
  items: LikertItem[],
  value: unknown,
): Record<string, number> | undefined {
  if (!value || typeof value !== 'object' || Array.isArray(value))
    return undefined;
  const responses = value as Record<string, number>;
  for (const item of items) {
    const answer = responses[item.id];
    const low = item.minimum ?? 1;
    const step = item.step ?? 1;
    const index = (answer - low) / step;
    if (
      !Number.isFinite(answer) ||
      !Number.isInteger(index) ||
      index < 0 ||
      index >= item.points
    )
      return undefined;
  }
  return Object.fromEntries(items.map((item) => [item.id, responses[item.id]]));
}
