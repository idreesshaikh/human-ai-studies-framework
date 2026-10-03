

export const EXTENSION_ID = "idreesrazak.tern";

export const EXTENSION_NAME = "TERN";

export const EXTENSION_RELEASES_URL =
  "https://github.com/idreesshaikh/human-ai-studies-framework/releases/latest";

export function vscodeDeepLink(connectionString: string): string {
  return `vscode://${EXTENSION_ID}/pair?c=${encodeURIComponent(connectionString)}`;
}
