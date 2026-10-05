/* Run: node --experimental-strip-types scripts/verify-compile-notices.mjs
 * Compile warnings that say the compiler changed or ignored what the researcher
 * stated must be separated out so the review can show them as a visible notice. */
import { splitCompileWarnings } from "../src/lib/compileNotices.ts";

let failures = 0;
const ok = (name, cond) => {
  console.log(`${cond ? "✓" : "✗"} ${name}`);
  if (!cond) failures++;
};

const { altered, other } = splitCompileWarnings([
  "ignored how many participants = 'lots': not a valid integer for participants.planned",
  "mapped the legacy taskTimer move to the valid TERN capture instrument",
  "added missing standard TERN capture settings (stuck.enabled); your values were kept",
  "some neutral note",
]);
ok("ignored input is flagged", altered[0].startsWith("Ignored how many"));
ok("remapped input is flagged", altered.length === 3);
ok("first letter is capitalised for display", altered[1].startsWith("Mapped"));
ok("neutral warnings stay in the quiet list", other.length === 1 && other[0] === "some neutral note");
ok("undefined input is safe", splitCompileWarnings(undefined).altered.length === 0);

const assumed = splitCompileWarnings([
  "Session length was not stated, so 45 minutes was assumed",
  "Added from the Within-subjects crossover template: research questions RQ-1, RQ-2",
  "some neutral note",
]);
ok("an assumed default is flagged", assumed.altered[0]?.startsWith("Session length was not stated"));
ok("template-supplied content is flagged", assumed.altered.length === 2);
ok("neutral stays quiet next to assumptions", assumed.other.length === 1);

if (failures) process.exit(1);
