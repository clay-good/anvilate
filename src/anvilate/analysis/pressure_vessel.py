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

from math import sqrt

from pydantic import BaseModel, ConfigDict

from ..units import Quantity
from .stress import von_mises_principal

__all__ = [
    "ThinWallStress",
    "ThickWallStress",
    "ThickWallSphereStress",
    "thin_wall_cylinder",
    "thin_wall_cylinder_diametral_growth",
    "thin_wall_thickness_for_pressure",
    "asme_cylinder_thickness",
    "asme_cylinder_mawp",
    "thick_wall_cylinder",
    "thin_wall_sphere_stress",
    "thin_wall_sphere_diametral_growth",
    "thick_wall_sphere",
    "cylinder_external_pressure_buckling",
    "sphere_external_pressure_buckling",
    "cylinder_axial_buckling_stress",
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


def thin_wall_cylinder_diametral_growth(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
    elastic_modulus: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The increase in diameter ΔD = D·(σ_hoop − ν·σ_long)/E of a pressurized thin
    cylinder.

    Internal pressure does not only stress a thin cylinder, it swells it: the biaxial
    membrane stress strains the circumference by ε_θ = (σ_hoop − ν·σ_long)/E, so the
    inner diameter grows by ΔD = D·ε_θ = p·D²·(1 − ν/2)/(2·t·E) (using σ_hoop = p·r/t
    and σ_long = p·r/2t). This is the radial breathing a running clearance must allow —
    a piston in a pressurized bore, a liner in its jacket, a rotor in a pressurized
    casing. ``pressure`` p, ``radius`` r (inner), ``wall_thickness`` t,
    ``elastic_modulus`` E, and Poisson's ratio ``poisson`` ν (0 ≤ ν < 0.5) describe the
    cylinder; the wall must be positive. Returns the diametral growth in mm.
    """
    stress = thin_wall_cylinder(pressure=pressure, radius=radius, wall_thickness=wall_thickness)
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    hoop = stress.hoop_stress.to("MPa").magnitude
    longitudinal = stress.longitudinal_stress.to("MPa").magnitude
    diameter = 2.0 * radius.to("mm").magnitude
    hoop_strain = (hoop - poisson * longitudinal) / e
    return Quantity(magnitude=diameter * hoop_strain, unit="mm")


def thin_wall_thickness_for_pressure(
    *,
    pressure: Quantity,
    radius: Quantity,
    allowable_stress: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least cylinder wall thickness to hold ``pressure`` within an allowable
    hoop stress.

    The inverse of :func:`thin_wall_cylinder`'s governing hoop stress: demanding
    p·r/t ≤ σ_allow/n gives t_min = n·p·r/σ_allow — the membrane wall-sizing form
    (ASME's ``t = p·r/(S·E)`` with the joint efficiency folded into σ_allow).
    ``pressure`` p is the internal gauge pressure, ``radius`` r the inner radius,
    ``allowable_stress`` σ_allow the material's allowable, and
    ``required_safety_factor`` n the margin on it (default 1.0). Returns the
    minimum thickness in mm; the pressure/radius/stress are dimension-checked and
    ``n`` / ``allowable_stress`` must be positive.

    A thin-wall (membrane) size — when the result gives r/t ≲ 10 the wall carries
    a genuine gradient and the exact Lamé form (:func:`thick_wall_cylinder`)
    governs, so re-check a thick result there.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    if allowable_stress.to("MPa").magnitude <= 0:
        raise ValueError(f"allowable_stress must be positive; got {allowable_stress}")
    thickness = required_safety_factor * pressure.pint * radius.pint / allowable_stress.pint
    return _as_quantity(thickness, "mm")


def asme_cylinder_thickness(
    *,
    pressure: Quantity,
    radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 code minimum wall for a cylindrical shell,
    t = P·R/(S·E − 0.6·P).

    The ASME Boiler & Pressure Vessel Code (Section VIII Div 1, UG-27) sizes a
    cylinder's wall on the circumferential (hoop) stress with two refinements over
    the bare membrane form ``P·R/(S·E)``: a weld ``joint_efficiency`` E (1.0 full
    radiography, 0.85 spot, 0.70 none) that derates the allowable, and the −0.6·P
    term that corrects toward the thick-wall stress as the wall grows.
    ``pressure`` P is the internal design pressure, ``radius`` R the inner radius,
    ``allowable_stress`` S the code allowable, and E the joint efficiency in (0, 1].
    Requires S·E > 0.6·P (above that pressure a thin shell cannot be sized — go to a
    thick-wall design). Returns the minimum thickness in mm.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(radius, "[length]", "radius")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    p = pressure.to("MPa").magnitude
    r = radius.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if p <= 0 or r <= 0 or s <= 0:
        raise ValueError("pressure, radius, and allowable_stress must be positive")
    denominator = s * joint_efficiency - 0.6 * p
    if denominator <= 0:
        raise ValueError(
            f"S·E ({s * joint_efficiency:.4g} MPa) must exceed 0.6·P "
            f"({0.6 * p:.4g} MPa); the pressure is too high for a thin-wall design"
        )
    return Quantity(magnitude=p * r / denominator, unit="mm")


def asme_cylinder_mawp(
    *,
    thickness: Quantity,
    radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 maximum allowable working pressure P = S·E·t/(R + 0.6·t).

    The rating inverse of :func:`asme_cylinder_thickness`: the highest internal pressure a
    cylindrical shell of ``thickness`` t and inner ``radius`` R may carry under the code hoop
    rule, P = S·E·t/(R + 0.6·t) for a code ``allowable_stress`` S and weld ``joint_efficiency``
    E. This is the MAWP a vessel is stamped and set its relief valve to — computed from the
    *as-built* wall (less any corrosion allowance), not the design pressure. All positive,
    E in (0, 1]. Returns the MAWP in MPa.
    """
    _require(thickness, "[length]", "thickness")
    _require(radius, "[length]", "radius")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    t = thickness.to("mm").magnitude
    r = radius.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if t <= 0 or r <= 0 or s <= 0:
        raise ValueError("thickness, radius, and allowable_stress must be positive")
    return Quantity(magnitude=s * joint_efficiency * t / (r + 0.6 * t), unit="MPa")


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

    @property
    def bore_von_mises_stress(self) -> Quantity:
        """The von Mises equivalent stress of the bore's hoop/radial/longitudinal
        triad — the less-conservative ductile yield criterion.

        Tresca (``bore_tresca_stress``) ignores the intermediate principal stress;
        von Mises accounts for all three, so for a closed-end cylinder it reads a
        few percent below the Tresca intensity and gives a less conservative but
        still safe screen. Evaluated through
        :func:`~anvilate.analysis.stress.von_mises_principal`.
        """
        return von_mises_principal(
            sigma_1=self.hoop_stress,
            sigma_2=self.radial_stress,
            sigma_3=self.longitudinal_stress,
        )

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
    closed_ends: bool = True,
) -> ThickWallStress:
    """The exact Lamé stresses in a thick-wall cylinder under internal pressure.

    ``pressure`` is the internal gauge pressure, ``radius`` the INNER radius
    r_i, and ``wall_thickness`` the wall (r_o = r_i + t) — the same arguments
    as :func:`thin_wall_cylinder`, so the two screens swap freely. At the
    bore, where everything peaks: σ_hoop = p·(r_o² + r_i²)/(r_o² − r_i²),
    σ_radial = −p, and σ_long = p·r_i²/(r_o² − r_i²) with closed ends (the
    hoop stress falls by exactly p across the wall, landing at 2·σ_long on
    the OD). Set ``closed_ends=False`` for an open-ended cylinder — a pipe with
    free or bellows-jointed ends, or a press-fit sleeve — which carries no axial
    pressure load, so σ_long = 0; the hoop and radial stresses (and the governing
    Tresca intensity) are unchanged, but the von Mises reading rises because the
    intermediate principal stress is gone. Exact at every r/t — as the wall thins
    it recovers the p·r/t membrane forms, and at r/t ≲ 10 it is the honest one: the
    thin-wall screen under-reports the bore. Every quantity argument is
    dimension-checked and must be positive.
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
    longitudinal = p * ri**2 / denom if closed_ends else 0.0
    return ThickWallStress(
        hoop_stress=Quantity(magnitude=p * (ro**2 + ri**2) / denom, unit="MPa"),
        radial_stress=Quantity(magnitude=-p, unit="MPa"),
        longitudinal_stress=Quantity(magnitude=longitudinal, unit="MPa"),
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


def thin_wall_sphere_diametral_growth(
    *,
    pressure: Quantity,
    radius: Quantity,
    wall_thickness: Quantity,
    elastic_modulus: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The increase in diameter ΔD = D·σ·(1 − ν)/E of a pressurized thin sphere.

    The spherical counterpart of :func:`thin_wall_cylinder_diametral_growth`: a
    sphere's equibiaxial membrane stress σ = p·r/(2·t) strains its surface by
    ε = σ·(1 − ν)/E in every direction, so the diameter grows by ΔD = D·ε =
    p·D²·(1 − ν)/(4·t·E). Because the sphere's stress is half a cylinder's and its
    strain carries (1 − ν) rather than (1 − ν/2), a pressurized sphere breathes
    appreciably less than a cylinder of the same size — the deformation a clearance or
    a shrink-fitted band around it must allow. ``pressure`` p, ``radius`` r (inner),
    ``wall_thickness`` t, ``elastic_modulus`` E, and Poisson's ratio ``poisson`` ν
    (0 ≤ ν < 0.5) describe the sphere; the wall must be positive. Returns the diametral
    growth in mm.
    """
    stress = thin_wall_sphere_stress(
        pressure=pressure, radius=radius, wall_thickness=wall_thickness
    )
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    sigma = stress.to("MPa").magnitude
    diameter = 2.0 * radius.to("mm").magnitude
    return Quantity(magnitude=diameter * sigma * (1.0 - poisson) / e, unit="mm")


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


def cylinder_external_pressure_buckling(
    *,
    elastic_modulus: Quantity,
    wall_thickness: Quantity,
    mean_radius: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The collapse pressure of a long thin cylinder under external pressure.

    Under *external* pressure a thin tube does not yield — it buckles, snapping into
    an oval (the n = 2 lobe) at a pressure far below its internal-pressure strength.
    This is the failure that implodes a vacuum vessel or a submarine hull. For a long
    cylinder the critical pressure is

        p_cr = E·t³ / (4·r³·(1 − ν²)) = (2·E / (1 − ν²))·(t/D)³,

    riding on the *cube* of the thin (t/r) ratio, so a tube stout enough against
    internal pressure can still be dangerously weak against external pressure.
    ``elastic_modulus`` E, ``wall_thickness`` t, ``mean_radius`` r (of the wall
    mid-thickness), and Poisson's ratio ``poisson`` ν describe the shell; the wall
    must be positive and 0 ≤ ν < 0.5. This is the classic (Timoshenko) long-cylinder
    result — short cylinders with stiffening rings or closed ends hold more. Returns
    the critical external pressure in MPa.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(mean_radius, "[length]", "mean_radius")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    t = wall_thickness.to("mm").magnitude
    r = mean_radius.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    p_cr = e * t**3 / (4.0 * r**3 * (1.0 - poisson**2))
    return Quantity(magnitude=p_cr, unit="MPa")


def sphere_external_pressure_buckling(
    *,
    elastic_modulus: Quantity,
    wall_thickness: Quantity,
    mean_radius: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The buckling collapse pressure of a thin spherical shell under external pressure.

    A complete thin sphere under uniform external pressure buckles inward at the
    classical (Zoelly) pressure

        p_cr = 2·E·(t/R)² / √(3·(1 − ν²)),

    which — unlike the cylinder — rides on the *square* of the thin ratio, so a
    sphere holds far more external pressure than a cylinder of the same t/R. That is
    why deep-submergence hulls and vacuum spheres are spherical. ``elastic_modulus``
    E, ``wall_thickness`` t, ``mean_radius`` R, and Poisson's ratio ``poisson`` ν
    describe the shell; the wall must be positive and 0 ≤ ν < 0.5. This is the ideal
    (perfect-sphere) buckling pressure — real shells with dimples knock down well
    below it, so apply a generous factor. Returns the critical external pressure in MPa.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(mean_radius, "[length]", "mean_radius")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    t = wall_thickness.to("mm").magnitude
    r = mean_radius.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    p_cr = 2.0 * e * (t / r) ** 2 / sqrt(3.0 * (1.0 - poisson**2))
    return Quantity(magnitude=p_cr, unit="MPa")


def cylinder_axial_buckling_stress(
    *,
    elastic_modulus: Quantity,
    wall_thickness: Quantity,
    mean_radius: Quantity,
    poisson: float = 0.3,
) -> Quantity:
    """The classical axial-compression buckling stress of a thin cylindrical shell.

    A thin tube squeezed *along its axis* — a rocket stage, a silo wall, a strut of
    tubing — does not simply yield or Euler-buckle as a column; its wall crinkles into
    a diamond pattern at the classical (Lorenz-Timoshenko) critical stress

        σ_cr = E·(t/R) / √(3·(1 − ν²)),

    which rises with the thin ratio t/R (not its cube, as external-pressure collapse
    does). ``elastic_modulus`` E, ``wall_thickness`` t, ``mean_radius`` R, and
    Poisson's ratio ``poisson`` ν describe the shell; the wall must be positive and
    0 ≤ ν < 0.5. This ideal value is famously unconservative — real cylinders, acutely
    sensitive to tiny dimples, buckle at only ~15–60% of it, so design codes apply a
    steep knockdown factor. Returns the critical axial stress in MPa.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(mean_radius, "[length]", "mean_radius")
    if not 0 <= poisson < 0.5:
        raise ValueError(f"poisson must lie in [0, 0.5); got {poisson}")
    e = elastic_modulus.to("MPa").magnitude
    t = wall_thickness.to("mm").magnitude
    r = mean_radius.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"wall_thickness must be positive; got {wall_thickness}")
    if r <= 0:
        raise ValueError(f"mean_radius must be positive; got {mean_radius}")
    sigma_cr = e * (t / r) / sqrt(3.0 * (1.0 - poisson**2))
    return Quantity(magnitude=sigma_cr, unit="MPa")
