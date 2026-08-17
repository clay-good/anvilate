# Tasks: Codify the analysis-library contract

## 1. Audit & codify

- [~] 1.1 Citation coverage audit across the public surface; backfill gaps — audited all
      1,745 manifest symbols against a curated authority list
      (`docs/api/citation-authorities.txt`): **47% named no source**, in their own
      docstring or their module's. Backfilled the fourteen worst-covered modules by
      giving each module docstring a real `Sources:` attribution (thermal, electrical,
      reactive_circuit, acoustics, sheetmetal, compressible_flow, psychrometrics,
      fluid_statics, engineering_economics, orbital_mechanics, antenna, combustion,
      reliability, dc_dc_converter) and then twenty-six more (section, composite, pump,
      rocket_propulsion, wind_power, machining, quantum, wing_aerodynamics,
      data_converter, fiber_optics, gas_compression, journal_bearing, magnetics,
      real_gas, servo, solar_pv, temperature_sensor, transmission_line, waveguide,
      hydraulic_cylinder, curved_beam, cooling_tower, energy_storage, hydro_power,
      chain, cable, comminution). **47% -> 22.8%.** The remaining 398 are enumerated in
      `docs/api/uncited-symbols.txt` and held by the ratchet gate (2.1).
      **Two false positives were caught and fixed before shipping**, which is the part
      worth keeping: `Turns` (a combustion text) matched "Turns the lumen method
      around..." and `Hazen` matched an analogy, "like Hazen-Williams in hydraulics", in
      a module citing neither. Found by listing, for every authority token, the symbols
      it is the ONLY citation for and reading them — that audit is now written into the
      header of `citation-authorities.txt` with the command to repeat it, and it must be
      run whenever a token is added.
      **Deliberately not backfilled wholesale:** attaching a source to a formula nobody
      re-read would be a citation that means nothing, which is worse than an honest gap.
      Pay the list down module by module as each is next touched.
- [x] 1.2 Enumerate the public API explicitly (single source of truth for the surface:
      `docs/api/analysis-public-surface.txt`, enforced by `tests/test_contract.py`)
- [x] 1.3 Inventory design inverses and their forward-check pairings —
      `docs/api/design-inverses.txt`. **Hand-verified, not inferred:** automatic pairing
      by naming convention resolved only 14 of 156 candidates, and a wrong pairing
      tested automatically would be worse than no test. 15 pairs are recorded AND
      round-tripped in `tests/test_design_inverses.py` — each asserts the inverse's
      answer lands its forward check at *exactly* the required margin, since an
      overshoot is a silent cost and an undershoot a silent failure. The remaining 143
      name-pattern candidates are recorded as not-yet-paired (several are unit
      conversions rather than design inverses). Moving a line from the second group to
      the first means writing its round-trip test, which is the point of the list.

## 2. CI enforcement

- [x] 2.1 Citation-required gate for new public functions —
      `test_every_new_public_check_names_its_source` in `tests/test_contract.py`, held as
      a **ratchet in both directions**: a public symbol naming no source and not recorded
      in `docs/api/uncited-symbols.txt` fails, and a symbol *on* that list which has since
      been cited fails too, so the debt cannot go stale and the count can only fall. A
      citation is any token from `docs/api/citation-authorities.txt` — a curated list, so
      the gate cannot be satisfied by an accidental word. Both directions were verified by
      injecting the failure into a copy: a new uncited public function, and a listed symbol
      given a source. A second test proves the detector itself distinguishes a cited
      docstring from a beautifully-written uncited one.
- [x] 2.2 Worked-example anchor presence check — covered by three gates that together
      say what this task wanted: `test_every_module_has_a_runnable_example` (every module
      is named by an example), `test_every_example_is_executed_by_this_file` (every
      example actually runs in CI), and the new
      `test_every_recorded_inverse_pairing_resolves_and_is_round_tripped` (a recorded
      pairing that no test names is a claim nobody checks). Per-symbol sourced-test
      mapping is deliberately NOT attempted: it would be satisfied by any test mentioning
      the name, which is coverage theatre — the citation ratchet (2.1) and the
      inverse round-trips are the checks that actually bite.
- [x] 2.3 Example-per-module coverage gate (`tests/test_contract.py`; backfilled the six
      uncovered modules: clutch, coupling, impact, journal_bearing, rivet, scotch_yoke)
- [x] 2.4 Public-surface diff check (additions/removals are deliberate; removals require
      deprecation path) — manifest diff in `tests/test_contract.py`

## 3. Docs

- [x] 3.1 Contributor doc: the seven contract rules with examples —
      [`docs/contributing-analysis.md`](../../../docs/contributing-analysis.md). Each
      rule names the gate that enforces it, and says plainly where there is none (rule 2,
      unit-typed inputs, has the least automated cover). Carries the two unit traps this
      library has actually been bitten by (`.to("K")` on a delta, `.to("Hz")` on an
      angular rate) and closes on the rule behind the rules: a check must not be able to
      report a green it did not earn.
- [x] 3.2 User doc: what a citation on a result means and how to verify it —
      [`docs/citations.md`](../../../docs/citations.md). Says what the claim IS (the
      relation is transcribed from the named source, its sharp limits are enforced, your
      inputs were used as given) and, at equal length, what it is NOT (not a code stamp,
      not a certification of the inputs, not a promise that every limit state was
      checked, and not full coverage — the 22.8% debt is named on the page). Four
      verification steps, starting with re-doing the substituted line's arithmetic.

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
  one. **Superseded note:** this decision previously cited
  `drag.stokes_settling_velocity` as the standing precedent for leaving a prose-only
  limit. It is no longer — that guard was added on 2026-08-17, and the two cases are not
  alike. Stokes' seam is the *definition* of creeping flow (a single sharp Re ≈ 1, not a
  transition band that moves with roughness), the Reynolds number is computable from the
  function's own arguments, and past it the answer is 5.8x unconservative. The rule that
  separates them: **enforce a limit that is sharp and whose error is unconservative;
  leave one that is fuzzy, and surface a ratio where the error runs conservative** (see
  `PlateBendingResult.small_deflection_ratio`). **Open follow-up:** if
  this is revisited, the shape to add is a public regime predicate (a named transition
  constant plus an `is_laminar(...)`-style check) the caller consults, not a raise inside
  the correlations.
- **The `float("inf")` zero-demand convention was split three ways** across analysis,
  packs, and `loads.py`. Resolved in favour of `NOT_EVALUATED` everywhere a *verdict* is
  produced; quantity-returning functions (`miner_spectrum_repeats_to_failure`) keep `inf`
  as a documented result. `isolation_scorecard`'s zero branch was left alone: it is
  unreachable (transmissibility overflows before it underflows) and would be an evaluated
  limiting result, not an absent demand.
- **The zero-demand `else None` idiom is unpinned at twelve more sites.** A mutation pass
  found `else None` -> `else 1.0` — "nothing to evaluate" silently becoming "exactly at
  the limit, PASS" — surviving in the pump cavitation margin, the masonry combined-unity
  check, the ASHRAE 62.1 outdoor-air check and the hearing-conservation dose. All four now
  have tests in `tests/test_no_silent_green.py`. **Not yet run individually:**
  `electrical.py:88,95`, `geotechnical.py:144,392`, `lighting.py:75,87`,
  `hydraulics.py:83,153`, `ventilation.py:81`, and `structural.py:993,1531,1885,1983,1984`.
  **Swept and closed.** All fourteen sites were run individually. Nine are reachable and
  every one is now pinned in `tests/test_no_silent_green.py`, each verified by re-applying
  its mutation and watching the new test fail. **Five are unreachable by construction** —
  `electrical.py:88,95`, `hydraulics.py:83,153`, `lighting.py:87` sit downstream of
  validators that already reject the only inputs that could reach them
  (`conductor_resistance` refuses a zero length, `pump_hydraulic_power` and
  `reynolds_number` a zero flow, a luminaire count must be positive). Mutating those is
  *equivalent*, not a silent green: they are defensive, not load-bearing. Recorded so a
  later audit does not re-file them as findings and a later refactor does not delete them
  as dead. This is the library's signature invariant and line coverage cannot see it —
  only mutation can.
- **Cross-module disagreements found 2026-08-17, recorded and NOT yet fixed.** Each was
  confirmed by execution; the beam-column one from the same sweep was fixed immediately
  because it was unconservative and flipped verdicts.
  - `acoustics` defaults the directivity factor Q two ways for the same free-field term:
    `sound_pressure_from_power_level` uses 2.0, `room_sound_pressure_level` and
    `critical_distance` use 1.0. The first is exactly the R->inf limit of the second, so a
    caller letting both default gets 80.998 dB and 77.987 dB for the same source — exactly
    10*log10(2) apart. 3 dB is not cosmetic when the docstring says to feed the result to
    the noise-exposure screen. The two docstrings also disagree on whether Q = 4 is a
    corner or a wall. Needs one default and one table across the three functions.
  - `packs/hydraulics.screen_pump_duty` screens NPSHa/NPSHr >= 1.1 and names the entry
    "NPSH margin", while `analysis/pump.npsh_margin` returns NPSHa - NPSHr in metres and
    says 0.5-1 m is usual. The pack never imports it. They disagree in both directions and
    unboundedly: the pack FAILs a 1.00 m cushion at 21/20 m and PASSes a 0.05 m one at
    0.55/0.5 m. Pump practice uses both a ratio floor AND an absolute-head floor; a single
    ratio silently greens the 50 mm case.
  - `beam.fixed_pinned_uniform_load` uses the rounded L^4/185 table coefficient where the
    partial-UDL and centre-patch forms (which ARE the same beam at loaded_length = L)
    root-find the true peak: 0.43784 mm vs 0.43871 mm, 0.198% apart with the special case
    LOW. The exact coefficient is 0.0054158; 1/185 = 0.0054054. Only outlier among 22
    degenerate-limit reductions swept.
  - `packs/structural` uses 0.577 for the shear-yield fraction where `analysis/stress`
    uses exact 1/sqrt(3), so two entries of ONE scorecard screening the same state at
    zero tension return 1.5117909 and 1.5127087 (0.061% apart). Tiny, and unreconcilable
    by a reader.
  - `psychrometrics.wet_bulb_temperature` guards T_wb <= T_db and not T_wb >= T_dp; 67 of
    a swept grid return a wet bulb below the module's own exact dew point, worst 0.198 K.
    Inside the declared +/-0.3 K fit accuracy, so the reportable part is the asymmetry: the
    module decided impossible answers should raise and guarded only one bound.
- **Mutation pass 2026-08-17 (88 mutations, 45 killed, 40 real survivors).** The eight
  highest-value survivors are now pinned in `tests/test_no_silent_green.py` and
  `tests/test_contract.py`, each verified by re-applying its mutation. **Still open, and
  recorded rather than pretended away:** 102 of the 108 pipe-schedule rows are pinned
  structurally (one OD per NPS, wall monotonic in schedule, wall < OD/2) plus about ten
  specific values, so an individual wall in the middle of the table can still be
  perturbed with the suite green. Value-pinning all 108 would be a transcription of the
  transcription and would catch nothing a structural check does not; the honest mitigation
  is that the structural invariants catch systematic slips and the divergence points are
  now pinned explicitly. Also open and low-value: the three `_engineering_order` guard
  clauses (label-only, no number changes) and four assertions over currently-empty sets.


## Cross-module disagreements recorded 2026-08-17 (second audit wave)

Reproduced by execution, recorded rather than rushed because the fix is a judgment call
about which convention the library adopts, not a bug fix.

- **6. The structural pack's column curve is not the AISC curve it cites.**
  `packs/structural.screen_column_member` and `screen_beam_column` compute buckling by
  Euler/Johnson and stamp the entry `reference = "AISC 360-16 Ch. E"`, while
  `analysis/column.aisc_flexural_buckling_stress` — the real §E3 curve — ships in the
  same library. For a 50 x 50 mm A36 section at K = 1, pack/AISC = 1.0937 at L = 1000 mm
  and 1.1403 at L >= 2000 mm: **9-14% unconservative**. On the contract suite's own
  fixture (`_structural_entries`, "post", L = 3000 mm, P = 40 kN) the pack reports
  SF 2.856 where §E3 gives 2.504, so at `required_safety_factor = 2.6` the pack **passes**
  and AISC **fails** — a flipped verdict, not a rounding difference. The same P_c feeds
  the §H1.1 axial term in `screen_beam_column`.
  The choice: adopt §E3 in the pack (and re-baseline every column and beam-column number
  in the suite and the examples), or keep Euler/Johnson and stop citing AISC for it. The
  citation is the part that is indefensible either way.
