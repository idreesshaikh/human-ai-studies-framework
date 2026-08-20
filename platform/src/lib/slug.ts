/**
 * A registry slug as words: `rct-between-subjects` becomes `Rct between subjects`,
 * `case-study` becomes `Case study`.
 */
export function humanSlug(slug: string): string {
  const words = slug.replace(/-/g, " ").trim();
  return words.charAt(0).toUpperCase() + words.slice(1);
}
