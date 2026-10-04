/* Exercises the study-folder helpers used by the mint dialog. Run:
 *   node --experimental-strip-types scripts/verify-workspace-setting.mjs
 *
 * Checks that:
 *   - absolute, ~/ and file:// paths are accepted; relative paths, web
 *     addresses, archives, '..' and empty input are refused with a reason
 *   - the one-line description names what a link will open, or warns that
 *     nothing will
 *   - uploads must be a .zip within the size limit
 */
import {
  describeWorkspace,
  formatBytes,
  workspaceFileProblem,
  workspacePathProblem,
} from "../src/lib/workspaceSetting.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};

for (const good of ["/home/p/task", "~/task", "file:///home/p/task", "C:\\study\\task", "C:/study/task"]) {
  ok(`accepts ${good}`, workspacePathProblem(good) === null);
}
for (const bad of ["", "  ", "task", "./task", "https://github.com/o/r", "task.zip", "/a/../b"]) {
  ok(`refuses ${JSON.stringify(bad)}`, typeof workspacePathProblem(bad) === "string");
}

ok(
  "describes a path",
  describeWorkspace({ kind: "path", path: "/home/p/task", updatedAt: "" }) ===
    "Opens /home/p/task on each participant's computer",
);
ok(
  "describes an archive with its size",
  describeWorkspace({ kind: "archive", filename: "t.zip", sha256: "", size: 2048, updatedAt: "" }) ===
    "Downloads t.zip (2.0 KB) and opens it",
);
ok("warns when nothing is set", describeWorkspace({ kind: null }).startsWith("No study folder set"));
ok("formats bytes", formatBytes(512) === "512 B" && formatBytes(5 * 1024 * 1024) === "5.0 MB");

ok("accepts a small zip", workspaceFileProblem({ name: "t.ZIP", size: 10 }) === null);
ok("refuses a non-zip", typeof workspaceFileProblem({ name: "t.tar.gz", size: 10 }) === "string");
ok("refuses an oversized zip", typeof workspaceFileProblem({ name: "t.zip", size: 51 * 1024 * 1024 }) === "string");

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log("\nall workspace-setting checks passed");
