## Building with this design system

This is the component library for a **conversational research platform** —
researchers *talk* a human-AI study into existence, grounded in a 1,000-paper
corpus. The components are React 19 + Tailwind v4, styled entirely through
**design tokens**. Build screens by composing these real components; never
re-implement them.

### Setup — wrap once, at the root

Import everything from the package global (`window.PlatformDS.*` / the bundle).
Leaf components (Button, Badge, Card, Table, the conversation pieces) need **no
provider** — render them directly. Only the app-chrome pieces that read
identity/routing (`AppFrame`, `ProjectSwitcher`, `MembersTable`,
`InviteDialog`) need the provider stack, in this order:

```jsx
<MemoryRouter>
  <ApiProvider>
    <SessionProvider>
      {/* app screens */}
    </SessionProvider>
  </ApiProvider>
</MemoryRouter>
```

`MemoryRouter`, `Routes`, `Route`, `Link` are re-exported from the bundle — use
those, not a separately-imported `react-router-dom`, so the router context
matches.

### The styling idiom — tokens, not raw values

Every colour, radius, duration, and font is a **CSS custom property** defined in
the shipped stylesheet (`styles.css` → `_ds_bundle.css`). Two ways to reach them:

1. **Tailwind utility classes** the components already use — the vocabulary:

| Concern | Utilities (real names) |
|---|---|
| Surfaces | `bg-bg` (warm paper), `bg-surface`, `bg-surface-raised` |
| Text | `text-text`, `text-text-muted` |
| Accent (indigo) | `bg-accent`, `text-accent`, `text-accent-contrast`, `bg-accent-soft` |
| Semantic | `text-grounded` (green, cited), `text-unsourced` / `bg-unsourced-soft` (amber, "your call") |
| Borders | `border-border`, `border-border-strong` |
| Radii | `rounded-card` (14px), `rounded-input` (10px), `rounded-chip` (pill) |
| Type | `font-display` (serif, for titles), `font-sans`; `.tabular` for numerals |
| Motion | easing utilities `ease-out`, `ease-in-out`; durations via the tokens `var(--motion-fast)`, `var(--motion-standard)`, `var(--motion-entrance)`, `var(--motion-settle)` |

2. **Raw `var(--*)`** for inline styles: `var(--accent)`, `var(--text)`,
   `var(--surface)`, `var(--grounded)`, `var(--unsourced)`, `var(--border)`,
   `var(--radius-card)`, `var(--font-display)`, etc. Tokens are theme-aware —
   they resolve for both light and `[data-theme="dark"]`; never hard-code a hex,
   ms, or px colour. Both WCAG-AA contrast pairings are guaranteed by the tokens.

### The product's own vocabulary (use it — it's the whole point)

- **Provenance is visible everywhere.** `TierBadge` marks a paper's source:
  Tier A (●, hand-curated seed), Tier B (◌, harvested), study (★, in this
  study). `GroundingChip` cites a paper inline; `UnsourcedLabel` honestly marks
  a move with no citation (dashed amber — "needs your judgment", never shameful).
- **The design conversation** is the core surface: `ConversationView` (full
  two-panel: thread + `DraftRail`), `StreamingTurn` (one turn), `MoveCard` (a
  proposed design move the researcher accepts `a` / rejects `r` — grounded,
  unsourced, caution, or accepted states), `RecommendationCard` (a matched
  paper), `SlotMeter` + `DraftRail` (the protocol compiling live from accepted
  moves), `FeedbackAffordance` (flag a turn as platform feedback).
- **Evolution**: `AmendmentBanner` (a consent surface — plainly states the
  study's revision; when a consent-relevant amendment awaits ethics re-approval
  it says "new sessions paused"), `AmendmentHistory`, `VersionChip`.
- **Voice**: first person for platform actions; no exclamation marks near
  numbers; statistics never animate. Content is study-domain (participants
  `P-01`, conditions `AI-assisted`/`Control`, real corpus papers) — never
  placeholder text.

### One idiomatic example

```jsx
import { Card, CardHeader, CardTitle, CardContent, Badge, Button } from "platform";

function StudyCard() {
  return (
    <Card style={{ maxWidth: 384 }}>
      <CardHeader>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <CardTitle>Comprehension debt under AI assistance</CardTitle>
          <Badge variant="grounded">design</Badge>
        </div>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-text-muted">
          Between-subjects, AI-assisted vs. Control, 24 sessions.
        </p>
        <div style={{ marginTop: 12 }}>
          <Button variant="subtle">Open conversation</Button>
        </div>
      </CardContent>
    </Card>
  );
}
```

Use component utility classes on the components; for your own layout glue, prefer
inline `style={{ display: "flex", gap: 12 }}` or the token utilities above. The
real stylesheets are the source of truth — read `styles.css` and its imports,
and each component's `.prompt.md`, before styling.
