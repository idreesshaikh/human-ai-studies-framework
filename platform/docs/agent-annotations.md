# Agent annotations (`data-agent`) — the convention

This platform's UI carries stable `data-agent` attributes on its
navigational landmarks and decision-bearing components, so a **browser
agent** driving the UI can find them by a stable name instead of by brittle
CSS selectors or visible text (which change with copy, layout, and theme).
Stable semantic anchors for agents (FR-AGF-3).

## Naming rules

- **Kebab-case, role-named, not layout-named.** `data-agent="move-card"`,
  not `data-agent="card-1"`. The name says what the element *is for*, never
  where it sits.
- **One name per role.** If two elements do the same job (e.g. two move
  cards), they share the attribute value; disambiguate with a secondary
  `data-agent-*` attribute (`data-agent-kind`, `data-agent-ref`), never by
  minting `move-card-2`.
- **Landmarks and decision points only.** Err toward fewer, stabler names.
  A `data-agent` on every `<div>` is noise; put it where an agent makes a
  choice (accept/reject, add, invite) or needs to orient (the conversation,
  the draft, the nav).

## Stability promise

A `data-agent` value is a **public contract**, like an API route. Renaming
or removing one is a breaking change: log it in this file's changelog and in
`requirements/traceability.md`, the same way an API change is logged.
Secondary `data-agent-*` values (status, kind, ref) mirror internal state
and may change with that state; only the primary landmark names are the
stable contract.

## Current inventory

Generated components adopt these from birth; the platform components were
retrofitted.

| `data-agent` | Component | What it marks |
| --- | --- | --- |
| `conversation` | `ConversationView` | the design-conversation surface (landmark) |
| `conversation-composer` | `ConversationView` | the message form |
| `conversation-send` | `ConversationView` | send the researcher's message |
| `conversation-thinking` | `ConversationView` | the platform is composing a reply (LLM or scripted) — a transient landmark |
| `conversation-streaming` | `ConversationView` | the reply's prose as it streams in (transient; replaced by the real turn) |
| `move-card` | `MoveCard` | one proposed design move (decision point); `data-agent-kind`, `data-agent-status` refine it |
| `move-accept` | `MoveCard` | accept the move |
| `move-reject` | `MoveCard` | reject the move |
| `recommendation-card` | `RecommendationCard` | a matched paper; `data-agent-ref` carries its corpus ref |
| `add-paper` | `RecommendationCard` | add the paper to the study set |
| `recommender-rail` | `RecommenderRail` | the persistent literature-recommender panel beside the conversation (landmark) |
| `design-shape` | `Templates` | one design shape in the ranked protocol repertoire; `data-agent-ref` carries its template id |
| `draft-rail` | `DraftRail` | the compiled protocol-draft view (landmark) |
| `draft-apply` | `DraftRail` | apply the server-validated compiled draft to the protocol (decision point) |
| `draft-finish` | `DraftRail` | open the finish-and-review moment that prepares the protocol draft (decision point) |
| `tour-open` | `StudyHome` | open the first-study guided walkthrough (help) |
| `tour-next` | `StudyTour` | advance the walkthrough to the next step |
| `tour-done` | `StudyTour` | finish the walkthrough and start working |
| `new-study` | `ProjectHome` | create a new study in the project (decision point) |
| `project-switcher` | `ProjectSwitcher` | open the ⌘K project switcher (landmark) |
| `project-nav` | `AppFrame` | the project sidebar (landmark) |
| `sign-in` | `SignInScreen` | the sign-in gate (landmark), shown instead of project UI until a credential exists |
| `invite` | `InviteDialog` | open the invite dialog (decision point) |
| `member-actions` | `MembersTable` | open a member's role/remove menu (decision point) |
| `amendment-banner` | `AmendmentBanner` | the study's amendment state (consent surface); `data-agent-paused` refines it |
| `amendment-reapprove` | `AmendmentBanner` | record the ethics re-approval that lifts the session pause (decision point) |
| `amendment-history` | `AmendmentHistory` | the amendment record list (landmark) |
| `amendment-history-toggle` | `StudyHome` | show/hide the amendment history |
| `version-chip` | `AmendmentHistory` | one protocol-revision chip |
| `feedback-mark` | `FeedbackAffordance` | flag a conversation turn as platform feedback (decision point) |
| `feedback-composer` | `FeedbackAffordance` | the feedback note + kind form |
| `feedback-send` | `FeedbackAffordance` | file the feedback as a finding |
| `feedback-marked` | `FeedbackAffordance` | a turn already marked as feedback |
| `platform-findings` | `PlatformFindings` | the feedback-findings list (landmark) |
| `retrospective-proposal` | `PlatformFindings` | the inert drafted proposal (landmark) |
| `study-tabs` | `StudyHome` | the study workspace section tabs (landmark) |
| `constellation` | `Constellation` | the citation-graph canvas (landmark) |
| `metric-strip` | `MetricStrip` | the per-condition metric distribution chart (landmark) |
| `enrollment-panel` | `EnrollmentPanel` | the study's participant enrollment surface (landmark) |
| `mint-tokens` | `MintDialog` | open the mint-enrollment-links dialog (decision point) |
| `open-in-vscode` | `MintDialog` | the vscode:// deep-link companion to a minted connection string (decision point) |
| `toggle-popover` | `TogglePopover` | per-metric capture-toggle popover showing label, grounding, and apply button (FR-DASH-11) |
| `swimlane-timeline` | `SwimlaneTimeline` | the per-session swimlane chart (landmark, FR-DASH-4) |

## Changelog

- **2026-07-18** — initial inventory. No prior names to
  supersede.
- **2026-07-18** — evolution surfaces added: amendment banner/history +
  version chip (FR-CONV-4), feedback marking + platform-findings lineage
  (FR-CONV-5).
- **2026-07-18** — knowledge-layer migration:
  study workspace tabs, citation constellation, metric-strip chart
  (FR-LIT-2/4, FR-DASH-5).
- **2026-07-19** — live capture link: enrollment panel + mint-links dialog
  (FR-DASH-10, Phase 19).
- **2026-07-21** — live conversation compile added: `draft-apply` (apply the
  server-validated draft to the protocol).
- **2026-07-21** — resolved a stash-pop conflict that had dropped the
  amendment banner/history wiring from `StudyHome`; restored
  `amendment-history-toggle`.
- **2026-07-21** — capture-console phase: `toggle-popover` for FR-DASH-11
  per-metric toggles on the enrollment surface.
- **2026-07-21** — session-timeline phase: `swimlane-timeline` for FR-DASH-4
  per-session chart.
- **2026-07-21** — LLM-driven conversation (FR-CONV-1.4): `conversation-thinking`
  (transient landmark while a turn is composing) + `data-agent-status="llm-guided"`
  on `StreamingTurn`'s author line (secondary attribute, not a new landmark).
