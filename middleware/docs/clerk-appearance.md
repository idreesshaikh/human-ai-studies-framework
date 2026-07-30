# Theming the Clerk hosted sign-in (FR-OPS-5, D29)

Applies only when the middleware runs in **`clerk`** auth mode
(`MIDDLEWARE_AUTH=clerk`; see `src/middleware/auth.py`). Self-hosted
`none`/`token` deployments never see a Clerk page and can ignore this.

## The one thing to know first

Clerk splits customization in two, and the split decides what's reachable:

- **Embedded components** (`<SignIn/>` mounted in *our* SPA): take the full
  `appearance` prop: per-element overrides, custom CSS, everything.
- **The hosted Account Portal** (Clerk's page we redirect to): **cannot take
  the `appearance` prop or custom CSS.** It is customizable *only* through the
  Clerk Dashboard's theme controls.

We are on the hosted portal, so the ceiling is **color / radius / logo / font
match, not character match.** The instrument's signature (the reading serif
for headings, the soft lifted-card shadow) needs custom CSS and is therefore
*not achievable* here. Getting the real look means embedding `<SignIn/>` in
the platform app (`@clerk/clerk-react` + `<ClerkProvider>` + a `/sign-in`
route), a frontend feature, gated by golden rules 1 & 5 (a requirement
trace and a build-vs-adopt row) before code.

Source of truth for every value below: `platform/src/styles/tokens.css`. If a
token changes there, re-derive here; these are a hand-copied snapshot, not a
live binding.

## Where in the Dashboard

Clerk Dashboard → your app → **Customization** → **Theme** (and **Branding**
for the logo). Exact labels drift between Clerk versions; it's the visual theme
editor that maps to Clerk's `variables`. Fields not offered by the editor are
code-only `variables`: skip them; they don't reach the hosted portal.

## Values: light theme ("Daylight instrument", the platform default)

| Dashboard control (`variable`)          | Value                | Token              |
| --------------------------------------- | -------------------- | ------------------ |
| Primary color (`colorPrimary`)          | `#2a45c0`            | `--accent`         |
| Background (`colorBackground`)          | `#e9edf3`            | `--bg`             |
| Foreground/text (`colorText`)           | `#16202e`            | `--text`           |
| Secondary text (`colorTextSecondary`)   | `#55627a`            | `--text-muted`     |
| Input background (`colorInputBackground`)| `#f7f9fc`           | `--surface`        |
| Input text (`colorInputText`)           | `#16202e`            | `--text`           |
| Neutral seed (`colorNeutral`)           | `#16202e`            | `--ink`            |
| Danger (`colorDanger`)                  | `#c0281f`            | `--status-critical`|
| Success (`colorSuccess`)                | `#1f7a4d`            | `--grounded`       |
| Warning (`colorWarning`)                | `#8a5710`            | `--unsourced`      |
| Border radius (`borderRadius`)          | `8px` (`0.5rem`)     | `--radius-input`   |
| Font family (`fontFamily`)              | `IBM Plex Mono`      | see note ↓         |

**Font note.** The machine face is **IBM Plex Mono**, self-hosted via
`@fontsource/ibm-plex-mono`; it's a stock Google Font, so Clerk's picker
should offer it directly (no substitution needed, unlike the old licensed
display face). The reading serif (**Newsreader**) never reaches the hosted
portal (Clerk's theme editor has no serif heading slot), so color + radius
carry the match there.

## Values: dark theme ("Observatory")

The hosted portal is effectively one theme; pick a lane. Light is the better
default (it's the platform's primary look). For a dark portal instead:

| `variable`             | Value     | Token              |
| ---------------------- | --------- | ------------------ |
| `colorPrimary`         | `#6ea8ff` | `--accent` (dark)  |
| `colorBackground`      | `#0e1420` | `--bg` (dark)      |
| `colorText`            | `#e6ecf5` | `--text` (dark)    |
| `colorInputBackground` | `#172033` | `--surface` (dark) |
| `colorSuccess`         | `#4ec98a` | `--grounded` (dark)|
| `colorWarning`         | `#e0a94f` | `--unsourced` (dark)|
| `colorDanger`          | `#ff6b5e` | `--status-critical`|

Making the portal *follow* the viewer's OS/app theme is embedded-only
(Option 1).
