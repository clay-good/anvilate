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

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "constrained_thermal_stress",
    "free_thermal_expansion",
    "shrink_fit_assembly_temperature",
    "DifferentialThermalStress",
    "differential_thermal_stress",
]


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
