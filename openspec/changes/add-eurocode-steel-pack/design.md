# Design notes: Eurocode 3 steel pack

Research done on 2026-10-19. Standards are paywalled; "anchor before implementing"
applies: no clause ships from a remembered edition.

## Editions and the transition

| Standard | Generation | Dates verified |
| --- | --- | --- |
| EN 1993-1-1:2005+A1:2014 | First | Applicable until national withdrawal, latest 2028-03-30 |
| EN 1993-1-1:2022 | Second | CEN approval 2022-07-24; DAV 2026-03-30; DoP 2027-09-30; DoW 2028-03-30 (JRC 2G Eurocode 3 workshop, 2025-06-03; BSI listing) |
| EN 1993-1-8:2005 | First | Superseded, applicable until withdrawal |
| EN 1993-1-8:2024 | Second | Approved 2024-03-27; DIN German version 2025-04 |

Sources:
- https://eurocodes.jrc.ec.europa.eu/sites/default/files/2025-08/20250603_2G_Eurocode3_JRC%2BWorkshop_final_website_0.pdf
- https://www.scia.net/en/news/second-generation-eurocodes-approaching
- https://genorma.com/en/standards/en-1993-1-8-2024
- https://tienda.aenor.com/p/norma-cen-en-1993-1-8-2024-64986

The pack ships with the first generation as its default edition until the owner's
jurisdiction changes, because that is what reviewers accept today, and declares it.
The second generation is selectable through the design basis the moment it is anchored.

## Open-source references (not dependencies)

| Library | License | State | Decision |
| --- | --- | --- | --- |
| Blueprints (Blueprints-org) | LGPL-2.1 | NEN-EN 1993-1-1+C2+A1:2016; 108 formulas, 20 tables, 28 figures | Reference for formula transcription checks; Dutch annex values never copied |
| steelsnakes | not verified | Eurocode 3 "in progress", docs updated 2026-03 | Watch |
| PySS | not verified | last release 0.6.0, 2020 | Reference only |
| eurocodepy | not verified | European profile JSON (IPE, HEA, HEB, HEM, L, C, T, pipe, box) | Profile geometry only, through `expand-open-design-data`, after its license is read |

Sources: https://github.com/Blueprints-org/blueprints, https://steelsnakes.readthedocs.io/,
https://pyss.readthedocs.io/en/latest/history.html, https://eurocodepy.readthedocs.io

## Nationally determined parameters

The recommended values in the standard are bundled with the clause that gives them. A
national annex value is a user-supplied input with its citation, under the existing
user-supplied allowables doctrine. The pack has no table of annexes by country, on
purpose: `add-standards-effectivity` already rules that a jurisdiction map is advisory at
most, and a wrong γM1 is a wrong buckling resistance.

## Composition with the AISC pack

Flexural buckling, lateral-torsional buckling and bolt bearing are limit states both codes
screen. Under the module contract they share a limit-state registry id; the EN screen
computes the EN resistance from the EN clause and cites it, and the duplicate detector
sees one limit state with two code implementations, not two conflicting checks.

## Golden tests

Worked examples with published numbers, re-derived rather than redistributed: the
Steel Construction Institute's and Arcelor's free worked examples for the first
generation, and the JRC "Eurocode 3 worked examples" where the second generation is
covered. Each test names its source and the edition.
