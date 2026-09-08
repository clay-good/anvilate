"""The design-inverse pairing contract: an inverse must land its own forward check.

A design inverse answers "what do I need" — the section modulus for a moment, the wall
for a pressure, the engagement for a load. The contract is that its answer, fed back into
the forward check it inverts, arrives at *exactly* the required margin. Not "better than",
not "close to". Exactly, because that is what turns a repair from a search into a solve,
and because an inverse that overshoots is a silent cost and one that undershoots is a
silent failure.

Each pairing here is hand-verified: the naming conventions across the library are too
varied to infer a pair reliably, and a wrong pairing tested automatically would be worse
than none. The inventory lives in ``docs/api/design-inverses.txt``; the gate that a new
inverse must be entered there is in ``tests/test_contract.py``.
"""

from __future__ import annotations

import pytest

from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


# The inverses this module actually round-trips, declared rather than inferred. The gate
# in tests/test_contract.py reads this set. It used to grep this file's text for the
# inverse's name, which a COMMENT satisfied — an audit slipped a nonsense pairing past it
# with a single "# TODO: round-trip ... someday" line.
ROUND_TRIPPED = frozenset(
    {
        "section.required_section_modulus",
        "axial.required_axial_area",
        "column.euler_second_moment_for_load",
        "torsion.shaft_diameter_for_torque",
        "fastener.bolt_diameter_for_shear",
        "pressure_vessel.thin_wall_thickness_for_pressure",
        "pressure_vessel.asme_b313_pipe_wall_thickness",
        "dynamics.isolator_static_deflection_for_transmissibility",
        "wire_rope.minimum_sheave_diameter_for_bending_stress",
        "fastener.thread_engagement_for_load",
        "control_valve.required_flow_coefficient",
        "machining.spindle_speed_for_cutting_speed",
        "dynamics.natural_frequency_from_deflection",
        "keys.key_length_for_torque",
        "thermal.fin_array_count_for_resistance",
        "bearing.bearing_rating_for_life",
        "brake.band_brake_tight_tension_for_torque",
        "centrifugal_casting.centrifugal_speed_for_g_factor",
        "clutch.disc_clutch_force_for_torque",
        "conveyor.belt_speed_for_capacity",
        "dc_dc_converter.boost_duty_cycle_for_output",
    }
)


def test_required_section_modulus_lands_the_bending_stress_at_the_margin():
    from anvilate.analysis import bending_stress, required_section_modulus

    moment, allowable, required = _q("1500 N*m"), _q("165 MPa"), 1.5
    z = required_section_modulus(
        bending_moment=moment, allowable_stress=allowable, required_safety_factor=required
    )
    stress = bending_stress(moment=moment, section_modulus=z)
    assert allowable.to("MPa").magnitude / stress.to("MPa").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_required_axial_area_lands_the_axial_stress_at_the_margin():
    from anvilate.analysis import axial_stress, required_axial_area

    load, allowable, required = _q("40 kN"), _q("250 MPa"), 2.0
    area = required_axial_area(
        axial_load=load, allowable_stress=allowable, required_safety_factor=required
    )
    stress = axial_stress(force=load, area=area)
    assert allowable.to("MPa").magnitude / stress.to("MPa").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_euler_second_moment_for_load_lands_the_buckling_load_at_the_margin():
    from anvilate.analysis import euler_buckling_load, euler_second_moment_for_load

    design, length, modulus, required = _q("50 kN"), _q("2 m"), _q("200 GPa"), 2.5
    i = euler_second_moment_for_load(
        design_load=design,
        length=length,
        elastic_modulus=modulus,
        required_safety_factor=required,
    )
    capacity = euler_buckling_load(elastic_modulus=modulus, second_moment=i, length=length)
    assert capacity.to("kN").magnitude / design.to("kN").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_shaft_diameter_for_torque_lands_the_torsional_stress_at_the_margin():
    from anvilate.analysis import shaft_diameter_for_torque, shaft_torsional_stress

    torque, allowable, required = _q("400 N*m"), _q("100 MPa"), 2.0
    d = shaft_diameter_for_torque(
        torque=torque, allowable_shear=allowable, required_safety_factor=required
    )
    stress = shaft_torsional_stress(torque=torque, diameter=d)
    assert allowable.to("MPa").magnitude / stress.to("MPa").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_bolt_diameter_for_shear_lands_the_bolt_shear_stress_at_the_margin():
    from anvilate.analysis import bolt_diameter_for_shear, bolt_shear_stress

    load, allowable, planes, required = _q("30 kN"), _q("140 MPa"), 2, 1.5
    d = bolt_diameter_for_shear(
        shear_load=load,
        allowable_shear=allowable,
        shear_planes=planes,
        required_safety_factor=required,
    )
    stress = bolt_shear_stress(force=load, diameter=d, shear_planes=planes)
    assert allowable.to("MPa").magnitude / stress.to("MPa").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_thin_wall_thickness_for_pressure_lands_the_hoop_stress_at_the_margin():
    from anvilate.analysis import thin_wall_cylinder, thin_wall_thickness_for_pressure

    pressure, radius, allowable, required = _q("2 MPa"), _q("300 mm"), _q("140 MPa"), 3.0
    t = thin_wall_thickness_for_pressure(
        pressure=pressure,
        radius=radius,
        allowable_stress=allowable,
        required_safety_factor=required,
    )
    stresses = thin_wall_cylinder(pressure=pressure, radius=radius, wall_thickness=t)
    assert stresses.bending_safety_factor(allowable) == pytest.approx(required, rel=1e-9)


def test_asme_b313_wall_and_its_rating_inverse_round_trip():
    from anvilate.analysis import asme_b313_pipe_pressure, asme_b313_pipe_wall_thickness

    pressure, od, allowable = _q("5 MPa"), _q("114.3 mm"), _q("138 MPa")
    t = asme_b313_pipe_wall_thickness(
        pressure=pressure, outside_diameter=od, allowable_stress=allowable
    )
    rating = asme_b313_pipe_pressure(
        wall_thickness=t, outside_diameter=od, allowable_stress=allowable
    )
    assert rating.to("MPa").magnitude == pytest.approx(pressure.to("MPa").magnitude, rel=1e-9)


def test_isolator_deflection_for_transmissibility_lands_the_target():
    from anvilate.analysis import isolator_static_deflection_for_transmissibility, transmissibility
    from anvilate.analysis.dynamics import natural_frequency_from_deflection
    from anvilate.units.rotation import count_rate_per_second

    forcing, target = _q("24.17 Hz"), 0.1
    delta = isolator_static_deflection_for_transmissibility(
        forcing_frequency=forcing, transmissibility=target
    )
    fn = count_rate_per_second(natural_frequency_from_deflection(delta), name="natural_frequency")
    f = count_rate_per_second(forcing, name="forcing_frequency")
    # The inverse is the undamped one, so the round trip is against zero damping.
    assert transmissibility(frequency_ratio=f / fn, damping_ratio=0.0) == pytest.approx(
        target, rel=1e-9
    )


def test_minimum_sheave_diameter_lands_the_wire_bending_stress_at_its_allowable():
    from anvilate.analysis import (
        minimum_sheave_diameter_for_bending_stress,
        wire_rope_bending_stress,
    )

    wire, modulus, allowable = _q("1.2 mm"), _q("100 GPa"), _q("300 MPa")
    d = minimum_sheave_diameter_for_bending_stress(
        wire_diameter=wire, rope_modulus=modulus, allowable_bending_stress=allowable
    )
    stress = wire_rope_bending_stress(wire_diameter=wire, sheave_diameter=d, rope_modulus=modulus)
    assert stress.to("MPa").magnitude == pytest.approx(allowable.to("MPa").magnitude, rel=1e-9)


def test_thread_engagement_for_load_lands_the_stripping_stress_at_the_margin():
    from anvilate.analysis import thread_engagement_for_load, thread_stripping_stress

    load, d, pitch, allowable, required = (
        _q("20 kN"),
        _q("12 mm"),
        _q("1.75 mm"),
        _q("140 MPa"),
        2.0,
    )
    length = thread_engagement_for_load(
        load=load,
        nominal_diameter=d,
        pitch=pitch,
        allowable_shear=allowable,
        required_safety_factor=required,
    )
    stress = thread_stripping_stress(
        load=load, nominal_diameter=d, pitch=pitch, engagement_length=length
    )
    assert allowable.to("MPa").magnitude / stress.to("MPa").magnitude == pytest.approx(
        required, rel=1e-9
    )


def test_required_flow_coefficient_lands_the_valve_flow_rate():
    from anvilate.analysis import required_flow_coefficient, valve_flow_rate

    flow, drop, sg = _q("20 m**3/hour"), _q("100 kPa"), 1.0
    cv = required_flow_coefficient(flow_rate=flow, pressure_drop=drop, specific_gravity=sg)
    delivered = valve_flow_rate(flow_coefficient=cv, pressure_drop=drop, specific_gravity=sg)
    assert delivered.to("m**3/hour").magnitude == pytest.approx(
        flow.to("m**3/hour").magnitude, rel=1e-9
    )


def test_spindle_speed_for_cutting_speed_round_trips():
    from anvilate.analysis import cutting_speed, spindle_speed_for_cutting_speed

    target, diameter = _q("120 m/min"), _q("25 mm")
    rpm = spindle_speed_for_cutting_speed(cutting_speed=target, diameter=diameter)
    back = cutting_speed(diameter=diameter, spindle_speed=rpm)
    assert back.to("m/min").magnitude == pytest.approx(target.to("m/min").magnitude, rel=1e-9)


def test_natural_frequency_from_deflection_agrees_with_the_stiffness_form():
    from anvilate.analysis import natural_frequency, natural_frequency_from_deflection
    from anvilate.analysis.dynamics import STANDARD_GRAVITY

    # A mass on a spring deflects mg/k under its own weight, and both routes to f_n must
    # give the same answer — the Rayleigh form is the same relation with k eliminated.
    mass, stiffness = _q("50 kg"), _q("200 N/mm")
    delta = Quantity(
        magnitude=mass.to("kg").magnitude
        * STANDARD_GRAVITY.to("m/s**2").magnitude
        / stiffness.to("N/m").magnitude,
        unit="m",
    )
    assert natural_frequency_from_deflection(delta).to("Hz").magnitude == pytest.approx(
        natural_frequency(stiffness=stiffness, mass=mass).to("Hz").magnitude, rel=1e-9
    )


def test_key_length_for_torque_lands_the_governing_key_limit_state():
    from anvilate.analysis import key_length_for_torque, key_shear_stress

    torque, shaft, w, h = _q("300 N*m"), _q("40 mm"), _q("12 mm"), _q("8 mm")
    shear_allow, bearing_allow = _q("60 MPa"), _q("100 MPa")
    requirement = key_length_for_torque(
        torque=torque,
        shaft_diameter=shaft,
        key_width=w,
        key_height=h,
        allowable_shear=shear_allow,
        allowable_bearing=bearing_allow,
    )
    # This inverse returns both limit states and names which governs, so the round trip
    # has two halves: the shear length lands shear exactly at its allowable, and the
    # length actually required is the governing one.
    at_shear = key_shear_stress(
        torque=torque, shaft_diameter=shaft, key_width=w, key_length=requirement.shear_length
    )
    assert at_shear.to("MPa").magnitude == pytest.approx(shear_allow.to("MPa").magnitude, rel=1e-9)
    assert requirement.required_length.to("mm").magnitude == pytest.approx(
        max(
            requirement.shear_length.to("mm").magnitude,
            requirement.bearing_length.to("mm").magnitude,
        ),
        rel=1e-12,
    )
    assert requirement.governing_mode == "bearing"
    # At the governing length the shear stress sits INSIDE its allowable, never past it.
    governing = key_shear_stress(
        torque=torque, shaft_diameter=shaft, key_width=w, key_length=requirement.required_length
    )
    assert governing.to("MPa").magnitude <= shear_allow.to("MPa").magnitude * (1 + 1e-9)


def test_fin_array_count_for_resistance_lands_the_target_array_resistance():
    """This test used to reassemble R = 1/(h·(η·N·A_f + A_base)) by hand.

    Which is the arithmetic under test written a second time, so it could only fail on a
    typo, and the inventory recorded the inverse as pairing with *itself* because the
    forward was not a public symbol. `fin_array_thermal_resistance` is that forward, and
    the round trip now goes through it.
    """
    from anvilate.analysis import fin_array_count_for_resistance, fin_array_thermal_resistance

    target, h = _q("0.5 K/W"), _q("30 W/(m**2*K)")
    fin_area, base_area, efficiency = _q("0.004 m**2"), _q("0.002 m**2"), 0.85
    n = fin_array_count_for_resistance(
        target_resistance=target,
        heat_transfer_coefficient=h,
        fin_efficiency=efficiency,
        fin_surface_area=fin_area,
        unfinned_base_area=base_area,
    )
    resistance = fin_array_thermal_resistance(
        fin_count=n,
        heat_transfer_coefficient=h,
        fin_efficiency=efficiency,
        fin_surface_area=fin_area,
        unfinned_base_area=base_area,
    )
    assert resistance.to("K/W").magnitude == pytest.approx(target.to("K/W").magnitude, rel=1e-12)


def test_bearing_rating_for_life_lands_the_required_life():
    """The selection step: the catalogue C a target L10 needs, fed back through the life."""
    from anvilate.analysis import bearing_basic_rating_life, bearing_rating_for_life

    load, target = _q("8 kN"), 25.0
    rating = bearing_rating_for_life(equivalent_load=load, required_life_millions=target)
    life = bearing_basic_rating_life(dynamic_load_rating=rating, equivalent_load=load)
    assert life == pytest.approx(target, rel=1e-12)

    # And the exponent travels: a roller bearing's 10/3 must be carried by both halves, or
    # the inverse sizes a ball bearing for a roller's life.
    roller = bearing_rating_for_life(
        equivalent_load=load, required_life_millions=target, life_exponent=10.0 / 3.0
    )
    assert bearing_basic_rating_life(
        dynamic_load_rating=roller, equivalent_load=load, life_exponent=10.0 / 3.0
    ) == pytest.approx(target, rel=1e-12)
    assert roller.to("N").magnitude < rating.to("N").magnitude


def test_disc_clutch_force_for_torque_lands_the_required_torque():
    """Both theories, because the inverse takes the same `theory` switch the forward does
    and a pair that only round-trips on the default is half a pair."""
    from anvilate.analysis import disc_clutch_force_for_torque, disc_clutch_torque

    geometry = {
        "outer_radius": _q("120 mm"),
        "inner_radius": _q("70 mm"),
        "friction_coefficient": 0.3,
        "surfaces": 2,
    }
    target = _q("120 N*m")
    for theory in ("uniform_wear", "uniform_pressure"):
        force = disc_clutch_force_for_torque(torque=target, theory=theory, **geometry)
        landed = disc_clutch_torque(actuating_force=force, theory=theory, **geometry)
        assert landed.to("N*m").magnitude == pytest.approx(target.to("N*m").magnitude, rel=1e-12), (
            theory
        )


def test_band_brake_tight_tension_for_torque_lands_the_required_torque():
    from anvilate.analysis import band_brake_tight_tension_for_torque, band_brake_torque

    band = {"drum_diameter": _q("300 mm"), "friction_coefficient": 0.35, "wrap_angle": 3.665}
    target = _q("400 N*m")
    tension = band_brake_tight_tension_for_torque(torque=target, **band)
    assert band_brake_torque(tight_tension=tension, **band).to("N*m").magnitude == pytest.approx(
        target.to("N*m").magnitude, rel=1e-12
    )


def test_belt_speed_for_capacity_lands_the_required_mass_flow():
    from anvilate.analysis import belt_speed_for_capacity, conveyor_mass_flow

    section = {"bulk_density": _q("1400 kg/m**3"), "cross_section_area": _q("0.03 m**2")}
    target = _q("50 t/hour")
    speed = belt_speed_for_capacity(mass_flow=target, **section)
    assert conveyor_mass_flow(belt_speed=speed, **section).to("kg/s").magnitude == pytest.approx(
        target.to("kg/s").magnitude, rel=1e-12
    )


def test_centrifugal_speed_for_g_factor_lands_the_required_g():
    from anvilate.analysis import centrifugal_g_factor, centrifugal_speed_for_g_factor

    radius, target = _q("150 mm"), 75.0
    speed = centrifugal_speed_for_g_factor(g_factor=target, radius=radius)
    assert centrifugal_g_factor(rotational_speed=speed, radius=radius) == pytest.approx(
        target, rel=1e-12
    )


def test_boost_duty_cycle_for_output_lands_the_required_output():
    from anvilate.analysis import boost_duty_cycle_for_output, boost_output_voltage

    supply, target = _q("12 V"), _q("30 V")
    duty = boost_duty_cycle_for_output(input_voltage=supply, output_voltage=target)
    assert boost_output_voltage(input_voltage=supply, duty_cycle=duty).to("V").magnitude == (
        pytest.approx(target.to("V").magnitude, rel=1e-12)
    )
