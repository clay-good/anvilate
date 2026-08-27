# Change: Process piping pack (ASME B31.3 screening)

## Why

Process piping is the largest closed-form code-check gap found in the OSS ecosystem: no
maintained Python library implements ASME B31.3 screening — the space is one-off web
calculators and Excel next to expensive CAESAR II seats; even ChEDL's excellent `fluids`
library deliberately avoids code-compliance checks
(https://github.com/CalebBell/fluids). B31.3's governing checks — pressure-design wall
thickness (§304.1.2), branch reinforcement, miter bends, displacement-stress-range
screening — are pure closed-form + tables, exactly Anvilate's pattern. The copyrighted
allowable-stress tables (Table A-1) are handled by Anvilate's established user-supplied
allowables doctrine.

## What Changes

- `discipline-packs` gains a process piping pack requirement: B31.3-cited screens for
  straight-pipe wall thickness, branch reinforcement, miter bends, and displacement
  stress range, with allowable stresses user-supplied (never bundled) and every check
  citing its paragraph.

## Impact

- Affected specs: `discipline-packs` (1 added requirement).
- Affected code (when implemented): new pack module + analysis functions, examples,
  worked-example anchors; pipe dimension tables (ASME B36.10M/B36.19M dimensions are
  standard-defined data, bundled with citations like existing fastener tables).
- Follows the existing pack contract (checks cite clause + edition, screening label,
  same scorecard).
