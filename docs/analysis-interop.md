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

The comparison runs in one canonical unit. A `Quantity` keeps the magnitude the caller
entered and stations are validated only to share component *names*, so a member reporting
500 kN·m at one station and 1000 N·m at another would otherwise hand the 1000 downstream —
a demand 500× too small, on a number nothing further down re-checks.

**An axial load that reverses sign along the member is refused, not reduced.** Bound by
magnitude, a member with +200 kN of tension and −180 kN of compression comes out as pure
tension, routes to AISC §H1.2 and is never checked for buckling — the exact failure the
sign declaration exists to prevent. Which sense governs is the caller's judgement, so the
two cases are bound separately. Bending and shear are screened on magnitude and their sign
carries no capacity consequence, so they reverse freely.

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

## The sectionproperties adapter

`ExternalSectionProperties` is a plain typed record, so the manual path always worked and
still does: filling it in by hand is a handful of keyword arguments, and nothing behaves
differently when the package is absent. `from_sectionproperties(section, name=…,
length_unit=…)` does the same filling in from a meshed section, and the value it adds is
the three things it **refuses** to do.

```python
from anvilate.interop import from_sectionproperties
```

**`length_unit` is required and not defaulted.** `sectionproperties` is unit-agnostic — it
returns bare floats in whatever units the geometry was drawn in, and has no way to tell you
which. A default would be a guess about somebody else's CAD file, and the failure is
silent, and unconservative in the direction that matters: a section drawn in millimetres
and declared as inches has its second moment read as 416,231 times larger (25.4⁴), so the
part screens as immensely stiffer than it is.

**A composite section is refused.** Its meaningful constants are modulus-weighted, and
reading `EI` where `I` belongs is a units error nothing downstream can see, because the
library's screens apply their own material.

**The major axis is the one with the larger second moment, not the one called x.**
`sectionproperties` reports an x and a y; Anvilate screens a major and a minor, and for a
section drawn wider than it is tall those are not the same axis. Mapping `ixx` to major
regardless would build a record `ExternalSectionProperties` refuses — with a message about
swapped axes that points at the record instead of at the mapping that made it. The same
rectangle drawn both ways imports identically.

**The extreme fibre comes from the smaller section modulus.** `get_z()` returns the top and
bottom fibres separately, and for an asymmetric section they differ. The governing fibre is
the far one, `c = I / min(z⁺, z⁻)`; taking the larger modulus would put a smaller `c` into
a bending check and overstate the capacity.

**The shear form factor is left unset, and this is the one to read twice.** `get_as()`
returns the *Timoshenko shear area*, so `A / A_s` is 1.2 for a rectangle.
`shear_form_factor` is the *peak-over-average* ratio, which is 1.5 for a rectangle. Both
read as "the shear factor for this shape"; substituting one for the other understates the
peak shear stress by 20% — 1.2 against a correct 1.5. Unset, the shear screen reports `not_evaluated` — the honest
outcome, and the same rule the manual path already followed.

The torsion constant is imported only when a warping analysis was run; when it was not, it
comes back `None` and the `method` line says so in words rather than leaving the absence to
be inferred from a null.

**The adapter is tested twice.** Once against a stub, which proves the mapping decisions,
and once against the real package, which proves the mapping is of the real API. A stub
written by the same hand as the code it exercises agrees with that code and says nothing
about the package — so the real test runs in CI, by name, on a job that fails if it
skipped.
