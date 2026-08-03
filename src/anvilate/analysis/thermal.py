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

from math import pi, sqrt, tanh

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "constrained_thermal_stress",
    "thermal_shock_stress",
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
]

_THERMAL_RESISTANCE_UNIT = "K/W"


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


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
