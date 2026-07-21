/**
 * The connection string a participant pastes to enroll their IDE: the copy-
 * safe `serverUrl#token`. Portable core (no vscode). The middleware mints it;
 * we split on the last `#` (base URLs never contain `#`; tokens are URL-safe
 * base64).
 */

export interface Connection {
  /** Middleware base URL, trailing slash stripped. */
  serverUrl: string;
  /** The raw pairing token (what /pair/redeem expects). */
  token: string;
}

export class ConnectionStringError extends Error {}

export function decodeConnectionString(raw: string): Connection {
  const s = raw.trim();
  const i = s.lastIndexOf('#');
  if (i <= 0) {
    throw new ConnectionStringError(
      'That does not look like a connection string — paste the whole line your researcher gave you.',
    );
  }
  const serverUrl = s.slice(0, i).replace(/\/$/, '');
  const token = s.slice(i + 1);
  if (!/^https?:\/\//.test(serverUrl)) {
    throw new ConnectionStringError(
      'The connection string must start with http(s)://',
    );
  }
  if (!token) {
    throw new ConnectionStringError(
      'The connection string is missing its token.',
    );
  }
  return { serverUrl, token };
}
