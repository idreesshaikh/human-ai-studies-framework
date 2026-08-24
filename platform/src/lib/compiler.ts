import {
  emptyDraft,
  isFieldPatch,
  isInstrumentPatch,
  isStatisticsPatch,
  isSectionPatch,
  isTemplatePatch,
  type DesignMove,
  type ProtocolDraft,
} from "./types.ts";

/* Turns accepted design moves into a protocol draft. A pure function of
 * (base draft, accepted moves): no LLM, no clock, no randomness  -  replaying
 * the same moves against the same base always yields the same draft. The
 * conversation proposes moves; only this deterministic step builds the draft.
 *
 * For now it compiles to the client-side draft model; the same logic moves
 * server-side later to emit real protocol YAML and a diff. */
export function compile(
  base: ProtocolDraft,
  moves: DesignMove[],
): ProtocolDraft {
  const draft = structuredClone(base);
  for (const move of moves) {
    if (move.status !== "accepted") continue;
    if (move.kind === "merge-templates") {
      // A merged protocol is a real design  -  the slot reads as filled with
      // the shapes being combined (the server's merge is authoritative).
      draft.design = move.mergeData?.templateIds ?? [];
      continue;
    }
    if (!move.patch) continue; // cautions have no patch
    if (isTemplatePatch(move.patch)) {
      // The only move kind that can ever fill the mandatory `design` slot.
      draft.design = [move.patch.templateId];
      continue;
    }
    if (isInstrumentPatch(move.patch)) {
      const { op, name } = move.patch;
      if (
        (op === "add-instrument" || op === "set-instrument") &&
        !draft.instruments.includes(name)
      ) {
        draft.instruments.push(name);
      }
      // `reconfigure` tweaks an already-added instrument's config  -  it
      // never fills the slot on its own (matches the server: an add/set
      // move is what makes the instrument exist at all).
      continue;
    }
    if (isStatisticsPatch(move.patch)) {
      draft.statisticalPlan = [move.patch.recipeId];
      continue;
    }
    if (isFieldPatch(move.patch)) {
      // Only participants.* maps onto one of the core sections here  -  the
      // other fillable slots (session.*, study.*) are administrative detail
      // this client-side preview does not track. This used to match none of
      // the type guards at all, so an accepted set-field move silently did
      // not move the dot it should have: the server's own compile (the
      // authoritative unresolved list) already reflected it, but the
      // optimistic preview a researcher watches while deciding did not.
      if (move.patch.path[0] === "participants") {
        draft.participants = ["set"];
      }
      continue;
    }
    if (!isSectionPatch(move.patch)) continue;
    const { section, op, value } = move.patch;
    if (op === "append") {
      const list = draft[section];
      if (!list.includes(value)) list.push(value);
    } else {
      // `set` replaces the section's single line (scalar-ish slots)
      draft[section] = [value];
    }
  }
  return draft;
}

/** Compile from scratch over the full move history  -  the draft rail's
 * source of truth. Folding over every move (rather than mutating in place)
 * is what lets rejecting a move cleanly remove its effect. */
export function compileAll(moves: DesignMove[]): ProtocolDraft {
  return compile(emptyDraft(), moves);
}
