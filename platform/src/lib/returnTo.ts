/* Where to send someone back to after they sign in.
 *
 * A gated route needs none of this: `Shell` renders the sign-in surface in
 * place, at the URL the researcher asked for, so signing in reloads that same
 * URL and they arrive where they were going. The problem is the sign-in links
 * on PUBLIC pages  -  the repertoire's "Sign in to keep this", the frame's
 * header button  -  which have to leave a page that was working fine, and had
 * nowhere to point but `/home`. That dropped the researcher on their project
 * list having just abandoned the merged protocol they were trying to save.
 *
 * Sign-in ends in `location.reload()` (auth.tsx: cached failed loads have to
 * restart signed in), so the return path cannot be component state, a ref, or
 * a module variable  -  none of them survive. It travels in the query string,
 * which does.
 */

const DEFAULT_NEXT = "/home";

/** Longer than any route this app has; a cap keeps a hostile link from
 * stuffing the address bar. */
const MAX_NEXT = 512;

/**
 * A `next` value that is safe to navigate to: our own app, our own origin.
 *
 * Anything else falls back to `/home` rather than being honoured. A raw
 * redirect target taken from a query string is the classic open-redirect
 * hole  -  `?next=https://evil.example` on a sign-in page hands an attacker a
 * link that starts on the real product's domain and ends on theirs, with the
 * researcher's trust already spent. Protocol-relative (`//evil.example`) and
 * backslash (`/\evil.example`) forms are the two that slip past a naive
 * "starts with /" check, so both are rejected explicitly.
 */
export function safeNext(raw: string | null | undefined): string {
  if (!raw) return DEFAULT_NEXT;
  if (raw.length > MAX_NEXT) return DEFAULT_NEXT;
  if (!raw.startsWith("/")) return DEFAULT_NEXT;
  if (raw.startsWith("//") || raw.startsWith("/\\")) return DEFAULT_NEXT;
  return raw;
}

/**
 * The href for a "Sign in" control, carrying where the researcher is now so
 * they land back on it. Pass `location.pathname + location.search`.
 *
 * `/signin` itself is never a return target  -  bouncing someone back to the
 * sign-in page after they signed in is a loop, and it is what happens if a
 * header "Sign in" button on the sign-in page builds its own href from the
 * current location.
 */
export function signInHref(from: string): string {
  const next = safeNext(from);
  if (next === DEFAULT_NEXT || next.startsWith("/signin")) return "/signin";
  return `/signin?next=${encodeURIComponent(next)}`;
}
