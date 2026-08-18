# Interop: analysis in, cited checks out

**Anvilate screens numbers it did not compute, and says so.** A frame analysis in Pynite
or a commercial solver produces member forces; `sectionproperties` produces cross-section
constants. This is the typed doorway that turns them into cited code checks, so the
checking layer sits on top of the ecosystem instead of competing with it.

The doorway is the design. Importing a member force is not a data-format problem, it is a
**convention** problem, and the conventions are where the failures live.

## Four things are declared, never inferred

**Which axis is the strong one.** One tool calls major-axis bending M3, another Mz, a
third My. Nothing in the number says which. Screening a built-up I-section's *minor*-axis
moment as though it were major overstates the flexural capacity by the ratio of the two
section moduli — **4.4×** for the worked example's section. So `AxisMapping` maps each
`ForceComponent` to the label the exporting tool used, and an undeclared import does not
import.

**The sign convention.** `axial_compression_positive` has no default. Most frame solvers
report compression as negative; Anvilate's beam-column screen takes it as positive. Import
a −180 kN column axial unflipped and the screen reads a 180 kN *tension*, routes to AISC
§H1.2 instead of §H1.1, and never checks the column for buckling at all. It does not fail
silently — the screen reports NOT_EVALUATED naming the reason — but the door exists so the
question gets asked before it arises.

**Every exported component.** An export carrying P, M3, M2, V2 and T bound to a mapping
that names four of them silently drops the fifth, and the check comes back green having
never seen the torsion. Every label must be either mapped or listed in `ignored` **by
name**; a label that is neither raises. Dropping a component is an act, not an omission —
and the reason lands in the report.

**Units.** Every component is a dimension-checked `Quantity`, so a kip-inch read as a
kip-foot dies at the door rather than three functions downstream.

## Each component governs at its own station

The axial peak is at the base, the major-axis moment at mid-height, the shear at the base.
`bind_demand` takes the largest magnitude of each component independently and records the
station it came from, because collapsing a member to a single station screens every
component at whichever one happened to win.

## Imported section properties

`ExternalSectionProperties` carries the tool, the version, and **how** — "warping
analysis, 6-node triangular mesh" is different provenance from "handbook table", and a
torsion constant from the first is trustworthy in a way the second is not for an open
section. `cross_section()` converts to the library's `CrossSection`.

Two guards:

- **Swapped axes are refused.** If the imported minor-axis second moment exceeds the
  major one, the axes are transposed. This is the transposition most likely to survive
  review, because both numbers look plausible on their own.
- **No shear form factor is invented.** It defaults to `None`, and the library's shear
  screen then reports NOT_EVALUATED rather than assuming a rectangle's 1.5. An imported
  arbitrary section is precisely where that assumption would be wrong.

## The provenance lines

A check that cites its clause but not the analysis it screened is only half traceable.

```
member forces: C-12 (portal column), load case LRFD 2: 1.2D + 1.6L, from Pynite 1.1.0
  (external analysis — Anvilate screened these numbers, it did not compute them)
  axial: 180 kN governing at 0 m
  major_bending: 148 kN*m governing at 3 m
section properties: BU-350x200 built-up I, from sectionproperties 3.2.1 by warping analysis
  no shear form factor supplied — a transverse-shear screen reports NOT_EVALUATED
not screened: T — torsion is resisted through the slab diaphragm, per the model notes
```

That last line is the one worth keeping. What was *not* screened has to be as visible as
what was.

See [`examples/frame_member_forces_to_checks.py`](../examples/frame_member_forces_to_checks.py).

No optional dependency is imported. `ExternalSectionProperties` is a plain typed record,
so the manual path and the "adapter" path are the same path — mapping a
`sectionproperties` result dict onto it is a handful of keyword arguments, and there is no
behaviour that differs when the package is absent.
