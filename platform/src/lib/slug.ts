/* Slugs read as words.
 *
 * A study's id IS its slug in the schema, and a registry entry's is too, so
 * these strings get printed as titles all over the app — a workspace's <h1>
 * included. Sentence-casing the first letter alone is not enough: the terms a
 * methods tool is full of are acronyms, and `rct-between-subjects` rendering
 * as "Rct between subjects" (or an AI study as "…in ai code review") reads as
 * a string that was never meant to be shown to anyone.
 *
 * Only the acronyms this domain actually uses are listed. A general
 * "capitalise short words" rule would mangle real ones ("Do" → "DO").
 */
const ACRONYMS = new Set([
  "ai",
  "api",
  "cli",
  "csv",
  "doi",
  "hci",
  "ide",
  "llm",
  "ml",
  "nlp",
  "pdf",
  "rct",
  "ui",
  "ux",
  "yaml",
]);

/**
 * A registry slug as words: `rct-between-subjects` becomes
 * `RCT between subjects`, `case-study` becomes `Case study`, and
 * `trust-in-ai-code-review` becomes `Trust in AI code review`.
 */
export function humanSlug(slug: string): string {
  const words = slug.replace(/-/g, " ").trim().split(/\s+/);
  if (words.length === 0 || words[0] === "") return "";
  return words
    .map((word, i) => {
      const lower = word.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();
      // Sentence case: only the first word is capitalised, and only if the
      // author did not already capitalise it themselves.
      if (i === 0) return word.charAt(0).toUpperCase() + word.slice(1);
      return word;
    })
    .join(" ");
}
