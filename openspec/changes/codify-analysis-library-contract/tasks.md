# Tasks: Codify the analysis-library contract

## 1. Audit & codify

- [ ] 1.1 Citation coverage audit across the ~495-symbol public surface; backfill gaps
- [x] 1.2 Enumerate the public API explicitly (single source of truth for the surface:
      `docs/api/analysis-public-surface.txt`, enforced by `tests/test_contract.py`)
- [ ] 1.3 Inventory design inverses and their forward-check pairings

## 2. CI enforcement

- [ ] 2.1 Citation-required gate for new public functions
- [ ] 2.2 Worked-example anchor presence check (every public function maps to a sourced test)
- [x] 2.3 Example-per-module coverage gate (`tests/test_contract.py`; backfilled the six
      uncovered modules: clutch, coupling, impact, journal_bearing, rivet, scotch_yoke)
- [x] 2.4 Public-surface diff check (additions/removals are deliberate; removals require
      deprecation path) — manifest diff in `tests/test_contract.py`

## 3. Docs

- [ ] 3.1 Contributor doc: the seven contract rules with examples
- [ ] 3.2 User doc: what a citation on a result means and how to verify it

## Recorded decisions (from the 2026-08-17 five-lens audit)

- **`boundary_layer.py` states ten Reynolds validity ranges and enforces none.**
  Confirmed numerically: `laminar_plate_drag_coefficient` at Re_L = 1e7 returns 0.000420
  where the turbulent form gives 0.002946 (7.0x low); `laminar_boundary_layer_thickness`
  returns 0.0237 m against 0.221 m (9.3x thin); `turbulent_plate_drag_coefficient` at
  Re = 1 returns 0.074 against a laminar 1.328 (18x low). **Decided: leave the prose
  limit, do not raise.** The seam is explicitly approximate in every docstring ("below
  ~5e5") because transition runs 3e5–1e6 on surface roughness and free-stream turbulence;
  a hard refusal at a fuzzy threshold would reject legitimate near-transition use, and it
  would break `test_turbulent_boundary_layer_...`, which deliberately evaluates both
  regimes at the same station (Re_x = 2.67e6) to show the turbulent layer is the thicker
  one. `drag.stokes_settling_velocity` is the standing precedent: prose-only limit,
  accepted deliberately, with a test that names the missing guard. **Open follow-up:** if
  this is revisited, the shape to add is a public regime predicate (a named transition
  constant plus an `is_laminar(...)`-style check) the caller consults, not a raise inside
  the correlations.
- **The `float("inf")` zero-demand convention was split three ways** across analysis,
  packs, and `loads.py`. Resolved in favour of `NOT_EVALUATED` everywhere a *verdict* is
  produced; quantity-returning functions (`miner_spectrum_repeats_to_failure`) keep `inf`
  as a documented result. `isolation_scorecard`'s zero branch was left alone: it is
  unreachable (transmissibility overflows before it underflows) and would be an evaluated
  limiting result, not an absent demand.
