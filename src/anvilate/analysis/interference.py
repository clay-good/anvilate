"""T1 analytical interference-fit (press/shrink-fit) check (thick-wall Lamé).

Pressing a shaft into a hub with a diametral interference generates a contact
pressure at the mating surface and a set of thick-wall (Lamé) stresses in both
members: the hub bore sees a tensile hoop stress (it is being stretched over the
shaft) and the shaft surface a compressive one. These are the Shigley forms for
two thick-wall cylinders of the same length, which the thin-wall pressure-vessel
check cannot supply. They tie the ISO 286 interference fits (the r/s/u shaft
letters) to a stress an engineer can screen against yield.

The general two-material result takes the mating (interface) diameter, the hub
outer diameter, an optional shaft bore (0 for a solid shaft), the radial
interference, and each member's elastic modulus and Poisson's ratio. As with the
other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "InterferenceFit",
    "interference_fit",
    "interference_for_contact_pressure",
    "interference_axial_capacity",
    "interference_torque_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class InterferenceFit(BaseModel):
    """The contact pressure and interface hoop stresses of a press/shrink fit.

    ``contact_pressure`` is the pressure at the mating surface. ``hub_hoop_stress``
    is the tangential stress at the hub bore — tensile, and the value that governs
    hub yielding. ``shaft_hoop_stress`` is the tangential stress at the shaft
    surface — compressive (negative), equal to −``contact_pressure`` for a solid
    shaft.
    """

    model_config = ConfigDict(frozen=True)

    contact_pressure: Quantity
    hub_hoop_stress: Quantity
    shaft_hoop_stress: Quantity

    def hub_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against yielding at the hub bore (the tensile
        hoop stress, which governs the hub)."""
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        return sy / self.hub_hoop_stress.to("MPa").magnitude

    def __str__(self) -> str:
        return (
            f"interference fit: contact {self.contact_pressure.to('MPa')}, "
            f"hub hoop {self.hub_hoop_stress.to('MPa')}, "
            f"shaft hoop {self.shaft_hoop_stress.to('MPa')}"
        )


def _fit_geometry(
    *,
    interface_diameter: Quantity,
    hub_outer_diameter: Quantity,
    hub_modulus: Quantity,
    hub_poisson: float,
    shaft_modulus: Quantity,
    shaft_poisson: float,
    shaft_bore_diameter: Quantity | None,
):
    """Validate the fit geometry and return ``(radius, hub_ratio, shaft_ratio,
    compliance)`` — the shared terms of δ = p·R·compliance linking the radial
    interference and the contact pressure (Shigley two-cylinder form)."""
    _require(interface_diameter, "[length]", "interface_diameter")
    _require(hub_outer_diameter, "[length]", "hub_outer_diameter")
    _require(hub_modulus, "[pressure]", "hub_modulus")
    _require(shaft_modulus, "[pressure]", "shaft_modulus")
    if shaft_bore_diameter is not None:
        _require(shaft_bore_diameter, "[length]", "shaft_bore_diameter")

    d = interface_diameter.to("mm").magnitude
    big_d = hub_outer_diameter.to("mm").magnitude
    d_i = 0.0 if shaft_bore_diameter is None else shaft_bore_diameter.to("mm").magnitude
    e_o = hub_modulus.to("MPa").magnitude
    e_i = shaft_modulus.to("MPa").magnitude

    if not (big_d > d > d_i >= 0):
        raise ValueError(
            f"need hub_outer_diameter > interface_diameter > shaft_bore_diameter >= 0; "
            f"got {hub_outer_diameter}, {interface_diameter}, {shaft_bore_diameter}"
        )

    hub_ratio = (big_d**2 + d**2) / (big_d**2 - d**2)  # (D²+d²)/(D²−d²)
    shaft_ratio = (d**2 + d_i**2) / (d**2 - d_i**2)  # (d²+d_i²)/(d²−d_i²)
    radius = d / 2
    compliance = (hub_ratio + hub_poisson) / e_o + (shaft_ratio - shaft_poisson) / e_i
    return radius, hub_ratio, shaft_ratio, compliance


def interference_fit(
    *,
    radial_interference: Quantity,
    interface_diameter: Quantity,
    hub_outer_diameter: Quantity,
    hub_modulus: Quantity,
    hub_poisson: float,
    shaft_modulus: Quantity,
    shaft_poisson: float,
    shaft_bore_diameter: Quantity | None = None,
) -> InterferenceFit:
    """The contact pressure and interface hoop stresses of an interference fit.

    ``radial_interference`` is the radial overlap δ (half the diametral
    interference the ISO 286 fit reports). ``interface_diameter`` d is the mating
    diameter, ``hub_outer_diameter`` D the hub's outer diameter, and
    ``shaft_bore_diameter`` the shaft's bore (``None`` or 0 for a solid shaft).
    Each member carries its own elastic ``modulus`` and ``poisson`` ratio.

    The contact pressure follows Shigley's two-cylinder form (from radial
    deflection compatibility); the hub bore sees a tensile hoop stress
    p·(D²+d²)/(D²−d²) and the shaft surface a compressive −p·(d²+d_i²)/(d²−d_i²).
    Every length/pressure argument is dimension-checked; D must exceed d, which
    must exceed any bore.
    """
    _require(radial_interference, "[length]", "radial_interference")
    radius, hub_ratio, shaft_ratio, compliance = _fit_geometry(
        interface_diameter=interface_diameter,
        hub_outer_diameter=hub_outer_diameter,
        hub_modulus=hub_modulus,
        hub_poisson=hub_poisson,
        shaft_modulus=shaft_modulus,
        shaft_poisson=shaft_poisson,
        shaft_bore_diameter=shaft_bore_diameter,
    )
    delta = radial_interference.to("mm").magnitude
    # δ = p·R·[ (hub_ratio + ν_o)/E_o + (shaft_ratio − ν_i)/E_i ]  ->  solve for p.
    pressure = delta / (radius * compliance)

    return InterferenceFit(
        contact_pressure=Quantity(magnitude=pressure, unit="MPa"),
        hub_hoop_stress=Quantity(magnitude=pressure * hub_ratio, unit="MPa"),
        shaft_hoop_stress=Quantity(magnitude=-pressure * shaft_ratio, unit="MPa"),
    )


def interference_for_contact_pressure(
    *,
    contact_pressure: Quantity,
    interface_diameter: Quantity,
    hub_outer_diameter: Quantity,
    hub_modulus: Quantity,
    hub_poisson: float,
    shaft_modulus: Quantity,
    shaft_poisson: float,
    shaft_bore_diameter: Quantity | None = None,
) -> Quantity:
    """The radial interference δ needed to develop a target ``contact_pressure``.

    The exact inverse of :func:`interference_fit`'s pressure solve:
    δ = p·R·[(D²+d²)/(D²−d²) + ν_o)/E_o + ((d²+d_i²)/(d²−d_i²) − ν_i)/E_i]. Sizing a
    press/shrink fit usually runs this way — a minimum contact pressure is required
    (e.g. for a torque-capacity target) and the interference, and hence the ISO 286
    fit class, must be chosen to reach it. Geometry and material arguments are as
    for :func:`interference_fit`. Returns the radial interference in mm (double it
    for the diametral value a fit table lists); ``contact_pressure`` must be a
    pressure.
    """
    _require(contact_pressure, "[pressure]", "contact_pressure")
    radius, _hub_ratio, _shaft_ratio, compliance = _fit_geometry(
        interface_diameter=interface_diameter,
        hub_outer_diameter=hub_outer_diameter,
        hub_modulus=hub_modulus,
        hub_poisson=hub_poisson,
        shaft_modulus=shaft_modulus,
        shaft_poisson=shaft_poisson,
        shaft_bore_diameter=shaft_bore_diameter,
    )
    p = contact_pressure.to("MPa").magnitude
    delta = p * radius * compliance
    return Quantity(magnitude=delta, unit="mm")


def interference_axial_capacity(
    contact_pressure: Quantity,
    *,
    interface_diameter: Quantity,
    engagement_length: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The axial force a press fit can transmit before the shaft slips out.

    Friction acts over the mating area π·d·L at the ``contact_pressure`` p, so the
    push-out force is F = μ·p·π·d·L. ``contact_pressure`` comes from
    :func:`interference_fit`, ``interface_diameter`` d is the mating diameter, and
    ``engagement_length`` L the axial length in contact. Returns the force in N.
    """
    _require(contact_pressure, "[pressure]", "contact_pressure")
    _require(interface_diameter, "[length]", "interface_diameter")
    _require(engagement_length, "[length]", "engagement_length")
    if friction_coefficient <= 0:
        raise ValueError(f"friction_coefficient must be positive; got {friction_coefficient}")
    force = (
        friction_coefficient
        * contact_pressure.pint
        * (math.pi * interface_diameter.pint * engagement_length.pint)
    )
    return Quantity(magnitude=float(force.to("N").magnitude), unit="N")


def interference_torque_capacity(
    contact_pressure: Quantity,
    *,
    interface_diameter: Quantity,
    engagement_length: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The torque a press fit can transmit before the shaft slips in the hub.

    The friction force μ·p·π·d·L acts at the shaft radius d/2, so the transmissible
    torque is T = μ·p·π·d²·L/2 — the functional limit of a shrink-fit coupling.
    Arguments as for :func:`interference_axial_capacity`. Returns the torque in N·m.
    """
    axial = interference_axial_capacity(
        contact_pressure,
        interface_diameter=interface_diameter,
        engagement_length=engagement_length,
        friction_coefficient=friction_coefficient,
    )
    torque = axial.pint * (interface_diameter.pint / 2)
    return Quantity(magnitude=float(torque.to("N*m").magnitude), unit="N*m")
