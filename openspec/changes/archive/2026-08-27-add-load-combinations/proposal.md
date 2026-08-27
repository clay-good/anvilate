# Change: Load combinations — typed factoring and governing-combination tracking

## Why

Anvilate validates strictly per load case; no requirement anywhere in `specs/` factors or
combines cases, yet every code check the structural packs cite assumes factored
combinations (LRFD) or service combinations (ASD) as input. Today that bookkeeping lives
in the user's head — the exact silent-error class Anvilate exists to remove. The
ecosystem confirms the gap: OSS analysis tools (Pynite) accept user-typed factors but
generate nothing; combination generation lives in throwaway web calculators; the one
PyPI "package" marketed for it does not exist (the promoting article is AI-generated slop
— verified via PyPI 404, July 2026). The combination expressions themselves (ASCE 7-22
Chapter 2) are short, universally republished equation lists with no meaningful
redistribution risk — unlike wind/seismic load *derivation*, which stays out of scope.

## What Changes

- `spec-ir` (ADDED): load cases may be classified by load nature (dead, live, wind,
  seismic, thermal, …), and a spec may declare a combination set — either generated from
  a named code basis (ASCE 7-22 LRFD or ASD, with seismic parameters as typed user
  inputs) or fully custom — as typed factored sums over declared cases.
- `validation-gauntlet` (ADDED): when a combination set is declared, checks evaluate
  every combination, report the envelope, and name the governing combination; no silent
  subsetting.

## Impact

- Affected specs: `spec-ir`, `validation-gauntlet` (one ADDED requirement each; all
  existing requirements unchanged — per-case evaluation remains the default when no
  combination set is declared).
- Affected code (when implemented): combination generator + expansion in the gauntlet
  runner; structural pack checks consume factored results unchanged.
- Out of scope: deriving wind/seismic/snow load magnitudes from maps or site parameters
  — combination factoring only.
