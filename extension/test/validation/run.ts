import { readFileSync } from 'node:fs';
import { parseRecording } from './recording';
import { renderReport } from './report';

// Usage: node out-tests/test/validation/run.js [--recording session.json]
const i = process.argv.indexOf('--recording');
const recording =
  i >= 0
    ? parseRecording(readFileSync(process.argv[i + 1], 'utf8'))
    : undefined;
console.log(renderReport(recording));
