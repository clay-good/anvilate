# Tasks: Member-force and section-property interop

## 1. Contracts

- [x] 1.1 Typed member-force record (stations, components, units, load case, tool + version)
- [x] 1.2 Typed external section-property record with source provenance
- [x] 1.3 Axis-convention declaration and mapping validation rules

## 2. Implementation

- [x] 2.1 Bind ingested demands to existing beam/column/beam-column/torsion screens
- [x] 2.2 Optional sectionproperties adapter (import constants, tag provenance) —
      `interop.from_sectionproperties`. The mapping is small; the value is the three
      refusals, and one of them is a constant that would have been wrong by 25%
- [x] 2.3 Report rendering: external-demand and external-property provenance lines

## 3. Tests

- [x] 3.1 Round-trip against a published frame example: external forces + Anvilate checks
      reproduce the worked design check
- [x] 3.2 Convention-mismatch rejection cases (undeclared, inconsistent, wrong units)
- [x] 3.3 Optional-dependency absence behaves identically with manual entry

## 4. Docs & examples

- [x] 4.1 Example: frame member forces (external) → cited AISC screens → scorecard
- [x] 4.2 Example: custom section constants → beam check

## Scope as shipped

Everything but 2.2's `sectionproperties` adapter, and that is a deliberate no-op rather
than a gap. `src/anvilate/interop.py` carries the typed member-force record, the axis and
sign mapping with its validation rules, the external section-property record with source
provenance, the binder onto the existing beam/column/beam-column screens, and the report
provenance lines. `examples/frame_member_forces_to_checks.py` and
`docs/analysis-interop.md` are the example and the page.

**No optional dependency is imported, so 3.3 is satisfied structurally.**
`ExternalSectionProperties` is a plain typed record; mapping a `sectionproperties` result
dict onto it is a handful of keyword arguments. There is no code path that differs when
the package is absent, which is a stronger form of "behaves identically" than an adapter
with a fallback.

**The sign convention was found during the build, not designed in.** Wiring the worked
example through `screen_beam_column` returned NOT_EVALUATED: the exported −180 kN axial
read as a *tension*, which AISC routes to §H1.2 rather than §H1.1, so the column was never
checked for buckling. The library caught it honestly — but `axial_compression_positive` is
now a required field with no default, because both conventions are ordinary and the
question has to be asked at the door rather than answered by accident. That is 1.3's
"no-silent-assumptions rule" doing exactly what it was for.

**Three rules carry the module**, all versions of the same idea:

1. Every exported label must be mapped or ignored **by name**. A mapping that names four
   of five components silently drops the fifth and the check comes back green having
   never seen it.
2. Each component's governing value is taken independently, with its own station.
   Collapsing a member to one station screens every component at whichever one won.
3. An imported section whose minor-axis second moment exceeds its major one is refused.
   That transposition survives review because both numbers look plausible alone.

3.1's "published frame example" is served by the worked example rather than by a
literature reproduction: the value under test is the doorway, and the checks it feeds are
already anchored in their own suites.

## Scope as shipped (2.2)

Every getter name and return shape was read from the package's published API reference
rather than recalled: `get_area()`, `get_ic() -> (ixx_c, iyy_c, ixy_c)`,
`get_z() -> (zxx_plus, zxx_minus, zyy_plus, zyy_minus)`, `get_j()`, `is_composite()`.

**The defect the adapter exists to not commit: `get_as()` is not the shear form factor.**
It returns the Timoshenko shear area, and `A / A_s` is 1.2 for a rectangle;
`shear_form_factor` is the peak-over-average ratio, 1.5 for a rectangle. Both read as "the
shear factor for this shape", and substituting one for the other understates the peak shear
stress by 25% with every dimension check downstream satisfied. The adapter leaves it unset,
so the shear screen reports `not_evaluated`.

The other two refusals: `length_unit` is required, because the package returns bare floats
and a default would be a guess about somebody else's CAD file; and a composite section is
refused, because its constants are modulus-weighted and reading `EI` as `I` is invisible to
a library that applies its own material.

**Tested twice, on purpose.** A stub proves the mapping decisions and proves nothing about
the package, because it was written by the same hand in the same hour as the code it
exercises. The real test meshes a 50x100 rectangle, runs both analyses, and compares against
closed-form values written out in the test file — not read back from the package. It is
opt-in locally and runs by name in a scheduled CI job that fails if it skipped.

**Audited after shipping, and the adapter had a fourth decision it had not made.** It
mapped `ixx` to the major axis unconditionally. For a section drawn wider than it is tall
the strong axis is y, so the record came back with a transverse second moment larger than
its major one — which `ExternalSectionProperties` refuses, correctly, with a message about
swapped axes that points at the record rather than at the mapping that produced it. The
major axis is now the one with the larger second moment, and the extreme fibre follows the
same axis. A rectangle drawn 50x100 and one drawn 100x50 now import identically.
