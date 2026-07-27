"""T1 analytical adhesive-bond checks (closed-form).

Bonded joints carry load in shear over the glued area, and the T1 screens are the
same ones every adhesive datasheet is written against. A single-lap joint of overlap
``L`` and width ``w`` under a force ``F`` carries an average shear stress

    τ = F / (L · w),

the number compared to the adhesive's tabulated lap-shear strength — which is itself
measured on standard lap coupons the same way, so the average-stress comparison is
consistent even though the true distribution peaks at the overlap ends (long overlaps
therefore stop adding strength proportionally; the allowable, not this formula, is
where that physics lives).

The other workhorse is the cylindrical bond: a retaining compound (anaerobic
adhesive) filling the annulus between a shaft and a bore of diameter ``d`` over an
engagement ``L``. The bond shears over the mating area π·d·L, so it holds an axial
force F = τ·π·d·L and, acting at the radius d/2, a torque

    T = τ · π · d² · L / 2

— the bonded analogue of a press fit's friction capacity μ·p·π·d²·L/2, with the
adhesive's full shear strength in place of the friction stress μ·p. That substitution
is why a slip fit plus retaining compound often out-holds a heavy press fit.

All three forms are exact geometry; the bond ``shear strength`` is the caller's
datasheet value (typically 10–30 MPa cured for a retaining compound, derated per the
datasheet for gap, temperature, and surface). Inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "lap_joint_average_shear_stress",
    "cylindrical_bond_axial_capacity",
    "cylindrical_bond_torque_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_mm(value: Quantity, name: str) -> float:
    _require(value, "[length]", name)
    magnitude = value.to("mm").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def _positive_mpa(value: Quantity, name: str) -> float:
    _require(value, "[pressure]", name)
    magnitude = value.to("MPa").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def lap_joint_average_shear_stress(
    *,
    load: Quantity,
    overlap_length: Quantity,
    joint_width: Quantity,
) -> Quantity:
    """The average shear stress τ = F/(L·w) in a bonded lap joint.

    A ``load`` F sheared over the glued overlap ``overlap_length`` L times
    ``joint_width`` w — the screen compared against the adhesive's tabulated
    lap-shear strength, which is measured on standard lap coupons the same way. The
    true stress peaks at the overlap ends, so widening the joint helps more than
    lengthening an already-long overlap. All inputs must be positive. Returns the
    average shear stress in MPa.
    """
    _require(load, "[force]", "load")
    force = load.to("N").magnitude
    if force <= 0:
        raise ValueError(f"load must be positive; got {load}")
    overlap = _positive_mm(overlap_length, "overlap_length")
    width = _positive_mm(joint_width, "joint_width")
    return Quantity(magnitude=force / (overlap * width), unit="MPa")


def cylindrical_bond_axial_capacity(
    *,
    interface_diameter: Quantity,
    engagement_length: Quantity,
    bond_shear_strength: Quantity,
) -> Quantity:
    """The axial force F = τ·π·d·L a cylindrical adhesive bond holds.

    A retaining compound cured in the annulus between a shaft and bore of
    ``interface_diameter`` d over ``engagement_length`` L shears over the mating
    area π·d·L at the ``bond_shear_strength`` τ — the caller's datasheet value,
    derated per the datasheet for gap, temperature, and surface condition. This is
    the push-out capacity of a bonded bushing, liner, or bearing seat. Returns the
    force in N.
    """
    d = _positive_mm(interface_diameter, "interface_diameter")
    length = _positive_mm(engagement_length, "engagement_length")
    tau = _positive_mpa(bond_shear_strength, "bond_shear_strength")
    return Quantity(magnitude=tau * pi * d * length, unit="N")


def cylindrical_bond_torque_capacity(
    *,
    interface_diameter: Quantity,
    engagement_length: Quantity,
    bond_shear_strength: Quantity,
) -> Quantity:
    """The torque T = τ·π·d²·L/2 a cylindrical adhesive bond transmits.

    The bond's shear capacity over the mating area, acting at the interface radius
    d/2 — the bonded analogue of a press fit's friction torque μ·p·π·d²·L/2, with
    the adhesive's shear strength standing in for the friction stress. Arguments as
    for :func:`cylindrical_bond_axial_capacity`. Returns the torque in N·m.
    """
    axial_n = cylindrical_bond_axial_capacity(
        interface_diameter=interface_diameter,
        engagement_length=engagement_length,
        bond_shear_strength=bond_shear_strength,
    ).to("N")
    radius_m = interface_diameter.to("m").magnitude / 2
    return Quantity(magnitude=axial_n.magnitude * radius_m, unit="N*m")
