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
    from anvilate.analysis import fin_array_count_for_resistance

    target, h = _q("0.5 K/W"), _q("30 W/(m**2*K)")
    fin_area, base_area, efficiency = _q("0.004 m**2"), _q("0.002 m**2"), 0.85
    n = fin_array_count_for_resistance(
        target_resistance=target,
        heat_transfer_coefficient=h,
        fin_efficiency=efficiency,
        fin_surface_area=fin_area,
        unfinned_base_area=base_area,
    )
    # R = 1 / (h·(η·N·A_f + A_base)) — reassemble it and confirm the target is reached.
    total = efficiency * n * fin_area.to("m**2").magnitude + base_area.to("m**2").magnitude
    resistance = 1.0 / (h.to("W/(m**2*K)").magnitude * total)
    assert resistance == pytest.approx(target.to("K/W").magnitude, rel=1e-9)
