/* Exercises the client-side protocol compiler (no browser needed). Run:
 *   node --experimental-strip-types scripts/verify-slice1.mjs
 *
 * This used to drive the client's design stub — a keyword-scripted stand-in
 * for the conversation that answered whenever the server was unreachable.
 * The stub is gone (the conversation requires a model and says so when it
 * has none), so the moves below are written out here instead. They are the
 * same shapes the server sends, which is what these checks are about: every
 * move kind the conversation can propose has to land in the draft preview,
 * or an accepted move reads as "noted" and silently changes nothing.
 */
import { compileAll, compile } from "../src/lib/compiler.ts";
import { emptyDraft } from "../src/lib/types.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures++;
};

const move = (moveId, kind, section, value, status = "accepted") => ({
  moveId,
  kind,
  target: `${section}[]`,
  proposal: value,
  patch: { section, op: "append", value },
  grounding: [],
  status,
});

// Accepted moves land in the draft's sections.
const accepted = [
  move("m1", "add-rq", "researchQuestions", "Do juniors review AI code less?"),
  move("m2", "add-measure", "measures", "Review latency"),
  move("m3", "add-measure", "measures", "Acceptance-test pass rate"),
];
const draft = compileAll(accepted);
ok("accepted moves compile into draft sections",
  draft.researchQuestions.length === 1 && draft.measures.length === 2,
  `RQs=${draft.researchQuestions.length} measures=${draft.measures.length}`);

// Rejecting one keeps it out, and re-folding removes its effect cleanly.
const mixed = accepted.map((m) =>
  m.moveId === "m2" ? { ...m, status: "rejected" } : m,
);
ok("rejected move absent from draft",
  !compileAll(mixed).measures.includes("Review latency"));

// Determinism — same accepted moves, same base → identical draft.
ok("compilation is deterministic (replay identical)",
  JSON.stringify(compileAll(accepted)) === JSON.stringify(compileAll(accepted)));

// A caution carries no patch, so it must change nothing.
const cautionDraft = compileAll([
  ...accepted,
  {
    moveId: "m4",
    kind: "caution",
    target: "measures",
    proposal: "Self-reported speed diverges from measured speed.",
    patch: undefined,
    grounding: [],
    status: "accepted",
  },
]);
ok("an accepted caution makes no draft change",
  JSON.stringify(cautionDraft) === JSON.stringify(draft));

// A real choose-template move's patch is {templateId, parameters} - not
// the generic {section, op, value} shape every other move kind uses.
// Regression: the compiler only knew the generic shape, so accepting a
// choose-template move silently did nothing (shown as "noted" instead of
// "in draft", and the draft's mandatory `design` slot never filled, no
// matter how many other moves were accepted).
const templateMove = {
  moveId: "t1-m1",
  kind: "choose-template",
  target: "design",
  proposal: "Adopt the two-group RCT template.",
  patch: { templateId: "two-group-rct-v1", parameters: {} },
  grounding: [],
  status: "accepted",
};
const templateDraft = compile(emptyDraft(), [templateMove]);
ok("accepting a choose-template move fills the draft's design slot",
  templateDraft.design.includes("two-group-rct-v1"),
  templateDraft.design.join(", "));

// Same regression, for add-instrument's {section: "instruments", op, name,
// config} patch shape - also not the generic {section, op, value} shape, so
// it was also silently dropped from the preview (instruments stayed
// "unresolved" no matter what got accepted).
const instrumentMove = {
  moveId: "t1-m2",
  kind: "add-instrument",
  target: "instruments",
  proposal: "Add a post-task survey instrument.",
  patch: { section: "instruments", op: "add-instrument", name: "post-task-survey", config: {} },
  grounding: [],
  status: "accepted",
};
const instrumentDraft = compile(emptyDraft(), [instrumentMove]);
ok("accepting an add-instrument move fills the draft's instruments slot",
  instrumentDraft.instruments.includes("post-task-survey"),
  instrumentDraft.instruments.join(", "));

console.log(failures === 0
  ? "\n✓ all checks pass"
  : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
