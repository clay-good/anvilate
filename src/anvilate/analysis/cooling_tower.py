"""T1 analytical cooling-tower performance checks (closed-form).

A cooling tower rejects heat by evaporating a little of the water it cools, and the hard floor on
how cold it can get is not the air temperature but the *wet-bulb* temperature — the coldest a wetted
surface reaches as water evaporates into the passing air. Every tower's performance is described in
two temperature differences measured against that floor, and one ratio built from them.

The *range* is how much the tower actually cools the water: R = T_hot − T_cold, the drop from the
hot water entering to the cold water leaving. It is set by the heat load and the water flow, not by
the tower — a bigger load over the same flow means a wider range. The *approach* is how close the
leaving water gets to the wet-bulb floor: A = T_cold − T_wb. The approach is the true measure of
tower size and capability: a tower can never reach the wet-bulb (that would need infinite size), and
pushing the approach from 5 °C down to 3 °C costs a disproportionately larger tower.

Together they give the tower *effectiveness* ε = R/(R + A): the fraction of the maximum possible
cooling — the full drop from the hot water down to the wet-bulb, R + A = T_hot − T_wb — that the
tower achieves. It pairs with :mod:`anvilate.analysis.psychrometrics` (which supplies the wet-bulb
and the air-side loads) and :mod:`anvilate.analysis.refrigeration` (whose condensers it cools).
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "cooling_tower_approach",
    "cooling_tower_blowdown_rate",
    "cooling_tower_effectiveness",
    "cooling_tower_makeup_rate",
    "cooling_tower_range",
]


def cooling_tower_range(
    *,
    hot_water_temperature: Quantity,
    cold_water_temperature: Quantity,
) -> Quantity:
    """The cooling-tower range, R = T_hot − T_cold.

    How far the tower cools the circulating water: the drop from the ``hot_water_temperature`` T_hot
    entering the tower to the ``cold_water_temperature`` T_cold leaving it, R = T_hot − T_cold. The
    range is fixed by the heat load and the water flow (Q = ṁ·c·R), not by the tower itself — the
    same tower shows a wider range under a heavier load. Feeds
    :func:`cooling_tower_effectiveness`. Returns the range as a temperature difference in K.
    """
    _check(hot_water_temperature, "[temperature]", "hot_water_temperature")
    _check(cold_water_temperature, "[temperature]", "cold_water_temperature")
    t_hot = hot_water_temperature.to("K").magnitude
    t_cold = cold_water_temperature.to("K").magnitude
    if t_hot <= t_cold:
        raise ValueError("hot_water_temperature must exceed cold_water_temperature")
    return Quantity(magnitude=t_hot - t_cold, unit="K")


def cooling_tower_approach(
    *,
    cold_water_temperature: Quantity,
    wet_bulb_temperature: Quantity,
) -> Quantity:
    """The cooling-tower approach, A = T_cold − T_wb.

    How close the leaving water gets to the thermodynamic floor: the gap from the
    ``cold_water_temperature`` T_cold down to the entering-air ``wet_bulb_temperature`` T_wb,
    A = T_cold − T_wb. The wet-bulb is the coldest evaporation can reach, so the approach can never
    fall to zero — and squeezing it smaller costs a disproportionately larger tower, which is why
    the approach, not the range, is the real measure of tower capability. Raises if the cold water
    is at or below the wet-bulb (physically impossible for an evaporative tower). Returns the
    approach as a temperature difference in K.
    """
    _check(cold_water_temperature, "[temperature]", "cold_water_temperature")
    _check(wet_bulb_temperature, "[temperature]", "wet_bulb_temperature")
    t_cold = cold_water_temperature.to("K").magnitude
    t_wb = wet_bulb_temperature.to("K").magnitude
    if t_cold <= t_wb:
        raise ValueError(
            "cold_water_temperature must exceed wet_bulb_temperature "
            "(a tower cannot cool below the wet-bulb)"
        )
    return Quantity(magnitude=t_cold - t_wb, unit="K")


def cooling_tower_effectiveness(*, range_: Quantity, approach: Quantity) -> float:
    """The cooling-tower effectiveness, ε = R/(R + A).

    The fraction of the maximum possible cooling the tower achieves: the actual ``range_`` R (from
    :func:`cooling_tower_range`) over the largest drop thermodynamically available — from the hot
    water all the way down to the wet-bulb, R + A, where the ``approach`` A comes from
    :func:`cooling_tower_approach`. A small approach relative to the range means ε near 1 (the water
    leaves close to the wet-bulb floor); a large approach means the tower is leaving much of the
    available cooling on the table. Returns the dimensionless effectiveness (0 to 1).
    """
    _check(range_, "[temperature]", "range_")
    _check(approach, "[temperature]", "approach")
    r = range_.to("K").magnitude
    a = approach.to("K").magnitude
    if r <= 0:
        raise ValueError("range_ must be a positive temperature difference")
    if a < 0:
        raise ValueError("approach must be a non-negative temperature difference")
    return r / (r + a)


def cooling_tower_blowdown_rate(
    *,
    evaporation_rate: Quantity,
    cycles_of_concentration: float,
) -> Quantity:
    """The cooling-tower blowdown rate, B = E/(COC − 1).

    Evaporation leaves dissolved solids behind, so their concentration climbs until a bleed stream
    (blowdown) carries them out. At steady state the salt balance fixes the blowdown from the
    ``evaporation_rate`` E and the ``cycles_of_concentration`` COC (the ratio of circulating- to
    makeup-water salt concentration): B = E/(COC − 1), drift neglected. Running more cycles (higher
    COC) saves water by shrinking the blowdown, but only until scaling or corrosion limits force a
    ceiling — which is why COC is the central water-treatment lever. COC must exceed 1 (you cannot
    concentrate less than the makeup). Returns the blowdown rate in the evaporation rate's flow
    units.
    """
    _check(evaporation_rate, "[volume]/[time]", "evaporation_rate")
    e = evaporation_rate.to("m**3/s").magnitude
    if e < 0:
        raise ValueError("evaporation_rate must be non-negative")
    if cycles_of_concentration <= 1.0:
        raise ValueError("cycles_of_concentration must be greater than 1")
    return Quantity(magnitude=e / (cycles_of_concentration - 1.0), unit="m**3/s")


def cooling_tower_makeup_rate(
    *,
    evaporation_rate: Quantity,
    blowdown_rate: Quantity,
    drift_rate: Quantity | None = None,
) -> Quantity:
    """The cooling-tower makeup water rate, M = E + B + D.

    A tower must replace every drop it loses, so the makeup equals the sum of the losses: the
    ``evaporation_rate`` E (the useful loss that does the cooling), the ``blowdown_rate`` B (the
    bleed that controls dissolved solids, see :func:`cooling_tower_blowdown_rate`), and the small
    windage/``drift_rate`` D of entrained droplets (taken as zero if omitted). M = E + B + D is the
    number that sizes the makeup supply and the water bill. Evaporation dominates, but blowdown is
    the part water treatment can shrink. Returns the makeup rate in m³/s.
    """
    _check(evaporation_rate, "[volume]/[time]", "evaporation_rate")
    _check(blowdown_rate, "[volume]/[time]", "blowdown_rate")
    e = evaporation_rate.to("m**3/s").magnitude
    b = blowdown_rate.to("m**3/s").magnitude
    d = 0.0
    if drift_rate is not None:
        _check(drift_rate, "[volume]/[time]", "drift_rate")
        d = drift_rate.to("m**3/s").magnitude
        if d < 0:
            raise ValueError("drift_rate must be non-negative")
    if e < 0 or b < 0:
        raise ValueError("evaporation_rate and blowdown_rate must be non-negative")
    return Quantity(magnitude=e + b + d, unit="m**3/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
