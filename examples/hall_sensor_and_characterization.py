"""Worked example: a Hall sensor reading a field, and a Hall measurement revealing a semiconductor.

The Hall effect serves two jobs from one relation. As a sensor, a calibrated Hall element turns a
magnetic field into a voltage, so a measured voltage reports the field — the contactless
magnetometer inside brushless-motor commutation and current clamps. As a lab measurement, applying a
known field
and current and reading the voltage reveals a semiconductor's carrier density (and, from the voltage
sign, whether it conducts by electrons or holes).

This example uses a thin n-type Hall element: 0.5 mm thick, carrier density 1e22 /m^3, biased at
1 mA. Placed in a 0.1 T field it develops about 0.125 mV across it — a small but readily amplified
signal, and much larger than a metal would give because the element is thin and lightly doped. Fed
back through the magnetometer inverse, that 0.125 mV recovers the 0.1 T field. Running the
characterization inverse on the same voltage recovers the 1e22 /m^3 carrier density. The example
reports the Hall voltage, the field recovered from it, and the carrier density recovered from it.

Run it directly (``python examples/hall_sensor_and_characterization.py``);
:func:`hall_readings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hall_carrier_density,
    hall_flux_density_from_voltage,
    hall_voltage,
)
from anvilate.units import Quantity

BIAS_CURRENT = Quantity.parse("1 mA")
FIELD = Quantity.parse("0.1 T")
CARRIER_DENSITY = Quantity(magnitude=1e22, unit="1/m**3")
THICKNESS = Quantity.parse("0.5 mm")


def hall_readings() -> dict[str, float]:
    """Return the Hall voltage, the field recovered from it, and the carrier density recovered."""
    voltage = hall_voltage(
        current=BIAS_CURRENT,
        flux_density=FIELD,
        carrier_density=CARRIER_DENSITY,
        thickness=THICKNESS,
    )
    recovered_field = hall_flux_density_from_voltage(
        hall_voltage=voltage,
        current=BIAS_CURRENT,
        carrier_density=CARRIER_DENSITY,
        thickness=THICKNESS,
    )
    recovered_density = hall_carrier_density(
        current=BIAS_CURRENT,
        flux_density=FIELD,
        thickness=THICKNESS,
        hall_voltage=voltage,
    )
    return {
        "hall_voltage_mv": voltage.to("mV").magnitude,
        "recovered_field_t": recovered_field.to("T").magnitude,
        "recovered_carrier_density": recovered_density.to("1/m**3").magnitude,
    }


def main() -> None:
    d = hall_readings()
    print(f"Hall voltage at 0.1 T: {d['hall_voltage_mv']:.3f} mV")
    print(f"field recovered from that voltage: {d['recovered_field_t']:.3f} T")
    print(f"carrier density recovered: {d['recovered_carrier_density']:.3e} /m^3")


if __name__ == "__main__":
    main()
