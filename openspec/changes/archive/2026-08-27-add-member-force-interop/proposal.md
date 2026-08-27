# Change: Member-force and section-property interop — analysis in, cited checks out

## Why

The most explicit unmet demand found in the OSS structural ecosystem is the code-check
layer on top of analysis: Pynite's own suggestion box is dominated by requests for AISC
360 design checks over computed member forces
(https://github.com/JWock82/Pynite/discussions/106), and the StructuralPython community
hand-assembles analysis + checking + reporting from fragments. Anvilate has the cited
check library; it lacks a typed doorway for externally computed member forces and section
properties. sectionproperties (https://github.com/robbievanleeuwen/section-properties)
is the de-facto engine for arbitrary cross-section constants and pairs naturally with
Anvilate's beam/torsion checks — an "FEA-lite" step requiring none of the deferred native
dependencies.

This positions Anvilate as the checking layer *for* the ecosystem instead of a competitor
to it.

## What Changes

- `analysis-library` gains three requirements: typed member-force ingestion (external
  analysis results feed cited member checks, with external-tool provenance), typed
  section-property ingestion (sectionproperties-class constants as CrossSection inputs,
  optional dependency), and a no-silent-assumptions rule for axis conventions and units
  on import.

## Impact

- Affected specs: `analysis-library` (depends on `codify-analysis-library-contract`).
- Affected code (when implemented): typed import records, axis-convention mapping,
  optional-dependency adapter for sectionproperties; structural pack check bindings.
- No change to existing check behavior; ingestion is a new input path.
