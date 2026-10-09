'use strict';

// Task-harness reporter. Runs the tests and records the result as a `task_outcome` event next to
// TERN's own session file, so the study's timing comes from TERN's session clock.
//   npm test                           run the tests and log a task_outcome event
//   node scripts/study.js export       print the logged events as a JSON batch for POST /ingest/events
//
// Needs an active TERN session (StudyLoop: Connect to Study, or a local session) in this folder.
// TERN writes `.study-data/<participant>_<timestamp>.jsonl`; set STUDY_DATA_DIR if `tern.output.directory` differs.

const { spawnSync } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const SOURCE = 'task-harness';
const DATA_DIR = process.env.STUDY_DATA_DIR || path.join(__dirname, '..', '.study-data');
const OUT_FILE = path.join(DATA_DIR, `${SOURCE}.jsonl`);

function readJsonl(file) {
  return fs
    .readFileSync(file, 'utf8')
    .split('\n')
    .filter(Boolean)
    .flatMap((line) => {
      try {
        return [JSON.parse(line)];
      } catch {
        return [];
      }
    });
}

// The newest TERN session file that has a session_start event, or null.
function findSession() {
  if (!fs.existsSync(DATA_DIR)) return null;
  const files = fs
    .readdirSync(DATA_DIR)
    .filter((f) => f.endsWith('.jsonl') && f !== path.basename(OUT_FILE))
    .map((f) => path.join(DATA_DIR, f))
    .sort((a, b) => fs.statSync(b).mtimeMs - fs.statSync(a).mtimeMs);
  for (const file of files) {
    const start = readJsonl(file).find((e) => e.type === 'session_start');
    if (start) return start;
  }
  return null;
}

function runTests() {
  const result = spawnSync(process.execPath, ['--test', path.join(__dirname, '..', 'test', 'server.test.js')], {
    encoding: 'utf8',
  });
  process.stdout.write(result.stdout);
  process.stderr.write(result.stderr);

  const count = (name) => Number((result.stdout.match(new RegExp(`(?:^|\\n)(?:# |ℹ )${name} (\\d+)`)) || [])[1] || 0);
  const passedTests = count('pass');
  const totalTests = count('tests');
  const passed = totalTests > 0 && passedTests === totalTests;

  const session = findSession();
  if (!session) {
    console.warn('\nWarning: no TERN session found in', DATA_DIR);
    console.warn('Start a session in VS Code first. This run was not logged.');
    process.exit(result.status ?? 1);
  }

  const previous = fs.existsSync(OUT_FILE) ? readJsonl(OUT_FILE).filter((e) => e.sessionId === session.sessionId) : [];
  const now = new Date();
  const event = {
    ts: now.toISOString(),
    sessionId: session.sessionId,
    participantId: session.participantId,
    condition: session.condition,
    taskId: session.taskId || '',
    seq: previous.length + 1,
    source: SOURCE,
    type: 'task_outcome',
    payload: { passed, passedTests, totalTests },
  };
  // Time from TERN's session_start to the first all-green run. TERN's clock excludes paused breaks;
  // this simple difference does not, so prefer the analysis recipe's own computation if breaks matter.
  if (passed && !previous.some((e) => e.payload.passed)) {
    event.payload.firstGreenMs = now - new Date(session.ts);
  }
  fs.mkdirSync(DATA_DIR, { recursive: true });
  fs.appendFileSync(OUT_FILE, JSON.stringify(event) + '\n');
  process.exit(result.status ?? 1);
}

function exportBatch() {
  if (!fs.existsSync(OUT_FILE)) {
    console.error('Nothing to export:', OUT_FILE, 'does not exist.');
    process.exit(1);
  }
  console.log(JSON.stringify({ source: SOURCE, events: readJsonl(OUT_FILE) }, null, 2));
}

const command = process.argv[2];
if (command === 'test') runTests();
else if (command === 'export') exportBatch();
else console.error('Usage: study.js test | export');
