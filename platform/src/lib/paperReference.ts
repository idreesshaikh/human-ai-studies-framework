/** Only scholarly identifiers belong in reader-facing provenance. Internal
 * corpus keys and requirement references are implementation details. */
export function publicPaperReference(ref: string): string | null {
  const value = ref.trim();
  if (
    !value ||
    /^(corpus|pdf):/i.test(value) ||
    /^(FR|NFR|D)[-_]/i.test(value)
  ) {
    return null;
  }
  if (value.startsWith("arxiv:")) return `arXiv:${value.slice(6)}`;
  if (value.startsWith("doi:")) return `doi:${value.slice(4)}`;
  return value;
}

/** Normalize the identifiers and source links a researcher can paste. */
export function paperLookupInput(
  raw: string,
): { arxivId?: string; doi?: string } | null {
  let value = raw.trim();
  if (/^https?:\/\//i.test(value)) {
    try {
      const url = new URL(value);
      if (
        ["arxiv.org", "www.arxiv.org", "export.arxiv.org"].includes(
          url.hostname,
        )
      ) {
        value = decodeURIComponent(url.pathname).replace(
          /^\/(abs|pdf|html)\//,
          "",
        );
      } else if (
        ["doi.org", "dx.doi.org", "www.doi.org"].includes(url.hostname)
      ) {
        value = decodeURIComponent(url.pathname).slice(1);
      } else return null;
    } catch {
      return null;
    }
  }
  value = value.replace(/^(arxiv|doi):\s*/i, "");
  if (/^10\.\d{4,9}\/\S+$/i.test(value)) return { doi: value };
  value = value.replace(/\.pdf$/i, "");
  if (/^(\d{4}\.\d{4,5}|[a-z.-]+\/\d{7})(v\d+)?$/i.test(value))
    return { arxivId: value };
  return null;
}

export function paperSourceHref(paper: {
  paperRef: string;
  url?: string;
}): string | null {
  if (paper.paperRef.startsWith("arxiv:"))
    return `https://arxiv.org/abs/${paper.paperRef.slice(6)}`;
  if (paper.paperRef.startsWith("doi:"))
    return `https://doi.org/${paper.paperRef.slice(4)}`;
  if (paper.url) {
    try {
      const url = new URL(paper.url);
      if (["http:", "https:"].includes(url.protocol)) return url.href;
    } catch {
      /* Use the scholarly identifier when source metadata has no URL. */
    }
  }
  return null;
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
