/* Setup-conversation QA fixes: decision follow-up rule, state labels, rail
 * values, review text, manual-entry pre-checks, and the source-level a11y
 * wiring. Run: node --experimental-strip-types scripts/verify-conversation-polish.mjs */
import { readFileSync, readdirSync } from "node:fs";
import {
  moveEyebrow,
  nextStepPrompt,
  shouldFollowUpAfterDecision,
  moveStateLabel,
  cleanProposalText,
  measureOptionsFromMoves,
} from "../src/lib/uiText.ts";
import { formatSlotValue, summarizeProtocol } from "../src/lib/protocolFormat.ts";
import { RECIPE_LABELS, recipeLabel } from "../src/lib/recipeLabels.ts";
import { targetLabel } from "../src/lib/types.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
const src = (p) => readFileSync(new URL(`../src/${p}`, import.meta.url), "utf8");

/* 1. follow-up only when nothing else is pending */
const card = (moveId, status) => ({ moveId, status });
ok("one of three pending: no follow-up",
  shouldFollowUpAfterDecision([card("a", "proposed"), card("b", "proposed"), card("c", "proposed")], "a") === false);
ok("last pending card: follow-up",
  shouldFollowUpAfterDecision([card("a", "accepted"), card("b", "rejected"), card("c", "proposed")], "c") === true);
ok("a lone card: follow-up", shouldFollowUpAfterDecision([card("a", "proposed")], "a") === true);
ok("undo never follows up",
  shouldFollowUpAfterDecision([card("a", "accepted")], "a", "proposed") === false);
ok("no cards: no follow-up", shouldFollowUpAfterDecision([], "a") === false);
const cv = src("components/conversation/ConversationView.tsx");
ok("decide uses the rule", /shouldFollowUpAfterDecision\(/.test(cv));
ok("decide no longer drops clicks while busy", !/if \(!move \|\| busy\) return;/.test(cv));
ok("a queued follow-up is sent after the stream", /queuedFollowUp/.test(cv));
ok("pending cards of older turns stay visible",
  /Pending choices stay/.test(cv));
ok("Stopped note lives in a status region", /role="status"/.test(cv));
ok("undo returns focus to the card", /data-move-id=.*focus|focusDecidedCard|returnFocusTo/.test(cv));

/* 2. state labels */
ok("accepted label", moveStateLabel("accepted", "add-measure") === "Accepted");
ok("rejected label", moveStateLabel("rejected", "add-measure") === "Rejected");
ok("caution noted", moveStateLabel("accepted", "caution") === "Noted");
ok("merge merged", moveStateLabel("accepted", "merge-templates") === "Merged");
ok("MoveCard no 'dismissed'", !/dismissed/i.test(src("components/conversation/MoveCard.tsx")));

/* 3. rail values */
const f = formatSlotValue;
ok("design prefix stripped + hyphen kept", f("design", "design: within-subjects") === "Within-subjects", f("design", "design: within-subjects"));
ok("design plain", f("design", "within-subjects") === "Within-subjects");
ok("participants design line", f("participants", "design: within-subjects") === "Within-subjects");
ok("planned count", f("participants", "12 planned") === "12 participants", f("participants", "12 planned"));
ok("planned count singular", f("participants", "1 planned") === "1 participant");
ok("population kept", f("participants", "professional developers") === "Professional developers");
ok("conditions case", f("conditions", "ai-assisted") === "AI-assisted", f("conditions", "ai-assisted"));
ok("conditions separators", f("conditions", "ai-assisted,unassisted") === "AI-assisted, unassisted");
ok("measures separators", f("measures", "task completion time,solution correctness") === "Task completion time, solution correctness", f("measures", "task completion time,solution correctness"));
ok("recipe id mapped", f("statisticalPlan", "paired-nonparametric") === recipeLabel("paired-nonparametric") && !/paired-nonparametric/.test(f("statisticalPlan", "paired-nonparametric")));
ok("instrument metrics", f("instruments", "metrics") === "Metrics");
ok("instrument TERN", f("instruments", "TERN") === "TERN");
ok("ethics pending", f("ethics", "pending: not yet obtained") === "Not yet obtained", f("ethics", "pending: not yet obtained"));
ok("unknown recipe humanised", recipeLabel("some-new-recipe") === "Some new recipe");
const section = summarizeProtocol({
  participants: { planned: 12, design: "within-subjects" },
  analysisPlan: [{ rq: "RQ1", recipes: ["paired-nonparametric", "tlx-debrief"] }],
});
const flat = section.flatMap((s) => s.lines).join(" | ");
ok("section view: no raw design or recipe ids", !/within subjects|paired-nonparametric|tlx-debrief/.test(flat), flat);

/* every recipe the analysis package defines has a label */
const dir = new URL("../../analysis/src/analysis/recipes/", import.meta.url);
const ids = readdirSync(dir)
  .filter((n) => n.endsWith(".py") && !n.startsWith("_"))
  .flatMap((n) => [...readFileSync(new URL(n, dir), "utf8").matchAll(/^\s*id="([a-z0-9-]+)"/gm)].map((m) => m[1]));
ok("found analysis recipe ids", ids.length >= 10, String(ids.length));
const missing = ids.filter((id) => !(id in RECIPE_LABELS));
ok("every analysis recipe has a plain label", missing.length === 0, missing.join(","));

/* 4. review text */
ok("strip Declare the task prefix + double period",
  cleanProposalText("Declare the task: Fix a bug in the app..") === "Fix a bug in the app.",
  cleanProposalText("Declare the task: Fix a bug in the app.."));
ok("ellipsis kept", cleanProposalText("Wait...") === "Wait...");
ok("target label has no slot leak", targetLabel("participants.description") === "Participants", targetLabel("participants.description"));
ok("target label keeps real detail", targetLabel("session.durationMinutes") === "Session • Duration minutes");
const fr = src("components/conversation/FinishReview.tsx");
ok("review cleans proposals", /cleanProposalText\(/.test(fr));
ok("warnings wrap", /break-words/.test(fr.slice(fr.indexOf("warnings.map"))));

/* 5. manual dialog */
const opts = ["task completion time", "solution correctness", "cognitive load", "code comprehension"];
ok("accepted measures pre-check matching options",
  JSON.stringify(measureOptionsFromMoves([
    { status: "accepted", kind: "add-measure", proposal: "Measure Task completion time.", patch: { section: "measures", op: "append", value: "task completion time" } },
    { status: "rejected", kind: "add-measure", proposal: "cognitive load" },
    { status: "accepted", kind: "add-measure", proposal: "Track Solution Correctness" },
    { status: "accepted", kind: "add-rq", proposal: "code comprehension?" },
  ], opts)) === JSON.stringify(["task completion time", "solution correctness"]));
const md = src("components/conversation/ManualProtocolDialog.tsx");
ok("participants text renamed", /Who takes part/.test(md) && !/>Participants<\/Label>/.test(md));
ok("outcomes error scrolls into view", /scrollIntoView/.test(md) && /outcomes-error/.test(md));
ok("dialog takes accepted measures", /measureOptionsFromMoves/.test(md) && /moves=\{allMoves\}/.test(cv));

/* 7 steer */
const sd = src("components/conversation/SteerDial.tsx");
ok("steer shows its mode name", /\{stop\.label\}/.test(sd));

/* 8 expert-thread polish: eyebrows, one decisions disclosure, rail next step, a11y */
ok("eyebrow: set-parameter on participants", moveEyebrow("set-parameter", { section: "participants" }) === "Participants");
ok("eyebrow: statistical plan is Analysis", moveEyebrow("set-parameter", { section: "statisticalPlan" }) === "Analysis");
ok("eyebrow: conditions section", moveEyebrow("add-measure", { section: "conditions" }) === "Conditions");
ok("eyebrow: plain set-parameter is Setting", moveEyebrow("set-parameter") === "Setting");
ok("eyebrow: measure/task/design/caution",
  moveEyebrow("add-measure") === "Measure" && moveEyebrow("declare-task") === "Task" &&
  moveEyebrow("choose-template") === "Design" && moveEyebrow("caution") === "Caution" &&
  moveEyebrow("add-rq") === "Research question" && moveEyebrow("prescribe-statistics") === "Analysis" &&
  moveEyebrow("add-instrument") === "Instrument");
ok("next-step prompt names the section and is not empty", /conditions/i.test(nextStepPrompt("Conditions")));
const mc = src("components/conversation/MoveCard.tsx");
ok("card uses moveEyebrow", /moveEyebrow\(/.test(mc) && !/"Parameter"/.test(mc));
ok("card handles u to undo", /"u"/.test(mc));
const ul = src("components/conversation/UnsourcedLabel.tsx");
ok("unsourced label wording", /No source: your call/.test(ul));
const stt = src("components/conversation/StreamingTurn.tsx");
ok("one Decisions (N) disclosure",
  /Decisions \(/.test(stt) && !/View recorded decisions/.test(stt) && !/View decisions/.test(cv) && /Decisions \(/.test(cv));
ok("keyboard hint caption with tooltip", /Keyboard shortcuts/.test(stt) && /A accept/.test(stt));
ok("stream is not a live region; completion is announced once",
  !/aria-live="polite">\s*\{streamingText\}/.test(cv) && /data-testid="turn-announcer"/.test(cv));
ok("thinking dots respect reduced motion", /motion-reduce:animate-none/.test(cv));
const dr = src("components/conversation/DraftRail.tsx");
ok("rail answers where and next", /drafted\./.test(dr) && /onNextStep/.test(dr) && /onNextStep=/.test(cv));
ok("canned copy has no apology", !/Couldn't|couldn't|Sorry/.test(cv.match(/setNote\([^)]*\)/g)?.join("") ?? ""));
console.log(failures ? `\n${failures} failed` : "\nall passed");
process.exit(failures ? 1 : 0);
