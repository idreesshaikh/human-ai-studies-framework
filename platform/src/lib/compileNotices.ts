/* Compile warnings that say the compiler changed or dropped something the
 * researcher stated. They get a visible notice; neutral ones stay quiet. */
const ALTERED =
  /^(ignored|mapped|added|filled|dropped|replaced)\b|\bwas assumed\b/i;

const capitalise = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

export function splitCompileWarnings(warnings: string[] | undefined): {
  altered: string[];
  other: string[];
} {
  const altered: string[] = [];
  const other: string[] = [];
  for (const w of warnings ?? []) {
    if (ALTERED.test(w)) altered.push(capitalise(w));
    else other.push(w);
  }
  return { altered, other };
}
