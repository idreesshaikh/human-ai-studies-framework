/* VS Code pairing URIs use the publisher.name identity from extension/package.json. */

/** `publisher.name`, exactly as VS Code resolves it. */
export const EXTENSION_ID = "idreesrazak.tern";

/** Human-readable name, for prose that shouldn't hardcode it twice. */
export const EXTENSION_NAME = "TERN";

/* TERN is published as a GitHub release artifact (a `.vsix`), never to the
 * VS Code Marketplace. This matters for the pairing flow: a Marketplace
 * extension can be installed on demand by the `vscode://` link itself, and a
 * sideloaded one cannot. A participant without it installed must be sent
 * here first, so the deep link has something to resolve to. */
export const EXTENSION_RELEASES_URL =
  "https://github.com/idreesshaikh/human-ai-studies-framework/releases/latest";

/** The deep link that pairs an installed editor with one enrollment token. */
export function vscodeDeepLink(connectionString: string): string {
  return `vscode://${EXTENSION_ID}/pair?c=${encodeURIComponent(connectionString)}`;
}
