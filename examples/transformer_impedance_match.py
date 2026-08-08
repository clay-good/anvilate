"""Worked example: what an ideal transformer does to voltage, current, and impedance.

An ideal transformer trades voltage for current at its turns ratio while passing the power through
unchanged, and in doing so it also transforms impedance by the square of that ratio. The last effect
is what makes a transformer an impedance-matching device — the reason a small speaker transformer or
an antenna balun exists. This example runs all three transformations for one step-down transformer.

The transformer has a 10:1 turns ratio and a 240 V primary. The secondary sees 240/10 = 24 V, and a
1 A primary current becomes 10 A on the secondary — voltage down tenfold, current up tenfold, so the
240 W flows through both sides intact. An 8 ohm load on the 24 V secondary, however, looks like
10^2 * 8 = 800 ohm from the primary: the turns ratio squared reflects the low load impedance up to a
high one, which is exactly how a source is matched to a mismatched load. The example reports the
secondary voltage, the secondary current, and the impedance the primary sees.

Run it directly (``python examples/transformer_impedance_match.py``);
:func:`transformer_ports` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    transformer_reflected_impedance,
    transformer_secondary_current,
    transformer_secondary_voltage,
)
from anvilate.units import Quantity

TURNS_RATIO = 10.0  # N_primary : N_secondary
PRIMARY_VOLTAGE = Quantity.parse("240 V")
PRIMARY_CURRENT = Quantity.parse("1 A")
SECONDARY_LOAD = Quantity.parse("8 ohm")


def transformer_ports() -> dict[str, float]:
    """Return the secondary voltage, the secondary current, and the reflected primary impedance."""
    v_s = transformer_secondary_voltage(primary_voltage=PRIMARY_VOLTAGE, turns_ratio=TURNS_RATIO)
    i_s = transformer_secondary_current(primary_current=PRIMARY_CURRENT, turns_ratio=TURNS_RATIO)
    z_p = transformer_reflected_impedance(
        secondary_impedance=SECONDARY_LOAD, turns_ratio=TURNS_RATIO
    )
    return {
        "secondary_voltage_v": v_s.to("V").magnitude,
        "secondary_current_a": i_s.to("A").magnitude,
        "reflected_impedance_ohm": z_p.to("ohm").magnitude,
    }


def main() -> None:
    d = transformer_ports()
    print(f"secondary voltage: {d['secondary_voltage_v']:.0f} V")
    print(f"secondary current: {d['secondary_current_a']:.0f} A")
    print(f"impedance seen at primary: {d['reflected_impedance_ohm']:.0f} ohm")


if __name__ == "__main__":
    main()
