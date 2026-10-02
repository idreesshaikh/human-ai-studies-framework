

export interface DiffLine {
  line: string;
  kind: "add" | "remove" | "context" | "hunk";
}

export interface Plates {

  record: DiffLine[];

  before: DiffLine[];

  after: DiffLine[];

  firstVersion: boolean;

  rows: number;
}

function strip(d: DiffLine): DiffLine {
  return d.kind === "add" || d.kind === "remove"
    ? { ...d, line: d.line.slice(1) }
    : d;
}

export function buildPlates(lines: DiffLine[]): Plates {
  const record = lines.map(strip);
  const before = lines.filter((d) => d.kind !== "add").map(strip);
  const after = lines.filter((d) => d.kind !== "remove").map(strip);
  return {
    record,
    before,
    after,
    firstVersion: before.length === 0,
    rows: Math.max(record.length, before.length, after.length),
  };
}

export function hasEarlierVersion(lines: DiffLine[]): boolean {
  return lines.some((d) => d.kind === "remove" || d.kind === "context");
}
