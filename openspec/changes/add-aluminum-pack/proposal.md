# Change: Aluminum structural design pack (ADM 2020)

## Why

Aluminum member design is the most persistently spreadsheet-bound structural discipline
surveyed: two decades of Eng-Tips threads all answer "write your own spreadsheet or use
Mathcad" (https://www.eng-tips.com/threads/aluminum-design-software-or-spreadsheet.394821/,
https://www.eng-tips.com/threads/aluminum-design-programs.269726/), commercial coverage is
thin analysis-suite add-ons (RISA, Dlubal RF-ALUMINUM), and no open-source ADM
implementation exists anywhere (verified July 2026). The audience — handrails, platforms,
walkways, sign structures, curtain wall, marine — is steady and unserved. The ADM's
unified-format member equations mirror AISC 360's structure, so this pack reuses the
architecture, doctrine, and section machinery the shipped structural steel pack already
established. ADM 2020 is viewable free on ICC Digital Codes
(https://codes.iccsafe.org/content/AAADM2020P1), giving users a no-cost way to verify
every cited clause.

## What Changes

- One ADDED requirement to `discipline-packs`: an aluminum structural pack providing ADM
  2020 member screens — yielding/rupture, local buckling by width-to-thickness class,
  member (flexural) buckling, lateral-torsional buckling, and combined loading — with
  weld-affected-zone (HAZ) strength reductions as a first-class, always-visible
  modifier, since welded aluminum's strength loss is the discipline's signature trap.
- Alloy-temper mechanical properties follow the user-supplied-allowables doctrine;
  buckling constants are computed from cited ADM formulas, never tabulated from the
  standard's tables.

## Impact

- Affected specs: `discipline-packs` (one ADDED requirement; existing packs unchanged).
- Affected code (when implemented): an `aluminum` pack module reusing the member-check
  architecture, section-property machinery, and combined-loading interaction forms of the
  structural steel pack.
- Data: alloy/temper properties (Fcy, Ftu, kt, weld-affected values) user-supplied with
  provenance, or resolved from the curated materials DB where records carry a
  redistribution-clean source; the ADM's own property tables are never bundled.
