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

from math import cos, log10, radians, sin, sqrt, tan

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import Provenance, RevalidatedModel
from ..derivation import Derivation, SymbolValue
from ..scorecard import CheckStatus, ScorecardEntry
from ..units import Quantity, require_finite
from ..units.temperature import temperature_difference_kelvin
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
    "BranchReinforcement",
    "asme_b313_branch_reinforcement",
    "asme_b313_branch_reinforcement_scorecard",
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
    "NozzleReinforcement",
    "FlangeGasketGeometry",
    "asme_ug37_nozzle_reinforcement",
    "asme_ug37_reinforcement_scorecard",
    "asme_appendix_2_gasket_geometry",
    "asme_appendix_2_required_bolt_area",
    "FlangeShapeFactors",
    "FlangeMoments",
    "LooseRingFlangeStress",
    "asme_appendix_2_shape_factors",
    "asme_appendix_2_flange_moments",
    "asme_appendix_2_ring_flange_stress",
    "asme_appendix_2_flange_stress_scorecard",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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


# The membrane forms are the r/t -> infinity limit of Lame, and the module docstring puts
# their floor at r/t ~ 10. Below it the error is not academic: at r/t = 2 the hoop is 23%
# under the exact bore value and the Tresca-relevant number is 44% under, and the SIZING
# inverse compounds it -- a wall sized by the thin form at p/S = 0.5 comes out 32% thin and
# runs 30% over the allowable it was sized against. The exact `thick_wall_cylinder` takes
# the same arguments and sits in this module, so the refusal has somewhere to send you.
# The sibling ASME B31.3 pair already enforces its analogous t < D/6 scope.
_THIN_WALL_RATIO_FLOOR = 10.0


def _check_thin_wall_scope(radius_mm: float, thickness_mm: float, label: str) -> None:
    """Refuse an r/t below the scope of the thin-wall membrane forms."""
    ratio = radius_mm / thickness_mm
    if ratio < _THIN_WALL_RATIO_FLOOR:
        raise ValueError(
            f"{label} gives r/t = {ratio:.4g}, below the r/t >= {_THIN_WALL_RATIO_FLOOR:g} "
            f"scope of the thin-wall membrane forms. The membrane stress is the large-r/t "
            f"limit of Lame and it understates the bore stress here (23% low at r/t = 2, and "
            f"the Tresca value 44% low). Use thick_wall_cylinder, which takes the same "
            f"arguments and is exact."
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
    if pressure.magnitude <= 0:
        raise ValueError(
            f"pressure must be positive; got {pressure}. A negative (external) pressure "
            f"returns a NEGATIVE membrane stress here, which is not the limit state: a "
            f"shell under external pressure fails by buckling, and the membrane formula "
            f"says nothing about it. Every other function in this module refuses it."
        )

    p = pressure.pint
    r = radius.pint
    t = wall_thickness.pint
    hoop = p * r / t
    longitudinal = p * r / (2 * t)
    ratio = (radius.to("mm").magnitude) / (wall_thickness.to("mm").magnitude)
    _check_thin_wall_scope(
        radius.to("mm").magnitude, wall_thickness.to("mm").magnitude, "the geometry given"
    )
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

    Source: Roark's *Formulas for Stress and Strain*, the thin-shell pressure formulas.
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

    A thin-wall (membrane) size, and the scope is enforced rather than delegated: when
    the required wall gives r/t < 10 the wall carries a genuine gradient, the membrane
    size comes out about 32% thin, and this raises naming the exact Lamé form
    (:func:`thick_wall_cylinder`) instead of returning the number.
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
    sized = _as_quantity(thickness, "mm")
    _check_thin_wall_scope(
        radius.to("mm").magnitude, sized.magnitude, "the thickness this pressure requires"
    )
    return sized


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
# One row of the ASME B31.3 Table A-1 temperature grid, which is spaced 100 degF.
_ALLOWABLE_TEMPERATURE_BAND_K = 56.0
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


_CLAUSE_B313_BRANCH = "ASME B31.3 §304.3.3 (reinforcement of welded branch connections)"


class BranchReinforcement(BaseModel):
    """The ASME B31.3 §304.3.3 area accounting for a welded branch connection.

    ``required`` A1 is the pressure-carrying metal the opening removed.
    ``run_excess`` A2 is the run pipe's wall beyond what pressure needs, within the
    reinforcement zone; ``branch_excess`` A3 the same for the branch; ``added`` A4 the
    pad and weld metal the caller declares. ``available`` is their sum.

    ``half_width`` d2 and ``height`` L4 are the zone the credit is taken over, reported
    because they are where the accounting goes wrong: metal outside the zone is real
    metal that does not count, and both limits move with the *branch* as well as the run.

    ``adequate`` is available ≥ required, and ``deficit`` is what a pad still has to
    supply — the number that actually sizes the pad.
    """

    model_config = ConfigDict(frozen=True)

    required: Quantity
    run_excess: Quantity
    branch_excess: Quantity
    added: Quantity
    available: Quantity
    half_width: Quantity
    height: Quantity
    adequate: bool
    deficit: Quantity
    # True when d2 was cut back to the run's outside diameter, which is the branch being
    # large enough relative to its run that the zone would otherwise leave the pipe.
    zone_limited_by_run: bool

    def __str__(self) -> str:
        verdict = "adequate" if self.adequate else f"short by {self.deficit}"
        return (
            f"B31.3 branch reinforcement {verdict}: "
            f"{self.available} available against {self.required}"
        )


def asme_b313_branch_reinforcement(
    *,
    run_outside_diameter: Quantity,
    run_wall: Quantity,
    run_pressure_design_thickness: Quantity,
    branch_outside_diameter: Quantity,
    branch_wall: Quantity,
    branch_pressure_design_thickness: Quantity,
    mechanical_allowance: Quantity,
    branch_angle_deg: float = 90.0,
    pad_thickness: Quantity | None = None,
    added_area: Quantity | None = None,
) -> BranchReinforcement:
    """The ASME B31.3 §304.3.3 area accounting for a welded branch connection.

    Cutting a hole in the run removes pressure-carrying metal that must be replaced
    within a zone around the opening. The required area is
    :func:`asme_b313_branch_required_reinforcement_area`'s A1 = t_h·d1·(2 − sin β); what
    replaces it is A2 + A3 + A4 over a zone 2·d2 wide and L4 tall:

    * **d1 = [D_b − 2(T_b − c)] / sin β**, the effective width the opening removed.
    * **d2**, the zone's half width, is the *greater* of d1 and
      (T_b − c) + (T_h − c) + d1/2.
    * **L4**, the zone's height above the run, is the *lesser* of 2.5(T_h − c) and
      2.5(T_b − c) + T_r.
    * **A2 = (2·d2 − d1)(T_h − t_h − c)**, the run's excess wall inside the zone.
    * **A3 = 2·L4·(T_b − t_b − c) / sin β**, the branch's excess wall inside the zone.
    * **A4** is pad and weld metal, which only the caller knows.

    **Both zone limits are "whichever is smaller/larger" and both mix the run with the
    branch**, which is where this accounting is got wrong by hand: taking L4 as
    2.5(T_h − c) alone credits a thin branch with the run's zone height, and taking d2 as
    d1 alone under-credits a thick-walled small branch. Each is computed here from both
    pipes.

    ``pad_thickness`` T_r raises L4 and therefore **A3 as well as A4** — a reinforcing
    pad lengthens the branch's zone. Omitted, it is zero: the accounting then credits no
    pad, which understates the available area rather than overstating it.

    ``added_area`` A4 is taken as declared. The Code credits only metal *inside* the
    zone, and an area alone does not say where the metal is, so this function cannot
    check that and does not pretend to: supply the portion of the pad and welds that lies
    within 2·d2 by L4. Omitted, A4 is zero and the accounting is the conservative one.

    Returns a :class:`BranchReinforcement`. Anchored against three published calculation
    sheets — an NPS 8 × NPS 4 Schedule 40 example (A1 0.5918 in², A2 0.7046 in²,
    A3 0.1896 in²) and two Keon Sae weldolet sheets in millimetres — each of which
    reproduces d1, d2, L4, A1, A2 and A3 exactly.
    """
    for value, name in (
        (run_outside_diameter, "run_outside_diameter"),
        (run_wall, "run_wall"),
        (run_pressure_design_thickness, "run_pressure_design_thickness"),
        (branch_outside_diameter, "branch_outside_diameter"),
        (branch_wall, "branch_wall"),
        (branch_pressure_design_thickness, "branch_pressure_design_thickness"),
        (mechanical_allowance, "mechanical_allowance"),
    ):
        _require(value, "[length]", name)
    if not 0 < branch_angle_deg <= 90:
        raise ValueError(f"branch_angle_deg must lie in (0, 90]; got {branch_angle_deg}")

    dh = run_outside_diameter.to("mm").magnitude
    th_actual = run_wall.to("mm").magnitude
    th = run_pressure_design_thickness.to("mm").magnitude
    db = branch_outside_diameter.to("mm").magnitude
    tb_actual = branch_wall.to("mm").magnitude
    tb = branch_pressure_design_thickness.to("mm").magnitude
    c = mechanical_allowance.to("mm").magnitude
    if pad_thickness is not None:
        _require(pad_thickness, "[length]", "pad_thickness")
    if added_area is not None:
        _require(added_area, "[length]**2", "added_area")
    tr = 0.0 if pad_thickness is None else pad_thickness.to("mm").magnitude
    a4 = 0.0 if added_area is None else added_area.to("mm**2").magnitude

    if min(dh, th_actual, th, db, tb_actual, tb) <= 0 or c < 0 or tr < 0 or a4 < 0:
        raise ValueError(
            "every diameter and thickness must be positive, and the mechanical "
            "allowance, pad thickness and added area non-negative"
        )
    if db > dh:
        raise ValueError(
            f"the branch ({branch_outside_diameter}) is larger than the run "
            f"({run_outside_diameter}); §304.3.3's area replacement is written for a "
            "branch in a run, and a larger branch is a reducing tee or a header "
            "transition rather than a reinforced opening"
        )
    if th_actual - th - c < 0 or tb_actual - tb - c < 0:
        raise ValueError(
            "a pipe whose wall is below its own pressure design thickness plus allowance "
            "has no excess to credit and is not adequate for the pressure in the first "
            "place; screen the straight-pipe wall before the branch"
        )

    sin_beta = sin(radians(branch_angle_deg))
    d1 = (db - 2.0 * (tb_actual - c)) / sin_beta
    if d1 <= 0:
        raise ValueError("the branch wall consumes the whole opening; check the inputs")

    # d2 is the greater of the two, capped at the run's outside diameter: a zone wider
    # than the pipe it sits on is credit taken from metal that is not there.
    d2_unlimited = max(d1, (tb_actual - c) + (th_actual - c) + d1 / 2.0)
    d2 = min(d2_unlimited, dh)
    l4 = min(2.5 * (th_actual - c), 2.5 * (tb_actual - c) + tr)

    # A1 through the function that already publishes it, not a second copy of the
    # formula. Two implementations of one Code expression are two places for it to
    # change, and the one that moves is always the one nothing is anchored against.
    a1 = (
        asme_b313_branch_required_reinforcement_area(
            header_pressure_design_thickness=run_pressure_design_thickness,
            branch_outside_diameter=branch_outside_diameter,
            branch_wall=branch_wall,
            mechanical_allowance=mechanical_allowance,
            branch_angle_deg=branch_angle_deg,
        )
        .to("mm**2")
        .magnitude
    )
    a2 = (2.0 * d2 - d1) * (th_actual - th - c)
    a3 = 2.0 * l4 * (tb_actual - tb - c) / sin_beta
    available = a2 + a3 + a4
    return BranchReinforcement(
        required=Quantity(magnitude=a1, unit="mm**2"),
        run_excess=Quantity(magnitude=a2, unit="mm**2"),
        branch_excess=Quantity(magnitude=a3, unit="mm**2"),
        added=Quantity(magnitude=a4, unit="mm**2"),
        available=Quantity(magnitude=available, unit="mm**2"),
        half_width=Quantity(magnitude=d2, unit="mm"),
        height=Quantity(magnitude=l4, unit="mm"),
        adequate=available >= a1,
        deficit=Quantity(magnitude=max(0.0, a1 - available), unit="mm**2"),
        zone_limited_by_run=d2_unlimited > dh,
    )


def asme_b313_branch_reinforcement_scorecard(
    name: str,
    *,
    reinforcement: BranchReinforcement | None,
    required: float = 1.0,
    missing: str = "",
) -> ScorecardEntry:
    """Screen an ASME B31.3 §304.3.3 branch area accounting into a :class:`ScorecardEntry`.

    The safety factor is available area over required area, judged against ``required``
    (1.0 = exactly the Code's rule, which carries no margin of its own). The detail names
    the deficit when there is one, because that is the pad the branch needs, and names
    the zone the credit was taken over.

    ``reinforcement`` of ``None`` is ``NOT_EVALUATED`` — a branch whose run pressure
    design thickness was never computed has not been screened, and ``missing`` says so.
    """
    if reinforcement is not None and not isinstance(reinforcement, BranchReinforcement):
        raise ValueError(f"reinforcement must be a BranchReinforcement; got {reinforcement!r}")
    if reinforcement is None:
        detail = "not evaluated"
        detail += (
            f" — {missing.strip()}"
            if missing.strip()
            else " — the §304.3.3 area accounting could not be run"
        )
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_B313_BRANCH,
        )
    have = reinforcement.available.to("mm**2").magnitude
    need = reinforcement.required.to("mm**2").magnitude
    computed = None if need == 0 else have / need
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = (
        f"{have:.4g} mm² available against {need:.4g} mm² required "
        f"(run {reinforcement.run_excess.magnitude:.4g}, branch "
        f"{reinforcement.branch_excess.magnitude:.4g}, added "
        f"{reinforcement.added.magnitude:.4g}) over a zone "
        f"{2 * reinforcement.half_width.magnitude:.4g} mm wide by "
        f"{reinforcement.height.magnitude:.4g} mm tall"
    )
    if not reinforcement.adequate:
        detail = (
            f"{detail}; short by {reinforcement.deficit.magnitude:.4g} mm², which is the "
            f"area a reinforcing pad has to supply"
        )
    # The three credits, added the way §304.3.3 adds them. A1 is not a symbol here: it is
    # the number this sum is judged against, and it is named in the result's gloss and in
    # the detail line rather than shown as a term of a sum it is not part of.
    derivation = Derivation(
        symbolic="A_avail = A_2 + A_3 + A_4",
        inputs=(
            SymbolValue(
                symbol="A_2",
                description="run's excess wall inside the zone, (2·d2 − d1)(T_h − t_h − c)",
                value=reinforcement.run_excess,
                unit="mm**2",
            ),
            SymbolValue(
                symbol="A_3",
                description="branch's excess wall inside the zone, 2·L4·(T_b − t_b − c)/sin β",
                value=reinforcement.branch_excess,
                unit="mm**2",
            ),
            SymbolValue(
                symbol="A_4",
                description="pad and weld metal the caller declared",
                value=reinforcement.added,
                unit="mm**2",
            ),
        ),
        result=SymbolValue(
            symbol="A_avail",
            description=(
                f"reinforcement available against the {need:.4g} mm² the opening removed "
                f"(A1 = t_h · d1 · (2 − sin β))"
            ),
            value=reinforcement.available,
            unit="mm**2",
        ),
        citation=_CLAUSE_B313_BRANCH,
    )
    return entry.model_copy(
        update={
            "detail": detail,
            "reference": _CLAUSE_B313_BRANCH,
            "derivation": derivation,
        }
    )


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
    conditions, and ``stress_range_factor`` f (the cyclic-reduction factor,
    from Table 302.3.5 — 1.0 up to 7,000 equivalent cycles, falling for more) accounts
    for the number of thermal cycles. f is bounded to (0, 1] and enforced: it only ever
    *reduces* the allowable, so a value above 1 is an input error, not a design choice.
    Compare the computed expansion stress range against this. S_c, S_h, and f are
    user-supplied code inputs. Returns S_A in MPa.
    """
    _require(cold_allowable, "[pressure]", "cold_allowable")
    _require(hot_allowable, "[pressure]", "hot_allowable")
    # f is a cyclic *reduction* factor: Table 302.3.5 tops out at 1.0 for 7,000 equivalent
    # cycles or fewer and falls from there. Above 1.0 it inflates the allowable in the
    # unconservative direction, and nothing downstream would notice — f = 3.0 on a
    # 138/130 MPa pair returns 615 MPa where the ceiling is 205. Every other dimensionless
    # factor in this module is bounded; this one was not.
    if not 0 < stress_range_factor <= 1.0:
        raise ValueError(
            f"stress_range_factor must be in (0, 1]; got {stress_range_factor}. B31.3 "
            f"Table 302.3.5 caps f at 1.0 (7,000 equivalent cycles or fewer) and it "
            f"falls above that — a value over 1 inflates the allowable"
        )
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
    if not isinstance(section_modulus, Quantity):
        raise ValueError(f"section_modulus must be a [length]**3 quantity; got {section_modulus!r}")
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
        # The longitudinal stress is what an open end takes away, and it is zero there —
        # so without it a closed cylinder and an open one at the same pressure render
        # identically while carrying different intensities. `ThinWallStress` prints it.
        return (
            f"thick-wall cylinder: bore hoop {self.hoop_stress.to('MPa')}, "
            f"radial {self.radial_stress.to('MPa')}, "
            f"long {self.longitudinal_stress.to('MPa')}, "
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

    Source: Roark's *Formulas for Stress and Strain*, the thin-shell pressure formulas.
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


# Classical shell buckling is a THIN-shell result: every one of these three formulas is
# derived from membrane-plus-bending shell theory, which needs r/t large. Outside it there
# is no upper bound at all -- at t/R = 1 the axial form returns 0.6*E, about 350x a
# structural steel yield, as a "critical stress" for a stubby tube that is not a
# shell-buckling problem in the first place. r/t >= 10 is the same floor the membrane
# stress functions in this module use.
_SHELL_BUCKLING_RATIO_FLOOR = 10.0


def _check_shell_buckling_scope(radius_mm: float, thickness_mm: float, what: str) -> None:
    """Refuse an r/t below the thin-shell scope of the classical buckling formulas."""
    ratio = radius_mm / thickness_mm
    if ratio < _SHELL_BUCKLING_RATIO_FLOOR:
        raise ValueError(
            f"r/t = {ratio:.4g} is below the r/t >= {_SHELL_BUCKLING_RATIO_FLOOR:g} thin-shell "
            f"scope of the classical {what} formula, which has no upper bound outside it and "
            f"returns critical values many times the material's yield. A wall this thick does "
            f"not fail by shell buckling; screen it as a thick cylinder instead."
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
    _check_shell_buckling_scope(r, t, "cylinder external-pressure buckling")
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

    Source: Timoshenko & Gere, *Theory of Elastic Stability*, the Zoelly buckling pressure.
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
    _check_shell_buckling_scope(r, t, "sphere external-pressure buckling")
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
    _check_shell_buckling_scope(r, t, "cylinder axial buckling")
    sigma_cr = e * (t / r) / sqrt(3.0 * (1.0 - poisson**2))
    return Quantity(magnitude=sigma_cr, unit="MPa")


class AllowableStress(RevalidatedModel):
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
    source: Provenance

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
        if not isinstance(design_temperature, Quantity):
            raise ValueError(
                f"design_temperature must be a [temperature] quantity; got {design_temperature!r}"
            )
        if not design_temperature.has_dimension("[temperature]"):
            raise ValueError(
                f"design_temperature must be a [temperature] quantity; got {design_temperature}"
            )
        if tolerance is None:
            band = _ALLOWABLE_TEMPERATURE_BAND_K
        else:
            # A tolerance is a band WIDTH, and pint converts a degC/degF quantity as an
            # ABSOLUTE temperature: Quantity(25, "degC").to("K") is 298.15, not 25. Written
            # in the same unit as the temperatures — the obvious thing to do — that
            # silently widened the band twelvefold and disarmed the check.
            # The unit is read *after* the type is checked. Reading it first made the
            # refusal below unreachable: a bare `25.0` never got "tolerance must be a
            # [temperature] quantity", it got `AttributeError: 'float' object has no
            # attribute 'unit'` off the guard that was checking it.
            if not isinstance(tolerance, Quantity):
                raise ValueError(f"tolerance must be a [temperature] quantity; got {tolerance!r}")
            if not tolerance.has_dimension("[temperature]"):
                raise ValueError(f"tolerance must be a [temperature] quantity; got {tolerance}")
            # This checked the unit's *spelling* -- "degree_Celsius", "degree_Fahrenheit",
            # "deg" -- and pint renders those units as "°C" and "°F", which contain none of
            # the three. The guard had never fired, and the failure it was written to
            # prevent was live: `tolerance="25 degC"` gave a **298 K** band, so an allowable
            # tabulated at 600 K read as valid for a design at 500 K. A 100 K extrapolation,
            # reported as in-range.
            #
            # `temperature_difference_kelvin` is the library's own answer and it is not
            # keyed on a spelling: it converts 1 and 2 of the unit and requires the result to
            # be linear, which is true of K, delta_degC, delta_degF and degR and false of
            # every offset scale however it is written.
            band = temperature_difference_kelvin(tolerance, name="tolerance")
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
    if allowable is not None and not isinstance(allowable, AllowableStress):
        raise ValueError(f"allowable must be an AllowableStress; got {allowable!r}")
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
    try:
        rating = asme_b313_pipe_pressure(
            wall_thickness=Quantity(magnitude=available, unit="mm"),
            outside_diameter=outside_diameter,
            allowable_stress=allowable.value,
            quality_factor=quality_factor,
            coefficient_y=coefficient_y,
        )
    except ValueError as exc:
        # The t < D/6 scope limit is a real refusal, but this entry point's contract is
        # to turn "cannot evaluate" into a NOT_EVALUATED entry, not to raise out of a
        # scorecard. NPS 1/2 and 3/4 Schedule 160 — ordinary purchasable pipe, and rows
        # of this library's own B36.10M table — land past D/6, so a caller sweeping the
        # schedule table got a traceback instead of a card.
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=f"not evaluated — {exc}",
            reference=_CLAUSE_B313_PRESSURE_DESIGN,
        )
    service = design_pressure.to("MPa").magnitude
    computed = None if service <= 0 else rating.to("MPa").magnitude / service
    # t is the wall the pipe can be RELIED on to have, not the wall it was ordered at: the
    # mill under-tolerance and the corrosion allowance are already off it. Substituting the
    # nominal wall here would render a formula that rates a pipe nobody bought.
    derivation = Derivation(
        symbolic="P = 2 · t · S · E / (D − 2 · Y · t)",
        inputs=(
            SymbolValue(
                symbol="t",
                description=(
                    f"pressure-design wall available — the {nominal_wall} ordered wall less "
                    f"the {mill_tolerance_fraction:.1%} mill under-tolerance"
                    + ("" if corrosion_allowance is None else f" and {corrosion_allowance}")
                ),
                value=Quantity(magnitude=available, unit="mm"),
                unit="mm",
            ),
            SymbolValue(
                symbol="S",
                description=f"B31.3 allowable stress at {allowable.temperature}",
                value=allowable.value,
                unit="MPa",
            ),
            SymbolValue(
                symbol="E",
                description="longitudinal weld joint quality factor",
                value=quality_factor,
            ),
            SymbolValue(
                symbol="D",
                description="pipe outside diameter",
                value=outside_diameter,
                unit="mm",
            ),
            SymbolValue(
                symbol="Y",
                description="material coefficient from Table 304.1.1",
                value=coefficient_y,
            ),
        ),
        result=SymbolValue(
            symbol="P",
            description="pressure the available wall is rated to carry",
            value=rating,
            unit="MPa",
        ),
        citation=_CLAUSE_B313_PRESSURE_DESIGN,
    )
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=1.0).model_copy(
        update={
            "reference": _CLAUSE_B313_PRESSURE_DESIGN,
            "derivation": derivation,
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


# --- ASME VIII Div 1 openings and flanges ------------------------------------
#
# The shell, head and cone screens above answer "is the wall thick enough". A real
# vessel then has holes cut in it and joints bolted to it, and both are governed by
# their own rules. UG-37 is an accounting problem: metal removed for an opening must
# be replaced within a defined zone around it. Appendix 2 is a two-load problem: a
# flange's bolts must both crush the gasket cold and hold the joint under pressure,
# and which of the two governs decides the bolt size.
#
# Sources: ASME BPVC Section VIII Division 1, UG-37 (reinforcement of openings) and
# Mandatory Appendix 2 (rules for bolted flange connections with ring-type gaskets),
# with the gasket factors m and y from Table 2-5.1 supplied by the caller.

_CLAUSE_UG37 = "ASME VIII Div 1 UG-37 (reinforcement of openings)"
_CLAUSE_APPENDIX_2 = "ASME VIII Div 1 Mandatory Appendix 2 (bolted flange connections)"

# Appendix 2 Table 2-5.2: below this basic seating width the effective width IS the
# basic width; above it the effective width grows as the square root instead, because
# a wide gasket does not seat uniformly across its whole face.
_APPENDIX_2_WIDTH_LIMIT_MM = 6.35  # 1/4 inch
_APPENDIX_2_WIDE_COEFFICIENT_MM = 2.52  # b = 2.52*sqrt(b_0) in mm; 0.5*sqrt(b_0) in inches


class NozzleReinforcement(BaseModel):
    """The ASME VIII Div 1 UG-37 opening area accounting: what was removed, and what replaces it.

    ``required`` A is the area the opening removed from the pressure boundary.
    ``shell_excess`` A_1 is the shell metal available beyond what pressure needs,
    ``nozzle_excess`` A_2 the same for the nozzle neck, and ``weld_area`` A_41 the
    attachment fillet. ``available`` is their sum.

    ``adequate`` is available ≥ required. The ``deficit`` is what a reinforcing pad
    would have to supply — the number that actually sizes the pad, which is why it is
    reported rather than left to the reader to subtract.
    """

    model_config = ConfigDict(frozen=True)

    required: Quantity
    shell_excess: Quantity
    nozzle_excess: Quantity
    weld_area: Quantity
    available: Quantity
    adequate: bool
    deficit: Quantity

    def __str__(self) -> str:
        verdict = "adequate" if self.adequate else f"short by {self.deficit}"
        return f"UG-37 reinforcement {verdict}: {self.available} available against {self.required}"


def asme_ug37_nozzle_reinforcement(
    *,
    shell_thickness: Quantity,
    shell_required_thickness: Quantity,
    nozzle_outside_diameter: Quantity,
    nozzle_thickness: Quantity,
    nozzle_required_thickness: Quantity,
    corrosion_allowance: Quantity,
    weld_leg: Quantity,
    strength_reduction_factor: float = 1.0,
) -> NozzleReinforcement:
    """The ASME VIII Div 1 UG-37 reinforcement accounting for a radial opening.

    Cutting a hole in a shell removes pressure-carrying metal, and UG-37 requires it to
    be replaced within a zone around the opening. The required area is A = d·t_r·F,
    where d is the finished opening diameter in the corroded condition and t_r the
    shell's *required* thickness — not its actual one, because only the metal pressure
    needs is what the hole took away.

    The replacement comes from three places here:

    * **A_1, excess shell** — the larger of d·(t − t_r) and 2·(t + t_n)·(t − t_r): the
      shell is usually thicker than pressure demands, and that surplus counts.
    * **A_2, excess nozzle** — the smaller of 5·(t_n − t_rn)·t and 5·(t_n − t_rn)·t_n,
      the neck's own surplus within the reinforcement zone.
    * **A_41, weld** — the attachment fillet, ``weld_leg``².

    ``strength_reduction_factor`` f_r is the nozzle-to-shell allowable stress ratio,
    capped at 1.0, and it appears in four places rather than two: a weaker nozzle
    contributes less to A_2 and A_41, and it also *raises* the required area by
    2·t_n·t_r·(1 − f_r) and lowers A_1 by 2·t_n·(t − t_r)·(1 − f_r), because the nozzle
    wall standing inside the shell no longer carries its share. All four terms collapse
    to the familiar form when f_r = 1, which is the common case of a nozzle in the same
    material — and is why the two extra terms are easy to leave out and worth up to 9.7%
    at f_r = 0.5. The corrosion allowance is stripped from every wall first, because the
    reinforcement has to still be there at the end of life.

    This is the **abutting** nozzle (set-on): f_r1 and f_r2 are taken as the same ratio.

    Two things this deliberately does not do. It does not credit an inward-projecting
    nozzle (A_3) or a reinforcing pad (A_5) — supply those separately if the design has
    them, and add them to ``available``. And it is the *radial-nozzle-in-a-cylinder*
    case: a hillside or an oblique nozzle opens a longer hole and takes UG-37's F factor,
    which is 1.0 only for the radial case this screens.

    Returns a :class:`NozzleReinforcement` naming the deficit, since that is what sizes
    a pad.
    """
    for value, name in (
        (shell_thickness, "shell_thickness"),
        (shell_required_thickness, "shell_required_thickness"),
        (nozzle_outside_diameter, "nozzle_outside_diameter"),
        (nozzle_thickness, "nozzle_thickness"),
        (nozzle_required_thickness, "nozzle_required_thickness"),
        (corrosion_allowance, "corrosion_allowance"),
        (weld_leg, "weld_leg"),
    ):
        _require(value, "[length]", name)
    if not 0 < strength_reduction_factor <= 1.0:
        raise ValueError(
            f"strength_reduction_factor f_r must lie in (0, 1]; got "
            f"{strength_reduction_factor}. It is the nozzle's allowable stress over the "
            f"shell's, and UG-37 caps it at 1 — a stronger nozzle earns no bonus."
        )
    c = corrosion_allowance.to("mm").magnitude
    t = shell_thickness.to("mm").magnitude - c
    tr = shell_required_thickness.to("mm").magnitude
    tn = nozzle_thickness.to("mm").magnitude - c
    trn = nozzle_required_thickness.to("mm").magnitude
    weld = weld_leg.to("mm").magnitude
    if c < 0 or weld < 0:
        raise ValueError("corrosion_allowance and weld_leg must be non-negative")
    if t <= 0 or tn <= 0:
        raise ValueError(
            f"the corrosion allowance ({corrosion_allowance}) consumes the whole shell or "
            f"nozzle wall; there is nothing left to reinforce with"
        )
    if tr <= 0 or trn < 0:
        raise ValueError("shell_required_thickness must be positive and the nozzle's non-negative")
    # The finished opening in the corroded condition: the neck's bore, both walls gone.
    d = nozzle_outside_diameter.to("mm").magnitude - 2.0 * tn
    if d <= 0:
        raise ValueError(
            f"the nozzle wall consumes the whole opening (bore {d:.4g} mm); check "
            f"nozzle_outside_diameter against nozzle_thickness"
        )
    if t < tr:
        raise ValueError(
            f"the corroded shell ({t:.4g} mm) is thinner than pressure requires "
            f"({tr:.4g} mm), so the shell fails before the opening is reached — there is "
            f"no reinforcement question to answer yet"
        )

    # Fig. UG-37.1 in full: the required area carries a second term for the nozzle wall
    # inside the shell, and A_1 subtracts the same wall from the credit. Both are scaled
    # by (1 - f_r1), so both vanish when the nozzle is the same material as the shell —
    # which is why dropping them looked right on the common case and ran up to 9.7%
    # unconservative at f_r = 0.5.
    weaker = 1.0 - strength_reduction_factor
    required = d * tr + 2.0 * tn * tr * weaker
    shell_credit = 2.0 * tn * (t - tr) * weaker
    shell_excess = max(d * (t - tr) - shell_credit, 2.0 * (t + tn) * (t - tr) - shell_credit)
    nozzle_surplus = max(tn - trn, 0.0) * strength_reduction_factor
    nozzle_excess = 5.0 * nozzle_surplus * min(t, tn)
    weld_area = weld**2 * strength_reduction_factor
    available = shell_excess + nozzle_excess + weld_area
    return NozzleReinforcement(
        required=Quantity(magnitude=required, unit="mm**2"),
        shell_excess=Quantity(magnitude=shell_excess, unit="mm**2"),
        nozzle_excess=Quantity(magnitude=nozzle_excess, unit="mm**2"),
        weld_area=Quantity(magnitude=weld_area, unit="mm**2"),
        available=Quantity(magnitude=available, unit="mm**2"),
        adequate=available >= required,
        deficit=Quantity(magnitude=max(required - available, 0.0), unit="mm**2"),
    )


def asme_ug37_reinforcement_scorecard(
    name: str,
    *,
    reinforcement: NozzleReinforcement | None,
    required: float = 1.0,
    missing: str = "",
) -> ScorecardEntry:
    """Screen an ASME VIII Div 1 UG-37 area accounting into a :class:`ScorecardEntry`.

    The safety factor is available area over required area, judged against ``required``
    (1.0 = exactly UG-37's rule, which carries no margin of its own). The detail names
    the deficit when there is one, because that is the pad the design needs.

    ``reinforcement`` of ``None`` is ``NOT_EVALUATED``: an opening whose required shell
    thickness was never computed has not been screened, and ``missing`` says so.
    """
    if reinforcement is not None and not isinstance(reinforcement, NozzleReinforcement):
        raise ValueError(f"reinforcement must be a NozzleReinforcement; got {reinforcement!r}")
    if reinforcement is None:
        detail = "not evaluated"
        if missing.strip():
            detail = f"{detail} — {missing.strip()}"
        else:
            detail = f"{detail} — the UG-37 area accounting could not be run"
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_UG37,
        )
    have = reinforcement.available.to("mm**2").magnitude
    need = reinforcement.required.to("mm**2").magnitude
    computed = None if need == 0 else have / need
    entry = ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
    detail = (
        f"{have:.4g} mm² available against {need:.4g} mm² required "
        f"(shell {reinforcement.shell_excess.magnitude:.4g}, nozzle "
        f"{reinforcement.nozzle_excess.magnitude:.4g}, weld "
        f"{reinforcement.weld_area.magnitude:.4g})"
    )
    if not reinforcement.adequate:
        detail = (
            f"{detail}; short by {reinforcement.deficit.magnitude:.4g} mm², which is the "
            f"area a reinforcing pad has to supply"
        )
    derivation = Derivation(
        symbolic="A_avail = A_1 + A_2 + A_41",
        inputs=(
            SymbolValue(
                symbol="A_1",
                description="shell's excess thickness available as reinforcement",
                value=reinforcement.shell_excess,
                unit="mm**2",
            ),
            SymbolValue(
                symbol="A_2",
                description="nozzle wall's excess thickness inside the limits",
                value=reinforcement.nozzle_excess,
                unit="mm**2",
            ),
            SymbolValue(
                symbol="A_41",
                description="outward nozzle fillet weld metal",
                value=reinforcement.weld_area,
                unit="mm**2",
            ),
        ),
        result=SymbolValue(
            symbol="A_avail",
            description=(
                f"reinforcement available against the {need:.4g} mm² UG-37 requires "
                f"(A = d · t_r · F + 2 · t_n · t_r · F · (1 − f_r1))"
            ),
            value=reinforcement.available,
            unit="mm**2",
        ),
        citation=_CLAUSE_UG37,
    )
    return entry.model_copy(
        update={"detail": detail, "reference": _CLAUSE_UG37, "derivation": derivation}
    )


class FlangeGasketGeometry(BaseModel):
    """The Appendix 2 gasket geometry the bolt-load formulas actually run on.

    ``basic_width`` b_0 and ``effective_width`` b are not the same thing, and the
    difference is the part that gets fumbled: a *wide* gasket does not seat uniformly
    across its face, so above a basic width of 6.35 mm the effective width stops growing
    linearly and goes as 2.52·√b_0 instead. ``diameter`` G moves with it — it is the
    gasket's mean diameter for a narrow gasket, but the OD less 2b for a wide one,
    because the seating load has migrated to the outer edge.

    Getting either wrong scales the bolt load directly, and both are silent errors: the
    numbers stay plausible.
    """

    model_config = ConfigDict(frozen=True)

    basic_width: Quantity
    effective_width: Quantity
    diameter: Quantity
    is_wide: bool


def asme_appendix_2_gasket_geometry(
    *, contact_width: Quantity, outside_diameter: Quantity
) -> FlangeGasketGeometry:
    """The Appendix 2 effective seating width b and diameter G of a flat ring gasket.

    For the flat-face, sheet-gasket column of Table 2-5.2 the basic seating width is
    b_0 = N/2, half the gasket's ``contact_width``. Then:

    * **b_0 ≤ 6.35 mm (¼ in)** — b = b_0, and G is the gasket's *mean* diameter
      (OD − N), because a narrow gasket seats evenly across its face.
    * **b_0 > 6.35 mm** — b = 2.52·√b_0 (in mm; the Code writes 0.5·√b_0 in inches), and
      G = OD − 2b. A wide gasket seats hardest near its outer edge, so the effective
      width grows only as the square root and the load acts further out.

    That discontinuity is deliberate in the Code and it bites: a gasket a millimetre
    wider than the limit does not give a proportionally larger b, and using b_0 above the
    limit overstates both the seating and the operating bolt load.

    Feed the results to :func:`~anvilate.analysis.gasket_seating_load` and
    :func:`~anvilate.analysis.gasket_operating_load`, then to
    :func:`asme_appendix_2_required_bolt_area` — **not** to
    :func:`~anvilate.analysis.governing_gasket_bolt_load`. That one takes the larger of
    the two loads with no allowables, which is only equivalent when the ambient and
    design-temperature bolt allowables are equal. On a hot joint (S_a = 172 MPa,
    S_b = 60 MPa) the load-max names seating as governing and gives a bolt area **36%
    below** what Appendix 2 requires, because the operating load is carried against a
    derated allowable the load comparison never sees.

    Returns a :class:`FlangeGasketGeometry` with all three lengths and which branch
    applied.
    """
    _require(contact_width, "[length]", "contact_width")
    _require(outside_diameter, "[length]", "outside_diameter")
    n = contact_width.to("mm").magnitude
    od = outside_diameter.to("mm").magnitude
    if n <= 0 or od <= 0:
        raise ValueError("contact_width and outside_diameter must be positive")
    if n >= od / 2.0:
        raise ValueError(
            f"a contact width of {contact_width} leaves no bore inside an outside "
            f"diameter of {outside_diameter}; check they are not swapped"
        )
    b0 = n / 2.0
    if b0 <= _APPENDIX_2_WIDTH_LIMIT_MM:
        b = b0
        g = od - n  # the mean diameter
        wide = False
    else:
        b = _APPENDIX_2_WIDE_COEFFICIENT_MM * sqrt(b0)
        g = od - 2.0 * b
        wide = True
    return FlangeGasketGeometry(
        basic_width=Quantity(magnitude=b0, unit="mm"),
        effective_width=Quantity(magnitude=b, unit="mm"),
        diameter=Quantity(magnitude=g, unit="mm"),
        is_wide=wide,
    )


def asme_appendix_2_required_bolt_area(
    *,
    operating_bolt_load: Quantity,
    seating_bolt_load: Quantity,
    operating_allowable: Quantity,
    seating_allowable: Quantity,
) -> Quantity:
    """The Appendix 2 required bolt area A_m = max(W_m1/S_b, W_m2/S_a), in mm².

    The two conditions are checked against *different* allowables and neither result
    substitutes for the other: the operating load W_m1 is carried at design temperature
    against S_b, while the seating load W_m2 is applied cold against the ambient
    allowable S_a. A hot joint can be seating-governed purely because its hot allowable
    has fallen away, which is invisible if both loads are divided by one number.

    ``operating_bolt_load`` and ``seating_bolt_load`` come from
    :func:`~anvilate.analysis.gasket_operating_load` and
    :func:`~anvilate.analysis.gasket_seating_load` on the geometry
    :func:`asme_appendix_2_gasket_geometry` returns. Returns the required total bolt
    root area; compare it against the area the chosen bolt count and size actually
    provide.
    """
    for value, name in (
        (operating_bolt_load, "operating_bolt_load"),
        (seating_bolt_load, "seating_bolt_load"),
    ):
        _require(value, "[force]", name)
        if value.magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    for value, name in (
        (operating_allowable, "operating_allowable"),
        (seating_allowable, "seating_allowable"),
    ):
        _require(value, "[pressure]", name)
        if value.magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    operating = operating_bolt_load.to("N").magnitude / operating_allowable.to("MPa").magnitude
    seating = seating_bolt_load.to("N").magnitude / seating_allowable.to("MPa").magnitude
    return Quantity(magnitude=max(operating, seating), unit="mm**2")


class FlangeShapeFactors(BaseModel):
    """The Appendix 2 shape factors T, U, Y and Z — functions of K = A/B and nothing else.

    Every one of them is a pure function of the flange's outside-to-inside diameter
    ratio, so a flange's *proportions* fix them before any load is known. ``y_factor``
    is the one a ring flange's stress runs on; ``t_factor``, ``u_factor`` and
    ``z_factor`` belong to the hub-flange equations this module does not implement, and
    are reported because they are free and because a reader checking against the Code's
    Table 2-7.1 will look for all four.

    Y rises steeply as K approaches 1: a thin ring is a flexible ring, and the same
    moment on it produces far more stress. That is real behaviour, not a numerical
    artefact — but it means a flange whose outside diameter is barely larger than its
    bore is governed by its proportions, not its thickness.
    """

    model_config = ConfigDict(frozen=True)

    ratio: float
    t_factor: float
    u_factor: float
    y_factor: float
    z_factor: float

    def __str__(self) -> str:
        return (
            f"Appendix 2 shape factors at K={self.ratio:.4g}: "
            f"T={self.t_factor:.4g}, U={self.u_factor:.4g}, "
            f"Y={self.y_factor:.4g}, Z={self.z_factor:.4g}"
        )


def asme_appendix_2_shape_factors(
    *, outside_diameter: Quantity, inside_diameter: Quantity
) -> FlangeShapeFactors:
    """The Appendix 2 flange shape factors T, U, Y, Z for the diameter ratio K = A/B.

    These are the closed-form equations of Appendix 2-7.1, not the F/V/f *curves* of
    Figures 2-7.2 through 2-7.6. That distinction is the whole reason this function
    exists and the hub-stress functions do not: T, U, Y and Z are published algebra and
    can be reproduced exactly, while F, V and f are digitised figures that would have to
    be guessed at.

        Z = (K² + 1) / (K² − 1)
        Y = [0.66845 + 5.71690·K²·log₁₀K/(K² − 1)] / (K − 1)
        T = [K²·(1 + 8.55246·log₁₀K) − 1] / [(1.04720 + 1.9448·K²)·(K − 1)]
        U = [K²·(1 + 8.55246·log₁₀K) − 1] / [1.36136·(K² − 1)·(K − 1)]

    **Anchored, not recalled.** A published worked calculation (a 19 in bore, 26.9685 in
    OD integral flange, K = 1.41939) reports T = 1.74578 and Z = 2.97106; these
    equations give 1.745783 and 2.971062, agreeing to 2×10⁻⁶ relative — both round to
    the published five-figure values exactly. Y and U are tied to
    each other by an identity that falls out of the constants — U = Y/0.910 to five
    figures at every K — so reproducing one reproduces the other. The suite asserts all
    of it.

    ``outside_diameter`` A is the flange OD and ``inside_diameter`` B its bore; A must
    exceed B. Returns a :class:`FlangeShapeFactors`.
    """
    _require(outside_diameter, "[length]", "outside_diameter")
    _require(inside_diameter, "[length]", "inside_diameter")
    a = outside_diameter.to("mm").magnitude
    b = inside_diameter.to("mm").magnitude
    if b <= 0:
        raise ValueError(f"inside_diameter must be positive; got {inside_diameter}")
    if a <= b:
        raise ValueError(
            f"outside_diameter {outside_diameter} must exceed inside_diameter "
            f"{inside_diameter}; K = A/B must be greater than 1"
        )
    k = a / b
    k2 = k * k
    log_k = log10(k)
    hub_numerator = k2 * (1.0 + 8.55246 * log_k) - 1.0
    return FlangeShapeFactors(
        ratio=k,
        t_factor=hub_numerator / ((1.04720 + 1.9448 * k2) * (k - 1.0)),
        u_factor=hub_numerator / (1.36136 * (k2 - 1.0) * (k - 1.0)),
        y_factor=(0.66845 + 5.71690 * k2 * log_k / (k2 - 1.0)) / (k - 1.0),
        z_factor=(k2 + 1.0) / (k2 - 1.0),
    )


class FlangeMoments(BaseModel):
    """The Appendix 2 flange moments, with every load and lever arm that built them.

    The operating moment is three loads on three different lever arms about the bolt
    circle, and they do not move together: ``end_force`` H_D acts at the bore,
    ``face_force`` H_T on the annulus between the bore and the gasket reaction, and
    ``gasket_force`` H_G out at the gasket. Pulling the bolt circle in toward the gasket
    shortens h_G and lengthens nothing, which is why the Code recommends keeping h_G
    small — and why the components are reported rather than only their sum.

    ``seating_moment`` is a different loading entirely: the full bolt-up load W on the
    gasket arm alone, cold, with no pressure anywhere in it. Neither moment substitutes
    for the other and the flange has to survive both against their own allowables.
    """

    model_config = ConfigDict(frozen=True)

    end_force: Quantity
    total_end_force: Quantity
    face_force: Quantity
    gasket_force: Quantity
    end_arm: Quantity
    face_arm: Quantity
    gasket_arm: Quantity
    operating_moment: Quantity
    seating_moment: Quantity

    def __str__(self) -> str:
        return (
            f"Appendix 2 flange moments: operating {self.operating_moment}, "
            f"seating {self.seating_moment}"
        )


def asme_appendix_2_flange_moments(
    *,
    inside_diameter: Quantity,
    bolt_circle_diameter: Quantity,
    gasket_diameter: Quantity,
    pressure: Quantity,
    operating_bolt_load: Quantity,
    seating_bolt_load: Quantity,
) -> FlangeMoments:
    """The Appendix 2 operating and seating moments of a **loose-type** flange.

    The three operating loads are H_D = 0.785·B²·P at the bore, the total end force
    H = 0.785·G²·P at the gasket reaction diameter, the annulus force H_T = H − H_D, and
    the residual gasket load H_G = W_m1 − H. Their lever arms about the bolt circle C
    are the **loose-type** row of Table 2-6:

        h_D = (C − B)/2,  h_G = (C − G)/2,  h_T = (h_D + h_G)/2

    and M_o = H_D·h_D + H_T·h_T + H_G·h_G. The seating moment is M_a = W·h_G.

    **The moment arms are type-specific and this function only knows one type.** An
    integral or optional-type flange takes h_D = R + g₁/2 and h_T = (R + g₁ + h_G)/2 off
    the hub, which are different numbers; using these arms on a welding-neck flange
    understates the moment. See :func:`asme_appendix_2_ring_flange_stress` for the
    matching stress equation and the same restriction.

    ``operating_bolt_load`` W_m1 comes from
    :func:`~anvilate.analysis.gasket_operating_load`. ``seating_bolt_load`` W is the
    flange *design* bolt load for gasket seating, W = (A_m + A_b)·S_a/2 — the mean of
    the required and actual bolt areas against the ambient allowable, **not** the gasket
    seating load W_m2 on its own. The Code deliberately charges the flange for the
    over-bolting a fitter can apply at assembly, so passing W_m2 here understates the
    seating moment whenever the chosen bolts exceed the required area, which they
    essentially always do.

    Diameters must satisfy C > G > B. Returns a :class:`FlangeMoments`.
    """
    _require(pressure, "[pressure]", "pressure")
    if pressure.magnitude <= 0:
        raise ValueError(f"pressure must be positive; got {pressure}")
    lengths = {}
    for value, name in (
        (inside_diameter, "inside_diameter"),
        (bolt_circle_diameter, "bolt_circle_diameter"),
        (gasket_diameter, "gasket_diameter"),
    ):
        _require(value, "[length]", name)
        magnitude = value.to("mm").magnitude
        if magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
        lengths[name] = magnitude
    for value, name in (
        (operating_bolt_load, "operating_bolt_load"),
        (seating_bolt_load, "seating_bolt_load"),
    ):
        _require(value, "[force]", name)
        if value.magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    b = lengths["inside_diameter"]
    c = lengths["bolt_circle_diameter"]
    g = lengths["gasket_diameter"]
    if not b < g < c:
        raise ValueError(
            f"the diameters must nest as bore < gasket reaction < bolt circle; got "
            f"B={inside_diameter}, G={gasket_diameter}, C={bolt_circle_diameter}"
        )
    p = pressure.to("MPa").magnitude
    w_m1 = operating_bolt_load.to("N").magnitude
    w_seat = seating_bolt_load.to("N").magnitude
    h_d = 0.785 * b * b * p
    h_total = 0.785 * g * g * p
    if w_m1 <= h_total:
        raise ValueError(
            f"operating_bolt_load {operating_bolt_load} does not exceed the hydrostatic "
            f"end force {h_total:.4g} N, so no gasket load survives pressurisation; it "
            f"should be W_m1 from gasket_operating_load, which includes that end force"
        )
    h_t = h_total - h_d
    h_g = w_m1 - h_total
    arm_d = (c - b) / 2.0
    arm_g = (c - g) / 2.0
    arm_t = (arm_d + arm_g) / 2.0
    return FlangeMoments(
        end_force=Quantity(magnitude=h_d, unit="N"),
        total_end_force=Quantity(magnitude=h_total, unit="N"),
        face_force=Quantity(magnitude=h_t, unit="N"),
        gasket_force=Quantity(magnitude=h_g, unit="N"),
        end_arm=Quantity(magnitude=arm_d, unit="mm"),
        face_arm=Quantity(magnitude=arm_t, unit="mm"),
        gasket_arm=Quantity(magnitude=arm_g, unit="mm"),
        operating_moment=Quantity(magnitude=h_d * arm_d + h_t * arm_t + h_g * arm_g, unit="N*mm"),
        seating_moment=Quantity(magnitude=w_seat * arm_g, unit="N*mm"),
    )


class LooseRingFlangeStress(BaseModel):
    """The Appendix 2 tangential stress in a loose ring flange, in both conditions.

    For a loose-type flange with no hub the longitudinal hub stress S_H and the radial
    stress S_R are both zero by definition, and the single tangential stress
    S_T = Y·M_o/(t²·B) is the whole check. That is why this case can be shipped and the
    hub cases cannot.

    ``governing_condition`` names which of operating and seating produced the lower
    safety factor, and it is genuinely not always operating: a cold bolt-up on a
    generously bolted joint can out-moment the pressurised condition, and it is checked
    against the *ambient* allowable, which is the higher of the two. Both stresses are
    reported so the loser is visible.
    """

    model_config = ConfigDict(frozen=True)

    shape_factors: FlangeShapeFactors
    operating_stress: Quantity
    seating_stress: Quantity
    operating_safety_factor: float
    seating_safety_factor: float
    governing_condition: str
    safety_factor: float
    adequate: bool
    # The three quantities S_T = Y·M_o/(t²·B) is built from, beside the shape factor that
    # was already here. Without them the scorecard could name the clause and print the
    # answer and had nothing to put between the two: the flange check reported a stress
    # with the moment that made it nowhere on the card.
    governing_moment: Quantity
    thickness: Quantity
    inside_diameter: Quantity

    def derivation(self, citation: str) -> Derivation:
        """S_T for the governing condition, worked, under the caller's clause.

        The *governing* moment rather than both: the entry's verdict rests on one of the
        two conditions, and showing the arithmetic of the other beside it invites a reader
        to check the number that did not decide anything. Which condition it is already
        appears in the entry's detail line and in the result gloss here.
        """
        stress = (
            self.operating_stress
            if self.governing_condition == "operating"
            else self.seating_stress
        )
        return Derivation(
            symbolic="S_T = Y·M_o/(t²·B)",
            inputs=(
                SymbolValue(
                    symbol="Y",
                    description=(
                        f"Appendix 2 shape factor at K = {self.shape_factors.ratio:.4g}, "
                        "the flange outside/inside diameter ratio"
                    ),
                    value=self.shape_factors.y_factor,
                ),
                SymbolValue(
                    symbol="M_o",
                    description=f"flange moment in the {self.governing_condition} condition",
                    value=self.governing_moment,
                    unit="N*mm",
                ),
                SymbolValue(symbol="t", description="flange ring thickness", value=self.thickness),
                SymbolValue(
                    symbol="B", description="flange inside diameter", value=self.inside_diameter
                ),
            ),
            result=SymbolValue(
                symbol="S_T",
                description=f"tangential flange stress, {self.governing_condition} condition",
                value=stress,
            ),
            citation=citation,
        )

    def __str__(self) -> str:
        verdict = "adequate" if self.adequate else "overstressed"
        return (
            f"Appendix 2 ring flange {verdict}: {self.governing_condition} governs at "
            f"SF {self.safety_factor:.3g}"
        )


def asme_appendix_2_ring_flange_stress(
    *,
    outside_diameter: Quantity,
    inside_diameter: Quantity,
    thickness: Quantity,
    moments: FlangeMoments,
    operating_allowable: Quantity,
    seating_allowable: Quantity,
) -> LooseRingFlangeStress:
    """The Appendix 2 tangential stress S_T = Y·M/(t²·B) of a **loose ring flange**.

    **Scope, stated up front because getting it wrong is silent.** This is Appendix
    2-7(b): loose-type flanges *without* hubs, and loose or optional-type flanges the
    designer chooses to calculate without crediting a hub (Figure 2-4 sketches 1, 1a, 2,
    2a, 3, 3a, 4, 4a, 4b, 4c and the optional sketches taken as loose). For those,
    S_H = 0 and S_R = 0 and S_T alone is the check. A **welding-neck or any
    hub-credited flange is not covered**: its S_T carries a −Z·S_R term and its hub
    stress S_H usually governs, both of which need the F, V and f *figures* of Appendix
    2. Running a hub flange through here reports the no-hub number, which is
    unconservative — the moment arms are wrong too, per
    :func:`asme_appendix_2_flange_moments`.

    Both conditions are screened, each against its own allowable: the operating moment
    against the flange material's allowable at design temperature, the seating moment
    against its allowable at ambient. The governing condition is whichever gives the
    lower safety factor, which is not decided by the moments alone — the two allowables
    differ, often by a lot, on a hot joint.

    Also out of scope: the bolt-spacing correction factor B_sc, which multiplies M_o
    when actual bolt spacing exceeds 2a + t, and the Appendix 2 rigidity index. Both are
    separate criteria a flange can fail while its stresses pass.

    Returns a :class:`LooseRingFlangeStress`; ``adequate`` is a safety factor of at
    least 1.0 in *both* conditions.
    """
    _require(thickness, "[length]", "thickness")
    t = thickness.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    for value, name in (
        (operating_allowable, "operating_allowable"),
        (seating_allowable, "seating_allowable"),
    ):
        _require(value, "[pressure]", name)
        if value.magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    factors = asme_appendix_2_shape_factors(
        outside_diameter=outside_diameter, inside_diameter=inside_diameter
    )
    b = inside_diameter.to("mm").magnitude
    denominator = t * t * b
    operating = factors.y_factor * moments.operating_moment.to("N*mm").magnitude / denominator
    seating = factors.y_factor * moments.seating_moment.to("N*mm").magnitude / denominator
    operating_sf = operating_allowable.to("MPa").magnitude / operating
    seating_sf = seating_allowable.to("MPa").magnitude / seating
    if seating_sf < operating_sf:
        condition, governing = "seating", seating_sf
    else:
        condition, governing = "operating", operating_sf
    return LooseRingFlangeStress(
        shape_factors=factors,
        operating_stress=Quantity(magnitude=operating, unit="MPa"),
        seating_stress=Quantity(magnitude=seating, unit="MPa"),
        operating_safety_factor=operating_sf,
        seating_safety_factor=seating_sf,
        governing_condition=condition,
        safety_factor=governing,
        adequate=governing >= 1.0,
        governing_moment=(
            moments.seating_moment if condition == "seating" else moments.operating_moment
        ),
        thickness=thickness,
        inside_diameter=inside_diameter,
    )


def asme_appendix_2_flange_stress_scorecard(
    name: str,
    *,
    stress: LooseRingFlangeStress | None,
    required: float = 1.0,
    missing: str = "",
) -> ScorecardEntry:
    """Screen an Appendix 2 ring-flange stress into a :class:`ScorecardEntry`.

    The safety factor is the governing one of the two conditions — allowable over
    S_T — judged against ``required`` (1.0 is exactly the Code's limit, which carries
    no margin of its own). The detail names which condition governed and reports both
    stresses, because a flange that passes operating and fails seating is a bolt-up
    problem, not a pressure problem, and the two have different fixes.

    ``stress`` of ``None`` is ``NOT_EVALUATED``, which is the honest answer for a
    hub-credited flange: this module cannot screen one, and ``missing`` should say so
    rather than leaving a reader to read the blank as a pass.
    """
    if stress is not None and not isinstance(stress, LooseRingFlangeStress):
        raise ValueError(f"stress must be a LooseRingFlangeStress; got {stress!r}")
    if stress is None:
        detail = "not evaluated"
        if missing.strip():
            detail = f"{detail} — {missing.strip()}"
        else:
            detail = f"{detail} — the Appendix 2 flange stress could not be run"
        return ScorecardEntry(
            name=name,
            status=CheckStatus.NOT_EVALUATED,
            detail=detail,
            reference=_CLAUSE_APPENDIX_2,
        )
    entry = ScorecardEntry.from_safety_factor(
        name, computed=stress.safety_factor, required=required
    )
    detail = (
        f"{stress.governing_condition} governs: S_T "
        f"{stress.operating_stress.magnitude:.4g} MPa operating and "
        f"{stress.seating_stress.magnitude:.4g} MPa seating, at "
        f"Y={stress.shape_factors.y_factor:.4g} (K="
        f"{stress.shape_factors.ratio:.4g})"
    )
    return entry.model_copy(
        update={
            "detail": detail,
            "reference": _CLAUSE_APPENDIX_2,
            "derivation": stress.derivation(_CLAUSE_APPENDIX_2),
        }
    )
