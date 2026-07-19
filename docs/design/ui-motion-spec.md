# UI & motion specification — "quirky-precise"

Realizes NFR-12 (`requirements/specs/nfr-12-experience.md` is the
requirement; this is the design). Traces: FR-CONV (conversation
surfaces), FR-LIT-9/10 (matching, constellation), FR-TPL (designer),
D34 (React + shadcn/ui vendored), D35 (designed with Claude, in-repo).

## 0. Design language — the personality

**"A very smart lab partner with excellent handwriting."** The platform
is playful in *motion* and *voice*, never in *data*. Two registers,
strictly separated:

- **Warm register** (conversation, empty states, celebrations): rounded
  cards, springy motion, first-person platform voice ("I found three
  RCTs that measured this — want them?").
- **Precise register** (protocol diffs, statistics, threats records):
  tabular numerals, hairline rules, zero animation beyond focus/settle,
  third-person factual voice. Statistics never bounce. Ever.

The quirk budget: **one quirky element per screen, maximum.** Quirk is
seasoning, not sauce — a wink in the empty state *or* a springy card
arrival, never both competing.

## 1. Tokens (single source, shared with all charts)

```
--motion-fast:     120ms   /* hover, focus rings, chip highlights   */
--motion-standard: 200ms   /* card state changes, panel reveals     */
--motion-entrance: 280ms   /* new elements arriving                 */
--motion-settle:   420ms   /* design-move fold-into-draft (the one
                              deliberately slow, watchable move)    */
--ease-out:    cubic-bezier(0.16, 1, 0.3, 1)     /* arrivals  */
--ease-in-out: cubic-bezier(0.65, 0, 0.35, 1)    /* moves     */
--spring:      spring(1, 220, 24)                 /* playful — warm register only */
--radius-card: 14px;  --radius-chip: 999px;  --radius-input: 10px
type: one display face (600/700) + one text face (400/500);
      tabular-nums on every number; fluid clamp() scale
color: the validated dataviz palette is the chart source of truth;
       UI neutrals + one accent per theme; 4.5:1 minimum everywhere
```

Lint rule (NFR-12 F1): no raw hex/ms/px literals in components — tokens
or nothing.

## 2. Component inventory (shadcn base → platform components)

| Component | Built from | Signature detail |
| --- | --- | --- |
| `MoveCard` | Card + Badge + Button | the accept/reject pair is keyboard-first (`a`/`r` when focused); accepted → 420ms fold toward the draft rail with a paper-fold crease shadow; rejected → 200ms exhale (scale 0.97, fade) — dismissal feels light, never punitive |
| `GroundingChip` | Badge + HoverCard | tier badge (A=filled dot, B=ring, study=star); hover reveals title/year/venue + "why this source"; click pulses the paper in the constellation (§4) |
| `UnsourcedLabel` | Badge (dashed border) | dashed amber ring + "needs your judgment" — honest, not shameful; never red (unsourced ≠ wrong) |
| `ProtocolDiff` | custom + shadcn ScrollArea | YAML hunks, precise register; each hunk's gutter dot color-keyed to its move card; plain-language hunk summary above each (NFR-11 in-product) |
| `RecommendationCard` | Card | arrives with 280ms ease-out rise + 2° tilt settling to 0° (the "dealt card" — the one quirk of the conversation screen); match reason is one sentence, always visible, never truncated |
| `SlotMeter` | custom radial | protocol completeness as a constellation-style ring of dots (one per mandatory section); dots light as slots fill; the last dot lighting triggers the §5 completion moment |
| `StreamingTurn` | custom | tokens fade in at 60ms stagger blocks; moves materialize *after* prose settles (never mid-scroll layout shift — reserve space with skeleton cards) |
| `TierBadge` | Badge | A/B/study provenance, always rendered wherever a paper appears — provenance is UI (data-model §4) |
| `AmendmentBanner` | Alert | consent-relevant amendments get the precise register + a lock glyph; "new sessions paused until re-approval" in plain language |
| `EmptyState` | custom | every empty view: one wry line + the single next action; e.g. constellation empty: "Space, but no stars yet — describe your idea and I'll find its neighbors." |

## 3. Streaming choreography (FR-CONV-1, the feel of "it talks back")

1. Composer is **never blocked**: typing, editing, and queuing work
   during any stream; send enqueues.
2. First visible token < 1s or a progress affordance appears — a
   thinking indicator that is a slowly orbiting dot pair (not a spinner;
   spinners mean "frozen", orbits mean "working").
3. Prose streams into a fixed-width column; **layout never shifts**
   during a stream (skeleton space reserved for known-incoming moves).
4. Moves materialize post-prose, 80ms stagger, left-to-right; grounding
   chips pop in last (120ms), because provenance arriving *after* the
   claim visually reads as "checked, then stamped".
5. Stream failure: turn dims to 60%, retry affordance inline, composer
   content untouched. Input loss is a P0 bug, not a UX note.

## 4. The living literature constellation (FR-LIT-10)

The signature surface. A force-directed citation graph that behaves
like a calm night sky, not a physics demo.

- **Idle:** stars (papers) drift ≤ 2px on a 6s sine loop — alive, not
  busy. Tier A stars are brighter; Tier B dimmer with a ring; study-set
  papers gold-tinted. Edges are hairlines at 12% opacity.
- **Conversation reactivity:** when a turn cites a paper, its star
  pulses twice (420ms each) and its chip and star share a brief drawn
  connecting line that fades over 800ms — the "the platform is reading
  with you" moment.
- **Arrival:** a paper added to the list streaks in from its
  recommending card's screen position along a bezier, decelerating into
  its cluster slot (600ms, ease-out) — the one deliberately theatrical
  animation in the product, because *growing your corpus should feel
  like something*.
- **Clusters:** thematic grouping (template designType + FTS topic
  terms) as gravity wells with soft label halos; lasso-select sets the
  RAG scope (§sequences 5); scoped stars brighten, others dim to 30% —
  scope is always visually unambiguous.
- **Gaps:** cluster regions with RQ-relevant terms but no study-set
  papers render a faint dashed halo — "nothing here yet" — clicking it
  drafts a gap note into the conversation (FR-LIT-9's loop-back).
- **Reduced motion:** drift off, pulses become outline highlights,
  streaks become instant placement with a highlight — the view loses
  zero function (NFR-12 F2).
- **Performance:** canvas/WebGL rendering ≥ 500 nodes at 60fps; layout
  computed off-main-thread (worker); deterministic seed per study so
  the sky is stable across visits (a constellation you *recognize*).

## 5. Micro-moments (the small details, exhaustively)

| Moment | Behavior |
| --- | --- |
| Protocol freeze | the draft rail's dots connect into a single line, then a 1px gold rule sweeps the diff — 700ms, once; precise register everywhere after |
| Statistics render | no animation; numbers appear set, like print. Effect sizes get a hairline underline on hover with the plain-language read ("large effect, but n=6") |
| Gate clears | the lifecycle column exhales: 4px settle of the whole board (200ms) — relief, not fireworks |
| Validation bounce | the offending move card shakes **once** (3px, 150ms) and the platform turn explaining it auto-scrolls into view |
| Invite accepted | new member's avatar drops into the project header with a 280ms bounce (spring) — warm register; their role chip appears static (roles are precise) |
| Mining job paused | the progress bar's leading edge breathes (rate-limit pause is calm, not alarming); tooltip: "GitHub asked us to slow down — resuming in 40s" |
| Dark/light toggle | 200ms crossfade, charts re-palette in the same frame (token system, no flash) |
| Keyboard traversal | every surface: visible focus ring (2px, offset 2px); conversation: `j/k` moves, `a/r` decides, `c` compiles, `?` overlays the map |
| Error copy | always: what happened → what we kept safe → the one next action. Never a bare code |
| Celebration ceiling | paper draft generated = confetti? **No.** A single gold rule under the title and "your methods section is written." The data is the celebration |

## 6. Voice & microcopy rules

First person for actions the platform took ("I matched these against
your RQ"), second person for the researcher's things ("your paper set"),
passive voice banned except in the precise register. No exclamation
marks within two lines of a number. Jargon budget: requirement IDs never
appear (NFR-11); statistical terms always carry a hover explainer
sourced from the SRS/glossary endpoints (FR-DASH-9 mechanism).

## 7. What is deliberately NOT animated

Protocol YAML, statistics, consent/ethics surfaces, the validity-threats
record, and anything on the participant's screen (NFR-1 — the
extension's surfaces stay minimal). Restraint *is* the design system:
the warm register earns trust for the moments the precise register
spends it.
