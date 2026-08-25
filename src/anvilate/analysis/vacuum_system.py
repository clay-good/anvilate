"""T1 analytical vacuum-system (pump-down) checks (closed-form).

Evacuating a chamber is a first-order process: a pump removes gas at a volumetric ``pumping_speed``
S, so the pressure falls exponentially with time. Ignoring leaks and outgassing, the pump-down time
from an initial pressure P₁ to a target P₂ is t = (V/S)·ln(P₁/P₂), where V is the chamber volume.
The logarithm is the key insight — each decade of pressure drop costs the same amount of time, so
reaching high vacuum takes many time constants, and the low-pressure end is where real outgassing
(not modeled here) starts to dominate.

The gas load a pump actually moves is the throughput Q = S·P, the pressure-volume flow (e.g.
mbar·L/s or Pa·m³/s) — the same physical quantity at any point in the line, which is what lets you
size a pump against a known leak or outgassing rate: the pump must provide S = Q/P at the operating
pressure P. Pumping speed, volume, and pressures are dimension-checked
:class:`~anvilate.units.Quantity` values.

Both of those take the pumping speed at the chamber, which is never the pump's nameplate speed. The
line between them throttles the flow: a tube of diameter d and length L has a molecular-flow
conductance C = (pi/12)*v_bar*d**3/L, and pump and line act in series, S_eff = S*C/(S + C). Because
the conductance goes as d**3, a modest line can cost most of the pump — and the pump-down time above
scales on whatever speed actually reaches the chamber, not the one on the datasheet.

Sources: Dushman, *Scientific Foundations of Vacuum Technique* — the pump-down time from a
chamber volume and pumping speed, throughput as pressure times volumetric rate, the molecular-
flow conductance of a long tube and of a thin aperture, and the effective pumping speed a
conductance in series leaves.
"""

from __future__ import annotations

from math import log, pi

from ..units import Quantity

__all__ = [
    "aperture_molecular_conductance",
    "effective_pumping_speed",
    "molecular_flow_tube_conductance",
    "vacuum_pump_down_time",
    "vacuum_throughput",
]


def vacuum_pump_down_time(
    *,
    chamber_volume: Quantity,
    pumping_speed: Quantity,
    initial_pressure: Quantity,
    final_pressure: Quantity,
) -> Quantity:
    """The ideal pump-down time, t = (V/S)·ln(P₁/P₂).

    The time to evacuate a chamber of ``chamber_volume`` V from ``initial_pressure`` P₁ to
    ``final_pressure`` P₂ with a pump of constant ``pumping_speed`` S: t = (V/S)·ln(P₁/P₂). Pressure
    falls exponentially, so each decade costs the same (V/S)·ln(10), and V/S is the system's time
    constant. This ignores leaks and outgassing — real systems deviate at low pressure, where those
    gas loads set a floor the pump-down curve flattens toward — so treat it as an optimistic
    screening estimate. Returns the pump-down time in seconds.
    """
    _check(chamber_volume, "[volume]", "chamber_volume")
    _check(pumping_speed, "[volume]/[time]", "pumping_speed")
    _check(initial_pressure, "[pressure]", "initial_pressure")
    _check(final_pressure, "[pressure]", "final_pressure")
    v = chamber_volume.to("m**3").magnitude
    s = pumping_speed.to("m**3/s").magnitude
    p1 = initial_pressure.to("Pa").magnitude
    p2 = final_pressure.to("Pa").magnitude
    if v <= 0 or s <= 0:
        raise ValueError("chamber_volume and pumping_speed must be positive")
    if p1 <= 0 or p2 <= 0:
        raise ValueError("pressures must be positive")
    if p2 >= p1:
        raise ValueError(
            "final_pressure must be below initial_pressure (the chamber is pumped down)"
        )
    return Quantity(magnitude=v / s * log(p1 / p2), unit="s")


def vacuum_throughput(*, pumping_speed: Quantity, pressure: Quantity) -> Quantity:
    """The vacuum throughput (gas load), Q = S·P.

    The pressure-volume flow of gas a pump moves at a given operating point: the ``pumping_speed`` S
    times the ``pressure`` P, Q = S·P. Throughput is conserved along a leak-free line, so it is the
    common currency for sizing a system — a pump must supply S = Q/P at the working pressure to
    balance a known leak or outgassing load Q. Returns the throughput in Pa·m³/s (divide by the
    pressure unit to recover the familiar mbar·L/s).
    """
    _check(pumping_speed, "[volume]/[time]", "pumping_speed")
    _check(pressure, "[pressure]", "pressure")
    s = pumping_speed.to("m**3/s").magnitude
    p = pressure.to("Pa").magnitude
    if s < 0:
        raise ValueError("pumping_speed must be non-negative")
    if p < 0:
        raise ValueError("pressure must be non-negative")
    return Quantity(magnitude=s * p, unit="Pa*m**3/s")


# Below this the Clausing/long-tube form outruns the aperture conductance; see the guard.
_LONG_TUBE_RATIO_LIMIT = 3.0


def molecular_flow_tube_conductance(
    *,
    mean_molecular_speed: Quantity,
    tube_diameter: Quantity,
    tube_length: Quantity,
) -> Quantity:
    """A long round tube's molecular-flow conductance, C = (π/12)·v̄·d³/L.

    In molecular flow — below roughly 10⁻³ mbar, where molecules cross the tube without colliding
    with each other — a pipe does not resist flow viscously but simply limits how many molecules
    happen to make it through. For a long round tube of ``tube_diameter`` d and ``tube_length`` L
    the Knudsen result is C = (π/12)·v̄·d³/L, from the ``mean_molecular_speed`` v̄ of the gas
    (:func:`anvilate.analysis.kinetic_theory.mean_molecular_speed`, which needs only the temperature
    and molar mass). Conductance has the units of a pumping speed because that is what it is: the
    largest speed the line itself can deliver, however big the pump. The cube of the diameter is the
    whole design lesson — halving the bore costs a factor of eight, so vacuum lines are short and
    fat. Valid for L ≫ d; a short tube or an aperture conducts more than this predicts. Returns the
    conductance in m³/s.
    """
    _check(mean_molecular_speed, "[length]/[time]", "mean_molecular_speed")
    _check(tube_diameter, "[length]", "tube_diameter")
    _check(tube_length, "[length]", "tube_length")
    v_bar = mean_molecular_speed.to("m/s").magnitude
    d = tube_diameter.to("m").magnitude
    length = tube_length.to("m").magnitude
    if v_bar <= 0:
        raise ValueError("mean_molecular_speed must be positive")
    if d <= 0 or length <= 0:
        raise ValueError("tube_diameter and tube_length must be positive")
    # The docstring's "valid for L ≫ d" is computable here and the extrapolation is not
    # merely inaccurate, it is impossible: the long-tube form grows without bound as L
    # shrinks, and at L/d = 1.33 it already crosses the aperture conductance — the
    # kinetic-theory ceiling on what a hole of that area can pass at all. At L/d = 0.1 it
    # returns 3076 L/s where the ceiling is 231. Dushman's short-tube correction is the
    # right tool below this seam; refusing is the honest stand-in for not having it.
    if length / d < _LONG_TUBE_RATIO_LIMIT:
        raise ValueError(
            f"tube_length/tube_diameter = {length / d:.4g} is below the L/d = "
            f"{_LONG_TUBE_RATIO_LIMIT:.0f} this long-tube form needs (it assumes L ≫ d). "
            f"Below it the formula exceeds the aperture conductance — more throughput than "
            f"an open hole of the same area can pass — crossing that ceiling at L/d = 1.33. "
            f"Use Dushman's short-tube correction, or the aperture conductance for a "
            f"near-zero-length opening."
        )
    return Quantity(magnitude=pi / 12.0 * v_bar * d**3 / length, unit="m**3/s")


def effective_pumping_speed(*, pumping_speed: Quantity, conductance: Quantity) -> Quantity:
    """The pumping speed actually delivered at the chamber, S_eff = S·C/(S + C).

    A pump of ``pumping_speed`` S connected through a line of ``conductance`` C
    (:func:`molecular_flow_tube_conductance`) evacuates the chamber at neither of those speeds but
    at their series combination, 1/S_eff = 1/S + 1/C, so S_eff = S·C/(S + C). It is the same
    resistances-in-series law as two conductors in a circuit, and it has the same consequence: the
    smaller of the two dominates, and S_eff can never exceed either. This is the correction that
    keeps :func:`vacuum_pump_down_time` honest — a large pump behind a restrictive line delivers a
    fraction of its nameplate speed, and the pump-down time stretches by exactly the reciprocal of
    that fraction. Returns the effective pumping speed in m³/s.
    """
    _check(pumping_speed, "[volume]/[time]", "pumping_speed")
    _check(conductance, "[volume]/[time]", "conductance")
    s = pumping_speed.to("m**3/s").magnitude
    c = conductance.to("m**3/s").magnitude
    if s <= 0 or c <= 0:
        raise ValueError("pumping_speed and conductance must be positive")
    return Quantity(magnitude=s * c / (s + c), unit="m**3/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def aperture_molecular_conductance(
    *, mean_molecular_speed: Quantity, aperture_area: Quantity
) -> Quantity:
    """The molecular-flow aperture conductance, C = v̄·A/4.

    The conductance of a thin opening — a chamber port, an orifice, the mouth of a tube — in
    molecular flow. It is pure kinetic theory: molecules cross the plane at the wall-collision rate
    n·v̄/4, so the volumetric conductance is a quarter of the ``mean_molecular_speed`` v̄ times the
    ``aperture_area`` A, independent of pressure and of anything downstream.

    :func:`molecular_flow_tube_conductance`'s docstring warns that "a short tube or an aperture
    conducts more than this predicts" and gave no way to compute it. The two differ enormously:
    nitrogen at room temperature through a 50 mm port conducts 231 L/s as a bare aperture but only
    15.4 L/s through the same bore as a 1 m tube. Treating a port as unrestricted is how a system
    ends up pumping at a small fraction of its nameplate speed for reasons the tube formula alone
    does not explain — the entrance itself is a conductance in series.

    Combine it with the tube in series through :func:`effective_pumping_speed`, which reproduces
    the Dushman short-tube form C_ap/(1 + 0.75·L/d) exactly. Valid only in molecular flow, where
    the mean free path exceeds the aperture — in viscous flow an orifice chokes instead and this
    does not apply. Returns the conductance in m**3/s.
    """
    _check(mean_molecular_speed, "[length]/[time]", "mean_molecular_speed")
    _check(aperture_area, "[area]", "aperture_area")
    speed = mean_molecular_speed.to("m/s").magnitude
    area = aperture_area.to("m**2").magnitude
    if speed <= 0:
        raise ValueError("mean_molecular_speed must be positive")
    if area <= 0:
        raise ValueError("aperture_area must be positive")
    return Quantity(magnitude=speed * area / 4.0, unit="m**3/s")
