"""T1 analytical helical compression-spring checks (closed-form).

A round-wire helical spring under an axial force ``F`` carries a torsional shear
stress in the wire, ``τ = K_w · 8·F·D/(π·d³)``, where ``D`` is the mean coil
diameter, ``d`` the wire diameter, and ``K_w`` the Wahl factor correcting for
curvature and the direct shear (Shigley). The spring index ``C = D/d`` sets the
correction. The same coil deflects at the rate ``k = G·d⁴/(8·D³·N_a)`` on its
``N_a`` active coils (its surge mode lives in
:func:`~anvilate.analysis.dynamics.spring_surge_frequency`).

A slender coil also buckles sideways like a column once its axial deflection
grows past a critical value; :func:`helical_spring_buckling` screens that from
the free length, mean diameter, and the two elastic moduli (Shigley). As with the
other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import log, pi, sqrt

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

# End-condition constant α relating a coil's free length to its effective column
# length for the buckling screen (Shigley, Mechanical Engineering Design, Table
# 10-2). Smaller α ⇒ a stiffer restraint ⇒ a more stable spring.
SPRING_END_PARALLEL_PLATES = 0.5  # both ends squared/ground on fixed parallel plates
SPRING_END_FIXED_HINGED = 0.707  # one end fixed (plate), the other pivoted
SPRING_END_HINGED_HINGED = 1.0  # both ends pivoted (on ball seats)
SPRING_END_CLAMPED_FREE = 2.0  # one end fixed, the other free (a cantilevered coil)

__all__ = [
    "spring_index",
    "wahl_factor",
    "spring_shear_stress",
    "helical_spring_rate",
    "helical_spring_active_coils_for_rate",
    "helical_spring_solid_length",
    "SPRING_END_PARALLEL_PLATES",
    "SPRING_END_FIXED_HINGED",
    "SPRING_END_HINGED_HINGED",
    "SPRING_END_CLAMPED_FREE",
    "SpringBucklingResult",
    "helical_spring_buckling",
    "spring_stored_energy",
    "springs_in_series",
    "springs_in_parallel",
    "helical_torsion_spring_rate",
    "helical_torsion_spring_stress",
    "leaf_spring_stress",
    "leaf_spring_rate",
    "BELLEVILLE_PLATEAU_RATIO",
    "belleville_washer_force",
    "belleville_flat_load",
    "spiral_spring_rate",
    "spiral_spring_stress",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def spring_index(*, mean_coil_diameter: Quantity, wire_diameter: Quantity) -> float:
    """The spring index C = D/d (mean coil diameter over wire diameter).

    Practical springs run C ≈ 4–12; the wire diameter must be below the mean coil
    diameter, else :class:`ValueError`.
    """
    _require(mean_coil_diameter, "[length]", "mean_coil_diameter")
    _require(wire_diameter, "[length]", "wire_diameter")
    big = mean_coil_diameter.to("mm").magnitude
    small = wire_diameter.to("mm").magnitude
    if not 0 < small < big:
        raise ValueError(
            f"wire_diameter ({wire_diameter}) must be positive and below the mean coil "
            f"diameter ({mean_coil_diameter})"
        )
    return big / small


def wahl_factor(spring_index: float) -> float:
    """The Wahl stress-correction factor K_w = (4C−1)/(4C−4) + 0.615/C for a
    spring of index ``spring_index`` (C), correcting the nominal shear stress for
    curvature and direct shear. ``spring_index`` must exceed 1."""
    c = spring_index
    if c <= 1:
        raise ValueError(f"spring_index must exceed 1; got {c}")
    return (4 * c - 1) / (4 * c - 4) + 0.615 / c


def spring_shear_stress(
    *,
    force: Quantity,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
) -> Quantity:
    """The Wahl-corrected torsional shear stress τ = K_w·8·F·D/(π·d³) in the wire
    of a round-wire helical compression spring.

    ``force`` is the axial spring force, ``mean_coil_diameter`` D, ``wire_diameter``
    d. Returns the peak shear stress in MPa; every quantity is dimension-checked.
    """
    _require(force, "[force]", "force")
    c = spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    kw = wahl_factor(c)
    stress = kw * 8 * force.pint * mean_coil_diameter.pint / (pi * wire_diameter.pint**3)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def helical_spring_rate(
    *,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
    active_coils: float,
    shear_modulus: Quantity,
) -> Quantity:
    """The helical-spring rate k = G·d⁴/(8·D³·N_a) of a round-wire coil.

    ``active_coils`` N_a counts the coils free to deflect (total coils minus
    the closed-and-ground end coils); ``shear_modulus`` G is the wire's, e.g.
    a material record's. Returns newtons per millimetre; every quantity is
    dimension-checked, the coil geometry is validated through the spring
    index, and ``active_coils`` must be positive.
    """
    spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    _require(shear_modulus, "[pressure]", "shear_modulus")
    if active_coils <= 0:
        raise ValueError(f"active_coils must be positive; got {active_coils}")
    if shear_modulus.to("Pa").magnitude <= 0:
        raise ValueError(f"shear_modulus must be positive; got {shear_modulus}")
    rate = (
        shear_modulus.pint * wire_diameter.pint**4 / (8 * mean_coil_diameter.pint**3 * active_coils)
    )
    converted = rate.to("N/mm")
    return Quantity(magnitude=float(converted.magnitude), unit="N/mm")


def helical_spring_active_coils_for_rate(
    *,
    target_rate: Quantity,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
    shear_modulus: Quantity,
) -> float:
    """The active coils N_a = G·d⁴/(8·D³·k) a helical spring needs for a target rate.

    The inverse of :func:`helical_spring_rate`: solving k = G·d⁴/(8·D³·N_a) for the
    coil count gives N_a = G·d⁴/(8·D³·k). This is the sizing step once the wire and
    coil diameters are fixed and a spring rate is wanted — add the closed-and-ground
    end coils (usually 2) to get the total coils to wind. ``target_rate`` k is the
    desired stiffness, ``mean_coil_diameter`` D and ``wire_diameter`` d the coil
    geometry, and ``shear_modulus`` G the wire's. A softer target or a bigger coil
    calls for more coils. Returns the (fractional) active coil count.
    """
    _require(target_rate, "[force] / [length]", "target_rate")
    spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    _require(shear_modulus, "[pressure]", "shear_modulus")
    k = target_rate.to("N/mm").magnitude
    g = shear_modulus.to("MPa").magnitude  # N/mm^2
    d = wire_diameter.to("mm").magnitude
    big_d = mean_coil_diameter.to("mm").magnitude
    if k <= 0:
        raise ValueError(f"target_rate must be positive; got {target_rate}")
    if g <= 0:
        raise ValueError(f"shear_modulus must be positive; got {shear_modulus}")
    return g * d**4 / (8.0 * big_d**3 * k)


def helical_spring_solid_length(*, total_coils: float, wire_diameter: Quantity) -> Quantity:
    """The solid (fully-compressed) length L_s = N_t·d of a helical spring.

    When a compression spring is squeezed until every coil touches, its length is
    just the total number of coils stacked wire-on-wire: L_s = N_t·d for
    ``total_coils`` N_t (the wound coils, active plus the closed end coils) of
    ``wire_diameter`` d. This holds for squared-and-ground ends (a plain-ended spring
    runs a fraction longer). It is the hard stop a design must clear: the free length
    must exceed L_s by more than the maximum working deflection, or the spring goes
    solid and stops acting like a spring (and its stress spikes). ``total_coils`` must
    be positive. Returns the solid length in mm.
    """
    _require(wire_diameter, "[length]", "wire_diameter")
    d = wire_diameter.to("mm").magnitude
    if total_coils <= 0:
        raise ValueError(f"total_coils must be positive; got {total_coils}")
    if d <= 0:
        raise ValueError(f"wire_diameter must be positive; got {wire_diameter}")
    return Quantity(magnitude=total_coils * d, unit="mm")


class SpringBucklingResult(BaseModel):
    """The lateral-buckling screen of a helical compression spring.

    ``effective_slenderness`` is λ_eff = α·L₀/D, the spring's column-like
    slenderness. ``absolutely_stable`` is ``True`` when λ_eff stays below the
    Shigley threshold √C₂′ — the coil then will not buckle at any deflection up to
    solid, and ``critical_deflection`` is ``None``. Otherwise
    ``critical_deflection`` is the axial deflection y_cr at which buckling begins;
    an operating deflection beyond it buckles the spring sideways.
    """

    model_config = ConfigDict(frozen=True)

    effective_slenderness: float
    absolutely_stable: bool
    critical_deflection: Quantity | None

    def will_buckle(self, deflection: Quantity) -> bool:
        """Whether an operating ``deflection`` buckles the spring.

        ``False`` whenever the spring is absolutely stable; otherwise ``True`` once
        ``deflection`` reaches the critical deflection. ``deflection`` must be a
        length.
        """
        _require(deflection, "[length]", "deflection")
        if self.absolutely_stable or self.critical_deflection is None:
            return False
        return deflection.to("mm").magnitude >= self.critical_deflection.to("mm").magnitude


def helical_spring_buckling(
    *,
    free_length: Quantity,
    mean_coil_diameter: Quantity,
    elastic_modulus: Quantity,
    shear_modulus: Quantity,
    end_condition_constant: float = SPRING_END_PARALLEL_PLATES,
) -> SpringBucklingResult:
    """Screen a helical compression spring for lateral (column) buckling.

    A slender coil compressed axially can snap sideways once its deflection passes
    a critical value. Following Shigley, the effective slenderness λ_eff = α·L₀/D
    and two dimensionless elastic ratios

        C₁′ = E/(2(E−G)),   C₂′ = 2π²(E−G)/(2G+E)

    give a critical deflection y_cr = L₀·C₁′·[1 − √(1 − C₂′/λ_eff²)]. When
    λ_eff ≤ √C₂′ the radicand never turns negative and the coil is *absolutely
    stable* — it will not buckle at any deflection — so ``critical_deflection`` is
    ``None``.

    ``free_length`` L₀ is the unloaded length, ``mean_coil_diameter`` D, and
    ``elastic_modulus`` E / ``shear_modulus`` G the wire's moduli.
    ``end_condition_constant`` α selects the end restraint (the
    ``SPRING_END_*`` constants; default parallel plates, α = 0.5). Returns a
    :class:`SpringBucklingResult`. Every quantity is dimension-checked and α must
    be positive.
    """
    _require(free_length, "[length]", "free_length")
    _require(mean_coil_diameter, "[length]", "mean_coil_diameter")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    _require(shear_modulus, "[pressure]", "shear_modulus")
    if end_condition_constant <= 0:
        raise ValueError(f"end_condition_constant must be positive; got {end_condition_constant}")
    l0 = free_length.to("mm").magnitude
    d = mean_coil_diameter.to("mm").magnitude
    if not d > 0:
        raise ValueError(f"mean_coil_diameter must be positive; got {mean_coil_diameter}")
    e = elastic_modulus.to("Pa").magnitude
    g = shear_modulus.to("Pa").magnitude
    if not e > g > 0:
        raise ValueError(
            f"need elastic_modulus > shear_modulus > 0; got E={elastic_modulus}, G={shear_modulus}"
        )

    lam = end_condition_constant * l0 / d
    c1 = e / (2 * (e - g))
    c2 = 2 * pi**2 * (e - g) / (2 * g + e)

    if lam <= sqrt(c2):
        return SpringBucklingResult(
            effective_slenderness=lam, absolutely_stable=True, critical_deflection=None
        )
    y_cr = l0 * c1 * (1 - sqrt(1 - c2 / lam**2))
    return SpringBucklingResult(
        effective_slenderness=lam,
        absolutely_stable=False,
        critical_deflection=Quantity(magnitude=y_cr, unit="mm"),
    )


def spring_stored_energy(*, spring_rate: Quantity, deflection: Quantity) -> Quantity:
    """The elastic energy U = ½·k·y² stored in a linear spring at ``deflection``.

    A compressed spring is an energy store; U (= ½·F·y for the force F = k·y at
    that deflection) is what it returns on release — the quantity a surge, a
    latch, or an impact snubber is sized around. ``spring_rate`` k is the coil rate
    from :func:`helical_spring_rate` (force per length) and ``deflection`` y the
    compression. Returns the energy in joules; both quantities are
    dimension-checked and ``deflection`` must be non-negative.
    """
    if not spring_rate.has_dimension("[force] / [length]"):
        raise ValueError(
            f"spring_rate must be a [force]/[length] quantity; got "
            f"{spring_rate.dimensionality} ({spring_rate})"
        )
    _require(deflection, "[length]", "deflection")
    if deflection.to("mm").magnitude < 0:
        raise ValueError(f"deflection must be non-negative; got {deflection}")
    energy = spring_rate.pint * deflection.pint**2 / 2
    converted = energy.to("J")
    return Quantity(magnitude=float(converted.magnitude), unit="J")


def _rates_in_n_per_mm(spring_rates: Sequence[Quantity]) -> list[float]:
    if len(spring_rates) < 1:
        raise ValueError("at least one spring rate is required")
    values = []
    for rate in spring_rates:
        if not rate.has_dimension("[force] / [length]"):
            raise ValueError(
                f"each spring rate must be a [force]/[length] quantity; got "
                f"{rate.dimensionality} ({rate})"
            )
        k = rate.to("N/mm").magnitude
        if k <= 0:
            raise ValueError(f"each spring rate must be positive; got {rate}")
        values.append(k)
    return values


def springs_in_series(spring_rates: Sequence[Quantity]) -> Quantity:
    """The combined rate of springs in series, 1/k = Σ(1/kᵢ).

    Springs stacked end to end share the same force and add their deflections, so
    the assembly is *softer* than any single spring — the combined rate is the
    reciprocal sum of the individual ``spring_rates``. Each must be a positive
    force-per-length; pass at least one. Returns the combined rate in N/mm.
    """
    rates = _rates_in_n_per_mm(spring_rates)
    combined = 1.0 / sum(1.0 / k for k in rates)
    return Quantity(magnitude=combined, unit="N/mm")


def springs_in_parallel(spring_rates: Sequence[Quantity]) -> Quantity:
    """The combined rate of springs in parallel, k = Σ kᵢ.

    Springs side by side share the same deflection and add their forces, so the
    assembly is *stiffer* than any single spring — the combined rate is the plain
    sum of the individual ``spring_rates`` (the same law that lets a bolt pattern or
    a set of parallel supports add stiffness). Each must be a positive
    force-per-length; pass at least one. Returns the combined rate in N/mm.
    """
    rates = _rates_in_n_per_mm(spring_rates)
    return Quantity(magnitude=sum(rates), unit="N/mm")


def helical_torsion_spring_rate(
    *,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
    active_coils: float,
    elastic_modulus: Quantity,
) -> Quantity:
    """The angular rate k = E·d⁴/(64·D·N_a) of a round-wire helical torsion spring.

    A helical torsion spring — a clothespin, a garage-door counterbalance, a
    hinge return — winds about its own axis, so unlike the axially-loaded
    compression coil its wire carries *bending*, not torsion. The applied moment M
    bends a wire of length L = π·D·N_a and second moment I = π·d⁴/64, twisting the
    ends through θ = M·L/(E·I) radians; the rate M/θ = E·d⁴/(64·D·N_a) then follows
    from beam bending alone. ``mean_coil_diameter`` D, ``wire_diameter`` d,
    ``active_coils`` N_a and ``elastic_modulus`` E (the wire's Young's modulus, not
    its shear modulus) set it. The coil geometry is validated through the spring
    index and ``active_coils`` must be positive. Returns the rate as a torque per
    radian in newton-metres (radians being dimensionless); real springs run a few
    percent stiffer as inter-coil friction adds to this ideal value.
    """
    spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    if active_coils <= 0:
        raise ValueError(f"active_coils must be positive; got {active_coils}")
    if elastic_modulus.to("Pa").magnitude <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    rate = (
        elastic_modulus.pint * wire_diameter.pint**4 / (64 * mean_coil_diameter.pint * active_coils)
    )
    converted = rate.to("N*m")
    return Quantity(magnitude=float(converted.magnitude), unit="N*m")


def helical_torsion_spring_stress(
    *,
    moment: Quantity,
    mean_coil_diameter: Quantity,
    wire_diameter: Quantity,
) -> Quantity:
    """The peak inner-fibre bending stress σ = K_i·32·M/(π·d³) of a helical torsion
    spring.

    The wire of a torsion spring is a curved beam in bending, so the stress is the
    straight-beam σ = 32·M/(π·d³) raised at the coil's inner fibre by the curvature
    factor K_i = (4C²−C−1)/(4C(C−1)), with the spring index C = D/d (Wahl, for
    round wire in bending). ``moment`` M is the applied wind-up moment,
    ``mean_coil_diameter`` D and ``wire_diameter`` d the coil geometry. As the coil
    opens up (large C) K_i → 1 and the correction fades. Returns the peak stress in
    MPa; every quantity is dimension-checked through the spring index.
    """
    _require(moment, "[force] * [length]", "moment")
    c = spring_index(mean_coil_diameter=mean_coil_diameter, wire_diameter=wire_diameter)
    ki = (4 * c**2 - c - 1) / (4 * c * (c - 1))
    stress = ki * 32 * moment.pint / (pi * wire_diameter.pint**3)
    converted = stress.to("MPa")
    return Quantity(magnitude=float(converted.magnitude), unit="MPa")


def _leaf_geometry(
    length: Quantity, num_leaves: int, leaf_width: Quantity, leaf_thickness: Quantity
) -> tuple[float, float, float]:
    """Validate and return (L, n·b, t) in mm — the shared leaf-spring geometry."""
    _require(length, "[length]", "length")
    _require(leaf_width, "[length]", "leaf_width")
    _require(leaf_thickness, "[length]", "leaf_thickness")
    if num_leaves < 1:
        raise ValueError(f"num_leaves must be a positive integer; got {num_leaves}")
    ell = length.to("mm").magnitude
    b = leaf_width.to("mm").magnitude
    t = leaf_thickness.to("mm").magnitude
    if ell <= 0 or b <= 0 or t <= 0:
        raise ValueError("length, leaf_width, and leaf_thickness must be positive")
    return ell, num_leaves * b, t


def leaf_spring_stress(
    *,
    load: Quantity,
    length: Quantity,
    num_leaves: int,
    leaf_width: Quantity,
    leaf_thickness: Quantity,
) -> Quantity:
    """The peak bending stress σ = 6·F·L/(n·b·t²) in a cantilever leaf spring.

    Models the multi-leaf spring as the idealized uniform-strength (fully-graduated)
    plate: ``num_leaves`` n leaves of ``leaf_width`` b and ``leaf_thickness`` t stack
    to a section modulus n·b·t²/6, so an end ``load`` F over a cantilever ``length``
    L makes σ = 6·F·L/(n·b·t²) at the root. For a semi-elliptic (simply-supported,
    centre-loaded) spring, use the half-span as L and half the central load as F.
    The load is a force and the geometry positive lengths; n ≥ 1. Returns the stress
    in MPa.
    """
    _require(load, "[force]", "load")
    ell, nb, t = _leaf_geometry(length, num_leaves, leaf_width, leaf_thickness)
    f = load.to("N").magnitude
    return Quantity(magnitude=6.0 * f * ell / (nb * t**2), unit="MPa")


def leaf_spring_rate(
    *,
    length: Quantity,
    num_leaves: int,
    leaf_width: Quantity,
    leaf_thickness: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The rate k = E·n·b·t³/(6·L³) of a cantilever leaf spring.

    The stiffness of the same idealized uniform-strength leaf spring as
    :func:`leaf_spring_stress`: its end deflection is δ = 6·F·L³/(E·n·b·t³) — 1.5×
    a plain rectangular cantilever, the flexibility a graduated stack buys — so the
    rate is F/δ = E·n·b·t³/(6·L³). ``elastic_modulus`` E is the leaf material's,
    with ``num_leaves`` n, ``leaf_width`` b, ``leaf_thickness`` t, and cantilever
    ``length`` L as in :func:`leaf_spring_stress`. Returns the rate in N/mm.
    """
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    ell, nb, t = _leaf_geometry(length, num_leaves, leaf_width, leaf_thickness)
    e = elastic_modulus.to("MPa").magnitude
    return Quantity(magnitude=e * nb * t**3 / (6.0 * ell**3), unit="N/mm")


# A Belleville washer's load-deflection curve stops being monotonic once the
# cone-height ratio h/t exceeds sqrt(2): dF/dy = 0 first acquires real roots
# there, opening the near-constant-force plateau (and, higher still, the
# snap-through regime) that disc springs are chosen for.
BELLEVILLE_PLATEAU_RATIO = sqrt(2.0)


def _belleville_geometry(
    thickness: Quantity,
    cone_height: Quantity,
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    poisson_ratio: float,
) -> tuple[float, float, float, float]:
    """Validate and return (t, h, De, K1) in mm for the Almen-Laszlo forms."""
    _require(thickness, "[length]", "thickness")
    _require(cone_height, "[length]", "cone_height")
    _require(outer_diameter, "[length]", "outer_diameter")
    _require(inner_diameter, "[length]", "inner_diameter")
    t = thickness.to("mm").magnitude
    h = cone_height.to("mm").magnitude
    de = outer_diameter.to("mm").magnitude
    di = inner_diameter.to("mm").magnitude
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    if h <= 0:
        raise ValueError(f"cone_height must be positive; got {cone_height}")
    if di <= 0:
        raise ValueError(f"inner_diameter must be positive; got {inner_diameter}")
    if de <= di:
        raise ValueError(
            f"outer_diameter ({outer_diameter}) must exceed inner_diameter ({inner_diameter})"
        )
    if not 0 <= poisson_ratio < 0.5:
        raise ValueError(f"poisson_ratio must lie in [0, 0.5); got {poisson_ratio}")
    ratio = de / di
    k1 = (6.0 / (pi * log(ratio))) * ((ratio - 1.0) / ratio) ** 2
    return t, h, de, k1


def belleville_washer_force(
    *,
    deflection: Quantity,
    thickness: Quantity,
    cone_height: Quantity,
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = 0.3,
) -> Quantity:
    """The load a Belleville (disc) washer carries at a given flattening,
    F(y) = 4·E·y / ((1−ν²)·K₁·D_e²) · [(h − y)·(h − y/2) + t²]  (Almen-Laszlo).

    A coned disc of ``thickness`` t and free ``cone_height`` h (the axial cone
    rise, free height minus t), ``outer_diameter``/``inner_diameter`` D_e/D_i,
    pressed flat by ``deflection`` y ∈ [0, h]; K₁ is the Almen-Laszlo geometry
    constant 6/(π·ln(D_e/D_i))·((D_e/D_i − 1)/(D_e/D_i))². The curve is what
    makes disc springs interesting: stiff for h/t well under
    :data:`BELLEVILLE_PLATEAU_RATIO` (≈ a linear washer-spring), nearly
    constant-force around h/t = √2, and regressive (snap-through) beyond — the
    same washer geometry tunes a bolt stack, a constant-pressure clamp, or a
    bistable detent. Returns the force in newtons.
    """
    t, h, de, k1 = _belleville_geometry(
        thickness, cone_height, outer_diameter, inner_diameter, poisson_ratio
    )
    _require(deflection, "[length]", "deflection")
    y = deflection.to("mm").magnitude
    if not 0 <= y <= h:
        raise ValueError(
            f"deflection must lie in [0, cone_height] = [0, {cone_height}]; got {deflection}"
        )
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    e = elastic_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    force = 4.0 * e * y / ((1.0 - poisson_ratio**2) * k1 * de**2) * ((h - y) * (h - y / 2.0) + t**2)
    return Quantity(magnitude=force, unit="N")


def belleville_flat_load(
    *,
    thickness: Quantity,
    cone_height: Quantity,
    outer_diameter: Quantity,
    inner_diameter: Quantity,
    elastic_modulus: Quantity,
    poisson_ratio: float = 0.3,
) -> Quantity:
    """The load that presses a Belleville washer flat,
    F_flat = 4·E·h·t² / ((1−ν²)·K₁·D_e²).

    :func:`belleville_washer_force` evaluated at full deflection y = h — the
    quadratic cone terms vanish and only the t² plate-bending term is left. The
    usual catalogue anchor point (and the preload a bolt stack reaches when the
    washers go flat). Arguments as there. Returns the force in newtons.
    """
    t, h, de, k1 = _belleville_geometry(
        thickness, cone_height, outer_diameter, inner_diameter, poisson_ratio
    )
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    e = elastic_modulus.to("MPa").magnitude
    if e <= 0:
        raise ValueError(f"elastic_modulus must be positive; got {elastic_modulus}")
    force = 4.0 * e * h * t**2 / ((1.0 - poisson_ratio**2) * k1 * de**2)
    return Quantity(magnitude=force, unit="N")


def _spiral_strip(width: Quantity, thickness: Quantity) -> tuple[float, float]:
    _require(width, "[length]", "width")
    _require(thickness, "[length]", "thickness")
    b = width.to("mm").magnitude
    t = thickness.to("mm").magnitude
    if b <= 0:
        raise ValueError(f"width must be positive; got {width}")
    if t <= 0:
        raise ValueError(f"thickness must be positive; got {thickness}")
    return b, t


def spiral_spring_rate(
    *,
    width: Quantity,
    thickness: Quantity,
    developed_length: Quantity,
    elastic_modulus: Quantity,
) -> Quantity:
    """The torsional rate k_θ = E·b·t³/(12·L) of a flat spiral (clock) spring.

    A flat strip wound into a spiral — a clock or wind-up spring, a constant-torque
    return spring — stores energy by bending along its whole length, so it behaves as
    a straight cantilever strip of the full developed length. Its angular rate is the
    strip's bending rigidity over that length: k_θ = M/θ = E·I/L = E·b·t³/(12·L),
    the torque per radian of wind-up. ``width`` b and ``thickness`` t are the strip's
    cross-section, ``developed_length`` L its total unwound length, and
    ``elastic_modulus`` E the material's. The long developed length is what makes a
    spiral spring soft enough to wind many turns. Returns the rate in N·m per radian.
    """
    b, t = _spiral_strip(width, thickness)
    _require(developed_length, "[length]", "developed_length")
    _require(elastic_modulus, "[pressure]", "elastic_modulus")
    length = developed_length.to("mm").magnitude
    e = elastic_modulus.to("MPa").magnitude
    if length <= 0:
        raise ValueError(f"developed_length must be positive; got {developed_length}")
    # E [MPa=N/mm^2], b,t,L [mm] -> k_theta in N*mm/rad; convert to N*m/rad.
    k_theta_n_mm = e * b * t**3 / (12.0 * length)
    return Quantity(magnitude=k_theta_n_mm / 1000.0, unit="N*m")


def spiral_spring_stress(*, moment: Quantity, width: Quantity, thickness: Quantity) -> Quantity:
    """The peak bending stress σ = 6·M/(b·t²) in a flat spiral (clock) spring.

    The wound strip is a rectangular section in bending, so a wind-up ``moment`` M
    raises a peak fibre stress σ = M·(t/2)/(b·t³/12) = 6·M/(b·t²) — screen it against
    the strip material's allowable to find how far the spring can be wound. ``width``
    b and ``thickness`` t are the strip cross-section as in
    :func:`spiral_spring_rate`. Returns the stress in MPa.
    """
    _require(moment, "[force] * [length]", "moment")
    b, t = _spiral_strip(width, thickness)
    m = moment.to("N*mm").magnitude
    return Quantity(magnitude=6.0 * m / (b * t**2), unit="MPa")
