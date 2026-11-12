# Adaptation notes - behavioral telemetry

What was taken from each studied reference plugin, what was rejected, and the
blind spots of the mechanisms we chose. The adopt/adapt rationale for Tako,
ActivityWatch and WakaTime is recorded below, alongside each one.

Method note: Tako's GitHub repo (`si-codelounge/tako`) is a docs-only mirror
of a private GitLab repo - it contains no source. Its mechanisms were studied
from the published Marketplace VSIX (`codelounge.tako` v1.2.2, unminified
compiled output). `aw-watcher-vscode` and `vscode-wakatime` were read from
source on GitHub.

## From Tako (AI-completion lifecycle)

**How Tako actually does it:** it monkey-patches _other extensions'_ `vscode`
API objects through the Node module cache (`Module._cache`), wrapping
`languages.registerInlineCompletionItemProvider` so that when Copilot
registers, Tako wraps `provideInlineCompletionItems` (suggestion computed),
Copilot's non-public `handleDidShowCompletionItem` (suggestion shown), and
`commands.registerCommand` to capture Copilot's internal
`_ghostTextPostInsert` command (acceptance). Review time = accept-command
timestamp minus provider-invocation timestamp; rejection is inferred from
absence of an accept.

**Taken:** joinable IDs for explicit accept/dismiss keybinding events.
Suggestion display and review latency are not observable through the public
API, and an absent accept does not establish rejection.

**Rejected:** both the mechanism and the display/rejection claims.
`Module._cache` patching requires activating
before the target extension, only works in a same-process Node extension
host, and is welded to undocumented Copilot internals that have already
changed since Tako shipped. That is debt, not engineering, and a
sensor that silently stops observing partway through a study corrupts the
dataset.

**Chosen instead (public API only):**

1. **Keybinding-scoped wrapper commands** (see below) on `Tab`
   (`when: inlineSuggestionVisible`) and `Escape` record
   `accepted`/`dismissed` and then delegate to the real
   `editor.action.inlineSuggest.commit` / `.hide`.
2. The **block-injection heuristic** (>= 80 chars inside 50 ms, both
   protocol-configurable) as a possible signal for non-inline AI surfaces
   (chat-panel "apply", CLI agents editing files on disk). It can also flag
   formatters, snippets, renames and other non-AI edits, so it does not
   establish AI origin.

The passive provider was removed because VS Code can query it during ordinary
typing, and its public API does not reveal whether another provider returned or
displayed a suggestion. TERN records keybinding accept/dismiss actions only;
these actions are incomplete measures of all suggestion use.

**Blind spots:**

- Partial accepts (accept-next-word commands), mouse-click accepts on the
  suggestion toolbar, and typing-through dismissals bypass the keybindings;
  sizeable rapid edits may be caught by the bulk-edit heuristic, but that
  heuristic cannot establish AI origin.
- The public API does not expose reliable suggestion display, rejection, or
  review-latency events. Do not infer rejection from the absence of an accept.

## From ActivityWatch (sensor -> local daemon)

**Taken:** the dumb-sensor architecture, already adopted for the cognitive
leg and reused unchanged here: cheap synchronous handlers, fire-and-forget
batched HTTP to the local middleware on :8000, the IDE never waits on the
network. Also the discipline of _not_ hooking hot paths for
presence: like `aw-watcher-vscode`, presence/focus signals come from
selection/active-editor/window-state listeners.

**Improved on:** `aw-client-js` has no retry and no offline buffer - events
are dropped while the daemon is down, and failures pop an error toast
(which would interrupt the participant). Our `HttpSink` buffers with backoff and is only
a best-effort mirror of the JSONL source of truth; loss is _detectable_ via
`seq` gaps. The HTTP sink never shows anything to the participant (only a failed local
file write does).

## From WakaTime (active/idle + filtering)

**Taken:**

- The **2-minute rule**: WakaTime's `TIME_BETWEEN_HEARTBEATS_MS = 120000` is
  the basis for our rolling 120 s activity window
  (`tern.behavior.idleWindowSeconds`). Improvement:
  WakaTime's idle is absence-of-heartbeats, reconstructed server-side; we
  emit explicit `heartbeat {state: active|idle}` _transitions_ (two rows per
  gap, no periodic spam), so time-on-task denominators are first-class data.
- The **language/path filter** concept. WakaTime delegates
  include/exclude to wakatime-cli's config; we put the predicate in
  `src/core/captureFilter.ts` (languages + workspace-internal-only) so it is
  unit-tested and protocol-derivable.
- The **AI-vs-human insert heuristic** family: WakaTime classifies a single
  contentChange > 50 chars / > 2 newlines as a possible AI insert and decays
  the flag on human keystrokes. We made it rigorous and configurable
  (threshold + window + correlation) and classify per-burst with
  a strict evidence ranking instead of a global flag.

**Rejected:** WakaTime's guard that _discards_ large line deltas as
"copy/paste noise" - paste volume is a first-class research variable here
(reliance loops), so pastes are measured, never dropped. Also its
hardcoded AI-vendor extension list as a _gate_ (we record installed AI
extensions in `environment_snapshot` as provenance instead).

## Paste detection (none of the three do it)

Verified: Tako records pastes only as unlabeled multi-char document changes;
`aw-watcher-vscode` and WakaTime never touch clipboard events; nobody
intercepts `editor.action.clipboardPasteAction`. So the mechanism is ours:

- **Keybinding-scoped wrapper commands** `tern.behavior.copy/
cut/paste` bound to `Ctrl/Cmd+C/X/V` with
  `when: tern.sessionActive && editorTextFocus`. Each records
  its measurement and _always_ delegates to the built-in clipboard command
  in a `finally` (a telemetry bug must never break paste).
- We deliberately do **not** shadow the built-in command ids via
  `registerCommand` (fragile, and a failure there breaks paste everywhere)
  and do **not** read the clipboard (`env.clipboard` is never called,
  because clipboard text is never captured). Paste size is measured from the
  resulting document change.
- Internal-copy correlation: on copy/cut inside the workspace, a
  **salted session-local hash** of the selection is kept in memory (never
  written, salt discarded with the session); a paste whose inserted text
  hashes identically yields `msSinceInternalCopy`. Pastes without a match
  came from outside (browser, AI chat pane, terminal) - exactly the signal
  studies of reliance loops need.

**Blind spots:** context-menu/menu-bar paste, drag-and-drop, and paste while
the extension host is not yet activated bypass the keybindings (no
`clipboard_paste` event; large ones may land as `edit_burst origin=ai` via the
block heuristic, which does not prove AI origin, while small ones may appear as
`human`). Keybindings only apply during an
active session (`sessionActive` context), so out-of-session copy/paste is
untouched native behavior. Multi-cursor copies are hashed as their
newline-joined concatenation, matching VS Code's own multi-cursor clipboard
join, but exotic clipboard transformations (auto-format-on-paste) change the
inserted text and break the hash match - the paste is still recorded, only
`msSinceInternalCopy` is lost.

## Floating prompt constraint

The debrief webview is glassmorphic (blur + translucency over theme colors).
The fatigue probe **cannot** be brought to the same standard with today's
stable API: VS Code has no floating/overlay webview surface - webview panels
occupy an editor group (taking focus and screen space, violating the
never-interrupt rule, which outranks styling), and the proposed
webview-inset API never stabilized. QuickPick styling is locked by the
platform theme and cannot receive backdrop blur.

Decision: the fatigue probe stays a **QuickPick** - VS Code's native
floating, translucent, keyboard-first overlay (the command-palette surface),
which is the closest the platform offers to an in-editor glass HUD. The
participant never leaves the editor and typing focus is only taken for the
one-keystroke answer, which is the rule this design exists to protect.
Revisit if/when `createWebviewTextEditorInset` or an overlay-webview API
stabilizes.
