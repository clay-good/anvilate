# Change: Pressure equipment pack (ASME VIII Div 1 components)

## Why

Anvilate already screens cylinder MAWP per ASME VIII; the surrounding component checks
that make it a coherent pressure-equipment story are missing, and the best OSS found is an
Excel/VBA workbook (ASME-PVDE, https://github.com/ry4ngch/ASME-PVDE) — no Python
equivalent exists. Formed heads (ellipsoidal/torispherical), UG-37 nozzle-opening area
replacement, conical sections, and Appendix 2 flange design are closed-form, cited, and
constantly recomputed in spreadsheets by exactly Anvilate's audience.

## What Changes

- `discipline-packs` gains a pressure equipment pack requirement: VIII-Div-1-cited
  screens for formed heads, nozzle reinforcement (UG-37), cones, and Appendix 2 flanges,
  composing with the existing cylinder MAWP and gasket (m/y) functions; allowables
  user-supplied per the established doctrine.

## Impact

- Affected specs: `discipline-packs` (1 added requirement).
- Affected code (when implemented): new analysis functions + pack module; reuses existing
  pressure_vessel and gasket modules; worked-example anchors from published VIII example
  problems.
