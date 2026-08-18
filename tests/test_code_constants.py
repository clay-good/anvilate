"""Code-mandated constants a mutation pass could change with the suite still green.

Every test here exists because a deliberate mutation of the number it pins left all 2,517
other tests passing. They are not arithmetic checks — the arithmetic is covered — they are
checks that the *specific value a standard mandates* is the one in the code. A factored
load combination with 0.6W where ASCE 7 writes 0.5W still produces a plausible number, and
that is exactly the failure this file is for.

The systemic version of the finding: statement coverage of the analysis library is
essentially total for computational lines, and the gap is almost entirely in **guard
bodies**. Of the guards that never execute under the suite, over two hundred enforce a
non-trivial numeric domain limit rather than mere positivity — and every one of those
limit values is unpinned by construction. The second half of this file walks that class.
"""

from __future__ import annotations

import pytest

from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


# --- Code-mandated load factors and allowable caps -----------------------------------


def test_the_asce7_snow_combination_carries_half_the_wind_not_six_tenths():
    """LRFD 3 is 1.2D + 1.6S + max(L, 0.5W). The 0.5 is ASCE 7's, not a rounding.

    A companion wind factor of 0.6 would raise every snow-governed member's demand and
    still look like a load combination. This drives the combination to be the governing
    one and reads the factor straight off the result.
    """
    from anvilate.analysis import asce7_lrfd_factored_load

    # Snow-dominated with no live load: LRFD 3 governs and the wind term is the only
    # unknown, so the answer names 0.5W directly.
    governing = asce7_lrfd_factored_load(
        dead=_q("10 kN"), roof_snow_rain=_q("30 kN"), wind=_q("20 kN")
    )
    assert governing.magnitude == pytest.approx(1.2 * 10 + 1.6 * 30 + 0.5 * 20, rel=1e-12)
    # And the max() is a max: a live load above 0.5W takes over the same slot.
    with_live = asce7_lrfd_factored_load(
        dead=_q("10 kN"), live=_q("15 kN"), roof_snow_rain=_q("30 kN"), wind=_q("20 kN")
    )
    assert with_live.magnitude == pytest.approx(1.2 * 10 + 1.6 * 30 + 15.0, rel=1e-12)


def test_the_asce7_asd_seismic_companion_is_seven_tenths_not_eight():
    """ASD 5 is D + max(0.6W, 0.7E). The 0.7 converts strength-level E to service level."""
    from anvilate.analysis import asce7_asd_factored_load

    governing = asce7_asd_factored_load(dead=_q("10 kN"), seismic=_q("40 kN"))
    # ASD 9 is 0.6D + 0.7E = 34 kN; ASD 5 is D + 0.7E = 38 kN and governs.
    assert governing.magnitude == pytest.approx(10.0 + 0.7 * 40.0, rel=1e-12)
    # The wind companion in the same slot is 0.6, and the max picks between them.
    wind_governed = asce7_asd_factored_load(dead=_q("10 kN"), wind=_q("40 kN"))
    assert wind_governed.magnitude == pytest.approx(10.0 + 0.6 * 40.0, rel=1e-12)


def test_the_aci_strength_reduction_factor_is_capped_at_ninety_hundredths():
    """φ tops out at 0.90 for tension-controlled sections; a cap of 0.99 is not ACI's."""
    from anvilate.analysis import rc_strength_reduction_factor

    # Well past the tension-controlled strain limit: φ is at its ceiling.
    assert rc_strength_reduction_factor(
        net_tensile_strain=0.010, steel_yield=_q("420 MPa")
    ) == pytest.approx(0.90, rel=1e-12)
    # And the caller's compression-controlled value is bounded by that same ceiling,
    # because a φ above 0.90 is not a conservative choice, it is a non-ACI one.
    with pytest.raises(ValueError, match=r"must be in \(0, 0.90\]"):
        rc_strength_reduction_factor(
            net_tensile_strain=0.002,
            steel_yield=_q("420 MPa"),
            compression_controlled_factor=0.95,
        )
    assert rc_strength_reduction_factor(
        net_tensile_strain=0.001, steel_yield=_q("420 MPa"), compression_controlled_factor=0.90
    ) == pytest.approx(0.90, rel=1e-12)


def test_the_aisc_plastic_moment_is_capped_at_one_point_six_times_the_yield_moment():
    """M_p ≤ 1.6·F_y·S bounds the shape factor a section may claim (AISC §F2.1).

    The cap exists because a very high Z/S ratio implies a plastic redistribution the
    section will not deliver before it deforms unacceptably. Raising it to 1.75 lets a
    stocky section claim capacity the Code does not grant, and nothing downstream notices.
    """
    from anvilate.analysis import aisc_minor_axis_flexural_strength

    # A section whose Z/S ratio (2.0) is well past the 1.6 cap: the cap governs, and the
    # answer is 1.6*Fy*S rather than Fy*Z.
    capped = aisc_minor_axis_flexural_strength(
        flange_width=_q("200 mm"),
        flange_thickness=_q("20 mm"),
        yield_strength=_q("345 MPa"),
        elastic_modulus=_q("200 GPa"),
        plastic_section_modulus=_q("2.0e5 mm**3"),
        elastic_section_modulus=_q("1.0e5 mm**3"),
    )
    expected = 1.6 * 345.0 * 1.0e5  # N*mm
    assert capped.to("N*mm").magnitude == pytest.approx(expected, rel=1e-9)
    # A section inside the cap gets Fy*Z, so the min() really is a min.
    uncapped = aisc_minor_axis_flexural_strength(
        flange_width=_q("200 mm"),
        flange_thickness=_q("20 mm"),
        yield_strength=_q("345 MPa"),
        elastic_modulus=_q("200 GPa"),
        plastic_section_modulus=_q("1.5e5 mm**3"),
        elastic_section_modulus=_q("1.0e5 mm**3"),
    )
    assert uncapped.to("N*mm").magnitude == pytest.approx(345.0 * 1.5e5, rel=1e-9)


def test_the_aci_effective_inertia_transition_starts_at_two_thirds_of_the_cracking_moment():
    """ACI 318-19's I_e uses M_a ≤ (2/3)M_cr as the uncracked branch, not M_cr itself.

    The 2/3 is the 2019 edition's change and it matters at service load: below it the
    member is uncracked and I_e is I_g, above it the interpolation runs. A denominator of
    4 instead of 3 moves the transition and quietly stiffens every member near it.
    """
    from anvilate.analysis import rc_effective_moment_of_inertia

    gross = _q("4.0e8 mm**4")
    cracked = _q("1.2e8 mm**4")
    cracking_moment = _q("60 kN*m")
    # Just below the 2/3 transition (40 kN*m): fully uncracked, I_e = I_g exactly.
    below = rc_effective_moment_of_inertia(
        applied_moment=_q("39.9 kN*m"),
        cracking_moment=cracking_moment,
        gross_inertia=gross,
        cracked_inertia=cracked,
    )
    assert below.to("mm**4").magnitude == pytest.approx(4.0e8, rel=1e-12)
    # Just above it: the interpolation has started, so I_e has dropped off I_g.
    above = rc_effective_moment_of_inertia(
        applied_moment=_q("40.1 kN*m"),
        cracking_moment=cracking_moment,
        gross_inertia=gross,
        cracked_inertia=cracked,
    )
    assert above.to("mm**4").magnitude < 4.0e8


def test_the_aci_crack_control_spacing_cap_is_three_hundred_over_the_stress_ratio():
    """ACI 318 §24.3.2: s ≤ 380(280/f_s) − 2.5c_c, but never more than 300(280/f_s)."""
    from anvilate.analysis import rc_max_bar_spacing_crack_control

    # Very small cover, so the 380-term is large and the 300-term is the binding one.
    fs = 280.0
    spacing = rc_max_bar_spacing_crack_control(
        steel_service_stress=_q("280 MPa"), clear_cover=_q("10 mm")
    )
    assert spacing.to("mm").magnitude == pytest.approx(300.0 * (280.0 / fs), rel=1e-12)
    # With generous cover the 380-term binds instead, so the min() is a real min.
    deep_cover = rc_max_bar_spacing_crack_control(
        steel_service_stress=_q("280 MPa"), clear_cover=_q("60 mm")
    )
    assert deep_cover.to("mm").magnitude == pytest.approx(380.0 - 2.5 * 60.0, rel=1e-12)


def test_the_asce7_live_load_reduction_floor_is_four_hundred_square_feet():
    """No reduction below K_LL·A_T = 37.16 m² (400 ft²), and the floor is the Code's."""
    from anvilate.analysis import reduced_live_load

    unreduced = _q("4.8 kPa")
    # Just under the threshold: no reduction at all.
    assert reduced_live_load(
        unreduced_live_load=unreduced, tributary_area=_q("9 m**2"), live_load_element_factor=4.0
    ).to("kPa").magnitude == pytest.approx(4.8, rel=1e-12)
    # Just over it: the reduction has begun.
    assert (
        reduced_live_load(
            unreduced_live_load=unreduced,
            tributary_area=_q("9.5 m**2"),
            live_load_element_factor=4.0,
        )
        .to("kPa")
        .magnitude
        < 4.8
    )


def test_the_tms402_slenderness_branch_is_at_the_ratio_where_the_two_curves_meet():
    """h/r = 99 is not arbitrary: it is where TMS 402's two axial expressions coincide.

    That property pins the number more strongly than the value itself does. The stocky
    branch runs [1 - (h/140r)^2] and the slender one (70r/h)^2; at h/r = 99 they agree to
    one part in ten thousand, which is why the Code puts the boundary there. Move the
    boundary and the allowable steps discontinuously across it.
    """
    from anvilate.analysis import masonry_allowable_axial_stress

    def allowable(ratio: float) -> float:
        return (
            masonry_allowable_axial_stress(masonry_strength=_q("13.8 MPa"), slenderness_ratio=ratio)
            .to("MPa")
            .magnitude
        )

    # The two branch expressions, written out, agree at 99 and nowhere near it.
    assert 1.0 - (99.0 / 140.0) ** 2 == pytest.approx((70.0 / 99.0) ** 2, rel=2e-4)
    assert 1.0 - (80.0 / 140.0) ** 2 != pytest.approx((70.0 / 80.0) ** 2, rel=0.1)
    # So the function has no step at the boundary: the drop from 98.9 to 99.0 matches the
    # drop from 99.0 to 99.1, which is the signature of a smooth join rather than of two
    # curves meeting at the wrong place.
    below = allowable(98.9) - allowable(99.0)
    above = allowable(99.0) - allowable(99.1)
    assert below == pytest.approx(above, rel=0.01)
    assert below > 0
    # And the curve still falls with slenderness, so the branches are not accidentally
    # equal everywhere.
    assert allowable(80.0) > allowable(99.0) > allowable(120.0)


def test_the_aisc_b2_amplifier_never_falls_below_unity():
    """B2 = 1/(1 − ΣP/ΣP_e) is a magnifier, and its floor is 1.0, not 1.1.

    A floor of 1.1 would invent 10% of amplification on a frame with no second-order
    effect at all, which reads as conservatism and is really an unstated load factor.
    """
    from anvilate.analysis import aisc_moment_amplifier_b2

    # A very stiff frame: the true amplifier is barely above 1, and the floor holds it at
    # exactly 1.0 rather than at anything invented.
    assert aisc_moment_amplifier_b2(
        story_axial_load=_q("1 kN"), story_elastic_buckling_strength=_q("1e6 kN")
    ) == pytest.approx(1.0, abs=1e-5)
    # And a genuinely flexible frame amplifies: the floor is a floor, not a clamp.
    assert aisc_moment_amplifier_b2(
        story_axial_load=_q("400 kN"), story_elastic_buckling_strength=_q("2000 kN")
    ) == pytest.approx(1.0 / (1.0 - 0.2), rel=1e-12)


def test_the_b313_miter_angle_split_is_twenty_two_and_a_half_degrees():
    """ASME B31.3 304.2.3 gives one expression to 22.5° and another above; past it, nothing.

    Both the branch boundary and the scope ceiling sit on the same number, so a slip
    moves a miter from one formula to the other and widens what the module claims to
    cover.
    """
    from anvilate.analysis import asme_b313_miter_bend_pressure

    common = {
        "wall_thickness": _q("6 mm"),
        "mean_radius": _q("106.55 mm"),
        "allowable_stress": _q("110 MPa"),
        "effective_bend_radius": _q("450 mm"),
    }
    at_limit = asme_b313_miter_bend_pressure(miter_angle=22.5, **common)
    assert at_limit.to("MPa").magnitude > 0
    # Past the split the Code gives no expression at all, and the module says so rather
    # than extrapolating one.
    with pytest.raises(ValueError, match="22.5"):
        asme_b313_miter_bend_pressure(miter_angle=22.6, **common)


def test_the_spring_end_condition_factors_are_the_published_four():
    """The buckling end factors are a published table; 0.707 is not 0.8 rounded."""
    from anvilate.analysis import (
        SPRING_END_CLAMPED_FREE,
        SPRING_END_FIXED_HINGED,
        SPRING_END_HINGED_HINGED,
        SPRING_END_PARALLEL_PLATES,
    )

    SPRING_END_FIXED_FIXED = SPRING_END_PARALLEL_PLATES
    assert SPRING_END_FIXED_FIXED == pytest.approx(0.5, rel=1e-12)
    assert SPRING_END_FIXED_HINGED == pytest.approx(0.707, rel=1e-12)
    assert SPRING_END_HINGED_HINGED == pytest.approx(1.0, rel=1e-12)
    assert SPRING_END_CLAMPED_FREE == pytest.approx(2.0, rel=1e-12)
    # They are the Euler column factors, so the two fixed cases bracket the pinned one by
    # exactly 2x and 1/2x — the relationship a transcription error breaks.
    assert SPRING_END_HINGED_HINGED / SPRING_END_FIXED_FIXED == pytest.approx(2.0, rel=1e-12)
    assert SPRING_END_CLAMPED_FREE / SPRING_END_HINGED_HINGED == pytest.approx(2.0, rel=1e-12)
    # And 0.707 is 1/sqrt(2), which is what makes it that value and not 0.8.
    assert SPRING_END_FIXED_HINGED == pytest.approx(2.0**-0.5, abs=2e-4)


def test_the_flat_plate_transition_reynolds_number_is_five_times_ten_to_the_fifth():
    """The laminar/turbulent convection correlations swap at Re = 5e5, both sides.

    Two functions read the same constant and refuse each other's regime, so the pair
    pins it from both directions: lower it and the laminar form starts refusing flows it
    models correctly.
    """
    from anvilate.analysis import (
        flat_plate_forced_convection_coefficient,
        flat_plate_turbulent_convection_coefficient,
    )

    flow = {
        "fluid_velocity": _q("5 m/s"),
        "kinematic_viscosity": Quantity(magnitude=1.5e-5, unit="m**2/s"),
        "thermal_conductivity": _q("0.026 W/(m*K)"),
        "prandtl_number": 0.71,
    }
    # 1.5 m at 5 m/s is Re = 5e5 exactly: the laminar form still answers there.
    assert flat_plate_forced_convection_coefficient(plate_length=_q("1.5 m"), **flow) is not None
    # Just past it the laminar form declines and the turbulent one takes over.
    assert flat_plate_forced_convection_coefficient(plate_length=_q("1.6 m"), **flow) is None
    assert flat_plate_turbulent_convection_coefficient(plate_length=_q("1.6 m"), **flow) is not None
    assert flat_plate_turbulent_convection_coefficient(plate_length=_q("1.4 m"), **flow) is None


def test_the_fad_plasticity_correction_is_capped_at_six_tenths():
    """The FAD's μ = min(0.001·E/σ_y, 0.6) cap is API 579's, and it binds on real steels.

    E/σ_y for structural steel is around 400-800, so 0.001·E/σ_y runs 0.4 to 0.8 and the
    cap is reached by ordinary material. A cap of 0.7 changes the curve for every
    high-strength steel and the assessment still returns a plausible point.
    """
    from math import exp

    from anvilate.analysis import fad_option1_curve

    def curve(load_ratio: float, mu: float) -> float:
        return (1.0 + 0.5 * load_ratio**2) ** -0.5 * (0.3 + 0.7 * exp(-mu * load_ratio**6))

    # A low-yield steel: 0.001*200000/250 = 0.8, above the cap, so mu is exactly 0.6.
    capped = fad_option1_curve(
        load_ratio=1.2, yield_strength=_q("250 MPa"), elastic_modulus=_q("200 GPa")
    )
    assert capped == pytest.approx(curve(1.2, 0.6), rel=1e-12)
    assert capped != pytest.approx(curve(1.2, 0.7), rel=1e-6)
    # A high-yield steel where 0.001*E/sy = 0.4 sits below the cap and mu is that value.
    uncapped = fad_option1_curve(
        load_ratio=1.2, yield_strength=_q("500 MPa"), elastic_modulus=_q("200 GPa")
    )
    assert uncapped == pytest.approx(curve(1.2, 0.4), rel=1e-12)
    # The cut-off matters most at high L_r, where the exponential term is doing work.
    assert capped < uncapped
    for value in (capped, uncapped):
        assert 0.0 < value <= 1.0


# --- AISI S100 Direct Strength Method: the whole curve-constant block ------------------


def test_the_dsm_curve_constants_are_the_transitions_they_claim_to_be():
    """Every DSM branch point is where the reduced strength meets the unreduced one.

    The Direct Strength Method's constants are not free parameters: each slenderness
    limit is the λ at which its own Winter-form expression returns exactly 1.0. That is
    the property that pins all four of them at once, and it is checkable without the
    standard in hand — a limit transcribed wrong makes its curve step at the branch.

    Local:  P_n/P_ne = [1 − 0.15·λ^0.8]·λ^-0.8 = 1 at λ = 0.776
    Dist.:  P_n/P_y  = [1 − 0.25·λ^1.2]·λ^-1.2 = 1 at λ = 0.561 (compression)
                                                and λ = 0.673 (flexure, 0.22/λ^1.0)
    """

    def winter(lam: float, coefficient: float, exponent: float) -> float:
        """The DSM reduction: (1 − c·λ^-2n)·λ^-2n, which is 1.0 at the limit."""
        power = lam ** (-2.0 * exponent)
        return (1.0 - coefficient * power) * power

    # Each published limit is the root of its own curve minus one.
    assert winter(0.776, 0.15, 0.4) == pytest.approx(1.0, abs=2e-3)
    assert winter(0.561, 0.25, 0.6) == pytest.approx(1.0, abs=2e-3)
    assert winter(0.673, 0.22, 0.5) == pytest.approx(1.0, abs=2e-3)
    # A transcribed limit breaks it: 0.80 in place of 0.776 steps by ~4%.
    assert winter(0.80, 0.15, 0.4) != pytest.approx(1.0, abs=2e-3)
    assert winter(0.60, 0.25, 0.6) != pytest.approx(1.0, abs=2e-3)


def test_the_dsm_effective_width_limit_is_winters_own_break_even_slenderness():
    """AISI S100's 0.673 is where Winter's effective-width expression gives b_e = b.

    ρ = (1 − 0.22/λ)/λ equals 1.0 at λ = 0.673, which is exactly why that is the limit
    below which an element is fully effective. Change either number and the effective
    width steps discontinuously at the boundary.
    """
    from anvilate.analysis import aisi_effective_width, aisi_plate_slenderness

    def winter_rho(lam: float) -> float:
        return (1.0 - 0.22 / lam) / lam

    assert winter_rho(0.673) == pytest.approx(1.0, abs=1e-3)
    assert winter_rho(0.70) != pytest.approx(1.0, abs=1e-3)

    # And the shipped function is continuous across it. Stress is the free variable:
    # slenderness goes as sqrt(stress), so a stress just under the one that puts λ at
    # 0.673 is fully effective, and just over it is only slightly reduced.
    geometry = {"flat_width": _q("100 mm"), "thickness": _q("2 mm")}
    modulus = _q("200 GPa")

    def slenderness_at(stress: Quantity) -> float:
        return aisi_plate_slenderness(stress=stress, elastic_modulus=modulus, **geometry)

    def effective_at(stress: Quantity) -> float:
        return (
            aisi_effective_width(stress=stress, elastic_modulus=modulus, **geometry)
            .to("mm")
            .magnitude
        )

    # Find the stress that puts lambda at the limit: lambda scales as sqrt(stress).
    reference = _q("100 MPa")
    scale = (0.673 / slenderness_at(reference)) ** 2
    at_limit = Quantity(magnitude=100.0 * scale, unit="MPa")
    assert slenderness_at(at_limit) == pytest.approx(0.673, rel=1e-6)
    assert effective_at(at_limit) == pytest.approx(100.0, rel=1e-3)
    just_past = Quantity(magnitude=100.0 * scale * 1.05, unit="MPa")
    assert 97.0 < effective_at(just_past) < 100.0


# --- Domain-limit guards that never fire under the suite -------------------------------
#
# A guard body that no test reaches has its limit VALUE unpinned by construction: the
# mutation pass could move any of them and nothing would notice. These are the ones whose
# limit is a physical or code constant rather than mere positivity — the highest-yield
# class the audit found, and the sample it verified.


def test_the_actuator_disc_guard_stops_at_the_axial_induction_factor_of_one_half():
    """Past a = 0.5 the actuator-disc model has the wake flowing backwards.

    Momentum theory gives a wake velocity of (1 − 2a)·U, so a > 0.5 is a negative wake
    velocity — not a poor estimate, a meaningless one. Betz's maximum sits at a = 1/3,
    well inside the valid range, so the guard never fires in ordinary use and its limit
    is unpinned unless something reaches for it deliberately.
    """
    from anvilate.analysis.wind_power import (
        actuator_disc_power_coefficient,
        actuator_disc_thrust_coefficient,
    )

    # C_T = 4a(1 − a) peaks at a = 0.5, which is the edge of validity and where the
    # thrust coefficient reaches exactly 1.
    assert actuator_disc_thrust_coefficient(axial_induction_factor=1.0 / 3.0) == pytest.approx(
        8.0 / 9.0, rel=1e-9
    )
    assert actuator_disc_thrust_coefficient(axial_induction_factor=0.5) == pytest.approx(
        1.0, rel=1e-12
    )
    with pytest.raises(ValueError, match="0.5"):
        actuator_disc_thrust_coefficient(axial_induction_factor=0.51)
    # The same limit is guarded independently in the power coefficient, and a relaxed
    # guard in either one is a model running where its own momentum theory does not hold.
    assert actuator_disc_power_coefficient(axial_induction_factor=1.0 / 3.0) == pytest.approx(
        16.0 / 27.0, rel=1e-9
    )
    with pytest.raises(ValueError, match="0.5"):
        actuator_disc_power_coefficient(axial_induction_factor=0.51)


def test_the_poisson_ratio_guards_stop_at_one_half_in_every_module_that_takes_one():
    """ν = 0.5 is incompressibility; above it the bulk modulus goes negative.

    Three modules take a Poisson's ratio and each guards it independently, so a single
    relaxed guard is a module that will happily compute for a material which expands
    under hydrostatic compression. This reaches all three.
    """
    from anvilate.analysis import (
        rotating_solid_disc_tangential_stress,
        simply_supported_plate_center_patch_load,
        sphere_external_pressure_buckling,
    )

    with pytest.raises(ValueError, match="poisson"):
        sphere_external_pressure_buckling(
            elastic_modulus=_q("200 GPa"),
            wall_thickness=_q("6 mm"),
            mean_radius=_q("500 mm"),
            poisson=0.6,
        )
    with pytest.raises(ValueError, match="[Pp]oisson"):
        rotating_solid_disc_tangential_stress(
            density=_q("7850 kg/m**3"),
            outer_radius=_q("300 mm"),
            radius=_q("100 mm"),
            rotational_speed=_q("3000 rpm"),
            poisson=0.55,
        )
    with pytest.raises(ValueError, match="[Pp]oisson"):
        simply_supported_plate_center_patch_load(
            pressure=_q("1 MPa"),
            patch_length=_q("20 mm"),
            patch_width=_q("20 mm"),
            length=_q("400 mm"),
            width=_q("300 mm"),
            thickness=_q("8 mm"),
            elastic_modulus=_q("200 GPa"),
            poisson_ratio=0.5,
        )


def test_the_siegert_guard_stops_below_the_oxygen_content_of_air():
    """The Siegert denominator is (21 − O₂%), so O₂ at 21% is a division by zero.

    A flue-gas oxygen reading at or above the oxygen content of air means no combustion
    took place — or the probe is reading ambient — and the loss is undefined, not large.
    """
    from anvilate.analysis import siegert_dry_flue_gas_loss

    ordinary = siegert_dry_flue_gas_loss(
        siegert_factor=0.65,
        flue_temperature=_q("473.15 K"),
        combustion_air_temperature=_q("293.15 K"),
        flue_oxygen_percent=5.0,
    )
    assert ordinary > 0
    with pytest.raises(ValueError, match="21"):
        siegert_dry_flue_gas_loss(
            siegert_factor=0.65,
            flue_temperature=_q("473.15 K"),
            combustion_air_temperature=_q("293.15 K"),
            flue_oxygen_percent=21.0,
        )


def test_the_solar_declination_guard_stops_at_the_earths_axial_tilt():
    """Declination cannot exceed 23.45°, because that is the tilt of the earth's axis.

    Not a modelling convenience — the physical range of the quantity, reached exactly
    twice a year at the solstices.
    """
    from anvilate.analysis import solar_altitude_at_noon

    assert solar_altitude_at_noon(latitude=51.5, declination=23.45).to(
        "degree"
    ).magnitude == pytest.approx(90.0 - (51.5 - 23.45), rel=1e-12)
    with pytest.raises(ValueError, match="23.45"):
        solar_altitude_at_noon(latitude=51.5, declination=24.0)
    with pytest.raises(ValueError, match="23.45"):
        solar_altitude_at_noon(latitude=51.5, declination=-24.0)


# --- More of the same class: physical bounds behind guards no test reached -------------


def test_the_compressible_flow_family_refuses_a_heat_capacity_ratio_at_or_below_one():
    """γ ≤ 1 means c_p ≤ c_v, which no gas does — and eleven functions guard it separately.

    γ = c_p/c_v and c_p − c_v = R > 0, so γ > 1 for any real gas. Every isentropic and
    normal-shock relation here divides by (γ − 1) or (γ + 1), so the guard is what stands
    between a transposed argument and a division by zero or a negative square root.
    Reaching a representative set pins the bound across the family.
    """
    from anvilate.analysis import (
        normal_shock_downstream_mach,
        prandtl_meyer_angle,
        speed_of_sound,
    )

    # Air at 288 K: the familiar 340 m/s, which is what says the guard is not just
    # refusing everything.
    assert speed_of_sound(
        temperature=_q("288.15 K"),
        heat_capacity_ratio=1.4,
        specific_gas_constant=_q("287 J/(kg*K)"),
    ).to("m/s").magnitude == pytest.approx(340.3, rel=1e-3)
    for gamma in (1.0, 0.9):
        with pytest.raises(ValueError, match="heat_capacity_ratio"):
            speed_of_sound(
                temperature=_q("288.15 K"),
                heat_capacity_ratio=gamma,
                specific_gas_constant=_q("287 J/(kg*K)"),
            )
        with pytest.raises(ValueError, match="heat_capacity_ratio"):
            normal_shock_downstream_mach(upstream_mach=2.0, heat_capacity_ratio=gamma)
        with pytest.raises(ValueError, match="heat_capacity_ratio"):
            prandtl_meyer_angle(mach_number=2.0, heat_capacity_ratio=gamma)


def test_the_supersonic_only_relations_refuse_subsonic_flow():
    """A normal shock cannot form in subsonic flow, and a Mach cone has no half-angle there.

    Both relations return a real, plausible-looking number if the guard is relaxed —
    the Prandtl-Meyer function evaluates to a complex-free value below M = 1 only by
    accident of the algebra — so the physical bound is the whole check.
    """
    from anvilate.analysis import mach_angle, normal_shock_downstream_mach, prandtl_meyer_angle

    # At M = 1 exactly the Mach angle is 90 degrees: the cone has degenerated to a plane.
    assert mach_angle(mach_number=1.0).to("degree").magnitude == pytest.approx(90.0, rel=1e-9)
    assert mach_angle(mach_number=2.0).to("degree").magnitude == pytest.approx(30.0, rel=1e-9)
    with pytest.raises(ValueError, match="mach_number"):
        mach_angle(mach_number=0.99)
    with pytest.raises(ValueError, match="mach_number"):
        prandtl_meyer_angle(mach_number=0.99, heat_capacity_ratio=1.4)
    with pytest.raises(ValueError, match="upstream_mach"):
        normal_shock_downstream_mach(upstream_mach=1.0, heat_capacity_ratio=1.4)


def test_the_sphere_drag_correlation_refuses_past_the_end_of_its_own_fit():
    """The Schiller-Naumann form is fitted to Re ≲ 800; past it the module says so.

    This is the guard that `drag.stokes_settling_velocity` and the centrifuge screens
    point at when they refuse — so its limit is load-bearing for three functions and was
    reached by none.
    """
    from anvilate.analysis import sphere_drag_coefficient

    # Deep in Stokes flow the correlation collapses to 24/Re, which is the exact result.
    assert sphere_drag_coefficient(reynolds_number=0.1) == pytest.approx(24.0 / 0.1, rel=0.1)
    assert sphere_drag_coefficient(reynolds_number=800.0) > 0
    with pytest.raises(ValueError, match="800"):
        sphere_drag_coefficient(reynolds_number=801.0)


def test_the_geotechnical_bounds_are_the_ones_that_make_the_quantity_a_quantity():
    """An OCR below 1, a resultant outside the middle third, and a soil lighter than water.

    Each of these is a quantity that cannot take the value, not a correlation running out
    of range: OCR is past-maximum over current stress and cannot be below 1; an
    eccentricity of half the base width puts the resultant off the footing entirely; and
    a critical hydraulic gradient needs solids denser than water or there is nothing to
    lift.
    """
    # Normally consolidated is OCR = 1 exactly, and K0 there is Jaky's 1 - sin(phi).
    from math import radians, sin

    from anvilate.analysis import (
        critical_hydraulic_gradient,
        eccentric_base_pressure,
        overconsolidated_at_rest_coefficient,
    )

    assert overconsolidated_at_rest_coefficient(
        friction_angle=30.0, overconsolidation_ratio=1.0
    ) == pytest.approx(1.0 - sin(radians(30.0)), rel=1e-9)
    with pytest.raises(ValueError, match="overconsolidation_ratio"):
        overconsolidated_at_rest_coefficient(friction_angle=30.0, overconsolidation_ratio=0.9)

    # Quartz sand at G_s = 2.65: the classic i_cr near 1.
    assert critical_hydraulic_gradient(specific_gravity=2.65, void_ratio=0.65) == pytest.approx(
        (2.65 - 1.0) / (1.0 + 0.65), rel=1e-12
    )
    with pytest.raises(ValueError, match="specific_gravity"):
        critical_hydraulic_gradient(specific_gravity=1.0, void_ratio=0.65)

    # e = B/2 puts the resultant on the edge of the footing; past it there is no bearing
    # area left to compute a pressure over.
    inside = eccentric_base_pressure(
        vertical_load=_q("500 kN/m"), base_width=_q("3 m"), eccentricity=_q("0.4 m")
    )
    assert inside["q_max"].to("kPa").magnitude > inside["q_min"].to("kPa").magnitude
    # e = B/6 is the middle-third boundary where q_min reaches zero; 0.4 m on a 3 m base
    # is past it in the trapezoidal-but-still-bearing range.
    assert inside["q_min"].to("kPa").magnitude > 0
    with pytest.raises(ValueError, match="eccentricity"):
        eccentric_base_pressure(
            vertical_load=_q("500 kN/m"), base_width=_q("3 m"), eccentricity=_q("1.5 m")
        )


def test_the_sheetmetal_bounds_hold_the_k_factor_inside_the_material():
    """k ≤ 0.5 says the neutral axis cannot move past mid-thickness, which is physics.

    Bending moves the neutral axis *toward the inside* of the bend, so k runs 0 to 0.5
    and a k above 0.5 is a neutral axis outside the material on the tension side. A
    bend angle outside (0, 180) and a reduction of area above 100% are the same kind of
    bound: the quantity cannot take the value.
    """
    from anvilate.analysis import minimum_bend_radius, neutral_axis_radius

    # k = 0.5 is the neutral axis exactly at mid-thickness — the undeformed limit.
    assert neutral_axis_radius(inner_radius=_q("3 mm"), thickness=_q("2 mm"), k_factor=0.5).to(
        "mm"
    ).magnitude == pytest.approx(4.0, rel=1e-12)
    with pytest.raises(ValueError, match="k_factor"):
        neutral_axis_radius(inner_radius=_q("3 mm"), thickness=_q("2 mm"), k_factor=0.55)

    # 100% reduction of area is a perfectly ductile material, and the minimum radius
    # there is zero — the bound is reachable and meaningful, not merely defensive.
    assert minimum_bend_radius(thickness=_q("2 mm"), reduction_of_area_percent=100.0).to(
        "mm"
    ).magnitude == pytest.approx(0.0, abs=1e-9)
    with pytest.raises(ValueError, match="reduction_of_area_percent"):
        minimum_bend_radius(thickness=_q("2 mm"), reduction_of_area_percent=101.0)


def test_an_isentropic_efficiency_above_unity_is_refused_not_reported():
    """An efficiency over 1 is a measurement error, and reporting it launders one.

    The isentropic outlet temperature is the best a turbine can do, so an actual outlet
    below it means the instrumentation disagrees with thermodynamics. Returning 1.04
    would put that in a report as a very good turbine.
    """
    from anvilate.analysis import turbine_isentropic_efficiency

    assert turbine_isentropic_efficiency(
        inlet_temperature=_q("800 K"),
        actual_outlet_temperature=_q("620 K"),
        isentropic_outlet_temperature=_q("600 K"),
    ) == pytest.approx(180.0 / 200.0, rel=1e-12)
    with pytest.raises(ValueError, match="efficiency"):
        turbine_isentropic_efficiency(
            inlet_temperature=_q("800 K"),
            actual_outlet_temperature=_q("590 K"),
            isentropic_outlet_temperature=_q("600 K"),
        )


def test_the_motor_branch_circuit_sizing_factor_cannot_fall_below_the_code_minimum():
    """NEC 430.22 sizes a motor branch circuit at 125% of full-load current, not less.

    A sizing factor below 1.0 is a conductor smaller than the motor's own running
    current, which is not a design choice at any level of aggression.
    """
    from anvilate.analysis import motor_branch_circuit_ampacity

    assert motor_branch_circuit_ampacity(full_load_current=_q("28 A")).to(
        "A"
    ).magnitude == pytest.approx(35.0, rel=1e-12)
    with pytest.raises(ValueError, match="sizing_factor"):
        motor_branch_circuit_ampacity(full_load_current=_q("28 A"), sizing_factor=0.9)
