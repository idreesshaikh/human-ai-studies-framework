---
name: PHOENIX
description: An observatory desk for designing human–AI studies  -  ruled ground, printed plates, one blue signal.
colors:
  signal: "#1059d8"
  signal-contrast: "#ffffff"
  signal-wash: "#e7f0fe"
  chart-paper: "#eff3f9"
  plate-white: "#ffffff"
  well: "#dde5f0"
  blue-black-ink: "#0e1b2d"
  muted-ink: "#52637c"
  hairline: "#dce4ef"
  framing-rule: "#aabbcf"
  control-edge: "#6f7f96"
  graticule: "#e4ebf4"
  drawn-mark: "#2b4666"
  unsourced-slate: "#5b6c85"
  superseded-slate: "#5e6d85"
  error-ink: "#b0231b"
typography:
  display:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "clamp(2.75rem, 5.5vw, 4rem)"
    fontWeight: 680
    lineHeight: 1
    letterSpacing: "-0.022em"
  title:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1.75rem"
    fontWeight: 640
    lineHeight: 1.12
    letterSpacing: "-0.014em"
  section:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.35
    letterSpacing: "-0.008em"
  subhead:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.35
  body-lg:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.6
  body:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.875rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.5
  control:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.8125rem"
    fontWeight: 550
    lineHeight: 1.5
    letterSpacing: "0"
  caption:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.5
  quantity:
    fontFamily: "Spline Sans Mono Variable, Spline Sans Mono, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "0.8125rem"
    fontWeight: 500
    lineHeight: 1.5
    fontFeature: "tabular-nums"
  quantity-lg:
    fontFamily: "Spline Sans Mono Variable, Spline Sans Mono, ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "1.375rem"
    fontWeight: 500
    lineHeight: 1
    fontFeature: "tabular-nums"
  legend:
    fontFamily: "Archivo Variable, Archivo, Helvetica Neue, Helvetica, Arial, sans-serif"
    fontSize: "0.6875rem"
    fontWeight: 600
    lineHeight: 1.5
    letterSpacing: "0.1em"
rounded:
  plate: "12px"
  control: "8px"
  mark: "4px"
  control-inner: "6px"
  input: "8px"
  chip: "999px"
spacing:
  tight: "8px"
  stack: "12px"
  gutter: "32px"
  section: "32px"
components:
  button-primary:
    backgroundColor: "{colors.signal}"
    textColor: "{colors.signal-contrast}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "#1050c1"
    textColor: "{colors.signal-contrast}"
  button-primary-disabled:
    backgroundColor: "{colors.well}"
    textColor: "{colors.muted-ink}"
  button-outline:
    backgroundColor: "{colors.plate-white}"
    textColor: "{colors.blue-black-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  button-ink:
    backgroundColor: "{colors.blue-black-ink}"
    textColor: "{colors.plate-white}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  button-danger:
    backgroundColor: "{colors.plate-white}"
    textColor: "{colors.error-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  tab-axis:
    backgroundColor: "transparent"
    textColor: "{colors.blue-black-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "0 12px"
  plate:
    backgroundColor: "{colors.plate-white}"
    textColor: "{colors.blue-black-ink}"
    rounded: "{rounded.plate}"
    padding: "16px"
  input-field:
    backgroundColor: "{colors.plate-white}"
    textColor: "{colors.blue-black-ink}"
    typography: "{typography.body}"
    rounded: "{rounded.input}"
    padding: "4px 12px"
    height: "36px"
  badge-grounded:
    backgroundColor: "{colors.plate-white}"
    textColor: "{colors.blue-black-ink}"
    typography: "{typography.legend}"
    rounded: "{rounded.chip}"
    padding: "2px 8px"
  badge-unsourced:
    backgroundColor: "transparent"
    textColor: "{colors.unsourced-slate}"
    typography: "{typography.legend}"
    rounded: "{rounded.chip}"
    padding: "2px 8px"
  badge-active:
    backgroundColor: "{colors.signal-wash}"
    textColor: "{colors.signal}"
    typography: "{typography.legend}"
    rounded: "{rounded.chip}"
    padding: "2px 8px"
---

# Design System: PHOENIX

## Overview

**Creative North Star: "The Observatory Desk"**

The whole product happens on one desk in an observatory. The desk itself is
ruled  -  a coordinate graticule you feel rather than read, holding still while
everything else scrolls across it. On the desk lie **plates**: printed sheets,
squared, hairline-framed, lifted a millimetre off the paper by their own
shadow. Beside them sits the **log**: dated entries, each one either confirmed
against the catalogue or written down as an unidentified object, never quietly
either. Nothing here is a card in an app; everything is a thing on a desk that
someone competent is working at.

Light and dark are two renditions of that one desk, never an inversion of each
other. Light is the atlas printed on chart paper, read in daylight: a cool
unprinted ground, plates in true white, blue-black ink. Dark is the same plate
on a **light table** at night  -  the bench goes unlit and the plates step *up*
toward the lamp, catching a lit top edge, their shadows deepening beneath them
rather than softening away. A dark plate that merely sits a few percent above
the page is the generic dark-mode prior and is wrong here.

The personality is quiet, dense and instrument-like, because the product's
aesthetic argument *is* its credibility argument: a researcher judges whether
the platform encodes real methodological knowledge partly by whether it looks
like someone who knew what they were doing built it. So the system spends
almost nothing on expression and everything on precision. One accent. Two
faces. Eleven type roles. Marks whose meaning survives a greyscale print. Body
copy stays at 14px because tables and metric shapes have to fit, and hierarchy
is bought *above* body, never below it.

**Key Characteristics:**

- One signal blue, used only for an action you can take or the axis mark that
  says where you are  -  never for the brand, never for links, never decoratively.
- A ruled ground at a 4rem pitch, masked away from the top of the viewport, felt
  and never counted.
- Plates: 12px corners, hairline frame, offset shadow, never nested inside one
  another.
- Provenance carried by **form** (framed dot, open ring, struck line, doubled
  mark) and by **printed number**, never by hue  -  and never by a size the eye
  has nothing to judge against.
- Two faces, three jobs: Archivo for everything set in letters, Spline Sans Mono
  for quantities and only quantities.
- Rounded is a commitment, not a softening: 12px plate, 8px control, fully round
  key.
- Motion decelerates and never overshoots. A research instrument that wobbles is
  one nobody trusts to hold still.

## Colors

A blue-black world with exactly one saturated colour in it: everything neutral
is mixed from the world's own hue, so a hover tint reads as light on paper
rather than as dirt on it.

### Primary

- **Signal** (`#1059d8` light / `#5ea3ff` dark): the only saturated colour in
  the app, and it means one thing  -  *this is where the work is now*. It fills a
  control that is the next action in its region, and it rules the 3px axis mark
  that says where you are. It is never the brand mark's colour, never a link's
  colour, never a chart series, never a decorative wash.
- **Signal Contrast** (`#ffffff` light / `#04080e` dark): the label on a filled
  signal control, and nothing else.
- **Signal Wash** (`#e7f0fe` light / `#1b3260` dark): the cleared field under an
  accent-marked key (an active badge), never a page background.

### Neutral

- **Chart Paper** (`#eff3f9` light / `#05090f` dark): the desk  -  the unprinted
  ground everything lies on.
- **Plate White** (`#ffffff` light / `#1a2b48` dark): what the record is printed
  on. In dark this steps *up* out of the ground (1.41:1), and the topmost plate
  further still (1.69:1).
- **Well** (`#dde5f0` light / `#0c1526` dark): a genuinely recessed region  -  a
  code block, a slider track, a refused control. Distinct from the hover step by
  construction.
- **Blue-Black Ink** (`#0e1b2d` light / `#e9eff8` dark): text, frames, the
  wordmark. The record itself.
- **Muted Ink** (`#52637c` light / `#9cafc7` dark): metadata, placeholders,
  captions, unselected siblings in a strip.
- **Hairline** (`#dce4ef`), **Framing Rule** (`#aabbcf`), **Graticule**
  (`#e4ebf4`): three weights of division  -  incidental, a titled plate's frame,
  and the coordinate grid under everything.
- **Control Edge** (`#6f7f96` light / `#7288b0` dark): the boundary of an
  *interactive* control, kept as its own token because WCAG 2.2 SC 1.4.11 binds
  it at 3:1 while a plate's frame is decoration. A later pass may lighten frames
  without silently taking the controls with them.

### Tertiary  -  the mark inks

- **Drawn Mark** (`#2b4666`): a shade off body ink, so a mark reads as something
  *struck onto* the plate rather than typed into it.
- **Unsourced Slate** (`#5b6c85`): the open ring's stroke and its label. It is
  not an error colour and must never be reused as one.
- **Superseded Slate** (`#5e6d85`): struck through, and still readable.
- **Error Ink** (`#b0231b` light / `#ff8b7f` dark): failure only. Never a second
  accent.

Charts are the one place the palette opens up: an eight-slot categorical set,
CVD-validated *as a set*, with a separate dark column that is stepped rather
than auto-flipped. Series hues are never re-picked to match the world's blue
discipline, because re-picking breaks the validation; instead every series that
must survive a greyscale print carries a mark as well as a hue.

### Named Rules

**The One Fill Rule.** A fill is an action you can take. It is always the
signal, and there is at most one primary fill per *region*  -  not per viewport. A
genuinely split surface with two panels doing two jobs (send / review) correctly
has two. Within one region, a second fill means one of the two is wrong.

**The Axis Mark Rule.** Position is never a fill. "You are here" is a 3px signal
rule on the edge the strip is ruled against, plus a cleared ground and full-ink
weight against muted siblings. A nav item, a tab and a selected row are all
positions, so all three are axis marks. Only a button is ever filled, and only
the signal ever fills it.

**The Greyscale Rule.** No state may rest on hue alone. Every provenance state
carries a form or a printed value as well as a colour, so it survives a
greyscale print and a colour-blind reader.

**The Three Jobs Rule.** One surface value may not carry three meanings. The
hover tint, the axis mark's cleared ground and a refused control are three
different jobs and take three different steps on the ramp; a refused control
sits in the *well*, recessed, never in the hover tint.

## Typography

**Display / Body Font:** Archivo Variable (with Helvetica Neue, Helvetica,
Arial, sans-serif)  -  one grotesk covers every role set in letters, because an
atlas is labelled in a grotesk: precise at 11px, with presence at display size.
**Quantity Font:** Spline Sans Mono Variable (with ui-monospace, SF Mono, Menlo,
Consolas)  -  quantities and only quantities.

**Character:** Sober, tightly spaced, engineered. Hierarchy comes from size and
weight, never from a compressed width axis or tracked caps; the width axis is
pinned at 100 everywhere. Display closes up slightly (-0.022em), running type
sits near zero, and a legend is tracked open (0.1em) so it reads as a label on a
field rather than as a word.

### Hierarchy

- **Display** (680, `clamp(2.75rem, 5.5vw, 4rem)`, 1.0, balanced): the headline,
  once. The only role above 28px.
- **Title** (640, 28px, 1.12, balanced): the page's name  -  exactly one per screen.
- **Section** (600, 20px, 1.35): a titled division within a page.
- **Subhead** (600, 16px, 1.35): a plate's own title.
- **Body Large** (400, 16px, 1.6): sustained reading  -  log entries, findings prose.
- **Body** (400, 14px, 1.5): the app's default voice.
- **Label** (500, 13px, 1.5): a form or control label.
- **Control** (550, 13px, 1.5, sentence case): a button or a tab.
- **Caption** (400, 12px, 1.5): metadata  -  counts, timestamps, provenance.
- **Quantity** (mono, 500, 13px, tabular): a measured value. **Quantity Large**
  (mono, 500, 22px, 1.0) for a tally or total called out on its own.
- **Legend** (600, 11px, uppercase, 0.1em): a key on the plate, a column head.

### Named Rules

**The Mono-Is-Not-A-Costume Rule.** The machine face carries measured
quantities. It never sets prose, button labels, headings, or anything that is
merely "technical-feeling". A magnitude, an effect size and a per-cell n must
align down a column; a sentence must not.

**The Sentence-Case Rule.** Controls read in the product's own voice. Tracked
caps on buttons made every control shout its label in a tool whose job is to be
quiet enough to think in. Legend is the only uppercase role, and it is a label
on a field  -  never an eyebrow set above a heading.

**The No-Fractions Rule.** `font-feature-settings` on quantities is `normal`,
deliberately. The `frac` feature makes "1/3" pretty and everything else wrong:
it stacked a slot meter's "0/8" into a fraction, and did the same to DOIs, dates
and version numbers. This product writes ratios and identifiers far more often
than it writes fractions.

**The Tabular Rule.** Anything showing a number gets tabular figures. A
measurement that changes width between states is not comparable down a column.

## Layout

Four content measures, chosen by what the page is *for*, never by reaching for
a bare utility width: **narrow** (26rem  -  a focused form), **reading** (44rem  -
prose), **work** (60rem  -  the default working measure), **wide** (72rem  -  a
dense dashboard), plus a **bubble** measure (46ch) for conversation turns.

The spacing rhythm is four steps: **tight** (0.5rem  -  the tightest cluster),
**stack** (0.75rem  -  within a section), **section** (2rem  -  between titled
sections), **gutter** (2rem  -  a Surface's own inset). One `Surface` owns one
measure, one gutter, one rhythm and one scroller; this is asserted by
`verify-layout.mjs` and `verify-shell.mjs`, not left to convention.

The workspace's split geometry is a measured column plus a rail that grows with
the window between a floor (22rem) and a cap (30rem) at 32vw, collapsing to a
single column below 64rem. The rail's track uses `minmax(0, 1fr)` and never a
bare `1fr`  -  a grid track's implicit min-content floor is what pushes a rail off
the side of the window.

The desk's graticule is a fixed hairline grid at a 4rem pitch, at low alpha,
radially masked away from the top of the viewport where the eye first lands on
content. Plates scroll across a field that holds still.

### Named Rules

**The Felt-Not-Read Rule.** A ruling you can count is graph paper. The pitch is
wide (4rem, never 1.5rem), the alpha low, and the mask aggressive  -  on a quiet
page the ground must never become the loudest thing on screen.

## Elevation & Depth

Depth is a printed sheet lying on paper: an **offset** shadow with a soft blur,
never a zero-offset halo, and never a glow. Three depths and no fourth.

### Shadow Vocabulary

- **Mark** (`0 1px 2px rgba(14,27,45,0.06)`): a mark on the plate  -  the barest
  separation, used by controls and chips.
- **Plate** (`0 1px 2px rgba(14,27,45,0.05), 0 4px 12px -4px rgba(14,27,45,0.09)`):
  a plate laid down on the desk. The default for cards, panels and dialogs.
- **Lifted** (`0 8px 20px -6px rgba(14,27,45,0.14), 0 20px 44px -18px rgba(14,27,45,0.16)`):
  a plate picked up to be moved  -  hover and drag only.

In dark, depth is the lamp *under* the plate: the shadows deepen
(`rgba(0,0,0,0.4–0.62)`) instead of fading, and a plate carries a lit top edge.

### Named Rules

**The Light-Table Rule.** Dark is a rendition, not an inversion. Plates step up
toward the lamp and are the luminous thing; the bench around them is unlit. A
dark surface that is merely a few percent lighter than the page has fallen back
to the generic prior and is wrong.

**The Explicit-Dark Rule.** There is deliberately no `prefers-color-scheme: dark`
block. The app always opens on the atlas in daylight; dark lives solely under
`[data-theme="dark"]`, applied by the toggle and a pre-paint stamp in
`index.html` so there is no flash.

## Shapes

Rounded is a commitment, not a softening  -  plates in an atlas are bound with
rounded corners and its legend keys are struck as circles. Five steps: a **plate**
at 12px (cards, panels, dialogs), a **control** at 8px (buttons, tabs, inputs),
a **control-inner** at 6px (a segment inside a segmented group  -  concentric radii
step down by the inset, or the inner corner looks squarer than the outer one), a
**mark frame** at 4px (the grounding mark's reference box  -  a plate in
miniature), and a **key** fully round (999px  -  chips, pills, dots).

The plate is *ruled*, not boxed. Three rule weights carry every division:
**hairline** (1px  -  the graticule and incidental division), **rule** (1.5px  -  a
frame, and the dashed open ring), and **heavy** (3px  -  the axis mark, and only
the axis mark).

Provenance is drawn in four forms, and every one of them is printed alongside
its value:

- **Framed dot**  -  grounding strength. A dot in the mark's ink, sized
  continuously by the score, centred in a constant 18px frame (1px
  `control-edge`, 4px corners). The frame is the reference: every mark is read
  against the same box, so the judgement is relative rather than absolute.
- **Open ring**  -  unsourced: seen and logged, not identified. A 9px dashed
  circle in unsourced slate, never filled, never the same shape as anything
  grounded.
- **Struck line**  -  superseded: replaced, left legible, never erased.
- **Doubled mark**  -  conflict: two marks claiming one coordinate. Nothing else
  in the system doubles, so a doubled mark always means exactly one thing.

### Named Rules

**The Framed-Magnitude Rule.** How strongly a claim is grounded is a dot sized
by the score inside a constant frame, with the score printed beside it in the
machine face and its plain words beside that where there is room
(`◉ 0.71  well grounded`). Three things are load-bearing and none may be
dropped. The **frame** must be constant, because a bare dot asks the eye to
judge absolute size against nothing  -  the failure that retired the first
notation here. The diameter must be **continuous**, because quantising a
continuous score into steps makes 0.51 and 0.74 render alike  -  the failure that
retired the second. And the **number** must be printed, because nobody should
have to estimate a value from a drawing. Grounding strength is never a hatch
density, a bar, a row of pips, or a hue.

**The Never-Erased Rule.** Nothing in this product is erased. A replaced line is
struck and stays readable, at the superseded ink, both before and after.

## Components

### Buttons

- **Shape:** gently rounded (8px), hairline-framed, 44px tall by default  -  the
  comfortable touch target (WCAG 2.5.5). `sm` (36px) is the one compact escape
  hatch for dense inline rows.
- **Primary:** the signal fill with white label; the next action in its region.
  Hover deepens the fill toward ink (`color-mix(in srgb, signal 88%, ink)`).
- **Outline / Subtle / Ghost:** unfilled  -  a control-edge frame on plate white, a
  cleared step, or a bare mark. The eye finds the action without reading a word.
- **Ink:** ink-filled with paper label, reserved for a commit that must *not*
  read as the helpful next step.
- **Danger:** unfilled at rest, framed and lettered in error ink; it fills
  critical only under the pointer, after confirmation has already been typed.
- **Focus:** a 2px signal outline at 2px offset, from the global rule. The
  element keeps its own radius  -  the focus rule sets no radius of its own.

### Tabs & Navigation

An axis mark, never a fill: a 3px signal rule on the spine (or under the label
on a horizontal strip, inset 18%), a transparent ground, and the label at full
ink at weight 600 while its siblings stay muted. Segmented controls are a
`radiogroup` with a roving tabindex; arrow keys move and select.

### Plates / Cards

- **Corner:** 12px. **Background:** plate white. **Border:** 1px hairline.
  **Shadow:** the *plate* shadow. **Padding:** 16px.
- `lift` adds the hover/press response for a plate that can be picked up.
- Never nested: a plate is a real object, so a division *within* a plate is a
  ruled band, not a second plate.

### Inputs / Fields

A ruled cell in the record: 36px tall, control-edge frame, plate ground, 8px
radius, set in the reading voice  -  what a researcher types is language. Passing
`quantity` switches the field to the machine face and right-aligns it so values
line up down a column; a `unit` prints in its own cell against the right edge in
the legend voice. Hover darkens the border; focus is the global ring *only*  -
turning the border accent as well drew a second blue ring two pixels inside the
first and read as a rendering fault.

### Grounding Mark

The dot and its score, together, wherever a citation's confidence appears: an
18px frame with a 1px `control-edge` border and 4px corners, holding a dot in
the mark ink whose diameter runs 5px→12px across the 0–1 score. The top of the
range stops short of the frame deliberately: a dot that touches its own frame
reads as a ring with a fill rather than as a mark on a field, and that
clearance is what keeps the frame legible *as* the reference at exactly the
magnitudes that matter most. The frame's
border is `control-edge` and not the plate's framing rule, because the box is
what the value is read against  -  a graphical object required to understand the
content, which SC 1.4.11 binds at 3:1 (`border-strong` sits at 2:1 on a plate
and would have failed silently). A source with no score reads `unrated`; an
unsourced claim takes the open ring instead. The whole notation is one ink and
a size, so it survives greyscale and colour-blind reading untouched.

### Chips / Badges

A key printed in the margin: fully round, hairline-ruled, set in the legend
voice. `grounded` is a solid ruled key; `unsourced` is a dashed open outline in
unsourced slate; `active` is the one accent-washed key, for the single thing in
play. `default` and `outline` carry no provenance claim at all.

### Refusal (all controls)

A disabled control **drops out of its variant** rather than fading inside it: to
the well, hairline-framed, with muted ink and no shadow. A washed-out signal
fill still reads as "the blue button", which makes the one thing that cannot be
pressed look like the one thing to press. `disabled` is mirrored to
`aria-disabled` so refusal is audible as well as visible.

### The Blink Comparator (signature)

The product's one watchable move. Two versions of the protocol alternate in
identical coordinates on a 900ms beat, so anything unchanged sits perfectly
still and only what actually changed appears to move  -  the instrument that found
Pluto, applied to a protocol diff. At rest it is not an animation but the
readable record: added lines at full ink, replaced lines struck and still
legible. Under reduced motion it stops alternating on its own; the manual blink
still works, because that one is a tool, not an effect.

### Motion (applies to every component)

Six durations: **instant** 90ms (press), **fast** 140ms (hover, focus, tint),
**standard** 220ms (control state, panel reveal, axis travel), **entrance**
320ms (a mark arriving), **settle** 460ms (a plate landing), plus **blink**
900ms and a 72s field drift. Every ease decelerates and none overshoot.

### Named Rules

**The No-Overshoot Rule.** A plate reads as having mass because of how far it
travels and how long it takes to stop, not because it bounces past its resting
place. An overshoot on a working surface is a wobble, and a research instrument
that wobbles is one nobody trusts to hold still.

**The Reduced-Motion Rule.** Every surface stays fully usable with animation
off: plates arrive already landed, the tracked field holds still, the comparator
stops alternating. Skeletons, never spinners; a streaming affordance within 1s.

## Do's and Don'ts

### Do:

- **Do** spend the signal on exactly two things: a control that is the next
  action in its region, and the axis mark that says where you are.
- **Do** give every provenance state a form or a printed number as well as a
  colour, and check it in greyscale.
- **Do** draw grounding strength as a continuously sized dot in its constant
  frame, with the tabular score printed beside it (`◉ 0.71  well grounded`).
- **Do** pick a named measure (narrow / reading / work / wide) for a page based
  on what the page is for, and let `Surface` own the gutter, rhythm and scroller.
- **Do** name a type role (`type-body`, `type-quantity`, `type-legend`) instead
  of a size. Tokens are the sole source of raw values *and* of type sizes;
  `lint-no-raw-literals.mjs` enforces both.
- **Do** send a refused control to the well with muted ink, and mirror
  `disabled` to `aria-disabled`.
- **Do** step concentric radii down by their inset (12px plate → 8px control →
  6px inner segment).
- **Do** measure contrast rather than trusting the word "muted"  -
  `check-contrast.mjs` runs in `npm run verify`.

### Don't:

- **Don't** ship two competing emphasis fills. A near-black "committed" fill and
  a coloured "next action" fill both meaning primary is the exact failure this
  system was built to end: when everything is primary, nothing is.
- **Don't** spend the one accent on the brand mark, the primary button, the
  active tab and every link at once. That is four different meanings wearing one
  colour, and it is why the previous world was discarded.
- **Don't** encode provenance as hatch density, or as any notation that needs a
  key consulted before it can be read. Six densities shipped once and nobody
  could read them.
- **Don't** draw a magnitude without its frame, or quantise a continuous score
  into steps. Those are the two failures the current notation exists to answer,
  and both shipped here before.
- **Don't** reuse the unsourced ink as an error colour. Unsourced is *your call
  to make*, not a fault; conflating them told researchers they had done
  something wrong by being honest.
- **Don't** let one surface value carry three jobs. The hover tint, the axis
  mark's cleared ground and a refused control are three different steps.
- **Don't** set controls in tracked caps, or set prose, labels or headings in the
  machine face.
- **Don't** let a focus rule mutate a focused element's radius  -  it rounded the
  command palette's full-width input by 8px the moment it took focus.
- **Don't** nest a plate inside a plate, or a card inside a card inside a card. A
  division within a plate is a ruled band.
- **Don't** add a `prefers-color-scheme: dark` block, and don't build dark by
  inverting light.
- **Don't** rename a `data-agent` attribute for a design reason; they are a
  machine-readable contract checked by `check-agent-annotations.mjs`.
