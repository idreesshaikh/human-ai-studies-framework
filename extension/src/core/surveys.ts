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
