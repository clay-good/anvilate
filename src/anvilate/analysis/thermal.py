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
"""

from __future__ import annotations

from math import erf, exp, log, pi, sqrt, tanh

from pydantic import BaseModel, ConfigDict

from ..scorecard import ScorecardEntry
from ..units import Quantity

__all__ = [
    "confined_liquid_thermal_pressure",
    "constrained_thermal_stress",
    "thermal_shock_stress",
    "thermal_shock_temperature_limit",
    "triaxial_constrained_thermal_stress",
    "through_wall_gradient_thermal_stress",
    "thermal_buckling_temperature_rise",
    "free_thermal_expansion",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
    "bimetallic_strip_curvature",
    "bimetallic_strip_tip_deflection",
    "conduction_thermal_resistance",
    "convection_thermal_resistance",
    "series_thermal_resistance",
    "parallel_thermal_resistance",
    "temperature_rise",
    "fin_efficiency",
    "junction_temperature_scorecard",
    "dittus_boelter_convection_coefficient",
    "flat_plate_forced_convection_coefficient",
    "flat_plate_turbulent_convection_coefficient",
    "vertical_plate_natural_convection_coefficient",
    "horizontal_cylinder_natural_convection_coefficient",
    "horizontal_plate_natural_convection_coefficient",
    "circular_source_spreading_resistance",
    "fin_array_count_for_resistance",
    "log_mean_temperature_difference",
    "heat_exchanger_area_for_duty",
    "heat_exchanger_duty",
    "heat_exchanger_ntu",
    "counterflow_effectiveness",
    "parallel_flow_effectiveness",
    "crossflow_both_unmixed_effectiveness",
    "counterflow_ntu_for_effectiveness",
    "parallel_flow_ntu_for_effectiveness",
    "biot_number",
    "lumped_capacitance_time_constant",
    "lumped_capacitance_cooling_time",
    "semi_infinite_solid_temperature_rise",
    "semi_infinite_solid_surface_flux",
    "radiation_heat_transfer",
    "radiation_heat_transfer_coefficient",
]

_STEFAN_BOLTZMANN = 5.670374419e-8  # W/(m²·K⁴)

_THERMAL_RESISTANCE_UNIT = "K/W"
# The laminar–turbulent transition Reynolds number for external flow over a flat
# plate (Incropera). Above it the laminar correlation no longer holds.
_FLAT_PLATE_LAMINAR_RE = 5.0e5
_STANDARD_GRAVITY = 9.80665  # m/s², for the buoyancy-driven Rayleigh number


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


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
    if not volumetric_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "volumetric_expansion_coefficient must have units of 1/temperature; got "
            f"{volumetric_expansion_coefficient.dimensionality}"
        )
    _require(bulk_modulus, "[pressure]", "bulk_modulus")
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    beta = volumetric_expansion_coefficient.to("1/K").magnitude
    k = bulk_modulus.to("Pa").magnitude
    dt = temperature_change.to("K").magnitude
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
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
        )
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    e = elastic_modulus.to("MPa").magnitude
    alpha = thermal_expansion_coefficient.to("1/K").magnitude
    delta_t = temperature_change.to("K").magnitude
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
    """
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
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
    delta_t = temperature_change.to("K").magnitude
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
    """
    _require(fracture_strength, "[pressure]", "fracture_strength")
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
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
    """
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
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
    delta_t = temperature_change.to("K").magnitude
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
    """
    if not elastic_modulus.has_dimension("[pressure]"):
        raise ValueError(
            f"elastic_modulus must be a [pressure] quantity; got {elastic_modulus.dimensionality}"
        )
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
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
    delta_t = temperature_difference.to("K").magnitude
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
    if not length.has_dimension("[length]"):
        raise ValueError(f"length must be a [length] quantity; got {length.dimensionality}")
    if not thermal_expansion_coefficient.has_dimension("1 / [temperature]"):
        raise ValueError(
            "thermal_expansion_coefficient must have units of 1/temperature; got "
            f"{thermal_expansion_coefficient.dimensionality}"
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
    delta_t = temperature_change.to("K").magnitude
    return Quantity(magnitude=alpha * size * delta_t, unit="mm")


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
    if not interface_diameter.has_dimension("[length]"):
        raise ValueError(
            f"interface_diameter must be a [length] quantity; got "
            f"{interface_diameter.dimensionality}"
        )
    if not diametral_interference.has_dimension("[length]"):
        raise ValueError(
            f"diametral_interference must be a [length] quantity; got "
            f"{diametral_interference.dimensionality}"
        )
    if not assembly_clearance.has_dimension("[length]"):
        raise ValueError(
            f"assembly_clearance must be a [length] quantity; got "
            f"{assembly_clearance.dimensionality}"
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
    delta_t = temperature_change.to("K").magnitude
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
    if not temperature_change.has_dimension("[temperature]"):
        raise ValueError(
            f"temperature_change must be a temperature difference; got "
            f"{temperature_change.dimensionality}"
        )
    delta_t = temperature_change.to("K").magnitude
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
    allowable = allowable_temperature_rise.to("K").magnitude
    if allowable <= 0:
        raise ValueError(
            f"allowable_temperature_rise must be positive; got {allowable_temperature_rise}"
        )
    rise = temperature_rise(power=power, thermal_resistance=thermal_resistance).to("K").magnitude
    computed = float("inf") if rise == 0 else allowable / rise
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = f"junction rise {rise:.1f} K vs {allowable:.1f} K allowable"
    return entry.model_copy(update={"detail": detail})


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
    dt = surface_temperature_difference.to("K").magnitude
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


def horizontal_cylinder_natural_convection_coefficient(
    *,
    surface_temperature_difference: Quantity,
    diameter: Quantity,
    thermal_conductivity: Quantity,
    kinematic_viscosity: Quantity,
    prandtl_number: float,
    thermal_expansion_coefficient: Quantity,
) -> Quantity:
    """The average natural-convection coefficient h on a long horizontal cylinder.

    The Churchill–Chu correlation for a horizontal cylinder (a hot pipe or tube
    losing heat to still fluid), on the diameter as the characteristic length:

        Ra_D = g·β·ΔT·D³·Pr/ν²,
        Nu = {0.60 + 0.387·Ra_D^(1/6) / [1 + (0.559/Pr)^(9/16)]^(8/27)}²,
        h = Nu·k/D.

    The arguments mirror :func:`vertical_plate_natural_convection_coefficient` with
    ``diameter`` D in place of the plate height; it is a distinct correlation (the
    cylinder's curvature changes the constants). Valid to Ra_D ≈ 10¹². Returns h in
    W/(m²·K).
    """
    _require(surface_temperature_difference, "[temperature]", "surface_temperature_difference")
    _require(diameter, "[length]", "diameter")
    _require(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    _require(kinematic_viscosity, "[length]**2 / [time]", "kinematic_viscosity")
    _require(thermal_expansion_coefficient, "1 / [temperature]", "thermal_expansion_coefficient")
    dt = surface_temperature_difference.to("K").magnitude
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
    dt = surface_temperature_difference.to("K").magnitude
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


def fin_array_count_for_resistance(
    *,
    target_resistance: Quantity,
    heat_transfer_coefficient: Quantity,
    fin_efficiency: float,
    fin_surface_area: Quantity,
    unfinned_base_area: Quantity,
) -> float:
    """The number of fins a target array resistance needs (the fin-array design inverse).

    An array of N identical fins plus the exposed base carries a convective
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
    dt1 = delta_t_1.to("K").magnitude
    dt2 = delta_t_2.to("K").magnitude
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
    lmtd = log_mean_temperature_difference.to("K").magnitude
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
    lmtd = log_mean_temperature_difference.to("K").magnitude
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
    theta_0 = initial_excess_temperature.to("K").magnitude
    theta = target_excess_temperature.to("K").magnitude
    tau = time_constant.to("s").magnitude
    if theta_0 <= 0 or theta <= 0 or tau <= 0:
        raise ValueError("the excess temperatures and time constant must be positive")
    if theta >= theta_0:
        raise ValueError("target_excess_temperature must be below initial_excess_temperature")
    return Quantity(magnitude=tau * log(theta_0 / theta), unit="s")


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
    if not thermal_diffusivity.has_dimension("[length]**2 / [time]"):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2/[time] quantity; got "
            f"{thermal_diffusivity.dimensionality}"
        )
    delta_ts = surface_step_change.to("K").magnitude
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
    if not thermal_conductivity.has_dimension("[power] / [length] / [temperature]"):
        raise ValueError(
            f"thermal_conductivity must be a [power]/[length]/[temperature] quantity; got "
            f"{thermal_conductivity.dimensionality}"
        )
    if not thermal_diffusivity.has_dimension("[length]**2 / [time]"):
        raise ValueError(
            f"thermal_diffusivity must be a [length]**2/[time] quantity; got "
            f"{thermal_diffusivity.dimensionality}"
        )
    delta_ts = abs(surface_step_change.to("K").magnitude)
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
