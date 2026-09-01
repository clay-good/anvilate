"""Refusals the library promises and nothing had ever proved.

A line-trace of the whole suite says **57% of the 4,299 `raise` sites in the imported
modules never execute**. Most are dimension and positivity checks whose absence a reader
would notice; the interesting subset is the 38 whose *condition carries a domain constant*
— a Poisson's ratio that cannot reach 0.5, an angle range a formula's geometry requires,
a Magnus-form validity floor, the speed of light. Those are the library's own statements
about where a formula stops applying, and until this file none of them had been executed.

Each case here trips one such guard. That is a lower bar than it sounds: a guard whose
refusal never runs is a guard whose *condition* has never been evaluated against the case
it exists for, and an inverted comparison in one reads exactly like a correct one.

What is being pinned is the boundary, not the message. Where the limit is physical — a
Poisson's ratio at 0.5 makes an incompressible material and divides by zero — the test
also checks the value just inside it is accepted, because a guard that refuses everything
passes a refusal test just as well as a correct one.
"""

from __future__ import annotations

import pytest

from anvilate.analysis import (
    agma_contact_stress,
    asme_conical_head_mawp,
    compound_plastic_section_modulus,
    compound_section_properties,
    compton_electron_energy,
    conical_pendulum_speed,
    dew_point_temperature,
    eccentric_shear_group_peak_force,
    eccentric_weld_group_peak_stress,
    flat_pattern_length,
    fourbar_time_ratio,
    i_section_plastic_section_modulus,
    involute_angle,
    net_width_staggered_holes,
    off_axis_modulus,
    open_section_torsion_constant,
    projectile_max_height,
    projectile_range_from_height,
    projectile_time_of_flight,
    relativistic_doppler_frequency,
    righting_moment,
    rotating_annular_disc_bore_stress,
    saturation_vapor_pressure,
    shear_spinning_reduction,
    snap_fit_mating_force,
    thermal_shock_temperature_limit,
    through_wall_gradient_thermal_stress,
    turn_rate,
    universal_joint_speed_fluctuation,
    wire_drawing_stress,
)
from anvilate.units import Quantity

Q = Quantity.parse


# --- Poisson's ratio: 0.5 is incompressible, and every one of these divides by (1 - nu) ---


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda nu: rotating_annular_disc_bore_stress(
                density=Q("7850 kg/m**3"),
                outer_radius=Q("200 mm"),
                inner_radius=Q("50 mm"),
                rotational_speed=Q("3000 rpm"),
                poisson=nu,
            ),
            id="rotating_annular_disc_bore_stress",
        ),
        pytest.param(
            lambda nu: thermal_shock_temperature_limit(
                fracture_strength=Q("300 MPa"),
                elastic_modulus=Q("200 GPa"),
                thermal_expansion_coefficient=Q("12e-6 1/K"),
                poisson=nu,
            ),
            id="thermal_shock_temperature_limit",
        ),
        pytest.param(
            lambda nu: through_wall_gradient_thermal_stress(
                elastic_modulus=Q("200 GPa"),
                thermal_expansion_coefficient=Q("12e-6 1/K"),
                temperature_difference=Q("50 K"),
                poisson=nu,
            ),
            id="through_wall_gradient_thermal_stress",
        ),
    ],
)
def test_a_poisson_ratio_of_one_half_is_refused(call):
    """At 0.5 the material is incompressible and the 1/(1 - nu) these carry is a division
    by zero. Just inside it is a real material and must still be screened."""
    with pytest.raises(ValueError):
        call(0.5)
    with pytest.raises(ValueError):
        call(-0.1)
    assert call(0.49) is not None
    assert call(0.0) is not None


def test_the_agma_contact_stress_refuses_an_incompressible_gear():
    common = {
        "tangential_load": Q("5 kN"),
        "pinion_pitch_diameter": Q("100 mm"),
        "face_width": Q("40 mm"),
        "geometry_factor": 0.11,
        "modulus_pinion": Q("200 GPa"),
        "modulus_gear": Q("200 GPa"),
    }
    with pytest.raises(ValueError):
        agma_contact_stress(**common, poisson_pinion=0.5)
    with pytest.raises(ValueError):
        agma_contact_stress(**common, poisson_gear=0.5)
    assert agma_contact_stress(**common) is not None


def test_an_off_axis_modulus_refuses_a_poisson_ratio_outside_the_lamina_bounds():
    """A major Poisson's ratio of a lamina lies in (-0.5, 1.0) — wider than an isotropic
    material's, because a composite can have a negative one, and narrower than unbounded."""
    common = {
        "angle": 30.0,
        "longitudinal_modulus": Q("140 GPa"),
        "transverse_modulus": Q("10 GPa"),
        "shear_modulus": Q("5 GPa"),
    }
    with pytest.raises(ValueError):
        off_axis_modulus(**common, major_poisson=1.0)
    with pytest.raises(ValueError):
        off_axis_modulus(**common, major_poisson=-0.5)
    assert off_axis_modulus(**common, major_poisson=0.3) is not None


# --- Angles: a formula's geometry, not a preference ------------------------------------


@pytest.mark.parametrize(
    "call,bad,good",
    [
        pytest.param(
            lambda a: projectile_max_height(launch_speed=Q("20 m/s"), launch_angle=a),
            0.0,
            45.0,
            id="projectile_max_height at 0",
        ),
        pytest.param(
            lambda a: projectile_time_of_flight(launch_speed=Q("20 m/s"), launch_angle=a),
            91.0,
            45.0,
            id="projectile_time_of_flight past vertical",
        ),
        pytest.param(
            lambda a: projectile_range_from_height(
                launch_speed=Q("20 m/s"), launch_angle=a, launch_height=Q("2 m")
            ),
            90.0,
            45.0,
            id="projectile_range_from_height at vertical",
        ),
        pytest.param(
            lambda a: conical_pendulum_speed(string_length=Q("1 m"), half_angle=a),
            90.0,
            30.0,
            id="conical_pendulum_speed at 90",
        ),
        pytest.param(
            lambda a: righting_moment(
                weight=Q("100 kN"), metacentric_height=Q("1 m"), heel_angle=a
            ),
            90.0,
            10.0,
            id="righting_moment at 90",
        ),
        pytest.param(
            lambda a: turn_rate(speed=Q("100 kt"), bank_angle=a),
            90.0,
            30.0,
            id="turn_rate at 90",
        ),
        pytest.param(
            lambda a: compton_electron_energy(
                incident_wavelength=Q("1 angstrom"), scattering_angle=a
            ),
            181.0,
            90.0,
            id="compton_electron_energy past 180",
        ),
        pytest.param(
            lambda a: universal_joint_speed_fluctuation(shaft_angle=a),
            90.0,
            20.0,
            id="universal_joint_speed_fluctuation at 90",
        ),
        pytest.param(
            lambda a: shear_spinning_reduction(half_cone_angle=a),
            90.0,
            30.0,
            id="shear_spinning_reduction at 90",
        ),
        pytest.param(
            lambda a: snap_fit_mating_force(
                deflection_force=Q("10 N"), insertion_angle=a, friction_coefficient=0.3
            ),
            90.0,
            30.0,
            id="snap_fit_mating_force at 90",
        ),
        pytest.param(
            lambda a: wire_drawing_stress(
                flow_stress=Q("300 MPa"),
                initial_area=Q("100 mm**2"),
                final_area=Q("80 mm**2"),
                die_half_angle=a,
                friction_coefficient=0.05,
            ),
            90.0,
            8.0,
            id="wire_drawing_stress at 90",
        ),
        pytest.param(
            lambda a: asme_conical_head_mawp(
                thickness=Q("10 mm"),
                diameter=Q("1000 mm"),
                allowable_stress=Q("120 MPa"),
                half_apex_angle_deg=a,
            ),
            90.0,
            30.0,
            id="asme_conical_head_mawp at 90",
        ),
    ],
)
def test_an_angle_outside_the_formulas_geometry_is_refused(call, bad, good):
    with pytest.raises(ValueError):
        call(bad)
    assert call(good) is not None


# --- Other physical and structural boundaries ------------------------------------------


def test_a_source_at_the_speed_of_light_is_refused():
    with pytest.raises(ValueError):
        relativistic_doppler_frequency(source_frequency=Q("1 GHz"), velocity=Q("299792458 m/s"))
    assert (
        relativistic_doppler_frequency(source_frequency=Q("1 GHz"), velocity=Q("1000 km/s"))
        is not None
    )


def test_the_magnus_form_is_refused_outside_the_range_it_was_fitted_over():
    """Both ends of the same correlation: a temperature at its pole, and a vapour pressure
    whose gamma runs past the numerator constant, where the inverse has no solution."""
    # -243.04 degC is the Magnus pole; 30 K is just below it. Written in kelvin because
    # a negative Celsius string does not parse, and a parse error passes a `raises`
    # assertion exactly as well as the guard would — which is how this test nearly went
    # green while measuring nothing.
    with pytest.raises(ValueError, match="below the valid range"):
        saturation_vapor_pressure(temperature=Quantity(magnitude=30.0, unit="K"))
    with pytest.raises(ValueError, match="above the valid range"):
        dew_point_temperature(vapor_pressure=Q("1e11 Pa"))
    assert saturation_vapor_pressure(temperature=Quantity(magnitude=293.15, unit="K")) is not None
    assert dew_point_temperature(vapor_pressure=Q("1.2 kPa")) is not None


def test_an_i_section_whose_flanges_meet_is_refused():
    """Two flanges thicker than half the section leave no web, and the plastic modulus of
    the remainder is a negative area the formula reports as a positive number."""
    with pytest.raises(ValueError):
        i_section_plastic_section_modulus(
            flange_width=Q("100 mm"),
            total_height=Q("100 mm"),
            flange_thickness=Q("50 mm"),
            web_thickness=Q("8 mm"),
        )
    assert (
        i_section_plastic_section_modulus(
            flange_width=Q("100 mm"),
            total_height=Q("200 mm"),
            flange_thickness=Q("12 mm"),
            web_thickness=Q("8 mm"),
        )
        is not None
    )


def test_an_involute_value_no_angle_produces_is_refused():
    """inv(phi) = tan(phi) - phi is solved by Newton iteration, and a value it cannot reach
    is refused rather than returned as the last iterate."""
    with pytest.raises(ValueError):
        involute_angle(involute_value=-1.0)
    # inv(20 deg) = tan 20 - 20 rad = 0.014904, and the function answers in degrees.
    assert involute_angle(involute_value=0.014904) == pytest.approx(20.0, abs=1e-3)


def test_involute_angle_refuses_a_root_it_cannot_certify_rather_than_returning_ninety():
    """The residual check is reachable, and was recorded below as unreachable for a year.

    The excuse was that it "fires only if Newton fails to converge". The solver is a
    *bracketed* Newton on (0, pi/2 - 1e-12), so it cannot fail to converge — it converges
    onto whatever the bracket allows, and past a certain argument that is the bracket's own
    top end, 89.9999999999427 degrees: the same answer for every such argument, which is a
    property of the bracket rather than of the input. The residual check is what turns that
    into a refusal, and its tolerance was unpinned because nothing reached the branch.

    Where it stops is fixed by the arithmetic, not chosen. Near the pole one ulp of phi
    (2.2e-16) moves tan(phi) by sec^2(phi) times that, so the finest residual a double can
    express grows with the argument and crosses the 1e-9 relative tolerance around
    inv ~ 5e6. That makes a *band*, not an edge — measured on 2026-08-29, everything below
    4.7e6 inverts, everything above 1e9 refuses, and in between it depends on where the
    iterates happen to land. The anchors below sit outside the band on purpose; do not
    tighten them into it.

    The pair is the test. A refusal alone would also pass if the function simply declined
    large arguments — a different and wrong gate — so a value below the band is asserted to
    still invert and round-trip.
    """
    from anvilate.analysis import involute_function

    inverted = involute_angle(involute_value=1.0e6)
    assert 0.0 < inverted < 90.0
    assert involute_function(pressure_angle=inverted) == pytest.approx(1.0e6, rel=1e-9)

    for beyond in (1.0e10, 1.0e12, 1.0e20):
        with pytest.raises(ValueError, match="does not lie in"):
            involute_angle(involute_value=beyond)


def test_a_fourbar_whose_advance_stroke_is_the_whole_revolution_is_refused():
    """A time ratio needs an advance stroke under 180 deg; at or past it the mechanism is
    not a crank-rocker and the ratio is not defined."""
    with pytest.raises(ValueError):
        fourbar_time_ratio(
            ground=Q("100 mm"), input_link=Q("100 mm"), coupler=Q("100 mm"), output_link=Q("100 mm")
        )


@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda seq: compound_section_properties(rectangles=seq),
            id="compound_section_properties",
        ),
        pytest.param(
            lambda seq: compound_plastic_section_modulus(rectangles=seq),
            id="compound_plastic_section_modulus",
        ),
    ],
)
def test_a_compound_rectangle_that_is_not_three_values_is_refused(call):
    """Width, height, centroid offset — a two-tuple silently loses the offset and every
    rectangle then stacks on the same axis."""
    with pytest.raises(ValueError):
        call([(Q("100 mm"), Q("10 mm"))])
    assert call([(Q("100 mm"), Q("10 mm"), Q("0 mm"))]) is not None


def test_a_torsion_rectangle_that_is_not_two_values_is_refused():
    with pytest.raises(ValueError):
        open_section_torsion_constant(rectangles=[(Q("100 mm"), Q("10 mm"), Q("0 mm"))])
    assert open_section_torsion_constant(rectangles=[(Q("100 mm"), Q("10 mm"))]) is not None


def test_a_fastener_or_weld_coordinate_that_is_not_a_pair_is_refused():
    with pytest.raises(ValueError):
        eccentric_shear_group_peak_force(
            positions=[(Q("0 mm"),)], load=Q("10 kN"), eccentricity=Q("100 mm")
        )
    with pytest.raises(ValueError):
        net_width_staggered_holes(
            gross_width=Q("200 mm"),
            hole_diameter=Q("22 mm"),
            hole_count=2,
            stagger_pitch_gauge=[(Q("50 mm"),)],
        )
    with pytest.raises(ValueError):
        eccentric_weld_group_peak_stress(
            segments=[((Q("0 mm"), Q("0 mm")), (Q("100 mm"),))],
            load=Q("10 kN"),
            eccentricity=Q("100 mm"),
            leg_size=Q("6 mm"),
        )


def test_a_flat_pattern_of_one_flange_has_no_bend_to_develop():
    with pytest.raises(ValueError):
        flat_pattern_length(
            flange_lengths=[Q("50 mm")],
            bend_angle=90.0,
            inner_radius=Q("3 mm"),
            thickness=Q("2 mm"),
            k_factor=0.44,
        )
    assert (
        flat_pattern_length(
            flange_lengths=[Q("50 mm"), Q("40 mm")],
            bend_angle=90.0,
            inner_radius=Q("3 mm"),
            thickness=Q("2 mm"),
            k_factor=0.44,
        )
        is not None
    )


# --- The same lens, second pass ---------------------------------------------------------
#
# Re-tracing after the cases above took the never-executed domain guards from 38 to 12,
# and six of those twelve turned out to be reached by a *different* guard than intended —
# a bearing whose contact angle never got as far as its own check because the rotational
# speed was refused first, a single malformed fastener position caught by the "at least
# two" rule instead. A guard reached through another guard is still unpinned, and the
# trace is what said so.


def test_the_remaining_poisson_and_angle_guards_fire_on_their_own_functions():
    from anvilate.analysis import (
        belleville_washer_force,
        rotating_annular_disc_radial_stress,
        simply_supported_circular_plate_center_load_deflection,
        worm_tangential_force,
    )

    disc = {
        "density": Q("7850 kg/m**3"),
        "outer_radius": Q("200 mm"),
        "inner_radius": Q("50 mm"),
        "radius": Q("100 mm"),
        "rotational_speed": Q("3000 rpm"),
    }
    with pytest.raises(ValueError):
        rotating_annular_disc_radial_stress(**disc, poisson=0.5)
    assert rotating_annular_disc_radial_stress(**disc, poisson=0.3) is not None

    plate = {
        "force": Q("1 kN"),
        "diameter": Q("500 mm"),
        "thickness": Q("10 mm"),
        "elastic_modulus": Q("200 GPa"),
    }
    with pytest.raises(ValueError):
        simply_supported_circular_plate_center_load_deflection(**plate, poisson_ratio=0.5)
    assert simply_supported_circular_plate_center_load_deflection(**plate, poisson_ratio=0.3)

    washer = {
        "deflection": Q("0.5 mm"),
        "thickness": Q("1 mm"),
        "cone_height": Q("1 mm"),
        "outer_diameter": Q("40 mm"),
        "inner_diameter": Q("20 mm"),
        "elastic_modulus": Q("200 GPa"),
    }
    with pytest.raises(ValueError):
        belleville_washer_force(**washer, poisson_ratio=0.5)
    assert belleville_washer_force(**washer, poisson_ratio=0.3) is not None

    worm = {
        "gear_tangential_load": Q("1 kN"),
        "lead_angle": 10.0,
        "friction_coefficient": 0.05,
    }
    with pytest.raises(ValueError):
        worm_tangential_force(**worm, normal_pressure_angle=90.0)
    assert worm_tangential_force(**worm, normal_pressure_angle=14.5) is not None


def test_a_bearing_contact_angle_at_ninety_degrees_is_refused():
    """Reached only with a rotational speed the units layer accepts — at 90 degrees the
    rolling element runs purely axially and every defect frequency divides by zero."""
    from anvilate.analysis import bearing_ball_pass_frequency_outer

    geometry = {
        "rotational_frequency": Q("1800 rpm"),
        "number_of_rolling_elements": 8,
        "rolling_element_diameter": Q("8 mm"),
        "pitch_diameter": Q("40 mm"),
    }
    with pytest.raises(ValueError, match=r"\(-90, 90\)"):
        bearing_ball_pass_frequency_outer(**geometry, contact_angle=90.0)
    with pytest.raises(ValueError, match=r"\(-90, 90\)"):
        bearing_ball_pass_frequency_outer(**geometry, contact_angle=-90.0)
    assert bearing_ball_pass_frequency_outer(**geometry, contact_angle=15.0) is not None


def test_a_sprinkler_k_factor_of_the_wrong_dimension_is_refused():
    """The K-factor of a sprinkler is flow per square root of pressure, which is not a
    length however familiar the number looks."""
    from anvilate.analysis import sprinkler_pressure_for_flow

    with pytest.raises(ValueError):
        sprinkler_pressure_for_flow(k_factor=Q("80 mm"), flow_rate=Q("100 L/min"))


def test_a_weld_segment_that_is_not_two_points_is_refused():
    """The outer check, distinct from the endpoint check above: three points is not a
    segment, and the extra one would be silently ignored."""
    with pytest.raises(ValueError, match="must be an"):
        eccentric_weld_group_peak_stress(
            segments=[((Q("0 mm"), Q("0 mm")), (Q("100 mm"), Q("0 mm")), (Q("1 mm"), Q("1 mm")))],
            load=Q("10 kN"),
            eccentricity=Q("100 mm"),
            leg_size=Q("6 mm"),
        )


def test_one_malformed_fastener_position_among_several_is_refused():
    """A single bad position used to be caught by the "at least two fasteners" rule, which
    is a different check with a different message. Two positions, one malformed, reaches
    the per-position one."""
    with pytest.raises(ValueError, match=r"positions\[1\]"):
        eccentric_shear_group_peak_force(
            positions=[(Q("0 mm"), Q("0 mm")), (Q("50 mm"),)],
            load=Q("10 kN"),
            eccentricity=Q("100 mm"),
        )
    assert (
        eccentric_shear_group_peak_force(
            positions=[(Q("0 mm"), Q("0 mm")), (Q("50 mm"), Q("0 mm"))],
            load=Q("10 kN"),
            eccentricity=Q("100 mm"),
        )
        is not None
    )


def test_a_conflict_of_one_value_is_not_a_conflict():
    """`FieldConflict` exists to stop a silent decision between two disagreeing extracted
    values. Built from one, it would report a conflict a reader has to resolve against
    nothing — and the draft would refuse to release over it."""
    from pydantic import ValidationError

    from anvilate.ingest import ExtractedValue, FieldConflict, SourceLocation

    where = SourceLocation(document="rfq.pdf", line_number=12, excerpt="design load 50 kN")
    value = ExtractedValue(field="load", quantity=Q("50 kN"), source=where)
    with pytest.raises(ValidationError, match="at least two values"):
        FieldConflict(field="load", values=(value,))
    other = ExtractedValue(
        field="load",
        quantity=Q("45 kN"),
        source=SourceLocation(document="rfq.pdf", line_number=40, excerpt="45 kN in the notes"),
    )
    assert len(FieldConflict(field="load", values=(value, other)).values) == 2


def test_an_incompressible_material_has_no_bulk_modulus():
    """K = E/(3(1 - 2nu)) has a pole at nu = 0.5, and the record refuses rather than
    returning the very large number just short of it as though it were a property."""
    from anvilate.standards import default_materials_db

    steel = default_materials_db().get("ASTM-A36")
    assert steel.bulk_modulus() is not None
    incompressible = steel.model_copy(
        update={"poisson_ratio": steel.poisson_ratio.model_copy(update={"value": 0.5})}
    )
    with pytest.raises(ValueError, match="incompressible"):
        incompressible.bulk_modulus()


def test_the_one_guard_left_unpinned_is_unreachable_by_construction():
    """Recorded rather than left as an unexplained gap in the trace.

    ``fourbar_time_ratio``'s ``advance >= 180`` cannot be reached from any input, and is a
    deliberate safety net rather than a domain limit: ``advance`` is the absolute
    difference of two toggle angles, each returned by ``acos`` and therefore in [0, 180],
    so it reaches 180 only when one is exactly 0 and the other exactly 180 — a degenerate
    linkage the Grashof check refuses first.

    **This said "the two guards" and named ``involute_angle``'s residual check as the
    second, on the grounds that it fires only when Newton fails and the one input that
    made it fail (a NaN) is refused ahead of it. That was wrong, and the reasoning stopped
    one step early.** The solver is a *bracketed* Newton, so it cannot fail to converge —
    it converges onto the bracket's own top end, 89.99999999999999 degrees, for any
    argument whose root lies above it. ``involute_value = 1e12`` is finite, non-negative,
    and reaches the check;
    ``test_involute_angle_refuses_a_root_outside_its_bracket_rather_than_returning_ninety``
    pins it. An "unreachable by construction" claim is a claim, and it is worth the same
    scrutiny as the code it excuses.
    """
    from anvilate.analysis import fourbar_time_ratio, is_grashof

    ratios = []
    for lengths in (
        (100, 40, 120, 80),
        (200, 50, 180, 150),
        (100, 30, 90, 70),
        (120, 40, 100, 110),
    ):
        links = {
            k: Quantity(magnitude=float(v), unit="mm")
            for k, v in zip(
                ("ground", "input_link", "coupler", "output_link"), lengths, strict=True
            )
        }
        assert is_grashof(**links)
        ratios.append(fourbar_time_ratio(**links))
    assert all(r >= 1.0 for r in ratios), "a time ratio is >= 1 by construction"
    assert max(ratios) < 10.0, (
        "an advance approaching 180 degrees would send the ratio to infinity; none of "
        "these is near it, which is what makes the guard a net rather than a limit"
    )


# --- the eleven that were still cold ------------------------------------------------------
#
# Re-run at HEAD, the raise-site trace says 2,400 of 4,794 sites never execute — but only
# **eleven** of those cold refusals state a number, which is the subset whose constant can be
# wrong without anything noticing. This section is those eleven. Ten are tripped; the
# eleventh is genuinely unreachable and what is pinned instead is the fact that makes it so.


def test_a_polytropic_exponent_below_one_is_refused():
    """n = 1 is isothermal and n ≈ 1.4 adiabatic; below 1 is neither, and the gas-law
    expansion the usable volume rests on has no meaning there."""
    from anvilate.analysis import accumulator_usable_volume

    sizes = {
        "total_volume": Quantity.parse("10 L"),
        "precharge_pressure": Quantity.parse("100 bar"),
        "minimum_pressure": Quantity.parse("150 bar"),
        "maximum_pressure": Quantity.parse("250 bar"),
    }
    with pytest.raises(ValueError, match="polytropic_exponent must be at least 1"):
        accumulator_usable_volume(**sizes, polytropic_exponent=0.999)
    # And the boundary itself is accepted: isothermal is a real process, not an error.
    assert accumulator_usable_volume(**sizes, polytropic_exponent=1.0).to("L").magnitude > 0


def test_a_torsional_amplification_below_one_is_refused():
    """Ax scales the accidental eccentricity *up* for a torsionally irregular building.
    Below 1 it would scale it down, which is a discount ASCE 7 does not offer."""
    from anvilate.analysis import seismic_accidental_torsional_moment

    inputs = {
        "story_shear": Quantity.parse("100 kN"),
        "building_dimension": Quantity.parse("30 m"),
    }
    with pytest.raises(ValueError, match="amplification_factor must be at least 1.0"):
        seismic_accidental_torsional_moment(**inputs, amplification_factor=0.999)
    at_one = seismic_accidental_torsional_moment(**inputs, amplification_factor=1.0)
    assert at_one.to("kN*m").magnitude == pytest.approx(100.0 * 0.05 * 30.0)


def test_a_non_wetting_contact_angle_is_refused_rather_than_returning_a_negative_time():
    """cos θ ≤ 0 is a liquid that does not wick. Washburn would return a *negative*
    penetration time for it — a number with the right units and the wrong sign."""
    from anvilate.analysis import washburn_penetration_time

    inputs = {
        "surface_tension": Quantity.parse("0.072 N/m"),
        "pore_radius": Quantity.parse("50 um"),
        "viscosity": Quantity.parse("0.001 Pa*s"),
        "length": Quantity.parse("10 mm"),
    }
    for outside in (90.001, 135.0, 179.0):
        with pytest.raises(ValueError, match="below 90 degrees"):
            washburn_penetration_time(**inputs, contact_angle=outside)
    # Just inside, and the time is positive — the property the guard exists to keep.
    assert washburn_penetration_time(**inputs, contact_angle=89.0).to("s").magnitude > 0
    # Exactly 90 is not refused, and the reason is arithmetic rather than intent:
    # `cos(radians(90.0))` is 6.1e-17, not 0. The guard tests the cosine, so the knife edge
    # falls on the accepting side and the answer is a very large but finite time.
    assert washburn_penetration_time(**inputs, contact_angle=90.0).to("s").magnitude > 1e12


def test_losses_that_exceed_the_fuel_are_refused_rather_than_reported_as_a_negative():
    """η = 100 − qA − other. Losses summing past 100 give a negative efficiency, which
    reads as a number rather than as the input error it is."""
    from anvilate.analysis import combustion_efficiency

    with pytest.raises(ValueError, match="exceed 100"):
        combustion_efficiency(dry_flue_gas_loss_percent=95.0, other_losses_percent=10.0)
    with pytest.raises(ValueError, match="exceed 100"):
        combustion_efficiency(dry_flue_gas_loss_percent=100.0)
    assert combustion_efficiency(dry_flue_gas_loss_percent=99.0) == pytest.approx(1.0)


def test_the_neuber_constant_must_be_a_quantity_and_says_so_by_name():
    """√a is a **√length**, and the one way to get it wrong is to pass the bare number off
    a table. The refusal names the dimension rather than failing inside the arithmetic."""
    from anvilate.analysis import neuber_notch_sensitivity

    with pytest.raises(ValueError, match=r"neuber_constant must be a \[length\]\*\*0.5"):
        neuber_notch_sensitivity(notch_radius=Quantity.parse("1 mm"), neuber_constant=0.25)
    with pytest.raises(ValueError, match=r"neuber_constant must be a \[length\]\*\*0.5"):
        neuber_notch_sensitivity(
            notch_radius=Quantity.parse("1 mm"), neuber_constant=Quantity.parse("0.25 mm")
        )
    q = neuber_notch_sensitivity(
        notch_radius=Quantity.parse("1 mm"), neuber_constant=Quantity.parse("0.25 mm**0.5")
    )
    assert 0.0 <= q <= 1.0


def test_a_weld_metal_shear_fraction_outside_its_band_is_refused():
    """The 0.6 in F_nw = 0.6·F_EXX is a ratio of shear strength to tensile. Above 1 it
    would make the weld metal stronger in shear than in tension."""
    from anvilate.analysis import fillet_weld_directional_strength

    inputs = {
        "leg_size": Quantity.parse("6 mm"),
        "length": Quantity.parse("100 mm"),
        "electrode_strength": Quantity.parse("70 ksi"),
        "load_angle": 0.5,
    }
    for outside in (0.0, -0.1, 1.01):
        with pytest.raises(ValueError, match=r"must lie in \(0, 1\]"):
            fillet_weld_directional_strength(**inputs, weld_metal_shear_fraction=outside)
    # 1.0 is the closed end and is accepted, which is what makes the band a band.
    assert (
        fillet_weld_directional_strength(**inputs, weld_metal_shear_fraction=1.0).to("kN").magnitude
        > 0
    )


def test_a_pressure_past_the_thin_wall_sphere_limit_is_refused():
    """ASME UG-27's sphere formula divides by 2·S·E − 0.2·P. At the limit the thickness
    goes to infinity; past it the sign flips and a *negative* thickness comes back."""
    from anvilate.analysis import asme_spherical_shell_thickness

    inputs = {"radius": Quantity.parse("500 mm"), "allowable_stress": Quantity.parse("100 MPa")}
    # 2·S·E = 200 MPa, so the limit is P = 1000 MPa.
    with pytest.raises(ValueError, match=r"2·S·E .* must exceed 0.2·P"):
        asme_spherical_shell_thickness(
            pressure=Quantity.parse("1000 MPa"), joint_efficiency=1.0, **inputs
        )
    inside = asme_spherical_shell_thickness(
        pressure=Quantity.parse("900 MPa"), joint_efficiency=1.0, **inputs
    )
    assert inside.to("mm").magnitude > 0
    # The efficiency is on the same side of the comparison, so halving it halves the limit.
    with pytest.raises(ValueError, match=r"2·S·E .* must exceed 0.2·P"):
        asme_spherical_shell_thickness(
            pressure=Quantity.parse("900 MPa"), joint_efficiency=0.5, **inputs
        )


def test_a_pressure_past_the_conical_head_limit_is_refused():
    """The cone's denominator is S·E − 0.6·P, a different constant on a different
    geometry — so it is pinned separately rather than assumed to follow the sphere."""
    from anvilate.analysis import asme_conical_head_thickness

    inputs = {
        "diameter": Quantity.parse("1000 mm"),
        "allowable_stress": Quantity.parse("100 MPa"),
        "half_apex_angle_deg": 30.0,
    }
    # S·E = 100 MPa, so the limit is P = 100/0.6 = 166.67 MPa.
    with pytest.raises(ValueError, match=r"S·E .* must exceed 0.6·P"):
        asme_conical_head_thickness(
            pressure=Quantity.parse("170 MPa"), joint_efficiency=1.0, **inputs
        )
    assert (
        asme_conical_head_thickness(
            pressure=Quantity.parse("160 MPa"), joint_efficiency=1.0, **inputs
        )
        .to("mm")
        .magnitude
        > 0
    )


def test_a_temperature_band_given_as_a_bare_number_is_named_rather_than_crashed_on():
    """The guard that checked the type read the unit off the value first.

    `unit = str(tolerance.unit)` sat one line **above** `isinstance(tolerance, Quantity)`, so
    a caller passing `25.0` never reached the refusal that names the dimension — they got
    `AttributeError: 'float' object has no attribute 'unit'` from the guard that was
    supposed to be checking them. The order is the fix; this pins it.
    """
    from anvilate.analysis.pressure_vessel import AllowableStress

    allowable = AllowableStress(
        value=Quantity.parse("100 MPa"),
        temperature=Quantity.parse("300 K"),
        material="ASTM-A36",
        source="a test fixture",
    )
    for bare in (25.0, "25 K", 0):
        with pytest.raises(ValueError, match=r"tolerance must be a \[temperature\] quantity"):
            allowable.is_valid_at(Quantity.parse("290 K"), tolerance=bare)
    # And the offset-scale refusal beside it, which had never fired at all. It tested the
    # unit's *spelling* — "degree_Celsius", "degree_Fahrenheit", "deg" — and pint renders
    # those units as "°C" and "°F", which contain none of the three. So the failure the
    # guard was written to prevent was live: a `25 degC` tolerance became a **298 K** band.
    hot = AllowableStress(
        value=Quantity.parse("100 MPa"),
        temperature=Quantity.parse("600 K"),
        material="ASTM-A36",
        source="a test fixture",
    )
    for offset in ("25 degC", "25 degF"):
        with pytest.raises(ValueError, match="temperature DIFFERENCE"):
            hot.is_valid_at(Quantity.parse("500 K"), tolerance=Quantity.parse(offset))
    # The consequence, stated: 500 K is 100 K below a value tabulated at 600 K, and every
    # unit that really is a band width says so.
    for width in ("25 K", "25 delta_degC", "25 degR"):
        assert not hot.is_valid_at(Quantity.parse("500 K"), tolerance=Quantity.parse(width))
    assert allowable.is_valid_at(Quantity.parse("290 K"), tolerance=Quantity.parse("25 K"))


def test_a_parallelogram_linkage_reaches_the_advance_angle_refusal():
    """An excuse this file already carried, and it was wrong.

    The advance-angle guard was described here as "a net rather than a limit" because no
    ordinary crank-rocker comes near 180 degrees. **200,000 random link sets never reached
    it either** — which is not evidence, because the condition is an exact one and a random
    sweep steps over exact conditions.

    Solving it instead: each toggle angle is an `acos`, so both are in [0°, 180°] and their
    difference reaches 180° only when one is 0° and the other 180°. That needs
    ``r4 = |r1 − (r2+r3)|`` and ``r4 = r1 + (r3−r2)`` at once, which gives ``r1 = r2`` and
    ``r3 = r4`` — a **parallelogram**, the linkage whose two extreme positions coincide.
    """
    from anvilate.analysis import fourbar_time_ratio

    def links(ground, crank, coupler, rocker):
        return {
            "ground": Quantity(magnitude=float(ground), unit="mm"),
            "input_link": Quantity(magnitude=float(crank), unit="mm"),
            "coupler": Quantity(magnitude=float(coupler), unit="mm"),
            "output_link": Quantity(magnitude=float(rocker), unit="mm"),
        }

    for ground, coupler in ((60, 100), (50, 80), (45, 120)):
        with pytest.raises(ValueError, match="advance angle must be below 180"):
            fourbar_time_ratio(**links(ground, ground, coupler, coupler))
    # And it really is an isolated point rather than the middle of a region. Move any one
    # link by a millimetre in either direction and the linkage leaves the crank-rocker
    # family altogether — the *toggle-existence* guard answers first, not this one. That is
    # why a random sweep finds nothing: there is no neighbourhood to land in.
    for perturbed in ((60, 60, 100, 99), (60, 60, 100, 101), (60, 61, 100, 100)):
        with pytest.raises(ValueError, match="is not a crank"):
            fourbar_time_ratio(**links(*perturbed))


def test_the_angular_tolerance_table_is_what_makes_its_last_refusal_unreachable():
    """The one cold refusal that cannot be tripped, and the fact it rests on.

    `general.py` walks the ISO 2768-1 angular ranges and raises after the loop if none
    matched. It never can, because the table's last row is open-topped — and *that* is the
    claim worth holding. A data edit closing the top would make the refusal reachable and
    the excuse false, and nothing would have noticed.
    """
    from anvilate.tolerance.general import _angular_table, general_angular_tolerance

    rows = _angular_table()["ranges"]
    assert rows, "the angular table is empty"
    assert rows[-1]["leg_up_to_mm"] is None, (
        "the last ISO 2768-1 angular range is no longer open-topped, so the refusal after "
        "the loop is now reachable and needs a case rather than a comment"
    )
    assert all(row["leg_up_to_mm"] is not None for row in rows[:-1]), (
        "an open top in the middle of the table would end the walk early"
    )
    # And the open top really does answer: a leg far past every stated range still resolves.
    huge = general_angular_tolerance(shorter_leg=Quantity.parse("1e6 mm"), tolerance_class="m")
    assert huge.deviation.to("arcminute").magnitude > 0
