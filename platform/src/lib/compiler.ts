import {
  emptyDraft,
  isSectionPatch,
  isTemplatePatch,
  type DesignMove,
  type ProtocolDraft,
} from "./types.ts";

/* Turns accepted design moves into a protocol draft. A pure function of
 * (base draft, accepted moves): no LLM, no clock, no randomness — replaying
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
    if (move.status !== "accepted" || !move.patch) continue; // cautions have no patch
    if (isTemplatePatch(move.patch)) {
      // The only move kind that can ever fill the mandatory `design` slot.
      draft.design = [move.patch.templateId];
      continue;
    }
    if (!isSectionPatch(move.patch)) continue; // instrument patches: not folded into this preview
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

/** Compile from scratch over the full move history — the draft rail's
 * source of truth. Folding over every move (rather than mutating in place)
 * is what lets rejecting a move cleanly remove its effect. */
export function compileAll(moves: DesignMove[]): ProtocolDraft {
  return compile(emptyDraft(), moves);
}
