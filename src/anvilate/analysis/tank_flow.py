"""T1 analytical tank-draining checks (Torricelli efflux, closed-form).

Liquid draining from an open tank through a hole in the bottom leaves at a speed set only by the
head above the hole — Torricelli's result, V = √(2·g·h), the same speed the liquid would reach
falling that height. As the tank empties the head falls and the flow slows, so the time to drain is
not head over a constant rate but the integral of Torricelli's law:

    t = (A_tank / (C_d·A_orifice)) · √(2/g) · (√h₁ − √h₂),

which stretches out because the last, low-head part of the drain trickles. ``C_d`` (~0.6 for a
sharp orifice) accounts for the vena-contracta and friction. This sizes a drain valve, a spill-
containment blowdown, or a process-vessel empty cycle. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Cengel & Cimbala, *Fluid Mechanics: Fundamentals and Applications* — Torricelli's
efflux velocity from a head, and the time a tank takes to drain through an orifice of stated
discharge coefficient.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "tank_drain_time",
    "torricelli_efflux_velocity",
]

_GRAVITY = 9.80665  # m/s^2, standard gravity


def torricelli_efflux_velocity(*, head: Quantity) -> Quantity:
    """The efflux velocity of liquid leaving an opening, V = √(2·g·h) (Torricelli).

    The speed at which liquid jets from an opening a depth ``head`` h below the free surface: from
    Bernoulli between the surface and the jet, V = √(2·g·h) — exactly the speed an object would
    reach falling that same height. It is independent of the fluid; only the head matters. Multiply
    by the opening area (and a discharge coefficient) for the flow rate. Returns velocity in m/s.
    """
    _check(head, "[length]", "head")
    h = head.to("m").magnitude
    if h < 0:
        raise ValueError("head must be non-negative")
    return Quantity(magnitude=sqrt(2.0 * _GRAVITY * h), unit="m/s")


def tank_drain_time(
    *,
    tank_area: Quantity,
    orifice_area: Quantity,
    discharge_coefficient: float,
    initial_head: Quantity,
    final_head: Quantity,
) -> Quantity:
    """The time to drain a tank between two levels through a bottom orifice.

    Because the efflux velocity falls as the tank empties, the drain time is the integral of
    Torricelli's law: t = (A_tank/(C_d·A_orifice))·√(2/g)·(√h₁ − √h₂). ``tank_area`` A_tank is the
    (constant) plan area of the liquid surface, ``orifice_area`` A_orifice the drain opening,
    ``discharge_coefficient`` C_d (~0.6 sharp-edged, ~0.8 rounded), and ``initial_head`` h₁ /
    ``final_head`` h₂ the liquid depths above the orifice at the start and end (h₂ = 0 to drain
    dry). Returns the drain time in seconds.
    """
    _check(tank_area, "[area]", "tank_area")
    _check(orifice_area, "[area]", "orifice_area")
    _check(initial_head, "[length]", "initial_head")
    _check(final_head, "[length]", "final_head")
    a_t = tank_area.to("m**2").magnitude
    a_o = orifice_area.to("m**2").magnitude
    h1 = initial_head.to("m").magnitude
    h2 = final_head.to("m").magnitude
    if a_t <= 0 or a_o <= 0:
        raise ValueError("tank_area and orifice_area must be positive")
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if h1 < 0 or h2 < 0:
        raise ValueError("heads must be non-negative")
    if h2 > h1:
        raise ValueError("final_head must not exceed initial_head (the tank drains down)")
    t = (a_t / (discharge_coefficient * a_o)) * sqrt(2.0 / _GRAVITY) * (sqrt(h1) - sqrt(h2))
    return Quantity(magnitude=t, unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
