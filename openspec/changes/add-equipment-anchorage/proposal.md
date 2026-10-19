# Change: Equipment anchorage — the lateral force on a piece of equipment, and the anchors that resist it

## Why

Most machines, tanks, panels, skids and racks end up bolted to a concrete slab, and in
much of the world the governing load on those bolts is seismic. The calculation is
routine, mandated, and done in a spreadsheet: the component design force from the
building code's nonstructural-component chapter, the overturning moment from the
equipment's center of gravity, the tension and shear on each anchor, and the anchor
check against the concrete provisions. Anvilate has the last step (the structural pack's
cast-in anchor breakout and pullout screens) and the statics; it has nothing that knows
what force to apply.

ASCE 7-22 §13.3.1 rewrote the component force equation after the ATC-120 project
(NIST GCR 18-917-43), so that the ASCE 7-16 and ASCE 7-22 forms differ and both are in
force depending on the adopted code: California's 2025 building code adopts the 7-22
form, and the HCAI pre-approval program lists Equation 13.3-1 and Tables 13.5-1 and
13.6-1 as the items that changed. Commercial tools (Enercalc's nonstructural module)
sell exactly this calculation. No open tool does it with the edition pinned.

The standard is copyrighted and its coefficient tables are the part engineers look up.
Under the user-supplied allowables doctrine, the equation's structure is implemented from
the cited clause and every tabulated coefficient is entered by the user with its table
citation; the pack bundles none of them. Lateral forces that are not seismic — a declared
wind pressure on rooftop equipment, a machine's own dynamic force, a declared impact —
go through the same statics, so the anchorage screen is one element whatever the force's
origin.

## What Changes

| Area | Change |
| --- | --- |
| Component force | The horizontal seismic design force from the cited equation of the declared edition (ASCE 7-16 or 7-22 form), with every coefficient user-supplied with its table citation, the lower and upper bounds applied and cited, and the vertical component by the cited rule. |
| Other lateral forces | Declared wind, dynamic and impact forces as load cases on the equipment at a declared height. |
| Overturning and anchor forces | Statics from the declared mass, center of gravity, footprint and anchor pattern: tension and shear per anchor for the governing direction, with uplift and sliding checked. Friction is not relied on. |
| Anchor checks | The existing concrete anchorage screens run on the per-anchor forces, with the overstrength or ductility basis the document declares. |
| Base and frame | A skid or base frame carries the forces through `add-frame-analysis` to its anchors when declared. |

## Impact

- Delta: `discipline-packs` (ADDED). Builds on the structural pack's anchorage screens
  in `src/anvilate/packs/structural.py`, the seismic coefficients already in
  `src/anvilate/analysis/building_loads.py`, `add-standards-effectivity` (the edition
  changes the equation), `add-frame-analysis` (base frames), `add-product-screening`
  (mass and center of gravity roll-up), and `add-walking-working-surfaces-pack` (post
  bases).
- Licensing: ASCE 7 is copyrighted. The equation structure is implemented from the
  cited clause; coefficient tables are never bundled and are user-supplied with their
  table citation. The NIST report behind the 7-22 change is a US government publication.
- Explicitly out:
  - Post-installed anchor capacities (product-specific, evaluation-report gated); the
    user supplies them with the report citation.
  - Vibration isolators and snubbers as elements (the isolation screen exists; the
    isolator's restraint is a user-declared load path).
  - Any statement of code compliance or jurisdiction mapping.
