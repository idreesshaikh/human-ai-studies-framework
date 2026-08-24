/* Exercises the protocol path  -  the ordered list of what the conversation
 * still needs, shown so a researcher can estimate how long the chat will be.
 * Run:
 *   node --experimental-strip-types scripts/verify-protocol-path.mjs
 *
 * Checks that:
 *   - the two phases appear in the order the conversation actually walks
 *     them (current focus, then fill the protocol)
 *   - exactly ONE step on the whole path is "current"  -  the cursor is what
 *     makes it a path rather than a checklist, and two of them is worse than
 *     none
 *   - once the idea is understood, the current step is the first unfilled
 *     protocol section
 *   - the focus row is orientation, not a sixth protocol requirement
 *   - the count stays at seven core protocol sections, so it cannot become a
 *     misleading 13-step checklist
 *   - the next question is passed through from the server, never composed
 *   - the path still builds before the first turn returns, when there is no
 *     understanding at all
 */
import { buildProtocolPath } from "../src/lib/protocolPath.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

const EMPTY_DRAFT = {
  researchQuestions: [],
  design: [],
  participants: [],
  conditions: [],
  measures: [],
  instruments: [],
  statisticalPlan: [],
  ethics: [],
};

const understanding = ({ known = [], nextQuestion = "" }) => {
  const ids = ["population", "task", "comparison", "outcome", "constraints"];
  const missing = ids.filter((id) => !known.includes(id));
  return {
    facets: Object.fromEntries(ids.map((id) => [id, known.includes(id)])),
    known,
    missing,
    missingLabels: missing.map((id) => `label:${id}`),
    facetLabels: Object.fromEntries(ids.map((id) => [id, `label:${id}`])),
    readyForDesign: known.length >= 3,
    facetsNeeded: 3,
    nextQuestion,
  };
};

const currents = (path) =>
  path.phases.flatMap((p) => p.steps).filter((s) => s.status === "current");

// --- early: nothing known, nothing drafted ---------------------------------
const fresh = buildProtocolPath(
  EMPTY_DRAFT,
  understanding({ known: [], nextQuestion: "Who takes part?" }),
);

ok(
  "phases run understand -> fill",
  fresh.phases.map((p) => p.title).join(" | ") ===
    "Current focus | Filling the protocol",
  fresh.phases.map((p) => p.title).join(" | "),
);

ok("exactly one current step", currents(fresh).length === 1, `${currents(fresh).length}`);

ok(
  "the cursor starts on the first unknown facet",
  currents(fresh)[0].id === "focus",
  currents(fresh)[0].id,
);

ok(
  "counts span both phases",
  fresh.total === 7 && fresh.done === 0,
  `${fresh.done} / ${fresh.total}`,
);

ok(
  "the next question is the server's",
  fresh.upNext === "Who takes part?",
  fresh.upNext,
);

// --- the current focus stays a single orientation row ----------------------
const skipped = buildProtocolPath(
  EMPTY_DRAFT,
  understanding({ known: ["population", "task"] }),
);
ok(
  "the focus row carries the next missing facet",
  currents(skipped)[0].id === "focus" && skipped.phases[0].steps[0].label === "label:comparison",
  currents(skipped)[0].id,
);
ok(
  "the focus row is not counted as protocol progress",
  skipped.done === 0,
  `${skipped.done}`,
);

// --- the cursor crosses into phase two -------------------------------------
const allFacets = buildProtocolPath(
  EMPTY_DRAFT,
  understanding({
    known: ["population", "task", "comparison", "outcome", "constraints"],
  }),
);
ok(
  "with the idea understood, the cursor moves to the first empty section",
  currents(allFacets).length === 1 &&
    currents(allFacets)[0].id === "slot:researchQuestions",
  currents(allFacets)[0]?.id,
);

// --- a partly filled draft -------------------------------------------------
const partly = buildProtocolPath(
  { ...EMPTY_DRAFT, researchQuestions: ["RQ-1"], design: ["within-subjects"] },
  understanding({
    known: ["population", "task", "comparison", "outcome", "constraints"],
  }),
);
ok(
  "a filled section is done and the cursor sits after it",
  currents(partly)[0].id === "slot:participants",
  currents(partly)[0].id,
);
ok("counts include filled sections", partly.done === 2, `${partly.done} / ${partly.total}`);

// --- before the first turn returns -----------------------------------------
const noUnderstanding = buildProtocolPath(EMPTY_DRAFT, undefined);
ok(
  "the path still builds with no understanding yet",
  noUnderstanding.phases.length === 1 && noUnderstanding.total === 7,
  `${noUnderstanding.phases.length} phase(s), ${noUnderstanding.total} steps`,
);
ok(
  "and asks nothing it was not told to ask",
  noUnderstanding.upNext === "",
);

console.log(failures === 0 ? "\n✓ protocol path" : `\n✗ ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
