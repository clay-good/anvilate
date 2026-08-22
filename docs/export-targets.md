# Export targets, and what was actually verified

**Aiming a target is cheap before the code exists and expensive afterwards — but a target
aimed at an unverified claim is worse than no target.** This page records where Anvilate's
export layer is pointed, and, for each claim, whether it was confirmed from a primary source
on **2026-08-22** or is carried as unverified.

No export code exists yet for STEP or 3MF. This is a roadmap page with citations, not a
description of shipped behavior. What *is* shipped is
[DXF plate export](../src/anvilate/export/dxf.py) and
[QIF Results](quality-interchange.md).

## What was confirmed

| Claim | Status | How |
| --- | --- | --- |
| The NIST STEP File Analyzer and Viewer is the de-facto free AP242 PMI checker | **confirmed** | [usnistgov/SFA](https://github.com/usnistgov/SFA) is live and its README describes AP242, AP203, AP214, AP209 and AP238 handling |
| The CAx-IF/MBx-IF MBE PMI test models are freely downloadable AP242 regression fixtures | **confirmed** | [mbx-if.org resources](https://www.mbx-if.org/home/cax/resources/) hosts the FTC, STC and CTC models with AP242 STEP files, and tells implementers to export AP242 and run the result through the NIST analyzer — which is exactly the conformance loop the spec asks CI to automate |
| 3MF is ISO/IEC 25422:2025 | **confirmed** | stated on [3mf.io](https://3mf.io/) |
| OCCT upstream has reached 8.0.1 | **confirmed** | `V8_0_0` and `V8_0_1` tags on the OCCT repository |

## What was not confirmed, and the target changed because of it

**AP242 "Edition 4, ISO 10303-242:2025" could not be confirmed, and its own cited source
says otherwise.** The prostep ivip fact sheet this project cited for the claim gives
ISO 10303-242:**2020**, Edition 2 as the normative document, describes Edition 3 as a
corrective maintenance edition, and says **"AP 242 Edition 4 is in development."** ISO's own
catalogue rejects scripted access (HTTP 403), so the publication date could not be checked
against the registry from here.

That does not prove Edition 4 is unpublished — the fact sheet may be stale. It does mean
nobody has verified that it *is*. So the requirement no longer names an edition. It targets
**AP242 at the latest edition the writer's kernel supports, written per the CAx-IF
Recommended Practices**, and it requires the edition actually written to be recorded in the
evidence bundle. That target is correct whichever edition is current when the writer lands,
and it makes the edition a fact about the file instead of a claim in a roadmap.

The Recommended Practices matter more than the ISO number either way: they, not the standard
text alone, are what makes two implementations interoperate, and they are what the free
referee checks against.

## The version pins, and the bump condition

The project-context guidance said "stay on OCCT 7.9; OCP 8 bindings are still
RC/experimental." Checked today, the pin stands but for a stronger reason than that:

- `cadquery-ocp` on PyPI tops out at **7.9.3.1.1**. There is no OCP 8.x release at all.
- `build123d` 0.11.1 requires `cadquery-ocp-novtk >=7.9,<8.0`.

So there is nothing to migrate *to*, and the geometry layer could not take it if there were.
The bump condition is now written down in
[`openspec/project.md`](../openspec/project.md) so it does not get re-litigated: an OCP 8.x
release on PyPI **and** build123d relaxing its `<8.0` cap. Both, then migrate.

Also re-verified against PyPI the same day: CadQuery 2.8.0, Gmsh 4.15.2, ezdxf 1.4.4 — all
matching the ranges already pinned.

## What the conformance gate will and will not guarantee

When the STEP writer lands, CI will run every exported file through an independent analyzer
and regression-test the reader and writer against the free test models. That buys a real
guarantee and a narrow one:

- **It will guarantee** that the file declares the AP242 schema, that its validation
  properties are present and self-consistent, and that its semantic PMI matches the test
  case's expected PMI where a test case exists.
- **It will not guarantee** that a particular commercial CAD system imports it without
  complaint — that is the separate import-regression matrix, and its proprietary tier runs
  on a documented cadence rather than on every commit.
- **It will not make the export a certified translation.** The same rule the scorecard
  follows applies: a check that could not run is reported as not run.
