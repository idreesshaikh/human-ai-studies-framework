# Undo a design-move decision

**Status:** approved, ready for implementation plan.
**Traces to:** FR-CONV-1 (individually acceptable/rejectable design moves),
a refinement of that existing interaction, not a new requirement.

## Problem

`MoveCard` shows Accept/Reject only while a move's status is `"proposed"`.
Once decided, the buttons are removed for good (`{!decided && (...)}` in
`platform/src/components/conversation/MoveCard.tsx`). A misclick on Accept
or Reject is permanent. There is no way to reverse a decision.

## Scope

- Undo covers **both** Accept and Reject (not accept-only).
- Undo stays available **indefinitely**: no timer, no snackbar-style
  auto-expiry. It's a plain, always-visible secondary control on a decided
  card, consistent with the rest of this UI having no disappearing
  affordances.
- Undo **reopens the card**: the move's status returns to `"proposed"`,
  Accept/Reject reappear, and the researcher decides again from scratch. It
  does not toggle directly to the opposite decision.

## Why no restriction around an already-approved draft

`POST /studies/{id}/conversation/approve` snapshots the currently-accepted
moves into a `Compilation` row at that point in time (`middleware/app.py`,
`approve_compilation`). It does not lock the individual `DesignMoveRow`
rows. Undoing a long-ago-accepted move never rewrites an already-applied
protocol version; it only changes what the *next* compile produces. That's
exactly how the amendment system already expects drift between "current
draft state" and "last-applied protocol version" to work (`is_amendment`
branch, same function). So undo needs no extra gating logic tied to
approval/ethics state; it can simply always be available.

## Backend change

`middleware/src/middleware/app.py`, `decide_move` (`POST
/studies/{study_id}/conversation/moves/{move_id}/decision`):

- Widen the accepted `status` values from `("accepted", "rejected")` to
  `("accepted", "rejected", "proposed")`. `"proposed"` is the undo case:
  "decide proposed again."
- When the new status is `"proposed"`, clear `decided_by`/`decided_at`
  (set to `None`): a reopened move shouldn't carry a stale decision
  timestamp/attribution.
- Otherwise unchanged: still updates the same row (never deletes), still
  publishes the same `{"changed": "move", "moveId": ..., "status": ...}`
  presence event so collaborators see the reopen live.
- Update the docstring to mention reopening.

No schema migration: `status` is already a free-form column holding
`"proposed"` as its default value everywhere else in the system.

Both compilers already filter strictly on `status === "accepted"`
(`platform/src/lib/compiler.ts` line 23, and
`middleware/src/middleware/compiler.py`'s `compile_moves`). A reopened
move already falls out of the next compile with no further changes needed
there.

## Frontend change

- `platform/src/lib/conversationApi.ts`: widen `decide`'s `status` parameter
  type from `"accepted" | "rejected"` to `"accepted" | "rejected" |
  "proposed"`.
- `platform/src/components/conversation/ConversationView.tsx`: widen
  `decide(moveId, status)`'s `status` parameter type the same way. The
  function body is unchanged: it's already a generic
  optimistic-update-with-rollback that sets whatever status it's given and
  rolls back `turns` to `before` on a server error, showing the existing
  `note` line ("That decision didn't reach the server. Try it again.").
- `platform/src/components/conversation/MoveCard.tsx`:
  - Widen the `onDecide` prop's type to match.
  - When `decided` (status !== `"proposed"`), render a small secondary
    "Undo" button next to the existing status label (`"in draft"` /
    `"noted"` / `"dismissed"`), calling `onDecide(move.moveId,
    "proposed")`.
  - No keyboard shortcut for undo. The existing `a`/`r` shortcuts only fire
    while the card itself has DOM focus, which the component auto-grants
    only to *undecided* cards on appearance (`useEffect` keyed on
    `!decided`). Undo is an occasional corrective action taken potentially
    much later while scrolled elsewhere in the thread, so a plain clickable
    button is sufficient; wiring a shortcut would require re-engineering the
    card's focus/tabIndex management for no real benefit.

## Testing

- `middleware/tests/test_conversation.py`: one new case: accept a move,
  undo it (`POST .../decision` with `status: "proposed"`), assert the
  response/row status is `"proposed"` and `decided_by`/`decided_at` are
  cleared, then compile and assert the move is absent from the draft.
- No new frontend test tooling: this project has no component-test setup
  (`docs/roadmap`'s own note: pushes decision logic into pure `.ts` modules
  covered by `verify-*.mjs`, and `.tsx` is covered by `tsc`/eslint/build
  only). This change has no new pure logic to extract; it's a type
  widening plus a button, so `tsc`/eslint/build are the gate, same as
  every other `MoveCard.tsx` change to date (that component has never had a
  dedicated test).

## Out of scope

- Any timer/snackbar-style undo UX.
- A keyboard shortcut for undo.
- Blocking undo based on ethics-approval or amendment state.
- A history/audit trail of decision changes beyond the current
  `status`/`decided_by`/`decided_at` fields: matches the existing "row is
  updated, never deleted" model; no append-only decision ledger is being
  introduced.
