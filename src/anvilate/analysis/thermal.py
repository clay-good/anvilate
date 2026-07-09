"""T1 analytical thermal-stress check (closed-form).

A member that would expand or contract with a temperature change but is fully
restrained develops a thermal stress with no mechanical load: ``σ = E·α·ΔT``,
where ``E`` is the elastic modulus, ``α`` the coefficient of thermal expansion,
and ``ΔT`` the temperature change. Compression on heating (positive ΔT), tension
on cooling. Inputs are dimension-checked :class:`~anvilate.units.Quantity` values.

``ΔT`` is a temperature *difference* — pass it in kelvin or ``delta_degC``, not an
absolute ``degC`` reading.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "constrained_thermal_stress",
]


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
