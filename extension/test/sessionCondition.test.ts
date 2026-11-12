import { test } from 'node:test';
import assert from 'node:assert/strict';
import { conditionForSessionBlock } from '../src/core/sessionCondition';

test('session start uses the refreshed condition after a within-subject block advances', () => {
  const firstBlock = { index: 0, condition: 'Unassisted' };
  const secondBlock = { index: 1, condition: 'AI-assisted' };

  const enrollmentCondition = firstBlock.condition;
  const conditionForFirstSession = conditionForSessionBlock(
    enrollmentCondition,
    firstBlock,
  );
  const conditionForSecondSession = conditionForSessionBlock(
    enrollmentCondition,
    secondBlock,
  );

  assert.equal(conditionForFirstSession, 'Unassisted');
  assert.equal(conditionForSecondSession, 'AI-assisted');
});

test('session condition falls back to the enrollment condition without a block condition', () => {
  assert.equal(conditionForSessionBlock('Unassisted'), 'Unassisted');
  assert.equal(
    conditionForSessionBlock('Unassisted', { condition: '  ' }),
    'Unassisted',
  );
});
