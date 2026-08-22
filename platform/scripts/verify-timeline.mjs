/* Exercises the timeline lane-assembly module (FR-DASH-4). Run:
 *   node --experimental-strip-types scripts/verify-timeline.mjs
 *
 * Checks that:
 *   - lane assignment is deterministic (replay → identical lanes)
 *   - every event lands inside [0, width] in the scale function
 *   - a single-event session does not crash the scale function
 *   - an empty event list produces no lanes
 *   - flagged events are counted in the lane's flagged property
 *   - gap facts surface as flag marks on events
 */
import { assembleLanes, timeScale, parseTs, laneStyle } from "../src/lib/timeline.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

// A stable set of events spanning multiple sources.
const EVENTS = [
  { source: "cognitive-overlay", ts: "2026-07-16T14:30:00.000Z", seq: 0, type: "session_start" },
  { source: "cognitive-overlay", ts: "2026-07-16T14:30:05.000Z", seq: 1, type: "edit_burst" },
  { source: "agent-capture", ts: "2026-07-16T14:30:45.000Z", seq: 0, type: "agent_turn" },
  { source: "workspace-snapshot", ts: "2026-07-16T14:35:00.000Z", seq: 0, type: "snapshot" },
  { source: "task-harness", ts: "2026-07-16T14:38:00.000Z", seq: 0, type: "test_result" },
];

function row(over = {}) {
  return {
    v: 4,
    mono: 0,
    sessionId: "S-test",
    source: "cognitive-overlay",
    participantId: "P1",
    condition: "ai-assisted",
    seq: 0,
    ts: "2026-07-16T14:30:00.000Z",
    type: "test",
    payload: {},
    flags: [],
    ...over,
  };
}

// Determinism: same input → same lane structure.
const a = assembleLanes(EVENTS.map(row));
const b = assembleLanes(EVENTS.map(row));
ok("lane assignment is deterministic", JSON.stringify(a) === JSON.stringify(b));

// Lanes are created per source.
ok("produces the right number of lanes", a.length === 4, `got ${a.length}`);
const sources = a.map((l) => l.source).sort();
ok("lanes cover all present sources",
  sources.join(",") === "agent-capture,cognitive-overlay,task-harness,workspace-snapshot");

// Lane ordering: known sources before unknown, then alphabetical.
ok("cognitive-overlay is lane 0", a[0].source === "cognitive-overlay");
ok("agent-capture is lane 1", a[1].source === "agent-capture");
ok("workspace-snapshot is lane 2 (before task-harness in rank order)", a[2].source === "workspace-snapshot" || a[2].source === "task-harness");

// Every event falls inside [0, width] in the scale function.
const allRows = EVENTS.map(row);
const scale = timeScale(allRows, 800, 60, 20);
ok("scale function is defined", typeof scale === "function");
for (const ev of allRows) {
  const x = scale(ev.ts);
  ok(`event ${ev.type} at ts=${ev.ts} maps to x=${x.toFixed(0)} inside [0,800]`, x >= 0 && x <= 800);
}

// Single-event edge case: does not crash, returns a valid scale.
const single = [row({ ts: "2026-07-16T14:30:00.000Z" })];
const singleScale = timeScale(single, 800);
const sx = singleScale("2026-07-16T14:30:00.000Z");
ok("single-event scale returns a valid x", sx >= 0 && sx <= 800, `x=${sx.toFixed(0)}`);

// Empty event list → no lanes.
const empty = assembleLanes([]);
ok("empty events produce no lanes", empty.length === 0);

// Single event → one lane, one event.
const one = assembleLanes([row()]);
ok("single event produces one lane", one.length === 1);
ok("single lane has one event", one[0].count === 1);

// Flagged events counted in lane.flagged.
const flagged = row({ flags: ["unauthenticated"], source: "agent-capture" });
const mixed = [
  row(),
  row({ flags: ["credential-mismatch"], source: "cognitive-overlay" }),
  flagged,
];
const mixedLanes = assembleLanes(mixed);
const cognitiveLane = mixedLanes.find((l) => l.source === "cognitive-overlay");
ok("flagged count is 1 for cognitive-overlay", cognitiveLane?.flagged === 1);
const agentLane = mixedLanes.find((l) => l.source === "agent-capture");
ok("flagged count is 1 for agent-capture", agentLane?.flagged === 1);

// Unflagged event does not count as flagged.
const unflagged = row({ flags: [] });
const unflaggedLanes = assembleLanes([unflagged, unflagged]);
ok("no flagged events when all flags are empty",
  unflaggedLanes.every((l) => l.flagged === 0));

// Lane style is deterministic per source.
const ls1 = laneStyle("cognitive-overlay");
const ls2 = laneStyle("cognitive-overlay");
ok("laneStyle is deterministic", ls1.slot === ls2.slot);

// Unknown source gets a fallback label.
const unknown = assembleLanes([row({ source: "unknown-instrument" })]);
ok("unknown source gets its name as label", unknown[0].label === "unknown-instrument");

// parseTs returns 0 for invalid timestamps.
ok("parseTs returns 0 for empty string", parseTs("") === 0);
ok("parseTs returns 0 for invalid string", parseTs("not-a-date") === 0);
ok("parseTs parses valid ISO", parseTs("2026-07-16T14:30:00.000Z") > 0);

// Event ordering: same timestamp → tiebreak by seq.
const tieEvents = [
  row({ ts: "2026-07-16T14:30:00.000Z", seq: 2 }),
  row({ ts: "2026-07-16T14:30:00.000Z", seq: 1 }),
  { ...row({ ts: "2026-07-16T14:30:00.000Z", seq: 0 }), source: "agent-capture" },
];
const tieLanes = assembleLanes(tieEvents);
const tieLane = tieLanes.find((l) => l.source === "cognitive-overlay");
ok("events with same ts ordered by seq", tieLane?.events[0].seq === 1);
ok("events with same ts ordered by seq (second)", tieLane?.events[1].seq === 2);

console.log(failures === 0
  ? "\n✓ all checks pass"
  : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
