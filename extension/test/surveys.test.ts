import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  AI_CONDITION_ITEM,
  END_SURVEY_ITEMS,
  FATIGUE_ITEM,
  LikertItem,
} from '../src/core/surveys';

function assertWellFormed(item: LikertItem): void {
  assert.ok(item.id.length > 0, 'id present');
  assert.ok(item.question.length > 0, 'question present');
  assert.ok(item.lowLabel.length > 0, 'low label present');
  assert.ok(item.highLabel.length > 0, 'high label present');
  assert.ok(Number.isInteger(item.points) && item.points >= 2, 'points valid');
}

test('fatigue item is a well-formed 7-point scale', () => {
  assertWellFormed(FATIGUE_ITEM);
  assert.equal(FATIGUE_ITEM.points, 7);
  // Hints, when present, must fall within the scale.
  for (const key of Object.keys(FATIGUE_ITEM.hints ?? {})) {
    const point = Number(key);
    assert.ok(
      point >= 1 && point <= FATIGUE_ITEM.points,
      `hint ${key} in range`,
    );
  }
});

test('end-survey items are all well-formed and on the same 7-point scale', () => {
  assert.ok(END_SURVEY_ITEMS.length > 0);
  for (const item of END_SURVEY_ITEMS) {
    assertWellFormed(item);
    assert.equal(item.points, 7, `${item.id} uses the shared 7-point scale`);
  }
});

test('all survey item ids are unique across the full instrument', () => {
  const ids = [
    FATIGUE_ITEM.id,
    ...END_SURVEY_ITEMS.map((i) => i.id),
    AI_CONDITION_ITEM.id,
  ];
  assert.equal(new Set(ids).size, ids.length, 'no duplicate scale ids');
});

test('AI-condition item is a distinct 7-point add-on', () => {
  assertWellFormed(AI_CONDITION_ITEM);
  assert.equal(AI_CONDITION_ITEM.points, 7);
  assert.ok(
    !END_SURVEY_ITEMS.some((i) => i.id === AI_CONDITION_ITEM.id),
    'AI item is not already in the base battery',
  );
});
