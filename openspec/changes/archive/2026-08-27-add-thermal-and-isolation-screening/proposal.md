# Change: Thermal screening and vibration-isolation/shock screening

## Why

Two adjacent screening domains are unserved by cited OSS and sit squarely in Anvilate's
audience:

- **Thermal screening for enclosures/electronics.** OSS is fragmented hobby scripts
  (e.g., https://github.com/sww1235/heatsink-calc) or full CFD; nothing offers cited
  closed-form screening (thermal resistance networks, fin efficiency, natural/forced
  convection correlations per Incropera-class sources) with junction-temperature margins.
  Mechanical engineers doing enclosure design are existing Anvilate users.
- **Vibration isolation and shock.** OSS covers measurement/analysis (enDAQ, PyTTa) but
  not *design screening*: transmissibility vs. frequency ratio and damping, isolator
  margin, half-sine shock response. Anvilate already ships the isolator
  static-deflection inverse; this completes the family.

Both are pure closed-form + citation — the established analysis-library pattern.

## What Changes

- `analysis-library` gains two requirements: a thermal screening set (resistance
  networks, fin/fin-array efficiency, convection correlations with stated validity
  ranges, junction-temperature margin checks) and a vibration-isolation/shock screening
  set (transmissibility, isolator selection margin, half-sine shock response), each
  cited, unit-typed, worked-example-anchored per the library contract.

## Impact

- Affected specs: `analysis-library` (2 added requirements; depends on
  `codify-analysis-library-contract`).
- Affected code (when implemented): new analysis modules + examples; correlation validity
  ranges enforced (out-of-range inputs report not evaluated, not extrapolated).
