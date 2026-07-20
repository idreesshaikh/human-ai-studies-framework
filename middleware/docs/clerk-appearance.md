# Theming the Clerk hosted sign-in (FR-OPS-5, D29)

Applies only when the middleware runs in **`clerk`** auth mode
(`MIDDLEWARE_AUTH=clerk`; see `src/middleware/auth.py`). Self-hosted
`none`/`token` deployments never see a Clerk page and can ignore this.

## The one thing to know first

Clerk splits customization in two, and the split decides what's reachable:

- **Embedded components** (`<SignIn/>` mounted in *our* SPA) — take the full
  `appearance` prop: per-element overrides, custom CSS, everything.
- **The hosted Account Portal** (Clerk's page we redirect to) — **cannot take
  the `appearance` prop or custom CSS.** It is customizable *only* through the
  Clerk Dashboard's theme controls.

We are on the hosted portal, so the ceiling is **color / radius / logo / font
match — not character match.** The Study Desk signature (the reading serif
for headings, the soft lifted-card shadow) needs custom CSS and is therefore
*not achievable* here. Getting the real Study-Desk look means embedding
`<SignIn/>` in the platform app (`@clerk/clerk-react` + `<ClerkProvider>` + a
`/sign-in` route) — a frontend feature, gated by golden rules 1 & 5 (a
requirement trace and a build-vs-adopt row) before code.

Source of truth for every value below: `platform/src/styles/tokens.css`. If a
token changes there, re-derive here — these are a hand-copied snapshot, not a
live binding.

## Where in the Dashboard

Clerk Dashboard → your app → **Customization** → **Theme** (and **Branding**
for the logo). Exact labels drift between Clerk versions; it's the visual theme
editor that maps to Clerk's `variables`. Fields not offered by the editor are
code-only `variables` — skip them; they don't reach the hosted portal.

## Values — light theme ("Daylight desk", the platform default)

| Dashboard control (`variable`)          | Value                | Token              |
| --------------------------------------- | -------------------- | ------------------ |
| Primary color (`colorPrimary`)          | `#2c6e72`            | `--accent`         |
| Background (`colorBackground`)          | `#f1ebdd`            | `--bg`             |
| Foreground/text (`colorText`)           | `#26221b`            | `--text`           |
| Secondary text (`colorTextSecondary`)   | `#63583f`            | `--text-muted`     |
| Input background (`colorInputBackground`)| `#fbf7ee`           | `--surface`        |
| Input text (`colorInputText`)           | `#26221b`            | `--text`           |
| Neutral seed (`colorNeutral`)           | `#26221b`            | `--ink`            |
| Danger (`colorDanger`)                  | `#b4241f`            | `--status-critical`|
| Success (`colorSuccess`)                | `#2f7a52`            | `--grounded`       |
| Warning (`colorWarning`)                | `#9e5514`            | `--unsourced`      |
| Border radius (`borderRadius`)          | `8px` (`0.5rem`)     | `--radius-input`   |
| Font family (`fontFamily`)              | `IBM Plex Mono`      | see note ↓         |

**Font note.** The machine face is **IBM Plex Mono**, self-hosted via
`@fontsource/ibm-plex-mono` — it's a stock Google Font, so Clerk's picker
should offer it directly (no substitution needed, unlike the old licensed
display face). The reading serif (**Newsreader**) never reaches the hosted
portal — Clerk's theme editor has no serif heading slot — so color + radius
carry the match there.

## Values — dark theme ("Lamplit desk")

The hosted portal is effectively one theme; pick a lane. Light is the better
default (it's the platform's primary look). For a dark portal instead:

| `variable`             | Value     | Token              |
| ---------------------- | --------- | ------------------ |
| `colorPrimary`         | `#63b7b0` | `--accent` (dark)  |
| `colorBackground`      | `#191510` | `--bg` (dark)      |
| `colorText`            | `#ece3d0` | `--text` (dark)    |
| `colorInputBackground` | `#221d16` | `--surface` (dark) |
| `colorSuccess`         | `#57c98b` | `--grounded` (dark)|
| `colorWarning`         | `#e7b45a` | `--unsourced` (dark)|
| `colorDanger`          | `#ff6b5e` | `--status-critical`|

Making the portal *follow* the viewer's OS/app theme is embedded-only
(Option 1).
