"""T1 analytical bolted/pinned-joint checks (closed-form).

The workhorse relation for a bolted joint is ``T = K·F·d``: the tightening torque
``T`` produces a preload ``F`` in a thread of nominal diameter ``d``, scaled by
the nut factor ``K`` (an empirical coefficient rolling up thread and under-head
friction). It inverts to ``F = T/(K·d)``. Given a fastener's nominal diameter
from the standards tables, those two functions convert between the torque a shop
applies and the preload it develops — a screening estimate, since K varies
widely with lubrication and surface finish.

A separate failure mode is bearing (the fastener crushing the hole it passes
through): ``σ_bearing = F/(d·t)`` over the projected pin-and-plate contact area.

A bolt in tension does not carry its axial load on the nominal shank area but on
the smaller *tensile stress area* through the threads, ``A_t = (π/4)·(d −
0.9382·P)²`` (ISO 898 / Shigley), midway between the pitch- and minor-diameter
areas — so the axial stress is ``σ = F/A_t``, always higher than F over the
nominal area.

As with the beam and column checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values and the arithmetic runs through Pint.
"""

from __future__ import annotations

from math import log, pi, sqrt

from ..units import Quantity
from .fatigue import CyclicStress, cyclic_stress_components

# ISO 898 tensile-stress-area factor: A_t = (pi/4)(d - 0.9382*P)^2, where the
# effective diameter is the mean of the pitch and rounded-root minor diameters.
_TENSILE_AREA_PITCH_FACTOR = 0.9382

# Basic ISO metric (60-degree) thread geometry, all derived from d and P alone.
# Minor diameter of the internal thread, D1 = d - (5/4)*H = d - 1.0825*P, where
# H = (sqrt(3)/2)*P is the height of the fundamental triangle; the bolt threads
# strip on a cylinder at this diameter.
_INTERNAL_MINOR_DIA_FACTOR = 1.0825
# Thread-stripping shear-area coefficients (Alexander / FED-STD-H28, basic
# profile): A_ext = 0.75*pi*D1*Le for the external (bolt) threads, A_int =
# 0.875*pi*d*Le for the internal (nut/tapped-hole) threads. The coefficients are
# 1/2 + tan(30)*(d2 - D1)/P = 0.75 and 1/2 + tan(30)*(d - d2)/P = 0.875, with the
# pitch diameter d2 = d - 0.6495*P; they are exact for the basic profile.
_EXTERNAL_STRIP_COEFFICIENT = 0.75
_INTERNAL_STRIP_COEFFICIENT = 0.875

__all__ = [
    "NUT_FACTOR_AS_RECEIVED",
    "bolt_preload_from_torque",
    "torque_for_preload",
    "bearing_stress",
    "bolt_shear_stress",
    "bolt_diameter_for_shear",
    "bolt_tensile_stress_area",
    "bolt_axial_stress",
    "thread_stripping_shear_area",
    "thread_stripping_stress",
    "thread_engagement_for_load",
    "bolt_axial_stiffness",
    "member_stiffness_frustum",
    "joint_stiffness_factor",
    "bolt_load_in_joint",
    "member_clamp_load_in_joint",
    "joint_separation_load",
    "preloaded_bolt_cyclic_stress",
]

# Typical nut factor K for as-received (lightly-oiled) steel fasteners. Dry/rough
# joints run higher (~0.3), well-lubricated or coated ones lower (~0.15); K is the
# dominant uncertainty in torque-tension, so it is exposed as a parameter.
NUT_FACTOR_AS_RECEIVED = 0.2


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _positive_factor(nut_factor: float) -> None:
    if nut_factor <= 0:
        raise ValueError(f"nut_factor must be positive; got {nut_factor}")


def bolt_preload_from_torque(
    *,
    torque: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The preload F = T/(K·d) a tightening ``torque`` develops in a thread.

    ``nominal_diameter`` is the thread's nominal diameter d (e.g. 8 mm for M8,
    from the standards tables); ``nut_factor`` is K. Returns the preload as a
    force. ``torque`` must be a torque (force·length) and ``nominal_diameter`` a
    length; ``nut_factor`` must be positive.
    """
    _require(torque, "[force] * [length]", "torque")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    preload = torque.pint / (nut_factor * nominal_diameter.pint)
    converted = preload.to("N")
    return Quantity(magnitude=float(converted.magnitude), unit="N")


def torque_for_preload(
    *,
    preload: Quantity,
    nominal_diameter: Quantity,
    nut_factor: float = NUT_FACTOR_AS_RECEIVED,
) -> Quantity:
    """The tightening torque T = K·F·d for a target ``preload``.

    The inverse of :func:`bolt_preload_from_torque`. ``preload`` must be a force
    and ``nominal_diameter`` a length; ``nut_factor`` must be positive. Returns the
    torque in newton-metres.
    """
    _require(preload, "[force]", "preload")
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _positive_factor(nut_factor)
    torque = nut_factor * preload.pint * nominal_diameter.pint
    converted = torque.to("N*m")
    return Quantity(magnitude=float(converted.magnitude), unit="N*m")


def bearing_stress(
    *,
    force: Quantity,
    diameter: Quantity,
    thickness: Quantity,
) -> Quantity:
    """The bearing stress σ = F/(d·t) a fastener exerts on the hole it bears in.

    ``force`` is the load transferred through the joint, ``diameter`` the pin or
    bolt diameter, and ``thickness`` the bearing plate thickness — the projected
    contact area is d·t. Returns the bearing stress in MPa; every quantity is
    dimension-checked and ``diameter``/``thickness`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(diameter, "[length]", "diameter")
    _require(thickness, "[length]", "thickness")
    for value, name in ((diameter, "diameter"), (thickness, "thickness")):
        if value.to("mm").magnitude <= 0:
            raise ValueError(f"{name} must be positive; got {value}")
    stress = force.pint / (diameter.pint * thickness.pint)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def bolt_shear_stress(
    *,
    force: Quantity,
    diameter: Quantity,
    shear_planes: int = 1,
) -> Quantity:
    """The average shear stress τ = F/(n·A) across a bolt or pin in shear.

    ``force`` is the transverse load, ``diameter`` the shank diameter (A = π·d²/4),
    and ``shear_planes`` the number of shear planes — 1 for single shear (a lap
    joint), 2 for double shear (a clevis). Returns the shear stress in MPa;
    ``shear_planes`` must be a positive integer.
    """
    _require(force, "[force]", "force")
    _require(diameter, "[length]", "diameter")
    if shear_planes < 1:
        raise ValueError(f"shear_planes must be a positive integer; got {shear_planes}")
    area = pi * diameter.pint**2 / 4
    stress = force.pint / (shear_planes * area)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def bolt_diameter_for_shear(
    *,
    shear_load: Quantity,
    allowable_shear: Quantity,
    shear_planes: int = 1,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least bolt/pin diameter to carry a transverse ``shear_load`` within an
    allowable shear stress.

    The inverse of :func:`bolt_shear_stress`: demanding F/(n·π·d²/4) ≤ τ_allow/SF
    gives d_min = √(4·SF·F/(π·n·τ_allow)) — the sizing step for a bolt or pin in
    shear. ``shear_load`` F is the transverse load, ``allowable_shear`` τ_allow the
    fastener's allowable shear stress, ``shear_planes`` n the number of shear planes
    (1 single shear, 2 double shear), and ``required_safety_factor`` SF the margin
    on it (default 1.0). Returns the minimum shank diameter in mm; the load and
    stress are dimension-checked, ``shear_planes`` must be a positive integer, and
    ``SF`` / ``allowable_shear`` must be positive.
    """
    _require(shear_load, "[force]", "shear_load")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    if shear_planes < 1:
        raise ValueError(f"shear_planes must be a positive integer; got {shear_planes}")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    f = shear_load.to("N").magnitude
    tau = allowable_shear.to("MPa").magnitude
    if tau <= 0:
        raise ValueError(f"allowable_shear must be positive; got {allowable_shear}")
    d_min = sqrt(4 * required_safety_factor * f / (pi * shear_planes * tau))
    return Quantity(magnitude=d_min, unit="mm")


def bolt_tensile_stress_area(*, nominal_diameter: Quantity, pitch: Quantity) -> Quantity:
    """The ISO 898 tensile stress area A_t = (π/4)·(d − 0.9382·P)² of a metric
    thread.

    A threaded bolt in tension carries its load on A_t — an effective area midway
    between the pitch- and minor-diameter areas — not on the nominal shank. Recovers
    the ISO 898-1 table values (M10×1.5 → 58.0 mm², M8×1.25 → 36.6 mm²).
    ``nominal_diameter`` is the thread's nominal diameter d and ``pitch`` its thread
    pitch P (both from the standards :class:`~anvilate.standards.MetricThread`).
    Returns the area in mm²; both must be lengths and d must exceed 0.9382·P.
    """
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _require(pitch, "[length]", "pitch")
    d = nominal_diameter.to("mm").magnitude
    p = pitch.to("mm").magnitude
    if p <= 0:
        raise ValueError(f"pitch must be positive; got {pitch}")
    effective = d - _TENSILE_AREA_PITCH_FACTOR * p
    if effective <= 0:
        raise ValueError(
            f"nominal_diameter ({nominal_diameter}) must exceed 0.9382·pitch "
            f"({pitch}) for a valid thread"
        )
    return Quantity(magnitude=pi * effective**2 / 4, unit="mm**2")


def _strip_geometry(
    nominal_diameter: Quantity, pitch: Quantity, member: str
) -> tuple[float, float]:
    """The (coefficient, shear-cylinder diameter) pair for a stripping member, in
    mm — the single source both the area and its length inverse read, so they
    never drift. Validates the thread and the ``member`` selector.
    """
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _require(pitch, "[length]", "pitch")
    d = nominal_diameter.to("mm").magnitude
    p = pitch.to("mm").magnitude
    if p <= 0:
        raise ValueError(f"pitch must be positive; got {p} mm")
    minor = d - _INTERNAL_MINOR_DIA_FACTOR * p
    if minor <= 0:
        raise ValueError(
            f"nominal_diameter ({nominal_diameter}) must exceed 1.0825·pitch "
            f"({pitch}) for a valid thread"
        )
    if member == "external":
        return _EXTERNAL_STRIP_COEFFICIENT, minor
    if member == "internal":
        return _INTERNAL_STRIP_COEFFICIENT, d
    raise ValueError(f"member must be 'external' (bolt) or 'internal' (nut); got {member!r}")


def thread_stripping_shear_area(
    *,
    nominal_diameter: Quantity,
    pitch: Quantity,
    engagement_length: Quantity,
    member: str = "external",
) -> Quantity:
    """The cylindrical shear area A_s that resists thread stripping over a length
    of engagement.

    A threaded joint can fail by the threads shearing off (stripping) instead of
    the bolt breaking in tension. The area that resists it is a cylinder through
    the engaged threads, and which cylinder depends on which member strips:

    - ``member="external"`` — the **bolt** threads strip, on a cylinder at the
      internal-thread minor diameter D1 = d − 1.0825·P:
      A_s = 0.75·π·D1·L_e.
    - ``member="internal"`` — the **nut** or tapped-hole threads strip, on a
      cylinder at the external-thread major diameter d:
      A_s = 0.875·π·d·L_e.

    These are the Alexander / FED-STD-H28 basic-profile shear areas, derived from
    the nominal diameter d and pitch P alone (no thread-tolerance data), so the
    internal area always exceeds the external — with matched materials the bolt
    threads strip first. ``nominal_diameter`` is d, ``pitch`` is P, and
    ``engagement_length`` L_e is the threaded length in contact. Returns the area
    in mm²; all three are dimension-checked lengths and must be positive, and d
    must exceed 1.0825·P for a valid thread.
    """
    _require(engagement_length, "[length]", "engagement_length")
    le = engagement_length.to("mm").magnitude
    if le <= 0:
        raise ValueError(f"engagement_length must be positive; got {le} mm")
    coefficient, diameter = _strip_geometry(nominal_diameter, pitch, member)
    area = coefficient * pi * diameter * le
    return Quantity(magnitude=area, unit="mm**2")


def thread_stripping_stress(
    *,
    load: Quantity,
    nominal_diameter: Quantity,
    pitch: Quantity,
    engagement_length: Quantity,
    member: str = "external",
) -> Quantity:
    """The average thread-stripping shear stress τ = F/A_s over the engaged
    threads.

    ``load`` is the axial force F the joint carries; the other arguments and the
    ``member`` selector are as in :func:`thread_stripping_shear_area`. Screen it
    against the stripping member's allowable shear stress (≈0.577·S_y, or the
    material's rated shear strength) — a short engagement in a soft tapped hole
    strips the internal threads before the bolt reaches proof load, which is why a
    steel bolt into aluminium needs roughly twice the engagement of steel into
    steel. Returns the stress in MPa; ``load`` must be a force.
    """
    _require(load, "[force]", "load")
    area = thread_stripping_shear_area(
        nominal_diameter=nominal_diameter,
        pitch=pitch,
        engagement_length=engagement_length,
        member=member,
    ).pint
    stress = load.pint / area
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def thread_engagement_for_load(
    *,
    load: Quantity,
    nominal_diameter: Quantity,
    pitch: Quantity,
    allowable_shear: Quantity,
    member: str = "external",
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least thread engagement length L_e to carry an axial ``load`` without
    stripping, within an allowable shear stress.

    The inverse of :func:`thread_stripping_stress`: demanding F/(c·π·D·L_e) ≤
    τ_allow/SF gives L_e = SF·F/(c·π·D·τ_allow), with the coefficient c and shear
    diameter D taken from the stripping ``member`` (external/bolt or
    internal/nut). This is the engagement-depth sizing step — how deep to tap a
    hole or how tall a nut must be so the threads develop the load. ``load`` F is
    the axial force, ``allowable_shear`` τ_allow the stripping member's allowable
    shear stress (≈0.577·S_y), and ``required_safety_factor`` SF the margin on it
    (default 1.0). Returns the minimum engagement in mm; ``load`` is a force,
    ``allowable_shear`` a stress, and both SF and τ_allow must be positive.
    """
    _require(load, "[force]", "load")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    tau = allowable_shear.to("MPa").magnitude
    if tau <= 0:
        raise ValueError(f"allowable_shear must be positive; got {allowable_shear}")
    coefficient, diameter = _strip_geometry(nominal_diameter, pitch, member)
    f = load.to("N").magnitude
    le_min = required_safety_factor * f / (coefficient * pi * diameter * tau)
    return Quantity(magnitude=le_min, unit="mm")


def bolt_axial_stress(
    *, tension: Quantity, nominal_diameter: Quantity, pitch: Quantity
) -> Quantity:
    """The axial tensile stress σ = F/A_t in a threaded bolt over its ISO 898
    tensile stress area.

    ``tension`` is the axial force F, ``nominal_diameter`` the thread diameter d,
    and ``pitch`` its pitch P. Uses :func:`bolt_tensile_stress_area`, so the stress
    is the one that governs bolt proof/yield — higher than F over the nominal shank
    area. Returns the stress in MPa; ``tension`` must be a force.
    """
    _require(tension, "[force]", "tension")
    area = bolt_tensile_stress_area(nominal_diameter=nominal_diameter, pitch=pitch).pint
    stress = tension.pint / area
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def bolt_axial_stiffness(
    *,
    nominal_diameter: Quantity,
    pitch: Quantity,
    grip_length: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The bolt axial stiffness k_b = A_t·E/L over the grip.

    A screening estimate of a bolt's tensile spring rate: its ISO 898 tensile stress
    area A_t (:func:`bolt_tensile_stress_area`) times its modulus over the
    ``grip_length`` L of clamped material, k_b = A_t·E/L. ``nominal_diameter`` d and
    ``pitch`` P set A_t, and ``elastic_modulus`` E is the bolt material's. This feeds
    :func:`joint_stiffness_factor` (with :func:`member_stiffness_frustum`) so the
    joint constant C can be found from geometry rather than assumed. A short grip or
    a fat bolt is stiffer. Every quantity is positive. Returns the stiffness in N/mm.
    """
    at = (
        bolt_tensile_stress_area(nominal_diameter=nominal_diameter, pitch=pitch)
        .to("mm**2")
        .magnitude
    )
    _require(grip_length, "[length]", "grip_length")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    length = grip_length.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if length <= 0:
        raise ValueError(f"grip_length must be positive; got {grip_length}")
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    return Quantity(magnitude=at * e / length, unit="N/mm")


def member_stiffness_frustum(
    *,
    nominal_diameter: Quantity,
    grip_length: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The clamped-member stiffness k_m of a bolted joint (Shigley frustum model).

    The clamped members carry the bolt's preload through a pair of 30°-half-angle
    stress cones (frusta) radiating from under the head and nut. For a symmetric
    joint of a single material with a standard washer face (D ≈ 1.5·d), Shigley
    integrates the cone compliance to

        k_m = 0.5774·π·E·d / (2·ln(5·(0.5774·L + 0.5·d)/(0.5774·L + 2.5·d)))

    where ``nominal_diameter`` d is the bolt diameter, ``grip_length`` L the total
    thickness clamped, and ``elastic_modulus`` E the member material's. The members
    are usually several times stiffer than the bolt, which is why the bolt sees only
    a fraction C of an external load (:func:`joint_stiffness_factor`). Every quantity
    is positive. Returns the member stiffness in N/mm.
    """
    _require(nominal_diameter, "[length]", "nominal_diameter")
    _require(grip_length, "[length]", "grip_length")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    d = nominal_diameter.to("mm").magnitude
    length = grip_length.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if d <= 0:
        raise ValueError(f"nominal_diameter must be positive; got {nominal_diameter}")
    if length <= 0:
        raise ValueError(f"grip_length must be positive; got {grip_length}")
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    tan30 = 0.5774
    numerator = tan30 * pi * e * d
    denominator = 2.0 * log(5.0 * (tan30 * length + 0.5 * d) / (tan30 * length + 2.5 * d))
    return Quantity(magnitude=numerator / denominator, unit="N/mm")


def joint_stiffness_factor(*, bolt_stiffness: Quantity, member_stiffness: Quantity) -> float:
    """The joint stiffness constant C = k_b/(k_b + k_m) of a preloaded bolted joint.

    When an external tensile load is applied to a preloaded joint, the bolt and the
    clamped members share it in proportion to their stiffnesses: the bolt picks up
    the fraction C and the members shed the rest. ``bolt_stiffness`` k_b and
    ``member_stiffness`` k_m are the axial stiffnesses (force per length, e.g.
    A·E/L for each path); the members are usually far stiffer than the bolt, so C is
    small (~0.2–0.4) — which is exactly why a preloaded bolt barely feels a
    fluctuating external load and survives fatigue. Both stiffnesses must be
    positive. Returns the dimensionless C in (0, 1).
    """
    _require(bolt_stiffness, "[force] / [length]", "bolt_stiffness")
    _require(member_stiffness, "[force] / [length]", "member_stiffness")
    kb = bolt_stiffness.to("N/mm").magnitude
    km = member_stiffness.to("N/mm").magnitude
    if kb <= 0:
        raise ValueError(f"bolt_stiffness must be positive; got {bolt_stiffness}")
    if km <= 0:
        raise ValueError(f"member_stiffness must be positive; got {member_stiffness}")
    return kb / (kb + km)


def bolt_load_in_joint(
    *,
    preload: Quantity,
    external_load: Quantity,
    stiffness_factor: float,
) -> Quantity:
    """The total tensile load a preloaded bolt carries, F_b = F_i + C·P.

    A bolt tightened to preload ``preload`` F_i and then pulled by an external load
    ``external_load`` P (per bolt) sees only the fraction C of P added on top of the
    preload, with ``stiffness_factor`` C from :func:`joint_stiffness_factor`. This is
    the load to screen against proof/yield and the amplitude that drives bolt
    fatigue — small because C is small. The forces must be forces and C must lie in
    (0, 1). Returns the bolt load in newtons.
    """
    _require(preload, "[force]", "preload")
    _require(external_load, "[force]", "external_load")
    _check_factor(stiffness_factor)
    fb = preload.to("N").magnitude + stiffness_factor * external_load.to("N").magnitude
    return Quantity(magnitude=fb, unit="N")


def member_clamp_load_in_joint(
    *,
    preload: Quantity,
    external_load: Quantity,
    stiffness_factor: float,
) -> Quantity:
    """The clamping load left in the members, F_m = F_i − (1 − C)·P.

    The external load ``external_load`` P relieves the members' clamp by (1 − C)·P;
    when this reaches zero the joint separates. A positive result is the remaining
    clamp force (the joint still holds); a non-positive result means it has opened.
    ``preload`` F_i and ``external_load`` P must be forces and ``stiffness_factor`` C
    in (0, 1). Returns the clamp load in newtons (signed).
    """
    _require(preload, "[force]", "preload")
    _require(external_load, "[force]", "external_load")
    _check_factor(stiffness_factor)
    fm = preload.to("N").magnitude - (1.0 - stiffness_factor) * external_load.to("N").magnitude
    return Quantity(magnitude=fm, unit="N")


def joint_separation_load(*, preload: Quantity, stiffness_factor: float) -> Quantity:
    """The external load that separates a preloaded joint, P₀ = F_i/(1 − C).

    The tensile load per bolt at which the members' clamp reaches zero and the joint
    opens — beyond it the bolt takes the full external load directly and fatigue
    life collapses. ``preload`` F_i must be a force and ``stiffness_factor`` C in
    (0, 1); a stiffer bolt (larger C) separates a joint at a lower load. Returns the
    separation load in newtons.
    """
    _require(preload, "[force]", "preload")
    _check_factor(stiffness_factor)
    p0 = preload.to("N").magnitude / (1.0 - stiffness_factor)
    return Quantity(magnitude=p0, unit="N")


def _check_factor(stiffness_factor: float) -> None:
    if not 0.0 < stiffness_factor < 1.0:
        raise ValueError(
            f"stiffness_factor (joint constant C) must lie in (0, 1); got {stiffness_factor}"
        )


def preloaded_bolt_cyclic_stress(
    *,
    preload: Quantity,
    min_external_load: Quantity,
    max_external_load: Quantity,
    stiffness_factor: float,
    tensile_stress_area: Quantity,
) -> CyclicStress:
    """The fatigue stress cycle in a preloaded bolt under a fluctuating external
    load.

    A bolt tightened to ``preload`` F_i and pulled by an external load that swings
    between ``min_external_load`` and ``max_external_load`` (per bolt) carries only
    the fraction ``stiffness_factor`` C of that swing (see
    :func:`joint_stiffness_factor`), all over the ``tensile_stress_area`` A_t. So the
    bolt stress runs between (F_i + C·P)/A_t at each extreme, giving an alternating
    stress σ_a = C·(P_max − P_min)/(2·A_t) and a mean σ_m = F_i/A_t + C·(P_max +
    P_min)/(2·A_t). The point of preload is right here: C is small, so the
    *amplitude* the bolt sees is tiny even though the mean is high — which is what
    keeps a preloaded bolt off the fatigue line. Feed the returned
    :class:`~anvilate.analysis.CyclicStress` straight to
    :func:`~anvilate.analysis.goodman_safety_factor` and its siblings. The loads
    must be forces, ``tensile_stress_area`` an area, and C in (0, 1).
    """
    _require(preload, "[force]", "preload")
    _require(min_external_load, "[force]", "min_external_load")
    _require(max_external_load, "[force]", "max_external_load")
    _check_factor(stiffness_factor)
    if not tensile_stress_area.has_dimension("[length]**2"):
        raise ValueError(
            f"tensile_stress_area must be a [length]**2 quantity; got "
            f"{tensile_stress_area.dimensionality} ({tensile_stress_area})"
        )
    fi = preload.to("N").magnitude
    p_min = min_external_load.to("N").magnitude
    p_max = max_external_load.to("N").magnitude
    if p_max < p_min:
        raise ValueError(
            f"max_external_load ({max_external_load}) must be at least "
            f"min_external_load ({min_external_load})"
        )
    area = tensile_stress_area.to("mm**2").magnitude
    if area <= 0:
        raise ValueError(f"tensile_stress_area must be positive; got {tensile_stress_area}")
    stress_max = (fi + stiffness_factor * p_max) / area
    stress_min = (fi + stiffness_factor * p_min) / area
    return cyclic_stress_components(
        max_stress=Quantity(magnitude=stress_max, unit="MPa"),
        min_stress=Quantity(magnitude=stress_min, unit="MPa"),
    )
