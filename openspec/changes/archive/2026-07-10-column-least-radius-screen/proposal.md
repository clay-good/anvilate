# Change: Column screens buckle about the least radius of gyration

## Why

A column buckles about its weakest axis, but `screen_column_member` and
`screen_beam_column` compute slenderness from `CrossSection.radius_of_gyration`
— the r of whatever axis the caller happened to declare as the bending axis.
Passing a strong-axis section silently overstates buckling capacity: an
unconservative screen, which is exactly what the no-silent-green ethos exists
to prevent. Today the pack only *documents* that the caller should pass the
weak-axis value ("``section``'s ``second_moment`` should be the *least*
(weak-axis) value"); nothing checks it.

`CrossSection` already carries what the fix needs: every builder fills
`second_moment_transverse`, and `least_radius_of_gyration` returns the min-I
radius, falling back to the bending-axis value when the transverse moment is
absent (a hand-built section).

## What Changes

- `screen_column_member` computes slenderness from
  `section.least_radius_of_gyration` instead of `section.radius_of_gyration`.
- `screen_beam_column` does the same for its axial-capacity term (its flexural
  term keeps the declared bending axis — bending is about the declared axis;
  buckling is about the weakest).
- Sections without a transverse second moment keep today's behavior exactly
  (the fallback is the bending-axis r), so hand-built `CrossSection`s are
  unaffected.
- Screens of standard-builder sections whose weak axis was already passed as
  the bending axis are numerically unchanged; strong-axis declarations now
  screen (correctly) lower.

## Impact

- Affected specs: `discipline-packs` (new requirement under the structural
  pack: buckling screens use the least available radius of gyration).
- Affected code: `src/anvilate/packs/structural.py`
  (`screen_column_member`, `screen_beam_column`), their tests, and the
  `ColumnMember`/`BeamColumnMember` docstrings (the "pass the least I"
  caveat becomes "the screen takes the least axis itself").
- Affected examples: `flat_bar_strut_weak_axis.py` teaches the weak-axis trap
  by screening both axes explicitly — it keeps working, but its lesson should
  note the pack now guards this automatically; `beam_column_check.py` and
  `mezzanine_structure.py` use symmetric or already-weak-axis sections and are
  numerically unchanged.
- **Breaking:** a screen that previously (mis)declared a strong axis will now
  report a lower — correct — buckling safety factor and may flip PASS → FAIL.
  That flip is the point of the change.
