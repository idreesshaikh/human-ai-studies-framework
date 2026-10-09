/* Preserve known domain acronyms when turning slugs into readable titles. */
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
  // An emoji or symbol glued to a word ("🚀study") needs a space after it.
  const spaced = slug.replace(/(\p{Extended_Pictographic}\uFE0F?)(?=[\p{L}\p{N}])/gu, "$1 ");
  const words = spaced.replace(/-/g, " ").trim().split(/\s+/);
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
