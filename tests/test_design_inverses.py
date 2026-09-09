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
        "weld.fillet_weld_leg_for_load",
        "gear.lewis_module_for_bending_stress",
        "gear.agma_module_for_bending_stress",
        "gear.gear_module_for_center_distance",
        "plate.clamped_circular_plate_thickness_for_pressure",
        "wear.sliding_distance_for_wear_depth",
        "reliability.weibull_life_for_reliability",
        "fatigue.basquin_stress_for_life",
        "welding_heat.weld_travel_speed_for_heat_input",
        "flow_measurement.differential_pressure_for_flow",
        "ventilation.airflow_for_air_changes",
        "rectifier.filter_capacitance_for_ripple",
        "thermal.heat_exchanger_area_for_duty",
        "thermal.counterflow_ntu_for_effectiveness",
        "thermal.parallel_flow_ntu_for_effectiveness",
        "thermal.shell_and_tube_ntu_for_effectiveness",
        "beam.fastener_spacing_for_shear_flow",
        "interference.interference_for_contact_pressure",
        "dynamics.isolator_natural_frequency_for_transmissibility",
        "energy_storage.current_from_c_rate",
        "open_channel.minimum_specific_energy_rectangular",
        "rocket_propulsion.thrust_from_coefficient",
        "level_turn.bank_angle_for_turn_rate",
        "projectile.projectile_launch_angle_for_range",
        "transmission_line.reflection_coefficient_from_vswr",
        "torsion.shaft_diameter_for_bending_torsion",
        "accumulator.accumulator_size_for_volume",
        "antenna.dish_diameter_for_gain",
        "beam.aisc_bearing_length_for_web_yielding",
        "belt.belt_tight_tension_for_power",
        "cam.cam_base_circle_for_pressure_angle",
        "chain.minimum_sprocket_teeth_for_chordal_variation",
        "dynamics.damping_ratio_from_log_decrement",
        "electrical.line_current_for_power",
        "fire_protection.sprinkler_pressure_for_flow",
        "flywheel.flywheel_inertia_for_fluctuation",
        "gaussian_beam.beam_waist_for_divergence",
        "machining.feed_for_surface_roughness",
        "pipe_flow.hagen_poiseuille_radius_for_flow",
        "thermal.wien_temperature_from_peak",
        "piezoelectric.piezoelectric_force_from_charge",
        "wave.frequency_from_wavelength",
        "wave.wavelength_from_frequency",
        "torsion.torque_from_power",
        "torsion.power_from_torque",
        "level_turn.load_factor_from_bank_angle",
        "momentum.coefficient_of_restitution_from_rebound",
        "radar.radial_velocity_from_doppler",
        "acoustics.doppler_velocity_from_shift",
        "optical_interference.wavelength_from_fringe_spacing",
        "hall_effect.hall_flux_density_from_voltage",
        "cyclotron.cyclotron_mass_from_frequency",
        "polarization.malus_angle_for_intensity",
        "strain_gauge.strain_from_bridge_output",
        "photometry.luminous_flux_from_power",
        "combustion.equivalence_ratio_from_excess_air",
        "dynamics.damping_ratio_from_half_power_bandwidth",
        "radioactivity.decay_constant_from_half_life",
        "energy_storage.discharge_time_from_c_rate",
        "acid_base.buffer_ratio_for_ph",
        "bulk_solids.beverloo_orifice_for_rate",
        "drilling.drilling_feed_for_torque_limit",
        "hall_petch.hall_petch_grain_diameter_for_yield",
        "illumination.illuminance_for_target_luminance",
        "injection_molding.max_projected_area_for_clamp",
        "living_hinge.living_hinge_web_length_for_strain",
        "pneumatics.air_receiver_volume_for_demand",
        "resistance_welding.spot_weld_current_for_heat",
        "shear_spinning.shear_spinning_half_angle_for_thickness",
        "shot_peening.peening_time_for_coverage",
        "solar_pv.pv_array_size_for_load",
        "temperature_sensor.thermocouple_temperature_from_voltage",
        "thermoforming.thermoforming_sheet_gauge_for_wall",
        "quantum.minimum_position_uncertainty",
        "electrical.capacitance_for_reactive_power",
        "fastener.bolt_preload_from_torque",
        "battery_peukert.peukert_exponent_from_two_rates",
        "reaction_kinetics.first_order_time_for_conversion",
        "dc_dc_converter.buck_minimum_inductance_for_ccm",
        "thermal.fouling_factor_from_coefficients",
        "belt.belt_speed_for_max_power",
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


def test_fillet_weld_leg_for_load_lands_the_allowable_throat_shear():
    """The leg a load needs, fed back through the throat stress it was sized against.

    The safety factor is the half a pairing can quietly drop: at SF = 1 the two formulas
    round-trip whether or not the inverse ever read it, so the margin is exercised here
    and the answer has to land at the allowable *divided by* it.
    """
    from anvilate.analysis import fillet_weld_leg_for_load, fillet_weld_throat_stress

    joint = {"force": _q("240 kN"), "length": _q("400 mm")}
    allowable, margin = _q("124 MPa"), 1.6
    leg = fillet_weld_leg_for_load(
        allowable_shear=allowable, required_safety_factor=margin, **joint
    )
    assert fillet_weld_throat_stress(leg_size=leg, **joint).to("MPa").magnitude == pytest.approx(
        allowable.to("MPa").magnitude / margin, rel=1e-12
    )
    # And at SF = 1 it lands on the allowable itself, which is the sizing contract.
    unmargined = fillet_weld_leg_for_load(allowable_shear=allowable, **joint)
    assert fillet_weld_throat_stress(leg_size=unmargined, **joint).to(
        "MPa"
    ).magnitude == pytest.approx(allowable.to("MPa").magnitude, rel=1e-12)


def test_lewis_module_for_bending_stress_lands_the_allowable_root_stress():
    from anvilate.analysis import lewis_bending_stress, lewis_module_for_bending_stress

    tooth = {
        "tangential_load": _q("3.2 kN"),
        "face_width": _q("40 mm"),
        "form_factor": 0.322,
    }
    allowable = _q("120 MPa")
    module = lewis_module_for_bending_stress(allowable_stress=allowable, **tooth)
    assert lewis_bending_stress(module=module, **tooth).to("MPa").magnitude == pytest.approx(
        allowable.to("MPa").magnitude, rel=1e-12
    )
    # A coarser tooth is a stronger one: halving the allowable stress doubles the module.
    softer = lewis_module_for_bending_stress(allowable_stress=_q("60 MPa"), **tooth)
    assert softer.to("mm").magnitude == pytest.approx(2.0 * module.to("mm").magnitude, rel=1e-12)


def test_agma_module_for_bending_stress_carries_every_derating_factor():
    """All five derating factors default to 1.0, so a pairing that dropped them would
    still round-trip on the defaults. Each is set away from 1 here, and the module is
    checked to have actually moved because of them."""
    from anvilate.analysis import agma_bending_stress, agma_module_for_bending_stress

    mesh = {
        "tangential_load": _q("3.2 kN"),
        "face_width": _q("40 mm"),
        "geometry_factor": 0.38,
    }
    derating = {
        "overload_factor": 1.25,
        "dynamic_factor": 1.4,
        "size_factor": 1.05,
        "load_distribution_factor": 1.3,
        "rim_thickness_factor": 1.1,
    }
    allowable = _q("210 MPa")
    module = agma_module_for_bending_stress(allowable_stress=allowable, **mesh, **derating)
    assert agma_bending_stress(module=module, **mesh, **derating).to(
        "MPa"
    ).magnitude == pytest.approx(allowable.to("MPa").magnitude, rel=1e-12)
    # The derating is the whole difference between this and the Lewis-shaped sizing.
    undertated = agma_module_for_bending_stress(allowable_stress=allowable, **mesh)
    assert undertated.to("mm").magnitude < module.to("mm").magnitude


def test_gear_module_for_center_distance_lands_the_housing_centre():
    from anvilate.analysis import gear_center_distance, gear_module_for_center_distance

    teeth = {"pinion_teeth": 19, "gear_teeth": 61}
    center = _q("200 mm")
    module = gear_module_for_center_distance(center_distance=center, **teeth)
    assert gear_center_distance(module=module, **teeth).to("mm").magnitude == pytest.approx(
        center.to("mm").magnitude, rel=1e-12
    )
    # 2·200/80 is a standard 5 mm module, which is the point of asking the question.
    assert module.to("mm").magnitude == pytest.approx(5.0, rel=1e-12)
    # More teeth into the same centre distance is a finer module.
    finer = gear_module_for_center_distance(center_distance=center, pinion_teeth=25, gear_teeth=75)
    assert finer.to("mm").magnitude < module.to("mm").magnitude


def test_clamped_circular_plate_thickness_lands_the_allowable_rim_stress():
    from anvilate.analysis import (
        clamped_circular_plate_thickness_for_pressure,
        clamped_circular_plate_uniform_load,
    )

    cover = {"pressure": _q("0.4 MPa"), "diameter": _q("600 mm")}
    allowable, margin = _q("165 MPa"), 1.5
    thickness = clamped_circular_plate_thickness_for_pressure(
        allowable_stress=allowable, required_safety_factor=margin, **cover
    )
    result = clamped_circular_plate_uniform_load(
        thickness=thickness, elastic_modulus=_q("200 GPa"), **cover
    )
    assert result.max_bending_stress.to("MPa").magnitude == pytest.approx(
        allowable.to("MPa").magnitude / margin, rel=1e-12
    )
    # The sizing is a strength one and the forward carries the stiffness seam with it,
    # so the round trip is only meaningful while thin-plate theory still applies.
    assert result.is_small_deflection


def test_sliding_distance_for_wear_depth_lands_the_wear_allowance():
    from anvilate.analysis import archard_wear_depth, sliding_distance_for_wear_depth

    contact = {
        "wear_coefficient": 1.2e-4,
        "contact_pressure": _q("2.5 MPa"),
        "hardness": _q("1.9 GPa"),
    }
    allowance = _q("0.5 mm")
    distance = sliding_distance_for_wear_depth(allowable_depth=allowance, **contact)
    assert archard_wear_depth(sliding_distance=distance, **contact).to(
        "mm"
    ).magnitude == pytest.approx(allowance.to("mm").magnitude, rel=1e-12)
    # Wear is linear in distance, so twice the allowance is twice the life.
    doubled = sliding_distance_for_wear_depth(allowable_depth=_q("1 mm"), **contact)
    assert doubled.to("m").magnitude == pytest.approx(2.0 * distance.to("m").magnitude, rel=1e-12)


def test_weibull_life_for_reliability_lands_the_survival_fraction():
    from anvilate.analysis import weibull_life_for_reliability, weibull_reliability

    population = {"characteristic_life": _q("8000 hour"), "shape": 1.8}
    target = 0.90
    life = weibull_life_for_reliability(reliability=target, **population)
    assert weibull_reliability(time=life, **population) == pytest.approx(target, rel=1e-12)
    # R = 1/e returns the characteristic life exactly, for any shape — which is what
    # makes eta "characteristic". Checked at a different beta so the anchor is not the
    # round trip again in disguise.
    from math import e

    anchor = weibull_life_for_reliability(
        reliability=1.0 / e, characteristic_life=_q("8000 hour"), shape=3.4
    )
    assert anchor.to("hour").magnitude == pytest.approx(8000.0, rel=1e-12)


def test_basquin_stress_for_life_lands_the_target_life():
    from anvilate.analysis import basquin_cycles_to_failure, basquin_stress_for_life

    curve = {"coefficient": _q("1200 MPa"), "exponent": -0.085}
    target = 5.0e5
    amplitude = basquin_stress_for_life(life_cycles=target, **curve)
    assert basquin_cycles_to_failure(stress_amplitude=amplitude, **curve) == pytest.approx(
        target, rel=1e-9
    )
    # A longer target life is a lower allowable amplitude (b is negative).
    assert (
        basquin_stress_for_life(life_cycles=5.0e6, **curve).to("MPa").magnitude
        < amplitude.to("MPa").magnitude
    )


def test_weld_travel_speed_for_heat_input_lands_the_qualified_heat_input():
    """The thermal efficiency defaults to 1.0, so it is set to a real process value here
    — a pair that round-trips only on the default is half a pair."""
    from anvilate.analysis import weld_heat_input, weld_travel_speed_for_heat_input

    arc = {
        "arc_voltage": _q("26 V"),
        "welding_current": _q("240 A"),
        "thermal_efficiency": 0.8,
    }
    target = _q("1.2 kJ/mm")
    speed = weld_travel_speed_for_heat_input(heat_input=target, **arc)
    assert weld_heat_input(travel_speed=speed, **arc).to("kJ/mm").magnitude == pytest.approx(
        target.to("kJ/mm").magnitude, rel=1e-12
    )
    # Faster travel is less heat into the joint, which is the control a welder has.
    cooler = weld_travel_speed_for_heat_input(heat_input=_q("0.8 kJ/mm"), **arc)
    assert cooler.to("mm/s").magnitude > speed.to("mm/s").magnitude


def test_differential_pressure_for_flow_lands_the_meter_reading():
    from anvilate.analysis import differential_pressure_for_flow, obstruction_meter_flow_rate

    meter = {
        "discharge_coefficient": 0.61,
        "throat_diameter": _q("50 mm"),
        "pipe_diameter": _q("100 mm"),
        "density": _q("998 kg/m**3"),
    }
    target = _q("0.012 m**3/s")
    drop = differential_pressure_for_flow(flow_rate=target, **meter)
    assert obstruction_meter_flow_rate(pressure_drop=drop, **meter).to(
        "m**3/s"
    ).magnitude == pytest.approx(target.to("m**3/s").magnitude, rel=1e-12)
    # Delta-p goes as Q squared, so doubling the flow quadruples the transmitter range.
    quadrupled = differential_pressure_for_flow(flow_rate=_q("0.024 m**3/s"), **meter)
    assert quadrupled.to("kPa").magnitude == pytest.approx(
        4.0 * drop.to("kPa").magnitude, rel=1e-12
    )


def test_airflow_for_air_changes_lands_the_required_change_rate():
    from anvilate.analysis import air_changes_per_hour, airflow_for_air_changes

    room = _q("200 m**3")
    target = 6.0
    airflow = airflow_for_air_changes(air_changes_per_hour=target, room_volume=room)
    assert air_changes_per_hour(airflow=airflow, room_volume=room) == pytest.approx(
        target, rel=1e-12
    )
    # The docstring's own worked example: six changes an hour in 200 m³ is 1,200 m³/h.
    assert airflow.to("m**3/hour").magnitude == pytest.approx(1200.0, rel=1e-12)


def test_filter_capacitance_for_ripple_lands_the_target_ripple():
    from anvilate.analysis import capacitor_filter_ripple_voltage, filter_capacitance_for_ripple

    supply = {"load_current": _q("1.5 A"), "frequency": _q("60 Hz")}
    target = _q("1.2 V")
    capacitance = filter_capacitance_for_ripple(ripple_voltage=target, **supply)
    assert capacitor_filter_ripple_voltage(capacitance=capacitance, **supply).to(
        "V"
    ).magnitude == pytest.approx(target.to("V").magnitude, rel=1e-12)
    # Halving the ripple doubles the capacitor, which is why tight ripple gets expensive.
    tighter = filter_capacitance_for_ripple(ripple_voltage=_q("0.6 V"), **supply)
    assert tighter.to("F").magnitude == pytest.approx(
        2.0 * capacitance.to("F").magnitude, rel=1e-12
    )


def test_heat_exchanger_area_for_duty_lands_the_required_duty():
    from anvilate.analysis import heat_exchanger_area_for_duty, heat_exchanger_duty

    service = {
        "overall_coefficient": _q("850 W/(m**2*K)"),
        "log_mean_temperature_difference": _q("24 delta_degC"),
    }
    target = _q("450 kW")
    area = heat_exchanger_area_for_duty(duty=target, **service)
    assert heat_exchanger_duty(area=area, **service).to("kW").magnitude == pytest.approx(
        target.to("kW").magnitude, rel=1e-12
    )


def test_counterflow_ntu_for_effectiveness_lands_every_branch():
    """Three closed forms hide behind one signature — C_r = 1, C_r = 0, and the general
    case — so a round trip at one capacity ratio leaves two of them unchecked."""
    from anvilate.analysis import counterflow_effectiveness, counterflow_ntu_for_effectiveness

    for capacity_ratio in (0.0, 0.45, 1.0):
        target = 0.72
        ntu = counterflow_ntu_for_effectiveness(effectiveness=target, capacity_ratio=capacity_ratio)
        assert counterflow_effectiveness(ntu=ntu, capacity_ratio=capacity_ratio) == pytest.approx(
            target, rel=1e-12
        )
    # A balanced exchanger is the hardest to make effective, so it needs the most size.
    assert counterflow_ntu_for_effectiveness(
        effectiveness=0.72, capacity_ratio=1.0
    ) > counterflow_ntu_for_effectiveness(effectiveness=0.72, capacity_ratio=0.0)


def test_parallel_flow_ntu_for_effectiveness_lands_the_target_effectiveness():
    from anvilate.analysis import (
        parallel_flow_effectiveness,
        parallel_flow_ntu_for_effectiveness,
    )

    for capacity_ratio in (0.0, 0.45):
        target = 0.55
        ntu = parallel_flow_ntu_for_effectiveness(
            effectiveness=target, capacity_ratio=capacity_ratio
        )
        assert parallel_flow_effectiveness(ntu=ntu, capacity_ratio=capacity_ratio) == pytest.approx(
            target, rel=1e-12
        )


def test_shell_and_tube_ntu_for_effectiveness_lands_the_target_effectiveness():
    from anvilate.analysis import (
        shell_and_tube_effectiveness,
        shell_and_tube_ntu_for_effectiveness,
    )

    for capacity_ratio in (0.0, 0.45):
        target = 0.55
        ntu = shell_and_tube_ntu_for_effectiveness(
            effectiveness=target, capacity_ratio=capacity_ratio
        )
        assert shell_and_tube_effectiveness(
            ntu=ntu, capacity_ratio=capacity_ratio
        ) == pytest.approx(target, rel=1e-12)
    # One shell pass has a ceiling the counterflow form does not, and the sizing form
    # refuses above it rather than returning a size that cannot work.
    with pytest.raises(ValueError, match="one shell pass cannot exceed"):
        shell_and_tube_ntu_for_effectiveness(effectiveness=0.9, capacity_ratio=0.45)


def test_fastener_spacing_for_shear_flow_carries_the_flow_the_beam_develops():
    """The spacing is sized against a flow the *forward* computes, so the pair is the join:
    the fasteners at that spacing carry exactly the flow at that section, no more."""
    from anvilate.analysis import fastener_spacing_for_shear_flow, shear_flow

    section = {
        "shear_force": _q("60 kN"),
        "first_moment_of_area": _q("450000 mm**3"),
        "second_moment_of_area": _q("120000000 mm**4"),
    }
    capacity = _q("18 kN")
    flow = shear_flow(**section)
    spacing = fastener_spacing_for_shear_flow(fastener_capacity=capacity, shear_flow=flow)
    assert (flow.to("N/mm").magnitude * spacing.to("mm").magnitude) == pytest.approx(
        capacity.to("N").magnitude, rel=1e-12
    )
    # Twice the capacity per fastener is twice the spacing, which is the sizing lever.
    assert fastener_spacing_for_shear_flow(fastener_capacity=_q("36 kN"), shear_flow=flow).to(
        "mm"
    ).magnitude == pytest.approx(2.0 * spacing.to("mm").magnitude, rel=1e-12)


def test_interference_for_contact_pressure_lands_the_required_contact_pressure():
    from anvilate.analysis import interference_fit, interference_for_contact_pressure

    joint = {
        "interface_diameter": _q("60 mm"),
        "hub_outer_diameter": _q("110 mm"),
        "hub_modulus": _q("200 GPa"),
        "hub_poisson": 0.3,
        "shaft_modulus": _q("200 GPa"),
        "shaft_poisson": 0.3,
    }
    target = _q("45 MPa")
    interference = interference_for_contact_pressure(contact_pressure=target, **joint)
    assert interference_fit(radial_interference=interference, **joint).contact_pressure.to(
        "MPa"
    ).magnitude == pytest.approx(target.to("MPa").magnitude, rel=1e-12)


def test_isolator_natural_frequency_for_transmissibility_lands_the_isolation():
    """The mount is sized in the undamped isolation region, so the round trip has to be
    taken there — at a damping ratio of zero, which is the assumption the inverse makes."""
    from anvilate.analysis import (
        isolator_natural_frequency_for_transmissibility,
        transmissibility,
    )

    forcing, target = _q("50 Hz"), 0.08
    natural = isolator_natural_frequency_for_transmissibility(
        forcing_frequency=forcing, transmissibility=target
    )
    ratio = forcing.to("Hz").magnitude / natural.to("Hz").magnitude
    assert transmissibility(frequency_ratio=ratio, damping_ratio=0.0) == pytest.approx(
        target, rel=1e-12
    )
    # Better isolation is a softer mount, which is the whole design move.
    softer = isolator_natural_frequency_for_transmissibility(
        forcing_frequency=forcing, transmissibility=0.02
    )
    assert softer.to("Hz").magnitude < natural.to("Hz").magnitude


def test_current_from_c_rate_lands_the_required_c_rate():
    from anvilate.analysis import c_rate, current_from_c_rate

    capacity = _q("100 A*hour")
    target = 0.5
    current = current_from_c_rate(c_rate=target, capacity=capacity)
    assert c_rate(current=current, capacity=capacity) == pytest.approx(target, rel=1e-12)
    # C/2 on a 100 Ah cell is 50 A, which is what makes the rate a useful shorthand.
    assert current.to("A").magnitude == pytest.approx(50.0, rel=1e-12)


def test_minimum_specific_energy_rectangular_is_the_energy_at_critical_depth():
    """E_min is the specific energy the channel has *at* its critical depth, so the pair
    is checked by computing that depth and asking the forward what the energy there is."""
    from anvilate.analysis import (
        critical_depth_rectangular,
        minimum_specific_energy_rectangular,
        specific_energy,
    )

    channel = {"flow_rate": _q("12 m**3/s"), "channel_width": _q("4 m")}
    minimum = minimum_specific_energy_rectangular(**channel)
    depth = critical_depth_rectangular(**channel)
    area = channel["channel_width"].to("m").magnitude * depth.to("m").magnitude
    velocity = Quantity(magnitude=channel["flow_rate"].to("m**3/s").magnitude / area, unit="m/s")
    assert specific_energy(depth=depth, velocity=velocity).to("m").magnitude == pytest.approx(
        minimum.to("m").magnitude, rel=1e-12
    )
    # And it is exactly 3/2 of the critical depth, which is what "minimum" means here.
    assert minimum.to("m").magnitude == pytest.approx(1.5 * depth.to("m").magnitude, rel=1e-12)


def test_thrust_from_coefficient_lands_the_coefficient_it_was_given():
    from anvilate.analysis import thrust_coefficient, thrust_from_coefficient

    nozzle = {"chamber_pressure": _q("6 MPa"), "throat_area": _q("0.02 m**2")}
    target = 1.55
    thrust = thrust_from_coefficient(thrust_coefficient=target, **nozzle)
    assert thrust_coefficient(thrust=thrust, **nozzle) == pytest.approx(target, rel=1e-12)


def test_bank_angle_for_turn_rate_lands_the_required_turn_rate():
    from anvilate.analysis import bank_angle_for_turn_rate, turn_rate

    speed, target = _q("120 m/s"), _q("3 deg/s")
    bank = bank_angle_for_turn_rate(speed=speed, turn_rate=target)
    assert turn_rate(speed=speed, bank_angle=bank).to("deg/s").magnitude == pytest.approx(
        target.to("deg/s").magnitude, rel=1e-12
    )
    # A tighter turn at the same speed needs more bank.
    assert bank_angle_for_turn_rate(speed=speed, turn_rate=_q("6 deg/s")) > bank


def test_projectile_launch_angle_for_range_lands_the_range_on_both_roots():
    """Every range short of the maximum is reachable at two angles, and the inverse takes
    a switch to pick. Both have to land it: a pair tested only on the default is half a
    pair, and the high root is the one an artillery or a water-jet problem actually wants."""
    from anvilate.analysis import projectile_launch_angle_for_range, projectile_range

    speed, target = _q("40 m/s"), _q("120 m")
    low = projectile_launch_angle_for_range(launch_speed=speed, target_range=target)
    high = projectile_launch_angle_for_range(
        launch_speed=speed, target_range=target, high_trajectory=True
    )
    for angle in (low, high):
        assert projectile_range(launch_speed=speed, launch_angle=angle).to(
            "m"
        ).magnitude == pytest.approx(target.to("m").magnitude, rel=1e-12)
    # The two roots straddle 45°, and they are complementary.
    assert low < 45.0 < high
    assert low + high == pytest.approx(90.0, rel=1e-12)


def test_reflection_coefficient_from_vswr_lands_the_standing_wave_ratio():
    from anvilate.analysis import reflection_coefficient_from_vswr, voltage_standing_wave_ratio

    target = 2.5
    gamma = reflection_coefficient_from_vswr(voltage_standing_wave_ratio=target)
    assert voltage_standing_wave_ratio(reflection_coefficient=gamma) == pytest.approx(
        target, rel=1e-12
    )
    # A perfect match is a VSWR of 1 and no reflection at all.
    assert reflection_coefficient_from_vswr(voltage_standing_wave_ratio=1.0) == pytest.approx(
        0.0, abs=1e-15
    )


def test_shaft_diameter_for_bending_torsion_lands_the_allowable_von_mises_stress():
    from anvilate.analysis import shaft_diameter_for_bending_torsion, shaft_von_mises_stress

    loads = {"bending_moment": _q("450 N*m"), "torque": _q("620 N*m")}
    yield_strength, margin = _q("530 MPa"), 2.0
    diameter = shaft_diameter_for_bending_torsion(
        yield_strength=yield_strength, required_safety_factor=margin, **loads
    )
    assert shaft_von_mises_stress(diameter=diameter, **loads).to("MPa").magnitude == pytest.approx(
        yield_strength.to("MPa").magnitude / margin, rel=1e-12
    )


def test_accumulator_size_for_volume_lands_the_usable_volume():
    from anvilate.analysis import accumulator_size_for_volume, accumulator_usable_volume

    circuit = {
        "precharge_pressure": _q("90 bar"),
        "minimum_pressure": _q("120 bar"),
        "maximum_pressure": _q("210 bar"),
        "polytropic_exponent": 1.4,
    }
    target = _q("1.2 L")
    size = accumulator_size_for_volume(required_volume=target, **circuit)
    assert accumulator_usable_volume(total_volume=size, **circuit).to(
        "L"
    ).magnitude == pytest.approx(target.to("L").magnitude, rel=1e-12)


def test_dish_diameter_for_gain_lands_the_required_gain():
    """The aperture efficiency defaults to 1.0, so it is set to a real dish value — a pair
    that round-trips only on a perfect aperture is half a pair."""
    from math import pi

    from anvilate.analysis import aperture_antenna_gain, dish_diameter_for_gain

    wavelength, efficiency = _q("0.03 m"), 0.6
    target = 10000.0
    diameter = dish_diameter_for_gain(gain=target, wavelength=wavelength, efficiency=efficiency)
    area = _q(f"{pi / 4.0 * diameter.to('m').magnitude ** 2} m**2")
    assert aperture_antenna_gain(
        aperture_area=area, wavelength=wavelength, efficiency=efficiency
    ) == pytest.approx(target, rel=1e-12)


def test_aisc_bearing_length_for_web_yielding_lands_the_required_reaction():
    """`at_member_end` changes the constant (2.5k vs 5k), so both branches round-trip here:
    a pair tested only at the interior is half a pair, and the end is the governing case."""
    from anvilate.analysis import (
        aisc_bearing_length_for_web_yielding,
        aisc_web_local_yielding_strength,
    )

    web = {
        "web_yield": _q("345 MPa"),
        "web_thickness": _q("10 mm"),
        "fillet_distance": _q("30 mm"),
    }
    # Above the clamp on both branches: the web alone spreads 517.5 kN at the interior and
    # 258.75 kN at the end, and below that there is no bearing length to solve for.
    target = _q("800 kN")
    for at_end in (False, True):
        length = aisc_bearing_length_for_web_yielding(
            required_reaction=target, at_member_end=at_end, **web
        )
        assert aisc_web_local_yielding_strength(
            bearing_length=length, at_member_end=at_end, **web
        ).to("kN").magnitude == pytest.approx(target.to("kN").magnitude, rel=1e-12)
    # And the documented exception to "exactly": a reaction the fillet spread already
    # carries needs no bearing length, so the answer clamps to zero and the forward comes
    # back HIGHER than asked rather than on it.
    none_needed = aisc_bearing_length_for_web_yielding(
        required_reaction=_q("400 kN"), at_member_end=False, **web
    )
    assert none_needed.to("mm").magnitude == 0.0
    assert aisc_web_local_yielding_strength(
        bearing_length=none_needed, at_member_end=False, **web
    ).to("kN").magnitude == pytest.approx(517.5, rel=1e-12)
    # The end has less web to spread into, so it needs the longer bearing.
    at_end = aisc_bearing_length_for_web_yielding(
        required_reaction=target, at_member_end=True, **web
    )
    interior = aisc_bearing_length_for_web_yielding(
        required_reaction=target, at_member_end=False, **web
    )
    assert at_end.to("mm").magnitude > interior.to("mm").magnitude


def test_belt_tight_tension_for_power_lands_the_transmitted_power():
    """The forward takes both tensions and the inverse returns only the tight side, so the
    slack side is taken from the library's own `belt_slack_tension` rather than
    reassembled here from e^(mu*theta)."""
    from anvilate.analysis import (
        belt_slack_tension,
        belt_tight_tension_for_power,
        belt_transmitted_power,
    )

    drive = {"friction_coefficient": 0.35, "wrap_angle": 2.9}
    speed, target = _q("18 m/s"), _q("15 kW")
    tight = belt_tight_tension_for_power(power=target, belt_speed=speed, **drive)
    slack = belt_slack_tension(tight_tension=tight, **drive)
    assert belt_transmitted_power(tight_tension=tight, slack_tension=slack, belt_speed=speed).to(
        "kW"
    ).magnitude == pytest.approx(target.to("kW").magnitude, rel=1e-12)


def test_cam_base_circle_for_pressure_angle_lands_the_peak_pressure_angle():
    from anvilate.analysis import cam_base_circle_for_pressure_angle, cam_pressure_angle

    motion = {"lift_gradient": _q("14 mm/rad"), "follower_displacement": _q("8 mm")}
    target = 28.0
    radius = cam_base_circle_for_pressure_angle(max_pressure_angle=target, **motion)
    assert cam_pressure_angle(base_circle_radius=radius, **motion).to(
        "deg"
    ).magnitude == pytest.approx(target, rel=1e-12)
    # Enlarging the base circle is the fix the docstring names, so a tighter limit is a
    # bigger cam.
    assert (
        cam_base_circle_for_pressure_angle(max_pressure_angle=20.0, **motion).to("mm").magnitude
        > radius.to("mm").magnitude
    )


def test_minimum_sprocket_teeth_for_chordal_variation_is_the_least_count_that_holds():
    """An integer inverse cannot land exactly, so the contract is the *least* count that
    meets the limit: it holds at N and fails at N − 1. An off-by-one that rounds the wrong
    way satisfies "holds at N" on its own."""
    from anvilate.analysis import (
        chordal_speed_variation,
        minimum_sprocket_teeth_for_chordal_variation,
    )

    target = 0.015
    teeth = minimum_sprocket_teeth_for_chordal_variation(max_variation=target)
    assert chordal_speed_variation(sprocket_teeth=teeth) <= target
    assert chordal_speed_variation(sprocket_teeth=teeth - 1) > target


def test_damping_ratio_from_log_decrement_lands_the_decrement():
    from anvilate.analysis import damping_ratio_from_log_decrement, logarithmic_decrement

    target = 0.42
    zeta = damping_ratio_from_log_decrement(log_decrement=target)
    assert logarithmic_decrement(damping_ratio=zeta) == pytest.approx(target, rel=1e-12)


def test_line_current_for_power_lands_the_three_phase_power():
    from anvilate.analysis import line_current_for_power, three_phase_power

    supply = {"line_voltage": _q("400 V"), "power_factor": 0.87}
    target = _q("22 kW")
    current = line_current_for_power(real_power=target, **supply)
    assert three_phase_power(line_current=current, **supply).to("kW").magnitude == pytest.approx(
        target.to("kW").magnitude, rel=1e-12
    )


def test_sprinkler_pressure_for_flow_lands_the_required_discharge():
    from anvilate.analysis import sprinkler_discharge, sprinkler_pressure_for_flow

    k_factor = _q("80 L/(min*bar**0.5)")
    target = _q("120 L/min")
    pressure = sprinkler_pressure_for_flow(k_factor=k_factor, flow_rate=target)
    assert sprinkler_discharge(k_factor=k_factor, pressure=pressure).to(
        "L/min"
    ).magnitude == pytest.approx(target.to("L/min").magnitude, rel=1e-12)
    # Flow goes as the square root of pressure, so doubling the flow is four times the head.
    quadrupled = sprinkler_pressure_for_flow(k_factor=k_factor, flow_rate=_q("240 L/min"))
    assert quadrupled.to("bar").magnitude == pytest.approx(
        4.0 * pressure.to("bar").magnitude, rel=1e-12
    )


def test_flywheel_inertia_for_fluctuation_lands_the_energy_swing():
    from anvilate.analysis import flywheel_energy_fluctuation, flywheel_inertia_for_fluctuation

    duty = {"mean_speed": _q("450 rpm"), "coefficient_of_fluctuation": 0.02}
    target = _q("2400 J")
    inertia = flywheel_inertia_for_fluctuation(energy_fluctuation=target, **duty)
    assert flywheel_energy_fluctuation(inertia=inertia, **duty).to("J").magnitude == pytest.approx(
        target.to("J").magnitude, rel=1e-12
    )
    # A tighter speed ripple costs inertia in inverse proportion.
    tighter = flywheel_inertia_for_fluctuation(
        energy_fluctuation=target, mean_speed=_q("450 rpm"), coefficient_of_fluctuation=0.01
    )
    assert tighter.to("kg*m**2").magnitude == pytest.approx(
        2.0 * inertia.to("kg*m**2").magnitude, rel=1e-12
    )


def test_beam_waist_for_divergence_lands_the_divergence():
    from anvilate.analysis import beam_divergence_half_angle, beam_waist_for_divergence

    wavelength, target = _q("1064 nm"), 0.002
    waist = beam_waist_for_divergence(divergence_half_angle=target, wavelength=wavelength)
    assert beam_divergence_half_angle(beam_waist=waist, wavelength=wavelength) == pytest.approx(
        target, rel=1e-12
    )


def test_feed_for_surface_roughness_lands_the_target_roughness():
    from anvilate.analysis import feed_for_surface_roughness, theoretical_surface_roughness

    nose = _q("0.8 mm")
    target = _q("3.2 um")
    feed = feed_for_surface_roughness(target_roughness=target, tool_nose_radius=nose)
    assert theoretical_surface_roughness(feed=feed, tool_nose_radius=nose).to(
        "um"
    ).magnitude == pytest.approx(target.to("um").magnitude, rel=1e-12)


def test_hagen_poiseuille_radius_for_flow_lands_the_required_flow():
    from anvilate.analysis import hagen_poiseuille_flow_rate, hagen_poiseuille_radius_for_flow

    line = {
        "pressure_drop": _q("40 kPa"),
        "viscosity": _q("0.001 Pa*s"),
        "length": _q("2 m"),
    }
    target = _q("5 mL/s")
    radius = hagen_poiseuille_radius_for_flow(flow_rate=target, **line)
    assert hagen_poiseuille_flow_rate(radius=radius, **line).to("mL/s").magnitude == pytest.approx(
        target.to("mL/s").magnitude, rel=1e-12
    )


def test_wien_temperature_from_peak_lands_the_peak_wavelength():
    from anvilate.analysis import wien_peak_wavelength, wien_temperature_from_peak

    target = _q("500 nm")
    temperature = wien_temperature_from_peak(peak_wavelength=target)
    assert wien_peak_wavelength(temperature=temperature).to("nm").magnitude == pytest.approx(
        target.to("nm").magnitude, rel=1e-12
    )


def test_piezoelectric_force_from_charge_lands_the_charge():
    from anvilate.analysis import piezoelectric_charge, piezoelectric_force_from_charge

    coefficient = _q("300 pC/N")
    target = _q("15 nC")
    force = piezoelectric_force_from_charge(charge=target, charge_coefficient=coefficient)
    assert piezoelectric_charge(force=force, charge_coefficient=coefficient).to(
        "nC"
    ).magnitude == pytest.approx(target.to("nC").magnitude, rel=1e-12)


def test_frequency_from_wavelength_lands_the_wave_speed():
    from anvilate.analysis import frequency_from_wavelength, wave_speed

    medium, wavelength = _q("1500 m/s"), _q("3 m")
    frequency = frequency_from_wavelength(wavelength=wavelength, wave_speed=medium)
    assert wave_speed(frequency=frequency, wavelength=wavelength).to(
        "m/s"
    ).magnitude == pytest.approx(medium.to("m/s").magnitude, rel=1e-12)


def test_wavelength_from_frequency_lands_the_wave_speed():
    from anvilate.analysis import wave_speed, wavelength_from_frequency

    medium, frequency = _q("343 m/s"), _q("440 Hz")
    wavelength = wavelength_from_frequency(frequency=frequency, wave_speed=medium)
    assert wave_speed(frequency=frequency, wavelength=wavelength).to(
        "m/s"
    ).magnitude == pytest.approx(medium.to("m/s").magnitude, rel=1e-12)
    # Wavelength is inverse in frequency at a fixed speed: an octave up is half as long.
    octave = wavelength_from_frequency(frequency=_q("880 Hz"), wave_speed=medium)
    assert octave.to("mm").magnitude == pytest.approx(
        0.5 * wavelength.to("mm").magnitude, rel=1e-12
    )


def test_torque_from_power_and_power_from_torque_invert_each_other():
    """The two halves of P = T·ω are each other's forward, so the pair is round-tripped in
    both directions — an error in either one alone breaks both assertions."""
    from anvilate.analysis import power_from_torque, torque_from_power

    speed = _q("1750 rpm")
    power = _q("15 kW")
    torque = torque_from_power(power=power, rotational_speed=speed)
    assert power_from_torque(torque=torque, rotational_speed=speed).to(
        "kW"
    ).magnitude == pytest.approx(power.to("kW").magnitude, rel=1e-12)

    delivered = power_from_torque(torque=_q("80 N*m"), rotational_speed=speed)
    assert torque_from_power(power=delivered, rotational_speed=speed).to(
        "N*m"
    ).magnitude == pytest.approx(80.0, rel=1e-12)
    # Torque for a fixed power goes inversely with speed: half the shaft speed, twice the torque.
    halved = torque_from_power(power=power, rotational_speed=_q("875 rpm"))
    assert halved.to("N*m").magnitude == pytest.approx(2.0 * torque.to("N*m").magnitude, rel=1e-12)


def test_load_factor_from_bank_angle_lands_the_bank_angle():
    """Both halves speak degrees, not radians — a 60 degree bank is the textbook 2 g, and
    reading the pair in radians would have it at 1.0001 g and still round-trip."""
    from anvilate.analysis import bank_angle_for_load_factor, load_factor_from_bank_angle

    bank = 60.0
    load_factor = load_factor_from_bank_angle(bank_angle=bank)
    assert load_factor == pytest.approx(2.0, rel=1e-12)
    assert bank_angle_for_load_factor(load_factor=load_factor) == pytest.approx(bank, rel=1e-12)


def test_coefficient_of_restitution_from_rebound_lands_the_rebound_height():
    from anvilate.analysis import coefficient_of_restitution_from_rebound, rebound_height

    drop, bounce = _q("1.2 m"), _q("0.75 m")
    restitution = coefficient_of_restitution_from_rebound(drop_height=drop, rebound_height=bounce)
    assert rebound_height(drop_height=drop, coefficient_of_restitution=restitution).to(
        "mm"
    ).magnitude == pytest.approx(bounce.to("mm").magnitude, rel=1e-12)


def test_radial_velocity_from_doppler_lands_the_doppler_shift():
    from anvilate.analysis import radar_doppler_shift, radial_velocity_from_doppler

    transmit, shift = _q("10 GHz"), _q("1.5 kHz")
    velocity = radial_velocity_from_doppler(transmit_frequency=transmit, doppler_shift=shift)
    assert radar_doppler_shift(transmit_frequency=transmit, radial_velocity=velocity).to(
        "kHz"
    ).magnitude == pytest.approx(shift.to("kHz").magnitude, rel=1e-12)


def test_doppler_velocity_from_shift_lands_the_shifted_frequency():
    """The acoustic inverse solves for the SOURCE speed with the observer at rest, so the
    forward has to be called with a zero observer velocity for the pair to close."""
    from anvilate.analysis import doppler_shifted_frequency, doppler_velocity_from_shift

    emitted, heard, sound = _q("1000 Hz"), _q("1080 Hz"), _q("343 m/s")
    source_speed = doppler_velocity_from_shift(
        source_frequency=emitted, observed_frequency=heard, speed_of_sound=sound
    )
    assert doppler_shifted_frequency(
        source_frequency=emitted,
        speed_of_sound=sound,
        source_velocity=source_speed,
        observer_velocity=_q("0 m/s"),
    ).to("Hz").magnitude == pytest.approx(heard.to("Hz").magnitude, rel=1e-12)
    # A pitch drop is a receding source, so the recovered closing speed is negative.
    receding = doppler_velocity_from_shift(
        source_frequency=emitted, observed_frequency=_q("940 Hz"), speed_of_sound=sound
    )
    assert receding.to("m/s").magnitude < 0.0


def test_wavelength_from_fringe_spacing_lands_the_fringe_spacing():
    from anvilate.analysis import double_slit_fringe_spacing, wavelength_from_fringe_spacing

    bench = {"slit_separation": _q("0.25 mm"), "screen_distance": _q("1.8 m")}
    spacing = _q("4.2 mm")
    wavelength = wavelength_from_fringe_spacing(fringe_spacing=spacing, **bench)
    assert double_slit_fringe_spacing(wavelength=wavelength, **bench).to(
        "mm"
    ).magnitude == pytest.approx(spacing.to("mm").magnitude, rel=1e-12)


def test_hall_flux_density_from_voltage_lands_the_hall_voltage():
    from anvilate.analysis import hall_flux_density_from_voltage, hall_voltage

    element = {
        "current": _q("5 mA"),
        "carrier_density": _q("1e22 1/m**3"),
        "thickness": _q("50 um"),
    }
    reading = _q("2.4 mV")
    flux = hall_flux_density_from_voltage(hall_voltage=reading, **element)
    assert hall_voltage(flux_density=flux, **element).to("mV").magnitude == pytest.approx(
        reading.to("mV").magnitude, rel=1e-12
    )


def test_cyclotron_mass_from_frequency_lands_the_cyclotron_frequency():
    from anvilate.analysis import cyclotron_frequency, cyclotron_mass_from_frequency

    ion = {"charge": _q("1.602176634e-19 C"), "magnetic_flux_density": _q("7 T")}
    orbit = _q("1.2 MHz")
    mass = cyclotron_mass_from_frequency(frequency=orbit, **ion)
    assert cyclotron_frequency(mass=mass, **ion).to("MHz").magnitude == pytest.approx(
        orbit.to("MHz").magnitude, rel=1e-12
    )


def test_malus_angle_for_intensity_lands_the_transmitted_intensity():
    """arccos has two roots per period; the inverse must return the one in [0, pi/2] that
    an analyzer is actually set to, and the forward has to land on it."""
    from math import pi

    from anvilate.analysis import malus_angle_for_intensity, malus_transmitted_intensity

    incident, target = _q("10 W/m**2"), _q("2.5 W/m**2")
    angle = malus_angle_for_intensity(incident_intensity=incident, transmitted_intensity=target)
    assert 0.0 <= angle <= pi / 2.0
    assert angle == pytest.approx(pi / 3.0, rel=1e-12)
    assert malus_transmitted_intensity(incident_intensity=incident, angle=angle).to(
        "W/m**2"
    ).magnitude == pytest.approx(target.to("W/m**2").magnitude, rel=1e-12)


def test_strain_from_bridge_output_lands_the_bridge_reading():
    from anvilate.analysis import strain_from_bridge_output, wheatstone_bridge_output

    bridge = {"gauge_factor": 2.1, "active_arms": 2}
    reading = 1.4e-3
    strain = strain_from_bridge_output(output_ratio=reading, **bridge)
    assert wheatstone_bridge_output(strain=strain, **bridge) == pytest.approx(reading, rel=1e-12)
    # The arm count is load-bearing: a full bridge reads the same strain at half the microstrain.
    full = strain_from_bridge_output(output_ratio=reading, gauge_factor=2.1, active_arms=4)
    assert full == pytest.approx(0.5 * strain, rel=1e-12)


def test_luminous_flux_from_power_lands_the_efficacy():
    from anvilate.analysis import luminous_efficacy, luminous_flux_from_power

    power, efficacy = _q("18 W"), _q("115 lm/W")
    flux = luminous_flux_from_power(electrical_power=power, luminous_efficacy=efficacy)
    assert luminous_efficacy(luminous_flux=flux, electrical_power=power).to(
        "lm/W"
    ).magnitude == pytest.approx(efficacy.to("lm/W").magnitude, rel=1e-12)


def test_equivalence_ratio_from_excess_air_lands_the_air_fuel_equivalence_ratio():
    """The excess-air form and the air-fuel-ratio form must agree, and the actual ratio is
    taken from the public sibling rather than rebuilt as stoich*(1 + EA) here."""
    from anvilate.analysis import (
        actual_air_fuel_ratio,
        equivalence_ratio,
        equivalence_ratio_from_excess_air,
    )

    stoichiometric, excess_air = 17.2, 0.2
    phi = equivalence_ratio_from_excess_air(excess_air_fraction=excess_air)
    actual = actual_air_fuel_ratio(
        stoichiometric_air_fuel_ratio=stoichiometric, excess_air_fraction=excess_air
    )
    assert equivalence_ratio(
        stoichiometric_air_fuel_ratio=stoichiometric, actual_air_fuel_ratio=actual
    ) == pytest.approx(phi, rel=1e-12)
    # No excess air is stoichiometric, whichever way it is stated.
    assert equivalence_ratio_from_excess_air(excess_air_fraction=0.0) == pytest.approx(1.0)


def test_damping_ratio_from_half_power_bandwidth_lands_the_quality_factor():
    """The half-power measurement gives Q and zeta from the same two frequencies, and the
    two readings have to be the same resonance: Q = 1/(2*zeta)."""
    from anvilate.analysis import (
        damping_ratio_from_half_power_bandwidth,
        quality_factor,
        quality_factor_from_half_power_bandwidth,
    )

    peak = {"resonant_frequency": _q("25 Hz"), "half_power_bandwidth": _q("1.2 Hz")}
    zeta = damping_ratio_from_half_power_bandwidth(**peak)
    assert quality_factor(damping_ratio=zeta) == pytest.approx(
        quality_factor_from_half_power_bandwidth(**peak), rel=1e-12
    )


def test_decay_constant_from_half_life_lands_the_mean_lifetime_activity():
    """The decay constant is the reciprocal of the mean lifetime, so at t = 1/lambda the
    decay law must have taken the source to exactly A0/e."""
    from math import e

    from anvilate.analysis import decay_constant_from_half_life, remaining_activity

    half_life = _q("5.27 year")
    decay_constant = decay_constant_from_half_life(half_life=half_life)
    mean_lifetime = Quantity(
        magnitude=1.0 / decay_constant.to("1/s").magnitude,
        unit="s",
    )
    initial = _q("40 GBq")
    assert remaining_activity(
        initial_activity=initial, elapsed_time=mean_lifetime, half_life=half_life
    ).to("GBq").magnitude == pytest.approx(initial.to("GBq").magnitude / e, rel=1e-12)


def test_discharge_time_from_c_rate_lands_the_rated_capacity():
    """The ideal runtime is the time in which the C-rate current removes exactly the rated
    capacity, so the charge drawn over it reads back as the same C-rate."""
    from anvilate.analysis import c_rate, current_from_c_rate, discharge_time_from_c_rate

    capacity = _q("100 A*h")
    rate = 0.5
    runtime = discharge_time_from_c_rate(c_rate=rate)
    current = current_from_c_rate(c_rate=rate, capacity=capacity)
    drawn = Quantity(
        magnitude=current.to("A").magnitude * runtime.to("hour").magnitude,
        unit="A*h",
    )
    assert drawn.to("A*h").magnitude == pytest.approx(capacity.to("A*h").magnitude, rel=1e-12)
    assert c_rate(current=current, capacity=drawn) == pytest.approx(rate, rel=1e-12)


def test_buffer_ratio_for_ph_lands_the_henderson_hasselbalch_ph():
    """The inverse returns a RATIO, so the round trip picks an acid concentration and
    scales it — which is what the ratio means, not a rebuild of the formula."""
    from anvilate.analysis import buffer_ratio_for_ph, henderson_hasselbalch_ph

    pka, target = 4.76, 5.5
    ratio = buffer_ratio_for_ph(pka=pka, ph=target)
    acid = _q("0.1 mol/L")
    base = Quantity(magnitude=ratio * acid.to("mol/L").magnitude, unit="mol/L")
    assert henderson_hasselbalch_ph(
        pka=pka, conjugate_base_concentration=base, weak_acid_concentration=acid
    ) == pytest.approx(target, rel=1e-12)
    # A pH at the pKa is the 1:1 buffer, whatever the acid.
    assert buffer_ratio_for_ph(pka=pka, ph=pka) == pytest.approx(1.0, rel=1e-12)


def test_beverloo_orifice_for_rate_lands_the_discharge_rate():
    from anvilate.analysis import beverloo_discharge_rate, beverloo_orifice_for_rate

    material = {"particle_diameter": _q("3 mm"), "bulk_density": _q("780 kg/m**3")}
    target = _q("2.5 kg/s")
    orifice = beverloo_orifice_for_rate(mass_flow=target, **material)
    assert beverloo_discharge_rate(orifice_diameter=orifice, **material).to(
        "kg/s"
    ).magnitude == pytest.approx(target.to("kg/s").magnitude, rel=1e-12)
    # The shape factor is not decoration: it moves the answer, so it must be carried.
    blunt = beverloo_orifice_for_rate(mass_flow=target, shape_factor=2.0, **material)
    assert blunt.to("mm").magnitude > orifice.to("mm").magnitude


def test_drilling_feed_for_torque_limit_lands_the_torque_limit():
    from anvilate.analysis import drilling_feed_for_torque_limit, drilling_torque

    job = {"specific_cutting_energy": _q("2.1 GPa"), "drill_diameter": _q("12 mm")}
    limit = _q("18 N*m")
    feed = drilling_feed_for_torque_limit(torque_limit=limit, **job)
    assert drilling_torque(feed_per_revolution=feed, **job).to("N*m").magnitude == pytest.approx(
        limit.to("N*m").magnitude, rel=1e-12
    )
    # The d**2 is the whole point: twice the drill, a quarter of the feed at the same torque.
    bigger = drilling_feed_for_torque_limit(
        torque_limit=limit,
        specific_cutting_energy=_q("2.1 GPa"),
        drill_diameter=_q("24 mm"),
    )
    assert bigger.to("mm").magnitude == pytest.approx(0.25 * feed.to("mm").magnitude, rel=1e-12)


def test_hall_petch_grain_diameter_for_yield_lands_the_yield_strength():
    from anvilate.analysis import hall_petch_grain_diameter_for_yield, hall_petch_yield_strength

    material = {
        "friction_stress": _q("70 MPa"),
        "strengthening_coefficient": _q("0.6 MPa*m**0.5"),
    }
    target = _q("250 MPa")
    grain = hall_petch_grain_diameter_for_yield(yield_strength=target, **material)
    assert hall_petch_yield_strength(grain_diameter=grain, **material).to(
        "MPa"
    ).magnitude == pytest.approx(target.to("MPa").magnitude, rel=1e-12)


def test_illuminance_for_target_luminance_lands_the_surface_luminance():
    from anvilate.analysis import diffuse_surface_luminance, illuminance_for_target_luminance

    reflectance = 0.55
    target = _q("120 cd/m**2")
    illuminance = illuminance_for_target_luminance(target_luminance=target, reflectance=reflectance)
    assert diffuse_surface_luminance(illuminance=illuminance, reflectance=reflectance).to(
        "cd/m**2"
    ).magnitude == pytest.approx(target.to("cd/m**2").magnitude, rel=1e-12)
    # A darker finish costs light in inverse proportion to its reflectance.
    dark = illuminance_for_target_luminance(target_luminance=target, reflectance=0.11)
    assert dark.to("lux").magnitude == pytest.approx(
        5.0 * illuminance.to("lux").magnitude, rel=1e-12
    )


def test_max_projected_area_for_clamp_lands_the_clamp_force():
    from anvilate.analysis import injection_clamp_force, max_projected_area_for_clamp

    pressure = _q("35 MPa")
    tonnage = _q("2500 kN")
    area = max_projected_area_for_clamp(clamp_force=tonnage, cavity_pressure=pressure)
    assert injection_clamp_force(projected_area=area, cavity_pressure=pressure).to(
        "kN"
    ).magnitude == pytest.approx(tonnage.to("kN").magnitude, rel=1e-12)


def test_living_hinge_web_length_for_strain_lands_the_fold_strain():
    from anvilate.analysis import living_hinge_fold_strain, living_hinge_web_length_for_strain

    hinge = {"web_thickness": _q("0.4 mm"), "fold_angle": 90.0}
    permissible = 0.06
    length = living_hinge_web_length_for_strain(permissible_strain=permissible, **hinge)
    assert living_hinge_fold_strain(web_length=length, **hinge) == pytest.approx(
        permissible, rel=1e-12
    )
    # The fold angle is carried, not defaulted away: a full 180 degree fold needs twice the web.
    flat = living_hinge_web_length_for_strain(
        web_thickness=_q("0.4 mm"), permissible_strain=permissible, fold_angle=180.0
    )
    assert flat.to("mm").magnitude == pytest.approx(2.0 * length.to("mm").magnitude, rel=1e-12)


def test_air_receiver_volume_for_demand_lands_the_holdup_time():
    from anvilate.analysis import air_receiver_holdup_time, air_receiver_volume_for_demand

    system = {
        "net_demand": _q("1.8 m**3/min"),
        "max_pressure": _q("8 bar"),
        "min_pressure": _q("6 bar"),
        "atmospheric_pressure": _q("101.325 kPa"),
    }
    target = _q("45 s")
    volume = air_receiver_volume_for_demand(holdup_time=target, **system)
    assert air_receiver_holdup_time(receiver_volume=volume, **system).to(
        "s"
    ).magnitude == pytest.approx(target.to("s").magnitude, rel=1e-12)


def test_spot_weld_current_for_heat_lands_the_joule_heat():
    from anvilate.analysis import spot_weld_current_for_heat, spot_weld_heat_generated

    schedule = {"contact_resistance": _q("100 uohm"), "weld_time": _q("0.2 s")}
    target = _q("900 J")
    current = spot_weld_current_for_heat(target_heat=target, **schedule)
    assert spot_weld_heat_generated(weld_current=current, **schedule).to(
        "J"
    ).magnitude == pytest.approx(target.to("J").magnitude, rel=1e-12)
    # Heat is quadratic in current, so a quarter of the weld time costs only twice the amps.
    quicker = spot_weld_current_for_heat(
        target_heat=target, contact_resistance=_q("100 uohm"), weld_time=_q("0.05 s")
    )
    assert quicker.to("kA").magnitude == pytest.approx(2.0 * current.to("kA").magnitude, rel=1e-12)


def test_shear_spinning_half_angle_for_thickness_lands_the_spun_wall():
    from anvilate.analysis import (
        shear_spinning_half_angle_for_thickness,
        shear_spinning_wall_thickness,
    )

    blank, target = _q("6 mm"), _q("3 mm")
    angle = shear_spinning_half_angle_for_thickness(blank_thickness=blank, final_thickness=target)
    assert angle == pytest.approx(30.0, rel=1e-12)
    assert shear_spinning_wall_thickness(blank_thickness=blank, half_cone_angle=angle).to(
        "mm"
    ).magnitude == pytest.approx(target.to("mm").magnitude, rel=1e-12)


def test_peening_time_for_coverage_lands_the_coverage():
    from anvilate.analysis import peening_coverage, peening_time_for_coverage

    rate = _q("0.15 1/s")
    target = 0.98
    exposure = peening_time_for_coverage(coverage_rate=rate, target_coverage=target)
    assert peening_coverage(coverage_rate=rate, exposure_time=exposure) == pytest.approx(
        target, rel=1e-12
    )
    # The law is asymptotic: the last two points of coverage cost as long again as the first 98.
    doubled = peening_time_for_coverage(coverage_rate=rate, target_coverage=0.9996)
    assert doubled.to("s").magnitude == pytest.approx(2.0 * exposure.to("s").magnitude, rel=1e-9)


def test_pv_array_size_for_load_lands_the_daily_energy():
    from anvilate.analysis import pv_array_size_for_load, pv_daily_energy

    site = {"peak_sun_hours": _q("4.6 hour"), "derate_factor": 0.78}
    target = _q("18 kW*hour")
    rating = pv_array_size_for_load(daily_energy_demand=target, **site)
    assert pv_daily_energy(rated_power=rating, **site).to("kW*hour").magnitude == pytest.approx(
        target.to("kW*hour").magnitude, rel=1e-12
    )


def test_thermocouple_temperature_from_voltage_lands_the_seebeck_emf():
    """The cold junction is the whole trick: the pair only closes if the inverse adds the
    reference temperature back, so the test puts the reference well away from zero."""
    from anvilate.analysis import thermocouple_temperature_from_voltage, thermocouple_voltage

    junction = {
        "seebeck_coefficient": _q("41 uV/K"),
        "reference_temperature": _q("298.15 K"),
    }
    reading = _q("12.5 mV")
    temperature = thermocouple_temperature_from_voltage(thermocouple_voltage=reading, **junction)
    assert thermocouple_voltage(measured_temperature=temperature, **junction).to(
        "mV"
    ).magnitude == pytest.approx(reading.to("mV").magnitude, rel=1e-12)
    # A zero EMF is the cold junction's own temperature, not absolute zero.
    assert thermocouple_temperature_from_voltage(thermocouple_voltage=_q("0 mV"), **junction).to(
        "K"
    ).magnitude == pytest.approx(298.15, rel=1e-12)


def test_thermoforming_sheet_gauge_for_wall_lands_the_average_wall():
    from anvilate.analysis import (
        thermoforming_average_wall_thickness,
        thermoforming_sheet_gauge_for_wall,
    )

    draw = 3.4
    target = _q("0.9 mm")
    gauge = thermoforming_sheet_gauge_for_wall(minimum_wall_thickness=target, areal_draw_ratio=draw)
    assert thermoforming_average_wall_thickness(sheet_thickness=gauge, areal_draw_ratio=draw).to(
        "mm"
    ).magnitude == pytest.approx(target.to("mm").magnitude, rel=1e-12)


def test_minimum_position_and_momentum_uncertainty_invert_each_other():
    """Heisenberg at the equality is its own inverse, so the pair closes both ways."""
    from anvilate.analysis import minimum_momentum_uncertainty, minimum_position_uncertainty

    # Both quantities are far below approx's default abs=1e-12 in their SI units, so the
    # round trip is asserted as a ratio to 1 — a scaled unit would only move the momentum.
    spread = _q("1e-10 m")
    momentum = minimum_momentum_uncertainty(position_uncertainty=spread)
    recovered = minimum_position_uncertainty(momentum_uncertainty=momentum)
    assert recovered.to("m").magnitude / spread.to("m").magnitude == pytest.approx(1.0, rel=1e-12)

    momentum_spread = _q("5e-25 kg*m/s")
    position = minimum_position_uncertainty(momentum_uncertainty=momentum_spread)
    closed = minimum_momentum_uncertainty(position_uncertainty=position)
    assert closed.to("kg*m/s").magnitude / momentum_spread.to("kg*m/s").magnitude == pytest.approx(
        1.0, rel=1e-12
    )


def test_capacitance_for_reactive_power_lands_the_reactive_power():
    """The forward is in another module: the sized capacitor's reactance comes from
    :func:`capacitive_reactance`, and a capacitor across V draws V**2/X_c by definition."""
    from anvilate.analysis import capacitance_for_reactive_power, capacitive_reactance

    supply = {"voltage": _q("400 V"), "frequency": _q("50 Hz")}
    target = _q("25 kVA")
    capacitance = capacitance_for_reactive_power(reactive_power=target, **supply)
    reactance = capacitive_reactance(capacitance=capacitance, frequency=supply["frequency"])
    drawn = supply["voltage"].to("V").magnitude ** 2 / reactance.to("ohm").magnitude
    assert drawn / 1000.0 == pytest.approx(target.to("kVA").magnitude, rel=1e-12)


def test_bolt_preload_from_torque_and_torque_for_preload_invert_each_other():
    """The two halves of T = K*F*d are each other's forward, so the pair closes both
    ways; the nut factor is set away from its default so a dropped K cannot pass."""
    from anvilate.analysis import bolt_preload_from_torque, torque_for_preload

    thread = {"nominal_diameter": _q("10 mm"), "nut_factor": 0.18}
    target = _q("22 kN")
    torque = torque_for_preload(preload=target, **thread)
    assert bolt_preload_from_torque(torque=torque, **thread).to("kN").magnitude == pytest.approx(
        target.to("kN").magnitude, rel=1e-12
    )

    applied = _q("45 N*m")
    preload = bolt_preload_from_torque(torque=applied, **thread)
    assert torque_for_preload(preload=preload, **thread).to("N*m").magnitude == pytest.approx(
        applied.to("N*m").magnitude, rel=1e-12
    )
    # A slicker thread develops more preload for the same torque, in inverse proportion.
    lubricated = bolt_preload_from_torque(
        torque=applied, nominal_diameter=_q("10 mm"), nut_factor=0.09
    )
    assert lubricated.to("kN").magnitude == pytest.approx(
        2.0 * preload.to("kN").magnitude, rel=1e-12
    )


def test_peukert_exponent_from_two_rates_reproduces_both_discharge_tests():
    """The exponent is fitted from two measurements, so the round trip has to land BOTH
    of them: a fit that reproduces only the test it was rated at says nothing."""
    from anvilate.analysis import peukert_exponent_from_two_rates, peukert_runtime

    low, low_time = _q("5 A"), _q("20 hour")
    high, high_time = _q("25 A"), _q("3.2 hour")
    exponent = peukert_exponent_from_two_rates(
        current_low=low, runtime_low=low_time, current_high=high, runtime_high=high_time
    )
    assert exponent > 1.0
    # The pack is rated at the low-current test: that current for that time.
    rated = Quantity(magnitude=low.to("A").magnitude * low_time.to("hour").magnitude, unit="A*h")
    battery = {"rated_capacity": rated, "rated_current": low, "peukert_exponent": exponent}
    assert peukert_runtime(discharge_current=low, **battery).to("hour").magnitude == pytest.approx(
        low_time.to("hour").magnitude, rel=1e-12
    )
    assert peukert_runtime(discharge_current=high, **battery).to("hour").magnitude == pytest.approx(
        high_time.to("hour").magnitude, rel=1e-12
    )


def test_first_order_time_for_conversion_lands_the_remaining_concentration():
    from anvilate.analysis import first_order_concentration, first_order_time_for_conversion

    rate = _q("0.045 1/min")
    conversion = 0.9
    duration = first_order_time_for_conversion(rate_constant=rate, conversion=conversion)
    initial = _q("2 mol/L")
    left = first_order_concentration(
        initial_concentration=initial, rate_constant=rate, time=duration
    )
    assert left.to("mol/L").magnitude / initial.to("mol/L").magnitude == pytest.approx(
        1.0 - conversion, rel=1e-12
    )
    # Each further nine costs the same increment again.
    two_nines = first_order_time_for_conversion(rate_constant=rate, conversion=0.99)
    assert two_nines.to("min").magnitude == pytest.approx(
        2.0 * duration.to("min").magnitude, rel=1e-12
    )


def test_buck_minimum_inductance_for_ccm_lands_the_boundary_ripple():
    """Continuous conduction ends where the ripple is twice the load current, so the
    critical inductance must be the one that produces exactly that ripple."""
    from anvilate.analysis import buck_inductor_ripple_current, buck_minimum_inductance_for_ccm

    output, load, duty = _q("5 V"), _q("2 A"), 0.4
    switching = _q("250 kHz")
    inductance = buck_minimum_inductance_for_ccm(
        output_voltage=output, load_current=load, duty_cycle=duty, switching_frequency=switching
    )
    supply = Quantity(magnitude=output.to("V").magnitude / duty, unit="V")
    ripple = buck_inductor_ripple_current(
        input_voltage=supply,
        output_voltage=output,
        inductance=inductance,
        switching_frequency=switching,
    )
    assert ripple.to("A").magnitude == pytest.approx(2.0 * load.to("A").magnitude, rel=1e-12)


def test_fouling_factor_from_coefficients_lands_the_fouled_coefficient():
    """The whole round trip runs through the public U: a fouling allowance is added to the
    clean wall, and reading the two coefficients back must recover exactly that allowance."""
    from anvilate.analysis import (
        fouling_factor_from_coefficients,
        overall_heat_transfer_coefficient,
    )

    wall = {
        "inside_coefficient": _q("3200 W/(m**2*K)"),
        "outside_coefficient": _q("1100 W/(m**2*K)"),
        "wall_thickness": _q("2 mm"),
        "wall_conductivity": _q("16 W/(m*K)"),
    }
    allowance = _q("0.0004 m**2*K/W")
    clean = overall_heat_transfer_coefficient(**wall)
    service = overall_heat_transfer_coefficient(inside_fouling_factor=allowance, **wall)
    assert fouling_factor_from_coefficients(
        clean_coefficient=clean, service_coefficient=service
    ).to("m**2*K/W").magnitude == pytest.approx(allowance.to("m**2*K/W").magnitude, rel=1e-12)


def test_belt_speed_for_max_power_is_the_speed_that_maximises_the_power():
    """An optimum, not an equality: the contract is that the transmitted power at v* beats
    the power either side of it, and that the centrifugal tension there is exactly T1/3."""
    from anvilate.analysis import (
        belt_centrifugal_tension,
        belt_max_transmissible_force_at_speed,
        belt_speed_for_max_power,
    )

    belt = {"tight_tension": _q("1800 N"), "linear_density": _q("0.35 kg/m")}
    grip = {"friction_coefficient": 0.4, "wrap_angle": 3.0}
    best = belt_speed_for_max_power(**belt)
    assert belt_centrifugal_tension(linear_density=belt["linear_density"], belt_speed=best).to(
        "N"
    ).magnitude == pytest.approx(belt["tight_tension"].to("N").magnitude / 3.0, rel=1e-12)

    def power(speed: Quantity) -> float:
        force = belt_max_transmissible_force_at_speed(belt_speed=speed, **belt, **grip)
        return force.to("N").magnitude * speed.to("m/s").magnitude

    peak = power(best)
    for factor in (0.8, 0.95, 1.05, 1.2):
        off = Quantity(magnitude=factor * best.to("m/s").magnitude, unit="m/s")
        assert power(off) < peak
