/** Only scholarly identifiers belong in reader-facing provenance. Internal
 * corpus keys and requirement references are implementation details. */
export function publicPaperReference(ref: string): string | null {
  const value = ref.trim();
  if (!value || value.startsWith("corpus:") || /^(FR|NFR|D)[-_]/i.test(value)) {
    return null;
  }
  if (value.startsWith("arxiv:")) return `arXiv:${value.slice(6)}`;
  if (value.startsWith("doi:")) return `doi:${value.slice(4)}`;
  return value;
}

export function paperIdentifier(paper: {
  paperRef: string;
  doi?: string;
  arxivId?: string;
}): string | null {
  if (paper.doi) return `doi:${paper.doi.replace(/^doi:/i, "")}`;
  if (paper.arxivId) return `arXiv:${paper.arxivId.replace(/^arxiv:/i, "")}`;
  return publicPaperReference(paper.paperRef);
}
