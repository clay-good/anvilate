# Change: Eurocode 3 steel pack — members and joints checked to EN 1993, with the generation declared

## Why

The `discipline-packs` spec has promised since the start that "Eurocode (EN 1993-1-8)
check sets SHALL follow the same contract when shipped." Nothing has shipped. Every
structural steel screen Anvilate runs today is AISC 360, so a European, Middle-Eastern or
Asia-Pacific structural engineer gets a base plate, a gusset or a beam checked to a code
their checker will not accept.

The timing is unusual and argues for doing it now rather than later. The second
generation of the Eurocodes is arriving in exactly the window this project is in:

| Document | Status (verified 2026-10-19) |
| --- | --- |
| EN 1993-1-1:2022 (general rules, members) | Published; approved by CEN 2022-07-24. Definitive texts to national bodies by 2026-03-30; national publication by 2027-09-30; conflicting national standards withdrawn by 2028-03-30. BSI and SNV have published their versions. |
| EN 1993-1-8:2024 (joints) | Approved 2024-03-27, listed in force; supersedes EN 1993-1-8:2005. |
| EN 1993-1-1:2005+A1:2014, EN 1993-1-8:2005 | Still the applicable standards in most jurisdictions until a relevant authority or project specification says otherwise, and withdrawn only in 2028. |

So for the next eighteen months both generations are in active use, often on the same
desk, and a check that does not say which generation it implements is unreviewable. That
is the case `add-standards-effectivity` was written for, and this pack is its first
consumer that needs both generations of one standard at once.

The open-source field confirms the gap without filling it. Blueprints (LGPL-2.1,
Blueprints-org) implements 108 formulas, 20 tables and 28 figures of the Dutch annex
edition of EN 1993-1-1 as a formula library; steelsnakes is under active development
with its Eurocode 3 region marked in progress; PySS last released in 2020. None is a
cited screen with a no-silent-green verdict, none carries partial factors as declared
nationally determined parameters, and the one that is mature is LGPL and annex-specific.
They are references, not dependencies. Anvilate's pack is implemented from the cited
clauses, as the AISC, ADM and NDS packs were.

## What Changes

| Area | Change |
| --- | --- |
| Members to EN 1993-1-1 | Cross-section classification by the width-to-thickness limits of the declared edition; cross-section resistance in tension, compression, bending, shear, and their interactions; flexural buckling by the cited buckling curves; lateral-torsional buckling; combined bending and axial compression by the interaction method the document declares. Each verdict cites its clause and its edition. |
| Joints to EN 1993-1-8 | Bolted connections by category (bearing type and slip-resistant, shear and tension), with bearing, shear, tension, punching and combined checks; slip resistance from a declared slip factor with its source; fillet welds by the directional method or the simplified method, declared, never silently chosen. |
| Nationally determined parameters | Partial factors (γM0, γM1, γM2) and the other parameters a national annex may set are typed inputs. The recommended values are bundled with their clause; a national annex value is entered by the user with its citation and overrides them, marked as user-supplied wherever it governs. The pack never guesses which annex applies. |
| Both generations | A design basis pins the edition per standard. Where a provision differs between the 2005 and 2022 generations and the difference is registered, the pack can evaluate under both and report the difference; where it is not registered, the pack says which edition it implements and reports the other as not evaluated. |
| Steel grades | Nominal yield and ultimate strengths for S235 to S460 by thickness range, cited to the product standard, as materials records with provenance. |
| European profiles | IPE, HE, UPN/UPE, L, hollow sections and the rest resolve from open profile geometry with properties computed at build time, through the importer `expand-open-design-data` already specifies. |
| Drawable parts | The parts that already draw (base plate, gusset, shear plate, members, lug) screen to EN 1993 when the document declares a Eurocode design basis. No new geometry. |

## Impact

- Delta: `discipline-packs` (ADDED). Builds on `add-standards-effectivity` (edition and
  design basis), `expand-open-design-data` (European profile data), the existing steel
  section library, and the module contract in `add-physical-domain-modules` (a limit
  state the AISC pack already implements is reused where the two codes share the
  physics, and the EN clause is cited on the EN entry).
- Licensing: the Eurocode text is copyrighted by CEN and sold by national bodies. The
  pack implements the cited formulas and bundles only the recommended values of
  nationally determined parameters and the nominal material strengths, each with its
  clause. No table of the standard is reproduced. Blueprints, steelsnakes and PySS are
  consulted as references and not vendored.
- Explicitly out:
  - EN 1993-1-2 (fire), 1-3 (cold-formed; the AISI pack covers DSM), 1-5 (plated
    structures), 1-9 (fatigue, which the weld-fatigue screen already covers with
    EN 1993-1-9 detail categories), 1-10 (toughness selection).
  - Semi-rigid joint stiffness (the component method). Joints are checked for
    resistance; rotational stiffness is a later phase.
  - Any national annex's values. They are the user's, with a citation.
  - Any claim that a design complies with a national building regulation.
