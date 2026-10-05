/* Run: node --experimental-strip-types scripts/verify-stream-recovery.mjs
 * A failed reply stream may be resent through the blocking endpoint only when it
 * failed before any event arrived and the researcher did not press Stop;
 * otherwise the error is surfaced and their text stays theirs to resend. */
import { shouldResendAfterStreamFailure } from "../src/lib/streamRecovery.ts";

let failures = 0;
const ok = (name, cond) => {
  console.log(`${cond ? "✓" : "✗"} ${name}`);
  if (!cond) failures++;
};

ok("no event yet, not aborted: resend", shouldResendAfterStreamFailure({ aborted: false, eventsReceived: 0 }) === true);
ok("events already received: surface, do not resend", shouldResendAfterStreamFailure({ aborted: false, eventsReceived: 2 }) === false);
ok("Stop pressed: never resend", shouldResendAfterStreamFailure({ aborted: true, eventsReceived: 0 }) === false);

if (failures) process.exit(1);
