# Export targets, and what was actually verified

**Aiming a target is cheap before the code exists and expensive afterwards — but a target
aimed at an unverified claim is worse than no target.** This page records where Anvilate's
export layer is pointed, and, for each claim, whether it was confirmed from a primary source
or is carried as unverified. Dates are named where they affect the conclusion.

A plain validation-gated AP242 STEP B-Rep writer is now shipped through `anvilate build` for
the audited `base_plate/1`, `cover_plate/1`, `transmission_shaft/1` and `timber_beam/1` patterns. It writes
valid solid geometry with a deterministic validation watermark and declares OCCT's managed
model-based 3D engineering schema. It also writes CAx-IF v4.6 part-level volume, total
surface area, and centroid properties, then verifies them against a fresh import before
releasing the file. It does
**not** populate or claim semantic PMI, which remains a roadmap target.

3MF is shipped as a library function for the same three patterns: `geometry.render_3mf(built,
authorization=...)` tessellates the solid, welds the vertices each face repeats, and writes
the ISO/IEC 25422 core through `export.threemf.render_mesh_3mf`. The file's metadata names
the standard, the writer and its version, and carries the export watermark. A mesh that is
not closed and consistently oriented, or that encloses a volume more than 1% from the
solid's own, is refused rather than written. The writer is this repository's, and its tests
read every file back with lib3mf, the 3MF Consortium's reference implementation, in strict
mode: no warnings, a manifold and oriented mesh, and the same metadata. `anvilate build` writes it when
`--output` ends in `.3mf`. There is no Beam Lattice content.
The other shipped formats are
[IFC](#ifc-for-a-structural-part-in-a-building-model), [DXF plate export](../src/anvilate/export/dxf.py) and [QIF Results](quality-interchange.md).
AP242 is the default; local `anvilate build --ap214` is the explicit legacy fallback and
retains the same properties and validation gate.

## IFC, for a structural part in a building model

`anvilate.export.ifc.render_ifc(parts, name=..., authorization=..., schema="IFC4")` writes
structural parts as the elements a building model holds, through IfcOpenShell (LGPL-3.0, the
optional `ifc` extra: `pip install 'anvilate[ifc]'`). `anvilate export --artifact ifc --output
part.ifc` and the MCP `export_artifact` tool (`format: ifc`) write one part, and `anvilate
combine frame.combination.yaml --output frame.ifc` writes a combination as one
`IfcElementAssembly`: each part at the rotation and shift its mates solved, its id as its
tag, and each bolt, nut and washer an `IfcMechanicalFastener` from its tabulated envelope
(`BOLT`; a nut and a washer are `USERDEFINED`, which neither schema enumerates). A
combination holding a part IFC has no class for, such as the bracket on its mounting plate,
is refused naming it. A product document still writes STEP only, and says so. IFC4 is the default; `--ifc-schema
IFC4X3_ADD2` (MCP: `ifc_schema`) writes IFC 4.3, where a base plate is its own `BASE_PLATE`
type, and naming a schema for a file that is not IFC is refused rather than ignored.

| What | How |
| --- | --- |
| Class per element | `IFC_ELEMENT_CLASSES`: beams `IfcBeam`, columns and beam-columns `IfcColumn`, tension members and tubes `IfcMember`, base, cover, gusset and shear plates `IfcPlate`. An element with no class is refused naming it, never written as a proxy. |
| Predefined type per schema | IFC 4.3 added `BASE_PLATE`, `GUSSET_PLATE` and `COVER_PLATE` to `IfcPlateTypeEnum`; IFC4 has none of them, so in IFC4 a base plate is `USERDEFINED` with `ObjectType` `BASE_PLATE`. Both enumerations were read from the schemas IfcOpenShell 0.9.0 ships, and a test reads them back. |
| Geometry | A member on a rolled or named section is its profile and an extrusion (`SweptSolid`): IPE and HEA as `IfcIShapeProfileDef` with the root radius, `BOX`, `TUBE` and `NPS ... SCH ...` as the rectangular and circular hollow profiles, and an AISC HSS (once its consented table is fetched) with AISC's corner radii. Everything else is a faceted B-rep (`IfcFacetedBrep`) of the welded, closed, outward mesh the 3MF writer is held to. Millimetres and kilograms, declared in the unit assignment. |
| Properties | `Pset_<Class>Common` (`Reference` = part number, `LoadBearing`) and `Anvilate_Screening`: element, validation status, the watermark pairs, part number, material, mass and card digest. |
| Watermark | The export gate's lines go into `FILE_DESCRIPTION`, its status into `FILE_NAME`'s authorization field, and both into the property set. |
| Same parts, same bytes | `GlobalId`s are derived from the part's identity and the header timestamp is fixed. |

Every mapped element's worked example is written in both IFC4 and IFC 4.3, validated by
IfcOpenShell's own checker with the EXPRESS rules on, re-read through IfcOpenShell's
geometry kernel, and its volume held within 1% of the built solid (the 3MF bound) and its
centroid within a thousandth of the part's size. A swept member is also held to the built
member's bounds on every axis, so a section laid in on its side fails even though its volume
and centroid would agree; round sections get 1% of their diameter, because the reader returns
the circle as a polygon. `ifc_part(spec, built, card)` builds the part from a spec: its mesh,
material, mass from the bundled density, the card's review digest, and the swept profile when
there is one. The AISC HSS branch is checked by hand against a fetched table and not in CI,
which never holds that table. A viewer import check is not yet recorded.

## What was confirmed

| Claim | Status | How |
| --- | --- | --- |
| Solid validation properties are volume, total surface area, and centroid; the current document identifier is v4.6 dated 2023-04-21 | **confirmed** | [CAx-IF Geometric and Assembly Validation Properties v4.6](https://www.mbx-if.org/home/wp-content/uploads/2024/05/rec_prac_gvp_v46.pdf), sections 3, 4.4, 4.7, and 4.13 |
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

## An independent reader

The STEP files are written by OCCT, and every check `anvilate build` runs on its own output
reads them back through OCCT, which agrees with itself by construction. So a scheduled CI job,
`step-referee`, reads every audited pattern with STEPcode (the former NIST STEP Class
Library). Its AP242 reader is generated from the schema's EXPRESS long form and shares no code
with the kernel. It is pinned to a commit, and a file passes only when both of its passes
report 0 errors and 0 warnings. What it checks is the Part 21 structure and each instance
against the schema's entity definitions: it does not check CAx-IF Recommended Practice
conformance, which is what NIST's STEP File Analyzer adds and why that remains the named
referee for semantic PMI.

## NIST's test models, read

The same job fetches NIST's AP242 PMI test models (the CTC, FTC and STC cases the CAx-IF
uses), checked against a pinned SHA-256, and holds `anvilate interfaces` to what each reads
as. Its first run found three defects in the reader, all fixed. A segfault inside build123d's
assembly import took the process down, so files are now read by OCCT's plain reader. Six
models were refused because supplemental geometry, such as a datum plane, sits outside the
solid; such faces are now set aside and counted in a warning. And coincident hole records
raised an internal error. Sixteen of the seventeen models now read; the one carrying only
tessellated geometry has no solid and is refused as such.

## What the conformance gate will and will not guarantee

When the AP242 semantic PMI writer lands, CI will run every exported file through an
independent analyzer and regression-test the reader and writer against the free test models.
That buys a real guarantee and a narrow one:

- **It will guarantee** that the file declares the AP242 schema, that its validation
  properties are present and self-consistent, and that its semantic PMI matches the test
  case's expected PMI where a test case exists.
- **It will not guarantee** that a particular commercial CAD system imports it without
  complaint — that is the separate import-regression matrix, and its proprietary tier runs
  on a documented cadence rather than on every commit.
- **It will not make the export a certified translation.** The same rule the scorecard
  follows applies: a check that could not run is reported as not run.
