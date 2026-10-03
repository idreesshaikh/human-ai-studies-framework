export interface LikertItem {
  id: string;
  question: string;
  lowLabel: string;
  highLabel: string;

  points: number;

  hints?: Record<number, string>;
}

export const FATIGUE_ITEM: LikertItem = {
  id: 'fatigue',
  question: 'How mentally fatigued do you feel right now?',
  lowLabel: 'Completely fresh',
  highLabel: 'Exhausted',
  points: 7,
  hints: { 1: 'wide awake', 4: 'neutral', 7: 'can barely focus' },
};

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

export const AI_CONDITION_ITEM: LikertItem = {
  id: 'ai_reliance',
  question: 'How much did you rely on the AI assistant to make progress?',
  lowLabel: 'Not at all',
  highLabel: 'Entirely',
  points: 7,
};
