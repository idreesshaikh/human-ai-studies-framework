/* Live-observed UI defects (UI-1 .. UI-11): pure helpers plus source-level
 * checks for the markup and CSS that cannot be exercised without a browser.
 * Run:
 *   node --experimental-strip-types scripts/verify-ui-fixes.mjs
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  rejectedMoveText,
  plainErrorMessage,
  isMissingProtocolError,
  describeMintError,
  mintCountProblem,
  GRAIN_OPTIONS,
  captureTokenLabel,
  producerStateLabel,
  eventTypeLabel,
  enrollmentHeading,
  shortcutLabel,
  isMacPlatform,
  NAME_MAX_LENGTH,
  clampName,
  nextFocusAfterDecision,
  NEW_PROJECT_PATH,
  paletteProjects,
  sentenceCase,
  displayServerMessage,
  isFatalInviteError,
  plainMatchReason,
} from "../src/lib/uiText.ts";
import { compileOnOpenAllowed } from "../src/lib/role.ts";
import { documentTitle } from "../src/lib/documentTitle.ts";
import { themeToggleLabel } from "../src/lib/theme.ts";
import { humanSlug } from "../src/lib/slug.ts";
import { resolveStudyTab } from "../src/lib/studyTabs.ts";
import { rememberStudyName, studyDisplayName } from "../src/lib/studyNames.ts";
import { summarizeProducerStates } from "../src/components/enrollment/captureSummary.ts";

let failures = 0;
const ok = (name, cond, detail = "") => {
  console.log(`${cond ? "✓" : "✗"} ${name}${detail ? `  -  ${detail}` : ""}`);
  if (!cond) failures++;
};
const src = (p) => readFileSync(new URL(`../src/${p}`, import.meta.url), "utf8");

/* UI-1 */
const raw = new Error(
  "Error: Semantic Scholar: GET https://api.semanticscholar.org/x HTTP 404",
);
const shown = plainErrorMessage(raw, "That paper could not be added.");
ok("raw transport error becomes the fallback", shown === "That paper could not be added.", shown);
ok(
  "a plain server sentence is kept verbatim",
  plainErrorMessage(new Error("No paper with that id was found."), "x") ===
    "No paper with that id was found.",
);
ok(
  "an 'Error:' prefix is never shown",
  plainErrorMessage(new Error("Error: That id looks wrong."), "x") === "That id looks wrong.",
);
ok("a non-error falls back", plainErrorMessage(42, "fallback") === "fallback");
const lib = src("components/library/LibraryTab.tsx");
ok("Add paper no longer prints String(e)", !/String\(e\)/.test(lib));
ok("Add paper clears the input only on success", !/\)\.then\(\(\) => setIdInput\(""\)\)/.test(lib));
ok("Add paper error is a problem Notice", /<Notice kind="problem"/.test(lib));

/* UI-2 / UI-3 */
ok(
  "404 means no protocol",
  isMissingProtocolError({ status: 404, message: "whatever" }) === true,
);
ok(
  "'no protocol for study' text means no protocol",
  isMissingProtocolError(new Error("no protocol for study abc")) === true,
);
ok("other errors are not missing-protocol", isMissingProtocolError(new Error("boom")) === false);
ok(
  "minting with no protocol gives the Setup hint",
  describeMintError(new Error("no protocol for study zz")) ===
    "Apply the protocol first, in Setup.",
);
ok(
  "other mint errors keep the server sentence",
  describeMintError({ status: 422, message: "Too many links." }) === "Too many links.",
);
ok("count 0 is a problem", mintCountProblem("0") !== null);
ok("count empty is a problem", mintCountProblem("") !== null);
ok("count 101 is a problem", mintCountProblem("101") !== null);
ok("count 2.5 is a problem", mintCountProblem("2.5") !== null);
ok("count 7 is fine", mintCountProblem("7") === null);
ok(
  "grain labels are plain words",
  GRAIN_OPTIONS.map((o) => o.label).join("|") ===
    "Per participant|Per session",
);
ok(
  "grain values stay stable for the API",
  GRAIN_OPTIONS.map((o) => o.value).join() === "participant,session",
);
ok("stuck is labelled", captureTokenLabel("stuck") === "Stuck prompts");
ok("ideHealth is labelled", captureTokenLabel("ideHealth") === "IDE health");
ok("unknown camelCase is humanised", captureTokenLabel("fooBarBaz") === "Foo bar baz");
ok("agent-capture is labelled", captureTokenLabel("agent-capture") === "Agent capture");
ok(
  "producer summary uses labels, not raw ids",
  summarizeProducerStates({ tern: "enabled", "agent-capture": "enabled" }) ===
    "Agent capture on",
  summarizeProducerStates({ tern: "enabled", "agent-capture": "enabled" }),
);
const mint = src("components/enrollment/MintDialog.tsx");
ok("dialog says Create, not Mint", !/Mint (\d|links|enrollment)/.test(mint) && /Create /.test(mint));
ok("dialog validates the count before creating", /mintCountProblem\(/.test(mint));
const panel = src("components/enrollment/EnrollmentPanel.tsx");
ok(
  "Revoke is a real Button with a visible edge",
  /<Button[^>]*variant="outline"[^>]*onClick=\{\(\) => void revoke[^>]*>\s*Revoke/.test(panel.replace(/\n/g, " ")),
);
ok("sticky Revoke cell has a token background that matches the row", /sticky right-0[^"]*bg-bg/.test(panel));
ok("polling is gated on a loaded protocol", /if \(!ready\) return;/.test(panel));
ok("capture chips use the label helper", /captureTokenLabel\(/.test(panel));

/* UI-4 */
ok("3 links, none redeemed", enrollmentHeading(3, 0).title === "3 links created" && enrollmentHeading(3, 0).detail === "0 redeemed");
ok("1 link created, 1 redeemed", enrollmentHeading(1, 1).title === "1 link created" && enrollmentHeading(1, 1).detail === "1 redeemed");
ok("no links yet", enrollmentHeading(0, 0).title === "No links yet");

/* UI-5 */
ok("Mac shows the glyph", shortcutLabel(true) === "⌘K");
ok("other platforms show Ctrl K", shortcutLabel(false) === "Ctrl K");
ok("MacIntel is Mac", isMacPlatform({ platform: "MacIntel" }) === true);
ok("Win32 is not Mac", isMacPlatform({ platform: "Win32" }) === false);
ok("iPhone is Mac-like", isMacPlatform({ platform: "iPhone" }) === true);
ok("New project opens the composer by query", NEW_PROJECT_PATH === "/home?new=1");
const pal = paletteProjects([
  { slug: "a", name: "A", role: "owner", studyCount: 1, createdAt: "" },
  { slug: "d", name: "Demo project", role: "viewer", studyCount: 1, createdAt: "" },
]);
ok("palette lists a viewer project too", pal.map((p) => p.slug).join() === "a,d");
const sw = src("components/shell/ProjectSwitcher.tsx");
ok("palette reads the same source as /home", /listProjects\(\)/.test(sw));
ok("palette refreshes on open", /\[open/.test(sw));
ok("palette rows truncate with a tooltip", /truncate/.test(sw) && /title=\{/.test(sw));
const frame = src("components/shell/AppFrame.tsx");
ok("Projects page opens the composer from ?new=1", /get\("new"\)/.test(src("pages/Projects.tsx")));

/* UI-6 */
ok("name limit is 80", NAME_MAX_LENGTH === 80);
ok("clampName trims to the limit", clampName("x".repeat(120)).length === 80);
ok("Projects name input has maxLength", /maxLength=\{NAME_MAX_LENGTH\}/.test(src("pages/Projects.tsx")));
ok("ProjectHome study input has maxLength", /maxLength=\{NAME_MAX_LENGTH\}/.test(src("pages/ProjectHome.tsx")));
ok("QuickStart study input has maxLength", /maxLength=\{NAME_MAX_LENGTH\}/.test(src("pages/QuickStart.tsx")));
ok("project rows carry a title tooltip", /title=\{project\.name\}/.test(src("pages/Projects.tsx")));

/* UI-7 */
const moves = [
  { moveId: "a", status: "proposed" },
  { moveId: "b", status: "proposed" },
  { moveId: "c", status: "proposed" },
];
ok(
  "after deciding a, focus goes to the next undecided card b",
  JSON.stringify(nextFocusAfterDecision(moves, "a")) === JSON.stringify({ kind: "move", moveId: "b" }),
);
ok(
  "with nothing left, focus goes to the decided card's Undo",
  JSON.stringify(nextFocusAfterDecision([{ moveId: "a", status: "accepted" }], "a")) ===
    JSON.stringify({ kind: "undo", moveId: "a" }),
);
ok(
  "next skips cautions already decided and wraps to an earlier undecided one",
  JSON.stringify(
    nextFocusAfterDecision(
      [
        { moveId: "a", status: "proposed" },
        { moveId: "b", status: "accepted" },
        { moveId: "c", status: "accepted" },
      ],
      "c",
    ),
  ) === JSON.stringify({ kind: "move", moveId: "a" }),
);
const cv = src("components/conversation/ConversationView.tsx");
ok(
  "a new send clears the previous notice",
  /const researcherTurn: Turn[\s\S]{0,400}setNote\(null\)/.test(cv) ||
    /setNote\(null\);\s*\n\s*\/\/ Optimistic/.test(cv),
);
ok("batch banner is not a permanent state", /setBatchNote|acceptedTogether/.test(cv) === false || /setNote\(null\)/.test(cv));
ok(
  "composer ring lives on the wrapper via focus-within",
  /focus-within:(outline|ring)/.test(cv) && /composer[\s\S]{0,200}focus-ring-owned|focus-ring-owned[\s\S]{0,400}Message the design assistant/.test(cv),
);
const st = src("components/conversation/StreamingTurn.tsx");
ok("no unlabelled cloud-off / sparkles glyph beside 'Not answered'", !/<CloudOff/.test(st) && !/<Sparkles/.test(st));

/* UI-8 */
const allFiles = [];
const walk = (d) => {
  for (const f of readdirSync(d)) {
    const p = join(d, f);
    statSync(p).isDirectory() ? walk(p) : /\.(tsx?|css)$/.test(f) && allFiles.push(p);
  }
};
walk(new URL("../src", import.meta.url).pathname);
const uiStrings = allFiles
  .filter((f) => /\.tsx$/.test(f))
  .map((f) => [f, readFileSync(f, "utf8")]);
const stale = uiStrings.filter(([, t]) => /in the conversation|in Conversation|Open the design conversation/.test(t.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "")));
ok("no user-facing copy sends people to 'the conversation' tab", stale.length === 0, stale.map(([f]) => f.split("/src/")[1]).join(", "));
ok("no PHOENIX capitals in copy", !/PHOENIX supports|PHOENIX will/.test(src("pages/QuickStart.tsx")));
ok("Data empty state has no hyphen-as-dash", !/draft - its/.test(src("components/charts/DataTab.tsx")));
const fr = src("components/conversation/FinishReview.tsx");
ok("dialog title is Review draft", /<DialogTitle>Review draft<\/DialogTitle>/.test(fr));
ok("dialog button is Apply protocol", /"Apply protocol"/.test(fr) && !/Apply to protocol/.test(fr));
ok("success link says Go to Run", /Go to Run/.test(fr) && !/Go to Participants/.test(fr));
ok("dialog has no nested max-h scroll boxes", !/max-h-48|max-h-56/.test(fr));
const dr = src("components/conversation/DraftRail.tsx");
ok("rail button is Review draft in both states", !/Review status/.test(dr));
ok("conversation header no longer repeats 'Build a runnable study'", !/Build a runnable study/.test(cv));
ok("conversation header no longer repeats the 0 / 7 count", !/core sections drafted/.test(cv));
const cs = src("components/conversation/ConversationStart.tsx");
ok("scope sentence reworded", /Supported: coding-task studies\. Not for exams, classrooms or surveys\./.test(cs));
ok("scope sentence has no side stripe", !/border-l-2 border-accent/.test(cs));
ok("one heading in the start view", (cs.match(/<h2/g) ?? []).length === 1);
const sh = src("pages/StudyHome.tsx");
ok("workspace heading is not sentence-cased from the slug", !/\{humanSlug\(id\)\}/.test(sh) || /studyDisplayName/.test(sh));
ok("study name round-trips as entered", (() => {
  const mem = new Map();
  const store = { getItem: (k) => mem.get(k) ?? null, setItem: (k, v) => mem.set(k, v) };
  rememberStudyName(store, "zz-audit-temp", "ZZ Audit Temp");
  return studyDisplayName(store, "zz-audit-temp") === "ZZ Audit Temp";
})());
ok("unknown study falls back to the slug as words", studyDisplayName({ getItem: () => null, setItem() {} }, "trust-in-ai-code") === "Trust in AI code");
ok("a broken store still yields a name", studyDisplayName({ getItem() { throw new Error("x"); }, setItem() {} }, "abc-def") === "Abc def");

/* UI-9 */
ok("?tab=run resolves to the Run tab", resolveStudyTab("run") === "enrollment");
ok("?tab=enrollment still works", resolveStudyTab("enrollment") === "enrollment");
ok("?tab=setup resolves", resolveStudyTab("setup") === "conversation");
ok("?tab=evidence resolves", resolveStudyTab("evidence") === "library");
ok("?tab=plan resolves", resolveStudyTab("plan") === "planning");
ok("unknown tab falls back to setup", resolveStudyTab("zzz") === "conversation" && resolveStudyTab(null) === "conversation");
const hero = src("components/hero/HeroShowcase.tsx");
ok("hero Accept/Reject carry no button chrome", !/rounded-control border border-control-edge px-3 py-1/.test(hero));
ok("hero paragraph keeps human-AI together", /human‑AI|whitespace-nowrap">human/.test(src("pages/Hero.tsx")));
ok("hero card header does not wrap into caps pairs", /whitespace-nowrap/.test(hero) || /truncate/.test(hero));
const qs = src("pages/QuickStart.tsx");
ok("Configure study explains why it is disabled", /study-name-hint|Name the study to continue/.test(qs));
const ph = src("pages/ProjectHome.tsx");
ok("empty study name shows a hint", /Give the study a name/.test(ph));
const lt = src("components/library/Constellation.tsx");
ok("Literature map empty text is not indented past its heading", !/p-6 type-body/.test(lt));
ok("Evidence Add button is not styled like a disabled one", /<Button\s+size="(sm|field)"\s+variant="outline"\s+onClick=\{ingest\}/.test(lib));

/* UI-10 */
const css = src("styles/index.css") + src("styles/tokens.css");
ok("coarse-pointer block exists", /@media \(pointer: coarse\)/.test(css));
ok("coarse targets use a token", /--touch-target/.test(css));

/* UI-11 */
const gc = src("components/conversation/GroundingChip.tsx");
ok("grounding card avoids the chip's own card actions", /event\.stopPropagation\(\)/.test(gc));
ok("Data tab leads with the data-source question", src("components/charts/DataTab.tsx").indexOf("<DataProvenance") < src("components/charts/DataTab.tsx").indexOf("Capture sources"));
ok("producers sit in a details disclosure", /<details[\s\S]{0,200}Configured producers|<summary[^>]*>[\s\S]{0,80}Configured producers|Capture sources/.test(src("components/charts/DataTab.tsx")));

/* Overlay scrim: a light wash over the dark theme was the defect. */
const tokens = src("styles/tokens.css");
const scrimAlpha = (block) => Number((block.match(/--scrim:\s*rgb\([^/]*\/\s*([0-9.]+)\)/) ?? [])[1]);
const lightBlock = tokens.slice(0, tokens.indexOf("--zone-0: #e9eff8"));
const darkBlock = tokens.slice(tokens.indexOf("--zone-0: #e9eff8"));
ok("a scrim token exists in both themes", Number.isFinite(scrimAlpha(lightBlock)) && Number.isFinite(scrimAlpha(darkBlock)));
ok("the dark scrim dims at least as much as the light one", scrimAlpha(darkBlock) >= scrimAlpha(lightBlock));
ok("no overlay uses the theme-flipping ink as its scrim",
  !["components/ui/dialog.tsx", "components/shell/StudyTour.tsx", "components/shell/AppFrame.tsx"]
    .some((f) => /bg-ink\/\d+/.test(src(f))));

/* Round 3: titles, invite copy, tap targets, labels */
const T = (pathname, extra = {}) => documentTitle({ pathname, search: "", signedOut: false, ...extra });
ok("title /home", T("/home") === "Projects · Phoenix", T("/home"));
ok("title /start", T("/start") === "Start a study · Phoenix");
ok("title /settings", T("/settings") === "Account settings · Phoenix");
ok("title /repertoire", T("/repertoire") === "Templates · Phoenix");
ok("title project falls back", T("/p/lab") === "Project · Phoenix");
ok("title project uses its name", T("/p/lab", { projectName: "Lab A" }) === "Lab A · Phoenix");
ok("title members", T("/p/lab/members") === "Members · Phoenix");
ok("title project settings", T("/p/lab/settings") === "Project settings · Phoenix");
ok("title invitation", T("/invitations/abc") === "Project invitation · Phoenix");
ok("title study + default tab", T("/p/lab/studies/s1", { studyName: "Trust study" }) === "Trust study · Setup · Phoenix", T("/p/lab/studies/s1", { studyName: "Trust study" }));
ok("title study + tab param", documentTitle({ pathname: "/p/lab/studies/s1", search: "?tab=data", studyName: "Trust study" }) === "Trust study · Data · Phoenix");
ok("title 404", T("/nope/zzz") === "Page not found · Phoenix");
ok("title landing has no suffix", T("/") === "Phoenix: run a defensible developer study");
ok("title sign-in", T("/signin") === "Sign in · Phoenix");
ok("sentenceCase", sentenceCase("invitation not found") === "Invitation not found");
ok("displayServerMessage capitalises and punctuates",
  displayServerMessage("invitation not found. It may have expired or been revoked") === "Invitation not found. It may have expired or been revoked.");
ok("displayServerMessage keeps ? and .", displayServerMessage("Done.") === "Done." && displayServerMessage("Why?") === "Why?");
ok("displayServerMessage of blank is blank", displayServerMessage("  ") === "");
ok("404/410 invite errors are fatal", isFatalInviteError({ status: 404 }) && isFatalInviteError({ status: 410 }));
ok("other invite errors are retryable", !isFatalInviteError({ status: 500 }) && !isFatalInviteError(new Error("x")));
const inv = src("pages/InviteAccept.tsx");
ok("invite page hides Accept after a fatal error", /fatal/.test(inv) && /displayServerMessage/.test(inv));
ok("invite link is a Button", /<Button asChild[^>]*>\s*<Link to="\/home"/.test(inv));
ok("plainMatchReason rewrites jargon", plainMatchReason("Describes itself with: self-reported, survey.") === "Matches: self-reported, survey.");
ok("plainMatchReason leaves others", plainMatchReason("Measures X.") === "Measures X.");
ok("theme toggle names the action", themeToggleLabel("light") === "Switch to dark theme" && themeToggleLabel("dark") === "Switch to light theme");
ok("emoji gets a space before a word", humanSlug("🚀study") === "🚀 study", humanSlug("🚀study"));
ok("plain slug unchanged", humanSlug("case-study") === "Case study");
ok("coarse block also covers narrow viewports", /@media \(pointer: coarse\), \(max-width: 640px\)/.test(css));
ok("switcher keeps New project reachable", /forceMount/.test(src("components/shell/ProjectSwitcher.tsx")));
ok("dialog primitive guarantees an accessible name", /DialogPrimitive\.Title/.test(src("components/ui/command.tsx")) || /VisuallyHidden|sr-only/.test(src("components/ui/command.tsx")));
ok("404 page is branded in the shell", /PhoenixMark/.test(src("App.tsx")) && /Page not found|does not exist/.test(src("App.tsx")));
ok("shell sets the document title", /useDocumentTitle/.test(src("components/shell/AppFrame.tsx")));

/* Write-on-open: a read-only role must never POST on load. */
ok("compile-on-open waits while the role is unknown", compileOnOpenAllowed({ status: "loading" }) === false);
ok("compile-on-open never runs for a viewer", compileOnOpenAllowed({ status: "known", role: "viewer" }) === false);
ok("compile-on-open runs for member and owner", compileOnOpenAllowed({ status: "known", role: "member" }) && compileOnOpenAllowed({ status: "known", role: "owner" }));
ok("compile-on-open leaves non-members to the server (local mode)", compileOnOpenAllowed({ status: "known", role: null }) === true);
ok("ConversationView takes the role and gates compile", /compileOnOpenAllowed/.test(src("components/conversation/ConversationView.tsx")) && /roleState=/.test(src("pages/StudyHome.tsx")));

/* Plain labels for producers, their states and raw event types. */
ok("workspace-snapshot is plain", captureTokenLabel("workspace-snapshot") === "Workspace snapshots");
ok("participant-git is plain", captureTokenLabel("participant-git") === "Git history");
ok("task-harness is plain", captureTokenLabel("task-harness") === "Task outcomes");
ok("agent-derived is plain", captureTokenLabel("agent-derived") === "Derived AI measures");
ok("external-required state is plain", producerStateLabel("external-required") === "Separate runner needed");
ok("unavailable state is plain", producerStateLabel("unavailable") === "Not configured");
ok("unknown state is humanised", producerStateLabel("some-new-state") === "Some new state");
ok("event types read as words", eventTypeLabel("agent.prompt_sent") === "Agent prompt sent");
ok("no raw capture tokens in evidence details", !/\{capture\.availability\}|>\{measure\.id\}:|\{capture\.eventTypes\?\.join/.test(src("components/conversation/EvidenceDetails.tsx")));
ok("data tab states are labelled", /producerStateLabel\(producer\.state\)/.test(src("components/charts/DataTab.tsx")));
ok("summary rows have a 24px+ target", /summary \{[^}]*min-height: var\(--target-min\)/.test(css));
ok("touch links reach 44px on phones", /a\.touch-link \{[^}]*min-width: var\(--touch-target\)/.test(css));

/* Decision echo shown as the researcher's own turn: plain nouns, no code words. */
ok("a rejected field card is described as a setting", rejectedMoveText("set-field") === "I rejected the proposed setting.");
ok("a rejected measure card is described as a measure", rejectedMoveText("add-measure") === "I rejected the proposed measure.");
ok("a rejected design card is described as a design", rejectedMoveText("choose-template") === "I rejected the proposed design.");
ok("no hyphenated kind name leaks into the echo", !/-/.test(rejectedMoveText("reconfigure-instrument")));

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
