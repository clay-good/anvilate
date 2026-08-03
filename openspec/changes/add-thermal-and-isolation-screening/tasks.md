# Tasks: Thermal and isolation/shock screening

## 1. Thermal set

- [x] 1.1 Resistance-network composition — `conduction_thermal_resistance` (L/kA),
      `convection_thermal_resistance` (1/hA), `circular_source_spreading_resistance`
      (1/4ka, isothermal circular source on a half-space), `series_thermal_resistance`,
      `parallel_thermal_resistance`, and `temperature_rise` (Q·R), all in K/W kept in
      temperature differences. Contact resistance is a caller-supplied series R.
- [x] 1.2 Fin efficiency and fin-array sizing — `fin_efficiency` = tanh(mL)/(mL) with
      m = √(hP/kA_c), and `fin_array_count_for_resistance` (the design inverse:
      N = (1/(hR) − A_base)/(η·A_f), the fin count a target array resistance needs).
- [x] 1.3 Convection correlations with enforced validity ranges — forced:
      `flat_plate_forced_convection_coefficient` (Incropera laminar external flow) returns
      ``None`` above the Re ≈ 5×10⁵ laminar limit rather than extrapolating; natural:
      `vertical_plate_natural_convection_coefficient` (Churchill–Chu, valid all Ra).
      Turbulent forced-flow and other geometries are follow-ups.
- [x] 1.4 Junction/surface temperature margin — `junction_temperature_scorecard` screens
      the rise ΔT = Q·R against an allowable rise budget (the rated junction limit over
      the ambient, a temperature difference), reporting the rise vs allowable; the
      heat-sink example screens through it.

## 2. Isolation/shock set

- [x] 2.1 Transmissibility screen with amplification-region failure — `transmissibility`
      (pre-existing) is now composed into `isolation_scorecard`, which judges TR against
      a target and, below the r = √2 isolation onset, reports that the mount *amplifies*
      rather than a bare number (No-silent-green for the classic tuned-into-resonance
      error).
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
