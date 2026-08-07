"""T1 analytical casting gating-system checks (closed-form).

The gating system is the network of channels — pouring basin, sprue, runner, and ingates — that
carries molten metal from the ladle into the mold cavity. Its job is to fill the cavity fast enough
to beat premature freezing but smoothly enough not to aspirate air or tear off oxide, and both
demands come down to controlling one cross-section: the choke, the smallest area the stream passes
through. This is the flow side of casting, distinct from the solidification the
:mod:`anvilate.analysis.casting` modulus governs and the spin of
:mod:`anvilate.analysis.centrifugal_casting`.

The metal leaves the choke at the Torricelli velocity v = √(2·g·h) set by the sprue head h, so with
a discharge coefficient C_d the mold of volume V fills in t = V/(C_d·A·√(2·g·h)) — and inverting it
sizes the choke A = V/(C_d·t·√(2·g·h)) for a target fill time. The sprue itself must be tapered, not
straight: a falling stream accelerates and narrows, and if the sprue walls do not follow it the
stream pulls away and sucks in air. Bernoulli and continuity fix the taper at A_top/A_bottom =
√(h_bottom/h_top) — the wider-at-top profile that keeps the sprue full and the casting clean.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "gating_choke_area",
    "gating_fill_time",
    "sprue_taper_ratio",
]


def gating_fill_time(
    *,
    casting_volume: Quantity,
    choke_area: Quantity,
    effective_head: Quantity,
    discharge_coefficient: float,
) -> Quantity:
    """The mold fill time, t = V/(C_d·A·√(2·g·h)).

    How long the cavity takes to fill under a topped-up pouring basin (constant head): the
    ``casting_volume`` V over the volumetric flow through the choke — its ``choke_area`` A carrying
    metal at the Torricelli velocity √(2·g·h) of the ``effective_head`` h, reduced by the
    ``discharge_coefficient`` C_d for friction and contraction — so t = V/(C_d·A·√(2·g·h)). The fill
    must beat premature freezing, so a too-long time calls for a bigger choke
    (:func:`gating_choke_area`). Distinct from the falling-head drain of
    :mod:`anvilate.analysis.tank_flow`, which integrates a dropping level. Returns the time in s.
    """
    _check(casting_volume, "[volume]", "casting_volume")
    _check(choke_area, "[area]", "choke_area")
    _check(effective_head, "[length]", "effective_head")
    v = casting_volume.to("m**3").magnitude
    a = choke_area.to("m**2").magnitude
    h = effective_head.to("m").magnitude
    if v <= 0:
        raise ValueError("casting_volume must be positive")
    if a <= 0:
        raise ValueError("choke_area must be positive")
    if h <= 0:
        raise ValueError("effective_head must be positive")
    _fraction(discharge_coefficient, "discharge_coefficient")
    velocity = sqrt(2.0 * STANDARD_GRAVITY_M_PER_S2 * h)
    return Quantity(magnitude=v / (discharge_coefficient * a * velocity), unit="s")


def gating_choke_area(
    *,
    casting_volume: Quantity,
    fill_time: Quantity,
    effective_head: Quantity,
    discharge_coefficient: float,
) -> Quantity:
    """The choke area for a target fill time, A = V/(C_d·t·√(2·g·h)).

    Inverting the fill-time relation (:func:`gating_fill_time`) for area: the choke cross-section
    that fills a ``casting_volume`` V in a chosen ``fill_time`` t under the ``effective_head`` h,
    at a ``discharge_coefficient`` C_d, A = V/(C_d·t·√(2·g·h)). It is the primary design output of a
    gating system — every other channel area is scaled from the choke by the gating ratio. Returns
    the choke area in mm**2.
    """
    _check(casting_volume, "[volume]", "casting_volume")
    _check(fill_time, "[time]", "fill_time")
    _check(effective_head, "[length]", "effective_head")
    v = casting_volume.to("m**3").magnitude
    t = fill_time.to("s").magnitude
    h = effective_head.to("m").magnitude
    if v <= 0:
        raise ValueError("casting_volume must be positive")
    if t <= 0:
        raise ValueError("fill_time must be positive")
    if h <= 0:
        raise ValueError("effective_head must be positive")
    _fraction(discharge_coefficient, "discharge_coefficient")
    velocity = sqrt(2.0 * STANDARD_GRAVITY_M_PER_S2 * h)
    area_m2 = v / (discharge_coefficient * t * velocity)
    return Quantity(magnitude=area_m2 * 1.0e6, unit="mm**2")


def sprue_taper_ratio(*, top_head: Quantity, bottom_head: Quantity) -> float:
    """The anti-aspiration sprue taper, A_top/A_bottom = √(h_bottom/h_top).

    The ratio of the sprue's top area to its bottom area needed to keep the falling stream full: as
    metal accelerates down the sprue it speeds up and its natural stream narrows, so by continuity
    and Bernoulli the sprue must narrow with it, A_top/A_bottom = √(h_bottom/h_top), with the heads
    ``top_head`` h_top and ``bottom_head`` h_bottom measured from the metal surface in the basin. A
    straight (untapered) sprue lets the stream pull away from the walls and aspirate air, folding
    oxide into the casting — the reason sprues are always tapered. Returns the area ratio (> 1).
    """
    _check(top_head, "[length]", "top_head")
    _check(bottom_head, "[length]", "bottom_head")
    h_top = top_head.to("m").magnitude
    h_bottom = bottom_head.to("m").magnitude
    if h_top <= 0:
        raise ValueError("top_head must be positive")
    if h_bottom <= h_top:
        raise ValueError("bottom_head must be greater than top_head (the sprue falls)")
    return sqrt(h_bottom / h_top)


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be a fraction in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
