"""T1 analytical arc-welding heat-input checks (closed-form).

Where :mod:`anvilate.analysis.weld` sizes a weld for strength, this module covers the *process*
side: how much heat the arc pours into the joint per unit length. Heat input governs the cooling
rate, and through it the hardness of the heat-affected zone, the risk of hydrogen cracking (too
little heat cools too fast and hardens), the risk of softening or burn-through (too much), and the
distortion — which is why a welding procedure qualifies a *range* of heat input, and the shop stays
inside it.

The arc delivers an electrical power P = U·I from the ``arc_voltage`` U and the ``welding_current``
I. Spread over the speed the torch travels, and scaled by the thermal efficiency η of the process
(how much of that arc power actually enters the plate — ~0.6 for GTAW, ~0.8 for SMAW/GMAW, ~1.0 for
submerged arc), it gives the heat input Q = η·U·I/v: energy per unit length of weld, conventionally
kJ/mm. Turned around, the travel speed a target heat input needs is v = η·U·I/Q — the knob a welder
actually turns to keep a run inside its qualified window.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "carbon_equivalent_iiw",
    "weld_arc_power",
    "weld_heat_input",
    "weld_travel_speed_for_heat_input",
]


def weld_arc_power(*, arc_voltage: Quantity, welding_current: Quantity) -> Quantity:
    """The electrical power an arc delivers, P = U·I.

    The raw power of the welding arc from the ``arc_voltage`` U across it and the
    ``welding_current`` I through it: P = U·I. It is the power available to melt the joint, before
    the process's thermal efficiency and the travel speed turn it into a heat input per unit length
    (see :func:`weld_heat_input`). Returns the arc power in watts.
    """
    _check(arc_voltage, "[electric_potential]", "arc_voltage")
    _check(welding_current, "[current]", "welding_current")
    u = arc_voltage.to("V").magnitude
    i = welding_current.to("A").magnitude
    if u <= 0 or i <= 0:
        raise ValueError("arc_voltage and welding_current must be positive")
    return Quantity(magnitude=u * i, unit="W")


def weld_heat_input(
    *,
    arc_voltage: Quantity,
    welding_current: Quantity,
    travel_speed: Quantity,
    thermal_efficiency: float = 1.0,
) -> Quantity:
    """The arc-welding heat input, Q = η·U·I/v.

    The energy the arc puts into the joint per unit length of weld, from the ``arc_voltage`` U, the
    ``welding_current`` I, the ``travel_speed`` v of the torch, and the ``thermal_efficiency`` η of
    the process (0 to 1, ~0.6 GTAW / ~0.8 SMAW-GMAW / ~1.0 SAW): Q = η·U·I/v. High heat input cools
    slowly (softer heat-affected zone, more distortion, risk of burn-through); low heat input cools
    fast (harder zone, hydrogen-cracking risk) — so a procedure qualifies a band of it. Returns the
    heat input in kJ/mm.
    """
    _check(travel_speed, "[length]/[time]", "travel_speed")
    _fraction(thermal_efficiency, "thermal_efficiency")
    power = weld_arc_power(arc_voltage=arc_voltage, welding_current=welding_current)
    speed = travel_speed.to("mm/s").magnitude
    if speed <= 0:
        raise ValueError("travel_speed must be positive")
    joules_per_mm = thermal_efficiency * power.to("W").magnitude / speed
    return Quantity(magnitude=joules_per_mm / 1000.0, unit="kJ/mm")


def weld_travel_speed_for_heat_input(
    *,
    arc_voltage: Quantity,
    welding_current: Quantity,
    heat_input: Quantity,
    thermal_efficiency: float = 1.0,
) -> Quantity:
    """The travel speed a target heat input needs, v = η·U·I/Q (the sizing inverse).

    How fast the torch must travel to hit a target ``heat_input`` Q at a given ``arc_voltage`` U and
    ``welding_current`` I: v = η·U·I/Q, the inverse of :func:`weld_heat_input`, with the
    ``thermal_efficiency`` η of the process. Travel speed is the parameter a welder controls to keep
    a run inside its qualified heat-input window: faster to drop the heat input, slower to raise it.
    Returns the required travel speed in mm/s.
    """
    _check(heat_input, "[energy]/[length]", "heat_input")
    _fraction(thermal_efficiency, "thermal_efficiency")
    power = weld_arc_power(arc_voltage=arc_voltage, welding_current=welding_current)
    q_joules_per_mm = heat_input.to("kJ/mm").magnitude * 1000.0
    if q_joules_per_mm <= 0:
        raise ValueError("heat_input must be positive")
    speed = thermal_efficiency * power.to("W").magnitude / q_joules_per_mm
    return Quantity(magnitude=speed, unit="mm/s")


def carbon_equivalent_iiw(
    *,
    carbon: float,
    manganese: float = 0.0,
    chromium: float = 0.0,
    molybdenum: float = 0.0,
    vanadium: float = 0.0,
    nickel: float = 0.0,
    copper: float = 0.0,
) -> float:
    """The IIW carbon equivalent, CE = C + Mn/6 + (Cr+Mo+V)/5 + (Ni+Cu)/15.

    A single number that rolls a steel's alloy content into its weldability — how prone the
    heat-affected zone is to hard, crack-susceptible martensite: CE = C + Mn/6 + (Cr+Mo+V)/5 +
    (Ni+Cu)/15 (the International Institute of Welding formula), from the alloying-element contents
    ``carbon``, ``manganese``, ``chromium``, ``molybdenum``, ``vanadium``, ``nickel``, and
    ``copper``, each in **weight percent**. Below about CE = 0.40% a steel welds readily; from
    ~0.40 to 0.60% it needs preheat and controlled cooling to avoid hydrogen cracking; above ~0.60%
    it is difficult and demands high preheat and low-hydrogen practice. It is the metallurgical
    companion to :func:`weld_heat_input` — heat input sets the cooling rate, CE sets how dangerous a
    fast quench is — and the number a welding procedure is qualified against. Returns the carbon
    equivalent in weight percent.
    """
    for name, value in (
        ("carbon", carbon),
        ("manganese", manganese),
        ("chromium", chromium),
        ("molybdenum", molybdenum),
        ("vanadium", vanadium),
        ("nickel", nickel),
        ("copper", copper),
    ):
        if value < 0:
            raise ValueError(f"{name} content must be non-negative; got {value}")
    if carbon <= 0:
        raise ValueError(f"carbon content must be positive; got {carbon}")
    return (
        carbon
        + manganese / 6.0
        + (chromium + molybdenum + vanadium) / 5.0
        + (nickel + copper) / 15.0
    )


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
