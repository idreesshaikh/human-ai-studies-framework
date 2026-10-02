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

export function compile(
  base: ProtocolDraft,
  moves: DesignMove[],
): ProtocolDraft {
  const draft = structuredClone(base);
  for (const move of moves) {
    if (move.status !== "accepted") continue;
    if (move.kind === "merge-templates") {

      draft.design = move.mergeData?.templateIds ?? [];
      continue;
    }
    if (!move.patch) continue;
    if (isTemplatePatch(move.patch)) {

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

      continue;
    }
    if (isStatisticsPatch(move.patch)) {
      draft.statisticalPlan = [move.patch.recipeId];
      continue;
    }
    if (isFieldPatch(move.patch)) {

      const path = move.patch.path.join(".");
      if (path === "comparison") {
        const values = legacyComparisonValues(move.patch.value);
        for (const value of values) {
          if (!draft.conditions.includes(value)) draft.conditions.push(value);
        }
      } else if (path === "design.conditionOrder") {
        draft.participants = ["set"];
      } else if (move.patch.path[0] === "participants") {
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

      draft[section] = [value];
    }
  }
  return draft;
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

export function compileAll(moves: DesignMove[]): ProtocolDraft {
  return compile(emptyDraft(), moves);
}
