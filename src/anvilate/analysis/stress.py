"""T1 stress-combination utilities (von Mises equivalent stress).

The individual checks in this package report component stresses — a bending
stress from a beam, a shear stress from a shaft. A ductile part yields on the
*combined* state, so those components are rolled into a single von Mises
equivalent stress before comparing to the yield strength:

    plane stress:      σ_vm = √(σx² − σx·σy + σy² + 3·τxy²)
    bending + torsion: σ_vm = √(σ² + 3·τ²)   (the common shaft case)

Inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity`
stresses; a helper returns the factor of safety against yield.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "yield_safety_factor",
]


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    return value.to("MPa").magnitude


def von_mises_plane_stress(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for a 2D plane-stress state.

    σ_vm = √(σx² − σx·σy + σy² + 3·τxy²). All three components must be stresses
    (pressure). Returns the equivalent stress in MPa.
    """
    sx = _require_stress(sigma_x, "sigma_x")
    sy = _require_stress(sigma_y, "sigma_y")
    txy = _require_stress(tau_xy, "tau_xy")
    vm = sqrt(sx * sx - sx * sy + sy * sy + 3 * txy * txy)
    return Quantity(magnitude=vm, unit="MPa")


def von_mises_bending_torsion(
    *,
    bending_stress: Quantity,
    shear_stress: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for the common bending-plus-torsion case.

    σ_vm = √(σ² + 3·τ²), the plane-stress form with a single normal stress
    ``bending_stress`` (σ) and a single shear ``shear_stress`` (τ) — e.g. a shaft
    carrying both a bending moment and a torque. Returns the equivalent stress in
    MPa.
    """
    sigma = _require_stress(bending_stress, "bending_stress")
    tau = _require_stress(shear_stress, "shear_stress")
    vm = sqrt(sigma * sigma + 3 * tau * tau)
    return Quantity(magnitude=vm, unit="MPa")


def yield_safety_factor(equivalent_stress: Quantity, yield_strength: Quantity) -> float:
    """The factor of safety against yielding: yield strength / equivalent stress.

    Both arguments must be stresses. A value below 1 means the part yields.
    """
    sigma = _require_stress(equivalent_stress, "equivalent_stress")
    sy = _require_stress(yield_strength, "yield_strength")
    return sy / sigma
