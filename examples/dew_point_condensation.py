"""Worked example: when a cold surface sweats, and how much water the air is carrying.

Condensation on a duct, a pipe, or a window is not a leak — it's the air itself giving up water
wherever a surface falls below the dew point. Predicting it is a psychrometric calculation: from
the room's temperature and relative humidity, find how much water the air holds and the temperature
at which it would start to shed it. This example takes a 25 °C room at 60% relative humidity and
computes the humidity ratio (how many grams of water ride on each kilogram of dry air) and the dew
point. Any surface colder than that dew point — a chilled-water pipe, an uninsulated duct in a
warm plenum — will run with condensate, which is why those surfaces are insulated or kept above
it. The number to design to is the dew point, not the room temperature.

Run it directly (``python examples/dew_point_condensation.py``);
:func:`room_moisture` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    dew_point_temperature,
    humidity_ratio,
    saturation_vapor_pressure,
)
from anvilate.units import Quantity

ROOM_TEMPERATURE = Quantity.parse("298.15 K")  # 25 deg C
RELATIVE_HUMIDITY = 0.60  # 60%
TOTAL_PRESSURE = Quantity.parse("101325 Pa")  # sea-level barometric
COLD_SURFACE = Quantity.parse("288.15 K")  # 15 deg C chilled-water pipe


def room_moisture() -> dict[str, float]:
    """Return the humidity ratio (g/kg), dew point (deg C), and whether the cold surface sweats."""
    p_ws = saturation_vapor_pressure(temperature=ROOM_TEMPERATURE)
    vapor_pressure = Quantity(magnitude=RELATIVE_HUMIDITY * p_ws.to("Pa").magnitude, unit="Pa")
    w = humidity_ratio(vapor_pressure=vapor_pressure, total_pressure=TOTAL_PRESSURE)
    dew_point = dew_point_temperature(vapor_pressure=vapor_pressure).to("degC").magnitude
    surface_c = COLD_SURFACE.to("degC").magnitude
    return {
        "humidity_ratio_gkg": w * 1000.0,
        "dew_point_degc": dew_point,
        "cold_surface_degc": surface_c,
        "condenses": surface_c < dew_point,
    }


def main() -> None:
    m = room_moisture()
    print(f"room air (25 C, 60% RH) : carries {m['humidity_ratio_gkg']:.1f} g water / kg dry air")
    print(f"dew point               : {m['dew_point_degc']:.1f} deg C")
    surface = m["cold_surface_degc"]
    verdict = "SWEATS (insulate it)" if m["condenses"] else "stays dry"
    print(f"{surface:.0f} deg C pipe surface : {verdict}")
    print("  -> any surface below the dew point runs with condensate — that's the design limit")


if __name__ == "__main__":
    main()
