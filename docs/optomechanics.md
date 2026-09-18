# Opto-mechanics

A lens and its housing both move with temperature, and not together. This page covers what
`anvilate.analysis.optomechanics` screens today, what it refuses, and why it is not a ray
tracer.

## What it screens

| Function | What it answers |
| --- | --- |
| `depth_of_focus(wavelength, f_number)` | How far from best focus a diffraction-limited image stays sharp: ±2·λ·N², by the Rayleigh quarter-wave criterion. f/4 at 550 nm is ±17.6 µm. |
| `thermal_focal_shift(focal_length, refractive_index, dn_dt, glass_cte, temperature_change)` | How far a thin lens's focal length moves: Δf = f·(α_g − (dn/dT)/(n − 1))·ΔT, the glass thermal constant of Jamieson (1981). The glass grows and lengthens f; a rising index shortens it. |
| `athermal_defocus(focal_shift, housing_cte, housing_length, temperature_change)` | Where the image lands relative to the detector the housing carries: δ = Δf − α_h·L·ΔT. Zero is the athermal condition. |
| `athermal_focus_scorecard(...)` | PASS when \|δ\| stays within the depth of focus, FAIL beyond it, with the comparison and the worked line δ = Δf − α_h·L·ΔT on the entry. |
| `miles_random_vibration_grms(natural_frequency, quality_factor, input_asd)` | A single mode's RMS response to flat random input, G_rms = √(π/2·f_n·Q·ASD) (Miles, 1954). Three times it is the 3σ load a mount is sized to. Q is required: the answer goes as √Q, and a default Q is an assumption about somebody else's mount. The ASD is written per hertz (`0.04 1/Hz`), because in a unit string `g` is the gram. |
| `retention_preload(mass, acceleration)` | The axial preload that keeps an element seated against an acceleration in g: P = m·a·g₀. Less, and the lens lifts, rattles and reseats somewhere else. |
| `stress_birefringence_retardance(stress_optic_coefficient, stress, path_length)` | The retardance stress puts into glass, K·σ·t, in nanometres. N-BK7's 2.77×10⁻⁶ mm²/N at 1 MPa over 10 mm is 27.7 nm. |
| `marechal_strehl_ratio(rms_wavefront_error, wavelength)` | The Maréchal approximation S ≈ exp(−(2πσ/λ)²). λ/14 gives S ≈ 0.8, the diffraction limit. |
| `internal_condensation_scorecard(name, coldest_surface_temperature, internal_dew_point or fill_temperature and fill_relative_humidity)` | Whether a sealed housing fogs at its cold soak: the internal dew point against the coldest internal surface. The dew point is the declared purge specification, or the one a fill condition implies through the Magnus relations — a fill at 25 °C and 50% relative humidity condenses below 13.9 °C. With neither declared the screen is not evaluated: an unstated purge is not a dry one. |
| `mount_decenter(mass, acceleration, radial_stiffness)` | How far an element moves sideways in its mount under a lateral acceleration in g: m·a·g₀/k. A 50 g lens at 10 g on a 5 N/µm mount moves 0.98 µm. |
| `decenter_line_of_sight(decenter, focal_length)` | The line-of-sight shift a lens decenter causes, Δ/f: that 0.98 µm behind a 100 mm lens is 9.8 µrad. |
| `mirror_tilt_line_of_sight(tilt)` | A mirror turned through an angle turns the beam through twice it. The tilt must be in an angle unit (rad, mrad, µrad, deg, arcmin, arcsec), because the unit layer would otherwise take a strain in mm/m for radians. |
| `ThermalCondition(kind, temperature_change, dwell, time_constant)` and `.qualify(entry)` | What a thermal screen is valid for. The kind — `soak`, `gradient` or `transient` — has no default. `qualify` replaces a soak screen's verdict with not evaluated under a gradient. Under a transient whose dwell is shorter than three time constants, the verdict stands and says it is optimistic, with both durations: a 30-minute dwell against a 20-minute time constant reaches 78% of the change. |
| `wavefront_budget_scorecard(name, contributors, wavelength, strehl_threshold)` | Named RMS contributors combined by root sum of squares and judged against the error at which a **declared** Strehl threshold is met. An empty budget is refused, because a total of nothing would pass. |

[`examples/lens_housing_athermal.py`](../examples/lens_housing_athermal.py) screens one f/4
singlet across 40 K in three housings. Aluminium leaves the image 76.4 µm out of a ±17.6 µm
depth of focus. Titanium misses by 0.8 µm. Invar holds it.

[`examples/lens_focus_budget.py`](../examples/lens_focus_budget.py) is the defect class the
budgets exist for. Three focus screens each pass, and the depth of focus declared as a
[budget](performance-budgets.md) with each term bound to its check fails. Worst-case, they
spend 25.4 µm of ±17.6 µm.

## What it refuses

| Refused | Why |
| --- | --- |
| A refractive index of 1 or less | A lens in air with n ≤ 1 does not focus, and (n − 1) divides. |
| A glass property with no unit, or the wrong one | dn/dT and a CTE are per-kelvin quantities; a bare number is refused before any arithmetic. |
| A non-finite f-number, wavelength or length | NaN walks past a `<= 0` guard, so every input is checked for finiteness first. |

Glass data is never bundled. dn/dT depends on the wavelength, on the temperature range and
on whether it is quoted relative to air or vacuum. A catalogue value used at the wrong one
is a confident wrong answer, so the caller states the value and owns where it came from.

## Why it is not a ray tracer

These are thin-lens, paraxial relations: one element, one focal length, one image plane. They
answer the screening question — does this housing hold focus over this range, to within the
depth of focus — early, before a prescription exists. They do not model a multi-element
system or field-dependent focus, and the wavefront budget combines errors the caller states
rather than computing any from a prescription. A design whose margin is small is the one to
take to optical design software; the screen says which one that is.

## Status

This is the depth of focus, the athermal focus screen, the random-vibration and retention
screens, stress birefringence, the wavefront budget and internal condensation
(`openspec/changes/add-optomechanical-module`, 2.1, 2.2, 3.3, 3.4, 3.5, 4.3, 4.4, 5.1, 10.3 and
this scope page). Not built yet: angular units, optical material records, preload change with
temperature, the shock screen, contact stress, the gland screen at temperature extremes, and
the line-of-sight budget. The focus budget is a worked example rather than a packaged screen.
