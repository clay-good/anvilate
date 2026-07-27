# Change: Weld fatigue screening — detail categories, cited S-N math, damage summation

## Why

Nominal-stress weld fatigue is the most common fatigue question in fabricated structures,
and the open-source stack stops one step short of answering it. pyLife (MIT, active) is
FKM-oriented and ships no detail categories; fatpack implements Eurocode-form trilinear
endurance curves and rainflow but bundles no category tables; nobody ships the step
engineers actually get wrong — *selecting the detail category for a joint and defending
the choice*. Meanwhile the shipped `fatigue` module already has Miner summation and
Basquin S-N, so the missing piece is the detail-category contract, not the math.

The licensing shape is the one Anvilate already handles well: category values live in
copyrighted standards (EN 1993-1-9, IIW), so the *user supplies the detail category* —
guardrail-safe exactly like a user-supplied allowable — and Anvilate encodes the
standardized curve construction (m = 3 / m = 5 slopes, constant-amplitude limit at 5M,
cutoff at 100M, thickness and mean-stress corrections) with clause citations. A new open
dataset of 52,608 welded-joint S-N sets (Scientific Data, 2025,
https://doi.org/10.6084/m9.figshare.29254265.v2) is available for validation and
benchmarking, subject to license verification, but is never the normative basis.

## What Changes

- One ADDED requirement to `analysis-library` (depends on
  `codify-analysis-library-contract`): a weld fatigue screening set — typed detail
  category as a user-supplied input with its declared source, standardized S-N curve
  construction from that category with cited slopes and knee points, size/thickness and
  mean-stress corrections applied explicitly and visibly, cumulative damage over a
  declared stress-range spectrum, and an allowable-cycles design inverse.

## Impact

- Affected specs: `analysis-library` (one ADDED requirement).
- Affected code (when implemented): extends `analysis/fatigue.py` and `analysis/weld.py`;
  composes the existing Miner summation.
- Interacts with `add-uncertainty-margins` (fatigue life is the natural home for scatter)
  and `add-lifting-device-pack` (service-class fatigue) without depending on either.
- Explicitly out: hot-spot and notch-stress methods (they need FEA-derived stresses),
  detail-category *inference* from geometry, and any bundled category table.
