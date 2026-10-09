import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import {
  readInstruments,
  instrumentItems,
  scoreInstrument,
  validateResponses,
  SurveyInstrument,
} from '../src/core/surveys';
import { SCHEMA_VERSION } from '../src/core/types';

const instruments = JSON.parse(
  readFileSync(
    resolve(
      __dirname,
      '../../../protocol/src/protocol/schema/survey-instruments.json',
    ),
    'utf8',
  ),
) as SurveyInstrument[];
test('v6 renders the shipped declared scales and scores reverse items', () => {
  assert.equal(SCHEMA_VERSION, 6);
  for (const instrument of instruments) {
    assert.equal(
      readInstruments([instrument], 'copilot-version-two', instrument.timing)
        .length,
      1,
    );
    const items = instrumentItems(instrument);
    const responses = Object.fromEntries(
      instrument.items.map((i) => [
        i.id,
        i.reverse ? i.scale.min : i.scale.max,
      ]),
    );
    assert.deepEqual(validateResponses(items, responses), responses);
    const score = scoreInstrument(instrument, responses);
    if (instrument.id === 'sus') assert.equal(score, 100);
    if (instrument.id === 'raw-nasa-tlx') assert.equal(score, 100);
    if (instrument.id === 'legacy-tlx-inspired') assert.equal(score, null);
    assert.equal(validateResponses(items, {}), undefined);
    const bad = {
      ...responses,
      [instrument.items[0].id]: instrument.items[0].scale.max + 1,
    };
    assert.equal(validateResponses(items, bad), undefined);
    assert.equal(scoreInstrument(instrument, bad), null);
  }
});
test('declared timing and conditions work for tool-version conditions', () => {
  const instrument = { ...instruments[0], conditions: ['copilot-version-two'] };
  assert.equal(
    readInstruments([instrument], 'copilot-version-one', 'post-task').length,
    0,
  );
  assert.equal(
    readInstruments([instrument], 'copilot-version-two', 'pre-task').length,
    0,
  );
  assert.equal(
    readInstruments([instrument], 'copilot-version-two', 'post-task').length,
    1,
  );
});
test('malformed definitions and nonfinite responses fail closed', () => {
  assert.deepEqual(readInstruments(undefined, 'control', 'post-task'), []);
  assert.deepEqual(
    readInstruments(
      [
        {
          ...instruments[0],
          items: [
            { id: 'x', text: 'x', scale: { min: 0, max: 1000, step: 1 } },
          ],
        },
      ],
      'control',
      'post-task',
    ),
    [],
  );
  assert.equal(
    validateResponses(instrumentItems(instruments[0]), { mental_demand: NaN }),
    undefined,
  );
});
