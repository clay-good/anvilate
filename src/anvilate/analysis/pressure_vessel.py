"""T1 analytical pressure-vessel checks (closed-form).

A thin-walled cylinder under internal pressure carries a circumferential (hoop)
membrane stress ``σ_hoop = p·r/t`` and a longitudinal stress ``σ_long = p·r/(2·t)``
— the hoop stress is twice the longitudinal, which is why pressurized cylinders
split along their length. These are the Roark / Shigley thin-wall forms, valid
when the radius-to-thickness ratio is large (r/t ≳ 10). Below that the wall
carries a genuine stress gradient and the exact Lamé thick-wall solution takes
over: the bore hoop stress ``p·(ro² + ri²)/(ro² − ri²)`` rides on a radial
compression ``−p``, so the governing Tresca intensity at the bore is
``2·p·ro²/(ro² − ri²)`` — always worse than what the thin-wall form reports. The
same thin/thick split holds for a sphere: the membrane form ``p·r/(2·t)`` gives
way to the exact Lamé bore Tresca ``3·p·ro³/(2·(ro³ − ri³))``. As with the other
checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values through Pint.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thick_wall_sphere",
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


class ThickWallStress(BaseModel):
    """The exact Lamé stresses at the bore of a thick-wall cylinder.

    ``hoop_stress`` is the circumferential stress at the bore (the peak in the
    wall), ``radial_stress`` the radial stress there (exactly −p),
    ``longitudinal_stress`` the closed-ends axial stress, and
    ``bore_tresca_stress`` the governing stress intensity σ_hoop − σ_radial
    that a yield screen should use — the bore sees tension and compression at
    right angles, so it works harder than the hoop number alone says.
    """

    model_config = ConfigDict(frozen=True)

    hoop_stress: Quantity
    radial_stress: Quantity
    longitudinal_stress: Quantity

    @property
    def bore_tresca_stress(self) -> Quantity:
        """The Tresca stress intensity σ_hoop − σ_radial at the bore."""
        hoop = self.hoop_stress.to("MPa").magnitude
        radial = self.radial_stress.to("MPa").magnitude
        return Quantity(magnitude=hoop - radial, unit="MPa")

    def yield_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against bore yielding on the Tresca intensity."""
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        return sy / self.bore_tresca_stress.to("MPa").magnitude

    def __str__(self) -> str:
        return (
            f"thick-wall cylinder: bore hoop {self.hoop_stress.to('MPa')}, "
            f"radial {self.radial_stress.to('MPa')}, "
            f"tresca {self.bore_tresca_stress.to('MPa')}"
        )


def thick_wall_cylinder(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
) -> ThickWallStress:
    """The exact Lamé stresses in a thick-wall cylinder under internal pressure.

    ``pressure`` is the internal gauge pressure, ``radius`` the INNER radius
    r_i, and ``wall_thickness`` the wall (r_o = r_i + t) — the same arguments
    as :func:`thin_wall_cylinder`, so the two screens swap freely. At the
    bore, where everything peaks: σ_hoop = p·(r_o² + r_i²)/(r_o² − r_i²),
    σ_radial = −p, and σ_long = p·r_i²/(r_o² − r_i²) with closed ends (the
    hoop stress falls by exactly p across the wall, landing at 2·σ_long on
    the OD). Exact at every r/t — as the wall thins it recovers the p·r/t
    membrane forms, and at r/t ≲ 10 it is the honest one: the thin-wall
    screen under-reports the bore. Every argument is dimension-checked and
    must be positive.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(wall_thickness, "[length]", "wall_thickness")
    p = pressure.to("MPa").magnitude
    ri = radius.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    if p <= 0 or ri <= 0 or t <= 0:
        raise ValueError("pressure, radius, and wall_thickness must be positive")
    ro = ri + t
    denom = ro**2 - ri**2
    return ThickWallStress(
        hoop_stress=Quantity(magnitude=p * (ro**2 + ri**2) / denom, unit="MPa"),
        radial_stress=Quantity(magnitude=-p, unit="MPa"),
        longitudinal_stress=Quantity(magnitude=p * ri**2 / denom, unit="MPa"),
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


class ThickWallSphereStress(BaseModel):
    """The exact Lamé stresses at the bore of a thick-wall sphere.

    ``hoop_stress`` is the tangential stress at the bore — equal in every
    direction on the surface, since a sphere is spherically symmetric, and the
    peak in the wall — and ``radial_stress`` the radial stress there (exactly −p).
    ``bore_tresca_stress`` is the governing σ_hoop − σ_radial intensity a yield
    screen should use.
    """

    model_config = ConfigDict(frozen=True)

    hoop_stress: Quantity
    radial_stress: Quantity

    @property
    def bore_tresca_stress(self) -> Quantity:
        """The Tresca stress intensity σ_hoop − σ_radial at the bore."""
        hoop = self.hoop_stress.to("MPa").magnitude
        radial = self.radial_stress.to("MPa").magnitude
        return Quantity(magnitude=hoop - radial, unit="MPa")

    def yield_safety_factor(self, yield_strength: Quantity) -> float:
        """The factor of safety against bore yielding on the Tresca intensity."""
        _require(yield_strength, "[pressure]", "yield_strength")
        sy = yield_strength.to("MPa").magnitude
        return sy / self.bore_tresca_stress.to("MPa").magnitude

    def __str__(self) -> str:
        return (
            f"thick-wall sphere: bore hoop {self.hoop_stress.to('MPa')}, "
            f"radial {self.radial_stress.to('MPa')}, "
            f"tresca {self.bore_tresca_stress.to('MPa')}"
        )


def thick_wall_sphere(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
) -> ThickWallSphereStress:
    """The exact Lamé stresses in a thick-wall sphere under internal pressure.

    Same arguments as :func:`thin_wall_sphere_stress` — ``pressure`` the internal
    gauge pressure, ``radius`` the INNER radius r_i, ``wall_thickness`` the wall
    (r_o = r_i + t) — so the membrane and exact screens swap freely. At the bore,
    where everything peaks: σ_hoop = p·(2·r_i³ + r_o³)/(2·(r_o³ − r_i³)) in every
    tangential direction, riding on σ_radial = −p, so the governing Tresca
    intensity is 3·p·r_o³/(2·(r_o³ − r_i³)). Exact at every r/t — it recovers the
    p·r/(2·t) membrane form as the wall thins and, like the cylinder, always
    exceeds it at the bore. Every argument is dimension-checked and must be
    positive.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(wall_thickness, "[length]", "wall_thickness")
    p = pressure.to("MPa").magnitude
    ri = radius.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    if p <= 0 or ri <= 0 or t <= 0:
        raise ValueError("pressure, radius, and wall_thickness must be positive")
    ro = ri + t
    denom = ro**3 - ri**3
    return ThickWallSphereStress(
        hoop_stress=Quantity(magnitude=p * (2 * ri**3 + ro**3) / (2 * denom), unit="MPa"),
        radial_stress=Quantity(magnitude=-p, unit="MPa"),
    )
