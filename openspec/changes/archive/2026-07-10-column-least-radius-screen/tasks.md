# Tasks: Column screens buckle about the least radius of gyration

## 1. Implementation

- [x] 1.1 `screen_column_member`: slenderness from `least_radius_of_gyration`
- [x] 1.2 `screen_beam_column`: axial-capacity slenderness from
      `least_radius_of_gyration` (flexural term unchanged)
- [x] 1.3 Update `ColumnMember`/`BeamColumnMember` docstrings — drop the
      "pass the least (weak-axis) value" caveat, state the automatic guard
      and the hand-built-section fallback

## 2. Tests

- [x] 2.1 A strong-axis rectangular column screens with the weak-axis r
      (lower SF than the same section screened pre-change)
- [x] 2.2 A weak-axis-declared section is numerically unchanged
- [x] 2.3 A hand-built `CrossSection` (no `second_moment_transverse`) keeps
      today's bending-axis behavior exactly
- [x] 2.4 `screen_beam_column`: axial term uses least-r, flexural term still
      the declared axis

## 3. Docs

- [x] 3.1 Note in `examples/flat_bar_strut_weak_axis.py` that the pack now
      screens the least axis automatically (the example still teaches why)
- [x] 3.2 Archive this change into `openspec/specs/discipline-packs/spec.md`
