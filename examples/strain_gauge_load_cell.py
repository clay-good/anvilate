"""Worked example: reading strain off a Wheatstone bridge and turning it into stress.

A strain gauge converts strain into a resistance change; a Wheatstone bridge converts that into a
voltage a data logger can read. This example runs the chain both ways. Forward: predict what a
bridge outputs for a known strain, so an instrument's range and resolution can be sized. Backward:
take a measured bridge voltage and recover the strain — and, through Hooke's law, the stress the
part is actually carrying.

A steel tension coupon (E = 200 GPa) is loaded to 1000 microstrain (0.001). With standard GF = 2.0
foil gauges, a quarter bridge outputs 0.5 mV per volt of excitation, and a full bridge — four active
arms — outputs 2.0 mV/V, four times the signal for the same strain, which is why load cells use full
bridges. Reading the 2.0 mV/V back through the full-bridge inverse recovers the 1000 microstrain,
and E times that strain is a 200 MPa working stress. The example reports the quarter- and
full-bridge outputs and the stress recovered from the full-bridge reading.

Run it directly (``python examples/strain_gauge_load_cell.py``);
:func:`read_load_cell` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gauge_strain_from_resistance,
    strain_from_bridge_output,
    wheatstone_bridge_output,
)
from anvilate.units import Quantity

GAUGE_FACTOR = 2.0
APPLIED_STRAIN = 0.001  # 1000 microstrain
ELASTIC_MODULUS = Quantity.parse("200 GPa")


def read_load_cell() -> dict[str, float]:
    """Return the quarter/full-bridge outputs and the stress recovered from the full-bridge read."""
    quarter_output = wheatstone_bridge_output(
        gauge_factor=GAUGE_FACTOR, strain=APPLIED_STRAIN, active_arms=1
    )
    full_output = wheatstone_bridge_output(
        gauge_factor=GAUGE_FACTOR, strain=APPLIED_STRAIN, active_arms=4
    )
    # Confirm the gauge's own definition matches the bridge model: dR/R = GF * strain.
    recovered_from_resistance = gauge_strain_from_resistance(
        resistance_change_ratio=GAUGE_FACTOR * APPLIED_STRAIN, gauge_factor=GAUGE_FACTOR
    )
    measured_strain = strain_from_bridge_output(
        output_ratio=full_output, gauge_factor=GAUGE_FACTOR, active_arms=4
    )
    stress = ELASTIC_MODULUS.to("Pa").magnitude * measured_strain
    return {
        "quarter_bridge_mv_per_v": quarter_output * 1000.0,
        "full_bridge_mv_per_v": full_output * 1000.0,
        "recovered_strain": recovered_from_resistance,
        "stress_mpa": stress / 1e6,
    }


def main() -> None:
    d = read_load_cell()
    print(f"quarter-bridge output: {d['quarter_bridge_mv_per_v']:.2f} mV/V")
    print(f"full-bridge output:    {d['full_bridge_mv_per_v']:.2f} mV/V")
    print(f"stress from full-bridge reading: {d['stress_mpa']:.0f} MPa")


if __name__ == "__main__":
    main()
