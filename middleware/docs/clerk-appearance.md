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

## Values: light theme (the platform default)

| Dashboard control (`variable`)          | Value                | Token              |
| --------------------------------------- | -------------------- | ------------------ |
| Primary color (`colorPrimary`)          | `#1059d8`            | `--accent`         |
| Background (`colorBackground`)          | `#eff3f9`            | `--bg`             |
| Foreground/text (`colorText`)           | `#0e1b2d`            | `--text`           |
| Secondary text (`colorTextSecondary`)   | `#52637c`            | `--text-muted`     |
| Input background (`colorInputBackground`)| `#ffffff`           | `--surface`        |
| Input text (`colorInputText`)           | `#0e1b2d`            | `--text`           |
| Neutral seed (`colorNeutral`)           | `#0e1b2d`            | `--ink`            |
| Danger (`colorDanger`)                  | `#b0231b`            | `--status-critical`|
| Border radius (`borderRadius`)          | `8px` (`0.5rem`)     | `--radius-input`   |
| Font family (`fontFamily`)              | `Archivo`            | see note ↓         |

**No `colorSuccess` / `colorWarning` row.** The design system dropped
dedicated success/warning hues: grounding strength is shown by a magnitude
mark (size), not colour, so there is no green or amber token left to hand to
Clerk (see `--unsourced`, `--status-critical`,
[`platform/README.md`](../../platform/README.md#conventions) for the mark
convention that replaced them). Leave those two Dashboard fields at their
Clerk defaults rather than force a mapping that doesn't exist here.

**Font note.** The UI face is **Archivo** (`Archivo Variable`, via
`@fontsource-variable/archivo`), a stock Google Font, so Clerk's picker
should offer it directly. The platform's numeral/mono face, **Spline Sans
Mono**, is reserved for data and quantities, not chrome or labels, so it is
not the right choice for a sign-in form's `fontFamily`.

## Values: dark theme

The hosted portal is effectively one theme; pick a lane. Light is the better
default (it's the platform's primary look). For a dark portal instead:

| `variable`             | Value     | Token              |
| ---------------------- | --------- | ------------------ |
| `colorPrimary`         | `#5ea3ff` | `--accent` (dark)  |
| `colorBackground`      | `#05090f` | `--bg` (dark)      |
| `colorText`            | `#e9eff8` | `--text` (dark)    |
| `colorInputBackground` | `#1a2b48` | `--surface` (dark) |
| `colorDanger`          | `#ff8b7f` | `--status-critical`|

Making the portal *follow* the viewer's OS/app theme is embedded-only
(Option 1).
