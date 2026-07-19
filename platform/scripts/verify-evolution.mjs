/* Exercises the offline evolution store — the surfaces the
 * amendment banner, history list, and platform-findings lineage render from.
 * Run:  node --experimental-strip-types scripts/verify-evolution.mjs
 *
 * Checks that:
 *   - the seeded amendment state is consistent (a consent-relevant amendment
 *     awaits re-approval → the banner shows the paused register)
 *   - recording re-approval lifts the pause and stamps the artifact
 *   - marking a turn as feedback files a finding with its conversation locus
 *   - the drafted proposal is inert and cites the findings it used (F5.2)
 */
import {
  evolutionStore,
  deriveProposal,
} from "../src/lib/evolutionStub.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? ` — ${detail}` : ""}`);
  if (!cond) failures++;
};

// The seed is a study mid-evolution: ethics-approved, with a consent-relevant
// amendment awaiting re-approval (the paused banner).
let snap = evolutionStore.getSnapshot();
ok("seeded study is under ethics approval",
  !!snap.amendmentState.ethicsApprovedAt);
ok("a consent-relevant amendment awaits re-approval (paused)",
  !!snap.amendmentState.pendingReapproval);
const pausedId = snap.amendmentState.pendingReapproval;
const pausedAmendment = snap.amendmentState.amendments.find((a,) => a.id === pausedId);
ok("the pending amendment is consent-relevant and not yet re-approved",
  !!pausedAmendment && pausedAmendment.consentRelevant &&
    !pausedAmendment.reapprovalArtifact);

// A resolved consent-relevant amendment and a calm config tweak coexist (both
// registers visible in the history).
ok("history shows a resolved consent-relevant amendment",
  snap.amendmentState.amendments.some(
    (a,) => a.consentRelevant && a.reapprovalArtifact));
ok("history shows a non-consent config change",
  snap.amendmentState.amendments.some((a,) => !a.consentRelevant));

// Recording re-approval lifts the pause and stamps the artifact.
evolutionStore.recordReapproval("ethics-reapproval.pdf");
snap = evolutionStore.getSnapshot();
ok("re-approval lifts the session pause", !snap.amendmentState.pendingReapproval);
ok("re-approval stamps the artifact on the amendment",
  snap.amendmentState.amendments.find((a,) => a.id === pausedId)
    ?.reapprovalArtifact === "ethics-reapproval.pdf");

// Marking a turn as feedback files a finding with its locus.
const before = snap.findings.length;
const finding = evolutionStore.markFeedback({
  studyId: "sample-study-2026",
  turnId: "t-42",
  seq: 42,
  note: "the diff is hard to scan",
  kind: "ux-defect",
});
snap = evolutionStore.getSnapshot();
ok("marking a turn files a finding", snap.findings.length === before + 1);
ok("the finding carries its conversation locus",
  finding.locus.turnId === "t-42" && finding.locus.seq === 42 &&
    finding.locus.kind === "ux-defect");

// The drafted proposal is inert and cites the findings it used (F5.2).
const proposal = deriveProposal(snap.findings);
ok("the proposal is an inert draft", proposal.status === "draft");
ok("the proposal cites its findings",
  proposal.citedFindingIds.length === snap.findings.length &&
    proposal.citedFindingIds.includes(finding.id),
  `cited ${proposal.citedFindingIds.length}`);
ok("the proposal drafts at least one item", proposal.items.length >= 1);

console.log(failures === 0
  ? "\n✓ all checks pass"
  : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
