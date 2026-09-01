# Change: The card answers every declaration the document makes

## Why

"No silent green" was written about checks that *tried and could not finish* — a mesh
failure, a missing property, a solver error. An audit of `screen_spec` against every field of
`DesignSpec` found the other half, and it had six instances:

- A spec declaring `max_mass`, `envelope` or `max_cost` screened to **PASS** with the bound
  never computed and never mentioned. Nothing anywhere read those three fields.
- A spec declaring `element_type` and demanding only T2 screened to **PASS** on a tolerance
  band, with nothing saying the element had not been looked at.
- A spec declaring a ±0.0001 mm band — achievable on no process this library knows — and
  demanding only T1 screened to **PASS**.
- A spec declaring `acceptance.max_displacement` screened to PASS; the pack screens take
  their deflection limit from the element, so the one on the acceptance criteria reached
  nothing.
- A spec writing its general tolerance class the way a drawing writes it, `ISO2768-m`,
  screened to PASS and then raised out of `anvilate export`, because the class was resolved
  only when the evidence bundle was assembled.
- A spec declaring `combination_basis` screened as though it had said nothing, while
  `DesignSpec.combination_set` and `combination_evidence` sat complete and uncalled.

None of these is a check that failed to finish. Each is a claim the document makes that
nothing answered, and a reader has no way to tell the difference between "checked and fine"
and "never looked at".

## What Changes

- `validation-gauntlet`'s **No silent green** requirement covers declarations as well as
  executions: a screen SHALL answer every claim the document makes, or report that nothing
  did, naming what it would take.

## Impact

Cards that used to read PASS now read NOT_EVALUATED where a declared bound was never
screened. That is the point: the exit code and the roll-up both move, and a reader who was
being told "this part passed" is told instead which of the things they wrote down nobody
looked at.
