# Change: Structural hand methods — the calculations aerospace and vehicle engineers actually sign

## Why

Anvilate's analysis library is wide: about 260 closed-form modules. On the methods that
lightweight structures depend on, it is shallow:

| Missing | Who needs it |
| --- | --- |
| A lug method with transverse and oblique loads | Every aircraft fitting, crane and trailer hitch |
| Preloaded-joint screening with preload scatter, relaxation and separation, to the free NASA bolted-joint standard | Spacecraft reviewers require it; vehicle teams want the same physics |
| Crippling, and buckling corrected for plasticity | Thin-walled extrusions and formed sections |
| Laminate theory (only micromechanics exists) | Every composite part |
| Sandwich-panel checks | Panels, floors, enclosures |
| Random-vibration screening (Miles' equation exists only inside the opto-mechanics module) | Every spacecraft, UAV and vehicle-mounted electronics box, which needs it on day one |
| A fracture-control classification helper | Aerospace hardware that must be shown non-fracture-critical |

Each has a public-domain anchor, so none needs a paid source. Most are documented in
NASA and Air Force reports that are free to read and cite:

- the Astronautics Structures Manual (NASA TM X-73305);
- the Air Force stress analysis manual (AFFDL-TR-69-42);
- NASA-STD-5020B (revalidated January 2026);
- NASA-SP-8007;
- GSFC-STD-7000B.

The commonly used textbooks are copyrighted. Their equations can be cited, but their
design curves must not be digitized.

## What Changes

New screens in `analysis-library`, each under the existing contract: unit-typed, cited by
clause, regression-anchored to a worked example, and paired with its inverse where one is
useful.

| Screen | Content |
| --- | --- |
| Preloaded joints (NASA-STD-5020B) | Maximum and minimum preload from the tightening method's scatter, short-term relaxation, and creep and thermal loss. Separation, with the separation factor. Slip. Bolt ultimate and yield under the fitting factor. Separation before rupture. |
| Lugs | Axial, transverse and oblique loads with the interaction rule, net-section, shear-bearing and bushing bearing, from the public-domain Air Force method. |
| Crippling and plastic buckling | Section crippling by element. Column and plate buckling with tangent- or secant-modulus plasticity correction. Thin-cylinder knockdown from NASA-SP-8007. |
| Fastener interaction | Combined shear and tension interaction, sheet pull-through, and load distribution in a fastener group by fastener and sheet stiffness. |
| Laminates | Classical lamination theory (the ABD matrix), ply stresses and strains, and first-ply failure by maximum stress, maximum strain and Tsai-Wu, with the strength basis stated. |
| Sandwich panels | Face wrinkling, intracell dimpling, core shear, and insert pull-out against a declared insert allowable. |
| Random vibration | Grms of a declared input PSD, response by Miles' equation from a declared Q, 3σ peak, and combination with quasi-static load factors by a declared rule. |
| Fracture-control helper | A classification record checked against the public standard's conditions, offered as a candidate for the engineer to accept and never as a classification on its own. |

## Impact

- Delta: `analysis-library` (ADDED). Results feed `add-margin-of-safety-reporting`, and
  joints and fittings accept loads from `add-cae-handoff`.
- Builds on the existing fastener, column, plate, composite-micromechanics, fracture and
  dynamics modules. It extends them rather than duplicating them.
- Open libraries with permissive licenses (lamination, bolted-joint stress fields) may be
  wrapped as optional extras, with their versions recorded in the evidence bundle.
- Explicitly out:
  - Damage-tolerance crack-growth software methods.
  - Proprietary design-curve data.
  - Open-hole and bearing-bypass allowables. These are user-declared with their basis.
  - Any certification claim.
