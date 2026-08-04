# Tasks: Cold-formed steel pack

## 1. Contracts

- [ ] 1.1 Typed elastic-buckling input records (local/distortional/global, provenance)
- [ ] 1.2 Prequalified-limits declaration and warning semantics

## 2. Checks

- [ ] 2.1 DSM compression: local, distortional, global strengths and governing state
- [ ] 2.2 DSM flexure: local, distortional, lateral-torsional strengths and governing
      state
- [~] 2.3 Effective-width method (AISI S100 Chapter B / Winter) — the complementary
      slice already shipped in `analysis/cold_formed_steel.py`: `aisi_plate_slenderness`
      (λ = (1.052/√k)·(w/t)·√(f/E)) and `aisi_effective_width` (b = w below λ = 0.673,
      else ρ·w). Yield/modulus caller-supplied; k caller-supplied. This is the EWM path;
      the DSM checks above remain the proposal's main scope.

## 3. Interop

- [ ] 3.1 Optional pyCUFSM adapter (buckling values in, provenance tagged), mirroring the
      sectionproperties adapter pattern

## 4. Tests, examples, docs

- [ ] 4.1 Worked-example anchors from published DSM design examples
- [ ] 4.2 Example: lipped channel — governing limit state shifts with length
- [ ] 4.3 Pack documentation: DSM scope, where buckling values come from, screening
      disclaimer
