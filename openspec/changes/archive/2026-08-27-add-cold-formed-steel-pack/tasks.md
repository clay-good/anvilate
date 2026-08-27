# Tasks: Cold-formed steel pack

## 1. Contracts

- [x] 1.1 Typed elastic-buckling input records — `ElasticBuckling` (local, distortional,
      global_, source). `source` is required and cannot be blank: for a real cold-formed
      shape these come from a finite-strip run, not a closed form, and a capacity resting
      on a buckling load nobody ran is the worst kind of silent green. `distortional` may
      be None for a section with no distortional mode, which REMOVES the mode from the
      governing set rather than treating it as infinitely strong by accident.
- [x] 1.2 Prequalified-limits declaration and warning semantics — `PrequalifiedLimits`
      and `PREQUALIFIED_LIPPED_CHANNEL` (§1.1.1.1), with `check()` returning WHICH ratios
      fall outside. Semantics: outside the calibrated geometry is a THIRD state, neither
      pass nor fail — AISI permits the section with a more conservative resistance factor
      — so `dsm_scorecard` downgrades a PASS to NOT_EVALUATED and names the offending
      dimension. The downgrade only ever removes a green; a failing section stays failed.

## 2. Checks

- [x] 2.1 DSM compression (§1.2.1) — `dsm_compression_strength` returns all three
      strengths and the governing `DSMLimitState`. The anchoring is the part that matters:
      the local curve is anchored on P_ne (local buckling INTERACTS with the global mode)
      and the distortional curve on P_y (it does not), which is the classic DSM
      implementation error and is pinned by a test.
- [x] 2.2 DSM flexure (§1.2.2) — `dsm_flexural_strength`, with all three branches of the
      lateral-torsional curve (elastic below M_cre = 0.56·M_y, M_y above 2.78·M_y, the
      inelastic transition between) and the flexural distortional curve's OWN constants
      (0.673 / 0.22 / 0.5), which are a separate fit from compression's and not one curve
      reused. Branch continuity is asserted at both seams.
- [~] 2.3 Effective-width method (AISI S100 Chapter B / Winter) — the complementary
      slice already shipped in `analysis/cold_formed_steel.py`: `aisi_plate_slenderness`
      (λ = (1.052/√k)·(w/t)·√(f/E)) and `aisi_effective_width` (b = w below λ = 0.673,
      else ρ·w). Yield/modulus caller-supplied; k caller-supplied. This is the EWM path;
      the DSM checks above remain the proposal's main scope.

## 3. Interop

- [x] 3.1 Optional pyCUFSM adapter (buckling values in, provenance tagged), mirroring the
      sectionproperties adapter pattern — `interop.from_pycufsm`. Values in, not the
      package's objects: what an importer has to get right here is arithmetic and
      judgement, not an API surface

## 4. Tests, examples, docs

- [x] 4.1 Worked-example anchors — every DSM branch worked by hand from Appendix 1 and
      pinned in `test_dsm_compression_anchors_to_the_hand_worked_curves` (P_ne 218.6,
      P_nl 151.7, P_nd 150.8 from P_y 245 / P_crl 120 / P_crd 155 / P_cre 900), with the
      hand arithmetic stated in the docstring.
- [x] 4.2 Example: lipped channel — governing limit state shifts with length
      (`examples/lipped_channel_dsm.py`). One section, three unbraced lengths, three
      DIFFERENT governing modes: distortional at 1 m (150.8 kN), local at 3 m (82.5 kN),
      global at 6 m (21.9 kN). A thicker web fixes the first and does nothing for the
      third; bracing fixes the third and does nothing for the first.
- [x] 4.3 Pack documentation — the DSM half of
      [`docs/cold-formed-steel.md`](../../../docs/cold-formed-steel.md): where the
      buckling values come from and why they are not ours to invent, the three-modes /
      three-repairs table, why local strength falls with length when P_crl never moved,
      the prequalified-geometry third state, and the scope (shear, web crippling,
      combined actions and connections are NOT screened).

## Scope as shipped (3.1)

`from_pycufsm` takes the run's **load factors** and a required `reference_load`, not a
pyCUFSM object. That is deliberate: what an importer has to get right about a signature
curve is arithmetic and judgement, and neither lives in the package's API.

**A load factor is not a load.** CUFSM's y-axis is a multiplier on the applied reference
stress distribution. The DSM formulas take ratios, so a factor imported where a load belongs
is wrong by the reference load and dimensionally unremarkable — no dimension check can see
it. Hence `reference_load` is required and accepts a force or a moment.

**Which minimum is which mode is a reading, not a lookup**, and it is the thing the analysis
was run to determine. An importer assuming "first minimum local, second distortional" is
guessing at it. `ModeIdentification` is a declared input; a `SIGNATURE_MINIMUM` reading must
carry the half-wavelength each minimum was read at.

**One physical invariant is checked**: local waves at about a plate width and distortional at
several times that, so a pair in the other order is refused. Swapping them moves strength
between a curve anchored on P_ne and one anchored on P_y, and the nominal changes with
nothing looking wrong. Scoped deliberately — a section that genuinely inverts builds
`ElasticBuckling` directly.

**The anchor is the pack's own hand-worked example, reached the long way round.** The same
P_y 245 / P_crl 120 / P_crd 155 / P_cre 900 that Appendix 1 was worked by hand for arrives
here as factors on a 245 kN reference and reproduces P_nd = 150.8 kN, distortional
governing — a number nothing in the adapter's test file computed.

**Audited immediately after, and the validation sat inside the wrong branch.** A supplied
half-wavelength was only dimension- and finiteness-checked on the `SIGNATURE_MINIMUM` path,
so a cFSM run that supplied one anyway handed a NaN straight to the ordering check — where
`local >= distortional` is False for NaN, and two minima in the wrong order passed as
correctly ordered. A wrong unit reached a pint conversion and raised a dimensionality error
naming millimetres instead of saying what was wrong with the input. Any supplied
half-wavelength is validated now; only the requirement that one be present is
identification-dependent.
