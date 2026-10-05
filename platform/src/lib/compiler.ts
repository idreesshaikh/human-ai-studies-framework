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
 * It compiles the client-side preview; the server's compiler remains
 * authoritative for protocol YAML and the audited diff. */
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
      const path = move.patch.path.join(".");
      if (path === "comparison") {
        const values = legacyComparisonValues(move.patch.value);
        for (const value of values) {
          if (!draft.conditions.includes(value)) draft.conditions.push(value);
        }
      } else if (path === "design.conditionOrder") {
        setParticipantLine(draft, "condition order", move.patch.value);
      } else if (move.patch.path[0] === "participants") {
        setParticipantLine(
          draft,
          move.patch.path.slice(1).join(" "),
          move.patch.value,
        );
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

/* The participants slot shows the move's real planned value ("12
 * participants"), never a placeholder. A repeat of the same field replaces its
 * earlier line rather than stacking. */
function setParticipantLine(
  draft: ProtocolDraft,
  field: string,
  value: unknown,
): void {
  const text = Array.isArray(value) ? value.join(", ") : String(value ?? "");
  const line =
    field === "planned" && /^\d+$/.test(text)
      ? `${text} participant${text === "1" ? "" : "s"}`
      : `${field || "participants"}: ${text}`;
  const prefix = field === "planned" ? /^\d+ participants?$/ : new RegExp(`^${field}: `);
  draft.participants = [...draft.participants.filter((l) => !prefix.test(l)), line];
}

function legacyComparisonValues(value: unknown): string[] {
  const raw = Array.isArray(value) ? value : [value];
  return raw
    .flatMap((item) =>
      typeof item === "string"
        ? item.split(/\s+(?:vs\.?|versus)\s+|\r?\n/i)
        : [],
    )
    .map((item) => item.trim().replace(/^[,;]+|[,;]+$/g, ""))
    .filter(Boolean);
}

function lastManualEntry(moves: DesignMove[]): number {
  for (let i = moves.length - 1; i >= 0; i--) {
    const { status, patch } = moves[i];
    if (status === "accepted" && patch && isTemplatePatch(patch) && patch.manual) return i;
  }
  return -1;
}

/** The moves still in effect: a manual entry replaces those before it. */
export function sinceManualEntry(moves: DesignMove[]): DesignMove[] {
  return moves.slice(Math.max(lastManualEntry(moves), 0));
}

export const asList = (value: unknown): unknown[] => (Array.isArray(value) ? value : []);
export const asRecord = (value: unknown): Record<string, unknown> =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
export const asText = (value: unknown): string =>
  typeof value === "string" || typeof value === "number" ? String(value) : "";

/** The draft sections a compiled protocol fills. */
export function protocolToDraft(protocol: Record<string, unknown>): ProtocolDraft {
  const participants = asRecord(protocol.participants);
  const texts = (values: unknown[]) => values.map(asText).filter(Boolean);
  return {
    researchQuestions: texts(asList(protocol.researchQuestions).map((rq) => asRecord(rq).text)),
    design: texts([participants.design]),
    participants: texts([participants.planned && `${asText(participants.planned)} planned`]),
    conditions: texts(asList(protocol.conditions)),
    measures: texts(asList(protocol.measures)),
    instruments: Object.keys(asRecord(protocol.instruments)),
    statisticalPlan: texts(asList(protocol.analysisPlan).flatMap((e) => asList(asRecord(e).recipes))),
    ethics: texts([asRecord(protocol.study).ethicsRef]),
  };
}

/** Compile from scratch over the full move history  -  the draft rail's
 * source of truth. Folding over every move (rather than mutating in place)
 * is what lets rejecting a move cleanly remove its effect. A manual entry
 * replaces the moves before it, and its template content is only known to
 * the server, so the server's compiled protocol fills the draft. */
export function compileAll(
  moves: DesignMove[],
  compiled?: Record<string, unknown>,
): ProtocolDraft {
  if (lastManualEntry(moves) < 0) return compile(emptyDraft(), moves);
  return compiled ? protocolToDraft(compiled) : compile(emptyDraft(), sinceManualEntry(moves));
}
