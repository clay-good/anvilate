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

from math import cos, radians, sin, sqrt

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
    "asme_ellipsoidal_head_thickness",
    "asme_torispherical_head_thickness",
    "asme_ellipsoidal_head_mawp",
    "asme_torispherical_head_mawp",
    "asme_spherical_shell_thickness",
    "asme_spherical_shell_mawp",
    "asme_conical_head_thickness",
    "asme_conical_head_mawp",
    "asme_b313_pipe_wall_thickness",
    "asme_b313_pipe_pressure",
    "asme_b313_minimum_ordered_wall",
    "asme_b313_branch_required_reinforcement_area",
    "asme_b313_allowable_displacement_stress_range",
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


def asme_ellipsoidal_head_thickness(
    *,
    pressure: Quantity,
    diameter: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 UG-32(d) wall for a 2:1 ellipsoidal head, t = P·D/(2·S·E − 0.2·P).

    A 2:1 semi-ellipsoidal head — the common dished vessel end whose depth is a
    quarter of its diameter — is sized by ``pressure`` P (internal design pressure),
    ``diameter`` D (the inside diameter), ``allowable_stress`` S (the code allowable),
    and weld ``joint_efficiency`` E. It comes out close to the shell wall because the
    2:1 shape carries pressure almost as efficiently as the cylinder. Requires
    2·S·E > 0.2·P. Returns the minimum head thickness in mm.
    """
    return _asme_head_thickness(
        coefficient=1.0,
        denom_factor=0.2,
        denom_leading=2.0,
        pressure=pressure,
        length=diameter,
        allowable_stress=allowable_stress,
        joint_efficiency=joint_efficiency,
    )


def asme_torispherical_head_thickness(
    *,
    pressure: Quantity,
    crown_radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 UG-32(e) wall for a standard torispherical head,
    t = 0.885·P·L/(S·E − 0.1·P).

    A standard (ASME flanged-and-dished) torispherical head — a shallow spherical
    crown of radius L blended to the cylinder by a small knuckle — is sized by
    ``pressure`` P, the ``crown_radius`` L (equal to the outside diameter for the
    standard head), ``allowable_stress`` S, and weld ``joint_efficiency`` E. The 0.885
    coefficient captures the knuckle's stress concentration, so a torispherical head
    is thicker than an ellipsoidal one for the same pressure — the price of the
    shallower, cheaper-to-form shape. Requires S·E > 0.1·P. Returns the thickness in
    mm.
    """
    return _asme_head_thickness(
        coefficient=0.885,
        denom_factor=0.1,
        denom_leading=1.0,
        pressure=pressure,
        length=crown_radius,
        allowable_stress=allowable_stress,
        joint_efficiency=joint_efficiency,
    )


def _asme_head_thickness(
    *,
    coefficient: float,
    denom_factor: float,
    denom_leading: float,
    pressure: Quantity,
    length: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float,
) -> Quantity:
    """Shared UG-32 head form t = K·P·L/(m·S·E − f·P)."""
    _require(pressure, "[pressure]", "pressure")
    _require(length, "[length]", "length")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    p = pressure.to("MPa").magnitude
    length_mm = length.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if p <= 0 or length_mm <= 0 or s <= 0:
        raise ValueError("pressure, the geometry, and allowable_stress must be positive")
    denominator = denom_leading * s * joint_efficiency - denom_factor * p
    if denominator <= 0:
        raise ValueError("S·E is too low for the pressure (the head denominator is non-positive)")
    return Quantity(magnitude=coefficient * p * length_mm / denominator, unit="mm")


def asme_ellipsoidal_head_mawp(
    *,
    thickness: Quantity,
    diameter: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 MAWP of a 2:1 ellipsoidal head, P = 2·S·E·t/(D + 0.2·t).

    The rating inverse of :func:`asme_ellipsoidal_head_thickness`: the maximum
    allowable working pressure a 2:1 head of ``thickness`` t and inside ``diameter``
    D carries at code ``allowable_stress`` S and weld ``joint_efficiency`` E. Use the
    as-built wall (less corrosion allowance) to get the head's pressure rating. All
    positive, E in (0, 1]. Returns the MAWP in MPa.
    """
    return _asme_head_mawp(
        denom_factor=0.2,
        numer_leading=2.0,
        thickness=thickness,
        length=diameter,
        allowable_stress=allowable_stress,
        joint_efficiency=joint_efficiency,
    )


def asme_torispherical_head_mawp(
    *,
    thickness: Quantity,
    crown_radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 MAWP of a standard torispherical head,
    P = S·E·t/(0.885·L + 0.1·t).

    The rating inverse of :func:`asme_torispherical_head_thickness`: the maximum
    allowable working pressure a standard flanged-and-dished head of ``thickness`` t
    and ``crown_radius`` L carries at ``allowable_stress`` S and ``joint_efficiency``
    E. The 0.885 knuckle coefficient makes its rating lower than an ellipsoidal head
    of the same wall. All positive, E in (0, 1]. Returns the MAWP in MPa.
    """
    return _asme_head_mawp(
        denom_factor=0.1,
        numer_leading=1.0,
        thickness=thickness,
        length=crown_radius,
        allowable_stress=allowable_stress,
        joint_efficiency=joint_efficiency,
        length_coefficient=0.885,
    )


def _asme_head_mawp(
    *,
    denom_factor: float,
    numer_leading: float,
    thickness: Quantity,
    length: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float,
    length_coefficient: float = 1.0,
) -> Quantity:
    """Shared UG-32 head rating P = m·S·E·t/(K·L + f·t)."""
    _require(thickness, "[length]", "thickness")
    _require(length, "[length]", "length")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    t = thickness.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if t <= 0 or length_mm <= 0 or s <= 0:
        raise ValueError("thickness, the geometry, and allowable_stress must be positive")
    numerator = numer_leading * s * joint_efficiency * t
    denominator = length_coefficient * length_mm + denom_factor * t
    return Quantity(magnitude=numerator / denominator, unit="MPa")


def asme_spherical_shell_thickness(
    *,
    pressure: Quantity,
    radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 UG-27(d) wall for a sphere or hemispherical head,
    t = P·R/(2·S·E − 0.2·P).

    A sphere carries pressure in two membrane directions at once, so it needs only
    about half the wall of a cylinder of the same radius — which is why a
    hemispherical head is the thinnest (and, formed, the most expensive) vessel end.
    ``pressure`` P is the internal design pressure, ``radius`` R the inside radius,
    ``allowable_stress`` S the code allowable, and ``joint_efficiency`` E the weld
    efficiency. Requires 2·S·E > 0.2·P. Returns the minimum thickness in mm.
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
    denominator = 2.0 * s * joint_efficiency - 0.2 * p
    if denominator <= 0:
        raise ValueError(
            f"2·S·E ({2 * s * joint_efficiency:.4g} MPa) must exceed 0.2·P "
            f"({0.2 * p:.4g} MPa); the pressure is too high for a thin-wall sphere"
        )
    return Quantity(magnitude=p * r / denominator, unit="mm")


def asme_spherical_shell_mawp(
    *,
    thickness: Quantity,
    radius: Quantity,
    allowable_stress: Quantity,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 MAWP of a sphere or hemispherical head,
    P = 2·S·E·t/(R + 0.2·t).

    The rating inverse of :func:`asme_spherical_shell_thickness`: the maximum
    allowable working pressure a sphere of ``thickness`` t and inside ``radius`` R
    carries at code ``allowable_stress`` S and weld ``joint_efficiency`` E. All
    positive, E in (0, 1]. Returns the MAWP in MPa.
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
    return Quantity(magnitude=2.0 * s * joint_efficiency * t / (r + 0.2 * t), unit="MPa")


def asme_conical_head_thickness(
    *,
    pressure: Quantity,
    diameter: Quantity,
    allowable_stress: Quantity,
    half_apex_angle_deg: float,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 UG-32(g) wall for a conical head or reducer,
    t = P·D/(2·cos α·(S·E − 0.6·P)).

    A cone (a reducer between two shell diameters, or a conical end) carries the same
    hoop mechanics as a cylinder but on a slant, so its wall is the cylinder form
    divided by cos α — steeper cones need more wall. ``pressure`` P is the internal
    design pressure, ``diameter`` D the inside diameter at the point checked (largest
    at the base), ``allowable_stress`` S the code allowable, ``half_apex_angle_deg``
    α the cone's half-apex angle (0 is a cylinder; the code limits a plain cone to
    α ≤ 30°, above which a knuckle or toriconical transition is required), and
    ``joint_efficiency`` E the weld efficiency. Requires S·E > 0.6·P. Returns the
    minimum thickness in mm.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(diameter, "[length]", "diameter")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 <= half_apex_angle_deg < 90:
        raise ValueError(f"half_apex_angle_deg must lie in [0, 90); got {half_apex_angle_deg}")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    p = pressure.to("MPa").magnitude
    d = diameter.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if p <= 0 or d <= 0 or s <= 0:
        raise ValueError("pressure, diameter, and allowable_stress must be positive")
    denominator = s * joint_efficiency - 0.6 * p
    if denominator <= 0:
        raise ValueError(
            f"S·E ({s * joint_efficiency:.4g} MPa) must exceed 0.6·P ({0.6 * p:.4g} MPa)"
        )
    return Quantity(
        magnitude=p * d / (2.0 * cos(radians(half_apex_angle_deg)) * denominator), unit="mm"
    )


def asme_conical_head_mawp(
    *,
    thickness: Quantity,
    diameter: Quantity,
    allowable_stress: Quantity,
    half_apex_angle_deg: float,
    joint_efficiency: float = 1.0,
) -> Quantity:
    """The ASME VIII-1 MAWP of a conical head or reducer,
    P = 2·cos α·S·E·t/(D + 1.2·cos α·t).

    The rating inverse of :func:`asme_conical_head_thickness`: the maximum allowable
    working pressure a cone of ``thickness`` t and inside ``diameter`` D (at the point
    checked) carries at code ``allowable_stress`` S, ``half_apex_angle_deg`` α, and
    weld ``joint_efficiency`` E. All positive, α in [0, 90), E in (0, 1]. Returns the
    MAWP in MPa.
    """
    _require(thickness, "[length]", "thickness")
    _require(diameter, "[length]", "diameter")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 <= half_apex_angle_deg < 90:
        raise ValueError(f"half_apex_angle_deg must lie in [0, 90); got {half_apex_angle_deg}")
    if not 0 < joint_efficiency <= 1:
        raise ValueError(f"joint_efficiency must lie in (0, 1]; got {joint_efficiency}")
    t = thickness.to("mm").magnitude
    d = diameter.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if t <= 0 or d <= 0 or s <= 0:
        raise ValueError("thickness, diameter, and allowable_stress must be positive")
    cos_alpha = cos(radians(half_apex_angle_deg))
    numerator = 2.0 * cos_alpha * s * joint_efficiency * t
    return Quantity(magnitude=numerator / (d + 1.2 * cos_alpha * t), unit="MPa")


def asme_b313_pipe_wall_thickness(
    *,
    pressure: Quantity,
    outside_diameter: Quantity,
    allowable_stress: Quantity,
    quality_factor: float = 1.0,
    coefficient_y: float = 0.4,
) -> Quantity:
    """The ASME B31.3 pressure-design wall for straight pipe, t = P·D/(2·(S·E + P·Y)).

    The process-piping code (ASME B31.3 §304.1.2) sizes straight pipe on the outside
    diameter: ``pressure`` P is the internal design pressure, ``outside_diameter`` D
    the pipe OD, ``allowable_stress`` S the code allowable at temperature (user-
    supplied from Table A-1), ``quality_factor`` E the product of the weld-joint and
    casting quality factors (E, from Tables A-1A/A-1B), and ``coefficient_y`` Y the
    material/temperature coefficient (0.4 for ferritic and austenitic steels below
    the code's temperature threshold; §304.1.1 Table 304.1.1). This is the
    *pressure-design* thickness only — the mechanical allowances (mill tolerance,
    typically 12.5%, and corrosion) are added on top separately. Valid for
    t < D/6; above that the code's thick-wall form applies. All inputs positive,
    E in (0, 1]. Returns the thickness in mm.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(outside_diameter, "[length]", "outside_diameter")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < quality_factor <= 1:
        raise ValueError(f"quality_factor must lie in (0, 1]; got {quality_factor}")
    p = pressure.to("MPa").magnitude
    d = outside_diameter.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if p <= 0 or d <= 0 or s <= 0:
        raise ValueError("pressure, outside_diameter, and allowable_stress must be positive")
    return Quantity(magnitude=p * d / (2.0 * (s * quality_factor + p * coefficient_y)), unit="mm")


def asme_b313_pipe_pressure(
    *,
    wall_thickness: Quantity,
    outside_diameter: Quantity,
    allowable_stress: Quantity,
    quality_factor: float = 1.0,
    coefficient_y: float = 0.4,
) -> Quantity:
    """The ASME B31.3 pressure a straight pipe wall carries, P = 2·t·S·E/(D − 2·Y·t).

    The rating inverse of :func:`asme_b313_pipe_wall_thickness`: the internal pressure
    a straight pipe of pressure-design wall ``wall_thickness`` t and
    ``outside_diameter`` D may carry under the code allowable ``allowable_stress`` S,
    quality factor ``quality_factor`` E, and coefficient ``coefficient_y`` Y. Use the
    *available* pressure-design wall (the as-built wall less the mill tolerance and
    corrosion allowance) to get the pressure rating. Requires D > 2·Y·t. All positive,
    E in (0, 1]. Returns the pressure in MPa.
    """
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(outside_diameter, "[length]", "outside_diameter")
    _require(allowable_stress, "[pressure]", "allowable_stress")
    if not 0 < quality_factor <= 1:
        raise ValueError(f"quality_factor must lie in (0, 1]; got {quality_factor}")
    t = wall_thickness.to("mm").magnitude
    d = outside_diameter.to("mm").magnitude
    s = allowable_stress.to("MPa").magnitude
    if t <= 0 or d <= 0 or s <= 0:
        raise ValueError("wall_thickness, outside_diameter, and allowable_stress must be positive")
    denominator = d - 2.0 * coefficient_y * t
    if denominator <= 0:
        raise ValueError(
            f"outside_diameter ({d:.4g} mm) must exceed 2·Y·t ({2.0 * coefficient_y * t:.4g} mm)"
        )
    return Quantity(magnitude=2.0 * t * s * quality_factor / denominator, unit="MPa")


def asme_b313_minimum_ordered_wall(
    *,
    pressure_design_thickness: Quantity,
    mechanical_allowance: Quantity,
    mill_tolerance_fraction: float = 0.125,
) -> Quantity:
    """The nominal wall to order so the thinnest delivered pipe still holds pressure.

    ASME B31.3 §304.1.1: the required minimum wall is the pressure-design thickness
    plus the mechanical allowances, t_m = t + c (``pressure_design_thickness`` t from
    :func:`asme_b313_pipe_wall_thickness`, ``mechanical_allowance`` c the sum of the
    corrosion/erosion allowance and any thread or groove depth). But pipe ships up to
    a ``mill_tolerance_fraction`` under nominal (12.5% for seamless pipe), so the
    *ordered* nominal wall must be T = (t + c)/(1 − mill_tolerance) for the thinnest
    delivered pipe to still meet t_m. Pick the first schedule at or above T. Both
    thicknesses positive; the mill tolerance in [0, 1). Returns the minimum nominal
    wall in mm.
    """
    _require(pressure_design_thickness, "[length]", "pressure_design_thickness")
    _require(mechanical_allowance, "[length]", "mechanical_allowance")
    if not 0 <= mill_tolerance_fraction < 1:
        raise ValueError(
            f"mill_tolerance_fraction must lie in [0, 1); got {mill_tolerance_fraction}"
        )
    t = pressure_design_thickness.to("mm").magnitude
    c = mechanical_allowance.to("mm").magnitude
    if t <= 0 or c < 0:
        raise ValueError(
            "pressure_design_thickness must be positive and mechanical_allowance non-negative"
        )
    return Quantity(magnitude=(t + c) / (1.0 - mill_tolerance_fraction), unit="mm")


def asme_b313_branch_required_reinforcement_area(
    *,
    header_pressure_design_thickness: Quantity,
    branch_outside_diameter: Quantity,
    branch_wall: Quantity,
    mechanical_allowance: Quantity,
    branch_angle_deg: float = 90.0,
) -> Quantity:
    """The ASME B31.3 §304.3.3 reinforcement area a branch connection requires,
    A1 = t_h·d1·(2 − sin β).

    Cutting a hole in the run for a branch removes pressure-carrying metal that must
    be replaced nearby. The required replacement area is A1 = t_h·d1·(2 − sin β),
    where ``header_pressure_design_thickness`` t_h is the run's pressure-design wall,
    the effective removed width d1 = [D_b − 2·(T_b − c)]/sin β is the branch opening
    projected onto the run, ``branch_outside_diameter`` D_b and ``branch_wall`` T_b
    are the branch's dimensions, ``mechanical_allowance`` c its corrosion/thread
    allowance, and ``branch_angle_deg`` β the angle between the branch and run axes.
    A skewed branch (β < 90°) opens a longer hole and needs more reinforcement.
    Compare A1 to the available excess-wall and added-pad area (A2+A3+A4); the branch
    is adequately reinforced when that meets or exceeds A1. Returns A1 in mm².
    """
    _require(header_pressure_design_thickness, "[length]", "header_pressure_design_thickness")
    _require(branch_outside_diameter, "[length]", "branch_outside_diameter")
    _require(branch_wall, "[length]", "branch_wall")
    _require(mechanical_allowance, "[length]", "mechanical_allowance")
    if not 0 < branch_angle_deg <= 90:
        raise ValueError(f"branch_angle_deg must lie in (0, 90]; got {branch_angle_deg}")
    th = header_pressure_design_thickness.to("mm").magnitude
    db = branch_outside_diameter.to("mm").magnitude
    tb = branch_wall.to("mm").magnitude
    c = mechanical_allowance.to("mm").magnitude
    if th <= 0 or db <= 0 or tb <= 0 or c < 0:
        raise ValueError(
            "the header thickness, branch diameter, and branch wall must be positive and "
            "the mechanical allowance non-negative"
        )
    sin_beta = sin(radians(branch_angle_deg))
    d1 = (db - 2.0 * (tb - c)) / sin_beta
    if d1 <= 0:
        raise ValueError("the branch wall consumes the whole opening; check the inputs")
    return Quantity(magnitude=th * d1 * (2.0 - sin_beta), unit="mm**2")


def asme_b313_allowable_displacement_stress_range(
    *,
    cold_allowable: Quantity,
    hot_allowable: Quantity,
    stress_range_factor: float = 1.0,
) -> Quantity:
    """The ASME B31.3 §302.3.5 allowable displacement stress range,
    S_A = f·(1.25·S_c + 0.25·S_h).

    A piping system's thermal expansion is restrained at its anchors, and the
    resulting secondary (displacement) stress cycles as the line heats and cools —
    a fatigue question, not a pressure one. The allowable range is
    S_A = f·(1.25·S_c + 0.25·S_h), where ``cold_allowable`` S_c and ``hot_allowable``
    S_h are the basic allowable stresses at the cold (installed) and hot (operating)
    conditions, and ``stress_range_factor`` f (the cyclic-reduction factor, ≤ 1,
    from Table 302.3.5 — 1.0 up to 7,000 equivalent cycles, falling for more) accounts
    for the number of thermal cycles. Compare the computed expansion stress range
    against this. S_c, S_h, and f are user-supplied code inputs. Returns S_A in MPa.
    """
    _require(cold_allowable, "[pressure]", "cold_allowable")
    _require(hot_allowable, "[pressure]", "hot_allowable")
    if stress_range_factor <= 0:
        raise ValueError(f"stress_range_factor must be positive; got {stress_range_factor}")
    sc = cold_allowable.to("MPa").magnitude
    sh = hot_allowable.to("MPa").magnitude
    if sc <= 0 or sh <= 0:
        raise ValueError("cold_allowable and hot_allowable must be positive")
    return Quantity(magnitude=stress_range_factor * (1.25 * sc + 0.25 * sh), unit="MPa")


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
