# Change: Export targets refresh — AP242 Edition 4, conformance refereeing, 3MF as ISO

## Why

The export landscape moved in 2025–2026 and the roadmap targets should move with it,
before STEP export code exists:

- **STEP AP242 Edition 4** published as ISO 10303-242:2025 (Aug 2025), extending semantic
  PMI (surface conditions, assembly-level PMI) and connection information
  (https://www.prostep.org/en/medialibrary/fact-sheets/iso-10303-242-step-ap242).
- **OCCT 8.0.0** shipped May 2026 (8.0.0p1 June 2026) with major STEP improvements —
  the project-context pin guidance ("stay on 7.9") is now stale.
- **Conformance refereeing is free**: NIST's STEP File Analyzer remains the de-facto
  AP242 PMI checker (https://github.com/usnistgov/SFA) and the CAx-IF/MBx-IF test models
  are freely downloadable regression fixtures (https://www.mbx-if.org/home/cax/resources/);
  the Recommended Practices, not the ISO text alone, are what makes exports interoperate.
- **3MF is now ISO/IEC 25422:2025** with a ratified Beam Lattice extension — the print
  export can cite an ISO number, on-brand for Anvilate.

## What Changes

- `artifact-export`: the STEP requirement is modified to target AP242 Edition 4 written
  per the CAx-IF Recommended Practices, with CI conformance refereed by an independent
  analyzer and the free interoperability test models; a new requirement pins 3MF export
  to ISO/IEC 25422 semantics.
- `openspec/project.md` version-pinning guidance updates to OCCT 8.0.x via current OCP
  bindings when the geometry phase starts (noted as impact; project.md is maintained
  alongside archiving).

## Impact

- Affected specs: `artifact-export` (1 modified, 1 added requirement).
- Affected code: none yet — STEP/3MF export is unbuilt; this re-aims the target at the
  cheapest possible time.
