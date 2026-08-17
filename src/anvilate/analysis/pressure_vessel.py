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

from math import cos, radians, sin, sqrt, tan

from pydantic import BaseModel, ConfigDict, model_validator

from ..scorecard import CheckStatus, ScorecardEntry
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
    "AllowableStress",
    "asme_b313_miter_bend_pressure",
    "asme_b313_pressure_scorecard",
    "asme_b313_pipe_wall_thickness",
    "asme_b313_pipe_pressure",
    "asme_b313_minimum_ordered_wall",
    "asme_b313_branch_required_reinforcement_area",
    "asme_b313_allowable_displacement_stress_range",
    "asme_b313_bend_stress_intensification",
    "asme_b313_displacement_stress",
    "thick_wall_cylinder",
    "thick_wall_cylinder_stress_at_radius",
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
    # An external (negative gauge) pressure is not a membrane-tension problem at all — the
    # shell is governed by buckling, which this module does not screen — and the formula
    # obligingly returned a negative thickness for it. The sibling ASME sizer in this module
    # already guards both, so this matches it rather than inventing a new refusal.
    if pressure.to("MPa").magnitude <= 0:
        raise ValueError(
            f"pressure must be a positive internal gauge pressure; got {pressure}. External "
            f"pressure is a buckling problem (ASME UG-28), not a membrane one"
        )
    if radius.to("mm").magnitude <= 0:
        raise ValueError(f"radius must be positive; got {radius}")
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


_CLAUSE_B313_PRESSURE_DESIGN = "ASME B31.3 §304.1.2 straight-pipe pressure design"
_CLAUSE_B313_MITER = "ASME B31.3 §304.2.3 miter bends"
# B31.3 304.2.3 splits the single-miter formula at a 22.5 deg cut angle, and scopes the
# multiple-miter treatment to cuts at or below it.
_MITER_ANGLE_SPLIT_DEG = 22.5


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
    thickness = p * d / (2.0 * (s * quality_factor + p * coefficient_y))
    _check_b313_thin_wall(thickness, d, "the thickness this pressure requires")
    return Quantity(magnitude=thickness, unit="mm")


# ASME B31.3 304.1.2 scopes the straight-pipe formula to t < D/6. It is not a soft seam:
# it is exactly where the formula crosses from conservative to unconservative against the
# Lamé thick-wall requirement (14% short at t/D = 0.32), and at P >= S it keeps returning a
# confident number for a pressure no monobloc wall can hold to the allowable. The sibling
# ASME VIII functions in this module already enforce their analogous limits.
_B313_THICKNESS_RATIO_LIMIT = 1.0 / 6.0


def _check_b313_thin_wall(thickness_mm: float, diameter_mm: float, label: str) -> None:
    """Refuse a t/D past the ASME B31.3 304.1.2 scope of the straight-pipe formula."""
    ratio = thickness_mm / diameter_mm
    if ratio >= _B313_THICKNESS_RATIO_LIMIT:
        raise ValueError(
            f"{label} gives t/D = {ratio:.4g}, at or past the t < D/6 = "
            f"{_B313_THICKNESS_RATIO_LIMIT:.4g} that ASME B31.3 304.1.2 scopes this "
            f"formula to. Past it the straight-pipe form runs UNconservative against the "
            f"thick-wall (Lame) requirement — 14% short at t/D = 0.32 — so B31.3 304.1.2(b) "
            f"requires a thick-wall analysis instead."
        )


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
    _check_b313_thin_wall(t, d, "wall_thickness")
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


def asme_b313_bend_stress_intensification(
    *,
    wall_thickness: Quantity,
    bend_radius: Quantity,
    mean_radius: Quantity,
) -> tuple[float, float]:
    """The ASME B31.3 Appendix D stress-intensification factors of a welding elbow / bend.

    A pipe bend is more flexible *and* more highly stressed than the straight pipe it
    replaces: as the line expands, the bend ovalizes, concentrating the bending stress.
    B31.3 rolls that into a stress-intensification factor (SIF) i that multiplies the
    nominal bending stress in the displacement-stress check
    (:func:`asme_b313_allowable_displacement_stress_range`). For a welding elbow the SIFs
    come from the flexibility characteristic h = T·R₁/r₂²: the in-plane factor is
    i_i = 0.9/h^(2/3) and the out-of-plane factor i_o = 0.75/h^(2/3), each floored at 1.0
    (a fitting is never less severe than straight pipe). ``wall_thickness`` T,
    ``bend_radius`` R₁ (the elbow's centreline bend radius), and ``mean_radius`` r₂ (the
    mean radius of the pipe wall, (D_o − T)/2). A long-radius, thick-walled bend (large h)
    has SIFs near 1; a short-radius thin bend concentrates stress the most. Returns the
    pair (in-plane, out-of-plane) as dimensionless factors.
    """
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(bend_radius, "[length]", "bend_radius")
    _require(mean_radius, "[length]", "mean_radius")
    t = wall_thickness.to("mm").magnitude
    r1 = bend_radius.to("mm").magnitude
    r2 = mean_radius.to("mm").magnitude
    if t <= 0 or r1 <= 0 or r2 <= 0:
        raise ValueError("wall_thickness, bend_radius, and mean_radius must be positive")
    h = t * r1 / r2**2
    in_plane = max(0.9 / h ** (2.0 / 3.0), 1.0)
    out_of_plane = max(0.75 / h ** (2.0 / 3.0), 1.0)
    return in_plane, out_of_plane


def asme_b313_displacement_stress(
    *,
    in_plane_moment: Quantity,
    out_of_plane_moment: Quantity,
    torsional_moment: Quantity,
    section_modulus: Quantity,
    in_plane_sif: float = 1.0,
    out_of_plane_sif: float = 1.0,
) -> Quantity:
    """The ASME B31.3 §319.4.4 displacement (expansion) stress range S_E at a fitting.

    The thermal-expansion stress a restrained line develops, computed from the moment
    ranges the flexibility analysis reports and the fitting's stress-intensification
    factors (:func:`asme_b313_bend_stress_intensification`). The bending and torsional
    parts combine as S_E = √(S_b² + 4·S_t²), where the intensified resultant bending
    stress is S_b = √((i_i·M_i)² + (i_o·M_o)²)/Z and the torsional stress S_t = M_t/(2·Z).
    ``in_plane_moment`` M_i, ``out_of_plane_moment`` M_o, and ``torsional_moment`` M_t are
    the moment ranges (peak-to-peak over the thermal cycle), ``section_modulus`` Z the
    pipe section modulus, and ``in_plane_sif`` i_i / ``out_of_plane_sif`` i_o the SIFs
    (1.0 for straight pipe). Compare the result against the allowable range
    (:func:`asme_b313_allowable_displacement_stress_range`). Returns S_E in MPa.
    """
    _require(in_plane_moment, "[force] * [length]", "in_plane_moment")
    _require(out_of_plane_moment, "[force] * [length]", "out_of_plane_moment")
    _require(torsional_moment, "[force] * [length]", "torsional_moment")
    if not section_modulus.has_dimension("[length]**3"):
        raise ValueError("section_modulus must be a [length]**3 quantity")
    mi = in_plane_moment.to("N*mm").magnitude
    mo = out_of_plane_moment.to("N*mm").magnitude
    mt = torsional_moment.to("N*mm").magnitude
    z = section_modulus.to("mm**3").magnitude
    if z <= 0:
        raise ValueError("section_modulus must be positive")
    if in_plane_sif < 1.0 or out_of_plane_sif < 1.0:
        raise ValueError("stress-intensification factors must be at least 1.0")
    s_b = ((in_plane_sif * mi) ** 2 + (out_of_plane_sif * mo) ** 2) ** 0.5 / z
    s_t = mt / (2.0 * z)
    s_e = (s_b**2 + 4.0 * s_t**2) ** 0.5
    return Quantity(magnitude=s_e, unit="MPa")


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


def thick_wall_cylinder_stress_at_radius(
    *,
    pressure: Quantity,
    inner_radius: Quantity,
    wall_thickness: Quantity,
    radius: Quantity,
    closed_ends: bool = True,
) -> ThickWallStress:
    """The exact Lamé stresses at any radius in an internally-pressurized thick-wall cylinder.

    :func:`thick_wall_cylinder` reports the bore, where the stress peaks; this gives the full
    through-wall distribution the bore is one point of. At radius r (r_i ≤ r ≤ r_o) under internal
    ``pressure`` p, the Lamé field is

        σ_hoop  = p·r_i²/(r_o² − r_i²)·(1 + r_o²/r²),
        σ_radial = p·r_i²/(r_o² − r_i²)·(1 − r_o²/r²),

    with the axial ``longitudinal_stress`` constant across the wall (p·r_i²/(r_o² − r_i²) for closed
    ends, 0 for open). Both fall monotonically from the bore to the OD — the hoop from its peak
    p·(r_o² + r_i²)/(r_o² − r_i²) to 2·σ_long, the radial from −p to 0 — so a wall is worked hardest
    at the bore and this quantifies the reserve deeper in. ``inner_radius`` r_i and
    ``wall_thickness`` set r_o = r_i + t; ``radius`` r must lie within the wall. Returns the
    :class:`ThickWallStress` at r.
    """
    _require(pressure, "[pressure]", "pressure")
    _require(inner_radius, "[length]", "inner_radius")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(radius, "[length]", "radius")
    p = pressure.to("MPa").magnitude
    ri = inner_radius.to("mm").magnitude
    t = wall_thickness.to("mm").magnitude
    r = radius.to("mm").magnitude
    if p <= 0 or ri <= 0 or t <= 0:
        raise ValueError("pressure, inner_radius, and wall_thickness must be positive")
    ro = ri + t
    if not ri <= r <= ro:
        raise ValueError(f"radius must lie within the wall [{ri}, {ro}] mm (bore to OD); got {r}")
    denom = ro**2 - ri**2
    coefficient = p * ri**2 / denom
    longitudinal = coefficient if closed_ends else 0.0
    return ThickWallStress(
        hoop_stress=Quantity(magnitude=coefficient * (1.0 + ro**2 / r**2), unit="MPa"),
        radial_stress=Quantity(magnitude=coefficient * (1.0 - ro**2 / r**2), unit="MPa"),
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


class AllowableStress(BaseModel):
    """A code allowable stress, the temperature it was read at, and where it came from.

    The B31.3 allowable stress tables are copyrighted, so the value is always the
    caller's to supply — but a bare number is not enough to review. An allowable is
    only meaningful *at a temperature*: A106-B is 138 MPa at 200 °C and 110 MPa at
    400 °C, and a screen handed the first number for a line running at the second is
    wrong by 25% with nothing to show for it.

    ``value`` S is the allowable stress, ``temperature`` the design temperature the
    table was read at, ``material`` the material designation, and ``source`` where the
    number came from (the table and edition, a datasheet, a client specification) so
    the report can cite it rather than presenting it as Anvilate's own.

    :meth:`is_valid_at` is the guard this type exists for: it says whether the
    allowable was read close enough to a stated design temperature to be used, and it
    answers ``False`` rather than interpolating between table rows Anvilate does not
    have.
    """

    model_config = ConfigDict(frozen=True)

    value: Quantity
    temperature: Quantity
    material: str
    source: str

    @model_validator(mode="after")
    def _well_formed(self) -> AllowableStress:
        if not self.value.has_dimension("[pressure]"):
            raise ValueError(f"value must be a [pressure] quantity; got {self.value}")
        if self.value.to("MPa").magnitude <= 0:
            raise ValueError(f"value must be positive; got {self.value}")
        if not self.temperature.has_dimension("[temperature]"):
            raise ValueError(
                f"temperature must be a [temperature] quantity; got {self.temperature}"
            )
        if not self.material.strip():
            raise ValueError("material must name the material the allowable belongs to")
        if not self.source.strip():
            raise ValueError("source must record where the allowable was read from")
        return self

    def is_valid_at(
        self, design_temperature: Quantity, *, tolerance: Quantity | None = None
    ) -> bool:
        """Whether this allowable may be used at ``design_temperature``.

        The allowable must have been read at or above the design temperature — code
        allowables fall with temperature, so a value read cooler is unconservative —
        and within ``tolerance`` of it (25 K by default), because the table rows are
        spaced and Anvilate does not have the rows to interpolate between. A value read
        far *hotter* than the service is safe but is not the number the code wants, so
        it fails too and the caller is told to read the right row.
        """
        if not design_temperature.has_dimension("[temperature]"):
            raise ValueError(
                f"design_temperature must be a [temperature] quantity; got {design_temperature}"
            )
        band = 25.0 if tolerance is None else tolerance.to("K").magnitude
        if band < 0:
            raise ValueError(f"tolerance must not be negative; got {tolerance}")
        read_at = self.temperature.to("K").magnitude
        design = design_temperature.to("K").magnitude
        return design <= read_at <= design + band

    def __str__(self) -> str:
        return f"{self.value.to('MPa')} for {self.material} at {self.temperature} [{self.source}]"


def asme_b313_pressure_scorecard(
    name: str,
    *,
    design_pressure: Quantity,
    design_temperature: Quantity,
    outside_diameter: Quantity,
    nominal_wall: Quantity,
    allowable: AllowableStress | None,
    quality_factor: float = 1.0,
    coefficient_y: float = 0.4,
    mill_tolerance_fraction: float = 0.125,
    corrosion_allowance: Quantity | None = None,
) -> ScorecardEntry:
    """Screen a straight pipe's pressure rating against its service → a scorecard entry.

    Rates the wall the pipe can be *relied on* to have — ``nominal_wall`` less the mill
    under-tolerance and the ``corrosion_allowance`` — through
    :func:`asme_b313_pipe_pressure`, and judges that rating against ``design_pressure``.
    The safety factor is rating over service, and the target is 1.0 because the B31.3
    allowable already carries the code margin.

    Two ways this reports ``NOT_EVALUATED`` rather than a number, and both are the
    point of the check:

    * ``allowable`` is ``None`` — no allowable stress was supplied. The B31.3 tables are
      the caller's to provide, and a pressure check without one has not been made.
    * the allowable was read at a temperature that does not match ``design_temperature``
      (see :meth:`AllowableStress.is_valid_at`). A 200 °C allowable on a 400 °C line is
      a quarter too high, and the arithmetic cannot tell.

    A wall entirely consumed by its allowances is ``NOT_EVALUATED`` too: there is no
    pressure-carrying wall left to rate, which is not the same as a rating of zero.
    """
    if allowable is None:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no B31.3 allowable stress supplied",
            reference=_CLAUSE_B313_PRESSURE_DESIGN,
        )
    if not allowable.is_valid_at(design_temperature):
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"not evaluated — the allowable was read at {allowable.temperature} but the "
                f"design temperature is {design_temperature}; read the allowable at the "
                f"design temperature rather than interpolating"
            ),
            reference=_CLAUSE_B313_PRESSURE_DESIGN,
        )
    _require(design_pressure, "[pressure]", "design_pressure")
    _require(nominal_wall, "[length]", "nominal_wall")
    if not 0.0 <= mill_tolerance_fraction < 1.0:
        raise ValueError(
            f"mill_tolerance_fraction must lie in [0, 1); got {mill_tolerance_fraction}"
        )
    available = nominal_wall.to("mm").magnitude * (1.0 - mill_tolerance_fraction)
    if corrosion_allowance is not None:
        _require(corrosion_allowance, "[length]", "corrosion_allowance")
        available -= corrosion_allowance.to("mm").magnitude
    if available <= 0:
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                "not evaluated — the mill tolerance and corrosion allowance consume the "
                "whole nominal wall, so there is none left to carry pressure"
            ),
            reference=_CLAUSE_B313_PRESSURE_DESIGN,
        )
    rating = asme_b313_pipe_pressure(
        wall_thickness=Quantity(magnitude=available, unit="mm"),
        outside_diameter=outside_diameter,
        allowable_stress=allowable.value,
        quality_factor=quality_factor,
        coefficient_y=coefficient_y,
    )
    service = design_pressure.to("MPa").magnitude
    computed = None if service <= 0 else rating.to("MPa").magnitude / service
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0).model_copy(
        update={
            "reference": _CLAUSE_B313_PRESSURE_DESIGN,
            "detail": (
                f"{available:.2f} mm available wall rates {rating.to('MPa').magnitude:.2f} MPa "
                f"against a {service:.2f} MPa service ({allowable})"
            )
            if computed is not None
            else "not evaluated — no design pressure",
        }
    )


def asme_b313_miter_bend_pressure(
    *,
    allowable_stress: Quantity,
    wall_thickness: Quantity,
    mean_radius: Quantity,
    miter_angle: float,
    effective_bend_radius: Quantity | None = None,
    quality_factor: float = 1.0,
) -> Quantity:
    """The ASME B31.3 §304.2.3 maximum internal pressure of a miter bend.

    A miter bend turns a line by welding straight pipe segments at an angle instead of
    using a formed elbow. It is cheaper and it is weaker: the cut leaves the wall
    carrying a bending moment the straight-pipe hoop formula knows nothing about, so a
    miter rates well below the pipe it is made from. §304.2.3 gives the rating.

    ``wall_thickness`` T is the pressure-carrying wall (nominal less the mill tolerance
    and allowances — see :meth:`AllowableStress` and the straight-pipe check),
    ``mean_radius`` r₂ the mean radius of the pipe, ``miter_angle`` θ the *cut* angle in
    degrees (half the change of direction the joint makes, so a 90° elbow built from
    two cuts has θ = 22.5°), and ``allowable_stress`` S and ``quality_factor`` E as in
    :func:`asme_b313_pipe_wall_thickness`.

    Two treatments, and which applies depends on the geometry:

    * **Single miter** (``effective_bend_radius`` left ``None``) —

          θ ≤ 22.5°:  P = (S·E·T/r₂)·[ T / (T + 0.643·tan θ·√(r₂·T)) ]
          θ > 22.5°:  P = (S·E·T/r₂)·[ 1 / (1 + 1.25·tan θ·√(r₂/T)) ]

    * **Multiple miter** (``effective_bend_radius`` R₁ supplied) — the lesser of the
      first expression above and

          P = (S·E·T/r₂)·(R₁ − r₂)/(R₁ − 0.5·r₂),

      because a closely-spaced set of cuts is also limited by how tight the bend is.

    The cut angle is capped at 22.5° for the multiple-miter case, which the code scopes
    there; past it a multiple miter is outside §304.2.3 and this refuses rather than
    evaluating the first expression alone and reporting a number the code does not
    sanction. ``effective_bend_radius`` must also exceed the mean radius — at R₁ = r₂
    the bend closes on itself and the second expression goes to zero.

    Returns the maximum allowable internal pressure in MPa.
    """
    _require(allowable_stress, "[pressure]", "allowable_stress")
    _require(wall_thickness, "[length]", "wall_thickness")
    _require(mean_radius, "[length]", "mean_radius")
    if not 0 < quality_factor <= 1:
        raise ValueError(f"quality_factor must lie in (0, 1]; got {quality_factor}")
    s = allowable_stress.to("MPa").magnitude
    t = wall_thickness.to("mm").magnitude
    r2 = mean_radius.to("mm").magnitude
    if s <= 0 or t <= 0 or r2 <= 0:
        raise ValueError("allowable_stress, wall_thickness, and mean_radius must be positive")
    if not 0 < miter_angle < 90:
        raise ValueError(
            f"miter_angle is the cut angle in degrees and must lie in (0, 90); got {miter_angle}"
        )
    base = s * quality_factor * t / r2
    tan_theta = tan(radians(miter_angle))
    # The θ ≤ 22.5° expression, which is also the first of the two multiple-miter limits.
    shallow = base * t / (t + 0.643 * tan_theta * sqrt(r2 * t))

    if effective_bend_radius is None:
        if miter_angle <= _MITER_ANGLE_SPLIT_DEG:
            return Quantity(magnitude=shallow, unit="MPa")
        steep = base / (1.0 + 1.25 * tan_theta * sqrt(r2 / t))
        return Quantity(magnitude=steep, unit="MPa")

    _require(effective_bend_radius, "[length]", "effective_bend_radius")
    if miter_angle > _MITER_ANGLE_SPLIT_DEG:
        raise ValueError(
            f"a multiple miter bend is scoped by ASME B31.3 §304.2.3 to a cut angle of "
            f"{_MITER_ANGLE_SPLIT_DEG}° or less; got {miter_angle}°. Past it the code gives no "
            f"multiple-miter rating — screen each cut as a single miter, or use a formed elbow."
        )
    r1 = effective_bend_radius.to("mm").magnitude
    if r1 <= r2:
        raise ValueError(
            f"effective_bend_radius ({effective_bend_radius}) must exceed the mean radius "
            f"({mean_radius}): at or below it the bend closes on itself and §304.2.3's "
            f"(R₁ − r₂)/(R₁ − 0.5·r₂) term is not positive"
        )
    tight = base * (r1 - r2) / (r1 - 0.5 * r2)
    return Quantity(magnitude=min(shallow, tight), unit="MPa")
