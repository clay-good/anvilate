"""T1 analytical injection-molding process checks (closed-form).

Where :mod:`anvilate.analysis.snapfit` and :mod:`anvilate.analysis.living_hinge` design the plastic
*part*, this module covers the *process* that makes it: the two numbers that pick the machine and
set the cycle time.

Molten plastic is injected under high pressure, and that pressure acts on the projected area of the
cavity trying to blow the mould open — so the machine's clamp must hold it shut with a force
F = A·p, the projected area A of the part (and runners) times the average cavity pressure p (roughly
20–100 MPa depending on the material and wall). That clamp force, quoted in tonnes, is how injection
machines are rated and sized; turned around, a given machine's clamp sets the largest projected area
it can mould at a pressure, A = F/p.

The cycle time is dominated by cooling — the part cannot be ejected until its core has frozen enough
to hold shape. One-dimensional heat conduction through the wall gives the classic estimate
t = (s²/(π²·α))·ln[(4/π)·(T_melt − T_mould)/(T_eject − T_mould)], from the wall thickness s, the
melt's thermal diffusivity α, and the melt, mould, and ejection temperatures. Because it goes as the
*square* of wall thickness, a thick section dominates the cycle — the reason thin, uniform walls are
the first rule of moulded-part design.

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (processing of
polymers, injection molding) — the clamp force a cavity pressure over a projected area demands,
the area a given clamp allows, and the cooling time a wall thickness dictates.
"""

from __future__ import annotations

from math import log, pi

from ..units import Quantity

__all__ = [
    "injection_clamp_force",
    "injection_cooling_time",
    "max_projected_area_for_clamp",
]


def injection_clamp_force(*, projected_area: Quantity, cavity_pressure: Quantity) -> Quantity:
    """The clamp force an injection mould needs, F = A·p.

    The force the machine's clamp must apply to hold the mould shut against the injection pressure:
    F = A·p, the ``projected_area`` A of the cavity (the part plus runners, seen along the clamp
    axis) times the average ``cavity_pressure`` p (~20–100 MPa). This is the tonnage an injection
    machine is rated by — size the machine above it, with margin, or the mould flashes open. Returns
    the clamp force in kN.
    """
    _check(projected_area, "[area]", "projected_area")
    _check(cavity_pressure, "[pressure]", "cavity_pressure")
    a = projected_area.to("m**2").magnitude
    p = cavity_pressure.to("Pa").magnitude
    if a <= 0:
        raise ValueError("projected_area must be positive")
    if p <= 0:
        raise ValueError("cavity_pressure must be positive")
    return Quantity(magnitude=a * p / 1000.0, unit="kN")


def max_projected_area_for_clamp(*, clamp_force: Quantity, cavity_pressure: Quantity) -> Quantity:
    """The largest projected area a machine can mould, A = F/p (the inverse).

    The biggest cavity projected area a machine of a given ``clamp_force`` F can hold shut at an
    average ``cavity_pressure`` p: A = F/p, the inverse of :func:`injection_clamp_force`. It answers
    the machine-selection question from the other side — whether a part (and its runners) will fit
    the tonnage on hand, or needs a bigger press or a lower moulding pressure. Returns the maximum
    projected area in cm².
    """
    _check(clamp_force, "[force]", "clamp_force")
    _check(cavity_pressure, "[pressure]", "cavity_pressure")
    f = clamp_force.to("N").magnitude
    p = cavity_pressure.to("Pa").magnitude
    if f <= 0:
        raise ValueError("clamp_force must be positive")
    if p <= 0:
        raise ValueError("cavity_pressure must be positive")
    return Quantity(magnitude=f / p * 1.0e4, unit="cm**2")


def injection_cooling_time(
    *,
    wall_thickness: Quantity,
    thermal_diffusivity: Quantity,
    melt_temperature: Quantity,
    mold_temperature: Quantity,
    ejection_temperature: Quantity,
) -> Quantity:
    """The cooling time of a moulded part, t = (s²/π²α)·ln[(4/π)·(T_melt−T_w)/(T_eject−T_w)].

    The time the part must stay in the mould for its centre to cool from the ``melt_temperature``
    T_melt to the ``ejection_temperature`` T_eject against a ``mold_temperature`` T_mould, by 1-D
    conduction through a wall of ``wall_thickness`` s with the melt's ``thermal_diffusivity`` α:
    t = (s²/(π²·α))·ln[(4/π)·(T_melt − T_mould)/(T_eject − T_mould)]. It goes as the *square* of the
    wall, so a thick section dominates the cycle — thin, even walls are the first rule of design.
    Requires T_melt > T_eject > T_mould. Returns the cooling time in seconds.
    """
    _check(wall_thickness, "[length]", "wall_thickness")
    _check(thermal_diffusivity, "[length]**2/[time]", "thermal_diffusivity")
    _check(melt_temperature, "[temperature]", "melt_temperature")
    _check(mold_temperature, "[temperature]", "mold_temperature")
    _check(ejection_temperature, "[temperature]", "ejection_temperature")
    s = wall_thickness.to("m").magnitude
    alpha = thermal_diffusivity.to("m**2/s").magnitude
    t_melt = melt_temperature.to("K").magnitude
    t_mold = mold_temperature.to("K").magnitude
    t_eject = ejection_temperature.to("K").magnitude
    if s <= 0:
        raise ValueError("wall_thickness must be positive")
    if alpha <= 0:
        raise ValueError("thermal_diffusivity must be positive")
    if not t_melt > t_eject > t_mold:
        raise ValueError("temperatures must satisfy melt > ejection > mold")
    ratio = (4.0 / pi) * (t_melt - t_mold) / (t_eject - t_mold)
    return Quantity(magnitude=(s**2 / (pi**2 * alpha)) * log(ratio), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
