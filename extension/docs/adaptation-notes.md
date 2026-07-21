# Adaptation notes - behavioral telemetry (MP-05)

What was taken from each studied reference plugin, what was rejected, and the
blind spots of the mechanisms we chose. This is the NFR-10 evidence for
decisions D2 (Tako), D3 (ActivityWatch), D4 (WakaTime); the adopt/adapt
rationale lives in `requirements/build-vs-adopt.md`.

Method note: Tako's GitHub repo (`si-codelounge/tako`) is a docs-only mirror
of a private GitLab repo - it contains no source. Its mechanisms were studied
from the published Marketplace VSIX (`codelounge.tako` v1.2.2, unminified
compiled output). `aw-watcher-vscode` and `vscode-wakatime` were read from
source on GitHub.

## From Tako (D2 - AI-completion lifecycle)

**How Tako actually does it:** it monkey-patches *other extensions'* `vscode`
API objects through the Node module cache (`Module._cache`), wrapping
`languages.registerInlineCompletionItemProvider` so that when Copilot
registers, Tako wraps `provideInlineCompletionItems` (suggestion computed),
Copilot's non-public `handleDidShowCompletionItem` (suggestion shown), and
`commands.registerCommand` to capture Copilot's internal
`_ghostTextPostInsert` command (acceptance). Review time = accept-command
timestamp minus provider-invocation timestamp; rejection is inferred from
absence of an accept.

**Taken:** the *shape* of the lifecycle instrument - suggestion-shown and
decision timestamps as separate joinable events, with review latency
(`visibleMs`) computed between them (FR-INST-8); rejection-by-absence as an
analysis-side concept.

**Rejected:** the mechanism. `Module._cache` patching requires activating
before the target extension, only works in a same-process Node extension
host, and is welded to undocumented Copilot internals that have already
changed since Tako shipped. That is debt, not engineering (NFR-10), and a
sensor that silently stops observing partway through a study corrupts the
dataset (NFR-2).

**Chosen instead (public API only):**

1. A **passive `InlineCompletionItemProvider`** (returns no items) timestamps
   when the editor computes inline completions - the public stand-in for
   "a suggestion is on screen". Queries separated by a quiet gap (> 2 s)
   start a new `suggestionId` and emit `ai_suggestion action=shown`.
2. **Keybinding-scoped wrapper commands** (see below) on `Tab`
   (`when: inlineSuggestionVisible`) and `Escape` record
   `accepted`/`dismissed` and then delegate to the real
   `editor.action.inlineSuggest.commit` / `.hide`.
3. The **block-injection heuristic** (>= 80 chars inside 50 ms, both
   protocol-configurable) as the fallback that also catches non-inline AI
   surfaces (chat-panel "apply", CLI agents editing files on disk).

**Blind spots (RQ-F1 evidence):**

- *Query is not display*: the passive provider fires when completions are
  computed; a provider may return nothing, so some `shown` events have no
  visible ghost text, and `visibleMs` is an upper bound on true visibility.
- Partial accepts (accept-next-word commands), mouse-click accepts on the
  suggestion toolbar, and typing-through dismissals bypass the keybindings;
  sizeable accepted blocks are still caught by the size heuristic as
  `edit_burst origin=ai`, but without a lifecycle event.
- Explicit `rejected` is not directly observable in VS Code; `dismissed`
  (Esc) is captured, and rejection can be inferred in analysis as a `shown`
  with no matching decision.

## From ActivityWatch (D3 - sensor -> local daemon)

**Taken:** the dumb-sensor architecture, already adopted for the cognitive
leg and reused unchanged here: cheap synchronous handlers, fire-and-forget
batched HTTP to the local middleware on :8000, the IDE never waits on the
network (NFR-1). Also the discipline of *not* hooking hot paths for
presence: like `aw-watcher-vscode`, presence/focus signals come from
selection/active-editor/window-state listeners.

**Improved on:** `aw-client-js` has no retry and no offline buffer - events
are dropped while the daemon is down, and failures pop an error toast
(which would violate NFR-1). Our `HttpSink` buffers with backoff and is only
a best-effort mirror of the JSONL source of truth; loss is *detectable* via
`seq` gaps (NFR-2). Nothing user-visible ever fires from a sink.

## From WakaTime (D4 - active/idle + filtering)

**Taken:**

- The **2-minute rule**: WakaTime's `TIME_BETWEEN_HEARTBEATS_MS = 120000` is
  the basis for our rolling 120 s activity window
  (`tern.behavior.idleWindowSeconds`, FR-INST-11). Improvement:
  WakaTime's idle is absence-of-heartbeats, reconstructed server-side; we
  emit explicit `heartbeat {state: active|idle}` *transitions* (two rows per
  gap, no periodic spam), so time-on-task denominators are first-class data.
- The **language/path filter** concept (FR-INST-12). WakaTime delegates
  include/exclude to wakatime-cli's config; we put the predicate in
  `src/core/captureFilter.ts` (languages + workspace-internal-only) so it is
  unit-tested and protocol-derivable.
- The **AI-vs-human insert heuristic** family: WakaTime classifies a single
  contentChange > 50 chars / > 2 newlines as a possible AI insert and decays
  the flag on human keystrokes. We made it rigorous and configurable
  (threshold + window + correlation, FR-INST-10) and classify per-burst with
  a strict evidence ranking instead of a global flag.

**Rejected:** WakaTime's guard that *discards* large line deltas as
"copy/paste noise" - paste volume is a first-class research variable here
(reliance loops, RQ-P5), so pastes are measured, never dropped. Also its
hardcoded AI-vendor extension list as a *gate* (we record installed AI
extensions in `environment_snapshot` as provenance instead).

## Paste detection (none of the three do it)

Verified: Tako records pastes only as unlabeled multi-char document changes;
`aw-watcher-vscode` and WakaTime never touch clipboard events; nobody
intercepts `editor.action.clipboardPasteAction`. So the mechanism is ours:

- **Keybinding-scoped wrapper commands** `tern.behavior.copy/
  cut/paste` bound to `Ctrl/Cmd+C/X/V` with
  `when: tern.sessionActive && editorTextFocus`. Each records
  its measurement and *always* delegates to the built-in clipboard command
  in a `finally` (a telemetry bug must never break paste - NFR-1).
- We deliberately do **not** shadow the built-in command ids via
  `registerCommand` (fragile, and a failure there breaks paste everywhere)
  and do **not** read the clipboard (`env.clipboard` is never called -
  FR-ETH-2). Paste size is measured from the resulting document change.
- Internal-copy correlation: on copy/cut inside the workspace, a
  **salted session-local hash** of the selection is kept in memory (never
  written, salt discarded with the session); a paste whose inserted text
  hashes identically yields `msSinceInternalCopy`. Pastes without a match
  came from outside (browser, AI chat pane, terminal) - exactly the signal
  RQ-P5's reliance loops need.

**Blind spots:** context-menu/menu-bar paste, drag-and-drop, and paste while
the extension host is not yet activated bypass the keybindings (no
`clipboard_paste` event; large ones land as `edit_burst origin=ai` via the
block heuristic, small ones as `human`). Keybindings only apply during an
active session (`sessionActive` context), so out-of-session copy/paste is
untouched native behavior. Multi-cursor copies are hashed as their
newline-joined concatenation, matching VS Code's own multi-cursor clipboard
join, but exotic clipboard transformations (auto-format-on-paste) change the
inserted text and break the hash match - the paste is still recorded, only
`msSinceInternalCopy` is lost.

## Glass HUD constraint (FR-INST-13)

The debrief webview is glassmorphic (blur + translucency over theme colors).
The fatigue probe **cannot** be brought to the same standard with today's
stable API: VS Code has no floating/overlay webview surface - webview panels
occupy an editor group (taking focus and screen space, violating NFR-1's
never-interrupt invariant, which outranks styling), and the proposed
webview-inset API never stabilized. QuickPick styling is locked by the
platform theme and cannot receive backdrop blur.

Decision: the fatigue probe stays a **QuickPick** - VS Code's native
floating, translucent, keyboard-first overlay (the command-palette surface),
which is the closest the platform offers to an in-editor glass HUD. The
participant never leaves the editor and typing focus is only taken for the
one-keystroke answer, which is the invariant FR-INST-13 exists to protect.
Revisit if/when `createWebviewTextEditorInset` or an overlay-webview API
stabilizes.
