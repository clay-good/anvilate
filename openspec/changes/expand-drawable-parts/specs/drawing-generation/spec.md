# Drawing Generation Specification (delta)

## ADDED Requirements

### Requirement: Views come from the solid, not from the pattern

Rendered views (iso, front, top, right) SHALL be produced by projecting the built solid's
own edges with hidden-line removal, so that any valid solid draws without code specific to
its pattern. Visible edges SHALL be solid lines and hidden edges dashed. The same
projection SHALL produce the SVG and the PNG, the output SHALL be deterministic for a
given solid, view and size, and a solid the projector cannot draw SHALL be refused with
the reason rather than drawn approximately.

#### Scenario: A new pattern draws with no drawing code

- **WHEN** a pattern is added to the library with no rendering code of its own
- **THEN** all four views render, with holes and steps visible and hidden edges dashed

#### Scenario: Existing drawings do not regress

- **WHEN** the four patterns drawn before this change are rendered by the projector
- **THEN** each view shows the same edges as before, and the comparison is held by a test

### Requirement: A view can carry the part's key dimensions

A rendered view SHALL optionally carry dimension callouts for the pattern's key dimensions
(overall size, thickness, hole diameters and positions, bolt circle, bend angle), each
value measured from the built solid rather than copied from the spec, in the spec's unit
system. Callouts SHALL be legible at the default size, MUST NOT overlap the part outline,
and SHALL be limited to the pattern's declared key dimensions; this is a check picture,
not a manufacturing drawing, and SHALL say so on the image.

#### Scenario: The agent checks its own work

- **WHEN** an agent requests a dimensioned view of the bracket it just built
- **THEN** the image shows the overall dimensions and hole positions as built, so a
  mismatch with the request is visible in the picture

#### Scenario: A callout is a measurement

- **WHEN** the spec's stated width and the built solid's width differ
- **THEN** the callout shows the built value

### Requirement: One sheet shows a part at a glance

A caller SHALL be able to request a single image containing the four views of a part with
its name, overall dimensions, material and verdict line, sized for display in a chat. It
SHALL be produced from the same projection as the individual views.

#### Scenario: One image answers "what did you make?"

- **WHEN** an agent asks for the overview image of a built part
- **THEN** it receives one PNG with the four views, the part's name, its overall size and
  whether it passed
