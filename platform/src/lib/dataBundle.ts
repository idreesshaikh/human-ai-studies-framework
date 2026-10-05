/* The data-bundle download: the collected study data as a zip of tidy CSVs.
 * Kept free of browser APIs so its path and filename are checkable in
 * `scripts/verify-data-export.mjs`. */

/** Dry-run (synthetic) rows are left out unless the caller opts in. */
export function dataBundlePath(study: string, includeSynthetic = false): string {
  const query = includeSynthetic ? "?includeSynthetic=true" : "";
  return `/studies/${encodeURIComponent(study)}/data-bundle${query}`;
}

export function dataBundleFilename(study: string): string {
  return `${study}-data.zip`;
}
