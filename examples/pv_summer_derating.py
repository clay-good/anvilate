"""Worked example: the rooftop array that makes less power on the hottest, sunniest day.

A solar panel's nameplate wattage is measured in a lab at a 25 °C cell, but a panel bolted to a hot
roof in full sun runs far above that — and silicon makes less power the hotter it gets. The result
is counterintuitive: peak sun does not mean peak output, because the same sun that drives the
irradiance also bakes the cell.

This example takes a 400 W module (temperature coefficient −0.38 %/°C, NOCT 45 °C) on a 35 °C summer
afternoon under a strong 900 W/m² of sun. The cell does not sit at 35 °C — the NOCT model puts it at
63 °C, nearly 30 degrees above the air. At that temperature the module's output falls to about
342 W, a 14 % haircut off its 400 W rating, even though the sun is close to full. The same module on
a cool 15 °C spring day at the same irradiance runs a 43 °C cell and gives about 373 W — more power
from a weaker season, purely because the panel is cooler. The lesson is that a PV array is sized on
*operating* output, not its nameplate: the cell temperature, driven by both the ambient heat and the
irradiance itself, quietly takes a tenth or more of the rating on exactly the days that look best.

Run it directly (``python examples/pv_summer_derating.py``);
:func:`module_output` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import pv_cell_temperature, pv_temperature_derated_power
from anvilate.units import Quantity

RATED_POWER = Quantity.parse("400 W")
TEMPERATURE_COEFFICIENT = -0.0038  # per deg C
NOCT = Quantity(magnitude=45.0, unit="degC")
IRRADIANCE = Quantity.parse("900 W/m**2")


def module_output() -> dict[str, float]:
    """Return the cell temperature and derated power on a hot summer and a cool spring day."""

    def output(ambient_c: float) -> dict[str, float]:
        cell = pv_cell_temperature(
            ambient_temperature=Quantity(magnitude=ambient_c, unit="degC"),
            irradiance=IRRADIANCE,
            noct=NOCT,
        )
        power = pv_temperature_derated_power(
            rated_power=RATED_POWER,
            cell_temperature=cell,
            temperature_coefficient=TEMPERATURE_COEFFICIENT,
        )
        return {"cell_c": cell.to("degC").magnitude, "power_w": power.to("W").magnitude}

    summer = output(35.0)
    spring = output(15.0)
    return {
        "summer_cell_c": summer["cell_c"],
        "summer_power_w": summer["power_w"],
        "spring_cell_c": spring["cell_c"],
        "spring_power_w": spring["power_w"],
    }


def main() -> None:
    m = module_output()
    rated = RATED_POWER.to("W").magnitude
    print(
        f"hot summer (35 C air) : cell {m['summer_cell_c']:.0f} C -> {m['summer_power_w']:.0f} W "
        f"({m['summer_power_w'] / rated:.0%} of 400 W)"
    )
    print(
        f"cool spring (15 C air) : cell {m['spring_cell_c']:.0f} C -> {m['spring_power_w']:.0f} W "
        f"({m['spring_power_w'] / rated:.0%})"
    )
    print("  -> the hotter cell gives less power at the same sun; size on operating output")


if __name__ == "__main__":
    main()
