# Change: Timber connections — dowel-type fasteners checked by the yield modes

## Why

The timber pack screens members: bending, shear, compression, bearing, stability, with
the NDS adjustment-factor chain itemized. A timber structure fails at its connections
far more often than in its members, and the pack has no connection screen. A bolt, lag
screw, nail or screw through wood is checked by the yield limit equations, which the NDS
adopted from Johansen's rigid-plastic theory (the European Yield Model): the capacity is
the least of the yield modes — crushing of the main or side member (Im, Is), dowel
rotation (II), one plastic hinge with crushing (IIIm, IIIs), and two or three hinges
(IV) — each a closed form in the fastener diameter, the dowel bending yield strength and
the members' dowel bearing strengths.

The forms are open literature. The American Wood Council's Technical Report 12 publishes
the generalized yield limit equations, including hollow members, gaps and varying
diameters, and is freely downloadable; Eurocode 5 states the same model in its own
notation. What is proprietary is the NDS's tabulated dowel bearing strengths and the
reference values that result, and under the user-supplied allowables doctrine those are
the user's inputs with a citation, or computed from a cited formula with the specific
gravity declared.

Engineers do this today in a spreadsheet they downloaded. Every one of the inputs is
already the kind of declaration the timber pack takes.

## What Changes

| Area | Change |
| --- | --- |
| Yield modes | Single- and double-shear capacity by every applicable yield mode, from the generalized equations, with the governing mode named and the cited section of the declared NDS edition. |
| Inputs | Fastener diameter and dowel bending yield strength, member thicknesses, dowel bearing strength of each member parallel and perpendicular to grain (user-supplied with citation, or from a cited formula with declared specific gravity), load-to-grain angle, and the reduction terms per mode from the cited table, user-supplied. |
| Adjustments | The existing itemized factor chain extended with the connection factors (group action, geometry, end grain, toe-nail where applicable), each visible with its condition. |
| Geometry | Edge distance, end distance, spacing and row spacing against the minimums the user declares from the cited table, with the factor consequence stated. |
| Withdrawal | Nail, screw and lag-screw withdrawal from user-cited values. |
| Honest gaps | A connection with no dowel bending yield strength or no bearing strength is not evaluated naming it. Hardwood dowels and other cases the yield equations do not cover are refused naming the limitation. |

## Impact

- Delta: `discipline-packs` (ADDED). Builds on the timber pack in
  `src/anvilate/packs/timber.py` and `src/anvilate/analysis/nds_timber.py` (the factor
  chain is reused), the fastener-group screen (bolt groups), and
  `add-standards-effectivity` (NDS edition).
- Licensing: AWC TR12 is freely published and cited for the generalized equations; the
  NDS itself is copyrighted and its tables are never bundled.
- Explicitly out:
  - Metal connector plates and proprietary hangers (product-specific capacities, the
    user's with the report citation).
  - Moment connections and split rings in the first phase.
  - Eurocode 5 connections, which follow when the Eurocode packs reach timber.
