# Agent annotations (`data-agent`): the convention

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
or removing one is a breaking change: log it in this file's changelog, the
same way an API change is logged elsewhere.
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
| `conversation-start` | `ConversationStart` | the blank record: how the conversation works, and the openings that load into the composer (shown only before the first researcher turn) |
| `conversation-send` | `ConversationView` | send the researcher's message |
| `conversation-thinking` | `ConversationView` | the platform is composing a reply (LLM or scripted), a transient landmark |
| `conversation-streaming` | `ConversationView` | the reply's prose as it streams in (transient; replaced by the real turn) |
| `understanding-line` | `DraftRail` | what the platform still doesn't know, and why no design shape is proposed yet |
| `hatch-legend` | `HatchLegend` | the key to the record's four marks: mark size is grounding strength, an open ring is unsourced, a doubled mark is a conflict, a struck line is superseded |
| `move-card` | `MoveCard` | one proposed design move (decision point); `data-agent-kind`, `data-agent-status` refine it |
| `move-accept` | `MoveCard` | accept the move |
| `move-reject` | `MoveCard` | reject the move |
| `move-undo` | `MoveCard` | reopen a decided move back to `proposed` |
| `recommendation-card` | `RecommendationCard` | a matched paper; `data-agent-ref` carries its corpus ref |
| `add-paper` | `RecommendationCard` | add the paper to the study set |
| `recommender-rail` | `RecommenderRail` | the persistent literature-recommender panel beside the conversation (landmark) |
| `design-shape` | `Templates` | one design shape in the ranked protocol repertoire; `data-agent-ref` carries its template id |
| `draft-rail` | `DraftRail` | the compiled protocol-draft view (landmark) |
| `draft-apply` | `DraftRail` | apply the server-validated compiled draft to the protocol (decision point) |
| `draft-finish` | `DraftRail` | open the finish-and-review moment that prepares the protocol draft (decision point) |
| `protocol-guide-open` | `ProtocolGuide` | open the reference explaining the 8 mandatory protocol-draft sections (help) |
| `tour-open` | `StudyHome` | open the first-study guided walkthrough (help) |
| `tour-next` | `StudyTour` | advance the walkthrough to the next step |
| `tour-done` | `StudyTour` | finish the walkthrough and start working |
| `new-study` | `ProjectHome` | create a new study in the project (decision point) |
| `project-list` | `Projects` | the list of projects you belong to, each row carrying its study count (landmark) |
| `new-project` | `Projects` | open the inline composer that creates a project (decision point) |
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
| `study-tabs` | `StudyHome` | the study workspace section tabs (landmark) |
| `presence-chips` | `PresenceChips` | who else is viewing this study right now (absent when you're alone) |
| `study-export` | `ExportStudy` | open the share/export menu for this study |
| `export-replication-kit` | `ExportStudy` | download the byte-reproducible replication kit (FR-PROT-7) |
| `export-elicitation-record` | `ExportStudy` | download the elicitation record (FR-CONV-6) |
| `export-ethics-package` | `ExportStudy` | download the ethics package: design, tasks, capture, and exact consent text (FR-AGENT-5) |
| `export-notebook` | `ExportStudy` | download the starter notebook + data dictionary, zipped (FR-ANA-6) |
| `power-curve` | `PowerPanel` | the power/sensitivity chart on the Planning surface (P2-2) |
| `power-required` | `PowerPanel` | the required-n table: effect size × per-group/total n × target reached |
| `constellation` | `Constellation` | the citation-graph canvas (landmark) |
| `metric-strip` | `MetricStrip` | the per-condition metric distribution chart (landmark) |
| `live-sessions` | `LiveSessions` | the live-session monitor: who is running right now, what task, and whether data is arriving (landmark, FR-DASH-3) |
| `live-session` | `LiveSessions` | one running session; `data-agent-ref` carries its session id |
| `enrollment-panel` | `EnrollmentPanel` | the study's participant enrollment surface (landmark) |
| `mint-tokens` | `MintDialog` | open the mint-enrollment-links dialog (decision point) |
| `open-in-vscode` | `MintDialog`, `EnrollmentPanel` | the vscode:// deep-link companion to a minted connection string (decision point) |
| `extension-install-link` | `EnrollmentPanel` | where a participant without the extension gets it — TERN ships as a GitHub release artifact, not on the Marketplace, so the deep link has nothing to resolve to until this is followed (decision point) |
| `new-study-open` | `ProjectHome` | open the inline new-study composer (decision point) |
| `steer-dial` | `SteerDial` | how much the researcher wants the assistant to drive this conversation: the one control that moves both register and initiative (`elicitation.STEER_LEVELS`) (decision point) |
| `toggle-popover` | `TogglePopover` | per-metric capture-toggle popover showing label, grounding, and apply button (FR-DASH-11) |
| `live-sessions` | `LiveSessions` | the live-session monitor: who is running right now (landmark, FR-DASH-10) |
| `live-session` | `LiveSessions` | one running session, with its event rate, task, condition and gap count; `data-agent-ref` carries the session id |
| `swimlane-timeline` | `SwimlaneTimeline` | the per-session swimlane chart (landmark, FR-DASH-4) |

## Changelog

- **2026-07-18**: initial inventory. No prior names to
  supersede.
- **2026-07-18**: evolution surfaces added: amendment banner/history +
  version chip (FR-CONV-4), feedback marking + platform-findings lineage
  (FR-CONV-5).
- **2026-07-18**: knowledge-layer migration:
  study workspace tabs, citation constellation, metric-strip chart
  (FR-LIT-2/4, FR-DASH-5).
- **2026-07-19**: live capture link: enrollment panel + mint-links dialog
  (FR-DASH-10, Phase 19).
- **2026-07-21**: live conversation compile added: `draft-apply` (apply the
  server-validated draft to the protocol).
- **2026-07-21**: resolved a stash-pop conflict that had dropped the
  amendment banner/history wiring from `StudyHome`; restored
  `amendment-history-toggle`.
- **2026-07-21**: capture-console phase: `toggle-popover` for FR-DASH-11
  per-metric toggles on the enrollment surface.
- **2026-07-21**: session-timeline phase: `swimlane-timeline` for FR-DASH-4
  per-session chart.
- **2026-07-21**: LLM-driven conversation (FR-CONV-1.4): `conversation-thinking`
  (transient landmark while a turn is composing) + `data-agent-status="llm-guided"`
  on `StreamingTurn`'s author line (secondary attribute, not a new landmark).
- **2026-07-30**: `protocol-guide-open` opens a reference dialog explaining
  the 8 mandatory `ProtocolDraft` sections.
- **2026-08-06**: removed the platform-findings surface (FR-CONV-5): the
  "Platform findings" nav item/page and the conversation "flag for the
  platform" affordance are gone, taking `feedback-mark`, `feedback-composer`,
  `feedback-send`, `feedback-marked`, `platform-findings`, and
  `retrospective-proposal` with them.
- **2026-08-18**: scope cut to design + setup. The lifecycle board and its
  phase rail are gone, so `project-list` rows no longer carry a phase mix.
  Added `extension-install-link`; `open-in-vscode` now also appears in
  `EnrollmentPanel`, and both build their URI from `lib/extension.ts` after
  the deep link was found pointing at an extension identity that has never
  existed.
- **2026-08-18**: `live-sessions` / `live-session` — the live-session monitor
  on the Participants surface. Documented from the component rather than by its
  author; correct the wording here if it undersells what they mark.
- **2026-08-18**: `steer-dial` — the steer-level control on the design
  conversation. Named `assist-dial` for part of the same day; renamed with the
  label the researcher actually reads, so the contract name and the UI agree.
- **2026-08-18**: `understanding-line` moved from `UnderstandingLine` (deleted)
  into `DraftRail`. It answers "why has no design been proposed yet", which is
  a question about the draft, not a turn in the thread; printed under every
  exchange it repeated itself on each turn.
- **2026-08-18**: `new-study-open` — the inline new-study composer's trigger
  on the project home.
- **2026-08-18**: `live-sessions` / `live-session` — the live-session monitor
  on the Participants surface. `GET /studies/{id}/live` had computed per-session
  event rates and gap counts all along with nothing rendering them.
- **2026-08-19**: `export-ethics-package` — the ethics-package download in
  the study export menu.
- **2026-08-19**: `export-notebook` — the starter-notebook download in the
  study export menu.
- **2026-08-19**: `power-curve` — the power/sensitivity chart on the new
  Planning surface. A browser agent lands here to read the curve the
  researcher is planning recruitment against.
- **2026-08-19**: `power-required` — the required-n table beside the
  power curve: effect size × per-group/total n × whether the target is
  reached within the explored range.
