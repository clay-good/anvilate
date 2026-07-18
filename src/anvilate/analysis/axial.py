"""T1 analytical direct-stress check (axial tension / compression).

The simplest stress state: a member carrying an axial ``force`` over a
cross-sectional ``area`` develops a uniform direct stress ``σ = F/A``. It is the
normal-stress input to the von Mises combination for a tension rod or a bolt
shank, and its own screening check against yield. Sizing runs the other way —
:func:`required_axial_area` inverts it to the least area a load needs within an
allowable stress. Area helpers for the common solid sections are provided. As
elsewhere, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "circular_area",
    "axial_stress",
    "required_axial_area",
    "axial_elongation",
    "axial_stiffness",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


def circular_area(diameter: Quantity) -> Quantity:
    """The area A = π·d²/4 of a solid circular section."""
    _require(diameter, "[length]", "diameter")
    return _as_quantity(pi * diameter.pint**2 / 4, "mm**2")


def axial_stress(*, force: Quantity, area: Quantity) -> Quantity:
    """The direct axial stress σ = F/A over a cross-sectional ``area``.

    A positive result is tension and a negative result compression, following the
    sign of ``force``. ``force`` must be a force and ``area`` an area (length²).
    Returns the stress in MPa.
    """
    _require(force, "[force]", "force")
    _require(area, "[length]**2", "area")
    stress = force.pint / area.pint
    return _as_quantity(stress, "MPa")


def required_axial_area(
    *,
    axial_load: Quantity,
    allowable_stress: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least cross-sectional area A a member needs to carry ``axial_load``
    within an allowable direct stress.

    The inverse of the σ = F/A check: demanding F/A ≤ σ_allow/n gives
    A_min = n·F/σ_allow — the sizing step for a tension member (or a short
    compression member not governed by buckling). ``axial_load`` F is the service
    load (magnitude; sign is irrelevant to the area), ``allowable_stress`` σ_allow
    the material's allowable, and ``required_safety_factor`` n the margin on it
    (default 1.0). Returns the minimum area in mm²; the load and stress are
    dimension-checked and ``n`` / ``allowable_stress`` must be positive.
    """
    _require(axial_load, "[force]", "axial_load")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    if allowable_stress.to("MPa").magnitude <= 0:
        raise ValueError(f"allowable_stress must be positive; got {allowable_stress}")
    area = required_safety_factor * abs(axial_load.pint) / allowable_stress.pint
    return _as_quantity(area, "mm**2")


def axial_elongation(
    *, force: Quantity, length: Quantity, area: Quantity, elastic_modulus: Quantity
) -> Quantity:
    """The axial deformation δ = F·L/(A·E) of a uniform member.

    A bar of ``length`` L and cross-sectional ``area`` A stretched (or compressed) by
    an axial ``force`` F changes length by δ = F·L/(A·E) — Hooke's law over the whole
    member, the axial counterpart of a beam's deflection and a shaft's twist. The
    result is SIGNED: a tensile force lengthens, a compressive one shortens, which is
    what a thermal-growth or fit-up clearance check needs. ``force`` is a force, L and
    A are positive geometry, and ``elastic_modulus`` E the material's. Returns the
    elongation in mm.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(area, "[length]**2", "area")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if length.to("mm").magnitude <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if area.to("mm**2").magnitude <= 0:
        raise ValueError(f"area must be positive; got {area}")
    if elastic_modulus.to("MPa").magnitude <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    delta = force.pint * length.pint / (area.pint * elastic_modulus.pint)
    return _as_quantity(delta, "mm")


def axial_stiffness(*, length: Quantity, area: Quantity, elastic_modulus: Quantity) -> Quantity:
    """The axial stiffness k = A·E/L of a uniform member.

    The axial spring rate of a bar — the force it takes to stretch it a unit length,
    k = A·E/L, so its elongation under a load is simply F/k (:func:`axial_elongation`).
    It is the stiffness a bolt or tie-rod contributes to a preloaded joint or a
    parallel load path, and the ``k`` a mass on the end of a rod resonates on. ``area``
    A, ``length`` L, and ``elastic_modulus`` E must be positive. Returns the stiffness
    in newtons per millimetre.
    """
    _require(length, "[length]", "length")
    _require(area, "[length]**2", "area")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if length.to("mm").magnitude <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if area.to("mm**2").magnitude <= 0:
        raise ValueError(f"area must be positive; got {area}")
    if elastic_modulus.to("MPa").magnitude <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    stiffness = area.pint * elastic_modulus.pint / length.pint
    return _as_quantity(stiffness, "N/mm")
