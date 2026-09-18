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

[`examples/lens_housing_athermal.py`](../examples/lens_housing_athermal.py) screens one f/4
singlet across 40 K in three housings. Aluminium leaves the image 76.4 µm out of a ±17.6 µm
depth of focus. Titanium misses by 0.8 µm. Invar holds it.

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
system, field-dependent focus, or wavefront error. A design whose margin against the depth
of focus is small is the one to take to optical design software; the screen says which one
that is.

## Status

This is the depth of focus and the athermal focus screen
(`openspec/changes/add-optomechanical-module`, 2.1 and 2.2, and this scope page). The rest of
that change is not built yet: angular units, optical material records, the dynamic,
interface and sealing screens, and its budgets.
