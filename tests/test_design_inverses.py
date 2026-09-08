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
        "dc_dc_converter.buck_boost_duty_cycle_for_output",
        "dc_dc_converter.buck_duty_cycle_for_output",
        "electroplating.electroplating_time_for_thickness",
        "fastener.torque_for_preload",
        "hydro_power.hydro_flow_for_power",
        "level_turn.bank_angle_for_load_factor",
        "mass_energy.mass_from_energy",
        "photon.photon_wavelength_from_energy",
        "radiation_shielding.shield_thickness_for_transmission",
        "radioactivity.time_for_activity_decay",
        "reactive_circuit.capacitance_for_reactance",
        "reactive_circuit.inductance_for_reactance",
        "reinforced_concrete.rc_stirrup_spacing_for_shear",
        "reinforced_concrete.rc_tension_steel_for_moment",
        "screw_conveyor.screw_conveyor_speed_for_capacity",
        "spectroscopy.concentration_from_absorbance",
        "spring.helical_spring_active_coils_for_rate",
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


def test_torque_for_preload_lands_the_required_preload():
    """The two halves of the nut-factor relation, each listed as a candidate against the
    other. Both take the nut factor, and it is the whole content of the relation: a pair
    that round-trips only on the 0.2 default proves the algebra and not the plumbing."""
    from anvilate.analysis import bolt_preload_from_torque, torque_for_preload

    diameter, target = _q("12 mm"), _q("30 kN")
    for nut_factor in (0.2, 0.15, 0.28):
        torque = torque_for_preload(
            preload=target, nominal_diameter=diameter, nut_factor=nut_factor
        )
        preload = bolt_preload_from_torque(
            torque=torque, nominal_diameter=diameter, nut_factor=nut_factor
        )
        assert preload.to("kN").magnitude == pytest.approx(target.to("kN").magnitude, rel=1e-12), (
            nut_factor
        )
    # A lower nut factor is a slipperier joint: less torque for the same preload.
    assert (
        torque_for_preload(preload=target, nominal_diameter=diameter, nut_factor=0.15)
        .to("N*m")
        .magnitude
        < torque_for_preload(preload=target, nominal_diameter=diameter, nut_factor=0.28)
        .to("N*m")
        .magnitude
    )


def test_buck_duty_cycle_for_output_lands_the_required_output():
    """One pair per test, and that is not a style choice.

    The contract ratchet requires *some single test* to name both halves of each recorded
    pairing, which is how it catches a pairing rewritten to an unrelated forward. Testing
    the buck and the buck-boost together named all four symbols in one function, so
    pairing `buck_duty_cycle_for_output` to `buck_boost_output_voltage` — a real mistake,
    the two sit beside each other in the module — stayed green. Split, it fails.
    """
    from anvilate.analysis import buck_duty_cycle_for_output, buck_output_voltage

    supply, target = _q("24 V"), _q("5 V")
    duty = buck_duty_cycle_for_output(input_voltage=supply, output_voltage=target)
    assert buck_output_voltage(input_voltage=supply, duty_cycle=duty).to("V").magnitude == (
        pytest.approx(target.to("V").magnitude, rel=1e-12)
    )
    # A buck steps down, so its duty cycle is the output over the input.
    assert duty == pytest.approx(5.0 / 24.0, rel=1e-12)


def test_buck_boost_duty_cycle_for_output_lands_the_required_output():
    from anvilate.analysis import buck_boost_duty_cycle_for_output, buck_boost_output_voltage

    supply, target = _q("12 V"), _q("18 V")
    duty = buck_boost_duty_cycle_for_output(input_voltage=supply, output_voltage=target)
    assert buck_boost_output_voltage(input_voltage=supply, duty_cycle=duty).to(
        "V"
    ).magnitude == pytest.approx(target.to("V").magnitude, rel=1e-12)
    # Stepping 12 V up to 18 V needs D/(1-D) = 1.5, so D = 0.6 — above the half that a
    # buck's duty cycle for the same ratio would sit below.
    assert duty == pytest.approx(0.6, rel=1e-12)


def test_bank_angle_for_load_factor_lands_the_required_load_factor():
    """The classic pair: a 2 g level turn is 60 degrees of bank, exactly."""
    from anvilate.analysis import bank_angle_for_load_factor, load_factor_from_bank_angle

    for target in (1.5, 2.0, 4.0):
        bank = bank_angle_for_load_factor(load_factor=target)
        assert load_factor_from_bank_angle(bank_angle=bank) == pytest.approx(target, rel=1e-12)
    assert bank_angle_for_load_factor(load_factor=2.0) == pytest.approx(60.0, rel=1e-12)


def test_photon_wavelength_from_energy_lands_the_required_energy():
    from anvilate.analysis import photon_energy, photon_wavelength_from_energy

    target = _q("2.5 eV")
    wavelength = photon_wavelength_from_energy(energy=target)
    assert photon_energy(wavelength=wavelength).to("eV").magnitude == pytest.approx(
        target.to("eV").magnitude, rel=1e-12
    )


def test_mass_from_energy_lands_the_required_rest_energy():
    from anvilate.analysis import mass_from_energy, rest_energy

    target = _q("1 MeV")
    mass = mass_from_energy(energy=target)
    assert rest_energy(mass=mass).to("MeV").magnitude == pytest.approx(
        target.to("MeV").magnitude, rel=1e-12
    )


def test_hydro_flow_for_power_lands_the_required_power():
    from anvilate.analysis import hydro_flow_for_power, hydro_turbine_power

    site = {
        "net_head": _q("40 m"),
        "overall_efficiency": 0.88,
        "fluid_density": _q("998 kg/m**3"),
    }
    target = _q("500 kW")
    flow = hydro_flow_for_power(target_power=target, **site)
    assert hydro_turbine_power(flow_rate=flow, **site).to("kW").magnitude == pytest.approx(
        target.to("kW").magnitude, rel=1e-12
    )


def test_electroplating_time_for_thickness_lands_the_required_thickness():
    from anvilate.analysis import (
        electroplating_deposition_thickness,
        electroplating_time_for_thickness,
    )

    bath = {
        "current": _q("12 A"),
        "plated_area": _q("0.25 m**2"),
        "equivalent_weight": 32.7,
        "density": _q("8960 kg/m**3"),
        "current_efficiency": 0.95,
    }
    target = _q("25 um")
    plating_time = electroplating_time_for_thickness(target_thickness=target, **bath)
    assert electroplating_deposition_thickness(plating_time=plating_time, **bath).to(
        "um"
    ).magnitude == pytest.approx(target.to("um").magnitude, rel=1e-12)


def test_rc_tension_steel_for_moment_lands_the_required_moment():
    """The reinforcement a required moment needs, fed back through the nominal moment.

    A_s enters M_n twice — once directly and once through the stress-block depth a =
    A_s·f_y/(0.85·f'_c·b) — so an inverse that solves the linear part and forgets the
    quadratic lands close and not on. Exactly is the contract.
    """
    from anvilate.analysis import rc_beam_nominal_moment, rc_tension_steel_for_moment

    beam = {
        "steel_yield": _q("420 MPa"),
        "concrete_strength": _q("30 MPa"),
        "beam_width": _q("300 mm"),
        "effective_depth": _q("450 mm"),
    }
    target = _q("250 kN*m")
    steel = rc_tension_steel_for_moment(required_moment=target, **beam)
    assert rc_beam_nominal_moment(steel_area=steel, **beam).to("kN*m").magnitude == pytest.approx(
        target.to("kN*m").magnitude, rel=1e-12
    )


def test_rc_stirrup_spacing_for_shear_lands_the_required_shear_strength():
    from anvilate.analysis import rc_shear_reinforcement_strength, rc_stirrup_spacing_for_shear

    stirrups = {
        "stirrup_area": _q("142 mm**2"),
        "stirrup_yield": _q("420 MPa"),
        "effective_depth": _q("450 mm"),
    }
    target = _q("180 kN")
    spacing = rc_stirrup_spacing_for_shear(required_shear_strength=target, **stirrups)
    assert rc_shear_reinforcement_strength(stirrup_spacing=spacing, **stirrups).to(
        "kN"
    ).magnitude == pytest.approx(target.to("kN").magnitude, rel=1e-12)
    # Closer stirrups carry more, so a larger demand must come back with a tighter spacing.
    tighter = rc_stirrup_spacing_for_shear(required_shear_strength=_q("260 kN"), **stirrups)
    assert tighter.to("mm").magnitude < spacing.to("mm").magnitude


def test_helical_spring_active_coils_for_rate_lands_the_required_rate():
    from anvilate.analysis import helical_spring_active_coils_for_rate, helical_spring_rate

    wire = {
        "mean_coil_diameter": _q("30 mm"),
        "wire_diameter": _q("4 mm"),
        "shear_modulus": _q("79.3 GPa"),
    }
    target = _q("12 N/mm")
    coils = helical_spring_active_coils_for_rate(target_rate=target, **wire)
    assert helical_spring_rate(active_coils=coils, **wire).to("N/mm").magnitude == pytest.approx(
        target.to("N/mm").magnitude, rel=1e-12
    )
    # The rate goes as 1/N, so a stiffer spring is a shorter stack of active coils.
    assert helical_spring_active_coils_for_rate(target_rate=_q("24 N/mm"), **wire) < coils


def test_capacitance_for_reactance_lands_the_required_reactance():
    from anvilate.analysis import capacitance_for_reactance, capacitive_reactance

    frequency, target = _q("60 Hz"), _q("50 ohm")
    capacitance = capacitance_for_reactance(reactance=target, frequency=frequency)
    assert capacitive_reactance(capacitance=capacitance, frequency=frequency).to(
        "ohm"
    ).magnitude == pytest.approx(target.to("ohm").magnitude, rel=1e-12)


def test_inductance_for_reactance_lands_the_required_reactance():
    """Separate from the capacitive pair on purpose: both inverses take the same two
    arguments and differ only in which way the frequency divides, so one test naming all
    four symbols would let the two pairings be swapped without failing."""
    from anvilate.analysis import inductance_for_reactance, inductive_reactance

    frequency, target = _q("60 Hz"), _q("50 ohm")
    inductance = inductance_for_reactance(reactance=target, frequency=frequency)
    assert inductive_reactance(inductance=inductance, frequency=frequency).to(
        "ohm"
    ).magnitude == pytest.approx(target.to("ohm").magnitude, rel=1e-12)


def test_concentration_from_absorbance_lands_the_required_absorbance():
    from anvilate.analysis import absorbance, concentration_from_absorbance

    cell = {"molar_absorptivity": _q("15000 L/(mol*cm)"), "path_length": _q("1 cm")}
    target = 0.65
    concentration = concentration_from_absorbance(absorbance=target, **cell)
    assert absorbance(concentration=concentration, **cell) == pytest.approx(target, rel=1e-12)


def test_shield_thickness_for_transmission_lands_the_required_transmission():
    from anvilate.analysis import radiation_transmission_fraction, shield_thickness_for_transmission

    mu, target = _q("0.15 1/cm"), 0.1
    thickness = shield_thickness_for_transmission(
        attenuation_coefficient=mu, transmission_fraction=target
    )
    assert radiation_transmission_fraction(
        attenuation_coefficient=mu, thickness=thickness
    ) == pytest.approx(target, rel=1e-12)


def test_screw_conveyor_speed_for_capacity_lands_the_required_capacity():
    from anvilate.analysis import (
        screw_conveyor_speed_for_capacity,
        screw_conveyor_volumetric_capacity,
    )

    screw = {
        "screw_diameter": _q("250 mm"),
        "shaft_diameter": _q("60 mm"),
        "pitch": _q("250 mm"),
        "fill_fraction": 0.35,
    }
    target = _q("0.02 m**3/s")
    speed = screw_conveyor_speed_for_capacity(volumetric_capacity=target, **screw)
    assert screw_conveyor_volumetric_capacity(rotational_speed=speed, **screw).to(
        "m**3/s"
    ).magnitude == pytest.approx(target.to("m**3/s").magnitude, rel=1e-12)


def test_time_for_activity_decay_lands_the_required_activity():
    from anvilate.analysis import remaining_activity, time_for_activity_decay

    initial, target, half_life = _q("100 MBq"), _q("25 MBq"), _q("6 hour")
    elapsed = time_for_activity_decay(
        initial_activity=initial, final_activity=target, half_life=half_life
    )
    assert remaining_activity(
        initial_activity=initial, half_life=half_life, elapsed_time=elapsed
    ).to("MBq").magnitude == pytest.approx(target.to("MBq").magnitude, rel=1e-12)
    # A quarter of the activity is exactly two half-lives.
    assert elapsed.to("hour").magnitude == pytest.approx(12.0, rel=1e-12)
