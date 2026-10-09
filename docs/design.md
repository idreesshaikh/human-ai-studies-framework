# Interface design

Use the existing interface and tokens as the starting point. The researcher
should be able to see what changed, why it matters, and what to do next.

## Layout and typography

The app uses Archivo for text and Spline Sans Mono for measurements. Type roles
are defined in `platform/src/styles/index.css`; colors, spacing, radii, and
motion are in `platform/src/styles/tokens.css`. Use those values rather than
adding component-specific colors or sizes.

`Surface` provides the scrollable body and a named content width:
`narrow` for forms, `reading` for prose, `work` for normal tasks, and `wide`
for dense views. The study workspace places the protocol beside the main view
from 768px upward. Its labelled, 48px collapsed rail keeps the draft discoverable
without taking space from the conversation. On smaller screens, the header's
Review draft action opens the review dialog regardless of the saved rail state.

Use one heading per view, clear labels, and a primary action for the next step.
Group comparable items in lists or tables. Keep explanatory copy short and
put detailed assumptions beside the calculation or measure they explain.

The Setup workspace follows the conversation-first approach of
[Open WebUI](https://docs.openwebui.com/features/chat-conversations/): chat is
the main task, with research tools available when needed. The header, messages,
and compact, growing composer share one reading column. Keep a single visible
Review draft action; applying a protocol belongs in the review dialog. Do not
hide pending decisions, source quality, or approval requirements to reduce text.

Plan presents a short summary and participant assignment first. Allocation,
capture details, validation issues, and sample-size assumptions live in labelled
disclosures. Preserve the selected participant when switching tabs and refresh
the plan on return. Initial loading must not briefly show an empty plan or
sample-size panel before the actual plan arrives.

## Color and meaning

The blue accent identifies actions and selection. Light and dark themes use
separate token values. Status, source quality, and errors must remain readable
without relying on color alone.

A grounding score appears as a number and a sized mark inside a fixed frame.
An absent score reads as unrated; an unsourced proposal is labelled unsourced.
Neither should look like a measured result or a validation failure.

## Interaction

Preserve keyboard operation, visible focus, and labelled fields. Errors should
name the failed action and allow recovery. Keep form input when a request fails.
Never report a successful save without a server response.

The protocol diff keeps additions and replacements legible. Its optional blink
comparison must remain manually usable with reduced motion enabled. Consent
must be readable before recording begins.

Run `npm run check` and `npm run a11y` in `platform/`. Check changed views
at desktop and mobile widths, including loading, empty, and error states.

## Form controls

One spec (`.control`, tokens.css/index.css); checked by frontend lint and browser accessibility verification.

- Control: 40px, 1px `--control-edge` border, input radius, surface fill, no
  shadow, on Input, Textarea, Select and the input group. Disabled is the well;
  read-only is the well with a normal edge; invalid is a critical edge plus icon
  and text, never colour alone.
- Focus: one 2px accent ring over the border, identical everywhere (a group
  draws it on its wrapper); forced-colors maps it to Highlight.
- Numbers: native spinners hidden; `stepper` only where +/- helps; arrow keys
  always work. A unit is muted text inside the field edge (`unit="min"`).
- Checkbox: always `ui/checkbox.tsx`, never raw `type="checkbox"`: empty box
  off, accent fill and check on, dash for indeterminate; the row is the 24px hit area.
- Field (`ui/field.tsx`): label at control size, 6px gap, hint or error below,
  20px between fields; wires id, aria-describedby, aria-invalid. Placeholders
  are short examples; guidance goes in the hint. `autoGrow` textareas have no grip.
- Dialog: `DialogHeader`, one scrolling `DialogBody`, sticky `DialogFooter`
  (secondary left of primary), capped in dvh, shade only when scrollable, full
  sheet on phones. Footer submit uses `form="id"`. Validation: role=alert
  summary of links that focus fields, plus inline errors.
- Beside a field in a row, use `Button size="field"` so heights match.
