# NFR-12: Experience quality (detailed specification)

**SRS row:** NFR-12. **Binds:** every platform surface; realized
first by phase 14's `platform/` app. **Decisions:** D34 (React + Tailwind +
shadcn/ui), D35 (Claude-driven design workflow).

## 1. The bar

Owner direction: "beautiful, modern, fluid, one of its kind." Made
testable, that means the platform surface is held to a *product* bar, not an
academic-tool bar. Beauty is not decoration here; it is credibility:
S7 judges whether the platform encodes real methodological knowledge
partly by whether it looks like someone who knew what they were doing
built it.

## 2. Design system

1. **Tokens first.** One token set (color, type scale, space, radius,
   motion durations/easings) defined once, consumed by both the shadcn
   layer and all charts. The dataviz palette already validated for the
   the design system is the chart-color source of truth: the two surfaces
   must read as one system (charts embedded in chat turns included).
2. **shadcn/ui as vendored source** (D34): components are copied in,
   owned, and restyled through tokens: never treated as an external
   look to inherit. Radix primitives underneath give focus management
   and ARIA for free; we never rebuild a dialog by hand.
3. **Light + dark from birth**, system-following with manual override
   (the theming decision carries over), pre-paint stamp, no flash.
4. **Type:** fluid scale (`clamp()`), one display face + one text face
   max, tabular numerals in all data contexts.

## 3. Motion & fluidity

1. Motion communicates state, never decorates: streaming turns settle,
   accepted design-move cards fold into the draft, validation failures
   shake *once*. Durations from the token set (fast 120–150 ms,
   standard 200–250 ms, entrances ≤ 300 ms); springs over linear eases
   for spatial moves.
2. `prefers-reduced-motion` honored everywhere (the discipline carries).
3. Perceived performance is a requirement: skeletons (not spinners) for
   structured content, optimistic UI for member/role edits, streaming
   for every LLM response (first token < 1 s or a progress affordance
   appears; the FR-LIT-6 "never appear frozen" rule made general).
4. Interaction budget: route transitions < 200 ms to first paint on the
   demo dataset; input latency in the conversation composer never
   blocks on network.

## 4. Chat & review surfaces (the signature interaction)

1. The conversation renders **decisions, not walls of text**: platform
   turns chunk into design-move cards with accept/reject affordances;
   long rationale collapses behind a disclosure
   (`im-not-reading-all-of-that`: engagement drops when agents dump
   prose; the UI must make skimming safe).
2. Grounding chips are first-class visual citizens (the knowledge
   layer's citation chips restyled, one component both surfaces).
3. The protocol diff view is readable by a non-programmer: YAML hunks
   annotated with plain-language summaries (NFR-11 inside the product).
4. Empty states teach: every empty view states what will appear and the
   one action that gets it there (the onboarding philosophy,
   FR-DASH-9, applied per-surface).

## 5. Accessibility (non-negotiable)

WCAG 2.2 AA: full keyboard operability (including accept/reject on
design moves and the diff review), visible focus, 4.5:1 text contrast
in both themes (the dataviz validator already checks chart colors),
labels/roles via the Radix layer, error messages tied to inputs. Axe
clean in CI on the core flows.

## 6. Fit criteria

- F1: token audit: zero raw hex/px literals in components (lint rule);
  charts and UI share the palette source file.
- F2: both themes + reduced-motion verified on every phase 14..18
  acceptance walkthrough (screenshot pairs archived).
- F3: axe CI job green on hero, designer, conversation, diff, board.
- F4: streaming-response demo shows first visible token or progress
  affordance under 1 s on the demo deployment.
- F5: keyboard-only session completes the FR-CONV F1.1 walkthrough.
- F6: the S7 hallway test (FR-PLAT-4 fit): hero → rendered report in
  ≤ 3 interactions; no interaction dead-ends without a next step.
