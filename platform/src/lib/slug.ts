

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

export function humanSlug(slug: string): string {
  const words = slug.replace(/-/g, " ").trim().split(/\s+/);
  if (words.length === 0 || words[0] === "") return "";
  return words
    .map((word, i) => {
      const lower = word.toLowerCase();
      if (ACRONYMS.has(lower)) return lower.toUpperCase();

      if (i === 0) return word.charAt(0).toUpperCase() + word.slice(1);
      return word;
    })
    .join(" ");
}
