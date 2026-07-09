"""T1 analytical thin-wall pressure-vessel check (closed-form).

A thin-walled cylinder under internal pressure carries a circumferential (hoop)
membrane stress ``σ_hoop = p·r/t`` and a longitudinal stress ``σ_long = p·r/(2·t)``
— the hoop stress is twice the longitudinal, which is why pressurized cylinders
split along their length. These are the Roark / Shigley thin-wall forms, valid
when the radius-to-thickness ratio is large (r/t ≳ 10); below that a thick-wall
(Lamé) treatment is needed. As with the other checks, inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "ThinWallStress",
    "thin_wall_cylinder",
    "thin_wall_sphere_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _as_quantity(pint_value, unit: str) -> Quantity:
    converted = pint_value.to(unit)
    return Quantity(magnitude=float(converted.magnitude), unit=unit)


class ThinWallStress(BaseModel):
    """The membrane stresses in a thin-wall cylinder under internal pressure.

    ``hoop_stress`` is the circumferential stress (the larger of the two, and the
    governing one for a cylinder); ``longitudinal_stress`` is the axial stress,
    half the hoop. ``thin_wall_ratio`` is the radius-to-thickness ratio r/t — the
    thin-wall forms lose accuracy below about 10.
    """

    model_config = ConfigDict(frozen=True)

    hoop_stress: Quantity
    longitudinal_stress: Quantity
    thin_wall_ratio: float

    def bending_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against yielding on the governing (hoop) stress."""
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        return sy / self.hoop_stress.to("MPa").magnitude

    def __str__(self) -> str:
        return (
            f"thin-wall cylinder: hoop {self.hoop_stress.to('MPa')}, "
            f"long {self.longitudinal_stress.to('MPa')} (r/t {self.thin_wall_ratio:.1f})"
        )


def thin_wall_cylinder(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
) -> ThinWallStress:
    """The hoop and longitudinal membrane stresses in a thin-wall cylinder.

    ``pressure`` is the internal gauge pressure, ``radius`` the cylinder's inner
    radius, and ``wall_thickness`` the wall thickness. Returns a
    :class:`ThinWallStress` with σ_hoop = p·r/t, σ_long = p·r/(2·t), and the r/t
    ratio. Every argument is dimension-checked and ``wall_thickness`` must be
    positive.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(wall_thickness, "[length]", "wall_thickness")
    if wall_thickness.to("mm").magnitude <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")

    p = pressure.pint
    r = radius.pint
    t = wall_thickness.pint
    hoop = p * r / t
    longitudinal = p * r / (2 * t)
    ratio = (radius.to("mm").magnitude) / (wall_thickness.to("mm").magnitude)
    return ThinWallStress(
        hoop_stress=_as_quantity(hoop, "MPa"),
        longitudinal_stress=_as_quantity(longitudinal, "MPa"),
        thin_wall_ratio=ratio,
    )


def thin_wall_sphere_stress(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
) -> Quantity:
    """The membrane stress σ = p·r/(2·t) in a thin-wall spherical shell.

    A sphere under internal pressure carries a uniform biaxial membrane stress in
    every direction — half the hoop stress of a cylinder of the same radius and
    wall, which is why spherical vessels are the most material-efficient shape.
    ``pressure`` internal gauge pressure, ``radius`` the inner radius,
    ``wall_thickness`` the wall. Returns the membrane stress in MPa.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(wall_thickness, "[length]", "wall_thickness")
    if wall_thickness.to("mm").magnitude <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    stress = pressure.pint * radius.pint / (2 * wall_thickness.pint)
    return _as_quantity(stress, "MPa")
