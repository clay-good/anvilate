# Change: Presentation craft — make it look like an instrument, not a dashboard

## Why

`workbench-ui` specifies the three panes and what they do. `interaction-quality`
specifies that nothing waits silently and every refusal is actionable. Neither says
anything about how the thing looks, and the difference between a tool engineers keep open
all day and one they close after a week is almost entirely there.

The target is narrow and worth naming precisely. Engineers trust instruments, not
dashboards. A micrometer, a good oscilloscope, a well-set drawing sheet: these are
pleasing because every mark earns its place, the numbers are set so they can be compared
at a glance, nothing moves that did not change, and the object does not try to be liked.
That is the aesthetic — restraint that reads as competence — and it is achievable with
rules rather than taste.

Most of what makes engineering output feel trustworthy is typographic and mechanical:
decimals aligned in a column, figures that do not change width as they update, a layout
that does not jump while results stream in, a report that prints as a document rather than
a screenshot of one. These are cheap to specify, nearly impossible to retrofit once four
surfaces have each grown their own habits, and they are the entire difference between
"this feels solid" and "this feels like a web app."

The inverse guardrail matters as much: a screening tool that congratulates you for passing
a check is a toy. Delight here comes from speed, precision, and craft — never from
ornament or personality.

## What Changes

- New capability spec `presentation-craft`: numbers set as engineering numbers with
  decimal alignment and fixed-width figures; layout that does not move while it fills; a
  small enumerated visual vocabulary where chrome that encodes nothing must justify itself;
  one reserved accent colour; motion only where it shows causality; light and dark derived
  from one token set; designed empty, waiting, and failed states.
- **A stated voice**: no jokes in errors, no congratulation on a pass, no
  anthropomorphism, no easter eggs. The tool is an instrument and reads as one.
- **The report prints as a document**: derivations are not split across pages, tables
  repeat headers, nothing requires colour, and identical input renders a byte-identical
  PDF.
- **Craft is measured**: visual regression over a reference corpus, with contrast,
  numeric alignment, and layout stability checked in CI — so "it looks good" is a gate
  rather than an opinion that decays.

## Impact

- Affected specs: new `presentation-craft`; `workbench-ui` (ADDED); `calculation-report`
  (ADDED). Interacts with `interaction-quality` (which owns behaviour; this owns
  appearance), `units-and-quantities` (which owns precision; this owns how it is set),
  and `drawing-generation`.
- Affected code (when implemented): a token set, numeric formatting and alignment
  primitives, layout reservation, print stylesheets, and the visual-regression harness.
- Explicitly out: a brand identity, illustration, theming by the user beyond light and
  dark, and any visual element that exists to be noticed rather than read.
