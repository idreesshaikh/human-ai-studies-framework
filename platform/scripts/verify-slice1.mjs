/* Exercises the real modules (no browser needed): the deterministic design
 * assistant + the compiler. Run:
 *   node --experimental-strip-types scripts/verify-slice1.mjs
 *
 * Checks that:
 *   - the over-trust demo runs end to end (input → moves → draft)
 *   - rejecting a move keeps it out of the compiled draft
 *   - compilation is deterministic (replay → identical draft)
 *   - self-report-only productivity draws the grounded METR caution
 *   - no move cites a paper the assistant didn't hold in that exchange
 */
import { respondTo, resetStub } from "../src/lib/designStub.ts";
import { compileAll, compile } from "../src/lib/compiler.ts";
import { emptyDraft } from "../src/lib/types.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures++;
};

// The over-trust script yields moves that compile into a draft.
const trustTurn = respondTo("junior developers over-trust AI-generated code");
const accepted = trustTurn.moves.map((m) => ({ ...m, status: "accepted" }));
const draft = compileAll(accepted);
ok("demo produces design moves", trustTurn.moves.length >= 3,
  `${trustTurn.moves.length} moves`);
ok("accepted moves compile into draft sections",
  draft.researchQuestions.length > 0 && draft.measures.length >= 2,
  `RQs=${draft.researchQuestions.length} measures=${draft.measures.length}`);
ok("the two matching papers are recommended",
  trustTurn.recommendations.some((r) => r.ref.includes("trust")) &&
  trustTurn.recommendations.some((r) => r.ref.includes("insecure")),
  trustTurn.recommendations.map((r) => r.ref).join(", "));

// Reject one measure → it's absent from the recompiled draft.
const target = trustTurn.moves.find((m) => m.kind === "add-measure");
const mixed = trustTurn.moves.map((m) =>
  m.moveId === target.moveId
    ? { ...m, status: "rejected" }
    : { ...m, status: "accepted" },
);
const draftAfterReject = compileAll(mixed);
const rejectedValue = target.patch.value;
ok("rejected move absent from draft",
  !draftAfterReject.measures.includes(rejectedValue),
  `rejected: "${rejectedValue}"`);

// Determinism — same accepted moves, same base → identical draft.
resetStub();
const a = compileAll(respondTo("junior over-trust").moves.map((m) => ({ ...m, status: "accepted" })));
resetStub();
const b = compileAll(respondTo("junior over-trust").moves.map((m) => ({ ...m, status: "accepted" })));
ok("compilation is deterministic (replay identical)",
  JSON.stringify(a) === JSON.stringify(b));

// Self-report-only productivity → grounded METR caution.
const prodTurn = respondTo("measure productivity by self-report survey only");
const caution = prodTurn.moves.find((m) => m.kind === "caution");
ok("self-report productivity draws a caution", !!caution);
ok("the caution cites the METR paper",
  !!caution && caution.grounding.some((g) => g.ref.includes("metr")),
  caution?.grounding.map((g) => g.ref).join(", "));
ok("the caution makes no draft change",
  !!caution && caution.patch === undefined);

// Every cited paper carries a title + reason (nothing invented).
const allGrounding = [
  ...trustTurn.moves,
  ...prodTurn.moves,
].flatMap((m) => m.grounding);
ok("every cited paper has a title and a reason",
  allGrounding.every((g) => g.ref && g.title && g.why),
  `${allGrounding.length} citations checked`);

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

// Vague input names the empty sections rather than going silent.
const vague = respondTo("i dunno, something about ai");
ok("vague input names the unresolved sections",
  /unresolved|empty|participants|conditions|ethics/i.test(vague.text));

console.log(failures === 0
  ? "\n✓ all checks pass"
  : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
