# Tasks: Typed repair feedback

## 1. Scorecard contract

- [x] 1.1 Extend the scorecard record type with optional repair-hint fields (parameter,
      direction, corrective value, hint provenance) — `RepairHint` (+ `Direction`) on
      `ScorecardEntry.repair_hint`, dropped from any non-failing entry.
- [x] 1.2 Add optional upper margin bound to acceptance criteria; new over-margin warning
      rendering — `from_safety_factor(upper=...)` yields `CheckStatus.OVER_MARGIN`
      (a pass, never blocking), rendered by the report as its band + quantified excess.
- [x] 1.3 Governing-check computation and governing-change diff across revalidations —
      `Scorecard.governing()` (tightest utilization) + `governing_shift(previous)`
      returning a `GoverningChange`.

## 2. Analysis bindings

- [x] 2.1 Bind existing design inverses to their forward checks as hint providers —
      demonstrated end-to-end with `minimum_sheave_diameter_for_bending_stress` in the
      example and a round-trip test; `RepairHint.solved(...)` is the binding pattern any
      pack check applies (isolator deflection, Lewis module, bearing rating, bolt count
      remain to be wired into their own pack entries).
- [ ] 2.2 Monotonicity declarations for hint direction on non-inverse checks —
      `RepairHint.directional(...)` carries a direction without a value; per-check
      monotonicity declarations across the packs are follow-up.

## 3. Tests

- [x] 3.1 Hint correctness: corrective value satisfies the forward check at the required
      margin (round-trip through the wire-rope sheave inverse).
- [x] 3.2 Two-sided band: pass, over-margin warning, and opt-in behavior.
- [x] 3.3 Governing-check identification and change reporting.

## 4. Docs & examples

- [x] 4.1 Example: a failing screen repaired by its inverse in one step
      (`examples/sheave_repair_from_inverse.py`).
- [x] 4.2 Documentation for the over-margin warning and how to declare bands
      (`docs/repair-feedback.md`).

## Deferred (recorded, not silently dropped)

- `agent-repair-loop` planner consumption (spec delta `agent-repair-loop/spec.md`):
  no planner component exists yet, so the deterministic planner that consumes hints
  before any numeric search is future work once that component lands.
- Wiring hints into every pack check that has a paired inverse, plus per-check
  monotonicity declarations (remainder of 2.1 / 2.2).
