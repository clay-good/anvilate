"""T1 analytical fillet-weld checks (throat shear, closed-form).

A fillet weld carries load on its *effective throat* — the shortest section
through the weld, ``a = 0.707·w`` for a leg size ``w`` (0.707 = 1/√2, the throat
of an equal-leg right triangle). The design stress is the shear on that throat,
``τ = F/(0.707·w·L)`` over a weld of length ``L`` (AISC treats all fillet-weld
stress, whatever the load direction, as shear on the throat). Sizing runs the
other way — :func:`fillet_weld_leg_for_load` inverts it to the leg a load needs.
As with the other checks, inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence
from math import pi, sin, sqrt

from ..units import Quantity

# The effective throat of a fillet weld is 0.707 (= 1/√2) of its leg size.
FILLET_THROAT_FACTOR = 0.707

__all__ = [
    "FILLET_THROAT_FACTOR",
    "fillet_weld_throat_stress",
    "fillet_weld_leg_for_load",
    "fillet_weld_design_strength",
    "fillet_weld_directional_strength",
    "weld_base_metal_shear_strength",
    "eccentric_weld_group_peak_stress",
]

# AISC J2.4 nominal weld-metal shear strength fraction: R_n uses 0.6·F_EXX.
_WELD_METAL_SHEAR_FRACTION = 0.6


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def fillet_weld_throat_stress(
    *,
    force: Quantity,
    leg_size: Quantity,
    length: Quantity,
) -> Quantity:
    """The shear stress τ = F/(0.707·w·L) on a fillet weld's effective throat.

    ``force`` is the load the weld carries, ``leg_size`` w the fillet leg (the
    effective throat is 0.707·w), and ``length`` L the weld length. Returns the
    throat shear stress as a pressure; every quantity is dimension-checked and
    ``leg_size`` / ``length`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(leg_size, "[length]", "leg_size")
    _require(length, "[length]", "length")
    w = leg_size.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    if w <= 0 or length_mm <= 0:
        raise ValueError("leg_size and length must be positive")
    throat_area = FILLET_THROAT_FACTOR * w * length_mm  # mm²
    return Quantity(magnitude=force.to("N").magnitude / throat_area, unit="MPa")


def fillet_weld_leg_for_load(
    *,
    force: Quantity,
    length: Quantity,
    allowable_shear: Quantity,
    required_safety_factor: float = 1.0,
) -> Quantity:
    """The least fillet-weld leg to carry ``force`` within an allowable throat shear.

    The inverse of :func:`fillet_weld_throat_stress`: demanding F/(0.707·w·L) ≤
    τ_allow/SF gives w_min = SF·F/(0.707·L·τ_allow) — the sizing step for a fillet
    weld (round up to the next standard leg, and mind the minimum leg for the
    thicker plate). ``force`` F is the load, ``length`` L the weld length,
    ``allowable_shear`` τ_allow the weld's allowable throat shear (e.g. 0.6·F_EXX),
    and ``required_safety_factor`` SF the margin on it (default 1.0). Returns the
    minimum leg in mm; the load/length/stress are dimension-checked and ``SF`` /
    ``allowable_shear`` must be positive.
    """
    _require(force, "[force]", "force")
    _require(length, "[length]", "length")
    _require(allowable_shear, "[pressure]", "allowable_shear")
    if required_safety_factor <= 0:
        raise ValueError(f"required_safety_factor must be positive; got {required_safety_factor}")
    length_mm = length.to("mm").magnitude
    tau = allowable_shear.to("MPa").magnitude
    if length_mm <= 0:
        raise ValueError(f"length must be positive; got {length}")
    if tau <= 0:
        raise ValueError(f"allowable_shear must be positive; got {allowable_shear}")
    leg = (
        required_safety_factor * force.to("N").magnitude / (FILLET_THROAT_FACTOR * length_mm * tau)
    )
    return Quantity(magnitude=leg, unit="mm")


def fillet_weld_design_strength(
    *,
    leg_size: Quantity,
    length: Quantity,
    electrode_strength: Quantity,
    weld_metal_shear_fraction: float = _WELD_METAL_SHEAR_FRACTION,
) -> Quantity:
    """The AISC J2.4 nominal strength of a fillet weld, R_n = 0.6·F_EXX·(0.707·w)·L.

    The load a fillet weld can carry, from the weld metal rather than the base metal:
    the weld-metal shear strength 0.6·F_EXX acts over the effective throat area
    0.707·w·L. ``leg_size`` w is the fillet leg, ``length`` L the weld length,
    ``electrode_strength`` F_EXX the electrode's tensile strength (e.g. 490 MPa for an
    E70 electrode), and ``weld_metal_shear_fraction`` the 0.6 factor (caller-tunable).
    This is the capacity (a force) to compare against the load, the rating complement
    to :func:`fillet_weld_throat_stress`; a real check also verifies the base-metal
    strength at the weld. Returns the nominal strength in kN.
    """
    _require(leg_size, "[length]", "leg_size")
    _require(length, "[length]", "length")
    _require(electrode_strength, "[pressure]", "electrode_strength")
    if weld_metal_shear_fraction <= 0:
        raise ValueError(
            f"weld_metal_shear_fraction must be positive; got {weld_metal_shear_fraction}"
        )
    w = leg_size.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    fexx = electrode_strength.to("MPa").magnitude
    if w <= 0 or length_mm <= 0 or fexx <= 0:
        raise ValueError("leg_size, length, and electrode_strength must be positive")
    # MPa·mm² = N; convert to kN.
    strength_n = weld_metal_shear_fraction * fexx * FILLET_THROAT_FACTOR * w * length_mm
    return Quantity(magnitude=strength_n / 1000.0, unit="kN")


def fillet_weld_directional_strength(
    *,
    leg_size: Quantity,
    length: Quantity,
    electrode_strength: Quantity,
    load_angle: float,
    weld_metal_shear_fraction: float = _WELD_METAL_SHEAR_FRACTION,
) -> Quantity:
    """The AISC J2.4 fillet-weld strength with the directional increase (sin θ factor).

    A fillet weld is stronger the more the load pulls *across* its axis rather than
    along it, and AISC J2.4(a) credits that: R_n = 0.6·F_EXX·(1.0 + 0.5·sin^1.5 θ)·A_we,
    where θ is the angle between the line of force and the weld's longitudinal axis.
    A weld loaded along its length (θ = 0, longitudinal) gets the base 0.6·F_EXX·A_we —
    exactly :func:`fillet_weld_design_strength` — while one loaded square across it
    (θ = π/2, transverse) is 50% stronger. ``leg_size`` w, ``length`` L, and
    ``electrode_strength`` F_EXX as in the base check; ``load_angle`` θ **in radians**
    (0 to π/2); ``weld_metal_shear_fraction`` the 0.6 factor. Use the base longitudinal
    strength for a weld group unless every segment shares one load angle. Returns the
    nominal strength in kN.
    """
    _require(leg_size, "[length]", "leg_size")
    _require(length, "[length]", "length")
    _require(electrode_strength, "[pressure]", "electrode_strength")
    if weld_metal_shear_fraction <= 0:
        raise ValueError(
            f"weld_metal_shear_fraction must be positive; got {weld_metal_shear_fraction}"
        )
    if not 0.0 <= load_angle <= pi / 2:
        raise ValueError(f"load_angle must be between 0 and pi/2 radians; got {load_angle}")
    w = leg_size.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    fexx = electrode_strength.to("MPa").magnitude
    if w <= 0 or length_mm <= 0 or fexx <= 0:
        raise ValueError("leg_size, length, and electrode_strength must be positive")
    directional = 1.0 + 0.5 * sin(load_angle) ** 1.5
    strength_n = (
        weld_metal_shear_fraction * fexx * directional * FILLET_THROAT_FACTOR * w * length_mm
    )
    return Quantity(magnitude=strength_n / 1000.0, unit="kN")


def weld_base_metal_shear_strength(
    *,
    base_thickness: Quantity,
    length: Quantity,
    base_ultimate_strength: Quantity,
    shear_fraction: float = _WELD_METAL_SHEAR_FRACTION,
) -> Quantity:
    """The AISC J2.4 / J4.2 base-metal shear rupture strength alongside a fillet weld.

    A welded joint is only as strong as the weaker of the weld metal and the base metal
    it fuses to, and the base-metal side is the shear rupture of the connected part along
    the weld line: R_n = 0.6·F_u·A_BM, with A_BM = t·L the base-metal area (the connected
    element's thickness through its length). ``base_thickness`` t is the thickness of the
    part the weld tears out of, ``length`` L the weld length, ``base_ultimate_strength``
    F_u the base metal's tensile strength, and ``shear_fraction`` the 0.6 rupture factor.
    Compare the lesser of this and the weld-metal :func:`fillet_weld_design_strength`: a
    heavy weld on a thin plate is base-metal-limited, a light weld on thick plate
    weld-metal-limited. Returns R_n in kN.
    """
    _require(base_thickness, "[length]", "base_thickness")
    _require(length, "[length]", "length")
    _require(base_ultimate_strength, "[pressure]", "base_ultimate_strength")
    if shear_fraction <= 0:
        raise ValueError(f"shear_fraction must be positive; got {shear_fraction}")
    t = base_thickness.to("mm").magnitude
    length_mm = length.to("mm").magnitude
    fu = base_ultimate_strength.to("MPa").magnitude
    if t <= 0 or length_mm <= 0 or fu <= 0:
        raise ValueError("base_thickness, length, and base_ultimate_strength must be positive")
    strength_n = shear_fraction * fu * t * length_mm
    return Quantity(magnitude=strength_n / 1000.0, unit="kN")


def eccentric_weld_group_peak_stress(
    *,
    segments: Sequence[tuple[tuple[Quantity, Quantity], tuple[Quantity, Quantity]]],
    load: Quantity,
    eccentricity: Quantity,
    leg_size: Quantity,
) -> Quantity:
    """The peak throat stress in an eccentrically-loaded fillet-weld group (elastic
    method).

    The AISC elastic-vector analysis of a weld line carrying an in-plane load offset
    from its centroid — the weld counterpart of
    :func:`~anvilate.analysis.eccentric_shear_group_peak_force`. Each straight weld
    ``segments`` (a ((x1, y1), (x2, y2)) pair of endpoint coordinates, treated as a
    line of unit throat) contributes its length and its polar moment to the group. The
    load ``load`` P, taken to act in the +y direction at a perpendicular
    ``eccentricity`` e from the group centroid, is replaced by a concentric P plus a
    torque T = P·e. Every point on the weld then carries a *direct* shear flow P/L_w
    (in the load direction) plus a *torsional* flow T·r/J_w perpendicular to its radius
    r from the centroid, where L_w is the total weld length and J_w = Σ(Lᵢ³/12 + Lᵢ·dᵢ²)
    the weld line's polar moment (each segment's own Lᵢ³/12 — orientation-independent —
    plus the parallel-axis term to the group centroid). The two flows sum as vectors,
    the largest resultant occurs at a segment endpoint, and dividing by the effective
    throat 0.707·``leg_size`` gives the peak throat stress. Coordinates are lengths,
    ``load`` a force, ``eccentricity`` and ``leg_size`` lengths; at least one segment is
    required. Returns the peak throat stress in MPa.
    """
    _require(load, "[force]", "load")
    _require(eccentricity, "[length]", "eccentricity")
    _require(leg_size, "[length]", "leg_size")
    w = leg_size.to("mm").magnitude
    if w <= 0:
        raise ValueError(f"leg_size must be positive; got {leg_size}")
    if len(segments) < 1:
        raise ValueError(f"segments must list at least one weld; got {len(segments)}")
    lengths: list[float] = []
    centroids: list[tuple[float, float]] = []
    endpoints: list[tuple[float, float]] = []
    for i, seg in enumerate(segments):
        if len(seg) != 2:
            raise ValueError(f"segments[{i}] must be an ((x1, y1), (x2, y2)) pair; got {seg!r}")
        (p1, p2) = seg
        _require(p1[0], "[length]", f"segments[{i}] start x")
        _require(p1[1], "[length]", f"segments[{i}] start y")
        _require(p2[0], "[length]", f"segments[{i}] end x")
        _require(p2[1], "[length]", f"segments[{i}] end y")
        x1, y1 = p1[0].to("mm").magnitude, p1[1].to("mm").magnitude
        x2, y2 = p2[0].to("mm").magnitude, p2[1].to("mm").magnitude
        length = sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if length <= 0:
            raise ValueError(f"segments[{i}] has zero length")
        lengths.append(length)
        centroids.append(((x1 + x2) / 2.0, (y1 + y2) / 2.0))
        endpoints.append((x1, y1))
        endpoints.append((x2, y2))
    total_length = sum(lengths)
    cx = sum(li * ci[0] for li, ci in zip(lengths, centroids, strict=True)) / total_length
    cy = sum(li * ci[1] for li, ci in zip(lengths, centroids, strict=True)) / total_length
    polar_moment = 0.0
    for li, ci in zip(lengths, centroids, strict=True):
        d2 = (ci[0] - cx) ** 2 + (ci[1] - cy) ** 2
        polar_moment += li**3 / 12.0 + li * d2  # mm^3 (unit throat)
    p = load.to("N").magnitude
    torque = p * eccentricity.to("mm").magnitude  # N*mm
    direct = p / total_length  # N/mm, along +y
    peak_flow = 0.0
    for x, y in endpoints:
        rx, ry = x - cx, y - cy
        fx = -torque * ry / polar_moment
        fy = direct + torque * rx / polar_moment
        peak_flow = max(peak_flow, sqrt(fx * fx + fy * fy))  # N/mm
    throat = FILLET_THROAT_FACTOR * w
    return Quantity(magnitude=peak_flow / throat, unit="MPa")
