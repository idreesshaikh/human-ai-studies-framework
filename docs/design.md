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
on wide screens and stacks them on smaller screens.

Use one heading per view, clear labels, and a primary action for the next step.
Group comparable items in lists or tables. Keep explanatory copy short and
put detailed assumptions beside the calculation or measure they explain.

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
