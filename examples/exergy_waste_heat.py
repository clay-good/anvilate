"""Worked example: why a First-Law-efficient boiler can be a Second-Law disaster.

A gas boiler that turns 1800 K flame into a 360 K hot-water stream looks excellent on a First-Law
energy balance — almost all the fuel's energy ends up in the water. Exergy tells the real story.
This example compares the available work (exergy) of 1000 kW of heat at the 1800 K flame with same
1000 kW delivered at 360 K, both against a 300 K dead state, and shows how much of the fuel's
work-potential the temperature drop throws away — before the water has done anything useful.

The flame heat carries about 833 kW of exergy (83% is available work); by the time that energy sits
in 360 K water it is worth only about 167 kW of work — the other ~667 kW of work-potential was
destroyed in the combustion-and-transfer step, an irreversibility no energy balance reveals. That
gap is the thermodynamic case for cascading high-temperature heat through an engine first (cogen)
rather than burning premium fuel straight into low-grade heat.

Run it directly (``python examples/exergy_waste_heat.py``);
:func:`heat_exergy_cascade` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import exergy_of_heat, irreversibility_from_entropy_generation
from anvilate.units import Quantity

HEAT = Quantity.parse("1000 kW")
FLAME_TEMPERATURE = Quantity.parse("1800 K")
WATER_TEMPERATURE = Quantity.parse("360 K")
DEAD_STATE = Quantity.parse("300 K")


def heat_exergy_cascade() -> dict[str, float]:
    """Return the flame-heat and water-heat exergies (kW) and the exergy destroyed in between."""
    flame = exergy_of_heat(
        heat=HEAT, source_temperature=FLAME_TEMPERATURE, dead_state_temperature=DEAD_STATE
    )
    water = exergy_of_heat(
        heat=HEAT, source_temperature=WATER_TEMPERATURE, dead_state_temperature=DEAD_STATE
    )
    # The exergy destroyed transferring the same 1000 kW from 1800 K to 360 K.
    destroyed_kw = flame.to("kW").magnitude - water.to("kW").magnitude
    # Cross-check via Gouy-Stodola: S_gen = Q*(1/T_cold - 1/T_hot); I = T0*S_gen.
    q = HEAT.to("W").magnitude
    s_gen = q * (1.0 / 360.0 - 1.0 / 1800.0)  # W/K
    idot = irreversibility_from_entropy_generation(
        entropy_generation=Quantity(magnitude=s_gen, unit="W/K"), dead_state_temperature=DEAD_STATE
    )
    return {
        "flame_exergy_kw": flame.to("kW").magnitude,
        "water_exergy_kw": water.to("kW").magnitude,
        "destroyed_kw": destroyed_kw,
        "destroyed_gouy_stodola_kw": idot.to("kW").magnitude,
    }


def main() -> None:
    c = heat_exergy_cascade()
    print("1000 kW of heat, dead state 300 K:")
    print(f"  at 1800 K flame : {c['flame_exergy_kw']:.0f} kW of exergy (available work)")
    print(f"  at 360 K water  : {c['water_exergy_kw']:.0f} kW of exergy")
    print(f"  -> destroyed    : {c['destroyed_kw']:.0f} kW of work-potential in the transfer")
    print(f"     (Gouy-Stodola T0*S_gen check: {c['destroyed_gouy_stodola_kw']:.0f} kW)")


if __name__ == "__main__":
    main()
