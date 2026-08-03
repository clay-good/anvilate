# Tasks: Thermal and isolation/shock screening

## 1. Thermal set

- [x] 1.1 Resistance-network composition — `conduction_thermal_resistance` (L/kA),
      `convection_thermal_resistance` (1/hA), `series_thermal_resistance`,
      `parallel_thermal_resistance`, and `temperature_rise` (Q·R), all in K/W kept in
      temperature differences. Contact resistance is a caller-supplied series R;
      spreading resistance is a follow-up.
- [~] 1.2 Fin efficiency — `fin_efficiency` = tanh(mL)/(mL) with m = √(hP/kA_c); the
      fin-array sizing design inverse is a follow-up.
- [ ] 1.3 Natural/forced convection correlations with enforced validity ranges — the
      coefficient h is caller-supplied for now; bundling correlations (with validity
      ranges → not-evaluated on out-of-range) is a follow-up.
- [~] 1.4 Junction/surface temperature margin — the rise composes into a safety-factor
      scorecard in the example (allowable rise / computed rise); a dedicated margin
      helper is a follow-up.

## 2. Isolation/shock set

- [~] 2.1 Transmissibility screen — the `dynamics` module already ships
      `transmissibility`, `base_excitation_relative_transmissibility`, and the isolator
      static-deflection / natural-frequency inverses (pre-existing).
- [ ] 2.2 Isolator selection margin composing the static-deflection inverse — follow-up.
- [ ] 2.3 Half-sine shock response screen with regime identification — follow-up.

## 3. Tests & examples

- [x] 3.1 Worked-example anchors (Incropera-class thermal) — resistance network and fin
      efficiency anchored against hand calcs.
- [x] 3.2 Example: an enclosure heat sink that passes with a fan but cooks in still air
      (`examples/power_device_heatsink.py`) — the convection to air governs.
- [ ] 3.3 Example: isolator that amplifies at running speed — follow-up.

## 4. Docs

- [x] 4.1 Documentation (`docs/thermal-screening.md`): the resistance-network screen,
      temperature-differences convention, and the caller-supplied-coefficient boundary.

## Follow-ups (recorded, not dropped)

- Spreading and contact-resistance helpers; a fin-array sizing inverse; bundled
  natural/forced convection correlations with enforced validity ranges (out-of-range →
  not evaluated); a junction-temperature margin helper.
- The isolation/shock set beyond the pre-existing transmissibility: an isolator
  selection-margin helper and a half-sine shock-response screen.
