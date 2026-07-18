"""T1 stress-combination utilities (von Mises equivalent stress).

The individual checks in this package report component stresses — a bending
stress from a beam, a shear stress from a shaft. A ductile part yields on the
*combined* state, so those components are rolled into a single von Mises
equivalent stress before comparing to the yield strength:

    plane stress:      σ_vm = √(σx² − σx·σy + σy² + 3·τxy²)
    bending + torsion: σ_vm = √(σ² + 3·τ²)   (the common shaft case)
    triaxial:          σ_vm = √(½·[(σ₁−σ₂)² + (σ₂−σ₃)² + (σ₃−σ₁)²])

The triaxial form takes three principal stresses directly — e.g. the
hoop/radial/longitudinal triad at a thick-wall vessel bore. Inputs and outputs
are dimension-checked :class:`~anvilate.units.Quantity` stresses; a helper
returns the factor of safety against yield.
"""

from __future__ import annotations

from math import atan2, degrees, sqrt

from pydantic import BaseModel, ConfigDict

from ..scorecard import ScorecardEntry
from ..units import Quantity

__all__ = [
    "von_mises_plane_stress",
    "von_mises_bending_torsion",
    "von_mises_principal",
    "octahedral_shear_stress",
    "principal_stresses_plane",
    "principal_angle_plane",
    "max_shear_stress_plane",
    "tresca_equivalent_stress",
    "tresca_principal",
    "yield_safety_factor",
    "strength_scorecard",
    "CombinedNormalStress",
    "combine_axial_bending",
    "concentrated_stress",
    "elliptical_hole_stress_concentration",
]


def _require_stress(value: Quantity, name: str) -> float:
    if not value.has_dimension("[pressure]"):
        raise ValueError(
            f"{name} must be a [pressure] quantity; got {value.dimensionality} ({value})"
        )
    return value.to("MPa").magnitude


class CombinedNormalStress(BaseModel):
    """The extreme-fibre normal stresses of combined axial + bending loading.

    ``tension_fibre`` is the axial stress plus the bending stress (the most
    tensile fibre); ``compression_fibre`` is the axial minus the bending (the most
    compressive). ``peak_magnitude`` is the larger of the two in magnitude — the
    stress that governs a yield check.
    """

    model_config = ConfigDict(frozen=True)

    tension_fibre: Quantity
    compression_fibre: Quantity

    @property
    def peak_magnitude(self) -> Quantity:
        t = abs(self.tension_fibre.to("MPa").magnitude)
        c = abs(self.compression_fibre.to("MPa").magnitude)
        return Quantity(magnitude=max(t, c), unit="MPa")

    def __str__(self) -> str:
        return (
            f"combined: tension fibre {self.tension_fibre.to('MPa')}, "
            f"compression fibre {self.compression_fibre.to('MPa')}"
        )


def combine_axial_bending(
    *,
    axial_stress: Quantity,
    bending_stress: Quantity,
) -> CombinedNormalStress:
    """Superpose a uniform ``axial_stress`` and a ``bending_stress`` on a section.

    Bending puts one fibre in tension and the opposite in compression; the axial
    stress shifts both. Returns the two extreme-fibre stresses (axial ± |bending|)
    — the governing normal stresses for an eccentrically-loaded member or a
    beam-column. Both inputs must be stresses; a signed ``axial_stress`` (negative
    for compression) carries through.
    """
    a = _require_stress(axial_stress, "axial_stress")
    b = abs(_require_stress(bending_stress, "bending_stress"))
    return CombinedNormalStress(
        tension_fibre=Quantity(magnitude=a + b, unit="MPa"),
        compression_fibre=Quantity(magnitude=a - b, unit="MPa"),
    )


def concentrated_stress(*, nominal_stress: Quantity, kt: float) -> Quantity:
    """The peak local stress σ_max = K_t·σ_nom at a geometric stress raiser.

    A fillet, hole, groove, or notch amplifies the nominal (net-section) stress by
    the geometric stress-concentration factor ``kt`` (read from a Peterson/Roark
    chart for the feature — those charts are not bundled). ``nominal_stress`` must
    be a stress and ``kt`` at least 1 (a raiser never reduces stress). Returns the
    peak stress in MPa.
    """
    sigma = _require_stress(nominal_stress, "nominal_stress")
    if kt < 1:
        raise ValueError(f"kt must be at least 1 (a stress raiser); got {kt}")
    return Quantity(magnitude=kt * sigma, unit="MPa")


def elliptical_hole_stress_concentration(
    *, semi_axis_across_load: Quantity, semi_axis_along_load: Quantity
) -> float:
    """The Inglis stress-concentration factor K_t = 1 + 2·a/b of an elliptical hole.

    An elliptical hole in a wide plate under uniaxial tension concentrates the
    stress at the ends of the axis across the load. Inglis's exact solution gives
    K_t = 1 + 2·a/b, where ``semi_axis_across_load`` a is the semi-axis
    perpendicular to the load (the one that raises the stress) and
    ``semi_axis_along_load`` b the semi-axis parallel to it. A circular hole (a = b)
    gives the familiar K_t = 3; a hole stretched across the load raises it without
    limit, so a crack-like slit (b → 0) is why sharp flaws are so dangerous. Feed
    the result to :func:`concentrated_stress`. Both semi-axes are positive lengths.
    Returns the dimensionless K_t (≥ 3, and = 3 only for a circular hole).
    """
    if not semi_axis_across_load.has_dimension("[length]"):
        raise ValueError(
            f"semi_axis_across_load must be a [length] quantity; got {semi_axis_across_load}"
        )
    if not semi_axis_along_load.has_dimension("[length]"):
        raise ValueError(
            f"semi_axis_along_load must be a [length] quantity; got {semi_axis_along_load}"
        )
    a = semi_axis_across_load.to("mm").magnitude
    b = semi_axis_along_load.to("mm").magnitude
    if a <= 0:
        raise ValueError(f"semi_axis_across_load must be positive; got {semi_axis_across_load}")
    if b <= 0:
        raise ValueError(f"semi_axis_along_load must be positive; got {semi_axis_along_load}")
    return 1.0 + 2.0 * a / b


def von_mises_plane_stress(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for a 2D plane-stress state.

    σ_vm = √(σx² − σx·σy + σy² + 3·τxy²). All three components must be stresses
    (pressure). Returns the equivalent stress in MPa.
    """
    sx = _require_stress(sigma_x, "sigma_x")
    sy = _require_stress(sigma_y, "sigma_y")
    txy = _require_stress(tau_xy, "tau_xy")
    vm = sqrt(sx * sx - sx * sy + sy * sy + 3 * txy * txy)
    return Quantity(magnitude=vm, unit="MPa")


def principal_stresses_plane(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> tuple[Quantity, Quantity]:
    """The two in-plane principal stresses of a plane-stress state.

    σ₁,₂ = (σx+σy)/2 ± √(((σx−σy)/2)² + τxy²). Returns ``(σ₁, σ₂)`` with σ₁ ≥ σ₂,
    both in MPa. The out-of-plane principal is zero for plane stress.
    """
    sx = _require_stress(sigma_x, "sigma_x")
    sy = _require_stress(sigma_y, "sigma_y")
    txy = _require_stress(tau_xy, "tau_xy")
    centre = (sx + sy) / 2
    radius = sqrt(((sx - sy) / 2) ** 2 + txy * txy)
    return (
        Quantity(magnitude=centre + radius, unit="MPa"),
        Quantity(magnitude=centre - radius, unit="MPa"),
    )


def principal_angle_plane(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The orientation of the major principal stress in a plane-stress state.

    The principal stresses (:func:`principal_stresses_plane`) act on planes rotated
    from the x-axis by θ_p = ½·atan2(2·τxy, σx − σy) — the angle at which the shear
    stress vanishes and the *major* principal σ₁ acts. This is what turns a
    strain-gauge rosette or a combined-loading state into a physical direction, and it
    locates the plane a brittle crack opens on. ``sigma_x`` σx, ``sigma_y`` σy, and
    ``tau_xy`` τxy are the plane-stress components; the maximum-shear planes lie at
    θ_p ± 45°. The quadrant-aware atan2 returns θ_p in (−90°, 90°] — for pure shear
    it is 45°, for a uniaxial σx it is 0°. Returns the angle in degrees.
    """
    sx = _require_stress(sigma_x, "sigma_x")
    sy = _require_stress(sigma_y, "sigma_y")
    txy = _require_stress(tau_xy, "tau_xy")
    return Quantity(magnitude=0.5 * degrees(atan2(2.0 * txy, sx - sy)), unit="degree")


def max_shear_stress_plane(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The maximum shear stress τ_max of a plane-stress state.

    τ_max = (σ_max − σ_min)/2 over the three principal stresses (the two in-plane
    principals and the zero out-of-plane one) — the basis of the Tresca criterion.
    Returns the shear stress in MPa.
    """
    s1, s2 = principal_stresses_plane(sigma_x=sigma_x, sigma_y=sigma_y, tau_xy=tau_xy)
    principals = (s1.to("MPa").magnitude, s2.to("MPa").magnitude, 0.0)
    return Quantity(magnitude=(max(principals) - min(principals)) / 2, unit="MPa")


def tresca_equivalent_stress(
    *,
    sigma_x: Quantity,
    sigma_y: Quantity,
    tau_xy: Quantity,
) -> Quantity:
    """The Tresca (maximum-shear) equivalent stress of a plane-stress state.

    σ_tresca = σ_max − σ_min over the three principal stresses (out-of-plane = 0),
    i.e. twice :func:`max_shear_stress_plane`. The Tresca criterion is the more
    conservative alternative to von Mises (σ_tresca ≥ σ_vm always), required by
    some pressure-vessel and structural codes. Returns the equivalent stress in MPa.
    """
    tau_max = max_shear_stress_plane(sigma_x=sigma_x, sigma_y=sigma_y, tau_xy=tau_xy)
    return Quantity(magnitude=2 * tau_max.to("MPa").magnitude, unit="MPa")


def von_mises_principal(
    *,
    sigma_1: Quantity,
    sigma_2: Quantity,
    sigma_3: Quantity,
) -> Quantity:
    """The von Mises equivalent stress of a general triaxial principal state.

    σ_vm = √(½·[(σ₁−σ₂)² + (σ₂−σ₃)² + (σ₃−σ₁)²]) for the three principal stresses,
    which need not be ordered. Unlike :func:`von_mises_plane_stress` this takes a
    fully three-dimensional state, so it accepts the hoop/radial/longitudinal
    triad from a thick-wall :func:`~anvilate.analysis.thick_wall_cylinder` bore
    directly. All three must be stresses. Returns the equivalent stress in MPa.
    """
    s1 = _require_stress(sigma_1, "sigma_1")
    s2 = _require_stress(sigma_2, "sigma_2")
    s3 = _require_stress(sigma_3, "sigma_3")
    vm = sqrt(((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 2)
    return Quantity(magnitude=vm, unit="MPa")


def octahedral_shear_stress(
    *,
    sigma_1: Quantity,
    sigma_2: Quantity,
    sigma_3: Quantity,
) -> Quantity:
    """The octahedral shear stress τ_oct = ⅓·√[(σ₁−σ₂)² + (σ₂−σ₃)² + (σ₃−σ₁)²].

    The shear stress on the octahedral plane (equally inclined to the three
    principal directions), and the physical quantity the distortion-energy yield
    theory is built on: yielding begins when τ_oct reaches √2/3·S_y. It relates to
    the von Mises stress by τ_oct = (√2/3)·σ_vm, so it carries the same information
    as :func:`von_mises_principal` in the shear form some plasticity and
    rock/soil-mechanics workflows use directly. ``sigma_1``, ``sigma_2``, ``sigma_3``
    are the three principal stresses (unordered). Returns the octahedral shear stress
    in MPa.
    """
    s1 = _require_stress(sigma_1, "sigma_1")
    s2 = _require_stress(sigma_2, "sigma_2")
    s3 = _require_stress(sigma_3, "sigma_3")
    tau = sqrt((s1 - s2) ** 2 + (s2 - s3) ** 2 + (s3 - s1) ** 2) / 3.0
    return Quantity(magnitude=tau, unit="MPa")


def tresca_principal(
    *,
    sigma_1: Quantity,
    sigma_2: Quantity,
    sigma_3: Quantity,
) -> Quantity:
    """The Tresca (maximum-shear) equivalent stress of a general triaxial state.

    σ_tresca = σ_max − σ_min over the three principal stresses (unordered) — the
    three-dimensional counterpart of :func:`tresca_equivalent_stress`, and always
    at least the von Mises value. Feeds the same thick-wall bore triad. All three
    must be stresses. Returns the equivalent stress in MPa.
    """
    principals = (
        _require_stress(sigma_1, "sigma_1"),
        _require_stress(sigma_2, "sigma_2"),
        _require_stress(sigma_3, "sigma_3"),
    )
    return Quantity(magnitude=max(principals) - min(principals), unit="MPa")


def von_mises_bending_torsion(
    *,
    bending_stress: Quantity,
    shear_stress: Quantity,
) -> Quantity:
    """The von Mises equivalent stress for the common bending-plus-torsion case.

    σ_vm = √(σ² + 3·τ²), the plane-stress form with a single normal stress
    ``bending_stress`` (σ) and a single shear ``shear_stress`` (τ) — e.g. a shaft
    carrying both a bending moment and a torque. Returns the equivalent stress in
    MPa.
    """
    sigma = _require_stress(bending_stress, "bending_stress")
    tau = _require_stress(shear_stress, "shear_stress")
    vm = sqrt(sigma * sigma + 3 * tau * tau)
    return Quantity(magnitude=vm, unit="MPa")


def yield_safety_factor(equivalent_stress: Quantity, yield_strength: Quantity) -> float:
    """The factor of safety against yielding: yield strength / equivalent stress.

    Both arguments must be stresses. A value below 1 means the part yields.
    """
    sigma = _require_stress(equivalent_stress, "equivalent_stress")
    sy = _require_stress(yield_strength, "yield_strength")
    return sy / sigma


def strength_scorecard(
    name: str,
    *,
    stress: Quantity,
    allowable: Quantity | None,
    required: float,
) -> ScorecardEntry:
    """Screen a computed ``stress`` against a material ``allowable`` strength.

    Builds a :class:`~anvilate.scorecard.ScorecardEntry`: the safety factor is
    ``allowable``/|``stress``| (stress magnitude, so tension and compression are
    treated alike), judged against the ``required`` minimum. When ``allowable`` is
    ``None`` — a material property that is not in the database, such as an
    unlisted endurance limit — the entry is ``NOT_EVALUATED`` rather than a silent
    pass, honouring the No-silent-green rule. ``stress`` (and ``allowable`` when
    given) must be stresses.
    """
    sigma = abs(_require_stress(stress, "stress"))
    if allowable is None:
        computed = None
    else:
        strength = _require_stress(allowable, "allowable")
        computed = float("inf") if sigma == 0 else strength / sigma
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)
