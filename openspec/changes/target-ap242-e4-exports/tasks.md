# Tasks: Export targets refresh

## 1. Spec & pins

- [x] 1.1 Update project.md version-pinning guidance: OCCT 8.0.x via current OCP bindings
      for the geometry phase (verify OCP/build123d rebase status first) — **verified, and the
      answer is the opposite of the proposal's premise: the 7.9 pin stands.** `cadquery-ocp`
      tops out at 7.9.3.1.1 on PyPI (no 8.x release exists) and build123d 0.11.1 requires
      `cadquery-ocp-novtk >=7.9,<8.0`, so there is nothing to migrate to. The bump condition
      is now written down rather than re-litigated: an OCP 8.x release on PyPI *and*
      build123d relaxing its cap. CadQuery 2.8.0, Gmsh 4.15.2 and ezdxf 1.4.4 re-verified
      against PyPI the same day; all match the existing ranges
- [x] 1.2 Record AP242 E4 + Recommended Practices as the STEP writer target — **the
      Recommended Practices are recorded; the edition number is deliberately not.** The
      proposal's claim that Edition 4 published as ISO 10303-242:2025 could not be confirmed
      and is contradicted by the prostep ivip fact sheet it cites, which gives
      ISO 10303-242:2020 (Edition 2) as normative and says Edition 4 is in development.
      ISO's catalogue rejects scripted access, so the registry could not be checked from
      here. The requirement now targets AP242 at the latest edition the kernel supports,
      per the CAx-IF Recommended Practices, and requires the edition *actually written* to
      be recorded in the evidence bundle — correct whichever edition is current when the
      writer lands

## 2. Conformance harness (lands with STEP export)

- [x] 2.1 Independent-analyzer CI job over exported files — the scheduled `step-referee`
      job builds STEPcode (the former NIST STEP Class Library) at a pinned commit and reads
      every audited pattern's STEP with its AP242 reader, generated from the schema's EXPRESS
      long form and sharing no code with OCCT; both passes must report 0 errors and 0
      warnings. NIST's STEP File Analyzer, the referee first named here, is Windows-only;
      STEPcode runs on the Linux runners. Checked locally: the three patterns read clean
      (368, 136 and more instances), and an unknown entity or a short ADVANCED_FACE fails
- [ ] 2.2 CAx-IF/NIST PMI test-model regression fixtures for the reader/writer — confirmed
      freely downloadable (mbx-if.org hosts the FTC/STC/CTC models with AP242 STEP files and
      recommends exactly this loop); blocked on the same exporter
- [x] 2.3 3MF writer via reference implementation with ISO citation in metadata —
      `export.threemf.render_mesh_3mf` writes the ISO/IEC 25422:2025 core (millimetres,
      deterministic bytes, the standard and writer in metadata beside the export watermark),
      refusing an open or inconsistently oriented mesh; `geometry.render_3mf` tessellates the
      three audited patterns, welds shared vertices, and holds the mesh to the solid's volume.
      Validated as an equivalent writer: lib3mf (the reference implementation, BSD-2, a dev
      dependency) reads every file in strict mode with no warnings (tests/test_threemf.py)

## 3. Docs

- [x] 3.1 Export documentation: what E4 adds, what the conformance gate guarantees —
      `docs/export-targets.md`, written as a verification record rather than a summary: each
      claim marked confirmed or not, with how it was checked, plus what the conformance gate
      will *not* guarantee. It does not describe what E4 adds, because nobody here has
      confirmed that E4 is published

## Note

This change first shipped no code, which is what made re-aiming cheap; the 3MF writer
(2.3) landed later. Its value turned out to be the two premises that did not survive checking.
