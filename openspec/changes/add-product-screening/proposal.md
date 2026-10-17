# Change: Product screening — the checks that only exist once parts meet

## Why

Every part in a product can pass its own screen while the product fails. The load the
engineer knows is the one on the product (a 50 kg payload on the carriage, a 2 g shock on
the frame), not the share each bracket carries. The mass that matters is the total and
where its center sits, not each part's. The tolerance that matters runs through five
parts. The fasteners that slow assembly are the eleven different sizes nobody noticed
accumulating. None of these is visible on a part card, and all of them are what an
experienced reviewer checks first at a design review.

Commercial tools do each of these in a separate, expensive module. No open tool does
them from a text model with cited methods. Anvilate already has the pieces (part screens,
joint checks, the budget primitive, 1D stack-ups, keepouts, constraint topology); this
change connects them across a product tree.

## What Changes

| Area | Change |
| --- | --- |
| Load path | Loads declared on the product are carried through its connections to ground by rigid-body statics, and each part is screened with the interface loads it carries. A statically indeterminate path is reported as such, never solved by guessing a split. |
| Mass properties | Mass, center of mass and inertia rolled up the tree, with each item's basis (computed, declared, placeholder) and maturity with its growth allowance shown; comparable against a declared mass or CG budget through the existing budget mechanism. |
| Clearance | Minimum gap between every pair of items, against declared clearances, alongside the existing interference check; swept clearance over each declared joint range. |
| Stack-ups across parts | A 1D tolerance chain may run through connections, picking up each part's toleranced dimension and each connection's fit. |
| Mobility | A Grübler–Kutzbach count of the product's declared joints, reported as a first-pass count that names parallel or coincident axes, never as a verdict on motion. |
| Thermal mismatch | Joints between dissimilar materials over a declared temperature range: differential growth across the joint against its clearance or slip allowance. |
| Assembly economy | Part count, unique fastener count, tool count, and merge candidates by the three classic part-count questions, reported as candidates for the engineer, not as a scored index. |
| Cost roll-up | Screening-grade cost rolled up the tree from part estimates and component prices the user supplies. |

## Impact

- New capability: `product-screening`. Delta: `tolerance-management` (ADDED).
- Builds on `add-product-structure`, `add-interface-contracts`, `add-purchased-components`.
  Reuses `add-performance-budgets` for mass/CG budgets, `add-constraint-topology` for
  indeterminacy, `add-keepout-envelopes` for swept volumes, and `add-check-dependency-graph`
  so a part screen that reads an interface load is downstream of the load-path entry.
- Explicitly out: FEA of the whole product; statically indeterminate load sharing (named,
  not solved); dynamics beyond the existing equivalent-static screens; proprietary DFA
  time tables.
