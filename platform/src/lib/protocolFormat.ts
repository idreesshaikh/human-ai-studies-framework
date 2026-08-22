/* Turns the compiled protocol dict (CompileResult.protocol  -  the same
 * structured draft the compiler yaml.safe_dump()s) into short prose lines
 * for the draft rail, instead of dumping the raw YAML. Pure and
 * schema-tolerant: known top-level keys (per
 * protocol/src/protocol/schema/study-protocol.schema.json) get a
 * hand-written formatter; anything else falls back to a generic
 * humanized-label + flattened-value line so a future schema addition never
 * silently disappears. */

export interface ProtocolSection {
  heading: string;
  lines: string[];
}

function asArray(v: unknown): unknown[] {
  return Array.isArray(v) ? v : [];
}

function asRecord(v: unknown): Record<string, unknown> {
  return v && typeof v === "object" && !Array.isArray(v)
    ? (v as Record<string, unknown>)
    : {};
}

function asString(v: unknown): string {
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return "";
}

function humanizeKey(key: string): string {
  const spaced = key.replace(/([a-z0-9])([A-Z])/g, "$1 $2").replace(/[-_]+/g, " ");
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/** Recursively renders any JSON value into one readable line  -  used for
 * instrument configs and any section this module doesn't know about yet. */
function describeValue(v: unknown): string {
  if (v == null) return "";
  if (Array.isArray(v)) return v.map(describeValue).filter(Boolean).join(", ");
  if (typeof v === "object") {
    return Object.entries(v as Record<string, unknown>)
      .map(([k, val]) => `${humanizeKey(k)}: ${describeValue(val)}`)
      .filter(Boolean)
      .join(" · ");
  }
  return String(v);
}

const INSTRUMENT_DISPLAY_NAMES: Record<string, string> = {
  tern: "TERN",
  agentCapture: "Agent capture",
  taskHarness: "Task harness",
};

function formatStudy(study: Record<string, unknown>): ProtocolSection {
  const lines: string[] = [];
  const title = asString(study.title);
  if (title) lines.push(title);
  const bits: string[] = [];
  const researchers = asArray(study.researchers).map(asString).filter(Boolean);
  if (researchers.length) bits.push(`led by ${researchers.join(", ")}`);
  const ethicsRef = asString(study.ethicsRef);
  if (ethicsRef) bits.push(`ethics: ${ethicsRef}`);
  if (bits.length) lines.push(bits.join(" · "));
  return { heading: "Study", lines };
}

function formatResearchQuestions(rqs: unknown[]): ProtocolSection {
  const lines = rqs
    .map((rq) => {
      const r = asRecord(rq);
      const id = asString(r.id);
      const text = asString(r.text);
      return id && text ? `${id}: ${text}` : id || text;
    })
    .filter(Boolean);
  return { heading: "Research questions", lines };
}

function formatParticipants(p: Record<string, unknown>): ProtocolSection {
  const bits: string[] = [];
  if (typeof p.planned === "number") {
    bits.push(`${p.planned} participant${p.planned === 1 ? "" : "s"}`);
  }
  if (typeof p.design === "string") bits.push(p.design.replace(/-/g, " "));
  if (typeof p.counterbalanced === "boolean") {
    bits.push(p.counterbalanced ? "counterbalanced" : "not counterbalanced");
  }
  const lines = bits.length ? [bits.join(" · ")] : [];
  const agents = asArray(p.agents);
  if (agents.length) {
    const roster = agents
      .map((a) => {
        const r = asRecord(a);
        return `${asString(r.id)} (${asString(r.tool)}/${asString(r.model)})`;
      })
      .join(", ");
    lines.push(`${agents.length} agent participant${agents.length === 1 ? "" : "s"}: ${roster}`);
  }
  return { heading: "Participants", lines };
}

function formatConditions(conditions: unknown[]): ProtocolSection {
  return { heading: "Conditions", lines: conditions.map(asString).filter(Boolean) };
}

function formatSession(session: Record<string, unknown>): ProtocolSection {
  const lines: string[] = [];
  if (typeof session.durationMinutes === "number") {
    lines.push(`${session.durationMinutes}-minute session.`);
  }
  const task = asString(session.taskDescription).replace(/\s+/g, " ").trim();
  if (task) lines.push(task);
  return { heading: "Session", lines };
}

/* The declared tasks (protocol v5)  -  what each session actually runs, as
 * opposed to `session.taskDescription`, which is the study's prose summary.
 * Reads as a numbered list because the count matters: a within-subjects
 * study wants at least one task per condition. */
function formatTasks(tasks: unknown[]): ProtocolSection {
  const lines = tasks.map((entry) => {
    const task = asRecord(entry);
    const title = asString(task.title) || asString(task.id);
    const detail: string[] = [];
    if (typeof task.minutes === "number") detail.push(`${task.minutes} min`);
    const conditions = asArray(task.conditions).map(asString).filter(Boolean);
    if (conditions.length) detail.push(conditions.join(" / "));
    const materials = asString(task.materials);
    if (materials) detail.push(materials);
    return detail.length ? `${title}: ${detail.join(" · ")}` : title;
  });
  return { heading: "Tasks", lines: lines.filter(Boolean) };
}

function formatInstruments(instruments: Record<string, unknown>): ProtocolSection {
  const lines = Object.entries(instruments).map(([name, config]) => {
    const label = INSTRUMENT_DISPLAY_NAMES[name] ?? humanizeKey(name);
    const detail = describeValue(config);
    return detail ? `${label}: ${detail}` : label;
  });
  return { heading: "Instruments", lines };
}

function formatAnalysisPlan(plan: unknown[]): ProtocolSection {
  const lines = plan
    .map((entry) => {
      const r = asRecord(entry);
      const rq = asString(r.rq);
      const recipes = asArray(r.recipes).map(asString).filter(Boolean);
      if (!rq) return "";
      return recipes.length ? `${rq} → ${recipes.join(", ")}` : rq;
    })
    .filter(Boolean);
  return { heading: "Analysis plan", lines };
}

function formatLiterature(lit: unknown[]): ProtocolSection {
  const lines = lit
    .map((entry) => {
      const r = asRecord(entry);
      const ref = asString(r.paperRef);
      const justifies = asArray(r.justifies).map(asString).filter(Boolean);
      if (!ref) return "";
      return justifies.length ? `${ref} justifies ${justifies.join(", ")}` : ref;
    })
    .filter(Boolean);
  return { heading: "Literature", lines };
}

function formatPhases(phases: unknown[]): ProtocolSection {
  const records = phases.map(asRecord);
  const names = records.map((r) => asString(r.name)).filter(Boolean);
  const lines = names.length ? [names.join(" → ")] : [];
  const gated = records
    .filter((r) => asArray(r.gates).length > 0)
    .map((r) => `${asString(r.name)} (${asArray(r.gates).map(asString).join(", ")})`);
  if (gated.length) lines.push(`Gated: ${gated.join(" · ")}`);
  return { heading: "Phases", lines };
}

const SECTION_ORDER = [
  "study",
  "researchQuestions",
  "participants",
  "conditions",
  "session",
  "tasks",
  "instruments",
  "analysisPlan",
  "literature",
  "phases",
] as const;

const FORMATTERS: Record<(typeof SECTION_ORDER)[number], (value: unknown) => ProtocolSection> = {
  study: (v) => formatStudy(asRecord(v)),
  researchQuestions: (v) => formatResearchQuestions(asArray(v)),
  participants: (v) => formatParticipants(asRecord(v)),
  conditions: (v) => formatConditions(asArray(v)),
  session: (v) => formatSession(asRecord(v)),
  tasks: (v) => formatTasks(asArray(v)),
  instruments: (v) => formatInstruments(asRecord(v)),
  analysisPlan: (v) => formatAnalysisPlan(asArray(v)),
  literature: (v) => formatLiterature(asArray(v)),
  phases: (v) => formatPhases(asArray(v)),
};

/** Keys with no dedicated formatter that also aren't worth a section of
 * their own (internal bookkeeping, not part of the story a researcher
 * reads). */
const SKIP_KEYS = new Set(["protocolVersion"]);

export function summarizeProtocol(protocol: Record<string, unknown>): ProtocolSection[] {
  const sections: ProtocolSection[] = [];
  for (const key of SECTION_ORDER) {
    if (!(key in protocol)) continue;
    const section = FORMATTERS[key](protocol[key]);
    if (section.lines.some((l) => l.trim())) sections.push(section);
  }
  for (const [key, value] of Object.entries(protocol)) {
    if ((SECTION_ORDER as readonly string[]).includes(key) || SKIP_KEYS.has(key)) continue;
    const section = { heading: humanizeKey(key), lines: [describeValue(value)] };
    if (section.lines.some((l) => l.trim())) sections.push(section);
  }
  return sections;
}
