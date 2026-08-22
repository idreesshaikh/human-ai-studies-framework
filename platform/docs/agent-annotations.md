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
| `slot-meter` | `SlotMeter` | compact protocol coverage and the next question |
| `protocol-readiness` | `SlotMeter` | whether the protocol is ready to review |
| `move-card` | `MoveCard` | one proposed design move (decision point); `data-agent-kind`, `data-agent-status` refine it |
| `move-accept` | `MoveCard` | accept the move |
| `move-reject` | `MoveCard` | reject the move |
| `move-undo` | `MoveCard` | reopen a decided move back to `proposed` |
| `recommendation-card` | `RecommendationCard` | a matched paper; `data-agent-ref` carries its corpus ref |
| `add-paper` | `RecommendationCard` | add the paper to the study set |
| `recommender-rail` | `RecommenderRail` | the persistent literature-recommender panel beside the conversation (landmark) |
| `design-shape` | `Templates` | one design shape in the ranked protocol repertoire; `data-agent-ref` carries its template id |
| `draft-rail` | `DraftRail` | the compiled protocol-draft view (landmark) |
| `draft-slot-plate` | `DraftRail` | every mandatory protocol slot as an address, filled or still an open ring (landmark) |
| `draft-apply` | `DraftRail` | apply the server-validated compiled draft to the protocol (decision point) |
| `draft-finish` | `DraftRail` | open the finish-and-review moment that prepares the protocol draft (decision point) |
| `protocol-path-current` | `SlotMeter` | the current step, shown even while the full phased checklist is collapsed |
| `protocol-path` | `SlotMeter` | the phased checklist of protocol steps covered so far (landmark), collapsed by default behind a disclosure |
| `path-up-next` | `SlotMeter` | what would move the researcher next, named under the path |
| `applied-next-step` | `FinishReview` | the callout shown after the draft is applied: what to do next (bring participants in) |
| `protocol-guide-open` | `ProtocolGuide` | open the reference explaining the 8 mandatory protocol-draft sections (help) |
| `tour-open` | `StudyHome` | open the first-study guided walkthrough (help) |
| `tour-next` | `StudyTour` | advance the walkthrough to the next step |
| `tour-done` | `StudyTour` | finish the walkthrough and start working |
| `new-study` | `ProjectHome` | create a new study in the project (decision point) |
| `seed-study` | `CreateStudyFrom` | create the study from the chosen template seed (decision point) |
| `project-list` | `Projects` | the list of projects you belong to, each row carrying its study count (landmark) |
| `new-project` | `Projects` | open the inline composer that creates a project (decision point) |
| `project-switcher` | `ProjectSwitcher` | open the ⌘K project switcher (landmark) |
| `project-nav` | `AppFrame` | the project sidebar (landmark) |
| `sign-in` | `SignInScreen` | the sign-in gate (landmark), shown instead of project UI until a credential exists |
| `invite` | `InviteDialog` | open the invite dialog (decision point) |
| `member-actions` | `MembersTable` | open a member's role/remove menu (decision point) |
| `study-tabs` | `StudyHome` | the study workspace section tabs (landmark) |
| `study-export` | `ExportStudy` | open the share/export menu for this study |
| `export-replication-kit` | `ExportStudy` | download the byte-reproducible replication kit (FR-PROT-7) |
| `export-elicitation-record` | `ExportStudy` | download the elicitation record (FR-CONV-6) |
| `export-notebook` | `ExportStudy` | download the starter notebook + data dictionary, zipped (FR-ANA-6) |
| `power-curve` | `PowerPanel` | the power/sensitivity chart on the Planning surface (P2-2) |
| `power-required` | `PowerPanel` | the required-n table: effect size × per-group/total n × target reached |
| `constellation` | `Constellation` | the citation-graph canvas (landmark) |
| `constellation-lens` | `Constellation` | which citation relation is on screen  -  earlier / later / similar work, or all; `data-agent-kind` carries the current lens |
| `metric-strip` | `MetricStrip` | the per-condition metric distribution chart (landmark) |
| `dry-run-plan` | `DryRunPlan` | the dry run's analysis-plan result: which prescribed tests ran on synthetic data, and which could not (landmark) |
| `dry-run-recipe` | `DryRunPlan` | one prescribed test that ran, with its verbatim statistical summary; `data-agent-ref` carries the recipe id |
| `live-sessions` | `LiveSessions` | the live-session monitor: who is running right now, what task, and whether data is arriving (landmark, FR-DASH-3) |
| `live-session` | `LiveSessions` | one running session; `data-agent-ref` carries its session id |
| `enrollment-panel` | `EnrollmentPanel` | the study's participant enrollment surface (landmark) |
| `mint-tokens` | `MintDialog` | open the mint-enrollment-links dialog (decision point) |
| `open-in-vscode` | `MintDialog`, `EnrollmentPanel` | the vscode:// deep-link companion to a minted connection string (decision point) |
| `extension-install-link` | `EnrollmentPanel` | where a participant without the extension gets it  -  TERN ships as a GitHub release artifact, not on the Marketplace, so the deep link has nothing to resolve to until this is followed (decision point) |
| `new-study-open` | `ProjectHome` | open the inline new-study composer (decision point) |
| `steer-dial` | `SteerDial` | how much the researcher wants the assistant to drive this conversation: the one control that moves both register and initiative (`elicitation.STEER_LEVELS`) (decision point) |
| `toggle-popover` | `TogglePopover` | per-metric capture-toggle popover showing label, grounding, and apply button (FR-DASH-11) |
| `live-sessions` | `LiveSessions` | the live-session monitor: who is running right now (landmark, FR-DASH-10) |
| `live-session` | `LiveSessions` | one running session, with its event rate, task, condition and gap count; `data-agent-ref` carries the session id |
| `swimlane-timeline` | `SwimlaneTimeline` | the per-session swimlane chart (landmark, FR-DASH-4) |
