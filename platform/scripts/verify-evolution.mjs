/* Exercises the offline evolution store — the surfaces the
 * amendment banner and history list render from.
 * Run:  node --experimental-strip-types scripts/verify-evolution.mjs
 *
 * Checks that:
 *   - the seeded amendment state is consistent (a consent-relevant amendment
 *     awaits re-approval → the banner shows the paused register)
 *   - recording re-approval lifts the pause and stamps the artifact
 */
import { evolutionStore } from "../src/lib/evolutionStub.ts";

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

console.log(failures === 0
  ? "\n✓ all checks pass"
  : `\n✗ ${failures} check(s) failed`);
process.exit(failures === 0 ? 0 : 1);
