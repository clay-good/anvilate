"""T1 analytical Hertzian contact check (elastic point contact).

Two curved elastic bodies pressed together touch over a small area and develop a
very high local contact pressure — the mechanism behind ball-bearing, cam, and
spherical-seat failures. For point (sphere-on-sphere or sphere-on-flat) contact,
Hertz theory gives a circular contact patch of radius ``a`` and a peak pressure
``p_max`` at its centre:

    a = ((3·F·R) / (4·E*))**(1/3),   p_max = 3·F / (2·π·a²)

where 1/E* = (1−ν₁²)/E₁ + (1−ν₂²)/E₂ is the effective modulus and 1/R = 1/R₁ + 1/R₂
the effective radius (a flat body has infinite radius, so it drops out). These are
the Shigley / Roark forms. As with the other checks, inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "HertzContact",
    "hertz_sphere_contact",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


class HertzContact(BaseModel):
    """A Hertzian point contact: the patch radius and the peak contact pressure.

    ``contact_radius`` is the radius of the circular contact patch; the peak
    pressure ``max_contact_pressure`` acts at its centre and is 1.5× the mean
    pressure over the patch. The peak pressure is what governs surface yielding and
    rolling-contact fatigue.
    """

    model_config = ConfigDict(frozen=True)

    contact_radius: Quantity
    max_contact_pressure: Quantity

    def surface_safety_factor(self, yield_strength: Quantity) -> float:
        """A screening factor of safety, yield / peak contact pressure.

        A rough surface-yield screen only: the true onset of yield in contact is
        governed by the subsurface shear stress (about 0.31·p_max at depth), so a
        contact fit that clears this simple ratio still warrants a fuller check.
        """
        _require(yield_strength, "[pressure]", "yield_strength")
        return yield_strength.to("MPa").magnitude / self.max_contact_pressure.to("MPa").magnitude


def hertz_sphere_contact(
    *,
    force: Quantity,
    diameter1: Quantity,
    modulus1: Quantity,
    poisson1: float,
    modulus2: Quantity,
    poisson2: float,
    diameter2: Quantity | None = None,
) -> HertzContact:
    """The contact patch radius and peak pressure of a Hertzian point contact.

    ``force`` is the load pressing the bodies together; ``diameter1`` and each
    body's elastic ``modulus`` and ``poisson`` ratio describe the spheres.
    ``diameter2`` is the second sphere's diameter, or ``None`` for a sphere on a
    flat (infinite radius). For convex external contact both diameters are
    positive. Returns a :class:`HertzContact`. Every length/force/pressure argument
    is dimension-checked and diameters must be positive.
    """
    _require(force, "[force]", "force")
    _require(diameter1, "[length]", "diameter1")
    _require(modulus1, "[pressure]", "modulus1")
    _require(modulus2, "[pressure]", "modulus2")

    d1 = diameter1.to("mm").magnitude
    if d1 <= 0:
        raise ValueError(f"diameter1 must be positive; got {diameter1}")
    r1 = d1 / 2
    if diameter2 is None:
        inv_r = 1.0 / r1  # sphere on a flat: 1/R2 -> 0
    else:
        _require(diameter2, "[length]", "diameter2")
        d2 = diameter2.to("mm").magnitude
        if d2 <= 0:
            raise ValueError(f"diameter2 must be positive; got {diameter2}")
        inv_r = 1.0 / r1 + 1.0 / (d2 / 2)
    effective_radius = 1.0 / inv_r  # R in mm

    e1 = modulus1.to("MPa").magnitude
    e2 = modulus2.to("MPa").magnitude
    inv_e_star = (1.0 - poisson1**2) / e1 + (1.0 - poisson2**2) / e2
    e_star = 1.0 / inv_e_star  # MPa

    f = force.to("N").magnitude
    a = (3.0 * f * effective_radius / (4.0 * e_star)) ** (1.0 / 3.0)  # mm
    p_max = 3.0 * f / (2.0 * math.pi * a**2)  # N/mm^2 = MPa
    return HertzContact(
        contact_radius=Quantity(magnitude=a, unit="mm"),
        max_contact_pressure=Quantity(magnitude=p_max, unit="MPa"),
    )
