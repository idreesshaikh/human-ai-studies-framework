'use strict';

// Local replacement for GitHub Classroom timing.
//   npm run begin -- <participant-id>   record the start time (run once, when ready to start)
//   npm test                            run the tests and log the result with a timestamp
// Everything is written to .study/ in this folder. Participants send that folder back.

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const DIR = path.join(__dirname, '..', '.study');
const START = path.join(DIR, 'start.json');
const LOG = path.join(DIR, 'runs.jsonl');

function begin(participantId) {
  if (fs.existsSync(START)) {
    console.error('Already started. Do not run this twice. Start time:', fs.readFileSync(START, 'utf8'));
    process.exit(1);
  }
  fs.mkdirSync(DIR, { recursive: true });
  const record = { participantId: participantId || null, startedAt: new Date().toISOString() };
  fs.writeFileSync(START, JSON.stringify(record) + '\n');
  console.log('Timer started at', record.startedAt);
}

function runTests() {
  const result = spawnSync(process.execPath, ['--test', path.join(__dirname, '..', 'test', 'server.test.js')], {
    encoding: 'utf8',
  });
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);

  const count = (name) => Number((result.stdout.match(new RegExp(`(?:^|\\n)(?:# |ℹ )${name} (\\d+)`)) || [])[1] || 0);
  const entry = { at: new Date().toISOString(), passed: count('pass'), total: count('tests') };

  if (!fs.existsSync(START)) {
    console.warn('\nWarning: timer not started. Run `npm run begin -- <participant-id>` first. This run is not logged.');
  } else {
    fs.appendFileSync(LOG, JSON.stringify(entry) + '\n');
  }
  process.exit(result.status ?? 1);
}

const [command, arg] = process.argv.slice(2);
if (command === 'begin') begin(arg);
else if (command === 'test') runTests();
else console.error('Usage: study.js begin <participant-id> | test');
