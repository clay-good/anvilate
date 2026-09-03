"""The bound a quantity's own name fixes, and the one keystroke that breaks it.

A line-trace of the whole suite at HEAD says **2,408 of the library's `raise` sites never
execute**, and 129 of those enforce a *numeric* bound. Almost all 129 are one family: a
parameter whose name already fixes its range — an efficiency, a mole fraction, a
coefficient of utilization, a heat-capacity ratio, a count of shear planes. Those guards
had never been run, so their comparisons had never been evaluated against the case they
exist for, and an inverted one reads exactly like a correct one.

They all exist for the same mistake, and it is one keystroke: **a percentage where a
fraction belongs**. `0.85` typed as `85`. The 0.6 weld factor typed as `6`. Nothing about
those values is ill-formed; they are floats in the right units, and without the guard they
travel straight through the formula and come back as a capacity a hundred times too large.

Each case here passes the slip and then passes a value just inside the bound, because a
guard that refuses everything passes a refusal test exactly as well as a correct one.
:func:`test_every_bounded_parameter_is_guarded` is the ratchet: it re-derives the census
from the source, so a new function taking one of these parameters without a guard fails
here rather than shipping.
"""

from __future__ import annotations

import ast
import pathlib
import re
from collections.abc import Callable
from typing import Any

import pytest

from anvilate.analysis import (
    adiabatic_compression_power,
    asme_b313_pipe_pressure,
    asme_cylinder_thickness,
    battery_bank_capacity,
    bolt_shear_strength,
    bragg_angle,
    buck_boost_output_voltage,
    coating_dry_film_thickness,
    collector_useful_heat,
    compressor_isentropic_from_polytropic,
    counterflow_ntu_for_effectiveness,
    crossflow_both_unmixed_effectiveness,
    electroplating_mass_deposited,
    equilibrium_vapor_mole_fraction,
    fillet_weld_design_strength,
    fin_thermal_resistance,
    future_value,
    heat_engine_second_law_efficiency,
    hydraulic_pump_flow_rate,
    laser_cutting_speed,
    line_current_for_power,
    lumen_method_illuminance,
    minimum_fluidization_velocity,
    obstruction_meter_flow_rate,
    otto_cycle_efficiency,
    parallel_flow_effectiveness,
    parallel_flow_ntu_for_effectiveness,
    parallel_system_reliability,
    pv_array_power,
    radiation_heat_transfer_coefficient,
    radiation_two_surface_exchange,
    rectangular_weir_flow,
    shell_and_tube_effectiveness,
    shell_and_tube_ntu_for_effectiveness,
    stagnation_temperature_ratio,
    view_factor_reciprocity,
    weld_base_metal_shear_strength,
    weld_heat_input,
    wind_turbine_rotor_thrust,
)
from anvilate.units import Quantity

Q = Quantity.parse


# One row per guard: what to call, the value that trips it, and a value inside the bound
# that must still be accepted. `refused` is the slip a user actually makes — a percentage
# for a fraction, a ratio taken the wrong way up, a count of none.
_CASES: tuple[tuple[str, Callable[[Any], Any], Any, Any], ...] = (
    (
        "volume_solids_fraction",
        lambda v: coating_dry_film_thickness(
            wet_film_thickness=Q("150 um"), volume_solids_fraction=v
        ),
        55,
        0.55,
    ),
    (
        "current_efficiency",
        lambda v: electroplating_mass_deposited(
            current=Q("100 A"),
            plating_time=Q("30 min"),
            equivalent_weight=32.7,
            current_efficiency=v,
        ),
        95,
        0.95,
    ),
    (
        "battery efficiency",
        lambda v: battery_bank_capacity(
            load_power=Q("500 W"),
            autonomy_time=Q("8 hour"),
            system_voltage=Q("48 V"),
            depth_of_discharge=0.5,
            efficiency=v,
        ),
        85,
        0.85,
    ),
    (
        "volumetric_efficiency",
        lambda v: hydraulic_pump_flow_rate(
            displacement=Q("50 cm**3"), rotational_speed=Q("1500 rpm"), volumetric_efficiency=v
        ),
        95,
        0.95,
    ),
    (
        "coupling_efficiency",
        lambda v: laser_cutting_speed(
            beam_power=Q("4 kW"),
            coupling_efficiency=v,
            thickness=Q("6 mm"),
            kerf_width=Q("0.3 mm"),
            density=Q("7850 kg/m**3"),
            specific_removal_energy=Q("2.0 MJ/kg"),
        ),
        40,
        0.4,
    ),
    (
        "module_efficiency",
        lambda v: pv_array_power(
            irradiance=Q("1000 W/m**2"), area=Q("1.6 m**2"), module_efficiency=v
        ),
        20,
        0.2,
    ),
    (
        "collector efficiency",
        lambda v: collector_useful_heat(
            efficiency=v, irradiance=Q("900 W/m**2"), area=Q("2.5 m**2")
        ),
        70,
        0.7,
    ),
    (
        "thermal_efficiency (arc)",
        lambda v: weld_heat_input(
            arc_voltage=Q("24 V"),
            welding_current=Q("220 A"),
            travel_speed=Q("5 mm/s"),
            thermal_efficiency=v,
        ),
        80,
        0.8,
    ),
    (
        "coefficient_of_utilization",
        lambda v: lumen_method_illuminance(
            luminaire_count=12,
            lumens_per_luminaire=Q("4000 lm"),
            coefficient_of_utilization=v,
            light_loss_factor=0.8,
            area=Q("100 m**2"),
        ),
        60,
        0.6,
    ),
    (
        "joint_efficiency",
        lambda v: asme_cylinder_thickness(
            pressure=Q("1.5 MPa"),
            radius=Q("500 mm"),
            allowable_stress=Q("138 MPa"),
            joint_efficiency=v,
        ),
        85,
        0.85,
    ),
    (
        "quality_factor",
        lambda v: asme_b313_pipe_pressure(
            wall_thickness=Q("6.02 mm"),
            outside_diameter=Q("168.3 mm"),
            allowable_stress=Q("110 MPa"),
            quality_factor=v,
        ),
        100,
        1.0,
    ),
    (
        "weld_metal_shear_fraction",
        lambda v: fillet_weld_design_strength(
            leg_size=Q("6 mm"),
            length=Q("200 mm"),
            electrode_strength=Q("490 MPa"),
            weld_metal_shear_fraction=v,
        ),
        6,
        0.6,
    ),
    (
        "base-metal shear_fraction",
        lambda v: weld_base_metal_shear_strength(
            base_thickness=Q("10 mm"),
            length=Q("200 mm"),
            base_ultimate_strength=Q("450 MPa"),
            shear_fraction=v,
        ),
        6,
        0.6,
    ),
    (
        "heat_capacity_ratio",
        lambda v: stagnation_temperature_ratio(mach_number=0.8, heat_capacity_ratio=v),
        1.0,
        1.4,
    ),
    (
        "specific_heat_ratio",
        lambda v: otto_cycle_efficiency(compression_ratio=9.0, specific_heat_ratio=v),
        1.0,
        1.4,
    ),
    (
        "thermal_efficiency (cycle)",
        lambda v: heat_engine_second_law_efficiency(thermal_efficiency=v, carnot_efficiency=0.6),
        35,
        0.35,
    ),
    (
        "power_factor",
        lambda v: line_current_for_power(
            real_power=Q("15 kW"), line_voltage=Q("400 V"), power_factor=v
        ),
        90,
        0.9,
    ),
    (
        "capacity_ratio",
        lambda v: parallel_flow_effectiveness(ntu=1.5, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "emissivity",
        lambda v: radiation_two_surface_exchange(
            emissivity_1=v,
            area_1=Q("2 m**2"),
            temperature_1=Q("600 K"),
            emissivity_2=0.8,
            area_2=Q("2 m**2"),
            temperature_2=Q("300 K"),
            view_factor=1.0,
        ),
        90,
        0.9,
    ),
    # --- Guards that EXIST and had never RUN -------------------------------------------
    #
    # `test_every_bounded_parameter_is_guarded` is a STATIC census: it reads the source and
    # asks whether a guard is written. It cannot ask whether one is ever evaluated, and a
    # line-trace says these eight never were — five functions share the `capacity_ratio`
    # bound and only `parallel_flow_effectiveness` above was called with a bad one; the
    # `emissivity` case passes its slip as `emissivity_1`, so the `emissivity_2` guard two
    # lines down returned before it could refuse anything.
    #
    # An unrun guard is an unevaluated comparison, and an inverted one reads exactly like a
    # correct one. All eight were checked by hand before these cases were written; the
    # cases are what keep them checked.
    (
        "capacity_ratio (crossflow, both unmixed)",
        lambda v: crossflow_both_unmixed_effectiveness(ntu=1.5, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "capacity_ratio (counterflow NTU inverse)",
        lambda v: counterflow_ntu_for_effectiveness(effectiveness=0.5, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "capacity_ratio (parallel-flow NTU inverse)",
        lambda v: parallel_flow_ntu_for_effectiveness(effectiveness=0.4, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "capacity_ratio (shell and tube)",
        lambda v: shell_and_tube_effectiveness(ntu=1.5, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "capacity_ratio (shell and tube NTU inverse)",
        lambda v: shell_and_tube_ntu_for_effectiveness(effectiveness=0.4, capacity_ratio=v),
        1.6,
        0.6,
    ),
    (
        "emissivity_2 (the second surface)",
        lambda v: radiation_two_surface_exchange(
            emissivity_1=0.8,
            area_1=Q("2 m**2"),
            temperature_1=Q("600 K"),
            emissivity_2=v,
            area_2=Q("2 m**2"),
            temperature_2=Q("300 K"),
            view_factor=1.0,
        ),
        90,
        0.9,
    ),
    (
        "emissivity (radiation film coefficient)",
        lambda v: radiation_heat_transfer_coefficient(
            emissivity=v,
            surface_temperature=Q("400 K"),
            surroundings_temperature=Q("300 K"),
        ),
        90,
        0.9,
    ),
    (
        "view_factor_1_to_2 (reciprocity)",
        lambda v: view_factor_reciprocity(
            area_1=Q("2 m**2"), view_factor_1_to_2=v, area_2=Q("1 m**2")
        ),
        50,
        0.5,
    ),
    (
        "liquid_mole_fraction",
        lambda v: equilibrium_vapor_mole_fraction(liquid_mole_fraction=v, relative_volatility=2.5),
        40,
        0.4,
    ),
    (
        "interest rate",
        lambda v: future_value(present_value=1000.0, rate=v, periods=10.0),
        -1.5,
        0.05,
    ),
    (
        "diffraction order",
        lambda v: bragg_angle(wavelength=Q("0.154 nm"), plane_spacing=Q("0.31 nm"), order=v),
        0,
        1,
    ),
    (
        "shear_planes",
        lambda v: bolt_shear_strength(
            nominal_shear_stress=Q("372 MPa"), bolt_diameter=Q("20 mm"), shear_planes=v
        ),
        0,
        1,
    ),
    (
        "pressure_ratio",
        lambda v: adiabatic_compression_power(
            volumetric_flow=Q("0.5 m**3/s"),
            inlet_pressure=Q("101.325 kPa"),
            pressure_ratio=v,
            heat_capacity_ratio=1.4,
        ),
        0.5,
        3.0,
    ),
    (
        "polytropic_efficiency",
        lambda v: compressor_isentropic_from_polytropic(
            pressure_ratio=4.0, polytropic_efficiency=v
        ),
        78,
        0.78,
    ),
    (
        "discharge_coefficient (orifice)",
        lambda v: obstruction_meter_flow_rate(
            discharge_coefficient=v,
            throat_diameter=Q("50 mm"),
            pipe_diameter=Q("100 mm"),
            pressure_drop=Q("20 kPa"),
            density=Q("998 kg/m**3"),
        ),
        61,
        0.61,
    ),
    (
        "fin_efficiency",
        lambda v: fin_thermal_resistance(
            fin_efficiency=v,
            heat_transfer_coefficient=Q("25 W/(m**2*K)"),
            fin_surface_area=Q("0.4 m**2"),
        ),
        90,
        0.9,
    ),
    (
        "void_fraction",
        lambda v: minimum_fluidization_velocity(
            particle_diameter=Q("0.5 mm"),
            particle_density=Q("2500 kg/m**3"),
            fluid_density=Q("1.2 kg/m**3"),
            fluid_viscosity=Q("1.8e-5 Pa*s"),
            void_fraction=v,
        ),
        45,
        0.45,
    ),
    (
        "component_reliabilities",
        lambda v: parallel_system_reliability(component_reliabilities=[v, 0.9]),
        99,
        0.99,
    ),
    (
        "discharge_coefficient (weir)",
        lambda v: rectangular_weir_flow(
            discharge_coefficient=v, crest_length=Q("1.2 m"), head=Q("0.15 m")
        ),
        62,
        0.62,
    ),
    (
        "duty_cycle",
        lambda v: buck_boost_output_voltage(input_voltage=Q("24 V"), duty_cycle=v),
        40,
        0.4,
    ),
    (
        "thrust_coefficient",
        lambda v: wind_turbine_rotor_thrust(
            air_density=Q("1.225 kg/m**3"),
            rotor_diameter=Q("90 m"),
            wind_speed=Q("12 m/s"),
            thrust_coefficient=v,
        ),
        80,
        0.8,
    ),
)


@pytest.mark.parametrize(
    ("label", "call", "refused", "accepted"), _CASES, ids=[c[0] for c in _CASES]
)
def test_a_value_outside_its_own_name_is_refused(
    label: str, call: Callable[[Any], Any], refused: Any, accepted: Any
) -> None:
    """The slip is refused, and the value inside the bound is not.

    Both halves matter. Without the second, a guard that had been written inverted — or
    one whose bound had been mutated to refuse the whole domain — would pass this test,
    since it would raise on the bad value too.
    """
    with pytest.raises(ValueError):
        call(refused)
    assert call(accepted) is not None


def test_the_weld_shear_fraction_bound_is_the_one_a_decimal_slip_crosses() -> None:
    """0.6 typed as 6 multiplied a weld's reported capacity tenfold, and did so quietly.

    The shear fraction is the ratio of the weld metal's shear strength to its tensile
    strength — 0.6 in AISC J2.4 — so a value above 1 is not a material. Positivity was
    guarded and the upper bound was not, which left the one wrong value a user actually
    produces travelling straight through. This pins the direction of the error as well as
    the refusal: what the missing guard bought was capacity, which is the unsafe way for a
    screening check to be wrong.
    """
    honest = fillet_weld_design_strength(
        leg_size=Q("6 mm"), length=Q("200 mm"), electrode_strength=Q("490 MPa")
    )
    assert honest.to("kN").magnitude == pytest.approx(249.5, rel=1e-3)
    with pytest.raises(ValueError, match=r"\(0, 1\]"):
        fillet_weld_design_strength(
            leg_size=Q("6 mm"),
            length=Q("200 mm"),
            electrode_strength=Q("490 MPa"),
            weld_metal_shear_fraction=6.0,
        )
    # And 1.0 — a weld metal as strong in shear as in tension — is still accepted, so the
    # guard rejects the slip rather than the domain.
    assert fillet_weld_design_strength(
        leg_size=Q("6 mm"),
        length=Q("200 mm"),
        electrode_strength=Q("490 MPa"),
        weld_metal_shear_fraction=1.0,
    ).to("kN").magnitude == pytest.approx(honest.to("kN").magnitude / 0.6, rel=1e-12)


# --- The ratchet -----------------------------------------------------------------

# A parameter whose name fixes its range. Matched on the whole name or its last word, so
# `module_efficiency`, `round_trip_efficiency` and `efficiency` are all one rule.
_BOUNDED_NAME = re.compile(
    r"(^|_)(efficiency|fraction|reflectivity|emissivity|absorptivity|transmissivity|"
    r"power_factor|duty_cycle|probability|reliability|utilization|humidity)$"
)

# The exceptions, each with the reason its name lies about its range. An entry here is a
# claim that the parameter is genuinely not a unit fraction — unbounded above, or not a
# scalar — and never that nobody got round to guarding it.
_NOT_A_FRACTION: dict[str, str] = {
    "bearing_cubic_mean_load.duty_cycle": (
        "not a scalar at all: a sequence of (time fraction, load) blocks, whose fractions "
        "are bound by the sum-to-1 check on their accumulator rather than one at a time"
    ),
    "shannon_minimum_eb_n0.spectral_efficiency": (
        "bits per second per hertz, not a fraction: a 64-QAM link runs at 6 and the "
        "Shannon bound has no ceiling"
    ),
    "absorbance.molar_absorptivity": (
        "the Beer-Lambert coefficient in L/(mol*cm), commonly tens of thousands"
    ),
    "concentration_from_absorbance.molar_absorptivity": (
        "the Beer-Lambert coefficient in L/(mol*cm), commonly tens of thousands"
    ),
    "degree_day_heating_energy.system_efficiency": (
        "a furnace is below 1 but a heat pump's COP is 3 to 4, and the docstring says so; "
        "capping this at 1 would refuse the heat pump the method is most used for"
    ),
    "actual_air_fuel_ratio.excess_air_fraction": (
        "excess air routinely exceeds 100%: a fraction of 1.0 is a burner running at "
        "twice stoichiometric air, which is ordinary for a kiln"
    ),
}


def _bounded_parameters_without_a_guard() -> dict[str, str]:
    """Every public parameter whose name fixes its range and whose function does not.

    A parameter counts as guarded when a `raise` in the function is reached through a
    comparison naming it against a bound in (0, 1] — or when it is handed to something
    that does, which is how the `_fraction` helpers each module carries are seen.
    Following that call is the whole difference between a census and a list of false
    positives: ten modules validate
    through a helper, and a scan that stopped at the function body would report all of
    them as holes and hide the real ones in the noise.
    """
    holes: dict[str, str] = {}
    for path in sorted(pathlib.Path(__file__).resolve().parents[1].glob("src/anvilate/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        functions = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
        for name, function in functions.items():
            if name.startswith("_"):
                continue
            for parameter in _parameters(function):
                if not _BOUNDED_NAME.search(parameter):
                    continue
                if not _guards(function, parameter, functions):
                    holes[f"{name}.{parameter}"] = f"{path.name}:{function.lineno}"
    return holes


def _parameters(function: ast.FunctionDef) -> list[str]:
    args = function.args
    return [a.arg for a in args.posonlyargs + args.args + args.kwonlyargs]


def _guards(
    function: ast.FunctionDef, parameter: str, functions: dict[str, ast.FunctionDef], depth: int = 0
) -> bool:
    for node in ast.walk(function):
        if not isinstance(node, ast.If):
            continue
        if not any(isinstance(inner, ast.Raise) for inner in ast.walk(node)):
            continue
        names = {n.id for n in ast.walk(node.test) if isinstance(n, ast.Name)}
        bounds = [
            n.value
            for n in ast.walk(node.test)
            if isinstance(n, ast.Constant)
            and isinstance(n.value, int | float)
            and not isinstance(n.value, bool)
        ]
        # Any bound in (0, 1] counts, not only 1: the trapezoidal-move guard is
        # `0 < accel_fraction <= 0.5`, and a scan that recognised only the literal 1
        # would call a correctly guarded parameter a hole.
        if parameter in names and any(0 < bound <= 1 for bound in bounds):
            return True
    if depth >= 2:
        return False
    for call in [n for n in ast.walk(function) if isinstance(n, ast.Call)]:
        callee = functions.get(call.func.id) if isinstance(call.func, ast.Name) else None
        if callee is None:
            continue
        names = _parameters(callee)
        for index, value in enumerate(call.args):
            if isinstance(value, ast.Name) and value.id == parameter and index < len(names):
                if _guards(callee, names[index], functions, depth + 1):
                    return True
        for keyword in call.keywords:
            passes = isinstance(keyword.value, ast.Name) and keyword.value.id == parameter
            if passes and keyword.arg:
                if _guards(callee, keyword.arg, functions, depth + 1):
                    return True
    return False


def test_every_bounded_parameter_is_guarded() -> None:
    """A new efficiency or fraction arrives guarded, or fails here.

    The 129 unrun bound guards were found by measuring; this keeps them from coming back
    one function at a time. The allow-list is for names that lie about their range, and
    each entry states why.
    """
    holes = _bounded_parameters_without_a_guard()
    unexplained = {k: v for k, v in holes.items() if k not in _NOT_A_FRACTION}
    assert not unexplained, (
        "these parameters are named for a bounded quantity and nothing enforces the "
        f"bound: {unexplained}. Guard it, or add it to _NOT_A_FRACTION with the reason "
        "its name lies about its range."
    )


def test_the_allow_list_is_current_and_reasoned() -> None:
    """An entry that no longer names a hole, or names one without a reason, fails.

    An allow-list nobody re-reads is a list of things that used to be true. If a parameter
    on it has since been guarded, the entry is stale and the exemption should go with it.
    """
    holes = _bounded_parameters_without_a_guard()
    stale = sorted(set(_NOT_A_FRACTION) - set(holes))
    assert not stale, f"these are guarded now; drop the exemption: {stale}"
    for parameter, reason in _NOT_A_FRACTION.items():
        assert len(reason.split()) >= 6, f"{parameter} is exempt for no stated reason"


def test_the_census_sees_a_hole_that_is_really_there() -> None:
    """The scanner, run against a function written to fail it, reports it.

    Written because the shape of this gate is one that agrees with whatever it is pointed
    at: if `_guards` returned True too easily — say, by counting any `raise` in the body —
    the census would come back empty and the ratchet would report clean forever. So the
    adversary is written out: two functions taking the same parameter, one guarding it and
    one not, and the scanner must separate them.
    """
    module = ast.parse(
        "def guarded(*, module_efficiency):\n"
        "    if not 0 < module_efficiency <= 1:\n"
        "        raise ValueError('out of range')\n"
        "    return module_efficiency\n"
        "\n"
        "def unguarded(*, module_efficiency):\n"
        "    if module_efficiency is None:\n"
        "        raise ValueError('missing')\n"
        "    return module_efficiency\n"
    )
    functions = {n.name: n for n in ast.walk(module) if isinstance(n, ast.FunctionDef)}
    assert _guards(functions["guarded"], "module_efficiency", functions)
    assert not _guards(functions["unguarded"], "module_efficiency", functions)


def test_the_census_covers_a_real_number_of_parameters() -> None:
    """The gate is looking at the library, not at an empty list.

    A scan whose regex stopped matching, or whose glob stopped resolving, would report no
    holes and no exemptions and read exactly like a clean repository. This asserts the
    census reaches the scale it is supposed to: the bounded-parameter rule applies to well
    over a hundred parameters across the analysis modules.
    """
    root = pathlib.Path(__file__).resolve().parents[1]
    seen = 0
    for path in sorted(root.glob("src/anvilate/**/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                seen += sum(1 for p in _parameters(node) if _BOUNDED_NAME.search(p))
    assert seen > 100, f"the bounded-parameter census only found {seen} parameters"


def test_the_contributing_page_states_this_files_own_counts() -> None:
    """The two numbers the page quotes about this file are read back out of it.

    A count in prose has no gate on it unless someone writes one, and both of these drift
    the moment a case or an exemption is added. The page is the first thing a contributor
    reads about the rule, so it is the worst place for a number that used to be true.
    """
    page = " ".join(
        (pathlib.Path(__file__).resolve().parents[1] / "docs" / "contributing-analysis.md")
        .read_text(encoding="utf-8")
        .split()
    )
    cases = re.search(r"trips (\d+) of these guards", page)
    assert cases is not None, "the guard-count sentence on the contributing page has moved"
    assert int(cases.group(1)) == len(_CASES)

    exempt = re.search(r"\*\*(\d+) parameters are exempt\*\*", page)
    assert exempt is not None, "the exemption count on the contributing page has moved"
    assert int(exempt.group(1)) == len(_NOT_A_FRACTION) - 1, (
        "the page counts the parameters whose name lies about its range; the duty-cycle "
        "entry is a sequence rather than a name that lies, and the page says so separately"
    )
