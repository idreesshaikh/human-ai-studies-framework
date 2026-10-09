// Cross-language contract fixture: protocol capture config -> core survey -> event.
import { readFileSync } from 'node:fs';
import { readInstruments, scoreInstrument } from '../src/core/surveys.ts';
const config = JSON.parse(readFileSync(0, 'utf8'));
const settings = config.settings;
const condition = settings['tern.condition'];
const instruments = ['pre-task', 'post-task'].flatMap(timing => readInstruments(settings['tern.surveys'], condition, timing));
const events = instruments.map((instrument, index) => {
  const responses = Object.fromEntries(instrument.items.map(item => [item.id, item.reverse ? item.scale.min : item.scale.max]));
  return { v:6, seq:index, ts:`2026-10-08T10:00:0${index}.000Z`, mono:index*1000,
    source:'tern', sessionId:'roundtrip-session', participantId:settings['tern.participantId'], condition,
    type:instrument.timing==='pre-task'?'pre_task_covariate':'survey_response',
    payload:{ instrumentId:instrument.id,instrumentVersion:instrument.version,
      instrumentHash:settings['tern.provenance'].instruments.find(i=>i.id===instrument.id).sha256,
      responses,score:scoreInstrument(instrument,responses),timing:instrument.timing } };
});
process.stdout.write(JSON.stringify(events));
