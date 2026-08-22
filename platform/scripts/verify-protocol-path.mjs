/* Exercises the protocol path  -  the ordered list of what the conversation
 * still needs, shown so a researcher can estimate how long the chat will be.
 * Run:
 *   node --experimental-strip-types scripts/verify-protocol-path.mjs
 *
 * Checks that:
 *   - the two phases appear in the order the conversation actually walks
 *     them (understand the idea, then fill the protocol)
 *   - exactly ONE step on the whole path is "current"  -  the cursor is what
 *     makes it a path rather than a checklist, and two of them is worse than
 *     none
 *   - the cursor crosses the phase boundary: once every facet is known, the
 *     current step is the first unfilled protocol section
 *   - a known facet never claims the cursor, however late in the list it sits
 *   - the counts cover both phases, so "3 / 13" means what it says
 *   - a step already DONE is still named correctly  -  labels come from the
 *     server's facet map, not from pairing `missingLabels` by position,
 *     which mislabels every completed step as soon as one is known
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
    "Understanding your idea | Filling the protocol",
  fresh.phases.map((p) => p.title).join(" | "),
);

ok("exactly one current step", currents(fresh).length === 1, `${currents(fresh).length}`);

ok(
  "the cursor starts on the first unknown facet",
  currents(fresh)[0].id === "facet:population",
  currents(fresh)[0].id,
);

ok(
  "counts span both phases",
  fresh.total === 13 && fresh.done === 0,
  `${fresh.done} / ${fresh.total}`,
);

ok(
  "the next question is the server's",
  fresh.upNext === "Who takes part?",
  fresh.upNext,
);

// --- a known facet must not claim the cursor -------------------------------
const skipped = buildProtocolPath(
  EMPTY_DRAFT,
  understanding({ known: ["population", "task"] }),
);
ok(
  "a known facet is never current",
  currents(skipped)[0].id === "facet:comparison",
  currents(skipped)[0].id,
);
ok(
  "known facets count as done",
  skipped.done === 2,
  `${skipped.done}`,
);

const doneFacets = skipped.phases[0].steps.filter((s) => s.status === "done");
ok(
  "a completed step keeps its own label",
  doneFacets.map((s) => s.label).join(",") === "label:population,label:task",
  doneFacets.map((s) => s.label).join(","),
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
ok("counts include filled sections", partly.done === 7, `${partly.done} / ${partly.total}`);

// --- before the first turn returns -----------------------------------------
const noUnderstanding = buildProtocolPath(EMPTY_DRAFT, undefined);
ok(
  "the path still builds with no understanding yet",
  noUnderstanding.phases.length === 1 && noUnderstanding.total === 8,
  `${noUnderstanding.phases.length} phase(s), ${noUnderstanding.total} steps`,
);
ok(
  "and asks nothing it was not told to ask",
  noUnderstanding.upNext === "",
);

console.log(failures === 0 ? "\n✓ protocol path" : `\n✗ ${failures} failure(s)`);
process.exit(failures === 0 ? 0 : 1);
