"""T1 analytical thermal expansion and stress checks (closed-form).

A member that would expand or contract with a temperature change but is fully
restrained develops a thermal stress with no mechanical load: ``σ = E·α·ΔT``,
where ``E`` is the elastic modulus, ``α`` the coefficient of thermal expansion,
and ``ΔT`` the temperature change. Compression on heating (positive ΔT), tension
on cooling. Left free, the same member simply grows ``δ = α·L·ΔT`` — the number
a clearance or slip-fit assembly check needs, and (inverted) the temperature
rise that lets a hub slip over its shrink-fit shaft. Inputs are
dimension-checked :class:`~anvilate.units.Quantity` values.

``ΔT`` is a temperature *difference* — pass it in kelvin or ``delta_degC``, not an
absolute ``degC`` reading.

Sources: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*
(conduction, convection, and the resistance network); Roark's *Formulas for Stress and
Strain* for the restrained-expansion thermal stress.
"""

from __future__ import annotations

from math import erf, exp, log, pi, sqrt, tanh

from pydantic import BaseModel, ConfigDict

from ..scorecard import ScorecardEntry
from ..units import Quantity, decimals_distinguishing, require_finite
from ..units.temperature import temperature_difference_kelvin

__all__ = [
    "confined_liquid_thermal_pressure",
    "constrained_thermal_stress",
    "thermal_shock_stress",
    "thermal_shock_temperature_limit",
    "triaxial_constrained_thermal_stress",
    "through_wall_gradient_thermal_stress",
    "thermal_buckling_temperature_rise",
    "free_thermal_expansion",
    "guided_cantilever_leg_length",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
    "bimetallic_strip_curvature",
    "bimetallic_strip_tip_deflection",
    "conduction_thermal_resistance",
    "convection_thermal_resistance",
    "critical_insulation_radius",
    "cylindrical_conduction_resistance",
    "degree_day_cooling_energy",
    "degree_day_heating_energy",
    "series_thermal_resistance",
    "parallel_thermal_resistance",
    "temperature_rise",
    "heatsink_thermal_resistance_required",
    "fin_efficiency",
    "fin_effectiveness",
    "fin_thermal_resistance",
    "junction_temperature_scorecard",
    "dittus_boelter_convection_coefficient",
    "laminar_tube_convection_coefficient",
    "flat_plate_forced_convection_coefficient",
    "flat_plate_turbulent_convection_coefficient",
    "cylinder_crossflow_convection_coefficient",
    "sphere_crossflow_convection_coefficient",
    "grashof_number",
    "marangoni_number",
    "rayleigh_number",
    "richardson_number",
    "vertical_plate_natural_convection_coefficient",
    "horizontal_cylinder_natural_convection_coefficient",
    "horizontal_plate_natural_convection_coefficient",
    "circular_source_spreading_resistance",
    "fin_array_thermal_resistance",
    "fin_array_count_for_resistance",
    "overall_heat_transfer_coefficient",
    "fouling_factor_from_coefficients",
    "cleanliness_factor",
    "log_mean_temperature_difference",
    "shell_and_tube_lmtd_correction_factor",
    "heat_exchanger_area_for_duty",
    "heat_exchanger_duty",
    "heat_exchanger_ntu",
    "counterflow_effectiveness",
    "heat_exchanger_effectiveness_from_temperatures",
    "parallel_flow_effectiveness",
    "crossflow_both_unmixed_effectiveness",
    "counterflow_ntu_for_effectiveness",
    "parallel_flow_ntu_for_effectiveness",
    "shell_and_tube_effectiveness",
    "shell_and_tube_ntu_for_effectiveness",
    "crossflow_cmax_mixed_effectiveness",
    "biot_number",
    "thermal_diffusivity",
    "fourier_number",
    "peclet_number",
    "brinkman_number",
    "lumped_capacitance_time_constant",
    "lumped_capacitance_cooling_time",
    "lumped_capacitance_excess_temperature",
    "semi_infinite_solid_temperature_rise",
    "semi_infinite_solid_surface_flux",
    "radiation_heat_transfer",
    "radiation_two_surface_exchange",
    "radiation_heat_transfer_coefficient",
    "crossed_strings_view_factor",
    "view_factor_reciprocity",
    "radiation_shield_reduction_factor",
    "wien_peak_wavelength",
    "wien_temperature_from_peak",
    "planetary_equilibrium_temperature",
]

_STEFAN_BOLTZMANN = 5.670374419e-8  # W/(m²·K⁴)
_WIEN_DISPLACEMENT = 2.897771955e-3  # m·K, Wien's displacement constant

_THERMAL_RESISTANCE_UNIT = "K/W"
# The laminar–turbulent transition Reynolds number for external flow over a flat
# plate (Incropera). Above it the laminar correlation no longer holds.
_FLAT_PLATE_LAMINAR_RE = 5.0e5
_STANDARD_GRAVITY = 9.80665  # m/s², for the buoyancy-driven Rayleigh number


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


def confined_liquid_thermal_pressure(
    *,
    volumetric_expansion_coefficient: Quantity,
    bulk_modulus: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The pressure rise of a liquid blocked in a rigid volume and heated, Δp = β·K·ΔT.

    A liquid trapped between two closed valves in a pipe and then heated has nowhere to expand, so
    almost all of its would-be expansion turns into pressure: Δp = β·K·ΔT. The rise is startling —
    for water it is about 0.46 MPa per °C, so a handful of degrees can burst a line — which is why
    valved-off liquid segments need thermal relief. ``volumetric_expansion_coefficient`` β is the
    liquid's cubical expansion (1/temperature; ~2.1e-4/K for water, larger for hydrocarbons),
    ``bulk_modulus`` K its stiffness (~2.2 GPa for water), and ``temperature_change`` ΔT the rise (a
    temperature difference, in K or delta_degC). Assumes a perfectly rigid container; real pipe
    compliance relieves some of it. Returns the pressure rise in MPa.
    """
    if not isinstance(volumetric_expansion_coefficient, Quantity):
        raise ValueError(
            f"volumetric_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {volumetric_expansion_coefficient!r}"
        )
    if not volumetric_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "volumetric_expansion_coefficient must have units of 1/temperature; got "
            f"{volumetric_expansion_coefficient.dimensionality}"
        )
    _require(bulk_modulus, "[pressure]", "bulk_modulus")
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    beta = volumetric_expansion_coefficient.to("1/K").magnitude
    k = bulk_modulus.to("Pa").magnitude
    dt = temperature_difference_kelvin(temperature_change, name="temperature_change")
    if beta <= 0 or k <= 0:
        raise ValueError("volumetric_expansion_coefficient and bulk_modulus must be positive")
    return Quantity(magnitude=beta * k * dt / 1.0e6, unit="MPa")


def constrained_thermal_stress(
    *,
    elastic_modulus: Quantity,
    thermal_expansion_coefficient: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The stress σ = E·α·ΔT in a fully-restrained member under a temperature change.

    ``elastic_modulus`` is E, ``thermal_expansion_coefficient`` the linear α (units
    of 1/temperature), and ``temperature_change`` ΔT (a temperature difference, in
    K or delta_degC). Returns the magnitude of the thermal stress in MPa — the
    stress a member develops when it is prevented from expanding or contracting.
    """
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    return Quantity(magnitude=abs(e * alpha * delta_t), unit="MPa")


def thermal_shock_stress(
    *,
    elastic_modulus: Quantity,
    thermal_expansion_coefficient: Quantity,
    temperature_change: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The surface stress of a thermally shocked body, σ = E·α·ΔT/(1 − ν).

    When a surface is quenched — suddenly cooled (or heated) while the bulk stays
    put — it wants to shrink but the cool interior holds it, and because the
    restraint acts in *both* in-plane directions the stress carries a biaxial factor
    1/(1 − ν) beyond the uniaxial :func:`constrained_thermal_stress`. A sudden
    cooling puts the surface in tension, which is why brittle parts (glass, ceramics,
    castings) crack when quenched. ``elastic_modulus`` E, the linear
    ``thermal_expansion_coefficient`` α (1/temperature), ``temperature_change`` ΔT
    (a temperature difference), and Poisson's ratio ``poisson`` ν (0 ≤ ν < 0.5)
    describe the shock — ΔT is the instantaneous surface-to-bulk difference, the
    severe limit of an infinitely fast quench. Returns the magnitude of the surface
    stress in MPa.

    Source: Roark's *Formulas for Stress and Strain*, the thermal-stress formulas.
    """
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    return Quantity(magnitude=abs(e * alpha * delta_t) / (1.0 - poisson), unit="MPa")


def thermal_shock_temperature_limit(
    *,
    fracture_strength: Quantity,
    elastic_modulus: Quantity,
    thermal_expansion_coefficient: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The critical quench ΔT_c = σ_f·(1 − ν)/(E·α) a body survives — thermal-shock resistance.

    The design inverse of :func:`thermal_shock_stress`: setting the quench surface stress
    equal to the material's fracture strength gives the largest instantaneous surface-to-bulk
    temperature difference the body can take before it cracks, ΔT_c = σ_f·(1 − ν)/(E·α). This
    is the classic first thermal-shock-resistance parameter R — the figure of merit that ranks
    materials for quench duty (a low-expansion, low-modulus, high-strength material like fused
    silica tolerates a huge ΔT; a stiff, high-expansion one cracks at a small one).
    ``fracture_strength`` σ_f, ``elastic_modulus`` E, the linear ``thermal_expansion_coefficient``
    α, and Poisson's ratio ``poisson`` ν (0 ≤ ν < 0.5). This is the severe (infinitely fast,
    infinite-Biot) limit; a finite quench rate tolerates more. Returns ΔT_c as a temperature
    difference in kelvin.

    Source: Roark's *Formulas for Stress and Strain*, the thermal-stress formulas.
    """
    _require(fracture_strength, "[pressure]", "fracture_strength")
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    sf = fracture_strength.to("MPa").magnitude
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    if sf <= 0:
        raise ValueError(f"fracture_strength must be positive; got {fracture_strength}")
    if e <= 0 or alpha <= 0:
        raise ValueError("elastic_modulus and thermal_expansion_coefficient must be positive")
    return Quantity(magnitude=sf * (1.0 - poisson) / (e * alpha), unit="K")


def triaxial_constrained_thermal_stress(
    *,
    elastic_modulus: Quantity,
    thermal_expansion_coefficient: Quantity,
    temperature_change: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The hydrostatic stress σ = E·α·ΔT/(1 − 2ν) of a fully (triaxially) constrained body.

    When a body is held in *all three* directions — a heated inclusion locked in a
    rigid matrix, a part filling a rigid cavity, a hot spot deep in a large solid —
    its thermal strain is entirely denied and it builds a hydrostatic stress
    σ = E·α·ΔT/(1 − 2ν). This is the most severe of the constraint family: it exceeds
    the biaxial :func:`thermal_shock_stress` (1/(1 − ν)) and the uniaxial
    :func:`constrained_thermal_stress` (1) by the shrinking (1 − 2ν) denominator — as
    ν → 0.5 (an incompressible material) the constrained stress diverges, because
    there is nowhere for the volume to go. ``elastic_modulus`` E, the linear
    ``thermal_expansion_coefficient`` α, ``temperature_change`` ΔT, and Poisson's
    ratio ``poisson`` ν (0 ≤ ν < 0.5) describe the body. Returns the magnitude of the
    hydrostatic stress in MPa.

    Source: Roark's *Formulas for Stress and Strain*, the thermal-stress formulas.
    """
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    return Quantity(magnitude=abs(e * alpha * delta_t) / (1.0 - 2.0 * poisson), unit="MPa")


def through_wall_gradient_thermal_stress(
    *,
    elastic_modulus: Quantity,
    thermal_expansion_coefficient: Quantity,
    temperature_difference: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The surface bending stress σ = E·α·ΔT/(2(1 − ν)) of a wall with a linear
    through-thickness temperature gradient.

    A wall hot on one face and cold on the other — a pipe carrying steam in cold air,
    a furnace wall, a reactor shell — wants to bow toward the cold side. Where it is
    restrained from bending (a long pipe held straight by its own continuity, a
    clamped plate), that bow is reacted as a bending stress that peaks at the two
    surfaces: tension on the cold face, compression on the hot. For a *linear*
    gradient the surface fibre sits ΔT/2 from the mean temperature and, restrained
    biaxially, develops σ = E·α·ΔT/(2·(1 − ν)) — exactly half the biaxial
    :func:`thermal_shock_stress` for the same total ΔT, because a gradient loads only
    the extreme fibres while a quench loads the whole surface. ``elastic_modulus`` E,
    the linear ``thermal_expansion_coefficient`` α, ``temperature_difference`` ΔT (the
    hot-to-cold difference across the wall), and Poisson's ratio ``poisson`` ν
    (0 ≤ ν < 0.5) describe the wall. An unrestrained wall simply curves and carries no
    stress; this is the restrained-against-bending case. Returns the magnitude of the
    surface stress in MPa.

    Source: Roark's *Formulas for Stress and Strain*, the thermal-stress formulas.
    """
    if not isinstance(elastic_modulus, Quantity):
        raise ValueError(f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus!r}")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not isinstance(temperature_difference, Quantity):
        raise ValueError(
            f"temperature_difference must be a [temperature] quantity; "
            f"got {temperature_difference!r}"
        )
    if not temperature_difference.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_difference must be a temperature difference; got "
            f"{temperature_difference.dimensionality}"
        )
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    return Quantity(magnitude=abs(e * alpha * delta_t) / (2.0 * (1.0 - poisson)), unit="MPa")


def free_thermal_expansion(
    *,
    length: Quantity,
    thermal_expansion_coefficient: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The free (unrestrained) thermal growth δ = α·L·ΔT of a member.

    ``length`` is the dimension that grows — a span, a diameter, a bolt
    circle. The result is SIGNED: positive ΔT grows, negative shrinks, which
    is what a clearance check needs. Dividing by L and multiplying by E
    recovers :func:`constrained_thermal_stress` exactly (the fully-restrained
    member develops the stress of the strain it was denied). ``length`` must
    be positive; ``temperature_change`` is a difference (K or delta_degC).
    """
    if not isinstance(length, Quantity):
        raise ValueError(f"length must be a [length] quantity; got {length!r}")
    if not length.has_dimension("[length]"):
        raise ValueError(f"length must be a [length] quantity; got {length.dimensionality}")
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    size = length.to("mm").magnitude
    if size <= 0:
        raise ValueError(f"length must be positive; got {length}")
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    return Quantity(magnitude=alpha * size * delta_t, unit="mm")


def guided_cantilever_leg_length(
    *,
    elastic_modulus: Quantity,
    pipe_outside_diameter: Quantity,
    expansion_to_absorb: Quantity,
    allowable_stress: Quantity,
) -> Quantity:
    """The pipe-loop leg length to absorb thermal expansion, L = √(3·E·D·Δ/S_A).

    A pipe run that grows with temperature must be given somewhere to flex, or the restrained
    expansion overstresses it. The guided-cantilever method sizes the offset (or expansion-loop) leg
    that takes the growth ``expansion_to_absorb`` Δ within an ``allowable_stress`` S_A: a leg of
    length L guided at both ends develops a bending stress 3·E·D·Δ/L², so setting that to S_A gives
    L = √(3·E·D·Δ/S_A), from the ``elastic_modulus`` E and the ``pipe_outside_diameter`` D. The leg
    grows only with the *square root* of the expansion, so absorbing twice the growth needs about
    40% more leg. A conservative first pass (real layouts share the flex over several legs and add
    stress-intensification at the elbows). Returns the required leg length in metres.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(pipe_outside_diameter, "[length]", "pipe_outside_diameter")
    _require(expansion_to_absorb, "[length]", "expansion_to_absorb")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    e = elastic_modulus.to("Pa").magnitude
    d = pipe_outside_diameter.to("m").magnitude
    delta = expansion_to_absorb.to("m").magnitude
    s_a = allowable_stress.to("Pa").magnitude
    if e <= 0 or d <= 0:
        raise ValueError("elastic_modulus and pipe_outside_diameter must be positive")
    if delta < 0:
        raise ValueError("expansion_to_absorb must be non-negative")
    if s_a <= 0:
        raise ValueError("allowable_stress must be positive")
    return Quantity(magnitude=sqrt(3.0 * e * d * delta / s_a), unit="m")


def shrink_fit_assembly_temperature(
    *,
    interface_diameter: Quantity,
    diametral_interference: Quantity,
    assembly_clearance: Quantity,
    thermal_expansion_coefficient: Quantity,
) -> Quantity:
    """The hub temperature RISE that opens a shrink fit for assembly.

    Heating the hub grows its bore stress-free by α·d·ΔT; to slip it over the
    shaft the bore must open by the fit's ``diametral_interference`` plus a
    working ``assembly_clearance`` (the slip allowance that keeps it from
    seizing half-way on), so ΔT = (δ + c)/(α·d). Exactly the inverse of
    :func:`free_thermal_expansion` applied to the bore diameter. Returns the
    temperature rise above the shaft's temperature (K); add it to ambient for
    the oven setpoint, and mind the material's tempering limit. Interference
    must be positive, the clearance non-negative.
    """
    if not isinstance(interface_diameter, Quantity):
        raise ValueError(
            f"interface_diameter must be a [length] quantity; got {interface_diameter!r}"
        )
    if not interface_diameter.has_dimension("[length]"):
        raise ValueError(
            f"interface_diameter must be a [length] quantity; got "
            f"{interface_diameter.dimensionality}"
        )
    if not isinstance(diametral_interference, Quantity):
        raise ValueError(
            f"diametral_interference must be a [length] quantity; got {diametral_interference!r}"
        )
    if not diametral_interference.has_dimension("[length]"):
        raise ValueError(
            f"diametral_interference must be a [length] quantity; got "
            f"{diametral_interference.dimensionality}"
        )
    if not isinstance(assembly_clearance, Quantity):
        raise ValueError(
            f"assembly_clearance must be a [length] quantity; got {assembly_clearance!r}"
        )
    if not assembly_clearance.has_dimension("[length]"):
        raise ValueError(
            f"assembly_clearance must be a [length] quantity; got "
            f"{assembly_clearance.dimensionality}"
        )
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    d = interface_diameter.to("mm").magnitude
    delta = diametral_interference.to("mm").magnitude
    clearance = assembly_clearance.to("mm").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    if d <= 0 or alpha <= 0:
        raise ValueError("interface_diameter and the expansion coefficient must be positive")
    if delta <= 0:
        raise ValueError(f"diametral_interference must be positive; got {diametral_interference}")
    if clearance < 0:
        raise ValueError(f"assembly_clearance must be non-negative; got {assembly_clearance}")
    return Quantity(magnitude=(delta + clearance) / (alpha * d), unit="K")


class DifferentialThermalStress(BaseModel):
    """The stresses two rigidly-joined members develop from a CTE mismatch.

    ``constraint_force`` is the shared internal force that pulls the two members
    to a common length. ``stress_1`` and ``stress_2`` are the resulting SIGNED
    stresses (tension positive): on heating, the higher-expansion member is held
    back in compression while the lower-expansion one is stretched into tension —
    the mechanism that cracks dissimilar-material joints on thermal cycling.
    """

    model_config = ConfigDict(frozen=True)

    constraint_force: Quantity
    stress_1: Quantity
    stress_2: Quantity


def differential_thermal_stress(
    *,
    temperature_change: Quantity,
    thermal_expansion_coefficient_1: Quantity,
    elastic_modulus_1: Quantity,
    area_1: Quantity,
    thermal_expansion_coefficient_2: Quantity,
    elastic_modulus_2: Quantity,
    area_2: Quantity,
) -> DifferentialThermalStress:
    """The CTE-mismatch stresses in two members forced to share one length.

    Two members of different expansion coefficient, rigidly joined and heated by
    the same ``temperature_change`` ΔT, cannot both reach their free length; the
    misfit (α₁ − α₂)·ΔT is taken up as strain. The shared constraint force is
    F = (α₁ − α₂)·ΔT / (1/(E₁·A₁) + 1/(E₂·A₂)) (independent of the shared length),
    and each member sees σᵢ = ∓F/Aᵢ — the higher-α member in compression on
    heating, the lower-α in tension.

    Each member carries its own ``thermal_expansion_coefficient`` (1/temperature),
    ``elastic_modulus`` (pressure), and ``area`` (length²); ``temperature_change``
    is a difference (K or delta_degC). Returns a :class:`DifferentialThermalStress`
    with the shared force and both signed stresses. Every quantity is
    dimension-checked and the areas must be positive.
    """
    _require(temperature_change, "[temperature]", "temperature_change")
    _require(
        thermal_expansion_coefficient_1, "1 / [temperature]", "thermal_expansion_coefficient_1"
    )
    _require(
        thermal_expansion_coefficient_2, "1 / [temperature]", "thermal_expansion_coefficient_2"
    )
    _require(elastic_modulus_1, "[pressure]", "elastic_modulus_1")
    _require(elastic_modulus_2, "[pressure]", "elastic_modulus_2")
    _require(area_1, "[length]**2", "area_1")
    _require(area_2, "[length]**2", "area_2")
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    a1 = thermal_expansion_coefficient_1.to("1/K").magnitude
    a2 = thermal_expansion_coefficient_2.to("1/K").magnitude
    ea1 = elastic_modulus_1.to("MPa").magnitude * area_1.to("mm**2").magnitude  # N
    ea2 = elastic_modulus_2.to("MPa").magnitude * area_2.to("mm**2").magnitude  # N
    if ea1 <= 0 or ea2 <= 0:
        raise ValueError("elastic moduli and areas must be positive")
    force = (a1 - a2) * delta_t / (1.0 / ea1 + 1.0 / ea2)  # N
    return DifferentialThermalStress(
        constraint_force=Quantity(magnitude=abs(force), unit="N"),
        stress_1=Quantity(magnitude=-force / area_1.to("mm**2").magnitude, unit="MPa"),
        stress_2=Quantity(magnitude=force / area_2.to("mm**2").magnitude, unit="MPa"),
    )


def thermal_buckling_temperature_rise(
    *,
    slenderness_ratio: float,
    thermal_expansion_coefficient: Quantity,
    end_condition_factor: float = 1.0,
) -> Quantity:
    """The temperature rise ΔT_cr = π²/((K·λ)²·α) that buckles an axially held bar.

    Heat a bar that cannot expand and it builds a compressive thermal stress
    E·α·ΔT; when that reaches the Euler buckling stress π²·E/(K·λ)² the bar snaps
    sideways — the "sun kink" that buckles constrained rail and pipe in hot weather.
    Setting the two equal, the elastic modulus cancels, so the critical temperature
    rise depends only on the geometry and the expansion coefficient:
    ΔT_cr = π²/((K·λ)²·α). ``slenderness_ratio`` λ = L/r is the pinned-pinned
    slenderness, ``end_condition_factor`` K the effective-length factor (1.0
    pinned-pinned, 0.5 fixed-fixed — stiffer restraint tolerates more heat), and
    ``thermal_expansion_coefficient`` α the material's linear α. λ, K, and α must be
    positive. Returns the critical temperature rise as a temperature difference (K).
    """
    if slenderness_ratio <= 0:
        raise ValueError(f"slenderness_ratio must be positive; got {slenderness_ratio}")
    if end_condition_factor <= 0:
        raise ValueError(f"end_condition_factor must be positive; got {end_condition_factor}")
    if not isinstance(thermal_expansion_coefficient, Quantity):
        raise ValueError(
            f"thermal_expansion_coefficient must be a 1 / [temperature] quantity; "
            f"got {thermal_expansion_coefficient!r}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    if alpha <= 0:
        raise ValueError(
            f"thermal_expansion_coefficient must be positive; got {thermal_expansion_coefficient}"
        )
    effective_slenderness = end_condition_factor * slenderness_ratio
    delta_t = pi**2 / (effective_slenderness**2 * alpha)
    return Quantity(magnitude=delta_t, unit="K")


def _bimetal_layer_check(
    alpha: Quantity, elastic_modulus: Quantity, thickness: Quantity, layer: int
) -> tuple[float, float, float]:
    """Validate one bimetal layer -> (alpha 1/K, E MPa, t mm), all positive."""
    if not isinstance(alpha, Quantity):
        raise ValueError(f"alpha_{layer} must be a 1 / [temperature] quantity; got {alpha!r}")
    if not alpha.has_dimension("1 / [temperature]"):
        raise ValueError(
            f"alpha_{layer} must have units of 1/temperature; got {alpha.dimensionality}"
        )
    _require(elastic_modulus, "[pressure]", f"elastic_modulus_{layer}")
    _require(thickness, "[length]", f"thickness_{layer}")
    a = alpha.to("1/K").magnitude
    e = elastic_modulus.to("MPa").magnitude
    t = thickness.to("mm").magnitude
    if e <= 0 or t <= 0:
        raise ValueError(f"elastic_modulus_{layer} and thickness_{layer} must be positive")
    return a, e, t


def bimetallic_strip_curvature(
    *,
    alpha_1: Quantity,
    elastic_modulus_1: Quantity,
    thickness_1: Quantity,
    alpha_2: Quantity,
    elastic_modulus_2: Quantity,
    thickness_2: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The curvature a heated bimetallic strip takes (Timoshenko, 1925).

    Two bonded layers with different expansion coefficients cannot grow equally, so
    a temperature change bows the strip — the working principle of a thermostat, a
    thermal breaker, a bimetal actuator. The strip curls toward the lower-expansion
    layer; its curvature 1/ρ follows Timoshenko's bimetal formula

        1/ρ = 6·(α₂ − α₁)·ΔT·(1 + m)² /
              [ h·(3·(1 + m)² + (1 + m·n)·(m² + 1/(m·n))) ],

    with m = t₁/t₂ the thickness ratio, n = E₁/E₂ the modulus ratio, and h = t₁ + t₂
    the total thickness. For equal thicknesses and moduli it reduces to the familiar
    1/ρ = 3·(α₂ − α₁)·ΔT/(2·h). Layer 1 and layer 2 each take a CTE ``alpha_i`` (a
    1/temperature quantity), an ``elastic_modulus_i``, and a ``thickness_i`` (both
    positive); ``temperature_change`` ΔT is a temperature difference. Returns the
    signed curvature as an inverse length (1/mm) — positive when α₂ > α₁ with a
    positive ΔT (the strip bends toward layer 1).
    """
    a1, e1, t1 = _bimetal_layer_check(alpha_1, elastic_modulus_1, thickness_1, 1)
    a2, e2, t2 = _bimetal_layer_check(alpha_2, elastic_modulus_2, thickness_2, 2)
    if not isinstance(temperature_change, Quantity):
        raise ValueError(
            f"temperature_change must be a [temperature] quantity; got {temperature_change!r}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    delta_t = temperature_difference_kelvin(temperature_change, name="temperature_change")
    m = t1 / t2
    n = e1 / e2
    h = t1 + t2
    curvature = (
        6.0
        * (a2 - a1)
        * delta_t
        * (1.0 + m) ** 2
        / (h * (3.0 * (1.0 + m) ** 2 + (1.0 + m * n) * (m**2 + 1.0 / (m * n))))
    )
    return Quantity(magnitude=curvature, unit="1/mm")


def bimetallic_strip_tip_deflection(
    *,
    length: Quantity,
    alpha_1: Quantity,
    elastic_modulus_1: Quantity,
    thickness_1: Quantity,
    alpha_2: Quantity,
    elastic_modulus_2: Quantity,
    thickness_2: Quantity,
    temperature_change: Quantity,
) -> Quantity:
    """The free-end deflection of a heated bimetallic cantilever strip.

    A bimetal strip clamped at one end deflects its free tip by δ ≈ (1/ρ)·L²/2 for a
    small curvature, where 1/ρ is the :func:`bimetallic_strip_curvature` and
    ``length`` L the strip's free length — the stroke a bimetal thermostat or actuator
    delivers per degree. The layer arguments and ``temperature_change`` are as in
    :func:`bimetallic_strip_curvature`; ``length`` must be positive. Returns the
    signed tip deflection in millimetres (positive toward layer 1).
    """
    _require(length, "[length]", "length")
    ell = length.to("mm").magnitude
    if ell <= 0:
        raise ValueError(f"length must be positive; got {length}")
    curvature = (
        bimetallic_strip_curvature(
            alpha_1=alpha_1,
            elastic_modulus_1=elastic_modulus_1,
            thickness_1=thickness_1,
            alpha_2=alpha_2,
            elastic_modulus_2=elastic_modulus_2,
            thickness_2=thickness_2,
            temperature_change=temperature_change,
        )
        .to("1/mm")
        .magnitude
    )
    return Quantity(magnitude=curvature * ell**2 / 2.0, unit="mm")


# --- Heat-transfer screening: resistance networks and fin efficiency ---
#
# Enclosure and electronics thermal design starts with a resistance network: the
# same series/parallel algebra as a circuit, with temperature difference playing
# the role of voltage and heat flow the current. Conduction is R = L/(kA),
# convection R = 1/(hA); the rise across a network carrying Q is ΔT = Q·R. These
# are the Incropera-class closed forms, kept in temperature *differences* (kelvin)
# so no absolute-temperature offset scale is involved. Convection coefficients h
# are caller-supplied (a correlation, datasheet, or measurement).


def conduction_thermal_resistance(
    *,
    thickness: Quantity,
    area: Quantity,
    conductivity: Quantity,
) -> Quantity:
    """The conduction thermal resistance R = L/(k·A) of a slab (K/W).

    Heat crossing a slab of ``thickness`` L and cross-sectional ``area`` A whose
    material has thermal ``conductivity`` k meets a resistance L/(k·A): a thicker or
    less-conductive slab resists more, a wider one less. ``conductivity`` is a
    ``[power]/[length]/[temperature]`` quantity (W/(m·K)). Returns K/W.
    """
    _require(thickness, "[length]", "thickness")
    _require(area, "[area]", "area")
    _require(conductivity, "[power] / [length] / [temperature]", "conductivity")
    length_m = thickness.to("m").magnitude
    area_m2 = area.to("m**2").magnitude
    k = conductivity.to("W/(m*K)").magnitude
    if length_m <= 0 or area_m2 <= 0 or k <= 0:
        raise ValueError("thickness, area, and conductivity must be positive")
    return Quantity(magnitude=length_m / (k * area_m2), unit=_THERMAL_RESISTANCE_UNIT)


def cylindrical_conduction_resistance(
    *,
    inner_radius: Quantity,
    outer_radius: Quantity,
    length: Quantity,
    conductivity: Quantity,
) -> Quantity:
    """The radial conduction resistance of a pipe or insulation layer, R = ln(r₂/r₁)/(2πkL) (K/W).

    Heat flowing outward through a cylindrical shell — a pipe wall or a layer of lagging — does not
    meet the slab resistance L/(k·A), because the area grows with radius. The right expression is
    R = ln(r₂/r₁)/(2πkL), from the ``inner_radius`` r₁, ``outer_radius`` r₂, pipe ``length`` L, and
    material ``conductivity`` k. Put it in series with the outer-surface
    :func:`convection_thermal_resistance` (area 2πr₂L) to get a bare or insulated pipe's heat loss.
    ``conductivity`` is a ``[power]/[length]/[temperature]`` quantity (W/(m·K)). Returns K/W.
    """
    _require(inner_radius, "[length]", "inner_radius")
    _require(outer_radius, "[length]", "outer_radius")
    _require(length, "[length]", "length")
    _require(conductivity, "[power] / [length] / [temperature]", "conductivity")
    r1 = inner_radius.to("m").magnitude
    r2 = outer_radius.to("m").magnitude
    length_m = length.to("m").magnitude
    k = conductivity.to("W/(m*K)").magnitude
    if r1 <= 0 or length_m <= 0 or k <= 0:
        raise ValueError("inner_radius, length, and conductivity must be positive")
    if r2 <= r1:
        raise ValueError("outer_radius must exceed inner_radius")
    return Quantity(
        magnitude=log(r2 / r1) / (2.0 * pi * k * length_m), unit=_THERMAL_RESISTANCE_UNIT
    )


def critical_insulation_radius(
    *,
    conductivity: Quantity,
    heat_transfer_coefficient: Quantity,
) -> Quantity:
    """The critical insulation radius of a pipe or wire, r_cr = k/h.

    A counterintuitive result: on a thin pipe or wire, adding a first layer of insulation can
    *raise* heat loss, because the extra outer area exposed to convection outweighs the added
    conduction resistance — up to the critical radius r_cr = k/h, from the insulation
    ``conductivity`` k and the outer ``heat_transfer_coefficient`` h. Insulation only ever reduces
    loss once the outer radius passes r_cr, so it matters only when the bare radius is below it
    (small tubes, cables); for any normal pipe the bare radius already exceeds r_cr and insulation
    always helps. Returns the critical radius as a length.
    """
    _require(conductivity, "[power] / [length] / [temperature]", "conductivity")
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    k = conductivity.to("W/(m*K)").magnitude
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    if k <= 0 or h <= 0:
        raise ValueError("conductivity and heat_transfer_coefficient must be positive")
    return Quantity(magnitude=k / h, unit="m")


def convection_thermal_resistance(
    *,
    area: Quantity,
    heat_transfer_coefficient: Quantity,
) -> Quantity:
    """The convection thermal resistance R = 1/(h·A) of a surface (K/W).

    Heat leaving a surface of ``area`` A to a fluid through a convection
    ``heat_transfer_coefficient`` h meets a resistance 1/(h·A): a larger area or a
    stronger coefficient (forced air over natural, liquid over air) resists less.
    ``heat_transfer_coefficient`` is a ``[power]/[length]**2/[temperature]`` quantity
    (W/(m²·K)), supplied by the caller from a correlation or datasheet. Returns K/W.
    """
    _require(area, "[area]", "area")
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    area_m2 = area.to("m**2").magnitude
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    if area_m2 <= 0 or h <= 0:
        raise ValueError("area and heat_transfer_coefficient must be positive")
    return Quantity(magnitude=1.0 / (h * area_m2), unit=_THERMAL_RESISTANCE_UNIT)


def degree_day_heating_energy(
    *,
    heat_loss_coefficient: Quantity,
    heating_degree_days: Quantity,
    system_efficiency: float = 1.0,
) -> Quantity:
    """The seasonal heating energy of a building by the degree-day method, E = UA·HDD/η.

    A building's heat loss over a season is set by how leaky it is and how cold and long the season
    was: E = UA·HDD/η, from the ``heat_loss_coefficient`` UA (the whole-building conductance, W/K —
    the sum of every envelope element's U·A plus infiltration), the ``heating_degree_days`` HDD (the
    season's total shortfall of outdoor temperature below the balance point, supplied as a
    temperature·time quantity such as ``"3000 K*day"``), and the heating ``system_efficiency`` η
    (furnace/boiler efficiency, or a COP for a heat pump). Returns the delivered fuel or electric
    energy in kWh.
    """
    _require(heat_loss_coefficient, "[power] / [temperature]", "heat_loss_coefficient")
    _require(heating_degree_days, "[temperature] * [time]", "heating_degree_days")
    if heat_loss_coefficient.to("W/K").magnitude <= 0:
        raise ValueError("heat_loss_coefficient must be positive")
    if heating_degree_days.to("K*day").magnitude < 0:
        raise ValueError("heating_degree_days must be non-negative")
    if system_efficiency <= 0:
        raise ValueError("system_efficiency must be positive")
    energy = heat_loss_coefficient.pint * heating_degree_days.pint / system_efficiency
    return Quantity(magnitude=float(energy.to("kWh").magnitude), unit="kWh")


def degree_day_cooling_energy(
    *,
    heat_loss_coefficient: Quantity,
    cooling_degree_days: Quantity,
    coefficient_of_performance: float,
) -> Quantity:
    """The seasonal cooling energy of a building by the degree-day method, E = UA·CDD/COP.

    The mirror of the heating case for the cooling season: the sensible cooling load is UA·CDD, and
    the electrical energy to remove it is that load over the equipment's
    ``coefficient_of_performance`` COP: E = UA·CDD/COP, from the ``heat_loss_coefficient`` UA (W/K)
    and the ``cooling_degree_days`` CDD (a temperature·time quantity such as ``"500 K*day"``).
    Because a chiller moves several units of heat per unit of electricity, the electric energy is a
    fraction of the thermal load. Returns the electrical energy in kWh.
    """
    _require(heat_loss_coefficient, "[power] / [temperature]", "heat_loss_coefficient")
    _require(cooling_degree_days, "[temperature] * [time]", "cooling_degree_days")
    if heat_loss_coefficient.to("W/K").magnitude <= 0:
        raise ValueError("heat_loss_coefficient must be positive")
    if cooling_degree_days.to("K*day").magnitude < 0:
        raise ValueError("cooling_degree_days must be non-negative")
    if coefficient_of_performance <= 0:
        raise ValueError("coefficient_of_performance must be positive")
    energy = heat_loss_coefficient.pint * cooling_degree_days.pint / coefficient_of_performance
    return Quantity(magnitude=float(energy.to("kWh").magnitude), unit="kWh")


def series_thermal_resistance(*resistances: Quantity) -> Quantity:
    """The total resistance of paths in series, R = ΣRᵢ (K/W).

    Conduction through a wall then convection off its face is two resistances in
    series — the heat flows through both, so they add. Needs at least one
    resistance; each is a ``[temperature]/[power]`` quantity.
    """
    if not resistances:
        raise ValueError("series_thermal_resistance needs at least one resistance")
    total = 0.0
    for r in resistances:
        _require(r, "[temperature] / [power]", "resistance")
        total += r.to(_THERMAL_RESISTANCE_UNIT).magnitude
    return Quantity(magnitude=total, unit=_THERMAL_RESISTANCE_UNIT)


def parallel_thermal_resistance(*resistances: Quantity) -> Quantity:
    """The total resistance of paths in parallel, 1/R = Σ(1/Rᵢ) (K/W).

    A heat sink and the enclosure wall both carrying heat away from a component are
    parallel paths — the conductances add, so the combined resistance is below the
    smallest. Needs at least one positive resistance; each is a
    ``[temperature]/[power]`` quantity.
    """
    if not resistances:
        raise ValueError("parallel_thermal_resistance needs at least one resistance")
    conductance = 0.0
    for r in resistances:
        _require(r, "[temperature] / [power]", "resistance")
        magnitude = r.to(_THERMAL_RESISTANCE_UNIT).magnitude
        if magnitude <= 0:
            raise ValueError(f"each resistance must be positive; got {r}")
        conductance += 1.0 / magnitude
    return Quantity(magnitude=1.0 / conductance, unit=_THERMAL_RESISTANCE_UNIT)


def temperature_rise(*, power: Quantity, thermal_resistance: Quantity) -> Quantity:
    """The temperature rise ΔT = Q·R across a resistance carrying a heat flow (K).

    The junction-to-ambient rise of a component dissipating ``power`` Q through a
    total ``thermal_resistance`` R — add it to the ambient temperature to get the
    junction temperature, and compare against the rated limit. ``power`` is a
    ``[power]`` quantity and ``thermal_resistance`` a ``[temperature]/[power]`` one.
    Returns the rise in kelvin (a temperature difference).
    """
    _require(power, "[power]", "power")
    _require(thermal_resistance, "[temperature] / [power]", "thermal_resistance")
    q = power.to("W").magnitude
    r = thermal_resistance.to(_THERMAL_RESISTANCE_UNIT).magnitude
    if q < 0 or r < 0:
        raise ValueError("power and thermal_resistance must be non-negative")
    return Quantity(magnitude=q * r, unit="K")


def heatsink_thermal_resistance_required(
    *,
    power: Quantity,
    allowable_temperature_rise: Quantity,
    internal_thermal_resistance: Quantity | None = None,
) -> Quantity:
    """The largest heatsink resistance that keeps a junction in budget, θ_sa = ΔT/Q − θ_int.

    The design inverse of :func:`temperature_rise`: a component dissipating ``power`` Q must keep
    its junction-to-ambient rise within ``allowable_temperature_rise`` ΔT (the rated junction limit
    above ambient), so the total path may be no more resistive than ΔT/Q. Subtracting the fixed
    ``internal_thermal_resistance`` θ_int already inside the package and interface (junction-to-case
    plus case-to-sink, zero if omitted) leaves the largest sink-to-ambient resistance the heatsink
    may have: θ_sa = ΔT/Q − θ_int. A smaller number means a bigger heatsink (or forced air). Raises
    if the internal resistance alone already blows the budget — no heatsink can rescue it, the part
    must dissipate less or run cooler. Returns the allowable heatsink resistance in K/W.
    """
    _require(power, "[power]", "power")
    _require(allowable_temperature_rise, "[temperature]", "allowable_temperature_rise")
    q = power.to("W").magnitude
    delta_t = temperature_difference_kelvin(
        allowable_temperature_rise, name="allowable_temperature_rise"
    )
    if q <= 0:
        raise ValueError("power must be positive")
    if delta_t <= 0:
        raise ValueError("allowable_temperature_rise must be positive")
    theta_int = 0.0
    if internal_thermal_resistance is not None:
        _require(
            internal_thermal_resistance, "[temperature] / [power]", "internal_thermal_resistance"
        )
        theta_int = internal_thermal_resistance.to(_THERMAL_RESISTANCE_UNIT).magnitude
        if theta_int < 0:
            raise ValueError("internal_thermal_resistance must be non-negative")
    theta_total_max = delta_t / q
    theta_sa = theta_total_max - theta_int
    if theta_sa <= 0:
        raise ValueError(
            "the internal thermal resistance alone exceeds the junction budget "
            f"(ΔT/Q = {theta_total_max:.3g} K/W ≤ internal {theta_int:.3g} K/W); "
            "no heatsink can keep the junction in limit — reduce the power or raise the budget"
        )
    return Quantity(magnitude=theta_sa, unit=_THERMAL_RESISTANCE_UNIT)


def fin_efficiency(
    *,
    heat_transfer_coefficient: Quantity,
    perimeter: Quantity,
    conductivity: Quantity,
    cross_section_area: Quantity,
    length: Quantity,
) -> float:
    """The efficiency η = tanh(mL)/(mL) of a straight fin (adiabatic tip).

    A fin is not isothermal — its tip runs cooler than its base, so it moves less
    heat than an ideal fin at the base temperature. The efficiency is
    η = tanh(mL)/(mL) with m = √(h·P/(k·A_c)), where ``perimeter`` P and
    ``cross_section_area`` A_c are the fin's section, ``conductivity`` k its
    material, ``heat_transfer_coefficient`` h the surface coefficient, and
    ``length`` L the fin length. A short, thick, conductive fin approaches η = 1; a
    long, thin, low-conductivity one falls off. Returns the dimensionless efficiency
    in (0, 1].
    """
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(perimeter, "[length]", "perimeter")
    _require(conductivity, "[power] / [length] / [temperature]", "conductivity")
    _require(cross_section_area, "[area]", "cross_section_area")
    _require(length, "[length]", "length")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    p = perimeter.to("m").magnitude
    k = conductivity.to("W/(m*K)").magnitude
    a_c = cross_section_area.to("m**2").magnitude
    length_m = length.to("m").magnitude
    if min(h, p, k, a_c, length_m) <= 0:
        raise ValueError("all fin parameters must be positive")
    m = sqrt(h * p / (k * a_c))
    ml = m * length_m
    return tanh(ml) / ml


def fin_effectiveness(
    *,
    fin_efficiency: float,
    fin_surface_area: Quantity,
    base_cross_section_area: Quantity,
) -> float:
    """A fin's effectiveness, ε_fin = η·A_f/A_c,b.

    Whether adding the fin is worth it at all: ε_fin is the heat the fin moves divided by the heat
    the bare base area would have shed, ε_fin = ``fin_efficiency`` η · ``fin_surface_area`` A_f /
    ``base_cross_section_area`` A_c,b (the fin's footprint). Distinct from the efficiency (which
    compares a fin to an ideal isothermal one), effectiveness compares having the fin to not having
    it: a fin is only justified when ε_fin ≳ 2, and high-conductivity, thin, closely spaced fins
    push it well above that. Returns the dimensionless effectiveness.
    """
    _require(fin_surface_area, "[area]", "fin_surface_area")
    _require(base_cross_section_area, "[area]", "base_cross_section_area")
    a_f = fin_surface_area.to("m**2").magnitude
    a_c = base_cross_section_area.to("m**2").magnitude
    if not 0.0 < fin_efficiency <= 1.0:
        raise ValueError(f"fin_efficiency must be in (0, 1]; got {fin_efficiency}")
    if a_f <= 0 or a_c <= 0:
        raise ValueError("fin_surface_area and base_cross_section_area must be positive")
    return fin_efficiency * a_f / a_c


def fin_thermal_resistance(
    *,
    fin_efficiency: float,
    heat_transfer_coefficient: Quantity,
    fin_surface_area: Quantity,
) -> Quantity:
    """A single fin's thermal resistance, R_fin = 1/(η·h·A_f).

    The conduction-plus-convection resistance of one fin between its base and the fluid: R_fin =
    1/(``fin_efficiency`` η · ``heat_transfer_coefficient`` h · ``fin_surface_area`` A_f). It drops
    straight into the series/parallel resistance network (:func:`series_thermal_resistance`,
    :func:`parallel_thermal_resistance`) — a fin sits in parallel with the exposed base between the
    surface and the fluid. A more efficient or larger fin lowers it. Returns the resistance in K/W.
    """
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(fin_surface_area, "[area]", "fin_surface_area")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    a_f = fin_surface_area.to("m**2").magnitude
    if not 0.0 < fin_efficiency <= 1.0:
        raise ValueError(f"fin_efficiency must be in (0, 1]; got {fin_efficiency}")
    if h <= 0 or a_f <= 0:
        raise ValueError("heat_transfer_coefficient and fin_surface_area must be positive")
    return Quantity(magnitude=1.0 / (fin_efficiency * h * a_f), unit="K/W")


def junction_temperature_scorecard(
    name: str,
    *,
    power: Quantity,
    thermal_resistance: Quantity,
    allowable_temperature_rise: Quantity,
    required: float = 1.0,
) -> ScorecardEntry:
    """Screen a junction-to-ambient temperature rise → a :class:`ScorecardEntry`.

    Computes the rise ΔT = Q·R from ``power`` and total ``thermal_resistance`` and
    judges it against ``allowable_temperature_rise`` — the rated junction limit above
    the ambient, a temperature *difference* (e.g. a 125 °C junction over a 40 °C
    ambient is an 85 K budget). The safety factor is the allowable rise over the
    computed rise, so it passes when the junction stays within budget at
    ``required`` margin. ``allowable_temperature_rise`` must be a positive
    ``[temperature]`` quantity.
    """
    _require(allowable_temperature_rise, "[temperature]", "allowable_temperature_rise")
    allowable = temperature_difference_kelvin(
        allowable_temperature_rise, name="allowable_temperature_rise"
    )
    if allowable <= 0:
        raise ValueError(
            f"allowable_temperature_rise must be positive; got {allowable_temperature_rise}"
        )
    rise = temperature_rise(power=power, thermal_resistance=thermal_resistance).to("K").magnitude
    # A zero rise means zero dissipated power (or zero resistance): there was no thermal
    # demand to screen. An infinite safety factor reported that as the strongest possible
    # PASS; `None` -> NOT_EVALUATED says what actually happened.
    computed = None if rise == 0 else allowable / rise
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    # One fixed place is a wide band to hide a shortfall in: an 85.04 K rise against an
    # 85 K allowable printed "junction rise 85.0 K vs 85.0 K allowable" on a FAIL.
    places = decimals_distinguishing(rise, allowable, minimum=1)
    detail = f"junction rise {rise:.{places}f} K vs {allowable:.{places}f} K allowable"
    return entry.model_copy(update={"detail": detail})


def laminar_tube_convection_coefficient(
    *,
    thermal_conductivity: Quantity,
    diameter: Quantity,
    constant_wall_temperature: bool = True,
) -> Quantity:
    """The convection coefficient h for fully-developed laminar flow in a tube (constant Nusselt).

    Unlike turbulent flow, fully-developed laminar tube flow has a *constant* Nusselt number set
    only by the boundary condition: Nu = 3.66 for a constant wall temperature and Nu = 4.36 for a
    constant heat flux. The coefficient is then h = Nu·k/D, from the fluid ``thermal_conductivity``
    k and the tube ``diameter`` D; ``constant_wall_temperature`` picks the boundary condition. It is
    much smaller
    than the turbulent :func:`dittus_boelter_convection_coefficient` — laminar flow is a poor
    heat-transfer regime, which is why exchangers run turbulent. Valid for Re below ~2300; above the
    transition the flow turns turbulent. Returns h in W/(m²·K).
    """
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(diameter, "[length]", "diameter")
    k = thermal_conductivity.to("W/(m*K)").magnitude
    d = diameter.to("m").magnitude
    if k <= 0 or d <= 0:
        raise ValueError("thermal_conductivity and diameter must be positive")
    nusselt = 3.66 if constant_wall_temperature else 4.36
    return Quantity(magnitude=nusselt * k / d, unit="W/(m**2*K)")


def dittus_boelter_convection_coefficient(
    *,
    fluid_velocity: Quantity,
    diameter: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
    heating: bool = True,
) -> Quantity | None:
    """The convection coefficient h for fully-turbulent flow inside a tube (Dittus-Boelter).

    The workhorse correlation for the tube-side coefficient of a heat exchanger: with the pipe
    Reynolds number Re = V·D/ν and the Nusselt number Nu = 0.023·Re^0.8·Pr^n, the coefficient is
    h = Nu·k/D. The exponent n is 0.4 when the fluid is being *heated* and 0.3 when it is *cooled*
    (set by ``heating``). ``fluid_velocity`` V is the mean velocity, ``diameter`` D the inside
    diameter (use :func:`~anvilate.analysis.hydraulic_diameter` for a non-circular duct),
    ``thermal_conductivity`` k and ``kinematic_viscosity`` ν the fluid's, and ``prandtl_number`` Pr
    its Prandtl number.

    Returns ``None`` when Re is below ~10⁴ — Dittus-Boelter is only valid for fully turbulent flow,
    so it reports "not evaluated" for laminar or transitional flow rather than extrapolating.
    Otherwise returns h in W/(m²·K).
    """
    _require(fluid_velocity, "[velocity]", "fluid_velocity")
    _require(diameter, "[length]", "diameter")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    v = fluid_velocity.to("m/s").magnitude
    d = diameter.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if min(v, d, k, nu) <= 0 or prandtl_number <= 0:
        raise ValueError(
            "fluid_velocity, diameter, thermal_conductivity, kinematic_viscosity, and "
            "prandtl_number must be positive"
        )
    reynolds = v * d / nu
    if reynolds < 1.0e4:
        return None
    exponent = 0.4 if heating else 0.3
    nusselt = 0.023 * reynolds**0.8 * prandtl_number**exponent
    return Quantity(magnitude=nusselt * k / d, unit="W/(m**2*K)")


def flat_plate_forced_convection_coefficient(
    *,
    fluid_velocity: Quantity,
    plate_length: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
) -> Quantity | None:
    """The average convection coefficient h for laminar flow over a flat plate.

    The Incropera correlation for external forced convection: with the Reynolds
    number Re_L = V·L/ν and the average Nusselt number Nu = 0.664·Re_L^(1/2)·Pr^(1/3),
    the coefficient is h = Nu·k/L. ``fluid_velocity`` V is the free-stream speed,
    ``plate_length`` L the plate length in the flow direction, ``thermal_conductivity``
    k and ``kinematic_viscosity`` ν the fluid's properties (caller-supplied — Anvilate
    evaluates the correlation, it does not carry a fluid-property database), and
    ``prandtl_number`` Pr its dimensionless Prandtl number.

    Returns ``None`` when Re_L exceeds the laminar limit (~5×10⁵): the flow is
    turbulent and this correlation would extrapolate, so it reports "not evaluated"
    rather than a wrong number — feed a turbulent correlation instead. Otherwise
    returns h in W/(m²·K).
    """
    _require(fluid_velocity, "[velocity]", "fluid_velocity")
    _require(plate_length, "[length]", "plate_length")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    v = fluid_velocity.to("m/s").magnitude
    length_m = plate_length.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if min(v, length_m, k, nu) <= 0:
        raise ValueError(
            "fluid_velocity, plate_length, thermal_conductivity, and kinematic_viscosity "
            "must be positive"
        )
    if prandtl_number <= 0:
        raise ValueError(f"prandtl_number must be positive; got {prandtl_number}")
    reynolds = v * length_m / nu
    if reynolds > _FLAT_PLATE_LAMINAR_RE:
        return None  # turbulent: out of the laminar correlation's validity range
    nusselt = 0.664 * reynolds**0.5 * prandtl_number ** (1.0 / 3.0)
    return Quantity(magnitude=nusselt * k / length_m, unit="W/(m**2*K)")


def flat_plate_turbulent_convection_coefficient(
    *,
    fluid_velocity: Quantity,
    plate_length: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
) -> Quantity | None:
    """The average convection coefficient h for turbulent flow over a flat plate.

    The Incropera correlation for fully turbulent external forced convection:
    Nu = 0.037·Re_L^(4/5)·Pr^(1/3), h = Nu·k/L. The turbulent counterpart of
    :func:`flat_plate_forced_convection_coefficient` — the one to use when that
    function returns ``None`` because the flow has gone turbulent. Arguments are as
    there. Returns ``None`` when Re_L is outside the correlation's validity range
    (5×10⁵ ≤ Re_L ≤ 10⁷): below it the flow is laminar (use the laminar function),
    above it the correlation extrapolates. Otherwise returns h in W/(m²·K).
    """
    _require(fluid_velocity, "[velocity]", "fluid_velocity")
    _require(plate_length, "[length]", "plate_length")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    v = fluid_velocity.to("m/s").magnitude
    length_m = plate_length.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if min(v, length_m, k, nu) <= 0:
        raise ValueError(
            "fluid_velocity, plate_length, thermal_conductivity, and kinematic_viscosity "
            "must be positive"
        )
    if prandtl_number <= 0:
        raise ValueError(f"prandtl_number must be positive; got {prandtl_number}")
    reynolds = v * length_m / nu
    if reynolds < _FLAT_PLATE_LAMINAR_RE or reynolds > 1.0e7:
        return None  # laminar below, or out of the turbulent correlation's range above
    nusselt = 0.037 * reynolds**0.8 * prandtl_number ** (1.0 / 3.0)
    return Quantity(magnitude=nusselt * k / length_m, unit="W/(m**2*K)")


def cylinder_crossflow_convection_coefficient(
    *,
    fluid_velocity: Quantity,
    diameter: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
) -> Quantity | None:
    """The average convection coefficient h for flow across a cylinder (Churchill-Bernstein).

    External crossflow past a tube — a heat-exchanger tube in the wind, a hot-wire anemometer, a pin
    fin — is a different geometry from the flat plate: the flow separates and wraps the back. The
    Churchill-Bernstein correlation spans the whole practical range in one expression, with the
    Reynolds number Re = V·D/ν and

        Nu = 0.3 + [0.62·Re^0.5·Pr^(1/3) / (1 + (0.4/Pr)^(2/3))^0.25]·[1 + (Re/282000)^(5/8)]^(4/5),

    and h = Nu·k/D. ``fluid_velocity`` V is the free-stream speed, ``diameter`` D the cylinder
    diameter, ``thermal_conductivity`` k and ``kinematic_viscosity`` ν the fluid's, and
    ``prandtl_number`` Pr its Prandtl number. Returns ``None`` when Re·Pr < 0.2 (below the
    correlation's validity) rather than extrapolating; otherwise h in W/(m²·K).
    """
    _require(fluid_velocity, "[velocity]", "fluid_velocity")
    _require(diameter, "[length]", "diameter")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    v = fluid_velocity.to("m/s").magnitude
    d = diameter.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if min(v, d, k, nu) <= 0 or prandtl_number <= 0:
        raise ValueError(
            "fluid_velocity, diameter, thermal_conductivity, kinematic_viscosity, and "
            "prandtl_number must be positive"
        )
    reynolds = v * d / nu
    if reynolds * prandtl_number < 0.2:
        return None
    nusselt = 0.3 + (0.62 * reynolds**0.5 * prandtl_number ** (1.0 / 3.0)) / (
        1.0 + (0.4 / prandtl_number) ** (2.0 / 3.0)
    ) ** 0.25 * (1.0 + (reynolds / 282000.0) ** (5.0 / 8.0)) ** (4.0 / 5.0)
    return Quantity(magnitude=nusselt * k / d, unit="W/(m**2*K)")


def sphere_crossflow_convection_coefficient(
    *,
    fluid_velocity: Quantity,
    diameter: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
) -> Quantity | None:
    """The average convection coefficient h for flow past a sphere (Whitaker).

    A sphere in a stream — a droplet, a bead, a falling particle, a temperature probe — carries a
    floor Nusselt of 2 (pure conduction into still fluid) plus a flow term. The Whitaker correlation
    (with the viscosity-ratio correction dropped) is

        Nu = 2 + (0.4·Re^0.5 + 0.06·Re^(2/3))·Pr^0.4,   Re = V·D/ν,

    and h = Nu·k/D. Even at rest (V → 0, Re → 0) it returns the conduction limit Nu = 2, unlike the
    plate and cylinder forms. ``fluid_velocity`` V, ``diameter`` D, ``thermal_conductivity`` k,
    ``kinematic_viscosity`` ν, and ``prandtl_number`` Pr describe the case. Returns ``None`` when Re
    exceeds ~76000 (above Whitaker's validity); otherwise h in W/(m²·K).
    """
    _require(fluid_velocity, "[velocity]", "fluid_velocity")
    _require(diameter, "[length]", "diameter")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    v = fluid_velocity.to("m/s").magnitude
    d = diameter.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if v < 0:
        raise ValueError("fluid_velocity must be non-negative")
    if min(d, k, nu) <= 0 or prandtl_number <= 0:
        raise ValueError(
            "diameter, thermal_conductivity, kinematic_viscosity, and prandtl_number must be "
            "positive"
        )
    reynolds = v * d / nu
    if reynolds > 76000.0:
        return None
    nusselt = 2.0 + (0.4 * reynolds**0.5 + 0.06 * reynolds ** (2.0 / 3.0)) * prandtl_number**0.4
    return Quantity(magnitude=nusselt * k / d, unit="W/(m**2*K)")


def grashof_number(
    *,
    thermal_expansion_coefficient: Quantity,
    temperature_difference: Quantity,
    characteristic_length: Quantity,
    kinematic_viscosity: Quantity,
) -> float:
    """The Grashof number of a natural-convection flow, Gr = g·β·ΔT·L³/ν².

    The ratio of buoyancy to viscous forces that drives natural convection: Gr = g·β·ΔT·L³/ν², from
    the fluid's ``thermal_expansion_coefficient`` β (1/T for an ideal gas), the surface-to-fluid
    ``temperature_difference`` ΔT, the ``characteristic_length`` L (plate height or cylinder
    diameter), and the ``kinematic_viscosity`` ν. It plays the role Reynolds does in forced flow —
    buoyancy stands in for the imposed velocity. Multiplied by the Prandtl number it gives the
    Rayleigh number (:func:`rayleigh_number`) that the natural-convection correlations use. Returns
    the dimensionless Grashof number.
    """
    _require(thermal_expansion_coefficient, "1/[temperature]", "thermal_expansion_coefficient")
    _require(temperature_difference, "[temperature]", "temperature_difference")
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(kinematic_viscosity, "[length]**2/[time]", "kinematic_viscosity")
    beta = thermal_expansion_coefficient.to("1/K").magnitude
    dt = abs(temperature_difference_kelvin(temperature_difference, name="temperature_difference"))
    length = characteristic_length.to("m").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    if length <= 0:
        raise ValueError("characteristic_length must be positive")
    if nu <= 0:
        raise ValueError("kinematic_viscosity must be positive")
    return _STANDARD_GRAVITY * beta * dt * length**3 / nu**2


def rayleigh_number(*, grashof_number: float, prandtl_number: float) -> float:
    """The Rayleigh number of a natural-convection flow, Ra = Gr·Pr.

    The product of the ``grashof_number`` Gr (:func:`grashof_number`) and the ``prandtl_number`` Pr:
    Ra = Gr·Pr. It is the single number the natural-convection Nusselt correlations are written in,
    and it classifies the flow — for a vertical plate the boundary layer stays laminar up to
    Ra ≈ 10⁹ and goes turbulent above it, which decides which correlation applies. Returns the
    dimensionless Rayleigh number.
    """
    if grashof_number < 0:
        raise ValueError("grashof_number must be non-negative")
    if prandtl_number <= 0:
        raise ValueError("prandtl_number must be positive")
    return grashof_number * prandtl_number


def richardson_number(
    *,
    thermal_expansion_coefficient: Quantity,
    temperature_difference: Quantity,
    characteristic_length: Quantity,
    velocity: Quantity,
) -> float:
    """The Richardson number Ri = g·β·ΔT·L/V² — buoyancy vs forced-flow inertia.

    The ratio that decides whether heat transfer is driven by an imposed flow or by buoyancy:
    Ri = g·β·ΔT·L/V², from the fluid's ``thermal_expansion_coefficient`` β, the surface-to-fluid
    ``temperature_difference`` ΔT, the ``characteristic_length`` L, and the forced ``velocity`` V.
    It equals the Grashof number over the Reynolds number squared, Ri = Gr/Re². When Ri ≪ 1 forced
    convection dominates and buoyancy is a small correction; when Ri ≫ 1 natural convection takes
    over and the imposed flow barely matters; near Ri ≈ 1 the two are comparable and the regime is
    mixed convection, where the buoyancy either aids or opposes the flow. The same group with a
    density gradient in place of β·ΔT is the stability criterion for stratified atmospheric and
    ocean flows. Returns the dimensionless Richardson number.

    Source: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*.
    """
    _require(thermal_expansion_coefficient, "1/[temperature]", "thermal_expansion_coefficient")
    _require(temperature_difference, "[temperature]", "temperature_difference")
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(velocity, "[length]/[time]", "velocity")
    beta = thermal_expansion_coefficient.to("1/K").magnitude
    dt = abs(temperature_difference_kelvin(temperature_difference, name="temperature_difference"))
    length = characteristic_length.to("m").magnitude
    v = velocity.to("m/s").magnitude
    if length <= 0:
        raise ValueError("characteristic_length must be positive")
    if v <= 0:
        raise ValueError("velocity must be positive")
    return _STANDARD_GRAVITY * beta * dt * length / v**2


def marangoni_number(
    *,
    surface_tension_temperature_gradient: Quantity,
    temperature_difference: Quantity,
    characteristic_length: Quantity,
    dynamic_viscosity: Quantity,
    thermal_diffusivity: Quantity,
) -> float:
    """The Marangoni number Ma = |dσ/dT|·ΔT·L/(μ·α) — thermocapillary vs diffusive transport.

    The strength of surface-tension-driven (thermocapillary) convection along a free surface with a
    temperature gradient: Ma = |dσ/dT|·ΔT·L/(μ·α), from the ``surface_tension_temperature_gradient``
    dσ/dT, the ``temperature_difference`` ΔT along the surface, the ``characteristic_length`` L, the
    ``dynamic_viscosity`` μ, and the ``thermal_diffusivity`` α. Because surface tension usually
    drops with temperature, the cooler (higher-σ) surface pulls fluid toward it, and above a
    critical Ma ≈ 80 that pull organises into steady thermocapillary cells; higher still it drives
    the vigorous flow that stirs a weld pool, a floating-zone crystal, a solder joint, or a drying
    paint film. It is the surface-tension analogue of the Rayleigh number, dominating over buoyancy
    in thin layers and in microgravity. Returns the dimensionless Marangoni number.

    Source: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*.
    """
    _require(
        surface_tension_temperature_gradient,
        "[force] / [length] / [temperature]",
        "surface_tension_temperature_gradient",
    )
    _require(temperature_difference, "[temperature]", "temperature_difference")
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(dynamic_viscosity, "[pressure]*[time]", "dynamic_viscosity")
    _require(thermal_diffusivity, "[length]**2/[time]", "thermal_diffusivity")
    dsigma_dt = abs(surface_tension_temperature_gradient.to("N/(m*K)").magnitude)
    dt = abs(temperature_difference_kelvin(temperature_difference, name="temperature_difference"))
    length = characteristic_length.to("m").magnitude
    mu = dynamic_viscosity.to("Pa*s").magnitude
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    if length <= 0:
        raise ValueError("characteristic_length must be positive")
    if mu <= 0:
        raise ValueError("dynamic_viscosity must be positive")
    if alpha <= 0:
        raise ValueError("thermal_diffusivity must be positive")
    return dsigma_dt * dt * length / (mu * alpha)


def vertical_plate_natural_convection_coefficient(
    *,
    surface_temperature_difference: Quantity,
    plate_height: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
    thermal_expansion_coefficient: Quantity,
) -> Quantity:
    """The average natural-convection coefficient h on a vertical plate.

    The Churchill–Chu correlation, valid over the whole Rayleigh range:

        Ra = g·β·ΔT·L³·Pr/ν²,
        Nu = {0.825 + 0.387·Ra^(1/6) / [1 + (0.492/Pr)^(9/16)]^(8/27)}²,
        h = Nu·k/L.

    ``surface_temperature_difference`` ΔT is the surface-to-fluid difference,
    ``plate_height`` L the vertical extent, ``thermal_conductivity`` k,
    ``kinematic_viscosity`` ν, ``prandtl_number`` Pr, and
    ``thermal_expansion_coefficient`` β (1/temperature — for an ideal gas ≈ 1/T) the
    fluid's caller-supplied properties (the thermal diffusivity is taken as ν/Pr).
    Buoyancy is the whole mechanism, so a passively-cooled enclosure lives or dies on
    this number. Returns h in W/(m²·K).
    """
    _require(surface_temperature_difference, "[temperature]", "surface_temperature_difference")
    _require(plate_height, "[length]", "plate_height")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    _require(thermal_expansion_coefficient, "1 / [temperature]", "thermal_expansion_coefficient")
    dt = temperature_difference_kelvin(
        surface_temperature_difference, name="surface_temperature_difference"
    )
    length_m = plate_height.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    beta = thermal_expansion_coefficient.to("1/K").magnitude
    if min(dt, length_m, k, nu, beta) <= 0:
        raise ValueError(
            "surface_temperature_difference, plate_height, thermal_conductivity, "
            "kinematic_viscosity, and thermal_expansion_coefficient must be positive"
        )
    if prandtl_number <= 0:
        raise ValueError(f"prandtl_number must be positive; got {prandtl_number}")
    rayleigh = _STANDARD_GRAVITY * beta * dt * length_m**3 * prandtl_number / nu**2
    nusselt = (
        0.825
        + 0.387
        * rayleigh ** (1.0 / 6.0)
        / (1.0 + (0.492 / prandtl_number) ** (9.0 / 16.0)) ** (8.0 / 27.0)
    ) ** 2
    return Quantity(magnitude=nusselt * k / length_m, unit="W/(m**2*K)")


# The stated upper bound of the Churchill-Chu horizontal-cylinder correlation.
_CHURCHILL_CHU_RAYLEIGH_CEILING = 1.0e12


def horizontal_cylinder_natural_convection_coefficient(
    *,
    surface_temperature_difference: Quantity,
    diameter: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
    thermal_expansion_coefficient: Quantity,
) -> Quantity | None:
    """The average natural-convection coefficient h on a long horizontal cylinder.

    The Churchill–Chu correlation for a horizontal cylinder (a hot pipe or tube
    losing heat to still fluid), on the diameter as the characteristic length:

        Ra_D = g·β·ΔT·D³·Pr/ν²,
        Nu = {0.60 + 0.387·Ra_D^(1/6) / [1 + (0.559/Pr)^(9/16)]^(8/27)}²,
        h = Nu·k/D.

    The arguments mirror :func:`vertical_plate_natural_convection_coefficient` with
    ``diameter`` D in place of the plate height; it is a distinct correlation (the
    cylinder's curvature changes the constants). Valid to Ra_D ≈ 10¹², and past that
    ceiling this returns ``None`` — not evaluated — rather than an extrapolated
    coefficient, matching the forced-convection functions in this module. Returns h in
    W/(m²·K).
    """
    _require(surface_temperature_difference, "[temperature]", "surface_temperature_difference")
    _require(diameter, "[length]", "diameter")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    _require(thermal_expansion_coefficient, "1 / [temperature]", "thermal_expansion_coefficient")
    dt = temperature_difference_kelvin(
        surface_temperature_difference, name="surface_temperature_difference"
    )
    d = diameter.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    beta = thermal_expansion_coefficient.to("1/K").magnitude
    if min(dt, d, k, nu, beta) <= 0:
        raise ValueError(
            "surface_temperature_difference, diameter, thermal_conductivity, "
            "kinematic_viscosity, and thermal_expansion_coefficient must be positive"
        )
    if prandtl_number <= 0:
        raise ValueError(f"prandtl_number must be positive; got {prandtl_number}")
    rayleigh = _STANDARD_GRAVITY * beta * dt * d**3 * prandtl_number / nu**2
    # Churchill-Chu is stated valid to Ra_D ~ 1e12 and this was the one natural-convection
    # function in the module that named a ceiling and then ignored it. Past it the returned
    # h overstates the coefficient, which understates a hot vessel's surface temperature and
    # the insulation it needs. The forced-convection siblings return None outside their
    # correlation's range; this now does the same.
    if rayleigh > _CHURCHILL_CHU_RAYLEIGH_CEILING:
        return None
    nusselt = (
        0.60
        + 0.387
        * rayleigh ** (1.0 / 6.0)
        / (1.0 + (0.559 / prandtl_number) ** (9.0 / 16.0)) ** (8.0 / 27.0)
    ) ** 2
    return Quantity(magnitude=nusselt * k / d, unit="W/(m**2*K)")


def horizontal_plate_natural_convection_coefficient(
    *,
    surface_temperature_difference: Quantity,
    characteristic_length: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
    thermal_expansion_coefficient: Quantity,
    hot_surface_facing_up: bool = True,
) -> Quantity:
    """The average natural-convection coefficient h on a horizontal plate.

    Buoyancy behaves very differently above and below a horizontal surface, so the
    correlation depends on which way the hot face points (Incropera):

    - hot face up (or a cold face down) — buoyant plumes lift freely off the surface:
      Nu = 0.54·Ra_L^(1/4) for Ra_L ≤ 10⁷, and 0.15·Ra_L^(1/3) above;
    - hot face down (or a cold face up) — the fluid is trapped and only creeps out
      the edges: Nu = 0.27·Ra_L^(1/4), roughly half the upward-facing value.

    ``characteristic_length`` L is the plate area divided by its perimeter (A/P), the
    convention for this correlation; the other arguments mirror
    :func:`vertical_plate_natural_convection_coefficient`, and
    ``hot_surface_facing_up`` selects the case. Returns h in W/(m²·K).
    """
    _require(surface_temperature_difference, "[temperature]", "surface_temperature_difference")
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    _require(thermal_expansion_coefficient, "1 / [temperature]", "thermal_expansion_coefficient")
    dt = temperature_difference_kelvin(
        surface_temperature_difference, name="surface_temperature_difference"
    )
    length_m = characteristic_length.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    nu = kinematic_viscosity.to("m**2/s").magnitude
    beta = thermal_expansion_coefficient.to("1/K").magnitude
    if min(dt, length_m, k, nu, beta) <= 0:
        raise ValueError(
            "surface_temperature_difference, characteristic_length, thermal_conductivity, "
            "kinematic_viscosity, and thermal_expansion_coefficient must be positive"
        )
    if prandtl_number <= 0:
        raise ValueError(f"prandtl_number must be positive; got {prandtl_number}")
    rayleigh = _STANDARD_GRAVITY * beta * dt * length_m**3 * prandtl_number / nu**2
    if not hot_surface_facing_up:
        nusselt = 0.27 * rayleigh**0.25
    elif rayleigh <= 1.0e7:
        nusselt = 0.54 * rayleigh**0.25
    else:
        nusselt = 0.15 * rayleigh ** (1.0 / 3.0)
    return Quantity(magnitude=nusselt * k / length_m, unit="W/(m**2*K)")


def circular_source_spreading_resistance(
    *,
    source_radius: Quantity,
    conductivity: Quantity,
) -> Quantity:
    """The spreading (constriction) resistance R = 1/(4·k·a) of a circular source (K/W).

    When heat enters a large body through a small patch — a die onto a heat-sink
    base, a bolt head onto a plate — it constricts to the patch and spreads out
    again, and that constriction adds a resistance on top of the bulk conduction.
    For an isothermal circular source of ``source_radius`` a on a semi-infinite body
    of thermal ``conductivity`` k, that spreading resistance is exactly 1/(4·k·a):
    smaller sources and less-conductive substrates spread worse. Add it in series
    with the conduction and convection paths. ``conductivity`` is a
    ``[power]/[length]/[temperature]`` quantity. Returns K/W.
    """
    _require(source_radius, "[length]", "source_radius")
    _require(conductivity, "[power] / [length] / [temperature]", "conductivity")
    a = source_radius.to("m").magnitude
    k = conductivity.to("W/(m*K)").magnitude
    if a <= 0 or k <= 0:
        raise ValueError("source_radius and conductivity must be positive")
    return Quantity(magnitude=1.0 / (4.0 * k * a), unit=_THERMAL_RESISTANCE_UNIT)


def fin_array_thermal_resistance(
    *,
    fin_count: float,
    heat_transfer_coefficient: Quantity,
    fin_efficiency: float,
    fin_surface_area: Quantity,
    unfinned_base_area: Quantity,
) -> Quantity:
    """A fin array's total thermal resistance, R = 1/(h·(N·η·A_f + A_base)).

    The N fins and the exposed base between them sit in *parallel* between the surface and
    the fluid, so their conductances add: h·(``fin_count`` N · ``fin_efficiency`` η ·
    ``fin_surface_area`` A_f + ``unfinned_base_area`` A_base), and the array resistance is
    the reciprocal. :func:`fin_thermal_resistance` is the single-fin term of that sum;
    this is the whole surface, which is the number a junction-temperature check consumes.

    ``fin_count`` is the real count and may be fractional — the design inverse
    :func:`fin_array_count_for_resistance` returns one, and rounding *up* to the physical
    number is a decision for the caller, so this evaluates whichever count it is handed.
    A count of zero is the bare base, which is a real answer as long as there is some base
    left; a surface with no fins and no exposed base carries nothing and is refused rather
    than returned as an infinite resistance. Returns the resistance in K/W.

    Source: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*, the
    fin-array total surface efficiency — the same construction
    :func:`fin_array_count_for_resistance` inverts.
    """
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(fin_surface_area, "[area]", "fin_surface_area")
    _require(unfinned_base_area, "[area]", "unfinned_base_area")
    if not 0 < fin_efficiency <= 1:
        raise ValueError(f"fin_efficiency must be in (0, 1]; got {fin_efficiency}")
    count = require_finite(fin_count, name="fin_count")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    a_f = fin_surface_area.to("m**2").magnitude
    a_base = unfinned_base_area.to("m**2").magnitude
    if count < 0 or h <= 0 or a_f <= 0 or a_base < 0:
        raise ValueError(
            "fin_count and unfinned_base_area must be non-negative, and "
            "heat_transfer_coefficient and fin_surface_area positive"
        )
    area = fin_efficiency * count * a_f + a_base
    if area <= 0:
        raise ValueError(
            "a fin array with no fins and no exposed base has no surface to carry heat "
            "through; its resistance is not a large number, it is undefined"
        )
    return Quantity(magnitude=1.0 / (h * area), unit=_THERMAL_RESISTANCE_UNIT)


def fin_array_count_for_resistance(
    *,
    target_resistance: Quantity,
    heat_transfer_coefficient: Quantity,
    fin_efficiency: float,
    fin_surface_area: Quantity,
    unfinned_base_area: Quantity,
) -> float:
    """The number of fins a target array resistance needs (the fin-array design inverse).

    The inverse of :func:`fin_array_thermal_resistance`, and the pair round-trips exactly:
    the count returned here, put back through that function, lands on
    ``target_resistance``. An array of N identical fins plus the exposed base carries a
    convective
    conductance h·(N·η·A_f + A_base), so its resistance is the reciprocal. Inverting
    for the fin count that just reaches ``target_resistance`` R gives
    N = (1/(h·R) − A_base)/(η·A_f), where ``heat_transfer_coefficient`` h is the
    surface coefficient, ``fin_efficiency`` η the per-fin efficiency (from
    :func:`fin_efficiency`), ``fin_surface_area`` A_f the wetted area of one fin, and
    ``unfinned_base_area`` A_base the exposed base between the fins. Returns the real
    fin count — round *up* for the physical number; returns 0.0 when the bare base
    already meets the target. ``fin_efficiency`` must be in (0, 1].
    """
    _require(target_resistance, "[temperature] / [power]", "target_resistance")
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(fin_surface_area, "[area]", "fin_surface_area")
    _require(unfinned_base_area, "[area]", "unfinned_base_area")
    if not 0 < fin_efficiency <= 1:
        raise ValueError(f"fin_efficiency must be in (0, 1]; got {fin_efficiency}")
    r = target_resistance.to(_THERMAL_RESISTANCE_UNIT).magnitude
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    a_f = fin_surface_area.to("m**2").magnitude
    a_base = unfinned_base_area.to("m**2").magnitude
    if r <= 0 or h <= 0 or a_f <= 0 or a_base < 0:
        raise ValueError(
            "target_resistance, heat_transfer_coefficient, and fin_surface_area must be "
            "positive, and unfinned_base_area non-negative"
        )
    count = (1.0 / (h * r) - a_base) / (fin_efficiency * a_f)
    return max(count, 0.0)


def overall_heat_transfer_coefficient(
    *,
    inside_coefficient: Quantity,
    outside_coefficient: Quantity,
    wall_thickness: Quantity,
    wall_conductivity: Quantity,
    inside_fouling_factor: Quantity | None = None,
    outside_fouling_factor: Quantity | None = None,
) -> Quantity:
    """The overall heat-transfer coefficient U from the series resistances (plane wall).

    The U that :func:`heat_exchanger_duty` and :func:`heat_exchanger_area_for_duty` consume, built
    from the resistances in series through a flat wall: 1/U = 1/h_i + R″_f,i + t/k + R″_f,o + 1/h_o,
    from the inside and outside film coefficients ``inside_coefficient`` h_i and
    ``outside_coefficient`` h_o (the convection correlations in this module supply them), the
    ``wall_thickness`` t and ``wall_conductivity`` k, and optional per-area fouling resistances
    ``inside_fouling_factor`` and ``outside_fouling_factor`` R″_f (m²·K/W, default clean). The
    smallest coefficient dominates 1/U, so U never exceeds the weakest film. Returns U in W/(m²·K).
    """
    _require(inside_coefficient, "[power] / [length]**2 / [temperature]", "inside_coefficient")
    _require(outside_coefficient, "[power] / [length]**2 / [temperature]", "outside_coefficient")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(wall_conductivity, "[power] / [length] / [temperature]", "wall_conductivity")
    hi = inside_coefficient.to("W/(m**2*K)").magnitude
    ho = outside_coefficient.to("W/(m**2*K)").magnitude
    t = wall_thickness.to("m").magnitude
    k = wall_conductivity.to("W/(m*K)").magnitude
    if hi <= 0 or ho <= 0 or k <= 0:
        raise ValueError("film coefficients and wall_conductivity must be positive")
    if t < 0:
        raise ValueError("wall_thickness must be non-negative")
    rfi = 0.0
    if inside_fouling_factor is not None:
        _require(
            inside_fouling_factor, "[length]**2 * [temperature] / [power]", "inside_fouling_factor"
        )
        rfi = inside_fouling_factor.to("m**2*K/W").magnitude
    rfo = 0.0
    if outside_fouling_factor is not None:
        _require(
            outside_fouling_factor,
            "[length]**2 * [temperature] / [power]",
            "outside_fouling_factor",
        )
        rfo = outside_fouling_factor.to("m**2*K/W").magnitude
    if rfi < 0 or rfo < 0:
        raise ValueError("fouling factors must be non-negative")
    resistance = 1.0 / hi + rfi + t / k + rfo + 1.0 / ho
    return Quantity(magnitude=1.0 / resistance, unit="W/(m**2*K)")


def fouling_factor_from_coefficients(
    *,
    clean_coefficient: Quantity,
    service_coefficient: Quantity,
) -> Quantity:
    """The fouling resistance implied by a drop in U, R″_f = 1/U_service − 1/U_clean.

    The extra per-area thermal resistance fouling has added, backed out of the clean and fouled
    overall coefficients: R″_f = 1/``service_coefficient`` − 1/``clean_coefficient``. It is the
    design allowance a TEMA fouling factor represents, and the quantity to compare against
    tabulated values when deciding cleaning intervals. The service coefficient must not exceed the
    clean one (fouling only adds resistance). Returns R″_f in m²·K/W.
    """
    _require(clean_coefficient, "[power] / [length]**2 / [temperature]", "clean_coefficient")
    _require(service_coefficient, "[power] / [length]**2 / [temperature]", "service_coefficient")
    uc = clean_coefficient.to("W/(m**2*K)").magnitude
    us = service_coefficient.to("W/(m**2*K)").magnitude
    if uc <= 0 or us <= 0:
        raise ValueError("clean_coefficient and service_coefficient must be positive")
    if us > uc:
        raise ValueError(
            "service_coefficient cannot exceed clean_coefficient (fouling adds resistance)"
        )
    return Quantity(magnitude=1.0 / us - 1.0 / uc, unit="m**2*K/W")


def cleanliness_factor(
    *,
    service_coefficient: Quantity,
    clean_coefficient: Quantity,
) -> float:
    """The cleanliness factor, CF = U_service/U_clean.

    The fouled overall coefficient as a fraction of the clean one: CF =
    ``service_coefficient``/``clean_coefficient``, the dimensionless condition metric used to grade
    a heat exchanger's fouling state (1.0 is spotless; ~0.85 a common design target). It is the
    ratio companion to the additive :func:`fouling_factor_from_coefficients`. The service
    coefficient must not exceed the clean one. Returns the dimensionless cleanliness factor.
    """
    _require(service_coefficient, "[power] / [length]**2 / [temperature]", "service_coefficient")
    _require(clean_coefficient, "[power] / [length]**2 / [temperature]", "clean_coefficient")
    us = service_coefficient.to("W/(m**2*K)").magnitude
    uc = clean_coefficient.to("W/(m**2*K)").magnitude
    if us <= 0 or uc <= 0:
        raise ValueError("service_coefficient and clean_coefficient must be positive")
    if us > uc:
        raise ValueError("service_coefficient cannot exceed clean_coefficient")
    return us / uc


def shell_and_tube_lmtd_correction_factor(
    *,
    hot_inlet_temperature: Quantity,
    hot_outlet_temperature: Quantity,
    cold_inlet_temperature: Quantity,
    cold_outlet_temperature: Quantity,
) -> float:
    """The LMTD correction factor F for a 1-shell-pass, 2-tube-pass exchanger (Bowman/TEMA).

    :func:`log_mean_temperature_difference` gives the *counterflow* driving force, which is the
    best any exchanger can do. A real shell-and-tube unit does not achieve it: with two tube
    passes, half the tube length runs counter to the shell flow and half runs with it, so the mean
    driving force is smaller. F is the ratio, and the design ΔT is F·ΔT_lm.

    With R = (T₁−T₂)/(t₂−t₁), P = (t₂−t₁)/(T₁−t₁) and s = √(R²+1):

        F = [s/(R−1)]·ln[(1−P)/(1−P·R)] / ln[(2/P − 1 − R + s)/(2/P − 1 − R − s)]

    F → 1 as P → 0 (a small temperature rise on the tube side approaches counterflow) and falls
    away as the streams are pushed closer together. For 200→100 °C shell-side against 30→80 °C
    tube-side it is 0.8924, so the counterflow ΔT_lm of 92.77 K is really 82.78 K and an area sized
    on the uncorrected value is **12% short**.

    The second failure it catches is worse than undersizing. Push the outlets into a temperature
    *cross* — the cold stream leaving hotter than the hot stream leaves — and the logarithm's
    argument goes negative: no 1-2 exchanger can meet that duty at any area, so the function
    raises rather than returning a number. That is a real design gate, not a math guard; the
    answer is more shell passes or a different configuration.

    All four temperatures are absolute Quantities. Returns F as a plain float in (0, 1].
    """
    _require(hot_inlet_temperature, "[temperature]", "hot_inlet_temperature")
    _require(hot_outlet_temperature, "[temperature]", "hot_outlet_temperature")
    _require(cold_inlet_temperature, "[temperature]", "cold_inlet_temperature")
    _require(cold_outlet_temperature, "[temperature]", "cold_outlet_temperature")
    t_hot_in = hot_inlet_temperature.to("K").magnitude
    t_hot_out = hot_outlet_temperature.to("K").magnitude
    t_cold_in = cold_inlet_temperature.to("K").magnitude
    t_cold_out = cold_outlet_temperature.to("K").magnitude
    if t_hot_in <= t_cold_in:
        raise ValueError(
            f"hot_inlet_temperature must exceed cold_inlet_temperature; got "
            f"{hot_inlet_temperature} against {cold_inlet_temperature}"
        )
    if t_hot_out > t_hot_in:
        raise ValueError("the hot stream must cool: hot_outlet cannot exceed hot_inlet")
    if t_cold_out < t_cold_in:
        raise ValueError("the cold stream must warm: cold_outlet cannot be below cold_inlet")
    if t_cold_out == t_cold_in:
        raise ValueError("cold_outlet_temperature must exceed cold_inlet_temperature")
    r = (t_hot_in - t_hot_out) / (t_cold_out - t_cold_in)
    p_eff = (t_cold_out - t_cold_in) / (t_hot_in - t_cold_in)
    s = sqrt(r * r + 1.0)
    # R = 1 is the removable singularity of the bracket, not a real discontinuity; the limit form
    # is the standard one and keeps a balanced exchanger (equal capacity rates) from dividing by 0.
    if abs(r - 1.0) < 1.0e-9:
        numerator = p_eff * s / (1.0 - p_eff)
    else:
        # P*R reduces exactly to (T_hot_in - T_hot_out)/(T_hot_in - T_cold_in), which is
        # 1 whenever the hot outlet meets the cold inlet — the zero-approach limit an
        # engineer types with round numbers. Only the numerator was guarded, so that one
        # point divided by zero while 1 K either side of it raised a clean message.
        if abs(1.0 - p_eff * r) < 1.0e-12:
            raise ValueError(
                "the hot outlet reaches the cold inlet (a zero temperature approach), "
                "which needs infinite area: no correction factor exists there"
            )
        inner = (1.0 - p_eff) / (1.0 - p_eff * r)
        if inner <= 0.0:
            raise ValueError(
                "these terminal temperatures are unreachable by a 1-shell-pass exchanger at any "
                "area (the correction factor's logarithm has no real value there). Use more shell "
                "passes or a different configuration."
            )
        numerator = (s / (r - 1.0)) * log(inner)
    denominator_upper = 2.0 / p_eff - 1.0 - r + s
    denominator_lower = 2.0 / p_eff - 1.0 - r - s
    if denominator_lower <= 0.0 or denominator_upper <= 0.0:
        raise ValueError(
            "these terminal temperatures are unreachable by a 1-shell-pass exchanger at any area "
            "(a temperature cross). Use more shell passes or a different configuration."
        )
    return numerator / log(denominator_upper / denominator_lower)


def log_mean_temperature_difference(
    *,
    delta_t_1: Quantity,
    delta_t_2: Quantity,
) -> Quantity:
    """The log-mean temperature difference ΔT_lm = (ΔT₁ − ΔT₂)/ln(ΔT₁/ΔT₂) (K).

    The effective driving temperature difference across a heat exchanger, whose local
    value changes along the length as the streams approach each other.
    ``delta_t_1`` and ``delta_t_2`` are the two terminal approach differences (for a
    counterflow exchanger, hot-in − cold-out and hot-out − cold-in; for parallel flow,
    hot-in − cold-in and hot-out − cold-out) — both temperature *differences* in
    kelvin, both positive. When the two are equal the log form is indeterminate and
    the LMTD is simply their common value. Returns ΔT_lm in K.
    """
    _require(delta_t_1, "[temperature]", "delta_t_1")
    _require(delta_t_2, "[temperature]", "delta_t_2")
    dt1 = temperature_difference_kelvin(delta_t_1, name="delta_t_1")
    dt2 = temperature_difference_kelvin(delta_t_2, name="delta_t_2")
    if dt1 <= 0 or dt2 <= 0:
        raise ValueError("delta_t_1 and delta_t_2 must be positive temperature differences")
    if dt1 == dt2:
        return Quantity(magnitude=dt1, unit="K")
    return Quantity(magnitude=(dt1 - dt2) / log(dt1 / dt2), unit="K")


def heat_exchanger_area_for_duty(
    *,
    duty: Quantity,
    overall_coefficient: Quantity,
    log_mean_temperature_difference: Quantity,
) -> Quantity:
    """The heat-transfer area A = Q/(U·ΔT_lm) a heat duty requires (m²).

    Sizing inverse of :func:`heat_exchanger_duty`: the surface area an exchanger needs
    to move ``duty`` Q with an overall heat-transfer ``overall_coefficient`` U and a
    ``log_mean_temperature_difference`` ΔT_lm. U comes from the wall and film
    resistances in series (the convection coefficients in this module feed it). Returns
    the area in m².
    """
    _require(duty, "[power]", "duty")
    _require(overall_coefficient, "[power] / [length]**2 / [temperature]", "overall_coefficient")
    _require(log_mean_temperature_difference, "[temperature]", "log_mean_temperature_difference")
    q = duty.to("W").magnitude
    u = overall_coefficient.to("W/(m**2*K)").magnitude
    lmtd = temperature_difference_kelvin(
        log_mean_temperature_difference, name="log_mean_temperature_difference"
    )
    if q <= 0 or u <= 0 or lmtd <= 0:
        raise ValueError("duty, overall_coefficient, and the LMTD must be positive")
    return Quantity(magnitude=q / (u * lmtd), unit="m**2")


def heat_exchanger_duty(
    *,
    overall_coefficient: Quantity,
    area: Quantity,
    log_mean_temperature_difference: Quantity,
) -> Quantity:
    """The heat duty Q = U·A·ΔT_lm an exchanger delivers (W).

    The rating form: the heat an exchanger of ``area`` A moves at an overall
    ``overall_coefficient`` U across a ``log_mean_temperature_difference`` ΔT_lm.
    Returns the duty in W.
    """
    _require(overall_coefficient, "[power] / [length]**2 / [temperature]", "overall_coefficient")
    _require(area, "[area]", "area")
    _require(log_mean_temperature_difference, "[temperature]", "log_mean_temperature_difference")
    u = overall_coefficient.to("W/(m**2*K)").magnitude
    a = area.to("m**2").magnitude
    lmtd = temperature_difference_kelvin(
        log_mean_temperature_difference, name="log_mean_temperature_difference"
    )
    if u <= 0 or a <= 0 or lmtd <= 0:
        raise ValueError("overall_coefficient, area, and the LMTD must be positive")
    return Quantity(magnitude=u * a * lmtd, unit="W")


def heat_exchanger_ntu(
    *,
    overall_coefficient: Quantity,
    area: Quantity,
    min_heat_capacity_rate: Quantity,
) -> float:
    """The number of transfer units NTU = U·A/C_min of a heat exchanger.

    A dimensionless size — how many transfer units the exchanger carries relative to
    the weaker stream's heat capacity rate. ``overall_coefficient`` U and ``area`` A
    are the exchanger's, and ``min_heat_capacity_rate`` C_min is the smaller of the
    two stream ṁ·c_p products (a ``[power]/[temperature]`` quantity, W/K). Feeds
    :func:`counterflow_effectiveness`. Returns the dimensionless NTU.
    """
    _require(overall_coefficient, "[power] / [length]**2 / [temperature]", "overall_coefficient")
    _require(area, "[area]", "area")
    _require(min_heat_capacity_rate, "[power] / [temperature]", "min_heat_capacity_rate")
    u = overall_coefficient.to("W/(m**2*K)").magnitude
    a = area.to("m**2").magnitude
    c_min = min_heat_capacity_rate.to("W/K").magnitude
    if u <= 0 or a <= 0 or c_min <= 0:
        raise ValueError("overall_coefficient, area, and min_heat_capacity_rate must be positive")
    return u * a / c_min


def heat_exchanger_effectiveness_from_temperatures(
    *,
    minimum_capacity_inlet_temperature: Quantity,
    minimum_capacity_outlet_temperature: Quantity,
    opposite_inlet_temperature: Quantity,
) -> float:
    """The measured heat-exchanger effectiveness, ε = |ΔT_Cmin|/(T_hot,in − T_cold,in).

    The effectiveness read from an operating exchanger's terminal temperatures, to compare against
    the ε-NTU prediction (:func:`counterflow_effectiveness` and its siblings). The minimum-capacity
    stream always sees the larger temperature change, so ε is its actual swing over the maximum
    thermodynamically available — the full inlet-to-inlet difference: ε =
    |``minimum_capacity_outlet_temperature`` − ``minimum_capacity_inlet_temperature``| /
    |``opposite_inlet_temperature`` − ``minimum_capacity_inlet_temperature``|. Feed it the C_min
    stream's own inlet and outlet plus the *other* stream's inlet (whether C_min is the hot or cold
    side). An ε well below the design value flags fouling or bypassing. Temperatures are absolute.
    Returns the dimensionless effectiveness (0 to 1).
    """
    _require(
        minimum_capacity_inlet_temperature, "[temperature]", "minimum_capacity_inlet_temperature"
    )
    _require(
        minimum_capacity_outlet_temperature, "[temperature]", "minimum_capacity_outlet_temperature"
    )
    _require(opposite_inlet_temperature, "[temperature]", "opposite_inlet_temperature")
    t_in = minimum_capacity_inlet_temperature.to("K").magnitude
    t_out = minimum_capacity_outlet_temperature.to("K").magnitude
    t_other = opposite_inlet_temperature.to("K").magnitude
    max_difference = t_other - t_in
    if max_difference == 0:
        raise ValueError(
            "the two inlet temperatures are equal, so no heat can transfer (undefined ε)"
        )
    # Signed, not absolute, on both halves. ε = q/q_max against q_max = C_min·(T_other,in − T_in)
    # is a second-law bound, so the honest value lies in [0, 1]. Taking the numerator's magnitude
    # discarded the direction of heat flow: a stream measured leaving COLDER than it entered while
    # sitting next to a hotter one folded onto the positive side and read back as a plausible
    # "16.7% effective, badly fouled" instead of the impossible measurement it is. The signed
    # ratio puts that case below zero and an outlet overshooting the opposite inlet above one,
    # and both are refused here rather than left for a downstream ε-NTU inverse to reject.
    effectiveness = (t_out - t_in) / max_difference
    if effectiveness < 0.0:
        raise ValueError(
            f"the C_min stream leaves at {t_out:g} K, moving AWAY from the opposite inlet at "
            f"{t_other:g} K rather than toward it (it entered at {t_in:g} K); heat cannot flow "
            "that way, so check which stream is which and the sign of the measurement"
        )
    if effectiveness > 1.0:
        raise ValueError(
            f"effectiveness came to {effectiveness:g}, above the second-law maximum of 1: the "
            f"C_min outlet ({t_out:g} K) has passed the opposite inlet ({t_other:g} K), which no "
            "heat exchanger can do; check the measured temperatures"
        )
    return effectiveness


def counterflow_effectiveness(*, ntu: float, capacity_ratio: float) -> float:
    """The effectiveness ε of a counterflow heat exchanger (the ε-NTU method).

    When the outlet temperatures are unknown, the effectiveness — the actual heat
    transfer as a fraction of the thermodynamic maximum — is found from the size and
    the stream balance rather than an LMTD. For counterflow,

        ε = [1 − exp(−NTU·(1 − C_r))] / [1 − C_r·exp(−NTU·(1 − C_r))]   (C_r < 1),
        ε = NTU/(1 + NTU)                                              (C_r = 1),

    where ``ntu`` is :func:`heat_exchanger_ntu` and ``capacity_ratio`` C_r = C_min/C_max
    (0 to 1). The actual duty is then ε·C_min·(T_hot,in − T_cold,in). ``ntu`` must be
    non-negative and ``capacity_ratio`` in [0, 1]. Returns ε in [0, 1].
    """
    if ntu < 0:
        raise ValueError(f"ntu must be non-negative; got {ntu}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    if capacity_ratio == 1:
        return ntu / (1.0 + ntu)
    exponent = exp(-ntu * (1.0 - capacity_ratio))
    return (1.0 - exponent) / (1.0 - capacity_ratio * exponent)


def parallel_flow_effectiveness(*, ntu: float, capacity_ratio: float) -> float:
    """The effectiveness ε of a parallel-flow heat exchanger (the ε-NTU method).

    The complement to :func:`counterflow_effectiveness` for streams that enter at the
    same end and run together: ε = [1 − exp(−NTU·(1 + C_r))] / (1 + C_r), where ``ntu``
    is :func:`heat_exchanger_ntu` and ``capacity_ratio`` C_r = C_min/C_max (0 to 1).
    Parallel flow is always less effective than counterflow for the same size, and its
    effectiveness is capped at 1/(1 + C_r) no matter how large the exchanger — the
    outlets converge to a common temperature before the maximum transfer is reached.
    ``ntu`` non-negative, ``capacity_ratio`` in [0, 1]. Returns ε in [0, 1].
    """
    if ntu < 0:
        raise ValueError(f"ntu must be non-negative; got {ntu}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    return (1.0 - exp(-ntu * (1.0 + capacity_ratio))) / (1.0 + capacity_ratio)


def crossflow_both_unmixed_effectiveness(*, ntu: float, capacity_ratio: float) -> float:
    """The effectiveness ε of a crossflow exchanger with both fluids unmixed (ε-NTU).

    Crossflow — the streams run at right angles, as in a car radiator or an HVAC coil —
    is the common compact-exchanger arrangement, and with both fluids unmixed its
    effectiveness follows the standard approximation

        ε = 1 − exp{ (1/C_r)·NTU^0.22·[exp(−C_r·NTU^0.78) − 1] },

    which sits between :func:`parallel_flow_effectiveness` and
    :func:`counterflow_effectiveness`. ``ntu`` is :func:`heat_exchanger_ntu` and
    ``capacity_ratio`` C_r = C_min/C_max in [0, 1]; at C_r = 0 (a boiler or condenser)
    it reduces to 1 − exp(−NTU), as every arrangement does. ``ntu`` non-negative.
    Returns ε in [0, 1].
    """
    if ntu < 0:
        raise ValueError(f"ntu must be non-negative; got {ntu}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    if capacity_ratio == 0 or ntu == 0:
        return 1.0 - exp(-ntu)
    return 1.0 - exp((1.0 / capacity_ratio) * ntu**0.22 * (exp(-capacity_ratio * ntu**0.78) - 1.0))


def counterflow_ntu_for_effectiveness(*, effectiveness: float, capacity_ratio: float) -> float:
    """The NTU a counterflow exchanger needs for a target effectiveness (the sizing form).

    The design inverse of :func:`counterflow_effectiveness`: given a required
    ``effectiveness`` ε and the stream balance ``capacity_ratio`` C_r, the number of
    transfer units (hence U·A) the exchanger must have,

        NTU = 1/(C_r − 1)·ln[(ε − 1)/(ε·C_r − 1)]   (C_r < 1),
        NTU = ε/(1 − ε)                             (C_r = 1).

    A counterflow exchanger can reach any ε < 1, so ``effectiveness`` must be in
    (0, 1) and ``capacity_ratio`` in [0, 1]. Size the area from NTU = U·A/C_min.
    Returns the required (dimensionless) NTU.
    """
    if not 0 < effectiveness < 1:
        raise ValueError(f"effectiveness must be in (0, 1); got {effectiveness}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    if capacity_ratio == 1:
        return effectiveness / (1.0 - effectiveness)
    if capacity_ratio == 0:
        return -log(1.0 - effectiveness)
    return (1.0 / (capacity_ratio - 1.0)) * log(
        (effectiveness - 1.0) / (effectiveness * capacity_ratio - 1.0)
    )


def parallel_flow_ntu_for_effectiveness(*, effectiveness: float, capacity_ratio: float) -> float:
    """The NTU a parallel-flow exchanger needs for a target effectiveness (sizing form).

    The design inverse of :func:`parallel_flow_effectiveness`:
    NTU = −ln[1 − ε·(1 + C_r)]/(1 + C_r). Because parallel flow caps out at
    ε_max = 1/(1 + C_r), a ``effectiveness`` at or above that ceiling is unreachable
    at any size and is rejected — a signal to switch to counterflow.
    ``capacity_ratio`` C_r in [0, 1]. Returns the required (dimensionless) NTU.
    """
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    ceiling = 1.0 / (1.0 + capacity_ratio)
    if not 0 < effectiveness < ceiling:
        raise ValueError(
            f"effectiveness must be in (0, {ceiling:.4g}) — parallel flow cannot exceed "
            f"1/(1+C_r); got {effectiveness}"
        )
    return -log(1.0 - effectiveness * (1.0 + capacity_ratio)) / (1.0 + capacity_ratio)


def shell_and_tube_effectiveness(*, ntu: float, capacity_ratio: float) -> float:
    """The effectiveness ε of a 1-shell-pass shell-and-tube exchanger (the ε-NTU method).

    The shell-and-tube exchanger — one shell pass over 2, 4, … tube passes — is the industrial
    workhorse, and its baffled, part-counterflow-part-parallel path gives a distinct closed form,

        ε₁ = 2 / { (1 + C_r) + √(1 + C_r²)·[1 + exp(−NTU·√(1 + C_r²))]
                                          / [1 − exp(−NTU·√(1 + C_r²))] },

    for ``ntu`` = :func:`heat_exchanger_ntu` and ``capacity_ratio`` C_r = C_min/C_max in [0, 1].
    It sits below :func:`counterflow_effectiveness` and above :func:`parallel_flow_effectiveness`
    for the same size, and at C_r = 0 (a boiler or condenser) reduces to 1 − exp(−NTU) like every
    arrangement. ``ntu`` non-negative. Returns ε in [0, 1].
    """
    if ntu < 0:
        raise ValueError(f"ntu must be non-negative; got {ntu}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    if ntu == 0:
        return 0.0
    root = sqrt(1.0 + capacity_ratio**2)
    e = exp(-ntu * root)
    return 2.0 / ((1.0 + capacity_ratio) + root * (1.0 + e) / (1.0 - e))


def shell_and_tube_ntu_for_effectiveness(*, effectiveness: float, capacity_ratio: float) -> float:
    """The NTU a 1-shell-pass shell-and-tube exchanger needs for a target effectiveness (sizing).

    The design inverse of :func:`shell_and_tube_effectiveness`: with
    E = [2/ε₁ − (1 + C_r)]/√(1 + C_r²),

        NTU = −ln[(E − 1)/(E + 1)] / √(1 + C_r²).

    A single shell pass cannot reach the counterflow ceiling — its maximum effectiveness is
    ε_max = 2/[(1 + C_r) + √(1 + C_r²)] — so an ``effectiveness`` at or above that limit is
    unreachable at any size and is rejected (add shell passes, or switch to counterflow).
    ``capacity_ratio`` C_r in [0, 1]. Returns the required (dimensionless) NTU.
    """
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    root = sqrt(1.0 + capacity_ratio**2)
    ceiling = 2.0 / ((1.0 + capacity_ratio) + root)
    if not 0 < effectiveness < ceiling:
        raise ValueError(
            f"effectiveness must be in (0, {ceiling:.4g}) — one shell pass cannot exceed "
            f"2/[(1+C_r)+√(1+C_r²)]; got {effectiveness}"
        )
    e_param = (2.0 / effectiveness - (1.0 + capacity_ratio)) / root
    return -log((e_param - 1.0) / (e_param + 1.0)) / root


def crossflow_cmax_mixed_effectiveness(*, ntu: float, capacity_ratio: float) -> float:
    """The effectiveness ε of a crossflow exchanger with the C_max stream mixed (ε-NTU).

    The companion to :func:`crossflow_both_unmixed_effectiveness` for the common case where the
    larger-capacity stream is free to mix laterally (an unbaffled gas side) while the C_min stream
    stays unmixed (in tubes):

        ε = (1/C_r)·{ 1 − exp[ −C_r·(1 − exp(−NTU)) ] },

    an exact closed form (no approximation), for ``ntu`` = :func:`heat_exchanger_ntu` and
    ``capacity_ratio`` C_r = C_min/C_max in (0, 1]. At C_r = 0 it reduces to 1 − exp(−NTU). Mixing
    the C_max stream costs a little effectiveness versus both-unmixed. ``ntu`` non-negative. Returns
    ε in [0, 1].
    """
    if ntu < 0:
        raise ValueError(f"ntu must be non-negative; got {ntu}")
    if not 0 <= capacity_ratio <= 1:
        raise ValueError(f"capacity_ratio must lie in [0, 1]; got {capacity_ratio}")
    if capacity_ratio == 0:
        return 1.0 - exp(-ntu)
    return (1.0 / capacity_ratio) * (1.0 - exp(-capacity_ratio * (1.0 - exp(-ntu))))


def biot_number(
    *,
    heat_transfer_coefficient: Quantity,
    characteristic_length: Quantity,
    thermal_conductivity: Quantity,
) -> float:
    """The Biot number Bi = h·L_c/k — whether a body cools as one lump.

    The ratio of a body's internal conduction resistance to its surface convection
    resistance. When Bi < 0.1 the inside stays nearly uniform in temperature as the
    body heats or cools, so the lumped-capacitance model (a single temperature vs
    time) applies; above that an internal gradient develops and a distributed solution
    is needed. ``characteristic_length`` L_c is the volume-to-surface-area ratio V/A,
    ``heat_transfer_coefficient`` h the surface coefficient, and
    ``thermal_conductivity`` k the body's. Returns the dimensionless Bi.
    """
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    lc = characteristic_length.to("m").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    if h <= 0 or lc <= 0 or k <= 0:
        raise ValueError("all inputs must be positive")
    return h * lc / k


def thermal_diffusivity(
    *,
    thermal_conductivity: Quantity,
    density: Quantity,
    specific_heat: Quantity,
) -> Quantity:
    """The thermal diffusivity, α = k/(ρ·c_p).

    How fast a temperature disturbance spreads through a material, as opposed to how much heat it
    conducts: from the ``thermal_conductivity`` k, the ``density`` ρ, and the ``specific_heat`` c_p,
    α = k/(ρ·c_p). It is the property that sets the pace of every transient — the α in the Fourier
    number (:func:`fourier_number`), the Péclet number (:func:`peclet_number`), and the √(α·t)
    penetration depth of a thermal front. A metal (high k, α ~ 1e-4 m²/s) equalises temperature far
    faster than a plastic or a gas of the same heat capacity. Returns the diffusivity in m²/s.
    """
    _require(thermal_conductivity, "[power]/[length]/[temperature]", "thermal_conductivity")
    _require(density, "[mass]/[length]**3", "density")
    _require(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    k = thermal_conductivity.to("W/(m*K)").magnitude
    rho = density.to("kg/m**3").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    if k <= 0:
        raise ValueError("thermal_conductivity must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if cp <= 0:
        raise ValueError("specific_heat must be positive")
    return Quantity(magnitude=k / (rho * cp), unit="m**2/s")


def fourier_number(
    *,
    thermal_diffusivity: Quantity,
    time: Quantity,
    characteristic_length: Quantity,
) -> float:
    """The Fourier number Fo = α·t/L² — the dimensionless time of a transient.

    A dimensionless clock for heat diffusion: Fo = α·t/L², from the ``thermal_diffusivity`` α (= k/ρ
    c_p), the elapsed ``time`` t, and the ``characteristic_length`` L. It measures how far a thermal
    disturbance has soaked into a body relative to its size — small Fo means the transient is barely
    begun (the core has not felt the surface change), and past Fo ≈ 0.2 the transient is
    well-developed, which is where the one-term Heisler-chart approximation becomes accurate. With
    the Biot number (:func:`biot_number`) it is the pair that governs all transient conduction.
    Returns
    the dimensionless Fo.
    """
    _require(thermal_diffusivity, "[length]**2/[time]", "thermal_diffusivity")
    _require(time, "[time]", "time")
    _require(characteristic_length, "[length]", "characteristic_length")
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    t = time.to("s").magnitude
    length = characteristic_length.to("m").magnitude
    if alpha <= 0 or length <= 0:
        raise ValueError("thermal_diffusivity and characteristic_length must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    return alpha * t / length**2


def peclet_number(
    *,
    velocity: Quantity,
    characteristic_length: Quantity,
    thermal_diffusivity: Quantity,
) -> float:
    """The thermal Péclet number Pe = V·L/α — advection vs conduction of heat.

    The ratio of heat carried by bulk flow to heat spread by conduction: Pe = V·L/α, from the flow
    ``velocity`` V, the ``characteristic_length`` L, and the ``thermal_diffusivity`` α = k/(ρ·c_p).
    It equals the product of the Reynolds and Prandtl numbers, Pe = Re·Pr. At low Pe conduction
    dominates and the temperature field is nearly symmetric; at high Pe the flow sweeps heat
    downstream before it can diffuse, which is why forced-convection heat exchangers and thermal
    entry lengths scale with it. The same group with mass diffusivity in place of α is the
    mass-transfer Péclet number (Pe = Re·Sc). Returns the dimensionless Pe.
    """
    _require(velocity, "[length]/[time]", "velocity")
    _require(characteristic_length, "[length]", "characteristic_length")
    _require(thermal_diffusivity, "[length]**2/[time]", "thermal_diffusivity")
    v = velocity.to("m/s").magnitude
    length = characteristic_length.to("m").magnitude
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    if length <= 0 or alpha <= 0:
        raise ValueError("characteristic_length and thermal_diffusivity must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return v * length / alpha


def brinkman_number(
    *,
    dynamic_viscosity: Quantity,
    velocity: Quantity,
    thermal_conductivity: Quantity,
    temperature_difference: Quantity,
) -> float:
    """The Brinkman number Br = μ·V²/(k·ΔT) — viscous heating vs conduction.

    The ratio of heat generated by viscous friction within a flow to heat conducted away to the
    wall: Br = μ·V²/(k·ΔT), from the ``dynamic_viscosity`` μ, the ``velocity`` V, the
    ``thermal_conductivity`` k, and the wall-to-fluid ``temperature_difference`` ΔT. It equals the
    product of the Eckert and Prandtl numbers, Br = Ec·Pr. When Br ≪ 1 viscous dissipation is
    negligible and the temperature field is set by the boundary conditions alone; when Br ≳ 1 the
    fluid heats itself appreciably — the reason a polymer melt in an extruder, a heavily loaded
    journal bearing, or a fast capillary-viscometer run can run far hotter than its walls and even
    show a temperature maximum inside the flow. Returns the dimensionless Brinkman number.

    Source: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*.
    """
    _require(dynamic_viscosity, "[pressure]*[time]", "dynamic_viscosity")
    _require(velocity, "[length]/[time]", "velocity")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(temperature_difference, "[temperature]", "temperature_difference")
    mu = dynamic_viscosity.to("Pa*s").magnitude
    v = velocity.to("m/s").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    delta_t = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    if mu <= 0:
        raise ValueError("dynamic_viscosity must be positive")
    if k <= 0:
        raise ValueError("thermal_conductivity must be positive")
    if delta_t <= 0:
        raise ValueError("temperature_difference must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return mu * v**2 / (k * delta_t)


def lumped_capacitance_time_constant(
    *,
    density: Quantity,
    volume: Quantity,
    specific_heat: Quantity,
    heat_transfer_coefficient: Quantity,
    surface_area: Quantity,
) -> Quantity:
    """The lumped-capacitance thermal time constant τ = ρ·V·c_p/(h·A) (seconds).

    How fast a body (small Biot number — see :func:`biot_number`) responds to a step
    change in its surroundings: its temperature difference from the ambient decays as
    exp(−t/τ), reaching 63% of the change in one τ. ``density`` ρ, ``volume`` V, and
    ``specific_heat`` c_p are the body's thermal mass; ``heat_transfer_coefficient`` h
    and ``surface_area`` A its heat-loss path. A heavy, insulated body has a long τ (it
    coasts through temperature swings); a light, well-cooled one a short τ. Returns τ
    in seconds.
    """
    _require(density, "[mass] / [length]**3", "density")
    _require(volume, "[length]**3", "volume")
    _require(specific_heat, "[energy] / [mass] / [temperature]", "specific_heat")
    _require(
        heat_transfer_coefficient,
        "[power] / [length]**2 / [temperature]",
        "heat_transfer_coefficient",
    )
    _require(surface_area, "[area]", "surface_area")
    rho = density.to("kg/m**3").magnitude
    v = volume.to("m**3").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    h = heat_transfer_coefficient.to("W/(m**2*K)").magnitude
    a = surface_area.to("m**2").magnitude
    if min(rho, v, cp, h, a) <= 0:
        raise ValueError("all inputs must be positive")
    return Quantity(magnitude=rho * v * cp / (h * a), unit="s")


def lumped_capacitance_cooling_time(
    *,
    initial_excess_temperature: Quantity,
    target_excess_temperature: Quantity,
    time_constant: Quantity,
) -> Quantity:
    """The time t = τ·ln(θ_0/θ) for a lumped body to cool to a target (seconds).

    Inverting the exponential decay θ(t) = θ_0·exp(−t/τ): the time for the body's
    excess temperature over the ambient to fall from ``initial_excess_temperature`` θ_0
    to ``target_excess_temperature`` θ, given the ``time_constant`` τ from
    :func:`lumped_capacitance_time_constant`. Both excess temperatures are differences
    over the ambient (kelvin), with the target below the initial. Returns the time in
    seconds.
    """
    _require(initial_excess_temperature, "[temperature]", "initial_excess_temperature")
    _require(target_excess_temperature, "[temperature]", "target_excess_temperature")
    _require(time_constant, "[time]", "time_constant")
    theta_0 = temperature_difference_kelvin(
        initial_excess_temperature, name="initial_excess_temperature"
    )
    theta = temperature_difference_kelvin(
        target_excess_temperature, name="target_excess_temperature"
    )
    tau = time_constant.to("s").magnitude
    if theta_0 <= 0 or theta <= 0 or tau <= 0:
        raise ValueError("the excess temperatures and time constant must be positive")
    if theta >= theta_0:
        raise ValueError("target_excess_temperature must be below initial_excess_temperature")
    return Quantity(magnitude=tau * log(theta_0 / theta), unit="s")


def lumped_capacitance_excess_temperature(
    *,
    initial_excess_temperature: Quantity,
    time: Quantity,
    time_constant: Quantity,
) -> Quantity:
    """The excess temperature of a cooling lumped body, θ(t) = θ_0·exp(−t/τ).

    The forward of :func:`lumped_capacitance_cooling_time` and the transient a body follows under
    Newton's law of cooling: its temperature difference over the ambient decays exponentially from
    ``initial_excess_temperature`` θ_0 with the ``time_constant`` τ (from
    :func:`lumped_capacitance_time_constant`), reaching θ(t) = θ_0·exp(−t/``time``). After one τ the
    excess has fallen to 37% of its start, after three τ to 5% (effectively settled). Add the result
    back to the ambient for the actual temperature. Valid for a small Biot number (see
    :func:`biot_number`), where the body stays nearly uniform. Returns the excess temperature (a
    difference in kelvin).
    """
    _require(initial_excess_temperature, "[temperature]", "initial_excess_temperature")
    _require(time, "[time]", "time")
    _require(time_constant, "[time]", "time_constant")
    theta_0 = temperature_difference_kelvin(
        initial_excess_temperature, name="initial_excess_temperature"
    )
    t = time.to("s").magnitude
    tau = time_constant.to("s").magnitude
    if theta_0 <= 0:
        raise ValueError("initial_excess_temperature must be positive")
    if t < 0:
        raise ValueError("time must be non-negative")
    if tau <= 0:
        raise ValueError("time_constant must be positive")
    return Quantity(magnitude=theta_0 * exp(-t / tau), unit="K")


def semi_infinite_solid_temperature_rise(
    *,
    surface_step_change: Quantity,
    depth: Quantity,
    time: Quantity,
    thermal_diffusivity: Quantity,
) -> Quantity:
    """The temperature rise at depth in a semi-infinite solid after a surface step (Incropera 5.7).

    When one face of a thick body is suddenly held at a new temperature — a quenched slab, a
    weld heat-affected zone, the ground after a cold snap — the change diffuses inward, and
    for early times (before it reaches the far side) the body behaves as *semi-infinite*.
    The rise at depth x and time t is ΔT(x, t) = ΔT_s·erfc(x/(2·√(α·t))), where ΔT_s is the
    sudden surface step and erfc the complementary error function. ``surface_step_change``
    ΔT_s = T_surface − T_initial (a temperature difference), ``depth`` x below the surface,
    ``time`` t since the step, and ``thermal_diffusivity`` α = k/(ρ·c_p). At the surface the
    rise equals ΔT_s; it decays with depth over the thermal penetration depth ~ √(α·t). Add
    the result to the initial temperature for the actual temperature. Returns the temperature
    rise at that point (a difference in kelvin).
    """
    _require(surface_step_change, "[temperature]", "surface_step_change")
    _require(depth, "[length]", "depth")
    _require(time, "[time]", "time")
    if not isinstance(thermal_diffusivity, Quantity):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2 / [time] quantity; "
            f"got {thermal_diffusivity!r}"
        )
    if not thermal_diffusivity.has_dimension("[length]**2 / [time]"):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2/[time] quantity; got "
            f"{thermal_diffusivity.dimensionality}"
        )
    delta_ts = temperature_difference_kelvin(surface_step_change, name="surface_step_change")
    x = depth.to("m").magnitude
    t = time.to("s").magnitude
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    if x < 0:
        raise ValueError(f"depth must be non-negative; got {depth}")
    if t <= 0 or alpha <= 0:
        raise ValueError("time and thermal_diffusivity must be positive")
    eta = x / (2.0 * sqrt(alpha * t))
    return Quantity(magnitude=delta_ts * (1.0 - erf(eta)), unit="K")


def semi_infinite_solid_surface_flux(
    *,
    surface_step_change: Quantity,
    time: Quantity,
    thermal_conductivity: Quantity,
    thermal_diffusivity: Quantity,
) -> Quantity:
    """The surface heat flux q₀'' = k·ΔT_s/√(π·α·t) drawn by a semi-infinite solid.

    The companion to :func:`semi_infinite_solid_temperature_rise`: to hold the surface at
    its stepped temperature, heat must flow across the face, and for the constant-surface-
    temperature case that instantaneous flux is q₀'' = k·ΔT_s/√(π·α·t). ``surface_step_change``
    ΔT_s = T_surface − T_initial, ``time`` t since the step, ``thermal_conductivity`` k, and
    ``thermal_diffusivity`` α. The flux is huge just after the step (it diverges as t → 0)
    and decays as 1/√t as the thermal layer thickens — the reason a quench pulls the most
    heat in the first instants. Returns the surface heat flux in W/m² (its magnitude).
    """
    _require(surface_step_change, "[temperature]", "surface_step_change")
    _require(time, "[time]", "time")
    if not isinstance(thermal_conductivity, Quantity):
        raise ValueError(
            f"thermal_conductivity must be a [power] / [length] / [temperature] quantity; "
            f"got {thermal_conductivity!r}"
        )
    if not thermal_conductivity.has_dimension("[power] / [length] / [temperature]"):
        raise ValueError(
            f"thermal_conductivity must be a [power]/[length]/[temperature] quantity; got "
            f"{thermal_conductivity.dimensionality}"
        )
    if not isinstance(thermal_diffusivity, Quantity):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2 / [time] quantity; "
            f"got {thermal_diffusivity!r}"
        )
    if not thermal_diffusivity.has_dimension("[length]**2 / [time]"):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2/[time] quantity; got "
            f"{thermal_diffusivity.dimensionality}"
        )
    delta_ts = abs(temperature_difference_kelvin(surface_step_change, name="surface_step_change"))
    t = time.to("s").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    if t <= 0 or k <= 0 or alpha <= 0:
        raise ValueError("time, thermal_conductivity, and thermal_diffusivity must be positive")
    return Quantity(magnitude=k * delta_ts / sqrt(pi * alpha * t), unit="W/m**2")


def radiation_heat_transfer(
    *,
    emissivity: float,
    area: Quantity,
    surface_temperature: Quantity,
    surroundings_temperature: Quantity,
) -> Quantity:
    """The net radiant heat q = ε·σ·A·(T_s⁴ − T_surr⁴) a surface exchanges (W).

    The third heat-transfer mode: every surface radiates, and the net exchange with
    large surroundings goes as the *fourth power* of absolute temperature, so radiation
    overtakes convection at high temperature. ``emissivity`` ε (0 to 1) is the
    surface's, ``area`` A its radiating area, ``surface_temperature`` T_s and
    ``surroundings_temperature`` T_surr the *absolute* temperatures (pass them in
    kelvin — a fourth power needs a true zero). A positive result is heat leaving the
    surface. Returns the net radiant power in W.
    """
    if not 0 <= emissivity <= 1:
        raise ValueError(f"emissivity must lie in [0, 1]; got {emissivity}")
    _require(area, "[area]", "area")
    _require(surface_temperature, "[temperature]", "surface_temperature")
    _require(surroundings_temperature, "[temperature]", "surroundings_temperature")
    a = area.to("m**2").magnitude
    ts = surface_temperature.to("K").magnitude
    tsur = surroundings_temperature.to("K").magnitude
    if a <= 0 or ts <= 0 or tsur <= 0:
        raise ValueError("area and the absolute temperatures must be positive")
    return Quantity(magnitude=emissivity * _STEFAN_BOLTZMANN * a * (ts**4 - tsur**4), unit="W")


def radiation_two_surface_exchange(
    *,
    emissivity_1: float,
    area_1: Quantity,
    temperature_1: Quantity,
    emissivity_2: float,
    area_2: Quantity,
    temperature_2: Quantity,
    view_factor: float,
) -> Quantity:
    """The net radiation between two gray surfaces of an enclosure (the radiation-network result).

    Where :func:`radiation_heat_transfer` handles one surface against large black surroundings, two
    real gray surfaces that see each other exchange less, because each reflects part of what it
    receives. The net flow from surface 1 to surface 2 runs through three thermal resistances in
    series — surface 1's, the space (view-factor) resistance, and surface 2's:

        Q₁₂ = σ·(T₁⁴ − T₂⁴) / [ (1 − ε₁)/(ε₁·A₁) + 1/(A₁·F₁₂) + (1 − ε₂)/(ε₂·A₂) ].

    ``emissivity_1``/``emissivity_2`` are the gray emissivities (0 to 1), ``area_1``/``area_2`` the
    surface areas, ``temperature_1``/``temperature_2`` the *absolute* temperatures (kelvin — a
    fourth power needs a true zero), and ``view_factor`` F₁₂ the fraction of surface 1's radiation
    that lands on surface 2 (a geometry term the caller supplies). For infinite parallel plates
    (A₁ = A₂, F₁₂ = 1) this collapses to the familiar σ(T₁⁴ − T₂⁴)/(1/ε₁ + 1/ε₂ − 1). A positive
    result is heat leaving surface 1. Returns the net radiant power in W.
    """
    if not 0 < emissivity_1 <= 1:
        raise ValueError(f"emissivity_1 must lie in (0, 1]; got {emissivity_1}")
    if not 0 < emissivity_2 <= 1:
        raise ValueError(f"emissivity_2 must lie in (0, 1]; got {emissivity_2}")
    if not 0 < view_factor <= 1:
        raise ValueError(f"view_factor must lie in (0, 1]; got {view_factor}")
    _require(area_1, "[area]", "area_1")
    _require(area_2, "[area]", "area_2")
    _require(temperature_1, "[temperature]", "temperature_1")
    _require(temperature_2, "[temperature]", "temperature_2")
    a1 = area_1.to("m**2").magnitude
    a2 = area_2.to("m**2").magnitude
    t1 = temperature_1.to("K").magnitude
    t2 = temperature_2.to("K").magnitude
    if a1 <= 0 or a2 <= 0 or t1 <= 0 or t2 <= 0:
        raise ValueError("areas and the absolute temperatures must be positive")
    resistance = (1 - emissivity_1) / (emissivity_1 * a1) + 1 / (a1 * view_factor)
    resistance += (1 - emissivity_2) / (emissivity_2 * a2)
    return Quantity(magnitude=_STEFAN_BOLTZMANN * (t1**4 - t2**4) / resistance, unit="W")


def radiation_heat_transfer_coefficient(
    *,
    emissivity: float,
    surface_temperature: Quantity,
    surroundings_temperature: Quantity,
) -> Quantity:
    """The linearized radiation coefficient h_r = ε·σ·(T_s² + T_surr²)(T_s + T_surr).

    Radiation folded into an equivalent convection coefficient, so it can be added to
    the true convection coefficient and put through the same resistance network
    (q_rad = h_r·A·(T_s − T_surr)). ``emissivity`` ε, ``surface_temperature`` T_s, and
    ``surroundings_temperature`` T_surr (both *absolute*, in kelvin). Because it embeds
    the operating temperatures, h_r rises steeply with temperature — the reason
    radiation matters little near ambient but dominates in a furnace. Returns h_r in
    W/(m²·K).
    """
    if not 0 <= emissivity <= 1:
        raise ValueError(f"emissivity must lie in [0, 1]; got {emissivity}")
    _require(surface_temperature, "[temperature]", "surface_temperature")
    _require(surroundings_temperature, "[temperature]", "surroundings_temperature")
    ts = surface_temperature.to("K").magnitude
    tsur = surroundings_temperature.to("K").magnitude
    if ts <= 0 or tsur <= 0:
        raise ValueError("the absolute temperatures must be positive")
    hr = emissivity * _STEFAN_BOLTZMANN * (ts**2 + tsur**2) * (ts + tsur)
    return Quantity(magnitude=hr, unit="W/(m**2*K)")


def wien_peak_wavelength(*, temperature: Quantity) -> Quantity:
    """The wavelength of peak blackbody emission, λ_max = b/T (Wien's displacement law).

    A hot body radiates across a spectrum, but the wavelength it emits most strongly shifts
    inversely with its absolute ``temperature``: λ_max = b/T, with b = 2.8978×10⁻³ m·K. It is why a
    heating element glows dull red, then orange, then white as it climbs — the peak marching out of
    infrared and up through the visible — and why the Sun (≈ 5800 K) peaks in green at about 500 nm
    while a room-temperature object peaks deep in the infrared near 10 µm. Returns the peak
    wavelength as a length.
    """
    _require(temperature, "[temperature]", "temperature")
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute)")
    return Quantity(magnitude=_WIEN_DISPLACEMENT / t, unit="m")


def wien_temperature_from_peak(*, peak_wavelength: Quantity) -> Quantity:
    """The blackbody temperature from its peak emission wavelength, T = b/λ_max (Wien inverted).

    The inverse of :func:`wien_peak_wavelength`: measure the wavelength a hot body radiates most
    strongly and Wien's law gives its temperature, T = b/λ_max, with b = 2.8978×10⁻³ m·K. This is
    how a spectral (color) pyrometer takes the temperature of something too hot or too far to touch
    — a furnace, a filament, a star. Returns the temperature in kelvin.
    """
    _require(peak_wavelength, "[length]", "peak_wavelength")
    lam = peak_wavelength.to("m").magnitude
    if lam <= 0:
        raise ValueError("peak_wavelength must be positive")
    return Quantity(magnitude=_WIEN_DISPLACEMENT / lam, unit="K")


def planetary_equilibrium_temperature(
    *,
    solar_flux: Quantity,
    albedo: float = 0.0,
    emissivity: float = 1.0,
) -> Quantity:
    """The radiative-equilibrium temperature of a planet, T = [S·(1 − a)/(4·ε·σ)]^(1/4).

    A body in space warms until it re-radiates exactly the sunlight it absorbs. A sphere intercepts
    the beam over its disc (π·R²) but radiates over its whole surface (4·π·R²), so balancing
    absorbed S·(1 − ``albedo``)·π·R² against emitted ``emissivity``·σ·4·π·R²·T⁴ gives
    T = [S·(1 − a)/(4·ε·σ)]^(1/4), from the ``solar_flux`` S at the body's orbit (1361 W/m² at
    Earth). It is the airless effective temperature — Earth's is 255 K (−18 °C), and the 33 K gap
    to its real surface is the greenhouse effect this bare balance omits. ``albedo`` a and
    ``emissivity`` ε are in [0, 1]. Returns the equilibrium temperature in kelvin.
    """
    _require(solar_flux, "[power]/[area]", "solar_flux")
    s = solar_flux.to("W/m**2").magnitude
    if s <= 0:
        raise ValueError("solar_flux must be positive")
    if not 0.0 <= albedo < 1.0:
        raise ValueError("albedo must lie in [0, 1)")
    if not 0.0 < emissivity <= 1.0:
        raise ValueError("emissivity must lie in (0, 1]")
    t = (s * (1.0 - albedo) / (4.0 * emissivity * _STEFAN_BOLTZMANN)) ** 0.25
    return Quantity(magnitude=t, unit="K")


def crossed_strings_view_factor(
    *,
    crossed_string_1: Quantity,
    crossed_string_2: Quantity,
    uncrossed_string_1: Quantity,
    uncrossed_string_2: Quantity,
    surface_1_width: Quantity,
) -> float:
    """Hottel's crossed-strings view factor, F₁₂ = (Σ crossed − Σ uncrossed)/(2·w₁).

    The view factor between two infinitely long surfaces of arbitrary 2D cross-section, by Hottel's
    crossed-strings construction: stretch imaginary strings between the four edge pairs, then
    F₁₂ = (crossed_1 + crossed_2 − uncrossed_1 − uncrossed_2)/(2·``surface_1_width``). The two
    ``crossed_string`` lengths connect opposite edges (they cross the gap), the two
    ``uncrossed_string`` lengths connect same-side edges, and w₁ is the width of surface 1. It fits
    tilted, offset, and blocked geometries that closed-form charts do not. Returns the view factor
    F₁₂ (dimensionless, 0 to 1).
    """
    _require(crossed_string_1, "[length]", "crossed_string_1")
    _require(crossed_string_2, "[length]", "crossed_string_2")
    _require(uncrossed_string_1, "[length]", "uncrossed_string_1")
    _require(uncrossed_string_2, "[length]", "uncrossed_string_2")
    _require(surface_1_width, "[length]", "surface_1_width")
    c1 = crossed_string_1.to("m").magnitude
    c2 = crossed_string_2.to("m").magnitude
    u1 = uncrossed_string_1.to("m").magnitude
    u2 = uncrossed_string_2.to("m").magnitude
    w1 = surface_1_width.to("m").magnitude
    if w1 <= 0:
        raise ValueError("surface_1_width must be positive")
    if min(c1, c2, u1, u2) < 0:
        raise ValueError("string lengths must be non-negative")
    f12 = (c1 + c2 - u1 - u2) / (2.0 * w1)
    if not 0.0 <= f12 <= 1.0:
        raise ValueError(
            f"computed view factor {f12:.4f} is outside [0, 1]; check the string assignments"
        )
    return f12


def view_factor_reciprocity(
    *, area_1: Quantity, view_factor_1_to_2: float, area_2: Quantity
) -> float:
    """The reciprocity relation for view factors, F₂₁ = A₁·F₁₂/A₂.

    The complementary view factor from the reciprocity theorem A₁·F₁₂ = A₂·F₂₁: from the ``area_1``
    A₁, the known ``view_factor_1_to_2`` F₁₂, and the ``area_2`` A₂, F₂₁ = A₁·F₁₂/A₂. It converts a
    view factor known one way into the other — so a small surface facing a large one sees a large
    fraction of it while the large one sees only a little back. Returns the view factor F₂₁
    (dimensionless).
    """
    _require(area_1, "[area]", "area_1")
    _require(area_2, "[area]", "area_2")
    a1 = area_1.to("m**2").magnitude
    a2 = area_2.to("m**2").magnitude
    if a1 <= 0:
        raise ValueError("area_1 must be positive")
    if a2 <= 0:
        raise ValueError("area_2 must be positive")
    if not 0.0 <= view_factor_1_to_2 <= 1.0:
        raise ValueError("view_factor_1_to_2 must be in [0, 1]")
    return a1 * view_factor_1_to_2 / a2


def radiation_shield_reduction_factor(*, number_of_shields: int) -> float:
    """The radiation-shield reduction factor, q_shielded/q_unshielded = 1/(N + 1).

    How much radiant heat transfer between two large parallel surfaces is cut by inserting ``N``
    thin shields of the same emissivity between them: q_shielded/q_unshielded = 1/(N + 1). A shield
    halves the flux, three quarters it, and so on — the principle of multi-layer insulation (MLI) on
    spacecraft, of the shields in a cryostat, and of a firefighter's reflective blanket. It assumes
    all surfaces share one emissivity; differing emissivities shift the factor but not the 1/(N+1)
    trend. Returns the reduction factor (dimensionless, 0 to 1).
    """
    if not isinstance(number_of_shields, int) or number_of_shields < 0:
        raise ValueError("number_of_shields must be a non-negative integer")
    return 1.0 / (number_of_shields + 1)
