import { test, afterEach, mock } from 'node:test';
import assert from 'node:assert/strict';
import {
  ComprehensionProbeMachine,
  DEFAULT_COMPREHENSION_PROBE_CONFIG,
  ComprehensionProbeConfig,
  ChunkMeta,
  ChunkReference,
  ProbeDescriptor,
  ProbeResponse,
  predictOutput,
  locateChange,
  resetBurstId,
} from '../src/core/comprehensionProbe';
import { CLOCK_BASE, advanceTo } from './helpers';

function meta(over: Partial<ChunkMeta> = {}): ChunkMeta {
  return {
    editBurstId: 'b001',
    file: '/workspace/task.py',
    linesTouched: 10,
    charsAdded: 250,
    language: 'python',
    ...over,
  };
}

function ref(over: Partial<ChunkReference> = {}): ChunkReference {
  return { editBurstId: 'b001', ...over };
}

interface Fixture {
  machine: ComprehensionProbeMachine;
  probes: Array<{
    meta: ChunkMeta;
    descriptor: ProbeDescriptor;
    ref: ChunkReference;
  }>;
  responses: ProbeResponse[];
}

function fixture(over: Partial<ComprehensionProbeConfig> = {}): Fixture {
  resetBurstId();
  const probes: Fixture['probes'] = [];
  const responses: ProbeResponse[] = [];
  const machine = new ComprehensionProbeMachine(
    { ...DEFAULT_COMPREHENSION_PROBE_CONFIG, ...over },
    {
      onProbe: (meta, descriptor, ref) =>
        probes.push({ meta, descriptor, ref }),
      onProbeResponse: (r) => responses.push(r),
    },
  );
  return { machine, probes, responses };
}

afterEach(() => mock.timers.reset());

test('acceptChunk transitions from idle to probe-pending and fires onProbe', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes, responses } = fixture();
  assert.equal(machine.state, 'idle');

  machine.acceptChunk(meta(), ref());
  assert.equal(machine.state, 'probe-pending');
  assert.equal(probes.length, 1);
  assert.equal(probes[0].meta.editBurstId, 'b001');
  assert.equal(probes[0].descriptor.promptKind, 'predict-output');
  assert.equal(responses.length, 0);
  machine.dispose();
});

test('cancelProbe returns to idle and does not fire onProbeResponse', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());
  assert.equal(machine.state, 'probe-pending');

  machine.cancelProbe();
  assert.equal(machine.state, 'idle');
  assert.equal(responses.length, 0);
  machine.dispose();
});

test('expire transitions to idle and fires onProbeResponse with expired: true', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes, responses } = fixture();
  machine.acceptChunk(
    meta({ editBurstId: 'b002' }),
    ref({ editBurstId: 'b002' }),
  );
  assert.equal(probes.length, 1);

  advanceTo(CLOCK_BASE + 30_100);
  machine.expire();
  assert.equal(machine.state, 'idle');
  assert.equal(responses.length, 1);
  assert.equal(responses[0].expired, true);
  assert.equal(responses[0].chunkRef.editBurstId, 'b002');
  machine.dispose();
});

test('answer stops records msToAnswer and expired: false', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());

  advanceTo(CLOCK_BASE + 5_000);
  machine.answer('42');
  assert.equal(machine.state, 'idle');
  assert.equal(responses.length, 1);
  assert.equal(responses[0].answer, '42');
  assert.equal(responses[0].expired, false);
  assert.ok(responses[0].msToAnswer >= 5_000);
  machine.dispose();
});

test('answer with correct flag is passed through', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());
  machine.answer('print("hello")', true);
  assert.equal(responses[0].correct, true);
  machine.dispose();
});

test('acceptChunk is ignored when disabled', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes } = fixture({ enabled: false });
  machine.acceptChunk(meta(), ref());
  assert.equal(machine.state, 'idle');
  assert.equal(probes.length, 0);
  machine.dispose();
});

test('acceptChunk only fires when state is idle', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes } = fixture();
  machine.acceptChunk(meta(), ref());
  assert.equal(probes.length, 1);

  machine.acceptChunk(
    meta({ editBurstId: 'b002' }),
    ref({ editBurstId: 'b002' }),
  );
  assert.equal(probes.length, 1);

  machine.answer('x');
  machine.acceptChunk(
    meta({ editBurstId: 'b003' }),
    ref({ editBurstId: 'b003' }),
  );
  assert.equal(probes.length, 2);
  machine.dispose();
});

test('sampled cadence: only some chunks trigger probes', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes } = fixture({
    cadence: 'sampled',
    sampleRate: 0.5,
    probeTypes: ['predict-output'],
  });
  for (let i = 1; i <= 6; i++) {
    machine.acceptChunk(
      meta({ editBurstId: `b${String(i).padStart(3, '0')}` }),
      ref({ editBurstId: `b${String(i).padStart(3, '0')}` }),
    );
    if (machine.state === 'probe-pending') {
      machine.answer('ok');
    }
  }
  assert.ok(
    probes.length >= 2 && probes.length <= 4,
    `expected ~3 probes, got ${probes.length}`,
  );
  machine.dispose();
});

test('predictOutput returns null for small chunks', () => {
  const small: ChunkMeta = {
    editBurstId: 'b1',
    file: 'x.py',
    linesTouched: 1,
    charsAdded: 5,
    language: 'python',
  };
  assert.equal(predictOutput(small), null);

  const big = meta();
  assert.notEqual(predictOutput(big), null);
  assert.equal(predictOutput(big)!.promptKind, 'predict-output');
});

test('locateChange returns null for small chunks', () => {
  const small: ChunkMeta = {
    editBurstId: 'b1',
    file: 'x.py',
    linesTouched: 1,
    charsAdded: 5,
    language: 'python',
  };
  assert.equal(locateChange(small), null);

  const big = meta();
  assert.notEqual(locateChange(big), null);
  assert.equal(locateChange(big)!.promptKind, 'locate-change');
});

test('no probe type configured skips chunk silently', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, probes } = fixture({ probeTypes: [] });
  machine.acceptChunk(meta(), ref());
  assert.equal(machine.state, 'idle');
  assert.equal(probes.length, 0);
  machine.dispose();
});

test('dispose clears active probe without firing response', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());
  assert.equal(machine.state, 'probe-pending');

  machine.dispose();
  assert.equal(machine.state, 'idle');
  assert.equal(responses.length, 0);
});

/**
 * FR-ETH-2: the probe descriptor must never contain code content.
 * Grep for fields that would violate privacy.
 */
test('FR-ETH-2: probe descriptor contains no code or text fields', () => {
  const descriptor = predictOutput(meta());
  const keys = Object.keys(descriptor!);
  for (const forbidden of ['code', 'text', 'snippet', 'content', 'body']) {
    assert.ok(
      !keys.includes(forbidden),
      `probe descriptor must not contain field "${forbidden}"`,
    );
  }
});

test('FR-ETH-2: ChunkMeta never contains code text', () => {
  const m = meta();
  const forbidden = ['code', 'text', 'snippet', 'content', 'body'];
  for (const key of Object.keys(m)) {
    for (const f of forbidden) {
      assert.ok(!key.includes(f), `ChunkMeta must not contain field "${key}"`);
    }
  }
});

test('expire after answer is a no-op', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());
  machine.answer('42');
  assert.equal(responses.length, 1);

  machine.expire();
  assert.equal(responses.length, 1, 'expire after answer must not double-fire');
  machine.dispose();
});

test('answer returns null for correct when not specified', () => {
  mock.timers.enable({ apis: ['Date', 'setTimeout'], now: CLOCK_BASE });
  const { machine, responses } = fixture();
  machine.acceptChunk(meta(), ref());
  machine.answer('maybe');
  assert.equal(responses[0].correct, null);
  machine.dispose();
});
