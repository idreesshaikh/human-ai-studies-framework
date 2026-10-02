export interface Connection {
  serverUrl: string;

  token: string;
}

export class ConnectionStringError extends Error {}

export function decodeConnectionString(raw: string): Connection {
  const s = raw.trim();
  const i = s.lastIndexOf('#');
  if (i <= 0) {
    throw new ConnectionStringError(
      'That does not look like a connection string  -  paste the whole line your researcher gave you.',
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
