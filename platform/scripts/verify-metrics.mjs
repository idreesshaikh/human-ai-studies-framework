/* Exercises the metric registry (FR-DASH-5). Run:
 *   node --experimental-strip-types scripts/verify-metrics.mjs
 *
 * Checks that:
 *   - every registry entry is well-formed (type in the four, extract present)
 *   - static metrics read their payload key from `metrics` rows
 *   - the AI-authored share is per-participant and computed correctly
 *   - categorical shares sum to 1 and honour declared category order
 *   - an ungradable (null) comprehension probe is dropped, not scored wrong
 *   - ordinal counts land in the right levels and are never averaged
 *   - populatedMetrics reports only measures that actually have rows
 *   - the five-number summary is correct on a known sample
 */
import {
  METRIC_REGISTRY,
  findMetric,
  populatedMetrics,
  summarize,
  ordinalCounts,
  categoryOrder,
  categoryShares,
} from "../src/lib/metricRegistry.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
const close = (a, b, eps = 1e-9) => Math.abs(a - b) < eps;

function row(over = {}) {
  return {
    source: "tern",
    ts: "",
    sessionId: "S1",
    participantId: "P01",
    condition: "ai-assisted",
    type: "edit_burst",
    seq: 0,
    flags: [],
    payload: {},
    ...over,
  };
}

// --- registry shape ---
const TYPES = new Set(["continuous", "count", "ordinal", "categorical"]);
ok("registry is non-empty", METRIC_REGISTRY.length > 0, `${METRIC_REGISTRY.length} metrics`);
ok(
  "every entry is well-formed",
  METRIC_REGISTRY.every(
    (m) => m.key && m.label && m.definition && TYPES.has(m.measurementType) && typeof m.extract === "function",
  ),
);
ok(
  "metric keys are unique",
  new Set(METRIC_REGISTRY.map((m) => m.key)).size === METRIC_REGISTRY.length,
);
ok("the original static metric is still first (stable default)", METRIC_REGISTRY[0].key === "cognitive_complexity");

// --- static metric extraction ---
const metricRows = [
  row({ source: "metrics", type: "function_metrics", participantId: "P01", condition: "ai-assisted", payload: { function: "f", file: "a.py", cognitive_complexity: 7, parameter_count: 3 } }),
  row({ source: "metrics", type: "function_metrics", participantId: "P02", condition: "unassisted", payload: { function: "g", file: "a.py", cognitive_complexity: 4, parameter_count: 2 } }),
  row({ source: "tern", type: "edit_burst", payload: { origin: "ai", charsAdded: 100 } }), // must be ignored by static metrics
];
const cc = findMetric("cognitive_complexity");
ok("cognitive_complexity reads only metrics rows", cc.extract(metricRows).length === 2);
ok("cognitive_complexity values are correct", cc.extract(metricRows).map((o) => o.value).sort().join(",") === "4,7");
ok("corrected scope keys exist", !!findMetric("max_scope_distance") && !!findMetric("mean_scope_distance"));
ok("the invalid variable_scope_distance key is gone", !findMetric("variable_scope_distance"));

// --- AI-authored share: per participant, ai / all ---
const authorshipRows = [
  row({ participantId: "P01", condition: "ai-assisted", payload: { origin: "ai", charsAdded: 300 } }),
  row({ participantId: "P01", condition: "ai-assisted", payload: { origin: "human", charsAdded: 100 } }),
  row({ participantId: "P02", condition: "ai-assisted", payload: { origin: "human", charsAdded: 200 } }),
];
const share = findMetric("ai_char_share").extract(authorshipRows);
ok("ai_char_share yields one point per participant", share.length === 2);
const p01 = share.find((o) => o.participantId === "P01");
const p02 = share.find((o) => o.participantId === "P02");
ok("ai_char_share P01 = 300/400 = 0.75", close(p01.value, 0.75), `got ${p01.value}`);
ok("ai_char_share P02 = 0 (no AI chars)", close(p02.value, 0), `got ${p02.value}`);

// --- categorical shares sum to 1, declared order honoured ---
const authorship = findMetric("code_authorship");
const obsAi = authorship.extract(authorshipRows).filter((o) => o.condition === "ai-assisted");
const order = categoryOrder(obsAi, authorship.categories);
ok("declared category order wins (ai before human)", order[0] === "ai" && order[1] === "human");
const { total, shares } = categoryShares(obsAi, order);
ok("categorical weight total is sum of chars", total === 600, `got ${total}`);
ok("categorical shares sum to 1", close(shares.reduce((a, s) => a + s.share, 0), 1));
ok("ai share = 300/600 = 0.5", close(shares.find((s) => s.category === "ai").share, 0.5));

// categoryOrder appends undeclared categories after declared, sorted.
const mixed = categoryOrder(
  [{ category: "zebra" }, { category: "ai" }, { category: "apple" }],
  ["ai", "human"],
);
ok("undeclared categories sort after declared ones", mixed.join(",") === "ai,apple,zebra");

// --- comprehension drops null, scores bool ---
const probeRows = [
  row({ type: "comprehension_probe_response", payload: { correct: true } }),
  row({ type: "comprehension_probe_response", payload: { correct: false } }),
  row({ type: "comprehension_probe_response", payload: { correct: null } }),
  row({ type: "comprehension_probe_response", payload: {} }),
];
const probeObs = findMetric("comprehension_correct").extract(probeRows);
ok("ungradable comprehension probes are dropped", probeObs.length === 2, `kept ${probeObs.length}`);
ok("comprehension categories are correct/incorrect", probeObs.map((o) => o.category).sort().join(",") === "correct,incorrect");

// --- ordinal counts, never averaged ---
const fatigueRows = [1, 1, 4, 7].map((value) => row({ type: "fatigue_response", payload: { value, points: 7 } }));
const fatigue = findMetric("fatigue");
const fObs = fatigue.extract(fatigueRows);
const counts = ordinalCounts(fObs, fatigue.levels);
ok("ordinal counts place values on the right levels", counts[0] === 2 && counts[3] === 1 && counts[6] === 1, counts.join(","));
ok("ordinal count total equals n", counts.reduce((a, b) => a + b, 0) === 4);

// fatigue reads `score` too (simulator / analysis convention), not only `value`
const scoreRows = [2, 2, 5].map((score) => row({ type: "fatigue_response", payload: { score } }));
const scoreCounts = ordinalCounts(fatigue.extract(scoreRows), fatigue.levels);
ok("fatigue reads the simulator's `score` key", scoreCounts[1] === 2 && scoreCounts[4] === 1, scoreCounts.join(","));

// --- task pass-rate categorical ---
const taskRows = [true, false, true].map((passed) => row({ type: "task_outcome", source: "agent-capture", payload: { passed, failed: passed ? 0 : 1, total: 1 } }));
const taskObs = findMetric("task_pass_rate").extract(taskRows);
ok("task_pass_rate categorises passed/failed", taskObs.filter((o) => o.category === "passed").length === 2);

// task_pass_rate drops zero-test outcomes (no suite ran: passed:false, total:0)
const taskZero = [
  row({ type: "task_outcome", source: "agent-capture", payload: { passed: true, failed: 0, total: 1 } }),
  row({ type: "task_outcome", source: "agent-capture", payload: { passed: false, failed: 0, total: 0 } }),
];
ok("task_pass_rate drops total:0 outcomes", findMetric("task_pass_rate").extract(taskZero).length === 1);

// agent_latency counts assistant turns only (user turns also carry latencyMs)
const turnRows = [
  row({ type: "agent_turn", source: "agent-capture", payload: { role: "assistant", latencyMs: 1200 } }),
  row({ type: "agent_turn", source: "agent-capture", payload: { role: "user", latencyMs: 9000 } }),
];
const lat = findMetric("agent_latency").extract(turnRows);
ok("agent_latency excludes user turns", lat.length === 1 && lat[0].value === 1200, `n=${lat.length}`);

// static metrics accept the in-browser rehearsal shape (source synthetic, type metric)
const rehearsalRows = [row({ source: "synthetic", type: "metric", payload: { cognitive_complexity: 6 } })];
ok("static metrics accept synthetic rehearsal rows", findMetric("cognitive_complexity").extract(rehearsalRows).length === 1);

// --- populatedMetrics ---
const populated = populatedMetrics([
  row({ source: "metrics", type: "function_metrics", payload: { cognitive_complexity: 5 } }),
  row({ type: "fatigue_response", payload: { value: 3, points: 7 } }),
]);
ok("populatedMetrics finds cognitive_complexity", populated.has("cognitive_complexity"));
ok("populatedMetrics finds fatigue", populated.has("fatigue"));
ok("populatedMetrics omits metrics with no rows", !populated.has("task_pass_rate"));

// --- summarize ---
const s = summarize([1, 2, 3, 4, 5]);
ok("summarize n/median/min/max", s.n === 5 && s.median === 3 && s.min === 1 && s.max === 5);
ok("summarize returns null for empty", summarize([]) === null);

console.log(failures === 0 ? "\n✓ all checks pass" : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
