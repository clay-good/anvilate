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

from collections.abc import Sequence
from math import log, pi, sqrt

from ..units import Quantity, require_finite
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
    "bolt_proof_load",
    "recommended_bolt_preload",
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
    "eccentric_shear_group_peak_force",
    "slip_critical_resistance",
    "block_shear_strength",
    "shear_lag_factor",
    "net_width_staggered_holes",
    "aisc_tension_member_design_strength",
    "bolt_shear_strength",
    "bolt_bearing_strength",
]

# AISC J3.8 D_u — the ratio of the mean installed bolt pretension to the specified
# minimum. 1.13 for the standard case (caller-tunable for a controlled installation).
SLIP_MEAN_PRETENSION_RATIO = 1.13

# Typical nut factor K for as-received (lightly-oiled) steel fasteners. Dry/rough
# joints run higher (~0.3), well-lubricated or coated ones lower (~0.15); K is the
# dominant uncertainty in torque-tension, so it is exposed as a parameter.
NUT_FACTOR_AS_RECEIVED = 0.2


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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


def slip_critical_resistance(
    *,
    slip_coefficient: float,
    bolt_pretension: Quantity,
    slip_planes: int = 1,
    filler_factor: float = 1.0,
    mean_pretension_ratio: float = SLIP_MEAN_PRETENSION_RATIO,
) -> Quantity:
    """The AISC J3.8 slip resistance of a pretensioned bolt, R_n = μ·D_u·h_f·T_b·n_s.

    A slip-critical connection carries shear by friction between the faying surfaces,
    clamped by the bolt's pretension, rather than by the bolt bearing on the hole. Its
    resistance is R_n = μ·D_u·h_f·T_b·n_s, where ``slip_coefficient`` μ is the mean
    slip coefficient of the faying surface (0.30 Class A, 0.50 Class B),
    ``mean_pretension_ratio`` D_u the mean-to-specified pretension ratio (1.13),
    ``filler_factor`` h_f the filler-plate factor (1.0 with no fillers),
    ``bolt_pretension`` T_b the minimum bolt pretension (AISC Table J3.1), and
    ``slip_planes`` n_s the number of slip planes. μ and T_b are the user's inputs.
    Returns the slip resistance per bolt in kN.
    """
    _require(bolt_pretension, "[force]", "bolt_pretension")
    if slip_coefficient <= 0:
        raise ValueError(f"slip_coefficient must be positive; got {slip_coefficient}")
    if slip_planes < 1:
        raise ValueError(f"slip_planes must be a positive integer; got {slip_planes}")
    if filler_factor <= 0 or mean_pretension_ratio <= 0:
        raise ValueError("filler_factor and mean_pretension_ratio must be positive")
    tb = bolt_pretension.to("kN").magnitude
    if tb <= 0:
        raise ValueError(f"bolt_pretension must be positive; got {bolt_pretension}")
    resistance = slip_coefficient * mean_pretension_ratio * filler_factor * tb * slip_planes
    return Quantity(magnitude=resistance, unit="kN")


def block_shear_strength(
    *,
    gross_shear_area: Quantity,
    net_shear_area: Quantity,
    net_tension_area: Quantity,
    yield_strength: Quantity,
    ultimate_strength: Quantity,
    tension_uniformity_factor: float = 1.0,
) -> Quantity:
    """The AISC 360 §J4.3 block-shear rupture strength of a connected element.

    A bolt group can tear a block of material out of the plate it connects: the block
    rips along a shear plane through the bolt line and pulls free on a tension plane
    across it. §J4.3 adds the two planes, R_n = 0.6·F_u·A_nv + U_bs·F_u·A_nt, but caps
    the shear term at shear yielding on the gross area, so
    R_n = min(0.6·F_u·A_nv, 0.6·F_y·A_gv) + U_bs·F_u·A_nt. ``gross_shear_area`` A_gv and
    ``net_shear_area`` A_nv are the shear plane before and after the bolt holes,
    ``net_tension_area`` A_nt the net tension plane, ``yield_strength`` F_y,
    ``ultimate_strength`` F_u, and ``tension_uniformity_factor`` U_bs — 1.0 when the
    tension stress is uniform (a single bolt line, an angle), 0.5 when it is not (the
    far row of a two-row coped-beam connection). Block shear often governs bolted
    tension connections that the net-section check alone passes. Returns R_n in kN.
    """
    _require(gross_shear_area, "[area]", "gross_shear_area")
    _require(net_shear_area, "[area]", "net_shear_area")
    _require(net_tension_area, "[area]", "net_tension_area")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(ultimate_strength, "[pressure]", "ultimate_strength")
    agv = gross_shear_area.to("mm**2").magnitude
    anv = net_shear_area.to("mm**2").magnitude
    ant = net_tension_area.to("mm**2").magnitude
    fy = yield_strength.to("MPa").magnitude
    fu = ultimate_strength.to("MPa").magnitude
    if agv <= 0 or anv <= 0 or ant <= 0 or fy <= 0 or fu <= 0:
        raise ValueError("all areas and strengths must be positive")
    if anv > agv:
        raise ValueError("net_shear_area cannot exceed gross_shear_area")
    if not 0 < tension_uniformity_factor <= 1.0:
        raise ValueError(
            f"tension_uniformity_factor must be in (0, 1]; got {tension_uniformity_factor}"
        )
    shear_term = min(0.6 * fu * anv, 0.6 * fy * agv)
    tension_term = tension_uniformity_factor * fu * ant
    return Quantity(magnitude=(shear_term + tension_term) / 1000.0, unit="kN")


def shear_lag_factor(
    *,
    connection_eccentricity: Quantity,
    connection_length: Quantity,
) -> float:
    """The AISC 360 §D3 shear-lag factor U = 1 − x̄/L for a tension member.

    When a tension load enters a member through some but not all of its cross-section —
    an angle bolted through one leg, a channel welded at its web — the far elements lag
    and the net section is not fully effective. Table D3.1 Case 2 scales the net area to
    an effective net area A_e = U·A_n with U = 1 − x̄/L, where ``connection_eccentricity``
    x̄ is the distance from the connection plane to the member's centroid (the connection
    eccentricity) and ``connection_length`` L is the length of the connection along the
    line of force (end bolt to end bolt, or the weld length). A short, eccentric
    connection (large x̄, small L) lags most; a long connection recovers U toward 1. Feed
    the result as the shear-lag factor of a tension-rupture check. Returns U (0 to 1).
    """
    _require(connection_eccentricity, "[length]", "connection_eccentricity")
    _require(connection_length, "[length]", "connection_length")
    x_bar = connection_eccentricity.to("mm").magnitude
    length = connection_length.to("mm").magnitude
    if x_bar < 0:
        raise ValueError(
            f"connection_eccentricity must be non-negative; got {connection_eccentricity}"
        )
    if length <= 0:
        raise ValueError(f"connection_length must be positive; got {connection_length}")
    u = 1.0 - x_bar / length
    if u <= 0:
        raise ValueError(
            "connection_eccentricity must be less than connection_length "
            f"(x̄/L = {x_bar / length:.2f} gives a non-positive U)"
        )
    return u


def aisc_tension_member_design_strength(
    *,
    gross_area: Quantity,
    effective_net_area: Quantity,
    yield_strength: Quantity,
    ultimate_strength: Quantity,
    yield_resistance_factor: float = 0.90,
    rupture_resistance_factor: float = 0.75,
) -> Quantity:
    """The AISC 360 §D2 design tensile strength of a member — the lesser of two limit states.

    A tension member is governed by whichever gives less: yielding on the *gross* section
    (which limits gross deformation) or rupture on the *effective net* section (at the
    holes). §D2 rates them with different resistance factors, so the design strength is
    min(φ_y·F_y·A_g, φ_r·F_u·A_e). ``gross_area`` A_g, ``effective_net_area`` A_e (the net
    area reduced by the shear-lag factor, A_e = U·A_n — see :func:`shear_lag_factor` and
    :func:`net_width_staggered_holes`), ``yield_strength`` F_y, and ``ultimate_strength``
    F_u; ``yield_resistance_factor`` φ_y = 0.90 and ``rupture_resistance_factor`` φ_r = 0.75
    are the LRFD factors (set both to 1/Ω for ASD, Ω_y = 1.67, Ω_r = 2.00). Rupture tends
    to govern once the holes and shear lag cut A_e enough; this is the terminal check of the
    net-section flow, to compare against the factored tension demand. Returns the design
    strength in kN.
    """
    if not gross_area.has_dimension("[length]**2"):
        raise ValueError("gross_area must be a [length]**2 quantity")
    if not effective_net_area.has_dimension("[length]**2"):
        raise ValueError("effective_net_area must be a [length]**2 quantity")
    _require(yield_strength, "[pressure]", "yield_strength")
    _require(ultimate_strength, "[pressure]", "ultimate_strength")
    require_finite(gross_area, name="gross_area")
    require_finite(effective_net_area, name="effective_net_area")
    ag = gross_area.to("mm**2").magnitude
    ae = effective_net_area.to("mm**2").magnitude
    fy = yield_strength.to("MPa").magnitude
    fu = ultimate_strength.to("MPa").magnitude
    if ag <= 0 or ae <= 0 or fy <= 0 or fu <= 0:
        raise ValueError("the areas and strengths must be positive")
    if ae > ag:
        raise ValueError("effective_net_area cannot exceed gross_area")
    # Through `require_finite` rather than a bare comparison: a NaN resistance factor walks
    # past `<= 0` and then `min(yielding, rupture)` *deletes* the poisoned limit state
    # instead of propagating it. With a NaN rupture factor the rupture check vanished and
    # the capacity came back 53% higher, from a function that had raised on 0.0.
    require_finite(yield_resistance_factor, name="yield_resistance_factor")
    require_finite(rupture_resistance_factor, name="rupture_resistance_factor")
    if yield_resistance_factor <= 0 or rupture_resistance_factor <= 0:
        raise ValueError("the resistance factors must be positive")
    yielding = yield_resistance_factor * fy * ag
    rupture = rupture_resistance_factor * fu * ae
    return Quantity(magnitude=min(yielding, rupture) / 1000.0, unit="kN")


def bolt_shear_strength(
    *,
    nominal_shear_stress: Quantity,
    bolt_diameter: Quantity,
    shear_planes: int = 1,
) -> Quantity:
    """The AISC 360 §J3.6 nominal shear strength R_n = F_nv·A_b·n of a bolt.

    A bolt in a bearing-type connection carries shear on its nominal (shank) area, and
    §J3.6 rates it at R_n = F_nv·A_b·n_s, with A_b = π·d²/4. ``nominal_shear_stress`` F_nv
    is the bolt's nominal shear strength from Table J3.2 — it depends on the grade and
    whether the threads lie in a shear plane (e.g. ≈372 MPa for an A325/Group 120 bolt
    with threads included, ≈469 MPa excluded) — ``bolt_diameter`` d the nominal diameter,
    and ``shear_planes`` n_s the number of shear planes (1 single, 2 double). Compare the
    lesser of this and the plate's :func:`bolt_bearing_strength` to find what governs a
    bolt: a small bolt in thick plate is shear-limited, a large bolt in thin plate
    bearing-limited. Returns R_n per bolt in kN.
    """
    _require(nominal_shear_stress, "[pressure]", "nominal_shear_stress")
    _require(bolt_diameter, "[length]", "bolt_diameter")
    fnv = nominal_shear_stress.to("MPa").magnitude
    d = bolt_diameter.to("mm").magnitude
    if fnv <= 0 or d <= 0:
        raise ValueError("nominal_shear_stress and bolt_diameter must be positive")
    if shear_planes < 1:
        raise ValueError(f"shear_planes must be a positive integer; got {shear_planes}")
    area = pi * d**2 / 4.0
    return Quantity(magnitude=fnv * area * shear_planes / 1000.0, unit="kN")


def bolt_bearing_strength(
    *,
    clear_distance: Quantity,
    plate_thickness: Quantity,
    bolt_diameter: Quantity,
    ultimate_strength: Quantity,
    deformation_at_service_considered: bool = True,
) -> Quantity:
    """The AISC 360 §J3.10 bolt bearing / tear-out strength at a bolt hole.

    At each bolt hole the plate can fail two ways, and §J3.10 takes the lesser: the bolt
    tears out a strip to the nearest edge or hole (proportional to the clear distance
    l_c), or the plate simply crushes in bearing (capped by the bolt diameter d). With
    deformation at the hole a design consideration, R_n = 1.2·l_c·t·F_u ≤ 2.4·d·t·F_u;
    when it is not, the coefficients rise to 1.5 and 3.0. ``clear_distance`` l_c is the
    clear distance in the load direction from the edge of the hole to the edge of the
    adjacent hole or the material edge, ``plate_thickness`` t, ``bolt_diameter`` d, and
    ``ultimate_strength`` F_u of the connected part. A short edge distance makes tear-out
    govern; a generous one lets bearing govern at the 2.4·d·t·F_u cap. This is the
    strength complement to the raw :func:`bearing_stress`. Returns R_n per bolt in kN.
    """
    _require(clear_distance, "[length]", "clear_distance")
    _require(plate_thickness, "[length]", "plate_thickness")
    _require(bolt_diameter, "[length]", "bolt_diameter")
    _require(ultimate_strength, "[pressure]", "ultimate_strength")
    lc = clear_distance.to("mm").magnitude
    t = plate_thickness.to("mm").magnitude
    d = bolt_diameter.to("mm").magnitude
    fu = ultimate_strength.to("MPa").magnitude
    if lc <= 0 or t <= 0 or d <= 0 or fu <= 0:
        raise ValueError(
            "clear_distance, plate_thickness, bolt_diameter, and ultimate_strength must be positive"
        )
    tearout_coeff, bearing_coeff = (1.2, 2.4) if deformation_at_service_considered else (1.5, 3.0)
    tearout = tearout_coeff * lc * t * fu
    bearing = bearing_coeff * d * t * fu
    return Quantity(magnitude=min(tearout, bearing) / 1000.0, unit="kN")


def net_width_staggered_holes(
    *,
    gross_width: Quantity,
    hole_diameter: Quantity,
    hole_count: int,
    stagger_pitch_gauge: Sequence[tuple[Quantity, Quantity]] = (),
) -> Quantity:
    """The AISC 360 §B4.3b net width of a bolted plate across a staggered hole path.

    A tension failure does not always run straight across a member — where bolts are
    staggered, the tear zigzags from hole to hole, and each diagonal leg recovers some
    width. §B4.3b nets that out with the classic s²/4g rule: the net width is the gross
    width less every hole the path crosses, plus s²/(4g) for each diagonal leg, where s
    is the longitudinal pitch (spacing along the load) and g the transverse gauge
    (spacing across it). ``gross_width`` w, ``hole_diameter`` d (the hole, i.e. bolt
    diameter plus clearance and any damage allowance), ``hole_count`` the number of
    holes on the path, and ``stagger_pitch_gauge`` the (s, g) pair of each diagonal leg
    (empty for a straight transverse path):

        w_net = w − hole_count·d + Σ s²/(4·g).

    Check every plausible path and take the smallest; multiply by thickness for the net
    area, then A_e = U·A_n for rupture. Returns the net width in mm.
    """
    _require(gross_width, "[length]", "gross_width")
    _require(hole_diameter, "[length]", "hole_diameter")
    w = gross_width.to("mm").magnitude
    d = hole_diameter.to("mm").magnitude
    if w <= 0 or d <= 0:
        raise ValueError("gross_width and hole_diameter must be positive")
    if hole_count < 1:
        raise ValueError(f"hole_count must be a positive integer; got {hole_count}")
    stagger = 0.0
    for i, pair in enumerate(stagger_pitch_gauge):
        if len(pair) != 2:
            raise ValueError(f"stagger_pitch_gauge[{i}] must be an (s, g) pair; got {pair!r}")
        s_q, g_q = pair
        _require(s_q, "[length]", f"stagger_pitch_gauge[{i}].s")
        _require(g_q, "[length]", f"stagger_pitch_gauge[{i}].g")
        s = s_q.to("mm").magnitude
        g = g_q.to("mm").magnitude
        if s <= 0 or g <= 0:
            raise ValueError(f"stagger_pitch_gauge[{i}] pitch and gauge must be positive")
        stagger += s * s / (4.0 * g)
    net = w - hole_count * d + stagger
    if net <= 0:
        raise ValueError(
            f"the holes remove the whole section (net width {net:.1f} mm <= 0); "
            "check hole_count and gross_width"
        )
    # A net section cannot exceed the gross section. The s²/4g credit outruns the hole
    # deduction as soon as s > 2*sqrt(g*d) — for a 22 mm hole on a 50 mm gauge that is a
    # 66 mm pitch, which is AISC's ordinary 3d spacing — and the unclamped formula then
    # returned 234 mm of net width on a 200 mm plate: 17% more steel than the plate has,
    # straight into A_e = U*A_n and the tensile rupture capacity built on it. §B4.3b
    # computes a path through the holes; the straight path across the gross width is always
    # available, so the governing net width is the lesser of the two.
    return Quantity(magnitude=min(net, w), unit="mm")


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
    if f <= 0:
        raise ValueError(
            f"shear_load must be positive to size a fastener; got {shear_load}. Every "
            f"other operand here was checked and this one, the value under the square "
            f"root, was not — a sign-reversed load reached math.sqrt and came back as a "
            f"bare domain error."
        )
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


# Shigley's recommended preload fractions of the proof load: reused connections are
# tightened to 0.75·F_p (leaving margin to retighten), permanent ones to 0.90·F_p.
REUSED_PRELOAD_FRACTION = 0.75
PERMANENT_PRELOAD_FRACTION = 0.90


def bolt_proof_load(*, tensile_stress_area: Quantity, proof_strength: Quantity) -> Quantity:
    """The proof load F_p = A_t·S_p of a bolt.

    The proof load is the largest tension a bolt takes without measurable permanent
    set — the property-class strength the fastener tables quote (585 MPa for grade
    8.8, 830 for 10.9, 970 for 12.9). It is the proof strength ``proof_strength`` S_p
    times the ISO 898 ``tensile_stress_area`` A_t (:func:`bolt_tensile_stress_area`),
    and it is the reference every preload target is a fraction of. A_t must be an area
    and S_p a stress, both positive. Returns the proof load in newtons.
    """
    if not tensile_stress_area.has_dimension("[length]**2"):
        raise ValueError(
            f"tensile_stress_area must be a [length]**2 quantity; got "
            f"{tensile_stress_area.dimensionality} ({tensile_stress_area})"
        )
    _require(proof_strength, "[pressure]", "proof_strength")
    area = tensile_stress_area.to("mm**2").magnitude
    sp = proof_strength.to("MPa").magnitude
    if area <= 0:
        raise ValueError(f"tensile_stress_area must be positive; got {tensile_stress_area}")
    if sp <= 0:
        raise ValueError(f"proof_strength must be positive; got {proof_strength}")
    return Quantity(magnitude=area * sp, unit="N")


def recommended_bolt_preload(*, proof_load: Quantity, permanent: bool = False) -> Quantity:
    """The recommended bolt preload as a fraction of the proof load (Shigley).

    A preloaded joint is tightened to a target tension well up the proof load: high
    enough that the members stay clamped and the bolt sees little of the external
    load's swing (good fatigue life), but below proof so the bolt does not yield.
    Shigley recommends F_i = 0.75·F_p for a ``permanent=False`` reused connection
    (leaving margin to loosen and retighten) and 0.90·F_p for a ``permanent=True``
    one. ``proof_load`` F_p is the bolt's proof load (:func:`bolt_proof_load`), which
    must be a positive force. Returns the recommended preload in newtons.
    """
    _require(proof_load, "[force]", "proof_load")
    fp = proof_load.to("N").magnitude
    if fp <= 0:
        raise ValueError(f"proof_load must be positive; got {proof_load}")
    fraction = PERMANENT_PRELOAD_FRACTION if permanent else REUSED_PRELOAD_FRACTION
    return Quantity(magnitude=fraction * fp, unit="N")


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
    _check_joint_not_separated(
        preload.to("N").magnitude,
        external_load.to("N").magnitude,
        stiffness_factor,
        "external_load",
    )
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


def _check_joint_not_separated(
    preload_n: float, external_load_n: float, stiffness_factor: float, label: str
) -> None:
    """Refuse an external load past the separation load P₀ = F_i/(1 − C).

    Beyond P₀ the members' clamp reaches zero, the joint opens, and the bolt takes the FULL
    external load rather than the fraction C of it — which is the one thing the
    load-sharing model these functions implement stops being true about. This module's own
    :func:`joint_separation_load` states it and had no caller anywhere in the package: at
    2.25x separation the bolt load came back 1.71x low and the alternating stress 2.67x
    low, which through Goodman reported a safety factor of 0.97 against a true 0.44.
    """
    separation = preload_n / (1.0 - stiffness_factor)
    if external_load_n > separation:
        raise ValueError(
            f"{label} is {external_load_n:.6g} N, past the joint separation load "
            f"P₀ = F_i/(1 − C) = {separation:.6g} N. Beyond separation the members' clamp is "
            f"gone and the bolt carries the whole external load, not the fraction C of it — "
            f"so the load-sharing forms here understate the bolt load and the fatigue "
            f"amplitude. Raise the preload or reduce the load; see joint_separation_load."
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
    _check_joint_not_separated(fi, p_max, stiffness_factor, "max_external_load")
    stress_max = (fi + stiffness_factor * p_max) / area
    stress_min = (fi + stiffness_factor * p_min) / area
    return cyclic_stress_components(
        max_stress=Quantity(magnitude=stress_max, unit="MPa"),
        min_stress=Quantity(magnitude=stress_min, unit="MPa"),
    )


def eccentric_shear_group_peak_force(
    *,
    positions: Sequence[tuple[Quantity, Quantity]],
    load: Quantity,
    eccentricity: Quantity,
) -> Quantity:
    """The peak fastener force in an eccentrically-loaded shear group (elastic method).

    The AISC "elastic vector" analysis of a bolt or rivet group carrying an in-plane
    load offset from its centroid. The load ``load`` P (taken to act in the
    y-direction) at a perpendicular ``eccentricity`` e from the group centroid is
    replaced by a concentric P plus a torque T = P·e. Every fastener then carries a
    *direct* share P/n (in the load direction) plus a *torsional* share T·r_i/J
    perpendicular to its radius r_i from the centroid, where J = Σ(x_i² + y_i²) is
    the group's polar moment of the fastener areas (equal areas assumed). The two are
    summed as vectors and the largest resultant governs the group.

    ``positions`` is the sequence of (x, y) fastener coordinates *relative to the
    group centroid* (each a length pair — the caller centres them); at least two are
    required and they must not all coincide. Assuming the load acts along +y, each
    fastener i sees (−T·y_i/J, P/n + T·x_i/J); this returns the maximum resultant
    magnitude over the group, in newtons. ``load`` must be a force and
    ``eccentricity`` a length.
    """
    _require(load, "[force]", "load")
    _require(eccentricity, "[length]", "eccentricity")
    n = len(positions)
    if n < 2:
        raise ValueError(f"positions must list at least two fasteners; got {n}")
    xs = []
    ys = []
    for i, pair in enumerate(positions):
        if len(pair) != 2:
            raise ValueError(f"positions[{i}] must be an (x, y) pair; got {pair!r}")
        x_q, y_q = pair
        _require(x_q, "[length]", f"positions[{i}].x")
        _require(y_q, "[length]", f"positions[{i}].y")
        xs.append(x_q.to("mm").magnitude)
        ys.append(y_q.to("mm").magnitude)
    polar_moment = sum(x * x + y * y for x, y in zip(xs, ys, strict=True))  # mm^2 (unit areas)
    if polar_moment <= 0:
        raise ValueError("fasteners must not all coincide at the centroid")
    p = load.to("N").magnitude
    torque = p * eccentricity.to("mm").magnitude  # N*mm
    direct = p / n  # N, along +y
    peak = 0.0
    for x, y in zip(xs, ys, strict=True):
        fx = -torque * y / polar_moment
        fy = direct + torque * x / polar_moment
        peak = max(peak, sqrt(fx * fx + fy * fy))
    return Quantity(magnitude=peak, unit="N")
